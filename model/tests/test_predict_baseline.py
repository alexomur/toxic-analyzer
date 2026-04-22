import json

import pytest

from toxic_analyzer import predict_baseline
from toxic_analyzer.inference_service import ToxicityInferenceService


class StubService:
    def build_single_response_payload(self, text: str) -> dict[str, object]:
        return {
            "text": text,
            "prediction": {
                "label": 1,
                "score": 0.9,
                "toxic_probability": 0.9,
            },
        }

    def build_batch_response_payload(self, texts: list[str]) -> dict[str, object]:
        return {
            "items": [
                {
                    "text": text,
                    "prediction": {
                        "label": int("идиот" in text.lower()),
                        "score": 0.9 if "идиот" in text.lower() else 0.8,
                        "toxic_probability": 0.9 if "идиот" in text.lower() else 0.2,
                    },
                }
                for text in texts
            ]
        }


def test_main_requires_text_or_stdin() -> None:
    with pytest.raises(
        SystemExit,
        match="Provide at least one --text value or pass input via --stdin.",
    ):
        predict_baseline.main([])


def test_main_prints_single_prediction_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_from_path(cls: type[ToxicityInferenceService], model_path: object) -> StubService:
        assert str(model_path).endswith("baseline_model_v3_3.pkl")
        return StubService()

    monkeypatch.setattr(
        predict_baseline.ToxicityInferenceService,
        "from_path",
        classmethod(fake_from_path),
    )

    exit_code = predict_baseline.main(["--text", "ты идиот"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "text": "ты идиот",
        "prediction": {
            "label": 1,
            "score": 0.9,
            "toxic_probability": 0.9,
        },
    }


def test_main_prints_batch_prediction_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_from_path(cls: type[ToxicityInferenceService], model_path: object) -> StubService:
        assert str(model_path).endswith("baseline_model_v3_3.pkl")
        return StubService()

    monkeypatch.setattr(
        predict_baseline.ToxicityInferenceService,
        "from_path",
        classmethod(fake_from_path),
    )

    exit_code = predict_baseline.main(
        ["--text", "спокойный комментарий", "--text", "ты идиот"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["items"][0]["prediction"]["label"] == 0
    assert payload["items"][1]["prediction"]["label"] == 1
