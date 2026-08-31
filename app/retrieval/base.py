from typing import Protocol, TypeVar

T = TypeVar("T")


class Retriever(Protocol[T]):
    def search(self, query: str, top_k: int) -> list[tuple[T, float]]: ...
