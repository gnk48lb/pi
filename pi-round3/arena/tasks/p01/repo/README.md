# pager

A tiny pagination helper for lists. Pure Python, no dependencies.

```python
from pager import paginate

page = paginate(["a", "b", "c", "d", "e"], page=2, per_page=2)
page.items        # ['c', 'd']
page.total_pages  # 3
page.has_prev     # True
page.has_next     # True
```

## API

### `paginate(items, page=1, per_page=10) -> Page`

* `items` - any iterable (list, tuple, range, generator, ...). It is read once and never modified.
* `page` - 1-based page number.
* `per_page` - number of items per page.

Returns a `Page`, a frozen dataclass with these fields:

| field         | meaning                                                          |
|---------------|------------------------------------------------------------------|
| `items`       | a new list with the items on the requested page                  |
| `page`        | the requested page number, exactly as given                      |
| `per_page`    | items per page, exactly as given                                 |
| `total_items` | number of items in the whole input                               |
| `total_pages` | number of pages needed to show every item; never less than 1     |
| `has_prev`    | `True` if `page` is greater than 1                               |
| `has_next`    | `True` if there is a page after `page`                           |

### Rules

1. Pages are 1-based. `page` must be an `int` that is at least 1; anything else
   (`0`, `-3`, `2.5`, `"2"`, `None`, ...) raises `ValueError`.
2. `per_page` must be an `int` from 1 to 100 (inclusive); anything else
   (`0`, `101`, `2.5`, `"10"`, `None`, ...) raises `ValueError`.
3. `total_pages` is the number of pages needed to show all items, but never less
   than 1: an empty input has exactly one (empty) page.
4. Asking for a page after the last one is not an error. It returns an empty
   `items` list with `has_next` false and `has_prev` true, and `page` still
   reports the number that was asked for.
5. The input is never modified, and `Page.items` is always a new list, never the
   input object itself.

## Development

Run the tests from the repository root:

```
python3 -m unittest
```
