"""Handcrafted sparse features for short and implicit toxic phrases."""


import re
from collections.abc import Sequence
from dataclasses import dataclass
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


@dataclass(slots=True)
class ExpertFeatureEvidence:
    feature_name: str
    feature_value: float
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_name": self.feature_name,
            "feature_value": round(self.feature_value, 6),
            "reasons": list(self.reasons),
        }


@dataclass(slots=True)
class ExpertFeatureDiagnostics:
    canonical_tokens: list[str]
    triggered_features: list[ExpertFeatureEvidence]

    def to_feature_row(self, feature_names: Sequence[str]) -> list[float]:
        values = {item.feature_name: item.feature_value for item in self.triggered_features}
        return [float(values.get(name, 0.0)) for name in feature_names]


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

    def _build_current_diagnostics(
        self,
        lowered: str,
        tokens: Sequence[str],
    ) -> ExpertFeatureDiagnostics:
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

        matched_mild_insults = [
            token
            for index, token in enumerate(canonical_tokens)
            if token in MILD_INSULT_WORDS and index not in negated_insult_indices
        ]
        matched_strong_insults = [
            token
            for index, token in enumerate(canonical_tokens)
            if token in STRONG_INSULT_WORDS and index not in negated_insult_indices
        ]
        matched_profanities = [token for token in canonical_tokens if token in PROFANE_WORDS]
        matched_identity_terms = [token for token in canonical_tokens if token in IDENTITY_TERMS]
        matched_harm_terms = [token for token in canonical_tokens if token in HARM_NOUN_WORDS]
        matched_imperatives = [token for token in canonical_tokens if token in IMPERATIVE_CUES]
        matched_second_person = [token for token in canonical_tokens if token in SECOND_PERSON_WORDS]
        matched_patterns = [
            f"pattern:{pattern.pattern}"
            for pattern in DISMISSIVE_PATTERNS
            if pattern.search(canonical_text) is not None
        ]
        negated_tokens = [canonical_tokens[index] for index in sorted(negated_insult_indices)]

        feature_rows = [
            ExpertFeatureEvidence(
                feature_name="token_count",
                feature_value=float(token_count),
                reasons=[f"token_count:{token_count}"],
            ),
            ExpertFeatureEvidence(
                feature_name="exclamation_count",
                feature_value=float(lowered.count("!")),
                reasons=[f"char:!:{lowered.count('!')}"] if "!" in lowered else [],
            ),
            ExpertFeatureEvidence(
                feature_name="question_count",
                feature_value=float(lowered.count("?")),
                reasons=[f"char:?:{lowered.count('?')}"] if "?" in lowered else [],
            ),
            ExpertFeatureEvidence(
                feature_name="second_person_count",
                feature_value=float(second_person_count),
                reasons=[f"token:{token}" for token in matched_second_person],
            ),
            ExpertFeatureEvidence(
                feature_name="mild_insult_count",
                feature_value=float(mild_insult_count),
                reasons=[f"token:{token}" for token in matched_mild_insults],
            ),
            ExpertFeatureEvidence(
                feature_name="strong_insult_count",
                feature_value=float(strong_insult_count),
                reasons=[f"token:{token}" for token in matched_strong_insults],
            ),
            ExpertFeatureEvidence(
                feature_name="profane_count",
                feature_value=float(profane_count),
                reasons=[f"token:{token}" for token in matched_profanities],
            ),
            ExpertFeatureEvidence(
                feature_name="identity_term_count",
                feature_value=float(identity_term_count),
                reasons=[f"token:{token}" for token in matched_identity_terms],
            ),
            ExpertFeatureEvidence(
                feature_name="harm_term_count",
                feature_value=float(harm_term_count),
                reasons=[f"token:{token}" for token in matched_harm_terms],
            ),
            ExpertFeatureEvidence(
                feature_name="imperative_count",
                feature_value=float(imperative_count),
                reasons=[f"token:{token}" for token in matched_imperatives],
            ),
            ExpertFeatureEvidence(
                feature_name="has_dismissive_pattern",
                feature_value=float(has_dismissive_pattern),
                reasons=matched_patterns,
            ),
            ExpertFeatureEvidence(
                feature_name="has_second_person_negated_insult",
                feature_value=float(has_second_person_negated_insult),
                reasons=[*([f"token:{token}" for token in matched_second_person]), *([f"negated_token:{token}" for token in negated_tokens])],
            ),
            ExpertFeatureEvidence(
                feature_name="has_pronoun_insult",
                feature_value=float(has_pronoun_insult),
                reasons=[*([f"token:{token}" for token in matched_second_person]), *([f"insult_token:{token}" for token in matched_mild_insults + matched_strong_insults])],
            ),
            ExpertFeatureEvidence(
                feature_name="has_pronoun_profanity",
                feature_value=float(has_pronoun_profanity),
                reasons=[*([f"token:{token}" for token in matched_second_person]), *([f"profanity_token:{token}" for token in matched_profanities])],
            ),
            ExpertFeatureEvidence(
                feature_name="has_identity_dismissal",
                feature_value=float(has_identity_dismissal),
                reasons=(["phrase:спросить забыли"] if "спросить забыли" in canonical_text else []) + [f"token:{token}" for token in matched_identity_terms],
            ),
            ExpertFeatureEvidence(
                feature_name="has_targeted_harm",
                feature_value=float(has_targeted_harm),
                reasons=[f"token:{token}" for token in matched_harm_terms] + [f"recipient:{token}" for token in canonical_tokens if _is_harm_recipient(token)],
            ),
            ExpertFeatureEvidence(
                feature_name="has_untargeted_harm",
                feature_value=float(has_untargeted_harm),
                reasons=[f"token:{token}" for token in matched_harm_terms],
            ),
            ExpertFeatureEvidence(
                feature_name="has_short_targeted_attack",
                feature_value=float(has_short_targeted_attack),
                reasons=[f"token_count:{token_count}", "composite:short_targeted_attack"],
            ),
        ]
        triggered = [
            item
            for item in feature_rows
            if item.feature_value != 0.0 or item.feature_name == "token_count"
        ]
        return ExpertFeatureDiagnostics(
            canonical_tokens=canonical_tokens,
            triggered_features=triggered,
        )

    def analyze_text(self, text: str) -> ExpertFeatureDiagnostics:
        lowered = str(text).lower()
        tokens = TOKEN_PATTERN.findall(lowered)
        feature_layout_version = getattr(self, "feature_layout_version", 2)
        if feature_layout_version <= 2:
            raise ValueError("Expert diagnostics are only supported for feature layout version 3.")
        return self._build_current_diagnostics(lowered, tokens)

    def transform(self, texts: Sequence[str]) -> csr_matrix:
        rows: list[list[float]] = []
        feature_layout_version = getattr(self, "feature_layout_version", 2)
        for text in texts:
            lowered = str(text).lower()
            tokens = TOKEN_PATTERN.findall(lowered)
            if feature_layout_version <= 2:
                rows.append(self._build_legacy_row(lowered, tokens))
            else:
                rows.append(
                    self._build_current_diagnostics(lowered, tokens).to_feature_row(FEATURE_NAMES)
                )
        return csr_matrix(np.asarray(rows, dtype=np.float64))

    def get_feature_names_out(self, input_features: Sequence[str] | None = None) -> np.ndarray:
        feature_layout_version = getattr(self, "feature_layout_version", 2)
        if feature_layout_version <= 2:
            return np.asarray(LEGACY_FEATURE_NAMES, dtype=object)
        return np.asarray(FEATURE_NAMES, dtype=object)
