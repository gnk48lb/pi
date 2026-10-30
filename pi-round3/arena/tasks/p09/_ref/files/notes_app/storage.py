"""Plain-file storage for notes: <base_dir>/<user>/<name>.

`user` and `name` are untrusted.  Every operation stays inside <base_dir>/<user>/, symbolic links included.
"""
import os
import re

from .errors import NotesError

USER_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")


class Storage:
    def __init__(self, base_dir):
        self.base = os.path.abspath(base_dir)

    def _user_root(self, user):
        if not isinstance(user, str) or not USER_RE.fullmatch(user) or user in (".", ".."):
            raise NotesError("invalid user name")
        return os.path.join(self.base, user)

    def _path(self, user, name):
        root = self._user_root(user)
        if not isinstance(name, str) or not name or "\0" in name or name.startswith("/"):
            raise NotesError("invalid note name")
        parts = name.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise NotesError("invalid note name")
        path = os.path.join(root, *parts)
        real_root = os.path.realpath(root)
        real_path = os.path.realpath(path)
        if os.path.commonpath([real_path, real_root]) != real_root or real_path == real_root:
            raise NotesError("note is outside the user's directory")
        return path

    def read_note(self, user, name):
        with open(self._path(user, name), encoding="utf-8") as fh:
            return fh.read()

    def save_note(self, user, name, text):
        path = self._path(user, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def delete_note(self, user, name):
        os.remove(self._path(user, name))

    def list_notes(self, user):
        root = self._user_root(user)
        real_root = os.path.realpath(root)
        names = []
        for folder, _dirs, files in os.walk(root):
            for filename in files:
                full = os.path.join(folder, filename)
                if os.path.commonpath([os.path.realpath(full), real_root]) != real_root:
                    continue
                names.append(os.path.relpath(full, root).replace(os.sep, "/"))
        return sorted(names)
