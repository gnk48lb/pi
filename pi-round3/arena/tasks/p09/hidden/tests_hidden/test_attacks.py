import os
import pathlib
import re
import shutil
import tempfile
import unittest

from notes_app.errors import NotesError
from notes_app.storage import Storage

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "data")
        self.store = Storage(self.data)
        self.store.save_note("alice", "mine.txt", "alice's note")
        self.store.save_note("bob", "secret.txt", "bob's secret")
        self.outside = os.path.join(self.tmp, "outside.txt")
        with open(self.outside, "w") as fh:
            fh.write("outside")
        self.snapshot = self.tree()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tree(self):
        out = {}
        for folder, dirs, files in os.walk(self.tmp):
            for f in files + dirs:
                p = os.path.join(folder, f)
                out[p] = (os.path.islink(p), open(p).read() if os.path.isfile(p) and not os.path.islink(p) else None)
        return out

    def assertUntouched(self):
        self.assertEqual(self.tree(), self.snapshot, "something on disk changed")

    def link(self, target, *where):
        path = os.path.join(self.data, "alice", *where)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.symlink(target, path)
        self.snapshot = self.tree()
        return path

    def refuse(self, user, name, ops=("read", "save", "delete")):
        for op in ops:
            with self.assertRaises(NotesError, msg="%s(%r, %r)" % (op, user, name)):
                if op == "read":
                    self.store.read_note(user, name)
                elif op == "save":
                    self.store.save_note(user, name, "pwned")
                else:
                    self.store.delete_note(user, name)
        self.assertUntouched()


class NameTricks(Base):
    def test_parent_segments(self):
        for name in ("../bob/secret.txt", "a/../../bob/secret.txt", "..", "a/..", "../../outside.txt", "x/../mine.txt"):
            self.refuse("alice", name)

    def test_dot_and_empty_segments_and_empty_name(self):
        for name in ("./mine.txt", "a//b.txt", "a/", "/", "", "a/./b.txt"):
            self.refuse("alice", name)

    def test_absolute_names(self):
        for name in (self.outside, os.path.join(self.data, "bob", "secret.txt"), "/etc/passwd", "/"):
            self.refuse("alice", name)

    def test_nul_character(self):
        for name in ("mine.txt\0.png", "\0", "a/\0/b"):
            self.refuse("alice", name)

    def test_list_does_not_accept_bad_users(self):
        for user in ("../bob", "", ".", "..", "a/b"):
            with self.assertRaises(NotesError, msg=repr(user)):
                self.store.list_notes(user)


class UserTricks(Base):
    def test_users_that_are_not_plain_names(self):
        for user in ("../bob", "bob/../alice", "", ".", "..", "a/b", "/abs", "a\0b", "a b", "x" * 65, "ünï", "a\\b"):
            self.refuse(user, "secret.txt", ops=("read", "save", "delete"))

    def test_plain_user_names_work(self):
        for user in ("carol_2", "d.e-f", "x" * 64, ".hidden-user", "UPPER"):
            self.store.save_note(user, "n.txt", user)
            self.assertEqual(self.store.read_note(user, "n.txt"), user)
            self.assertEqual(self.store.list_notes(user), ["n.txt"])


class Symlinks(Base):
    def test_directory_link_to_another_user(self):
        self.link(os.path.join(self.data, "bob"), "link")
        self.refuse("alice", "link/secret.txt")

    def test_directory_link_relative(self):
        self.link("../bob", "rel")
        self.refuse("alice", "rel/secret.txt")

    def test_directory_link_to_the_data_directory(self):
        self.link("..", "up")
        self.refuse("alice", "up/bob/secret.txt")

    def test_file_link_to_a_file_outside(self):
        self.link(self.outside, "peek.txt")
        self.refuse("alice", "peek.txt", ops=("read", "save"))

    def test_link_inside_a_subfolder(self):
        os.makedirs(os.path.join(self.data, "alice", "sub"))
        self.link("../../bob", "sub", "deep")
        self.refuse("alice", "sub/deep/secret.txt")
        self.refuse("alice", "sub/deep/new.txt", ops=("save",))

    def test_chain_of_links(self):
        self.link("second", "first")
        self.link(os.path.join(self.data, "bob"), "second")
        self.refuse("alice", "first/secret.txt")

    def test_links_that_stay_inside_are_fine(self):
        self.link("mine.txt", "alias.txt")
        self.assertEqual(self.store.read_note("alice", "alias.txt"), "alice's note")
        os.makedirs(os.path.join(self.data, "alice", "real"))
        self.store.save_note("alice", "real/n.txt", "n")
        self.link("real", "shortcut")
        self.assertEqual(self.store.read_note("alice", "shortcut/n.txt"), "n")


class NothingBrokenForHonestUsers(Base):
    def test_odd_but_legitimate_names(self):
        for name in ("a..b.txt", ".hidden", "...", "with space.txt", "ünï ✓.txt", "2026/jan/todo.txt", "a/b/c/d/e.txt", "x" * 200):
            self.store.save_note("alice", name, "content of " + name)
            self.assertEqual(self.store.read_note("alice", name), "content of " + name)
        listed = self.store.list_notes("alice")
        self.assertEqual(listed, sorted(listed))
        self.assertIn("2026/jan/todo.txt", listed)
        self.assertIn("a..b.txt", listed)

    def test_missing_notes_are_not_security_errors(self):
        with self.assertRaises(FileNotFoundError):
            self.store.read_note("alice", "nothing.txt")
        with self.assertRaises(FileNotFoundError):
            self.store.delete_note("alice", "nothing.txt")
        self.assertEqual(self.store.list_notes("nobody"), [])

    def test_delete_and_overwrite(self):
        self.store.save_note("alice", "mine.txt", "new")
        self.assertEqual(self.store.read_note("alice", "mine.txt"), "new")
        self.store.delete_note("alice", "mine.txt")
        self.assertEqual(self.store.list_notes("alice"), [])

    def test_other_users_are_unaffected(self):
        self.assertEqual(self.store.read_note("bob", "secret.txt"), "bob's secret")


class AgentTests(unittest.TestCase):
    def test_security_tests_were_added(self):
        text = (ROOT / "tests" / "test_security.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(re.findall(r"^\s*def test_", text, re.M)), 4)
        self.assertRegex(text, r"(?i)symlink")
        self.assertIn("NotesError", text)


if __name__ == "__main__":
    unittest.main()
