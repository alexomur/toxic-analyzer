import numpy as np

from toxic_analyzer.baseline_features import FEATURE_NAMES, ExpertFeatureTransformer


def test_expert_features_distinguish_targeted_insult_from_standalone_word() -> None:
    transformer = ExpertFeatureTransformer()
    matrix = transformer.transform(["чудище", "ты чудище"]).toarray()
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}

    assert matrix[0, feature_index["has_pronoun_insult"]] == 0.0
    assert matrix[1, feature_index["has_pronoun_insult"]] == 1.0
    assert matrix[1, feature_index["second_person_count"]] > matrix[0, feature_index["second_person_count"]]


def test_expert_features_capture_dismissive_template() -> None:
    transformer = ExpertFeatureTransformer()
    matrix = transformer.transform(["Гея спросить забыли", "Он неплохо справляется!"]).toarray()
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}

    assert matrix[0, feature_index["has_identity_dismissal"]] == 1.0
    assert matrix[1, feature_index["has_identity_dismissal"]] == 0.0
    assert np.all(matrix >= 0.0)


def test_expert_features_capture_negated_insult_without_targeted_attack() -> None:
    transformer = ExpertFeatureTransformer()
    matrix = transformer.transform(["ты тупой", "ты не тупой"]).toarray()
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}

    assert matrix[0, feature_index["has_pronoun_insult"]] == 1.0
    assert matrix[1, feature_index["has_second_person_negated_insult"]] == 1.0
    assert matrix[1, feature_index["has_pronoun_insult"]] == 0.0


def test_expert_features_distinguish_targeted_harm_from_harm_topic() -> None:
    transformer = ExpertFeatureTransformer()
    matrix = transformer.transform(["смерть это страшно", "смерть геям"]).toarray()
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}

    assert matrix[0, feature_index["has_targeted_harm"]] == 0.0
    assert matrix[0, feature_index["has_untargeted_harm"]] == 1.0
    assert matrix[1, feature_index["has_targeted_harm"]] == 1.0
    assert matrix[1, feature_index["has_untargeted_harm"]] == 0.0


def test_expert_features_normalize_single_edit_typos() -> None:
    transformer = ExpertFeatureTransformer()
    matrix = transformer.transform(["поплач", "иди нафег", "заткнис уже"]).toarray()
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}

    assert matrix[0, feature_index["imperative_count"]] == 1.0
    assert matrix[1, feature_index["has_dismissive_pattern"]] == 1.0
    assert matrix[2, feature_index["imperative_count"]] == 1.0


def test_expert_feature_diagnostics_return_canonical_tokens_and_reasons() -> None:
    transformer = ExpertFeatureTransformer()

    diagnostics = transformer.analyze_text("ты не тупой")
    triggered = {item.feature_name: item for item in diagnostics.triggered_features}

    assert diagnostics.canonical_tokens == ["ты", "не", "тупой"]
    assert "has_second_person_negated_insult" in triggered
    assert "negated_token:тупой" in triggered["has_second_person_negated_insult"].reasons
