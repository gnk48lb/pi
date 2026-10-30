# notes_app

The storage layer of a small multi-user notes service. Notes are plain text files:

```
<base_dir>/<user>/<name>          e.g.  data/alice/shopping.txt   data/alice/2026/todo.txt
```

```python
from notes_app.storage import Storage

store = Storage("data")
store.save_note("alice", "2026/todo.txt", "buy milk")
store.read_note("alice", "2026/todo.txt")      # 'buy milk'
store.list_notes("alice")                      # ['2026/todo.txt']
store.delete_note("alice", "2026/todo.txt")
```

* `user` and `name` come straight from HTTP requests, i.e. from untrusted people.
* Names use `/` as separator and may contain subfolders. Missing notes raise `FileNotFoundError`.
* `list_notes(user)` returns the names of all notes of the user, sorted, with `/` separators.
* Things that are not allowed raise `notes_app.errors.NotesError`.

## Tests

`python3 -m unittest`
