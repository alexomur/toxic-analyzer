import numpy as np

from toxic_analyzer.baseline_features import FEATURE_NAMES, ExpertFeatureTransformer


def test_expert_features_distinguish_targeted_insult_from_standalone_word() -> None:
    transformer = ExpertFeatureTransformer()
    matrix = transformer.transform(["чудище", "ты чудище"]).toarray()
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}

    assert matrix[0, feature_index["has_pronoun_insult"]] == 0.0
    assert matrix[1, feature_index["has_pronoun_insult"]] == 1.0
    assert (
        matrix[1, feature_index["second_person_count"]]
        > matrix[0, feature_index["second_person_count"]]
    )


def test_expert_features_capture_dismissive_template() -> None:
    transformer = ExpertFeatureTransformer()
    matrix = transformer.transform(["Гея спросить забыли", "Он неплохо справляется!"]).toarray()
    feature_index = {name: index for index, name in enumerate(FEATURE_NAMES)}

    assert matrix[0, feature_index["has_identity_dismissal"]] == 1.0
    assert matrix[1, feature_index["has_identity_dismissal"]] == 0.0
    assert np.all(matrix >= 0.0)
