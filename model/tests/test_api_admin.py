from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from toxic_analyzer.admin_service import (
    ModelRegistryRecord,
    RetrainAdminService,
    RetrainJobRecord,
)
from toxic_analyzer.api.app import create_app
from toxic_analyzer.api.runtime_state import ModelRuntimeState
from toxic_analyzer.baseline_model import ToxicityPrediction
from toxic_analyzer.inference_service import ModelIdentity, ModelInfo
from toxic_analyzer.training_service import BaselineTrainingResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StubInferenceService:
    def __init__(self, *, model_key: str, model_version: str, model_path: Path) -> None:
        self._identity = ModelIdentity(model_key=model_key, model_version=model_version)
        self.model_path = model_path.resolve()

    def predict_one(self, text: str) -> ToxicityPrediction:
        is_toxic = "toxic" in text.lower() or "idiot" in text.lower()
        toxic_probability = 0.88 if is_toxic else 0.11
        score = toxic_probability if is_toxic else 1.0 - toxic_probability
        return ToxicityPrediction(
            label=int(is_toxic),
            score=score,
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
            threshold=0.4,
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


class InMemoryAdminStore:
    def __init__(self) -> None:
        self._next_model_id = 1
        self._next_job_id = 1
        self.models_by_key: dict[str, ModelRegistryRecord] = {}
        self.models_by_id: dict[int, ModelRegistryRecord] = {}
        self.jobs_by_key: dict[str, RetrainJobRecord] = {}

    def create_retrain_job(
        self,
        *,
        job_key: str,
        trigger_type: str,
        requested_by: str | None,
        dataset_snapshot: dict[str, object],
        job_metadata: dict[str, object],
    ) -> RetrainJobRecord:
        job = RetrainJobRecord(
            id=self._next_job_id,
            job_key=job_key,
            job_type="retrain",
            trigger_type=trigger_type,
            status="queued",
            requested_by=requested_by,
            output_model_id=None,
            dataset_snapshot=dict(dataset_snapshot),
            job_metadata=dict(job_metadata),
            error_message=None,
            created_at=_utcnow(),
            started_at=None,
            finished_at=None,
            output_model_key=None,
            output_model_version=None,
        )
        self._next_job_id += 1
        self.jobs_by_key[job_key] = job
        return job

    def mark_retrain_job_running(self, job_key: str) -> RetrainJobRecord:
        job = self.jobs_by_key[job_key]
        updated = replace(job, status="running", started_at=job.started_at or _utcnow())
        self.jobs_by_key[job_key] = updated
        return updated

    def mark_retrain_job_succeeded(
        self,
        job_key: str,
        *,
        output_model_id: int,
    ) -> RetrainJobRecord:
        job = self.jobs_by_key[job_key]
        model = self.models_by_id[output_model_id]
        updated = replace(
            job,
            status="succeeded",
            output_model_id=output_model_id,
            output_model_key=model.model_key,
            output_model_version=model.model_version,
            finished_at=_utcnow(),
            error_message=None,
        )
        self.jobs_by_key[job_key] = updated
        return updated

    def mark_retrain_job_failed(self, job_key: str, *, error_message: str) -> RetrainJobRecord:
        job = self.jobs_by_key[job_key]
        updated = replace(
            job,
            status="failed",
            error_message=error_message,
            finished_at=_utcnow(),
        )
        self.jobs_by_key[job_key] = updated
        return updated

    def register_model(
        self,
        *,
        model_key: str,
        model_version: str,
        artifact_path: str,
        artifact_sha256: str,
        training_summary: dict[str, object],
        metrics: dict[str, object],
    ) -> ModelRegistryRecord:
        record = ModelRegistryRecord(
            id=self._next_model_id,
            model_key=model_key,
            model_family="baseline",
            model_version=model_version,
            artifact_path=artifact_path,
            artifact_storage="local_artifact",
            artifact_sha256=artifact_sha256,
            training_summary=dict(training_summary),
            metrics=dict(metrics),
            status="ready",
            created_at=_utcnow(),
            trained_at=_utcnow(),
            promoted_at=None,
        )
        self._next_model_id += 1
        self.models_by_key[model_key] = record
        self.models_by_id[record.id] = record
        return record

    def get_model(self, model_key: str) -> ModelRegistryRecord | None:
        return self.models_by_key.get(model_key)

    def get_retrain_job(self, job_key: str) -> RetrainJobRecord | None:
        return self.jobs_by_key.get(job_key)

    def list_retrain_jobs(self, *, limit: int = 20) -> list[RetrainJobRecord]:
        jobs = sorted(
            self.jobs_by_key.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )
        return jobs[:limit]


class DeferredLauncher:
    def __init__(self) -> None:
        self.tasks: list[callable] = []

    def launch(self, task) -> None:
        self.tasks.append(task)

    def run_all(self) -> None:
        while self.tasks:
            task = self.tasks.pop(0)
            task()


class FakeTrainedModel:
    def __init__(self, *, model_version: str) -> None:
        self.metadata = {"model_version": model_version}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"trained-model")


def test_reload_switches_active_model_and_failed_reload_keeps_previous_model(
    tmp_path: Path,
) -> None:
    model_a_path = tmp_path / "baseline-a.pkl"
    model_b_path = tmp_path / "baseline-b.pkl"
    runtime_state = _build_runtime_state(
        default_model_path=model_a_path,
        service_map={
            model_a_path.resolve(): StubInferenceService(
                model_key="baseline-a",
                model_version="v3.3",
                model_path=model_a_path,
            ),
            model_b_path.resolve(): StubInferenceService(
                model_key="baseline-b",
                model_version="v3.4",
                model_path=model_b_path,
            ),
        },
    )
    store = InMemoryAdminStore()
    store.register_model(
        model_key="baseline-b",
        model_version="v3.4",
        artifact_path=str(model_b_path),
        artifact_sha256="abc123",
        training_summary={"source": "test"},
        metrics={"test": {"overall": {"f1": 1.0}}},
    )
    admin_service = RetrainAdminService(store=store)
    app = create_app(runtime_state=runtime_state, admin_service=admin_service)

    with TestClient(app) as client:
        before_reload = client.post("/v1/predict", json={"text": "calm"})
        reload_response = client.post("/v1/admin/reload", json={"model_key": "baseline-b"})
        after_reload = client.post("/v1/predict", json={"text": "calm"})
        failed_reload = client.post(
            "/v1/admin/reload",
            json={"model_path": str(tmp_path / "missing.pkl")},
        )
        after_failed_reload = client.post("/v1/predict", json={"text": "calm"})

    assert before_reload.status_code == 200
    assert before_reload.json()["model_key"] == "baseline-a"

    assert reload_response.status_code == 200
    assert reload_response.json()["model_key"] == "baseline-b"
    assert reload_response.json()["model_version"] == "v3.4"

    assert after_reload.status_code == 200
    assert after_reload.json()["model_key"] == "baseline-b"

    assert failed_reload.status_code == 400
    assert "train-baseline" in failed_reload.json()["detail"]

    assert after_failed_reload.status_code == 200
    assert after_failed_reload.json()["model_key"] == "baseline-b"


def test_retrain_endpoint_returns_job_key_and_status_moves_to_succeeded(
    tmp_path: Path,
) -> None:
    runtime_path = tmp_path / "baseline-runtime.pkl"
    runtime_state = _build_runtime_state(
        default_model_path=runtime_path,
        service_map={
            runtime_path.resolve(): StubInferenceService(
                model_key="baseline-runtime",
                model_version="v3.3",
                model_path=runtime_path,
            )
        },
    )
    store = InMemoryAdminStore()
    launcher = DeferredLauncher()

    def training_runner(_request) -> BaselineTrainingResult:
        return BaselineTrainingResult(
            model=FakeTrainedModel(model_version="v9.0"),  # type: ignore[arg-type]
            report={
                "metrics": {
                    "test": {
                        "overall": {
                            "f1": 0.99,
                            "precision": 0.99,
                            "recall": 0.99,
                        }
                    }
                }
            },
        )

    admin_service = RetrainAdminService(
        store=store,
        background_launcher=launcher,
        training_runner=training_runner,
        artifact_dir=tmp_path / "artifacts",
    )
    app = create_app(runtime_state=runtime_state, admin_service=admin_service)

    with TestClient(app) as client:
        start_response = client.post("/v1/admin/retrain", json={"requested_by": "alice"})
        job_key = start_response.json()["job_key"]
        queued_response = client.get(f"/v1/admin/jobs/{job_key}")
        list_response = client.get("/v1/admin/jobs")
        launcher.run_all()
        succeeded_response = client.get(f"/v1/admin/jobs/{job_key}")

    assert start_response.status_code == 202
    assert start_response.json()["status"] == "queued"
    assert start_response.json()["requested_by"] == "alice"

    assert queued_response.status_code == 200
    assert queued_response.json()["status"] == "queued"
    assert queued_response.json()["output_model_key"] is None

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["job_key"] == job_key

    assert succeeded_response.status_code == 200
    assert succeeded_response.json()["status"] == "succeeded"
    assert succeeded_response.json()["output_model_version"] == "v9.0"
    output_model_key = succeeded_response.json()["output_model_key"]
    assert output_model_key is not None

    registered_model = store.get_model(output_model_key)
    assert registered_model is not None
    assert Path(registered_model.artifact_path).exists()
