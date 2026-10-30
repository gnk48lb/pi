"""Tiny pagination helper. See README.md for the documented behaviour."""
from dataclasses import dataclass
from typing import Any, List

MAX_PER_PAGE = 100


@dataclass(frozen=True)
class Page:
    items: List[Any]
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_prev: bool
    has_next: bool


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def paginate(items, page=1, per_page=10):
    if not _is_int(per_page) or not 1 <= per_page <= MAX_PER_PAGE:
        raise ValueError("per_page must be an int from 1 to %d" % MAX_PER_PAGE)
    if not _is_int(page) or page < 1:
        raise ValueError("page must be an int >= 1")

    items = list(items)
    total_items = len(items)
    total_pages = max(1, -(-total_items // per_page))

    start = (page - 1) * per_page
    chunk = items[start:start + per_page]

    return Page(
        items=chunk,
        page=page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
        has_prev=page > 1,
        has_next=page < total_pages,
    )
