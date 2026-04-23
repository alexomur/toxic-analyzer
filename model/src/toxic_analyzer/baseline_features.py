"""Handcrafted sparse features for short and implicit toxic phrases."""


import re
from collections.abc import Sequence
from functools import lru_cache

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
LEGACY_IDENTITY_TERMS = {
    "гей",
    "гея",
    "гею",
    "геем",
    "геи",
    "гомик",
    "гомосек",
}
IDENTITY_TERMS = LEGACY_IDENTITY_TERMS | {"геям"}
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
HARM_NOUN_WORDS = {
    "смерть",
    "смерти",
}
NEGATION_WORDS = {
    "не",
    "ни",
}
HARM_RECIPIENT_WORDS = {
    "им",
    "вам",
    "тебе",
    "ему",
    "ей",
    "этим",
    "таким",
}
DISMISSIVE_PATTERNS = [
    re.compile(r"\bпоплач\w*\b"),
    re.compile(r"\bиди\b.{0,16}\b(нафиг|нахуй|лесом|отсюда)\b"),
    re.compile(r"\b(свали|заткнись|молчи|отвали|съебал)\b"),
    re.compile(r"\bспросить\s+забыли\b"),
]
APPROXIMATE_MATCH_WORDS = frozenset(
    MILD_INSULT_WORDS
    | STRONG_INSULT_WORDS
    | PROFANE_WORDS
    | IDENTITY_TERMS
    | IMPERATIVE_CUES
    | HARM_NOUN_WORDS
    | {"нафиг"}
)
APPROXIMATE_WORDS_BY_LENGTH = {
    length: tuple(sorted(word for word in APPROXIMATE_MATCH_WORDS if len(word) == length))
    for length in range(1, max(len(word) for word in APPROXIMATE_MATCH_WORDS) + 1)
}

LEGACY_FEATURE_NAMES = [
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
FEATURE_NAMES = [
    "token_count",
    "exclamation_count",
    "question_count",
    "second_person_count",
    "mild_insult_count",
    "strong_insult_count",
    "profane_count",
    "identity_term_count",
    "harm_term_count",
    "imperative_count",
    "has_dismissive_pattern",
    "has_second_person_negated_insult",
    "has_pronoun_insult",
    "has_pronoun_profanity",
    "has_identity_dismissal",
    "has_targeted_harm",
    "has_untargeted_harm",
    "has_short_targeted_attack",
]


def _count_matches(tokens: Sequence[str], vocabulary: set[str]) -> int:
    return sum(1 for token in tokens if token in vocabulary)


def _normalize_token(token: str) -> str:
    return token.lower().replace("ё", "е")


def _is_single_edit_variant(source: str, target: str) -> bool:
    if source == target:
        return True
    source_length = len(source)
    target_length = len(target)
    if abs(source_length - target_length) > 1:
        return False
    if source_length == target_length:
        mismatch_indices = [
            index
            for index, (left, right) in enumerate(zip(source, target, strict=True))
            if left != right
        ]
        if len(mismatch_indices) == 1:
            return True
        if len(mismatch_indices) == 2:
            first, second = mismatch_indices
            return (
                second == first + 1
                and source[first] == target[second]
                and source[second] == target[first]
            )
        return False

    if source_length > target_length:
        source, target = target, source
        source_length, target_length = target_length, source_length

    source_index = 0
    target_index = 0
    mismatch_found = False
    while source_index < source_length and target_index < target_length:
        if source[source_index] == target[target_index]:
            source_index += 1
            target_index += 1
            continue
        if mismatch_found:
            return False
        mismatch_found = True
        target_index += 1
    return True


@lru_cache(maxsize=50_000)
def canonicalize_token(token: str) -> str:
    normalized = _normalize_token(token)
    if len(normalized) < 5 or normalized in APPROXIMATE_MATCH_WORDS:
        return normalized
    matches: list[str] = []
    for candidate_length in range(len(normalized) - 1, len(normalized) + 2):
        for candidate in APPROXIMATE_WORDS_BY_LENGTH.get(candidate_length, ()):
            if _is_single_edit_variant(normalized, candidate):
                matches.append(candidate)
        if len(matches) > 1:
            return normalized
    if len(matches) == 1:
        return matches[0]
    return normalized


def _collect_negated_insult_indices(tokens: Sequence[str]) -> set[int]:
    insult_words = MILD_INSULT_WORDS | STRONG_INSULT_WORDS
    negated_indices: set[int] = set()
    for index, token in enumerate(tokens):
        if token not in NEGATION_WORDS:
            continue
        for lookahead in range(index + 1, min(index + 3, len(tokens) - 1) + 1):
            if tokens[lookahead] in insult_words:
                negated_indices.add(lookahead)
    return negated_indices


def _is_harm_recipient(token: str) -> bool:
    return token in HARM_RECIPIENT_WORDS or (len(token) >= 4 and token.endswith(("ам", "ям")))


def _has_targeted_harm(tokens: Sequence[str]) -> bool:
    if len(tokens) > 5:
        return False
    for index, token in enumerate(tokens):
        if token not in HARM_NOUN_WORDS:
            continue
        for candidate in tokens[index + 1 : index + 3]:
            if _is_harm_recipient(candidate):
                return True
    return False


class ExpertFeatureTransformer(BaseEstimator, TransformerMixin):
    """Extract lightweight interpretable signals for implicit hostility."""

    def __init__(self, feature_layout_version: int = 3) -> None:
        self.feature_layout_version = feature_layout_version

    def fit(
        self,
        texts: Sequence[str],
        y: Sequence[int] | None = None,
    ) -> "ExpertFeatureTransformer":
        return self

    def _build_legacy_row(self, lowered: str, tokens: Sequence[str]) -> list[float]:
        token_count = len(tokens)
        second_person_count = _count_matches(tokens, SECOND_PERSON_WORDS)
        mild_insult_count = _count_matches(tokens, MILD_INSULT_WORDS)
        strong_insult_count = _count_matches(tokens, STRONG_INSULT_WORDS)
        profane_count = _count_matches(tokens, PROFANE_WORDS)
        identity_term_count = _count_matches(tokens, LEGACY_IDENTITY_TERMS)
        imperative_count = _count_matches(tokens, IMPERATIVE_CUES)
        has_dismissive_pattern = int(
            any(pattern.search(lowered) is not None for pattern in DISMISSIVE_PATTERNS)
        )
        has_pronoun_insult = int(
            second_person_count > 0 and (mild_insult_count + strong_insult_count) > 0
        )
        has_pronoun_profanity = int(second_person_count > 0 and profane_count > 0)
        has_identity_dismissal = int("спросить забыли" in lowered and identity_term_count > 0)
        has_short_targeted_attack = int(
            token_count <= 4
            and (
                has_pronoun_insult
                or has_pronoun_profanity
                or has_dismissive_pattern
                or (strong_insult_count > 0 and second_person_count > 0)
            )
        )
        return [
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

    def _build_current_row(self, lowered: str, tokens: Sequence[str]) -> list[float]:
        token_count = len(tokens)
        canonical_tokens = [canonicalize_token(token) for token in tokens]
        canonical_text = " ".join(canonical_tokens)
        second_person_count = _count_matches(canonical_tokens, SECOND_PERSON_WORDS)
        negated_insult_indices = _collect_negated_insult_indices(canonical_tokens)
        mild_insult_count = sum(
            1
            for index, token in enumerate(canonical_tokens)
            if token in MILD_INSULT_WORDS and index not in negated_insult_indices
        )
        strong_insult_count = sum(
            1
            for index, token in enumerate(canonical_tokens)
            if token in STRONG_INSULT_WORDS and index not in negated_insult_indices
        )
        profane_count = _count_matches(canonical_tokens, PROFANE_WORDS)
        identity_term_count = _count_matches(canonical_tokens, IDENTITY_TERMS)
        harm_term_count = _count_matches(canonical_tokens, HARM_NOUN_WORDS)
        imperative_count = _count_matches(canonical_tokens, IMPERATIVE_CUES)
        has_dismissive_pattern = int(
            any(pattern.search(canonical_text) is not None for pattern in DISMISSIVE_PATTERNS)
        )
        has_negated_insult = int(bool(negated_insult_indices))
        has_second_person_negated_insult = int(second_person_count > 0 and has_negated_insult)
        has_pronoun_insult = int(
            second_person_count > 0 and (mild_insult_count + strong_insult_count) > 0
        )
        has_pronoun_profanity = int(second_person_count > 0 and profane_count > 0)
        has_identity_dismissal = int(
            "спросить забыли" in canonical_text and identity_term_count > 0
        )
        has_targeted_harm = int(_has_targeted_harm(canonical_tokens))
        has_untargeted_harm = int(harm_term_count > 0 and not has_targeted_harm)
        has_short_targeted_attack = int(
            token_count <= 4
            and (
                has_pronoun_insult
                or has_pronoun_profanity
                or has_dismissive_pattern
                or has_targeted_harm
                or (strong_insult_count > 0 and second_person_count > 0)
            )
        )
        return [
            float(token_count),
            float(lowered.count("!")),
            float(lowered.count("?")),
            float(second_person_count),
            float(mild_insult_count),
            float(strong_insult_count),
            float(profane_count),
            float(identity_term_count),
            float(harm_term_count),
            float(imperative_count),
            float(has_dismissive_pattern),
            float(has_second_person_negated_insult),
            float(has_pronoun_insult),
            float(has_pronoun_profanity),
            float(has_identity_dismissal),
            float(has_targeted_harm),
            float(has_untargeted_harm),
            float(has_short_targeted_attack),
        ]

    def transform(self, texts: Sequence[str]) -> csr_matrix:
        rows: list[list[float]] = []
        feature_layout_version = getattr(self, "feature_layout_version", 2)
        for text in texts:
            lowered = str(text).lower()
            tokens = TOKEN_PATTERN.findall(lowered)
            if feature_layout_version <= 2:
                rows.append(self._build_legacy_row(lowered, tokens))
            else:
                rows.append(self._build_current_row(lowered, tokens))
        return csr_matrix(np.asarray(rows, dtype=np.float64))

    def get_feature_names_out(self, input_features: Sequence[str] | None = None) -> np.ndarray:
        feature_layout_version = getattr(self, "feature_layout_version", 2)
        if feature_layout_version <= 2:
            return np.asarray(LEGACY_FEATURE_NAMES, dtype=object)
        return np.asarray(FEATURE_NAMES, dtype=object)
