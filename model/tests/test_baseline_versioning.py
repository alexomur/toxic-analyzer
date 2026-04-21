from toxic_analyzer.baseline_model import ToxicityBaselineModel


def test_v3_2_model_version_keeps_v3_probability_adjustments() -> None:
    model = ToxicityBaselineModel(
        pipeline=None,  # type: ignore[arg-type]
        calibrator=None,  # type: ignore[arg-type]
        threshold=0.5,
        metadata={"model_version": "v3.2"},
    )

    assert model._supports_v3_adjustments() is True
