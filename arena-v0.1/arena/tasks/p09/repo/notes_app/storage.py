"""Plain-file storage for notes: <base_dir>/<user>/<name>."""
import os


class Storage:
    def __init__(self, base_dir):
        self.base = os.path.abspath(base_dir)

    def _path(self, user, name):
        return os.path.join(self.base, user, name)

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
        root = os.path.join(self.base, user)
        names = []
        for folder, _dirs, files in os.walk(root):
            for filename in files:
                rel = os.path.relpath(os.path.join(folder, filename), root)
                names.append(rel.replace(os.sep, "/"))
        return sorted(names)
