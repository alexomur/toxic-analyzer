from pathlib import Path

from toxic_analyzer.ask_baseline import (
    format_prediction,
    interactive_loop,
    parse_args,
    sanitize_text,
)
from toxic_analyzer.baseline_model import ToxicityPrediction


class StubModel:
    def predict_one(self, text: str) -> ToxicityPrediction:
        label = int("идиот" in text.lower())
        score = 0.9 if label == 1 else 0.8
        toxic_probability = score if label == 1 else 1.0 - score
        return ToxicityPrediction(
            label=label,
            score=score,
            toxic_probability=toxic_probability,
        )


def test_parse_args_supports_positional_text() -> None:
    args = parse_args(["просто", "фраза"])

    assert args.text == ["просто", "фраза"]
    assert isinstance(args.model_path, Path)


def test_format_prediction_uses_human_readable_verdict() -> None:
    rendered = format_prediction(
        "ты идиот",
        ToxicityPrediction(label=1, score=0.95, toxic_probability=0.95),
    )

    assert "Вердикт модели: токсичный" in rendered
    assert "label: 1" in rendered


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
    assert any("Вердикт модели: токсичный" in line for line in outputs)
    assert outputs[-1] == "Завершение."


def test_sanitize_text_removes_bom_and_spaces() -> None:
    assert sanitize_text("\ufeff  привет  ") == "привет"
    assert sanitize_text("п»їпривет") == "привет"
