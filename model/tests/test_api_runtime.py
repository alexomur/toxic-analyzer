from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from toxic_analyzer.api.app import create_app
from toxic_analyzer.api.runtime_state import ModelRuntimeState
from toxic_analyzer.baseline_model import (
    AppliedAdjustment,
    ExplainedToxicityPrediction,
    FeatureContribution,
    ToxicityExplanation,
    ToxicityPrediction,
    TriggeredExpertFeature,
)
from toxic_analyzer.inference_service import ModelIdentity, ModelInfo


class StubInferenceService:
    def __init__(self, *, model_key: str, model_version: str, model_path: Path) -> None:
        self._identity = ModelIdentity(model_key=model_key, model_version=model_version)
        self.model_path = model_path.resolve()

    def predict_one(self, text: str) -> ToxicityPrediction:
        is_toxic = "toxic" in text.lower() or "idiot" in text.lower()
        toxic_probability = 0.91 if is_toxic else 0.14
        return ToxicityPrediction(
            label=int(is_toxic),
            toxic_probability=toxic_probability,
        )

    def predict_many(self, texts: list[str]) -> list[ToxicityPrediction]:
        return [self.predict_one(text) for text in texts]

    def predict_one_explained(self, text: str, *, top_n: int = 10) -> ExplainedToxicityPrediction:
        is_toxic = "toxic" in text.lower() or "idiot" in text.lower()
        return ExplainedToxicityPrediction(
            label=int(is_toxic),
            toxic_probability=0.91 if is_toxic else 0.14,
            raw_model_probability=0.86 if is_toxic else 0.11,
            calibrated_probability=0.92 if is_toxic else 0.13,
            posthoc_adjusted_probability=0.91 if is_toxic else 0.14,
            threshold=0.42,
            explanation=ToxicityExplanation(
                canonical_tokens=text.lower().split(),
                top_positive_features=[
                    FeatureContribution(
                        feature_group="word_ngram",
                        feature_name="idiot",
                        feature_value=1.0,
                        feature_weight=2.5,
                        contribution=2.5,
                    )
                ][:top_n],
                top_negative_features=[
                    FeatureContribution(
                        feature_group="expert_feature",
                        feature_name="has_second_person_negated_insult",
                        feature_value=1.0,
                        feature_weight=-0.4,
                        contribution=-0.4,
                    )
                ][:top_n],
                triggered_expert_features=[
                    TriggeredExpertFeature(
                        feature_name="strong_insult_count",
                        feature_value=1.0,
                        reasons=["token:idiot"],
                    )
                ],
                applied_adjustments=[
                    AppliedAdjustment(
                        adjustment_name="second_person_negated_insult",
                        delta=-0.01,
                        trigger_features=["strong_insult_count"],
                    )
                ],
            ),
        )

    def get_model_identity(self) -> ModelIdentity:
        return self._identity

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_path=str(self.model_path),
            model_version=self._identity.model_version,
            threshold=0.42,
            calibration_method="sigmoid",
            training_config={"min_df": 2},
        )


def _build_runtime_state(
    *,
    default_model_path: Path,
    service_map: dict[Path, StubInferenceService],
) -> ModelRuntimeState:
    def service_loader(path: Path) -> StubInferenceService:
        resolved_path = path.resolve()
        if resolved_path not in service_map:
            raise FileNotFoundError(resolved_path)
        return service_map[resolved_path]

    return ModelRuntimeState(
        default_model_path=default_model_path,
        service_loader=service_loader,
    )


@pytest.fixture
def workspace_tmp_dir() -> Path:
    root = Path("test-temp") / f"api-runtime-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_runtime_reports_not_ready_when_model_missing(workspace_tmp_dir: Path) -> None:
    missing_path = workspace_tmp_dir / "missing-model.pkl"
    runtime_state = _build_runtime_state(default_model_path=missing_path, service_map={})
    app = create_app(runtime_state=runtime_state)

    with TestClient(app) as client:
        ready_response = client.get("/health/ready")
        predict_response = client.post("/v1/predict", json={"text": "hello"})

    assert ready_response.status_code == 503
    assert ready_response.json()["status"] == "not_ready"
    assert "train-baseline" in ready_response.json()["detail"]

    assert predict_response.status_code == 503
    assert predict_response.json()["status"] == "not_ready"


def test_runtime_predict_endpoints_expose_model_identity_and_preserve_batch_order(
    workspace_tmp_dir: Path,
) -> None:
    model_path = workspace_tmp_dir / "baseline-a.pkl"
    runtime_state = _build_runtime_state(
        default_model_path=model_path,
        service_map={
            model_path.resolve(): StubInferenceService(
                model_key="baseline-a",
                model_version="v3.3",
                model_path=model_path,
            )
        },
    )
    app = create_app(runtime_state=runtime_state)

    with TestClient(app) as client:
        ready_response = client.get("/health/ready")
        info_response = client.get("/v1/model/info")
        predict_response = client.post(
            "/v1/predict",
            json={"id": "single-1", "text": "You are an idiot"},
        )
        batch_response = client.post(
            "/v1/predict/batch",
            json={
                "items": [
                    {"id": "a", "text": "calm technical comment"},
                    {"id": "b", "text": "toxic phrase here"},
                ]
            },
        )
        explain_response = client.post(
            "/v1/predict/explain",
            json={"id": "exp-1", "text": "You are an idiot", "top_n": 1},
        )

    assert ready_response.status_code == 200
    assert ready_response.json() == {
        "status": "ready",
        "detail": None,
        "model_key": "baseline-a",
        "model_version": "v3.3",
    }

    assert info_response.status_code == 200
    assert info_response.json()["model_key"] == "baseline-a"
    assert info_response.json()["model_version"] == "v3.3"
    assert info_response.json()["threshold"] == 0.42

    assert predict_response.status_code == 200
    assert predict_response.json() == {
        "id": "single-1",
        "label": 1,
        "toxic_probability": 0.91,
        "model_key": "baseline-a",
        "model_version": "v3.3",
    }

    batch_payload = batch_response.json()
    assert batch_response.status_code == 200
    assert batch_payload["model_key"] == "baseline-a"
    assert batch_payload["model_version"] == "v3.3"
    assert [item["id"] for item in batch_payload["items"]] == ["a", "b"]
    assert [item["label"] for item in batch_payload["items"]] == [0, 1]

    explain_payload = explain_response.json()
    assert explain_response.status_code == 200
    assert explain_payload["id"] == "exp-1"
    assert explain_payload["raw_model_probability"] == 0.86
    assert explain_payload["calibrated_probability"] == 0.92
    assert explain_payload["threshold"] == 0.42
    assert explain_payload["model_key"] == "baseline-a"
    assert explain_payload["explanation"]["top_positive_features"][0]["feature_group"] == "word_ngram"
    assert explain_payload["explanation"]["applied_adjustments"][0]["adjustment_name"] == "second_person_negated_insult"
