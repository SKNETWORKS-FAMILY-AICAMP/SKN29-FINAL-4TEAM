"""Deterministic lexical retrieval components for Experiment Lab comparisons."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Sequence


_TOKEN_PATTERN = re.compile(r"[0-9a-z가-힣]+")


def korean_mixed_terms(text: str) -> list[str]:
    """Return word terms plus within-word character bigrams.

    Character bigrams reduce Korean 조사·어미 mismatch without a mutable external
    morphological dictionary. Prefixes keep word and character term spaces distinct.
    """

    normalized = unicodedata.normalize("NFKC", text).casefold()
    terms: list[str] = []
    for token in _TOKEN_PATTERN.findall(normalized):
        terms.append(f"w:{token}")
        if len(token) > 1:
            terms.extend(
                f"c:{token[index:index + 2]}"
                for index in range(len(token) - 1)
            )
    return terms


@dataclass(frozen=True, slots=True)
class BM25Parameters:
    k1: float = 1.5
    b: float = 0.75

    def __post_init__(self) -> None:
        if self.k1 <= 0:
            raise ValueError("BM25 k1은 0보다 커야 합니다.")
        if not 0 <= self.b <= 1:
            raise ValueError("BM25 b는 0..1 범위여야 합니다.")


class BM25Index:
    """Small in-memory BM25 index with immutable document order."""

    def __init__(
        self,
        documents: Sequence[str],
        *,
        parameters: BM25Parameters | None = None,
    ) -> None:
        if not documents:
            raise ValueError("BM25 문서가 비어 있습니다.")
        self.parameters = parameters or BM25Parameters()
        self.term_frequencies = [Counter(korean_mixed_terms(text)) for text in documents]
        self.document_lengths = [sum(frequencies.values()) for frequencies in self.term_frequencies]
        self.average_document_length = sum(self.document_lengths) / len(self.document_lengths)
        document_frequency: Counter[str] = Counter()
        for frequencies in self.term_frequencies:
            document_frequency.update(frequencies.keys())
        document_count = len(documents)
        self.inverse_document_frequency = {
            term: math.log(1 + (document_count - count + 0.5) / (count + 0.5))
            for term, count in document_frequency.items()
        }

    def scores(self, query: str) -> list[float]:
        query_terms = Counter(korean_mixed_terms(query))
        k1 = self.parameters.k1
        b = self.parameters.b
        scores: list[float] = []
        for frequencies, length in zip(self.term_frequencies, self.document_lengths):
            length_ratio = length / self.average_document_length if self.average_document_length else 0.0
            normalization = k1 * (1 - b + b * length_ratio)
            score = 0.0
            for term, query_frequency in query_terms.items():
                term_frequency = frequencies.get(term, 0)
                if term_frequency == 0:
                    continue
                idf = self.inverse_document_frequency.get(term, 0.0)
                score += (
                    idf
                    * (term_frequency * (k1 + 1))
                    / (term_frequency + normalization)
                    * query_frequency
                )
            scores.append(score)
        return scores
