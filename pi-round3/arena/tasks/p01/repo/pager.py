"""Tiny pagination helper. See README.md for the documented behaviour."""
from dataclasses import dataclass
from typing import Any, List


@dataclass(frozen=True)
class Page:
    items: List[Any]
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_prev: bool
    has_next: bool


def paginate(items, page=1, per_page=10):
    if per_page < 1:
        raise ValueError("per_page must be at least 1")

    total_items = len(items)
    total_pages = total_items // per_page + 1

    # keep the page number inside the valid range
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    chunk = list(items[start:start + per_page])

    return Page(
        items=chunk,
        page=page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
    )
