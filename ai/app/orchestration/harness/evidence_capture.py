"""Pre-generation evidence guard that preserves RetrievedChunk metadata for Harness verification."""

from __future__ import annotations

from typing import Any

from ...retrieval.models.retrieved_chunk import RetrievedChunk
from .product_match import ProductContext, ProductFamily, normalize_model_code
from .product_registry import resolve_product_generation


class GuardedEvidenceSearchService:
    """Capture raw search results and forward only customer-safe exact-model evidence."""

    VERIFIED_STATUSES = {"official_verified", "team_verified"}

    def __init__(self, delegate: Any, product: ProductContext) -> None:
        self.delegate = delegate
        self.product = product
        self._forwarded: list[RetrievedChunk] = []
        self._rejected: list[RetrievedChunk] = []
        self._all_rejected: list[RetrievedChunk] = []

    def begin_attempt(self) -> None:
        """Reset attempt-local evidence so a clean retry is not poisoned by the previous attempt."""

        self._forwarded = []
        self._rejected = []

    def search(self, *args: Any, **kwargs: Any) -> list[RetrievedChunk]:
        # Known-but-unapproved products must not reach embedding/pgvector at all.
        if not self.product.runtime_approved:
            return []

        guarded_args = args
        if args:
            guarded_args = (self._with_product_context(args[0]), *args[1:])
        elif "query" in kwargs:
            kwargs = dict(kwargs)
            kwargs["query"] = self._with_product_context(kwargs["query"])
        chunks = list(self.delegate.search(*guarded_args, **kwargs))
        expected_model = normalize_model_code(self.product.model_code)
        forwarded: list[RetrievedChunk] = []
        rejected: list[RetrievedChunk] = []

        for chunk in chunks:
            candidate = chunk.model_copy(deep=True)
            exact_model_match = normalize_model_code(candidate.model_code) == expected_model
            customer_safe = (
                self.product.runtime_approved
                and self.product.product_family != ProductFamily.UNKNOWN
                and candidate.allowed_use
                and candidate.runtime_eligible
                and candidate.verification_status in self.VERIFIED_STATUSES
                and exact_model_match
            )
            if customer_safe:
                forwarded.append(candidate)
            else:
                rejected.append(candidate)

        self._forwarded.extend(forwarded)
        self._rejected.extend(rejected)
        self._all_rejected.extend(rejected)
        return [chunk.model_copy(deep=True) for chunk in forwarded]

    def _with_product_context(self, query: Any) -> Any:
        model_copy = getattr(query, "model_copy", None)
        if not callable(model_copy):
            return query
        updates: dict[str, Any] = {"model_code": self.product.model_code}
        generation = resolve_product_generation(self.product.model_code)
        if generation is not None:
            updates["product_generation"] = generation
        return model_copy(update=updates)

    def evidence_for_harness(self, ctx: Any) -> list[RetrievedChunk]:
        """Return actually-used safe chunks plus pre-generation rejected chunks for audit/decisioning."""

        used_ids = {
            item.chunk_id
            for item in (getattr(ctx, "evidence_references", []) or [])
        }
        used_safe = [
            chunk for chunk in self._forwarded if chunk.chunk_id in used_ids
        ]
        merged = [*used_safe, *self._rejected]
        deduplicated: dict[str, RetrievedChunk] = {}
        for chunk in merged:
            deduplicated.setdefault(chunk.chunk_id, chunk)
        return list(deduplicated.values())

    @property
    def rejected_chunk_ids(self) -> list[str]:
        return list(dict.fromkeys(chunk.chunk_id for chunk in self._all_rejected))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)
