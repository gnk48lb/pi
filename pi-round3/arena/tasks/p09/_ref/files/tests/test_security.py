import os
import shutil
import tempfile
import unittest

from notes_app.errors import NotesError
from notes_app.storage import Storage


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Storage(os.path.join(self.dir, "data"))
        self.store.save_note("bob", "secret.txt", "bob's secret")
        self.outside = os.path.join(self.dir, "outside.txt")
        with open(self.outside, "w") as fh:
            fh.write("outside")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_dotdot_in_name(self):
        for name in ("../bob/secret.txt", "a/../../bob/secret.txt", "..", "a/.."):
            with self.assertRaises(NotesError, msg=name):
                self.store.read_note("alice", name)

    def test_absolute_name(self):
        with self.assertRaises(NotesError):
            self.store.read_note("alice", self.outside)

    def test_bad_user(self):
        for user in ("../bob", "", ".", "..", "a/b", "/abs"):
            with self.assertRaises(NotesError, msg=repr(user)):
                self.store.read_note(user, "secret.txt")
            with self.assertRaises(NotesError, msg=repr(user)):
                self.store.save_note(user, "x.txt", "x")

    def test_symlinked_directory_cannot_be_followed(self):
        self.store.save_note("alice", "keep.txt", "x")
        os.symlink(os.path.join(self.dir, "data", "bob"), os.path.join(self.dir, "data", "alice", "link"))
        with self.assertRaises(NotesError):
            self.store.read_note("alice", "link/secret.txt")
        with self.assertRaises(NotesError):
            self.store.save_note("alice", "link/new.txt", "x")

    def test_symlinked_file_outside_is_refused(self):
        self.store.save_note("alice", "keep.txt", "x")
        os.symlink(self.outside, os.path.join(self.dir, "data", "alice", "peek.txt"))
        with self.assertRaises(NotesError):
            self.store.read_note("alice", "peek.txt")

    def test_legitimate_names_still_work(self):
        for name in ("a..b.txt", ".hidden", "2026/todo.txt", "with space.txt", "ünï.txt"):
            self.store.save_note("alice", name, name)
            self.assertEqual(self.store.read_note("alice", name), name)

    def test_symlink_inside_the_users_directory_is_fine(self):
        self.store.save_note("alice", "real.txt", "real")
        os.symlink("real.txt", os.path.join(self.dir, "data", "alice", "alias.txt"))
        self.assertEqual(self.store.read_note("alice", "alias.txt"), "real")

    def test_nothing_outside_was_touched(self):
        with self.assertRaises(NotesError):
            self.store.save_note("alice", "../bob/secret.txt", "overwritten")
        self.assertEqual(self.store.read_note("bob", "secret.txt"), "bob's secret")
        with self.assertRaises(NotesError):
            self.store.delete_note("alice", "../bob/secret.txt")
        self.assertEqual(self.store.read_note("bob", "secret.txt"), "bob's secret")
