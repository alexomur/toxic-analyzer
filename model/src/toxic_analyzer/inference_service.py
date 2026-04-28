"""Service layer for model inference, ready to be reused by future FastAPI handlers."""


from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from toxic_analyzer.baseline_model import (
    ExplainedToxicityPrediction,
    ToxicityBaselineModel,
    ToxicityPrediction,
)
from toxic_analyzer.model_runtime import (
    DEFAULT_ARTIFACT_PATHS,
    DEFAULT_MODEL_PATH,
    ModelArtifactPaths,
    load_baseline_model,
)


@dataclass(slots=True)
class BatchPredictionItem:
    text: str
    prediction: ToxicityPrediction

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "prediction": self.prediction.to_dict(),
        }


@dataclass(slots=True)
class ModelInfo:
    model_path: str | None
    model_version: str | None
    threshold: float
    calibration_method: str | None
    training_config: dict[str, Any] | None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_path": self.model_path,
            "model_version": self.model_version,
            "threshold": round(self.threshold, 6),
            "calibration_method": self.calibration_method,
            "training_config": self.training_config,
        }


@dataclass(slots=True)
class ModelIdentity:
    model_key: str
    model_version: str

    def to_dict(self) -> dict[str, str]:
        return {
            "model_key": self.model_key,
            "model_version": self.model_version,
        }


@dataclass(slots=True)
class ToxicityInferenceService:
    model: ToxicityBaselineModel
    model_path: Path | None = None

    @classmethod
    def from_path(
        cls,
        model_path: Path = DEFAULT_MODEL_PATH,
        *,
        artifacts: ModelArtifactPaths = DEFAULT_ARTIFACT_PATHS,
    ) -> "ToxicityInferenceService":
        model, resolved_path = load_baseline_model(model_path, artifacts=artifacts)
        return cls(model=model, model_path=resolved_path)

    def predict_one(self, text: str) -> ToxicityPrediction:
        return self.model.predict_one(text)

    def predict_many(self, texts: Sequence[str]) -> list[ToxicityPrediction]:
        return self.model.predict(list(texts))

    def predict_one_explained(self, text: str, *, top_n: int = 10) -> ExplainedToxicityPrediction:
        return self.model.predict_one_explained(text, top_n=top_n)

    def predict_batch(self, texts: Sequence[str]) -> list[BatchPredictionItem]:
        predictions = self.predict_many(texts)
        return [
            BatchPredictionItem(text=text, prediction=prediction)
            for text, prediction in zip(texts, predictions, strict=True)
        ]

    def build_single_response_payload(self, text: str) -> dict[str, object]:
        return {
            "text": text,
            "prediction": self.predict_one(text).to_dict(),
        }

    def build_batch_response_payload(self, texts: Sequence[str]) -> dict[str, object]:
        return {
            "items": [item.to_dict() for item in self.predict_batch(texts)],
        }

    def build_explain_response_payload(self, text: str, *, top_n: int = 10) -> dict[str, object]:
        return {
            "text": text,
            "prediction": self.predict_one_explained(text, top_n=top_n).to_dict(),
        }

    def get_model_identity(self) -> ModelIdentity:
        metadata = self.model.metadata
        model_version = str(metadata.get("model_version") or "unknown")
        raw_model_key = metadata.get("model_key")
        if raw_model_key:
            model_key = str(raw_model_key)
        elif self.model_path is not None:
            model_key = self.model_path.stem
        else:
            model_key = f"baseline-{model_version}"
        return ModelIdentity(
            model_key=model_key,
            model_version=model_version,
        )

    def get_model_info(self) -> ModelInfo:
        metadata = self.model.metadata
        return ModelInfo(
            model_path=str(self.model_path) if self.model_path is not None else None,
            model_version=metadata.get("model_version"),
            threshold=float(self.model.threshold),
            calibration_method=metadata.get("calibration_method"),
            training_config=metadata.get("training_config"),
        )
