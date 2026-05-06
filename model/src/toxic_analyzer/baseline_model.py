"""Baseline text classifier facade for mixed-domain toxicity detection."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.pipeline import Pipeline

from toxic_analyzer.baseline_explainability import (
    AppliedAdjustment,
    ExplainedToxicityPrediction,
    FeatureContribution,
    ToxicityExplanation,
    TriggeredExpertFeature,
    apply_v3_probability_adjustments,
    build_explained_prediction,
    supports_v3_adjustments,
)
from toxic_analyzer.baseline_training import (
    BaselineTrainingConfig,
    IsotonicProbabilityCalibrator,
    ProbabilityCalibrator,
    SigmoidProbabilityCalibrator,
    build_baseline_pipeline,
    build_probability_calibrator,
    compute_binary_metrics,
    compute_hard_case_metrics,
    compute_split_metrics,
    select_decision_threshold,
)
from toxic_analyzer.baseline_training import (
    train_baseline_model as train_baseline_model_impl,
)


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
class ToxicityBaselineModel:
    pipeline: Pipeline
    calibrator: Any
    threshold: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def _supports_v3_adjustments(self) -> bool:
        return supports_v3_adjustments(self.metadata)

    def predict_one_explained(self, text: str, *, top_n: int = 10) -> ExplainedToxicityPrediction:
        return build_explained_prediction(
            pipeline=self.pipeline,
            calibrator=self.calibrator,
            threshold=self.threshold,
            metadata=self.metadata,
            text=text,
            top_n=top_n,
        )

    def predict_toxic_probabilities(self, texts: Sequence[str]) -> list[float]:
        raw_probabilities = self.pipeline.predict_proba(list(texts))[:, 1]
        calibrated = self.calibrator.predict(raw_probabilities)
        clipped = np.clip(calibrated, 0.0, 1.0)
        adjusted = apply_v3_probability_adjustments(
            self.pipeline,
            self.metadata,
            texts,
            clipped,
        )
        return [float(value) for value in adjusted]

    def predict(self, texts: Sequence[str]) -> list[ToxicityPrediction]:
        probabilities = self.predict_toxic_probabilities(texts)
        return [
            ToxicityPrediction(
                label=int(probability >= self.threshold),
                toxic_probability=float(probability),
            )
            for probability in probabilities
        ]

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


def train_baseline_model(
    dataset_bundle: Any,
    *,
    config: BaselineTrainingConfig | None = None,
    hard_case_dataset: Any | None = None,
    seed_dataset: Any | None = None,
) -> tuple[ToxicityBaselineModel, dict[str, Any]]:
    return train_baseline_model_impl(
        dataset_bundle,
        model_factory=ToxicityBaselineModel,
        config=config,
        hard_case_dataset=hard_case_dataset,
        seed_dataset=seed_dataset,
    )


__all__ = [
    "AppliedAdjustment",
    "BaselineTrainingConfig",
    "ExplainedToxicityPrediction",
    "FeatureContribution",
    "IsotonicProbabilityCalibrator",
    "ProbabilityCalibrator",
    "SigmoidProbabilityCalibrator",
    "ToxicityBaselineModel",
    "ToxicityExplanation",
    "ToxicityPrediction",
    "TriggeredExpertFeature",
    "build_baseline_pipeline",
    "build_probability_calibrator",
    "compute_binary_metrics",
    "compute_hard_case_metrics",
    "compute_split_metrics",
    "select_decision_threshold",
    "train_baseline_model",
]
