"""Baseline text classifier for mixed-domain toxicity detection."""

from __future__ import annotations

import math
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectKBest, chi2
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import FeatureUnion, Pipeline

from toxic_analyzer.baseline_data import DatasetBundle, DatasetSplit
from toxic_analyzer.baseline_features import FEATURE_NAMES, ExpertFeatureTransformer
from toxic_analyzer.hard_case_dataset import HardCaseDataset


@dataclass(slots=True)
class BaselineTrainingConfig:
    random_seed: int = 42
    logistic_c: float = 4.0
    logistic_max_iter: int = 1000
    min_df: int = 2
    word_ngram_range: tuple[int, int] = (1, 2)
    char_ngram_range: tuple[int, int] = (3, 5)
    max_word_features: int | None = 100_000
    max_char_features: int | None = 150_000
    select_k_best: int = 120_000
    threshold_grid_size: int = 181
    use_expert_features: bool = True
    calibration_method: str = "sigmoid"

    def to_summary(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ToxicityPrediction:
    label: int
    score: float
    toxic_probability: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "label": self.label,
            "score": round(self.score, 6),
            "toxic_probability": round(self.toxic_probability, 6),
        }


@dataclass(slots=True)
class ToxicityBaselineModel:
    pipeline: Pipeline
    calibrator: Any
    threshold: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def _supports_v3_adjustments(self) -> bool:
        return str(self.metadata.get("model_version", "")).lower() in {"v3", "v3.1", "v3.2"}

    def _apply_v3_probability_adjustments(
        self,
        texts: Sequence[str],
        probabilities: np.ndarray,
    ) -> np.ndarray:
        transformer = ExpertFeatureTransformer()
        feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}
        feature_matrix = transformer.transform(texts).toarray()
        adjusted = probabilities.astype(float, copy=True)
        for row_index, feature_row in enumerate(feature_matrix):
            token_count = float(feature_row[feature_index["token_count"]])
            has_untargeted_harm = bool(feature_row[feature_index["has_untargeted_harm"]])
            has_targeted_harm = bool(feature_row[feature_index["has_targeted_harm"]])
            has_second_person_negated_insult = bool(
                feature_row[feature_index["has_second_person_negated_insult"]]
            )
            has_pronoun_insult = bool(feature_row[feature_index["has_pronoun_insult"]])
            strong_insult_count = float(feature_row[feature_index["strong_insult_count"]])
            profane_count = float(feature_row[feature_index["profane_count"]])

            if has_untargeted_harm and not has_targeted_harm and token_count <= 4:
                adjusted[row_index] -= 0.18
                if token_count <= 1:
                    adjusted[row_index] -= 0.18

            if (
                has_second_person_negated_insult
                and not has_pronoun_insult
                and strong_insult_count == 0.0
                and profane_count == 0.0
            ):
                adjusted[row_index] -= 0.35

        return np.clip(adjusted, 0.0, 1.0)

    def predict_toxic_probabilities(self, texts: Sequence[str]) -> list[float]:
        raw_probabilities = self.pipeline.predict_proba(list(texts))[:, 1]
        calibrated = self.calibrator.predict(raw_probabilities)
        clipped = np.clip(calibrated, 0.0, 1.0)
        if self._supports_v3_adjustments():
            clipped = self._apply_v3_probability_adjustments(texts, clipped)
        return [float(value) for value in clipped]

    def predict(self, texts: Sequence[str]) -> list[ToxicityPrediction]:
        probabilities = self.predict_toxic_probabilities(texts)
        predictions: list[ToxicityPrediction] = []
        for probability in probabilities:
            label = int(probability >= self.threshold)
            score = probability if label == 1 else 1.0 - probability
            predictions.append(
                ToxicityPrediction(
                    label=label,
                    score=float(score),
                    toxic_probability=float(probability),
                )
            )
        return predictions

    def predict_one(self, text: str) -> ToxicityPrediction:
        return self.predict([text])[0]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pipeline": self.pipeline,
            "calibrator": self.calibrator,
            "threshold": self.threshold,
            "metadata": self.metadata,
        }
        with path.open("wb") as handle:
            pickle.dump(payload, handle)

    @classmethod
    def load(cls, path: Path) -> "ToxicityBaselineModel":
        with path.open("rb") as handle:
            payload = pickle.load(handle)
        return cls(
            pipeline=payload["pipeline"],
            calibrator=payload["calibrator"],
            threshold=float(payload["threshold"]),
            metadata=dict(payload.get("metadata") or {}),
        )


class ProbabilityCalibrator(BaseEstimator):
    def fit(self, probabilities: Sequence[float], labels: Sequence[int]) -> "ProbabilityCalibrator":
        raise NotImplementedError

    def predict(self, probabilities: Sequence[float]) -> np.ndarray:
        raise NotImplementedError

    @property
    def method_name(self) -> str:
        raise NotImplementedError


class IsotonicProbabilityCalibrator(ProbabilityCalibrator):
    def __init__(self) -> None:
        self.model = IsotonicRegression(out_of_bounds="clip")

    def fit(
        self,
        probabilities: Sequence[float],
        labels: Sequence[int],
    ) -> "IsotonicProbabilityCalibrator":
        self.model.fit(np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=int))
        return self

    def predict(self, probabilities: Sequence[float]) -> np.ndarray:
        calibrated = self.model.predict(np.asarray(probabilities, dtype=float))
        return np.clip(calibrated, 0.0, 1.0)

    @property
    def method_name(self) -> str:
        return "isotonic"


class SigmoidProbabilityCalibrator(ProbabilityCalibrator):
    def __init__(self, random_seed: int = 42) -> None:
        self.random_seed = random_seed
        self.model = LogisticRegression(random_state=random_seed, solver="lbfgs")

    @staticmethod
    def _to_logit(probabilities: Sequence[float]) -> np.ndarray:
        array = np.asarray(probabilities, dtype=float)
        clipped = np.clip(array, 1e-6, 1.0 - 1e-6)
        return np.log(clipped / (1.0 - clipped)).reshape(-1, 1)

    def fit(
        self,
        probabilities: Sequence[float],
        labels: Sequence[int],
    ) -> "SigmoidProbabilityCalibrator":
        self.model.fit(self._to_logit(probabilities), np.asarray(labels, dtype=int))
        return self

    def predict(self, probabilities: Sequence[float]) -> np.ndarray:
        calibrated = self.model.predict_proba(self._to_logit(probabilities))[:, 1]
        return np.clip(calibrated, 0.0, 1.0)

    @property
    def method_name(self) -> str:
        return "sigmoid"


def build_probability_calibrator(config: BaselineTrainingConfig) -> ProbabilityCalibrator:
    if config.calibration_method == "isotonic":
        return IsotonicProbabilityCalibrator()
    if config.calibration_method == "sigmoid":
        return SigmoidProbabilityCalibrator(random_seed=config.random_seed)
    raise ValueError(
        "Unsupported calibration_method. "
        f"Expected 'isotonic' or 'sigmoid', got {config.calibration_method!r}."
    )


def build_baseline_pipeline(config: BaselineTrainingConfig) -> Pipeline:
    word_vectorizer = TfidfVectorizer(
        analyzer="word",
        lowercase=True,
        ngram_range=config.word_ngram_range,
        token_pattern=r"(?u)\b\w+\b",
        min_df=config.min_df,
        sublinear_tf=True,
        max_features=config.max_word_features,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        lowercase=True,
        ngram_range=config.char_ngram_range,
        min_df=config.min_df,
        sublinear_tf=True,
        max_features=config.max_char_features,
    )
    text_features = FeatureUnion(
        [
            ("word_tfidf", word_vectorizer),
            ("char_tfidf", char_vectorizer),
        ]
    )
    selected_text_features: Any = text_features
    if config.select_k_best > 0:
        selected_text_features = Pipeline(
            [
                ("tfidf_features", text_features),
                ("select_k_best", SelectKBest(score_func=chi2, k=config.select_k_best)),
            ]
        )
    feature_blocks: list[tuple[str, Any]] = [("selected_text_features", selected_text_features)]
    if config.use_expert_features:
        feature_blocks.append(("expert_features", ExpertFeatureTransformer()))
    features: Any
    if len(feature_blocks) == 1:
        features = selected_text_features
    else:
        features = FeatureUnion(feature_blocks)
    steps: list[tuple[str, Any]] = [("features", features)]
    steps.append(
        (
            "classifier",
            LogisticRegression(
                C=config.logistic_c,
                max_iter=config.logistic_max_iter,
                random_state=config.random_seed,
                solver="liblinear",
            ),
        )
    )
    return Pipeline(steps)


def _safe_scalar_metric(
    metric_fn: Any,
    labels: Sequence[int],
    probabilities: np.ndarray,
) -> float | None:
    try:
        return float(metric_fn(labels, probabilities))
    except ValueError:
        return None


def compute_binary_metrics(
    labels: Sequence[int],
    probabilities: Sequence[float],
    *,
    threshold: float,
) -> dict[str, float | int | None]:
    probability_array = np.asarray(probabilities, dtype=float)
    label_array = np.asarray(labels, dtype=int)
    prediction_array = (probability_array >= threshold).astype(int)
    positive_count = int(np.sum(prediction_array == 1))
    negative_count = int(np.sum(prediction_array == 0))
    unique_labels = set(label_array.tolist())
    average_precision = None
    if int(np.sum(label_array == 1)) > 0:
        average_precision = _safe_scalar_metric(
            average_precision_score,
            label_array,
            probability_array,
        )
    roc_auc = None
    if len(unique_labels) > 1:
        roc_auc = _safe_scalar_metric(roc_auc_score, label_array, probability_array)
    return {
        "rows": int(len(labels)),
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(label_array, prediction_array)),
        "precision": float(precision_score(label_array, prediction_array, zero_division=0)),
        "recall": float(recall_score(label_array, prediction_array, zero_division=0)),
        "f1": float(f1_score(label_array, prediction_array, zero_division=0)),
        "average_precision": average_precision,
        "roc_auc": roc_auc,
        "brier_score": float(brier_score_loss(label_array, probability_array)),
        "predicted_positive": positive_count,
        "predicted_negative": negative_count,
        "positive_rate": float(np.mean(probability_array >= threshold)),
    }


def compute_split_metrics(
    split: DatasetSplit,
    model: ToxicityBaselineModel,
) -> dict[str, Any]:
    probabilities = np.asarray(model.predict_toxic_probabilities(split.texts), dtype=float)
    per_source: dict[str, Any] = {}
    for source in sorted(set(split.sources)):
        indices = [
            index for index, split_source in enumerate(split.sources) if split_source == source
        ]
        source_labels = [split.labels[index] for index in indices]
        source_probabilities = probabilities[indices]
        per_source[source] = compute_binary_metrics(
            source_labels,
            source_probabilities,
            threshold=model.threshold,
        )
    return {
        "summary": split.to_summary(),
        "overall": compute_binary_metrics(split.labels, probabilities, threshold=model.threshold),
        "per_source": per_source,
    }


def compute_hard_case_metrics(
    dataset: HardCaseDataset,
    model: ToxicityBaselineModel,
) -> dict[str, Any]:
    probabilities = np.asarray(model.predict_toxic_probabilities(dataset.texts), dtype=float)
    per_tag: dict[str, Any] = {}
    for tag in dataset.unique_tags:
        indices = [index for index, item in enumerate(dataset.items) if tag in item.tags]
        tag_labels = [dataset.labels[index] for index in indices]
        tag_probabilities = probabilities[indices]
        per_tag[tag] = compute_binary_metrics(
            tag_labels,
            tag_probabilities,
            threshold=model.threshold,
        )
    return {
        "summary": dataset.summary(),
        "overall": compute_binary_metrics(dataset.labels, probabilities, threshold=model.threshold),
        "per_tag": per_tag,
    }


def select_decision_threshold(
    labels: Sequence[int],
    probabilities: Sequence[float],
    *,
    grid_size: int = 181,
) -> dict[str, float]:
    probability_array = np.asarray(probabilities, dtype=float)
    best_threshold = 0.5
    best_f1 = -1.0
    best_precision = -1.0
    candidate_thresholds = np.linspace(0.05, 0.95, num=grid_size)
    for threshold in candidate_thresholds:
        predictions = (probability_array >= threshold).astype(int)
        f1_value = float(f1_score(labels, predictions, zero_division=0))
        precision_value = float(precision_score(labels, predictions, zero_division=0))
        is_better = f1_value > best_f1 + 1e-12
        is_equal_f1 = math.isclose(f1_value, best_f1, rel_tol=0.0, abs_tol=1e-12)
        better_precision = precision_value > best_precision + 1e-12
        closer_to_midpoint = abs(threshold - 0.5) < abs(best_threshold - 0.5)
        if is_better or (is_equal_f1 and better_precision) or (
            is_equal_f1
            and math.isclose(precision_value, best_precision, abs_tol=1e-12)
            and closer_to_midpoint
        ):
            best_threshold = float(threshold)
            best_f1 = f1_value
            best_precision = precision_value
    return {
        "threshold": best_threshold,
        "validation_f1": best_f1,
        "validation_precision": best_precision,
    }


def train_baseline_model(
    dataset_bundle: DatasetBundle,
    *,
    config: BaselineTrainingConfig | None = None,
    hard_case_dataset: HardCaseDataset | None = None,
    seed_dataset: HardCaseDataset | None = None,
) -> tuple[ToxicityBaselineModel, dict[str, Any]]:
    training_config = config or BaselineTrainingConfig()
    pipeline = build_baseline_pipeline(training_config)
    train_texts = list(dataset_bundle.train.texts)
    train_labels = list(dataset_bundle.train.labels)
    if seed_dataset is not None:
        train_texts.extend(seed_dataset.texts)
        train_labels.extend(seed_dataset.labels)
    pipeline.fit(train_texts, train_labels)

    validation_raw_probabilities = pipeline.predict_proba(dataset_bundle.validation.texts)[:, 1]
    calibrator = build_probability_calibrator(training_config)
    calibrator.fit(validation_raw_probabilities, dataset_bundle.validation.labels)
    validation_probabilities = calibrator.predict(validation_raw_probabilities)
    threshold_info = select_decision_threshold(
        dataset_bundle.validation.labels,
        validation_probabilities,
        grid_size=training_config.threshold_grid_size,
    )

    model = ToxicityBaselineModel(
        pipeline=pipeline,
        calibrator=calibrator,
        threshold=float(threshold_info["threshold"]),
        metadata={
            "training_config": training_config.to_summary(),
            "threshold_selection": threshold_info,
            "calibration_method": calibrator.method_name,
            "model_version": "v3.2",
            "posthoc_adjustments": {
                "short_untargeted_harm": {
                    "base_delta": -0.18,
                    "single_token_extra_delta": -0.18,
                },
                "second_person_negated_insult": {
                    "delta": -0.35,
                },
            },
        },
    )
    report = {
        "dataset": dataset_bundle.dataset_stats,
        "training_config": training_config.to_summary(),
        "threshold_selection": threshold_info,
        "calibration_method": calibrator.method_name,
        "model_version": "v3.2",
        "posthoc_adjustments": model.metadata["posthoc_adjustments"],
        "metrics": {
            "train": compute_split_metrics(dataset_bundle.train, model),
            "validation": compute_split_metrics(dataset_bundle.validation, model),
            "test": compute_split_metrics(dataset_bundle.test, model),
        },
    }
    if seed_dataset is not None:
        report["seed_dataset"] = seed_dataset.summary()
    if hard_case_dataset is not None:
        report["hard_cases"] = compute_hard_case_metrics(hard_case_dataset, model)
    return model, report
