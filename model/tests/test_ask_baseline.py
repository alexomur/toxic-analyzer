from pathlib import Path

from toxic_analyzer.ask_baseline import (
    format_explained_prediction,
    format_prediction,
    interactive_loop,
    parse_args,
    sanitize_text,
)
from toxic_analyzer.baseline_model import (
    AppliedAdjustment,
    ExplainedToxicityPrediction,
    FeatureContribution,
    ToxicityExplanation,
    ToxicityPrediction,
    TriggeredExpertFeature,
)


class StubModel:
    def predict_one(self, text: str) -> ToxicityPrediction:
        label = int("идиот" in text.lower())
        toxic_probability = 0.9 if label == 1 else 0.2
        return ToxicityPrediction(
            label=label,
            toxic_probability=toxic_probability,
        )

    def predict_one_explained(self, text: str, *, top_n: int = 10) -> ExplainedToxicityPrediction:
        return ExplainedToxicityPrediction(
            label=1,
            toxic_probability=0.87,
            raw_model_probability=0.82,
            calibrated_probability=0.9,
            posthoc_adjusted_probability=0.87,
            threshold=0.4,
            explanation=ToxicityExplanation(
                canonical_tokens=["ты", "мудак"],
                top_positive_features=[
                    FeatureContribution(
                        feature_group="word_ngram",
                        feature_name="мудак",
                        feature_value=1.0,
                        feature_weight=7.031,
                        contribution=7.031,
                    )
                ][:top_n],
                top_negative_features=[],
                triggered_expert_features=[
                    TriggeredExpertFeature(
                        feature_name="strong_insult_count",
                        feature_value=1.0,
                        reasons=["token:мудак"],
                    )
                ],
                applied_adjustments=[
                    AppliedAdjustment(
                        adjustment_name="second_person_negated_insult",
                        delta=-0.35,
                        trigger_features=["has_second_person_negated_insult"],
                    )
                ],
            ),
        )


def test_parse_args_supports_positional_text() -> None:
    args = parse_args(["просто", "фраза"])

    assert args.text == ["просто", "фраза"]
    assert isinstance(args.model_path, Path)
    assert args.top_n == 3


def test_parse_args_supports_top_n() -> None:
    args = parse_args(["--top-n", "3", "ты", "мудак"])

    assert args.top_n == 3
    assert args.text == ["ты", "мудак"]


def test_format_prediction_uses_human_readable_verdict() -> None:
    rendered = format_prediction(
        "ты идиот",
        ToxicityPrediction(label=1, toxic_probability=0.95),
    )

    assert "Вердикт модели: токсичный" in rendered
    assert "label: 1" in rendered
    assert "p(toxic): 0.950000" in rendered


def test_format_explained_prediction_renders_technical_explanation() -> None:
    rendered = format_explained_prediction("ты мудак", StubModel().predict_one_explained("ты мудак"))

    assert "======\nraw_model_probability: 0.820000" in rendered
    assert "canonical_tokens: ты, мудак\n======" in rendered
    assert "raw_model_probability: 0.820000" in rendered
    assert "1. word_ngram: мудак => +7.031" in rendered
    assert "1. posthoc_adjustment: second_person_negated_insult => -0.350" in rendered


def test_interactive_loop_reads_until_exit() -> None:
    model = StubModel()
    prompts: list[str] = []
    outputs: list[str] = []
    replies = iter(["ты идиот", "", "лишнее"])

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(replies)

    interactive_loop(model, input_fn=fake_input, output_fn=outputs.append)

    assert prompts == ["> ", "> "]
    assert any("1. word_ngram: мудак => +7.031" in line for line in outputs)
    assert outputs[-1] == "Завершение."


def test_interactive_loop_supports_top_n() -> None:
    model = StubModel()
    outputs: list[str] = []
    replies = iter(["ты мудак", ""])

    interactive_loop(
        model,
        top_n=1,
        input_fn=lambda prompt: next(replies),
        output_fn=outputs.append,
    )

    assert any("1. word_ngram: мудак => +7.031" in line for line in outputs)


def test_sanitize_text_removes_bom_and_spaces() -> None:
    assert sanitize_text("\ufeff  привет  ") == "привет"
    assert sanitize_text("п»—привет") == "привет"
