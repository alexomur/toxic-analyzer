from pathlib import Path

from toxic_analyzer.hard_case_dataset import load_hard_case_dataset


def test_load_hard_case_dataset_reads_tags_and_labels(tmp_path: Path) -> None:
    dataset_path = tmp_path / "hard_cases.jsonl"
    dataset_path.write_text(
        "\n".join(
            [
                '{"text":"поплачь об этом","label":1,"tags":["implicit_toxicity","short_text"]}',
                '{"text":"Он неплохо справляется!","label":0,"tags":["benign"]}',
            ]
        ),
        encoding="utf-8",
    )

    dataset = load_hard_case_dataset(dataset_path)

    assert dataset.labels == [1, 0]
    assert dataset.texts == ["поплачь об этом", "Он неплохо справляется!"]
    assert dataset.unique_tags == ["benign", "implicit_toxicity", "short_text"]
    assert dataset.summary()["rows"] == 2
