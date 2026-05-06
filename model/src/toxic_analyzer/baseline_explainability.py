"""Explainability and posthoc adjustment helpers for the baseline model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline

from toxic_analyzer.baseline_features import ExpertFeatureDiagnostics, ExpertFeatureTransformer


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


def get_expert_transformer(pipeline: Pipeline) -> ExpertFeatureTransformer | None:
    features_step = pipeline.named_steps["features"]
    if isinstance(features_step, FeatureUnion):
        for name, transformer in features_step.transformer_list:
            if name == "expert_features" and isinstance(transformer, ExpertFeatureTransformer):
                return transformer
        return None
    if isinstance(features_step, ExpertFeatureTransformer):
        return features_step
    return None


def supports_v3_adjustments(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("model_version", "")).lower() in {
        "v3",
        "v3.1",
        "v3.2",
        "v3.3",
        "v3.4",
    }


def get_feature_value_map(diagnostics: ExpertFeatureDiagnostics) -> dict[str, float]:
    return {item.feature_name: item.feature_value for item in diagnostics.triggered_features}


def compute_v3_adjustments(
    diagnostics: ExpertFeatureDiagnostics,
    probability: float,
) -> tuple[float, list[AppliedAdjustment]]:
    feature_values = get_feature_value_map(diagnostics)
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


def apply_v3_probability_adjustments(
    pipeline: Pipeline,
    metadata: dict[str, Any],
    texts: Sequence[str],
    probabilities: np.ndarray,
) -> np.ndarray:
    transformer = get_expert_transformer(pipeline) or ExpertFeatureTransformer()
    adjusted = probabilities.astype(float, copy=True)
    for row_index, text in enumerate(texts):
        diagnostics = transformer.analyze_text(text)
        adjusted[row_index], _ = compute_v3_adjustments(diagnostics, adjusted[row_index])
    return adjusted if supports_v3_adjustments(metadata) else probabilities


def build_feature_descriptors(pipeline: Pipeline) -> list[_FeatureDescriptor]:
    features_step = pipeline.named_steps["features"]
    if isinstance(features_step, FeatureUnion):
        descriptors: list[_FeatureDescriptor] = []
        for name, transformer in features_step.transformer_list:
            descriptors.extend(build_transformer_descriptors(name, transformer))
        return descriptors
    return build_transformer_descriptors("features", features_step)


def build_transformer_descriptors(
    transformer_name: str,
    transformer: Any,
) -> list[_FeatureDescriptor]:
    if transformer_name == "selected_text_features" or (
        isinstance(transformer, Pipeline) and "tfidf_features" in transformer.named_steps
    ):
        return build_selected_text_descriptors(transformer)
    if transformer_name == "expert_features":
        names = transformer.get_feature_names_out().tolist()
        return [_FeatureDescriptor("expert_feature", str(name)) for name in names]
    if isinstance(transformer, TfidfVectorizer):
        group = "word_ngram" if transformer.analyzer == "word" else "char_ngram"
        return [
            _FeatureDescriptor(group, str(name))
            for name in transformer.get_feature_names_out()
        ]
    if isinstance(transformer, ExpertFeatureTransformer):
        return [
            _FeatureDescriptor("expert_feature", str(name))
            for name in transformer.get_feature_names_out()
        ]
    raise TypeError(f"Unsupported transformer for explanation: {transformer_name}")


def build_selected_text_descriptors(transformer: Any) -> list[_FeatureDescriptor]:
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


def compute_raw_probability(
    pipeline: Pipeline,
    feature_row: csr_matrix,
) -> tuple[float, np.ndarray]:
    classifier = pipeline.named_steps["classifier"]
    coefficients = classifier.coef_[0]
    logit = float(feature_row.dot(coefficients).item() + classifier.intercept_[0])
    probability = 1.0 / (1.0 + math.exp(-logit))
    return probability, coefficients


def extract_ranked_contributions(
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


def build_explained_prediction(
    *,
    pipeline: Pipeline,
    calibrator: Any,
    threshold: float,
    metadata: dict[str, Any],
    text: str,
    top_n: int = 10,
) -> ExplainedToxicityPrediction:
    features_step = pipeline.named_steps["features"]
    feature_row = features_step.transform([text])
    raw_probability, coefficients = compute_raw_probability(pipeline, feature_row)
    calibrated_probability = float(calibrator.predict([raw_probability])[0])

    transformer = get_expert_transformer(pipeline) or ExpertFeatureTransformer()
    diagnostics = transformer.analyze_text(text)
    adjusted_probability = calibrated_probability
    adjustments: list[AppliedAdjustment] = []
    if supports_v3_adjustments(metadata):
        adjusted_probability, adjustments = compute_v3_adjustments(
            diagnostics,
            calibrated_probability,
        )

    descriptors = build_feature_descriptors(pipeline)
    positive_features, negative_features = extract_ranked_contributions(
        feature_row,
        coefficients,
        descriptors,
        top_n=top_n,
    )
    label = int(adjusted_probability >= threshold)
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
        threshold=float(threshold),
        explanation=explanation,
    )
