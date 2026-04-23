from pathlib import Path

from toxic_analyzer.baseline_model import ToxicityPrediction
from toxic_analyzer.inference_service import ToxicityInferenceService


class StubModel:
    def __init__(self) -> None:
        self.threshold = 0.39
        self.metadata = {
            "model_version": "v3.3",
            "calibration_method": "sigmoid",
            "training_config": {"min_df": 2},
        }

    def predict_one(self, text: str) -> ToxicityPrediction:
        label = int("идиот" in text.lower())
        toxic_probability = 0.9 if label == 1 else 0.2
        return ToxicityPrediction(
            label=label,
            toxic_probability=toxic_probability,
        )

    def predict(self, texts: list[str]) -> list[ToxicityPrediction]:
        return [self.predict_one(text) for text in texts]


def test_build_single_response_payload_uses_model_prediction() -> None:
    service = ToxicityInferenceService(model=StubModel())  # type: ignore[arg-type]

    payload = service.build_single_response_payload("ты идиот")

    assert payload == {
        "text": "ты идиот",
        "prediction": {
            "label": 1,
            "toxic_probability": 0.9,
        },
    }


def test_build_batch_response_payload_preserves_input_order() -> None:
    service = ToxicityInferenceService(model=StubModel())  # type: ignore[arg-type]

    payload = service.build_batch_response_payload(["спокойный комментарий", "ты идиот"])

    assert payload["items"][0]["text"] == "спокойный комментарий"
    assert payload["items"][0]["prediction"]["label"] == 0
    assert payload["items"][1]["text"] == "ты идиот"
    assert payload["items"][1]["prediction"]["label"] == 1


def test_get_model_info_exposes_runtime_metadata() -> None:
    service = ToxicityInferenceService(
        model=StubModel(),  # type: ignore[arg-type]
        model_path=Path("C:/tmp/baseline.pkl"),
    )

    info = service.get_model_info().to_dict()

    assert info["model_path"] == "C:\\tmp\\baseline.pkl"
    assert info["model_version"] == "v3.3"
    assert info["threshold"] == 0.39
    assert info["calibration_method"] == "sigmoid"
    assert info["training_config"] == {"min_df": 2}
