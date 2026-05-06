import json
from pathlib import Path

import pytest

from toxic_analyzer import evaluate_baseline
from toxic_analyzer.inference_service import ModelInfo, ToxicityPrediction


class StubService:
    def __init__(self) -> None:
        self.model = type("StubModel", (), {"threshold": 0.5})()

    def predict_many(self, texts: list[str]) -> list[ToxicityPrediction]:
        return [
            ToxicityPrediction(
                label=int("tox" in text.lower()),
                toxic_probability=0.9 if "tox" in text.lower() else 0.1,
            )
            for text in texts
        ]

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_path="stub-model.pkl",
            model_version="test",
            threshold=0.5,
            calibration_method="sigmoid",
            training_config=None,
        )


class MixedStubService(StubService):
    def predict_many(self, texts: list[str]) -> list[ToxicityPrediction]:
        payload: list[ToxicityPrediction] = []
        for text in texts:
            lowered = text.lower()
            if "false positive" in lowered:
                payload.append(ToxicityPrediction(label=1, toxic_probability=0.8))
            elif "false negative" in lowered:
                payload.append(ToxicityPrediction(label=0, toxic_probability=0.2))
            else:
                payload.append(
                    ToxicityPrediction(
                        label=int("tox" in lowered),
                        toxic_probability=0.9 if "tox" in lowered else 0.1,
                    )
                )
        return payload


def test_parse_labeled_text_cases_supports_multiline_entries() -> None:
    payload = "first line\nsecond line ^ 1;\nneutral text ^ 0;\n"

    cases = evaluate_baseline.parse_labeled_text_cases(payload)

    assert cases == [
        evaluate_baseline.LabeledTextCase(text="first line\nsecond line", label=1),
        evaluate_baseline.LabeledTextCase(text="neutral text", label=0),
    ]


def test_parse_labeled_text_cases_rejects_invalid_tail() -> None:
    with pytest.raises(ValueError, match=r"Expected '<text> \^ <toxicity>;'"):
        evaluate_baseline.parse_labeled_text_cases("broken record without delimiter")


def test_main_prints_metrics_for_dataset(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "test_text.txt"
    dataset_path.write_text("neutral sample ^ 0;\nmultiline\ntox sample ^ 1;\n", encoding="utf-8")

    def fake_from_path(cls: type[object], model_path: object) -> StubService:
        assert str(model_path).endswith("baseline_model_v3_4.pkl")
        return StubService()

    monkeypatch.setattr(
        evaluate_baseline.ToxicityInferenceService,
        "from_path",
        classmethod(fake_from_path),
    )

    exit_code = evaluate_baseline.main(["--dataset-path", str(dataset_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset"]["rows"] == 2
    assert payload["dataset"]["positive_labels"] == 1
    assert payload["metrics"]["accuracy"] == 1.0
    assert payload["metrics"]["true_positive"] == 1
    assert payload["metrics"]["true_negative"] == 1
    assert payload["metrics"]["false_positive"] == 0
    assert payload["metrics"]["false_negative"] == 0
    assert payload["errors"] == []


def test_main_prints_all_model_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "test_text.txt"
    dataset_path.write_text(
        "clean text ^ 0;\nfalse positive sample ^ 0;\nfalse negative sample ^ 1;\n",
        encoding="utf-8",
    )

    def fake_from_path(cls: type[object], model_path: object) -> MixedStubService:
        assert str(model_path).endswith("baseline_model_v3_4.pkl")
        return MixedStubService()

    monkeypatch.setattr(
        evaluate_baseline.ToxicityInferenceService,
        "from_path",
        classmethod(fake_from_path),
    )

    exit_code = evaluate_baseline.main(["--dataset-path", str(dataset_path)])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["errors"]) == 2
    assert payload["errors"][0]["error_type"] == "false_positive"
    assert payload["errors"][0]["index"] == 2
    assert payload["errors"][0]["expected_label"] == 0
    assert payload["errors"][0]["predicted_label"] == 1
    assert payload["errors"][0]["text"] == "false positive sample"
    assert payload["errors"][1]["error_type"] == "false_negative"
    assert payload["errors"][1]["index"] == 3
    assert payload["errors"][1]["expected_label"] == 1
    assert payload["errors"][1]["predicted_label"] == 0
    assert payload["errors"][1]["text"] == "false negative sample"
