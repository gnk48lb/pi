import shutil
import tempfile
import unittest

from notes_app.storage import Storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Storage(self.dir)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_save_and_read(self):
        self.store.save_note("alice", "todo.txt", "buy milk")
        self.assertEqual(self.store.read_note("alice", "todo.txt"), "buy milk")

    def test_overwrite(self):
        self.store.save_note("alice", "a.txt", "one")
        self.store.save_note("alice", "a.txt", "two")
        self.assertEqual(self.store.read_note("alice", "a.txt"), "two")

    def test_subfolders(self):
        self.store.save_note("alice", "2026/jan/todo.txt", "x")
        self.assertEqual(self.store.read_note("alice", "2026/jan/todo.txt"), "x")

    def test_missing_note(self):
        with self.assertRaises(FileNotFoundError):
            self.store.read_note("alice", "nope.txt")

    def test_delete(self):
        self.store.save_note("alice", "a.txt", "x")
        self.store.delete_note("alice", "a.txt")
        with self.assertRaises(FileNotFoundError):
            self.store.read_note("alice", "a.txt")

    def test_list_is_sorted_and_per_user(self):
        self.store.save_note("alice", "b.txt", "1")
        self.store.save_note("alice", "a/c.txt", "2")
        self.store.save_note("bob", "z.txt", "3")
        self.assertEqual(self.store.list_notes("alice"), ["a/c.txt", "b.txt"])
        self.assertEqual(self.store.list_notes("bob"), ["z.txt"])
        self.assertEqual(self.store.list_notes("nobody"), [])

    def test_unicode_and_spaces(self):
        self.store.save_note("alice", "日本語 メモ.txt", "こんにちは")
        self.assertEqual(self.store.read_note("alice", "日本語 メモ.txt"), "こんにちは")
