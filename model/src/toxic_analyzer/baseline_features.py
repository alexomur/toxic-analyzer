"""Handcrafted sparse features for short and implicit toxic phrases."""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.base import BaseEstimator, TransformerMixin

TOKEN_PATTERN = re.compile(r"(?u)\b\w+\b")
SECOND_PERSON_WORDS = {
    "ты",
    "тебя",
    "тебе",
    "тобой",
    "тобою",
    "твой",
    "твоя",
    "твоё",
    "твое",
    "твои",
    "вы",
    "вас",
    "вам",
    "вами",
    "ваш",
    "ваша",
    "ваше",
    "ваши",
}
MILD_INSULT_WORDS = {
    "плохой",
    "плохая",
    "плохие",
    "глупый",
    "глупая",
    "жалкий",
    "жалкая",
    "мерзкий",
    "мерзкая",
    "тупой",
    "тупая",
    "тупые",
    "чудище",
}
STRONG_INSULT_WORDS = {
    "идиот",
    "дебил",
    "урод",
    "мудак",
    "мразь",
    "сволочь",
    "ублюдок",
    "ублюдки",
    "гнида",
    "пидор",
    "пидорас",
    "пидора",
    "пидоры",
    "еблан",
    "долбоеб",
    "долбоёб",
    "долбоебы",
    "долбоёбы",
}
PROFANE_WORDS = {
    "нахуй",
    "нафиг",
    "хуй",
    "хуйня",
    "похуй",
    "ебать",
    "блять",
    "сука",
    "съебал",
    "съебись",
}
IDENTITY_TERMS = {
    "гей",
    "гея",
    "гею",
    "геем",
    "геи",
    "гомик",
    "гомосек",
}
IMPERATIVE_CUES = {
    "иди",
    "свали",
    "заткнись",
    "молчи",
    "поплачь",
    "успокойся",
    "смирись",
    "съебал",
    "отвали",
    "проваливай",
}
DISMISSIVE_PATTERNS = [
    re.compile(r"\bпоплач\w*\b"),
    re.compile(r"\bиди\b.{0,16}\b(нафиг|нахуй|лесом|отсюда)\b"),
    re.compile(r"\b(свали|заткнись|молчи|отвали|съебал)\b"),
    re.compile(r"\bспросить\s+забыли\b"),
]

FEATURE_NAMES = [
    "token_count",
    "exclamation_count",
    "question_count",
    "second_person_count",
    "mild_insult_count",
    "strong_insult_count",
    "profane_count",
    "identity_term_count",
    "imperative_count",
    "has_dismissive_pattern",
    "has_pronoun_insult",
    "has_pronoun_profanity",
    "has_identity_dismissal",
    "has_short_targeted_attack",
]


def _count_matches(tokens: Sequence[str], vocabulary: set[str]) -> int:
    return sum(1 for token in tokens if token in vocabulary)


class ExpertFeatureTransformer(BaseEstimator, TransformerMixin):
    """Extract lightweight interpretable signals for implicit hostility."""

    def fit(
        self,
        texts: Sequence[str],
        y: Sequence[int] | None = None,
    ) -> "ExpertFeatureTransformer":
        return self

    def transform(self, texts: Sequence[str]) -> csr_matrix:
        rows: list[list[float]] = []
        for text in texts:
            lowered = str(text).lower()
            tokens = TOKEN_PATTERN.findall(lowered)
            token_count = len(tokens)
            second_person_count = _count_matches(tokens, SECOND_PERSON_WORDS)
            mild_insult_count = _count_matches(tokens, MILD_INSULT_WORDS)
            strong_insult_count = _count_matches(tokens, STRONG_INSULT_WORDS)
            profane_count = _count_matches(tokens, PROFANE_WORDS)
            identity_term_count = _count_matches(tokens, IDENTITY_TERMS)
            imperative_count = _count_matches(tokens, IMPERATIVE_CUES)
            has_dismissive_pattern = int(
                any(pattern.search(lowered) is not None for pattern in DISMISSIVE_PATTERNS)
            )
            has_pronoun_insult = int(
                second_person_count > 0 and (mild_insult_count + strong_insult_count) > 0
            )
            has_pronoun_profanity = int(second_person_count > 0 and profane_count > 0)
            has_identity_dismissal = int(
                "спросить забыли" in lowered and identity_term_count > 0
            )
            has_short_targeted_attack = int(
                token_count <= 4
                and (
                    has_pronoun_insult
                    or has_pronoun_profanity
                    or has_dismissive_pattern
                    or (strong_insult_count > 0 and second_person_count > 0)
                )
            )
            rows.append(
                [
                    float(token_count),
                    float(lowered.count("!")),
                    float(lowered.count("?")),
                    float(second_person_count),
                    float(mild_insult_count),
                    float(strong_insult_count),
                    float(profane_count),
                    float(identity_term_count),
                    float(imperative_count),
                    float(has_dismissive_pattern),
                    float(has_pronoun_insult),
                    float(has_pronoun_profanity),
                    float(has_identity_dismissal),
                    float(has_short_targeted_attack),
                ]
            )
        return csr_matrix(np.asarray(rows, dtype=np.float64))

    def get_feature_names_out(self, input_features: Sequence[str] | None = None) -> np.ndarray:
        return np.asarray(FEATURE_NAMES, dtype=object)
