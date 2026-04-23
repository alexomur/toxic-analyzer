
from pathlib import Path

from fastapi.testclient import TestClient

from toxic_analyzer.api.app import create_app
from toxic_analyzer.api.runtime_state import ModelRuntimeState
from toxic_analyzer.baseline_model import ToxicityPrediction
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


def test_runtime_reports_not_ready_when_model_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing-model.pkl"
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
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "baseline-a.pkl"
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
