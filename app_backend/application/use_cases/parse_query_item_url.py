from __future__ import annotations


class ParseQueryItemUrlUseCase:
    def __init__(self, parser) -> None:
        self._parser = parser

    def execute(self, *, product_url: str):
        return self._parser.parse(product_url)
