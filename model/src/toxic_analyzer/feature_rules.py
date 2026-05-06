"""Lexicons and low-level rule helpers for expert baseline features."""

from __future__ import annotations

import re
from collections.abc import Sequence
from functools import lru_cache

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


def count_matches(tokens: Sequence[str], vocabulary: set[str]) -> int:
    return sum(1 for token in tokens if token in vocabulary)


def normalize_token(token: str) -> str:
    return token.lower().replace("ё", "е")


def is_single_edit_variant(source: str, target: str) -> bool:
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
    normalized = normalize_token(token)
    if len(normalized) < 5 or normalized in APPROXIMATE_MATCH_WORDS:
        return normalized
    matches: list[str] = []
    for candidate_length in range(len(normalized) - 1, len(normalized) + 2):
        for candidate in APPROXIMATE_WORDS_BY_LENGTH.get(candidate_length, ()):
            if is_single_edit_variant(normalized, candidate):
                matches.append(candidate)
        if len(matches) > 1:
            return normalized
    if len(matches) == 1:
        return matches[0]
    return normalized


def collect_negated_insult_indices(tokens: Sequence[str]) -> set[int]:
    insult_words = MILD_INSULT_WORDS | STRONG_INSULT_WORDS
    negated_indices: set[int] = set()
    for index, token in enumerate(tokens):
        if token not in NEGATION_WORDS:
            continue
        for lookahead in range(index + 1, min(index + 3, len(tokens) - 1) + 1):
            if tokens[lookahead] in insult_words:
                negated_indices.add(lookahead)
    return negated_indices


def is_harm_recipient(token: str) -> bool:
    return token in HARM_RECIPIENT_WORDS or (
        len(token) >= 4 and token.endswith(("ам", "ям"))
    )


def has_targeted_harm(tokens: Sequence[str]) -> bool:
    if len(tokens) > 5:
        return False
    for index, token in enumerate(tokens):
        if token not in HARM_NOUN_WORDS:
            continue
        for candidate in tokens[index + 1 : index + 3]:
            if is_harm_recipient(candidate):
                return True
    return False
