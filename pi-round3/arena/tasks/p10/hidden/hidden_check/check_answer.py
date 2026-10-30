"""Hidden judge of p10 (read-only question answering).

Reads the agent's final answer from $ARENA_FINAL, checks the five answers against what the code really does and
checks that the workspace was left untouched.  Prints "ARENA_NOTE: ..." lines for the report; exit code 0 = pass.
"""
import os
import re
import subprocess
import sys

NUM = re.compile(r"(?<![\d.])\d+(?:\.\d+)?(?![\d])")
ITEM = re.compile(r"^\s*(?:[-*>]\s*)?(?:\*\*|__)?(?:Q|A)?\s*(\d)\s*(?:[.):]|-)(?:\*\*|__)?(?=\s|$)\s*(.*)$")


def parse_items(text):
    """Numbered answers 1..5 in order; any other line continues the item above it."""
    items = {}
    cur = 0
    for line in text.splitlines():
        m = ITEM.match(line)
        if m and int(m.group(1)) == cur + 1 and cur < 5:
            cur += 1
            items[cur] = m.group(2)
        elif cur:
            items[cur] += " " + line.strip()
    return items


def numbers(text):
    return [float(x) for x in NUM.findall(text)]


def has_number(text, value):
    return any(abs(n - value) < 1e-9 for n in numbers(text))


def q1(t):
    # the variable is TASKQ_MAX_ATTEMPTS (the README's TASKQ_RETRIES does not exist), default 5 (Job's own 3 is a decoy)
    if not re.search(r"TASKQ_MAX_ATTEMPTS", t, re.I) or not has_number(t, 5):
        return False
    if re.search(r"TASKQ_RETRIES", t) and not re.search(
            r"stale|outdated|out of date|out-of-date|wrong|incorrect|not (?:actually|used|read|honou?red|exist)|"
            r"does ?n[o']t|no longer|isn't|ignored|README|docs?\b", t, re.I):
        return False                                        # names the stale variable as an alternative
    return True


def q2(t):
    # attempts: 5 -> delays after failures 1..4: 1.5, 4.5, 13.5, min(30, 40.5) = 30; the 5th failure ends the job
    need, i = [1.5, 4.5, 13.5, 30.0], 0
    for n in numbers(t):
        if i < len(need) and abs(n - need[i]) < 1e-9:
            i += 1
    if i < len(need):
        return False
    if sum(1 for n in numbers(t) if abs(n - 30.0) < 1e-9) >= 2 and not re.search(r"cap|max|limit|clamp", t, re.I):
        return False                                        # five waits (30 listed twice) instead of four
    return not re.search(r"\b1\s*s?\s*,\s*2\s*s?\s*,\s*4\b", t)


def q3(t):
    # reaper runs every REAP_INTERVAL = 30 s (comment and docs say "once a minute"); stuck after VISIBILITY_TIMEOUT = 120 s
    return has_number(t, 30) and has_number(t, 120)


def q4(t):
    # FatalJobError -> Queue.bury -> State.DEAD, metrics.count("dead"), never retried
    return bool(re.search(r"dead", t, re.I)) and bool(re.search(r"\bno\b|\bnot\b|\bnever\b|n't\b|\bwithout\b", t, re.I))


def q5(t):
    # `max_attempts or settings.DEFAULT_MAX_ATTEMPTS`: 0 is falsy, so the default (5) applies
    if not has_number(t, 5):
        return False
    return not re.search(r"\b0\s+attempts|never\s+(?:run|executed)|no\s+attempts|zero\s+attempts", t, re.I)


CHECKS = {1: q1, 2: q2, 3: q3, 4: q4, 5: q5}


def main():
    path = os.environ.get("ARENA_FINAL", "")
    text = open(path, encoding="utf-8", errors="replace").read() if path and os.path.isfile(path) else ""
    items = parse_items(text)
    wrong = [n for n in CHECKS if n not in items or not CHECKS[n](items[n])]
    right = len(CHECKS) - len(wrong)
    note = "answers correct %d/%d" % (right, len(CHECKS))
    if wrong:
        missing = [n for n in wrong if n not in items]
        note += " (wrong: %s%s)" % (", ".join(map(str, wrong)), "; missing: " + ", ".join(map(str, missing)) if missing else "")
    print("ARENA_NOTE: " + note)
    ok = not wrong
    git = subprocess.run(["git", "status", "--porcelain", "--", ".", ":(exclude)hidden_check"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    dirty = [ln[3:] for ln in git.stdout.splitlines() if ln.strip()]
    if dirty:
        print("ARENA_NOTE: workspace modified: " + ", ".join(dirty[:5]))
        ok = False
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
