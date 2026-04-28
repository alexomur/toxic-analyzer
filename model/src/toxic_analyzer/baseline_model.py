"""Baseline text classifier for mixed-domain toxicity detection."""

from __future__ import annotations

import math
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.sparse import csr_matrix
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
from toxic_analyzer.baseline_features import (
    FEATURE_NAMES,
    ExpertFeatureDiagnostics,
    ExpertFeatureTransformer,
)
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
    toxic_probability: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "label": self.label,
            "toxic_probability": round(self.toxic_probability, 6),
        }


@dataclass(slots=True)
class FeatureContribution:
    feature_group: str
    feature_name: str
    feature_value: float
    feature_weight: float
    contribution: float

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_group": self.feature_group,
            "feature_name": self.feature_name,
            "feature_value": round(self.feature_value, 6),
            "feature_weight": round(self.feature_weight, 6),
            "contribution": round(self.contribution, 6),
        }


@dataclass(slots=True)
class TriggeredExpertFeature:
    feature_name: str
    feature_value: float
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_name": self.feature_name,
            "feature_value": round(self.feature_value, 6),
            "reasons": list(self.reasons),
        }


@dataclass(slots=True)
class AppliedAdjustment:
    adjustment_name: str
    delta: float
    trigger_features: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "adjustment_name": self.adjustment_name,
            "delta": round(self.delta, 6),
            "trigger_features": list(self.trigger_features),
        }


@dataclass(slots=True)
class ToxicityExplanation:
    canonical_tokens: list[str]
    top_positive_features: list[FeatureContribution]
    top_negative_features: list[FeatureContribution]
    triggered_expert_features: list[TriggeredExpertFeature]
    applied_adjustments: list[AppliedAdjustment]

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_tokens": list(self.canonical_tokens),
            "top_positive_features": [item.to_dict() for item in self.top_positive_features],
            "top_negative_features": [item.to_dict() for item in self.top_negative_features],
            "triggered_expert_features": [
                item.to_dict() for item in self.triggered_expert_features
            ],
            "applied_adjustments": [item.to_dict() for item in self.applied_adjustments],
        }


@dataclass(slots=True)
class ExplainedToxicityPrediction:
    label: int
    toxic_probability: float
    raw_model_probability: float
    calibrated_probability: float
    posthoc_adjusted_probability: float
    threshold: float
    explanation: ToxicityExplanation

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "toxic_probability": round(self.toxic_probability, 6),
            "raw_model_probability": round(self.raw_model_probability, 6),
            "calibrated_probability": round(self.calibrated_probability, 6),
            "posthoc_adjusted_probability": round(self.posthoc_adjusted_probability, 6),
            "threshold": round(self.threshold, 6),
            "explanation": self.explanation.to_dict(),
        }


@dataclass(slots=True)
class _FeatureDescriptor:
    feature_group: str
    feature_name: str


@dataclass(slots=True)
class ToxicityBaselineModel:
    pipeline: Pipeline
    calibrator: Any
    threshold: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def _get_expert_transformer(self) -> ExpertFeatureTransformer | None:
        features_step = self.pipeline.named_steps["features"]
        if isinstance(features_step, FeatureUnion):
            for name, transformer in features_step.transformer_list:
                if name == "expert_features" and isinstance(transformer, ExpertFeatureTransformer):
                    return transformer
            return None
        if isinstance(features_step, ExpertFeatureTransformer):
            return features_step
        return None

    def _supports_v3_adjustments(self) -> bool:
        return str(self.metadata.get("model_version", "")).lower() in {"v3", "v3.1", "v3.2", "v3.3"}

    def _get_feature_value_map(
        self,
        diagnostics: ExpertFeatureDiagnostics,
    ) -> dict[str, float]:
        return {item.feature_name: item.feature_value for item in diagnostics.triggered_features}

    def _compute_v3_adjustments(
        self,
        diagnostics: ExpertFeatureDiagnostics,
        probability: float,
    ) -> tuple[float, list[AppliedAdjustment]]:
        feature_values = self._get_feature_value_map(diagnostics)
        token_count = float(feature_values.get("token_count", 0.0))
        has_untargeted_harm = bool(feature_values.get("has_untargeted_harm", 0.0))
        has_targeted_harm = bool(feature_values.get("has_targeted_harm", 0.0))
        has_second_person_negated_insult = bool(
            feature_values.get("has_second_person_negated_insult", 0.0)
        )
        has_pronoun_insult = bool(feature_values.get("has_pronoun_insult", 0.0))
        strong_insult_count = float(feature_values.get("strong_insult_count", 0.0))
        profane_count = float(feature_values.get("profane_count", 0.0))

        adjusted_probability = float(probability)
        adjustments: list[AppliedAdjustment] = []

        if has_untargeted_harm and not has_targeted_harm and token_count <= 4:
            adjusted_probability -= 0.18
            adjustments.append(
                AppliedAdjustment(
                    adjustment_name="short_untargeted_harm",
                    delta=-0.18,
                    trigger_features=["has_untargeted_harm", "token_count"],
                )
            )
            if token_count <= 1:
                adjusted_probability -= 0.18
                adjustments.append(
                    AppliedAdjustment(
                        adjustment_name="short_untargeted_harm_single_token_extra",
                        delta=-0.18,
                        trigger_features=["has_untargeted_harm", "token_count"],
                    )
                )

        if (
            has_second_person_negated_insult
            and not has_pronoun_insult
            and strong_insult_count == 0.0
            and profane_count == 0.0
        ):
            adjusted_probability -= 0.35
            adjustments.append(
                AppliedAdjustment(
                    adjustment_name="second_person_negated_insult",
                    delta=-0.35,
                    trigger_features=[
                        "has_second_person_negated_insult",
                        "has_pronoun_insult",
                        "strong_insult_count",
                        "profane_count",
                    ],
                )
            )

        return float(np.clip(adjusted_probability, 0.0, 1.0)), adjustments

    def _apply_v3_probability_adjustments(
        self,
        texts: Sequence[str],
        probabilities: np.ndarray,
    ) -> np.ndarray:
        transformer = self._get_expert_transformer() or ExpertFeatureTransformer()
        adjusted = probabilities.astype(float, copy=True)
        for row_index, text in enumerate(texts):
            diagnostics = transformer.analyze_text(text)
            adjusted[row_index], _ = self._compute_v3_adjustments(diagnostics, adjusted[row_index])
        return adjusted

    def _build_feature_descriptors(self) -> list[_FeatureDescriptor]:
        features_step = self.pipeline.named_steps["features"]
        if isinstance(features_step, FeatureUnion):
            descriptors: list[_FeatureDescriptor] = []
            for name, transformer in features_step.transformer_list:
                descriptors.extend(self._build_transformer_descriptors(name, transformer))
            return descriptors
        return self._build_transformer_descriptors("features", features_step)

    def _build_transformer_descriptors(
        self,
        transformer_name: str,
        transformer: Any,
    ) -> list[_FeatureDescriptor]:
        if transformer_name == "selected_text_features" or (
            isinstance(transformer, Pipeline) and "tfidf_features" in transformer.named_steps
        ):
            return self._build_selected_text_descriptors(transformer)
        if transformer_name == "expert_features":
            names = transformer.get_feature_names_out().tolist()
            return [_FeatureDescriptor("expert_feature", str(name)) for name in names]
        if isinstance(transformer, TfidfVectorizer):
            group = "word_ngram" if transformer.analyzer == "word" else "char_ngram"
            return [
                _FeatureDescriptor(group, str(name))
                for name in transformer.get_feature_names_out().tolist()
            ]
        if isinstance(transformer, ExpertFeatureTransformer):
            return [
                _FeatureDescriptor("expert_feature", str(name))
                for name in transformer.get_feature_names_out().tolist()
            ]
        raise TypeError(f"Unsupported transformer for explanation: {transformer_name}")

    def _build_selected_text_descriptors(self, transformer: Any) -> list[_FeatureDescriptor]:
        if isinstance(transformer, Pipeline):
            tfidf_union = transformer.named_steps["tfidf_features"]
            base_names = tfidf_union.get_feature_names_out().tolist()
            selector = transformer.named_steps["select_k_best"]
            support = selector.get_support(indices=True)
            selected_names = [str(base_names[index]) for index in support]
        else:
            selected_names = [str(name) for name in transformer.get_feature_names_out().tolist()]

        descriptors: list[_FeatureDescriptor] = []
        for full_name in selected_names:
            if full_name.startswith("word_tfidf__"):
                descriptors.append(
                    _FeatureDescriptor("word_ngram", full_name.removeprefix("word_tfidf__"))
                )
            elif full_name.startswith("char_tfidf__"):
                descriptors.append(
                    _FeatureDescriptor("char_ngram", full_name.removeprefix("char_tfidf__"))
                )
            else:
                raise ValueError(f"Unexpected text feature name: {full_name}")
        return descriptors

    def _compute_raw_probability(self, feature_row: csr_matrix) -> tuple[float, np.ndarray]:
        classifier: LogisticRegression = self.pipeline.named_steps["classifier"]
        coefficients = classifier.coef_[0]
        logit = float(feature_row.dot(coefficients).item() + classifier.intercept_[0])
        probability = 1.0 / (1.0 + math.exp(-logit))
        return probability, coefficients

    def _extract_ranked_contributions(
        self,
        feature_row: csr_matrix,
        coefficients: np.ndarray,
        descriptors: Sequence[_FeatureDescriptor],
        *,
        top_n: int,
    ) -> tuple[list[FeatureContribution], list[FeatureContribution]]:
        coo_row = feature_row.tocoo()
        contributions: list[FeatureContribution] = []
        for value, column_index in zip(coo_row.data.tolist(), coo_row.col.tolist(), strict=True):
            weight = float(coefficients[column_index])
            contribution = float(value) * weight
            descriptor = descriptors[column_index]
            contributions.append(
                FeatureContribution(
                    feature_group=descriptor.feature_group,
                    feature_name=descriptor.feature_name,
                    feature_value=float(value),
                    feature_weight=weight,
                    contribution=contribution,
                )
            )

        positive = sorted(
            [item for item in contributions if item.contribution > 0.0],
            key=lambda item: item.contribution,
            reverse=True,
        )[:top_n]
        negative = sorted(
            [item for item in contributions if item.contribution < 0.0],
            key=lambda item: item.contribution,
        )[:top_n]
        return positive, negative

    def predict_one_explained(self, text: str, *, top_n: int = 10) -> ExplainedToxicityPrediction:
        features_step = self.pipeline.named_steps["features"]
        feature_row = features_step.transform([text])
        raw_probability, coefficients = self._compute_raw_probability(feature_row)
        calibrated_probability = float(self.calibrator.predict([raw_probability])[0])

        transformer = self._get_expert_transformer() or ExpertFeatureTransformer()
        diagnostics = transformer.analyze_text(text)
        adjusted_probability = calibrated_probability
        adjustments: list[AppliedAdjustment] = []
        if self._supports_v3_adjustments():
            adjusted_probability, adjustments = self._compute_v3_adjustments(
                diagnostics,
                calibrated_probability,
            )

        descriptors = self._build_feature_descriptors()
        positive_features, negative_features = self._extract_ranked_contributions(
            feature_row,
            coefficients,
            descriptors,
            top_n=top_n,
        )
        label = int(adjusted_probability >= self.threshold)
        explanation = ToxicityExplanation(
            canonical_tokens=list(diagnostics.canonical_tokens),
            top_positive_features=positive_features,
            top_negative_features=negative_features,
            triggered_expert_features=[
                TriggeredExpertFeature(
                    feature_name=item.feature_name,
                    feature_value=item.feature_value,
                    reasons=list(item.reasons),
                )
                for item in diagnostics.triggered_features
                if item.feature_name != "token_count" or item.feature_value > 0.0
            ],
            applied_adjustments=adjustments,
        )
        return ExplainedToxicityPrediction(
            label=label,
            toxic_probability=float(adjusted_probability),
            raw_model_probability=float(raw_probability),
            calibrated_probability=float(calibrated_probability),
            posthoc_adjusted_probability=float(adjusted_probability),
            threshold=float(self.threshold),
            explanation=explanation,
        )

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
            predictions.append(
                ToxicityPrediction(
                    label=label,
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
            "model_version": "v3.3",
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
        "model_version": "v3.3",
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
