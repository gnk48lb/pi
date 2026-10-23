"""Judge an agent-written test suite for discounts.py: it must pass on the real module and kill enough mutants."""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.getcwd()
HERE = os.path.dirname(os.path.abspath(__file__))
MIN_TESTS = 8
MIN_KILLED = 10          # of the mutants in mutants/
CMD = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]


def run_suite(module_source=None):
    work = tempfile.mkdtemp(prefix="mut-")
    try:
        dst = os.path.join(work, "ws")
        shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns("hidden_check", "__pycache__", ".git"))
        if module_source is not None:
            shutil.copy(module_source, os.path.join(dst, "discounts.py"))
        try:
            r = subprocess.run(CMD, cwd=dst, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        except subprocess.TimeoutExpired:
            return 124, "timeout"
        return r.returncode, r.stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    code, out = run_suite()
    m = re.search(r"^Ran (\d+) tests?", out, re.M)
    ran = int(m.group(1)) if m else 0
    print(out[-1500:])
    if code != 0:
        print("ARENA_NOTE: the tests fail on the real module")
        return 1
    if ran < MIN_TESTS:
        print("ARENA_NOTE: only %d tests found (need at least %d)" % (ran, MIN_TESTS))
        return 1
    mutants = sorted(glob.glob(os.path.join(HERE, "mutants", "*.py")))
    survived = []
    for path in mutants:
        code, _ = run_suite(path)
        if code == 0:
            survived.append(os.path.basename(path)[:-3])
    killed = len(mutants) - len(survived)
    print("survivors: %s" % ", ".join(survived) if survived else "no survivors")
    print("ARENA_NOTE: %d tests, killed %d/%d mutants" % (ran, killed, len(mutants)))
    return 0 if killed >= MIN_KILLED else 1


if __name__ == "__main__":
    sys.exit(main())
