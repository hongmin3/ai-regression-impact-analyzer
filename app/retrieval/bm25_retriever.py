from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Generic, TypeVar

from rank_bm25 import BM25Okapi

T = TypeVar("T")


def tokenize(text: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z가-힣_]+", text.lower())


class BM25Retriever(Generic[T]):
    def __init__(self, items: Sequence[T], text_getter: Callable[[T], str]) -> None:
        self.items = list(items)
        self.corpus = [tokenize(text_getter(item)) for item in self.items]
        self.index = BM25Okapi(self.corpus) if self.corpus else None

    def search(self, query: str, top_k: int) -> list[tuple[T, float]]:
        if not self.index:
            return []
        scores = self.index.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda item: float(item[1]), reverse=True)
        # BM25 can produce zero/negative IDF in very small corpora. Keep ranked
        # items so an MVP with only a few registered TC/spec chunks still works.
        return [(self.items[index], float(score)) for index, score in ranked[:top_k]]
