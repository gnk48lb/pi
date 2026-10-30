"""Arena core: isolated environments, running one agent, verifying the result, building the result row.

Design rules (see README.md):
  * every run gets an empty HOME, TMPDIR and agent config dir (at the same path every time, see fresh_env_dir), so
    nothing leaks between runs or in from the user's own pi / Claude Code setup;
  * the agent's environment is built from a whitelist (no inherited secrets);
  * the model gateway is the only reachable network endpoint (everything else is pointed at a dead proxy);
  * the verifier runs *after* the agent exits, with hidden tests the agent never saw.
"""
import datetime
import getpass
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time

import arena_parse

ARENA_DIR = os.path.dirname(os.path.abspath(__file__))
BLACKHOLE = "http://127.0.0.1:9"          # discard port: connection refused immediately
LOCAL_NO_PROXY = "127.0.0.1,localhost,::1"
GIT_IDENT = {"GIT_AUTHOR_NAME": "arena", "GIT_AUTHOR_EMAIL": "arena@example.invalid",
             "GIT_COMMITTER_NAME": "arena", "GIT_COMMITTER_EMAIL": "arena@example.invalid"}
TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec|specs|hidden_test|tests_hidden)(/|$)|"
                          r"(^|/)test_[^/]*$|[^/]*_test\.[a-z]+$|[^/]*\.(test|spec)\.[a-z]+$")
INFRA_RE = re.compile(r"(\b429\b|rate.?limit|overloaded|\b50[0-9]\b|ECONN|ETIMEDOUT|EAI_AGAIN|fetch failed|"
                      r"socket hang up|bad gateway|gateway timeout|service unavailable|temporarily unavailable|"
                      r"connection (refused|reset|error|closed)|unable to connect|network error|terminated)", re.I)


# ------------------------------------------------------------------------------------------ small helpers
def nap(seconds):
    """time.sleep for the pauses between requests / retries.  ARENA_SLEEP_SCALE=0.02 shrinks them (used by the
    simulations that exercise the whole flow against a mock gateway); real runs never set it."""
    try:
        scale = float(os.environ.get("ARENA_SLEEP_SCALE", "1"))
    except ValueError:
        scale = 1.0
    time.sleep(max(0.0, float(seconds)) * scale)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_rmtree(path, under):
    """rmtree, but only for a directory strictly inside `under` (never follows a bad path to something precious)."""
    path, under = os.path.realpath(path), os.path.realpath(under)
    if not path.startswith(under + os.sep) or len(under) < 4:
        raise RuntimeError("refusing to delete %s (not inside %s)" % (path, under))
    shutil.rmtree(path, ignore_errors=True)


GATE_RE = re.compile(r"^\[(?:safety|fidelity)-gate\] blocked (\S+): (.*)$", re.M)
BUDGET_SOFT_RE = re.compile(r"^\[budget-guard\] soft limit", re.M)
BUDGET_HARD_RE = re.compile(r"^\[budget-guard\] stopped", re.M)


def parse_guard(stderr_text):
    """Events written to stderr by the v1 extensions (non-interactive mode): gate blocks (rule id and a snippet of the
    command or path; the safety-gate's ids are plain words, the fidelity-gate's start with "fid-") and budget-guard
    soft / hard limits.  All zeros for an agent without those extensions."""
    blocks = GATE_RE.findall(stderr_text or "")
    ids = {}
    for rid, _ in blocks:
        ids[rid] = ids.get(rid, 0) + 1
    return {"gate_blocks": len(blocks), "gate_ids": ids,
            "fid_blocks": sum(1 for rid, _ in blocks if rid.startswith("fid-")),
            "gate_examples": ["%s: %s" % (rid, detail.strip()[:160]) for rid, detail in blocks[:5]],
            "budget_soft": len(BUDGET_SOFT_RE.findall(stderr_text or "")),
            "budget_hard": len(BUDGET_HARD_RE.findall(stderr_text or ""))}


def tail(path, n=2000):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


# ------------------------------------------------------------------------------------------ prices / cost
def load_prices(arena_dir=ARENA_DIR):
    return load_json(os.path.join(arena_dir, "prices.json"), {"models": {}})


def price_for(prices, model, override=None):
    """Price entry (a copy carrying its table key as "name") for a model id, or None when the table has no match."""
    models = prices.get("models", {})
    if override:
        p = models.get(override)
        return dict(p, name=override) if p else None
    m = (model or "").lower()
    for key, p in models.items():
        if any(s.lower() in m for s in p.get("match", [])):
            return dict(p, name=key)
    return None


def compute_cost(tokens, price):
    """USD from fresh input, cache read/write and output tokens (each a count) and a price entry (USD per 1M)."""
    if price is None:
        return None
    return (tokens["input"] * price["input"] + tokens["cache_read"] * price["cache_read"]
            + tokens["cache_write"] * price.get("cache_write", price["input"]) + tokens["output"] * price["output"]) / 1e6


# ------------------------------------------------------------------------------------------ tasks
def task_dir(arena_dir, task_id):
    return os.path.join(arena_dir, "tasks", task_id)


SPLITS = ("dev", "held", "hard")


def list_tasks(arena_dir=ARENA_DIR, split=None):
    """All task ids; with split="dev" / "held" / "hard" only the tasks of that split (task.json "split", default "dev")."""
    root = os.path.join(arena_dir, "tasks")
    ids = sorted(d for d in os.listdir(root) if os.path.isfile(os.path.join(root, d, "task.json")))
    if split:
        ids = [t for t in ids if (load_json(os.path.join(root, t, "task.json")) or {}).get("split", "dev") == split]
    return ids


def missing_tools(task):
    """Programs the task needs (task.json "requires") that are not on PATH."""
    return [t for t in task.get("requires", []) if shutil.which(t) is None]


def expand_tasks(arena_dir, spec):
    """--tasks value -> task ids: "all", "dev" (the tasks to iterate on), "held" (the held-out ones: look at them rarely),
    "hard" (harder tasks, a separate group so that the dev suite keeps its meaning) or a comma list.
    Unknown ids are an error."""
    if spec == "all":
        return list_tasks(arena_dir)
    if spec in SPLITS:
        return list_tasks(arena_dir, spec)
    ids = [t for t in spec.split(",") if t]
    known = set(list_tasks(arena_dir))
    bad = [t for t in ids if t not in known]
    if bad:
        raise SystemExit("unknown task(s) %s (have: %s; or all / dev / held / hard)" % (", ".join(bad), ", ".join(sorted(known))))
    return ids


def select_tasks(arena_dir, spec, say=None):
    """expand_tasks, minus the tasks that need a program this machine does not have (make, node, ...), with a note."""
    ids = expand_tasks(arena_dir, spec)
    usable = []
    for t in ids:
        miss = missing_tools(load_task(arena_dir, t))
        if miss:
            (say or print)("note: leaving out task %s: %s not found on PATH" % (t, ", ".join(miss)))
        else:
            usable.append(t)
    return usable


def load_task(arena_dir, task_id):
    t = load_json(os.path.join(task_dir(arena_dir, task_id), "task.json"))
    if t is None:
        raise SystemExit("unknown task %r (have: %s)" % (task_id, ", ".join(list_tasks(arena_dir))))
    return t


def protected_hashes(arena_dir, task):
    base = os.path.join(task_dir(arena_dir, task["id"]), "repo")
    return {rel: sha256_file(os.path.join(base, rel)) for rel in task.get("protected", [])
            if os.path.isfile(os.path.join(base, rel))}


# ------------------------------------------------------------------------------------------ environments
def base_env(run_dir, allow_net=False, extra=None, real_home=False):
    """Whitelisted environment for an agent (or the verifier).  Nothing is inherited except PATH (and HOME when
    `real_home`, a fallback for tools that cannot start with a fresh HOME)."""
    home, tmp = os.path.join(run_dir, "home"), os.path.join(run_dir, "tmp")
    os.makedirs(home, exist_ok=True)
    os.makedirs(tmp, exist_ok=True)
    if real_home and os.environ.get("HOME"):
        home = os.environ["HOME"]
    try:
        user = getpass.getuser()
    except Exception:  # noqa
        user = "arena"
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": home, "TMPDIR": tmp, "TMP": tmp, "TEMP": tmp,
        "USER": user, "LOGNAME": user, "SHELL": "/bin/bash",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
        "TERM": "dumb", "NO_COLOR": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
    }
    env.update(GIT_IDENT)
    if not allow_net:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env[k] = BLACKHOLE
    env["NO_PROXY"] = env["no_proxy"] = LOCAL_NO_PROXY
    if extra:
        env.update(extra)
    return env


def tree_digest(path):
    """Short sha256 over (relative path, content) of every file below `path`; None for no path."""
    if not path:
        return None
    h = hashlib.sha256()
    for dp, dns, fns in os.walk(path):
        dns.sort()
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            h.update(os.path.relpath(p, path).encode() + b"\0")
            with open(p, "rb") as f:
                h.update(f.read())
            h.update(b"\0")
    return h.hexdigest()[:12]


def merge_overlay(base_dir, overlay_dir):
    """Layer a variant on top of the blank baseline: settings.json is merged key by key (the overlay wins),
    every other file is added or replaced.  The provider/model entry in models.json therefore stays identical
    unless the overlay deliberately ships its own models.json."""
    for dp, dns, fns in os.walk(overlay_dir):
        rel = os.path.relpath(dp, overlay_dir)
        dest = os.path.normpath(os.path.join(base_dir, rel))
        os.makedirs(dest, exist_ok=True)
        for fn in fns:
            src, dst = os.path.join(dp, fn), os.path.join(dest, fn)
            if rel == "." and fn == "settings.json" and os.path.isfile(dst):
                merged = load_json(dst, {}) or {}
                merged.update(load_json(src, {}) or {})
                save_json(dst, merged)
            else:
                shutil.copy2(src, dst)


def pi_env(run_dir, cfg_root, allow_net=False, template=None, real_home=False):
    """Copy the blank pi config made by `setup` into the run dir (plus the variant overlay, if any), point pi at it."""
    agent_dir = os.path.join(run_dir, "pi-agent")
    shutil.copytree(os.path.join(cfg_root, "pi"), agent_dir)
    if template:
        merge_overlay(agent_dir, template)
    return base_env(run_dir, allow_net, {
        "PI_CODING_AGENT_DIR": agent_dir, "PI_OFFLINE": "1", "PI_SKIP_VERSION_CHECK": "1", "PI_TELEMETRY": "0"},
        real_home)


def cc_env(run_dir, cfg_root, allow_net=False, real_home=False):
    """Fresh CLAUDE_CONFIG_DIR + the gateway variables recorded by `setup`.  Behaviour-changing switches such as
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC are deliberately NOT set: it removes a tool and ~2k prompt tokens."""
    conf_dir = os.path.join(run_dir, "cc-config")
    os.makedirs(conf_dir, exist_ok=True)
    src = os.path.join(cfg_root, "cc", "settings.json")
    if os.path.isfile(src):
        shutil.copy(src, os.path.join(conf_dir, "settings.json"))
    extra = {"CLAUDE_CONFIG_DIR": conf_dir, "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1",
             "DISABLE_ERROR_REPORTING": "1"}
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        extra["IS_SANDBOX"] = "1"          # claude refuses bypassPermissions as root otherwise
    extra.update(load_json(os.path.join(cfg_root, "cc", "env.json"), {}))
    return base_env(run_dir, allow_net, extra, real_home)


# ------------------------------------------------------------------------------------------ fixed agent directories
def env_root(ws_root):
    """Parent of the per-agent HOME / TMPDIR / config directories: <ws_root>-env, e.g. /tmp/arena-ws-env."""
    return os.path.abspath(ws_root).rstrip(os.sep) + "-env"


def fresh_env_dir(ws_root, agent):
    """The agent's private HOME + TMPDIR + config parent, emptied: <ws_root>-env/<agent>.

    The path is the SAME on every run on purpose.  Agents print their own paths into the system prompt (Claude Code:
    its memory directory under CLAUDE_CONFIG_DIR, pi: the path of every AGENTS.md it loads), so a path that changes
    per run makes the first request of every run miss the gateway's prompt cache for a reason that has nothing to do
    with the harness.  A real installation has a stable ~/.claude and ~/.pi as well."""
    root = env_root(ws_root)
    d = os.path.join(root, agent)
    os.makedirs(root, exist_ok=True)
    if os.path.exists(d):
        safe_rmtree(d, root)
    os.makedirs(d)
    return d


def retire_env_dir(env_dir, run_dir, keep=False):
    """After a run: move the agent directories into <run_dir>/env (keep, for debugging) or delete them."""
    if not os.path.isdir(env_dir):
        return
    if keep:
        dest = os.path.join(run_dir, "env")
        shutil.rmtree(dest, ignore_errors=True)
        shutil.move(env_dir, dest)
    else:
        safe_rmtree(env_dir, os.path.dirname(env_dir))


_LOCKS = []          # keeps the lock file object (and with it the lock) alive until the process ends


def arena_lock(ws_root, what=""):
    """One agent-running arena command at a time per workspace root.  Workspaces and agent directories sit at fixed
    paths, so two concurrent runs would overwrite each other and the process sweep (by TMPDIR marker) would kill the
    other run's agent.  The OS drops the lock when the process ends, however it ends.  Locking problems other than
    "somebody else holds it" (an odd filesystem, say) are ignored: the lock is a guard rail, not a requirement."""
    try:
        import fcntl
        root = env_root(ws_root)
        os.makedirs(root, exist_ok=True)
        f = open(os.path.join(root, ".lock"), "a+")
    except (ImportError, OSError):
        return
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.seek(0)
        holder = f.read().strip() or "unknown"
        f.close()
        raise SystemExit("error: another arena command (%s) is already using the workspace root %s.\n"
                         "Wait for it to finish (or stop it with Ctrl-C), or give this command its own --ws-root."
                         % (holder, ws_root))
    except OSError:
        f.close()
        return
    f.seek(0)
    f.truncate()
    f.write("pid %d%s\n" % (os.getpid(), ", " + what if what else ""))
    f.flush()
    _LOCKS.append(f)


def agent_argv(agent, bins, prompt, opts):
    """Command line for one run.  opts: pi_thinking, cc_effort, toolset ('default'|'aligned'), extra_args."""
    if agent == "pi":
        argv = [bins["pi"], "-p", prompt, "--mode", "json", "--no-session"]
        if opts.get("pi_thinking"):
            argv += ["--thinking", opts["pi_thinking"]]
        if opts.get("toolset") == "aligned":
            argv += ["--tools", "read,bash,edit,write"]
    else:
        argv = [bins["cc"], "-p", prompt, "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                "--permission-mode", "bypassPermissions"]
        if opts.get("toolset") == "aligned":
            argv += ["--tools", "Bash,Read,Edit,Write"]
        else:
            argv += ["--disallowedTools", "WebFetch,WebSearch"]
        if opts.get("cc_effort"):
            argv += ["--effort", opts["cc_effort"]]
    return argv + list(opts.get("extra_args") or [])


def tool_version(binary, env):
    try:
        r = subprocess.run([binary, "--version"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=60, stdin=subprocess.DEVNULL)
        m = re.search(r"\d+\.\d+\.\d+(?:[-+.\w]*)?", r.stdout or "")
        if r.returncode != 0 or not m:
            return "unknown (exit %d: %s)" % (r.returncode, (r.stdout or "").strip()[:200])
        return m.group(0)
    except Exception as e:  # noqa
        return "unknown (%s)" % e


# ------------------------------------------------------------------------------------------ workspace
BASELINE_DATE = "2020-01-01T00:00:00+0000"


def prepare_workspace(arena_dir, task, ws, ws_root, env):
    """Fresh copy of the task repo at a fixed path, committed as the baseline.  Returns the baseline commit.

    The baseline commit gets a fixed date, so its hash is the same on every run of a task.  Claude Code lists the recent
    commits ("f37febe baseline") in the first message of the conversation; with a hash that changes per run the first
    request of every run would miss the gateway's prompt cache after the system prompt."""
    if os.path.exists(ws):
        safe_rmtree(ws, ws_root)
    os.makedirs(os.path.dirname(ws), exist_ok=True)
    shutil.copytree(os.path.join(task_dir(arena_dir, task["id"]), "repo"), ws, symlinks=True)
    genv = dict(env, GIT_AUTHOR_DATE=BASELINE_DATE, GIT_COMMITTER_DATE=BASELINE_DATE)

    def git(*a):
        r = subprocess.run(["git", "-C", ws, "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"] + list(a),
                           env=genv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (" ".join(a), r.stdout))
        return r.stdout.strip()

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "baseline")
    return git("rev-parse", "HEAD")


# ------------------------------------------------------------------------------------------ running an agent
def _kill_group(proc, term_first):
    pg = proc.pid                       # start_new_session=True makes the child its own group leader
    try:
        if term_first:
            os.killpg(pg, signal.SIGTERM)
            deadline = time.time() + 5
            while time.time() < deadline and proc.poll() is None:
                time.sleep(0.1)
        os.killpg(pg, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def kill_by_env_marker(marker):
    """SIGKILL every process (same user) whose environment contains `marker` (our unique TMPDIR=<run>/tmp).
    Catches descendants that escaped the process group, e.g. shells a tool started with setsid."""
    killed = 0
    needle = b"\0" + marker + b"\0"
    for name in os.listdir("/proc"):
        if not name.isdigit() or int(name) == os.getpid():
            continue
        try:
            with open("/proc/%s/environ" % name, "rb") as f:
                data = b"\0" + f.read() + b"\0"
            if needle in data:
                os.kill(int(name), signal.SIGKILL)
                killed += 1
        except (OSError, ProcessLookupError, PermissionError):
            continue
    return killed


def run_agent(argv, env, cwd, out_dir, timeout):
    """Run the agent in its own process group, stream stdout to events.jsonl (+ arrival times to events.ts)."""
    os.makedirs(out_dir, exist_ok=True)
    ev_path, ts_path, err_path = (os.path.join(out_dir, n) for n in ("events.jsonl", "events.ts", "stderr.txt"))
    t0 = time.time()
    timed_out = False
    with open(err_path, "wb") as errf:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=errf, start_new_session=True)

        def pump():
            with open(ev_path, "wb") as evf, open(ts_path, "w") as tsf:
                for line in iter(proc.stdout.readline, b""):
                    tsf.write("%.3f\n" % (time.time() - t0))
                    evf.write(line)
                    evf.flush()
                    tsf.flush()

        th = threading.Thread(target=pump, daemon=True)
        th.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc, term_first=True)
            proc.wait()
        except BaseException:                     # Ctrl-C / SIGTERM: the agent lives in its own session, so stop it
            _kill_group(proc, term_first=False)   # explicitly, or it would keep working (and spending) behind our back
            kill_by_env_marker(("TMPDIR=%s" % env["TMPDIR"]).encode())
            raise
        _kill_group(proc, term_first=False)       # stragglers (background servers, ...) must not outlive the run
        stray = kill_by_env_marker(("TMPDIR=%s" % env["TMPDIR"]).encode())
        th.join(timeout=15)
    return {"exit_code": proc.returncode, "timed_out": timed_out, "wall_s": round(time.time() - t0, 3),
            "stray_killed": stray}


# ------------------------------------------------------------------------------------------ verification
def _count_tests(output):
    """(ran, failed) from unittest / node:test output; None when unknown."""
    m = re.search(r"^Ran (\d+) tests?", output, re.M)
    if m:
        ran = int(m.group(1))
        f = re.search(r"FAILED \((?:failures=(\d+))?(?:, )?(?:errors=(\d+))?", output)
        failed = (int(f.group(1) or 0) + int(f.group(2) or 0)) if f else 0
        return ran, failed
    tests = re.search(r"^(?:#|ℹ)\s*tests\s+(\d+)", output, re.M)
    fail = re.search(r"^(?:#|ℹ)\s*fail\s+(\d+)", output, re.M)
    if tests:
        return int(tests.group(1)), int(fail.group(1)) if fail else 0
    return None, None


def diff_stats(ws, base, env, out_dir):
    """Stage everything (respecting .gitignore) and diff against the baseline commit."""
    def git(*a):
        return subprocess.run(["git", "-C", ws] + list(a), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, errors="replace")
    git("add", "-A")
    num = git("diff", "--cached", "--numstat", base).stdout
    stats = {"files": 0, "added": 0, "removed": 0, "src_lines": 0, "test_lines": 0, "paths": []}
    for line in num.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a, r, path = parts
        a = int(a) if a.isdigit() else 0
        r = int(r) if r.isdigit() else 0
        stats["files"] += 1
        stats["added"] += a
        stats["removed"] += r
        stats["paths"].append(path)
        stats["test_lines" if TEST_PATH_RE.search(path) else "src_lines"] += a + r
    patch = git("diff", "--cached", base).stdout
    with open(os.path.join(out_dir, "diff.patch"), "w", encoding="utf-8", errors="replace") as f:
        f.write(patch[:400000])
    return stats


def verify(arena_dir, task, ws, base, env, out_dir, protected, final_text=""):
    """Run the hidden verifier.  Returns a dict; never raises for a failing agent.

    The agent's final answer is written to <out_dir>/final.txt and its path is given to the verifier commands as
    $ARENA_FINAL (question-answering tasks are judged on it).  A verifier command may print lines "ARENA_NOTE: text";
    they are collected in res["notes"] (e.g. "killed 6/10 mutants") and shown by the report for failing runs."""
    res = {"solved": False, "reason": None, "tampered": [], "tests_ran": None, "tests_failed": None, "diff": {}, "notes": []}
    final_path = os.path.join(out_dir, "final.txt")
    with open(final_path, "w", encoding="utf-8") as fh:
        fh.write(final_text or "")
    env = dict(env, ARENA_FINAL=final_path)
    res["diff"] = diff_stats(ws, base, env, out_dir)
    for rel, digest in protected.items():
        p = os.path.join(ws, rel)
        if not os.path.isfile(p) or sha256_file(p) != digest:
            res["tampered"].append(rel)
    hidden = os.path.join(task_dir(arena_dir, task["id"]), task.get("hidden_dir", "hidden"))
    if os.path.isdir(hidden):
        shutil.copytree(hidden, ws, dirs_exist_ok=True)
    logs, ok = [], True
    ran_total, failed_total, known = 0, 0, True
    for cmd in task["verify"]:
        try:
            r = subprocess.run(["bash", "-c", cmd], cwd=ws, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                               timeout=task.get("verify_timeout", 120))
            out, code = r.stdout, r.returncode
        except subprocess.TimeoutExpired as e:
            out, code = (e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) \
                        + "\n[verifier timed out]", 124
        logs.append("$ %s\n(exit %d)\n%s" % (cmd, code, out[-6000:]))
        res["notes"] += [ln.split(":", 1)[1].strip()[:200] for ln in out.splitlines() if ln.startswith("ARENA_NOTE:")]
        ran, failed = _count_tests(out)
        if ran is None:
            known = False
        else:
            ran_total += ran
            failed_total += failed
        if code != 0:
            ok = False
    if known:
        # unittest counts every failing subTest as a failure, so cap at the number of tests that ran
        res["tests_ran"], res["tests_failed"] = ran_total, min(failed_total, ran_total)
    with open(os.path.join(out_dir, "verify.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(logs))
    res["notes"] = res["notes"][:8]
    if res["tampered"]:
        res["reason"] = "modified protected file(s): " + ", ".join(res["tampered"])
    elif not ok:
        res["reason"] = "hidden/visible tests failed"
    res["solved"] = ok and not res["tampered"]
    return res


# ------------------------------------------------------------------------------------------ the result row
def build_row(meta, trace, outcome, ver, task, prices, price_override=None):
    tot = trace["totals"]
    prompt_total = tot["input"] + tot["cache_read"] + tot["cache_write"]
    main = [c for c in trace["calls"] if not c.get("sub")]
    cliffs, lost = arena_parse.find_cliffs(trace["calls"])
    model = (trace["meta"].get("model") or meta.get("model") or "")
    price = price_for(prices, model, price_override) or price_for(prices, meta.get("model") or "", price_override)
    tools = {}
    for t in trace["tool_calls"]:
        d = tools.setdefault(t["name"] or "?", [0, 0])
        d[0] += 1
        d[1] += 1 if t["is_error"] else 0
    n_tools = len(trace["tool_calls"])
    n_err = sum(1 for t in trace["tool_calls"] if t["is_error"])
    first = main[0] if main else None
    diff = ver.get("diff") or {}
    ref = task.get("ref_diff_lines")
    err_text = (trace.get("agent_error") or "")
    infra = False
    if not outcome["timed_out"]:
        if trace.get("agent_error") or not main:
            infra = bool(INFRA_RE.search(err_text + "\n" + meta.get("stderr_tail", ""))) or not main
    row = {
        "schema": 1,
        "label": meta["label"], "seq": meta["seq"], "run_id": meta["run_id"], "attempt": meta.get("attempt", 1),
        "agent": meta["agent"], "agent_version": meta.get("agent_version"), "model": model,
        "effort": meta.get("effort"), "toolset": meta.get("toolset"), "variant": meta.get("variant"),
        "task": task["id"], "rep": meta["rep"], "started_at": meta.get("started_at"),
        "pass": bool(ver.get("solved")) and not outcome["timed_out"],
        "solved": bool(ver.get("solved")), "timed_out": outcome["timed_out"], "exit_code": outcome["exit_code"],
        "fail_reason": ("timeout" if outcome["timed_out"] else ver.get("reason")),
        "agent_error": trace.get("agent_error"), "infra_error": infra,
        "wall_s": outcome["wall_s"], "startup_s": trace["timing"].get("startup_s"),
        "llm_s": trace["timing"].get("llm_s"), "tool_s": trace["timing"].get("tool_s"),
        "turns": len(main), "tool_calls": n_tools, "tool_errors": n_err,
        "tools": tools,
        "tokens": {"input": tot["input"], "cache_read": tot["cache_read"], "cache_write": tot["cache_write"],
                   "output": tot["output"], "reasoning": tot["reasoning"], "prompt_total": prompt_total},
        "cache_hit_rate": (tot["cache_read"] / prompt_total) if prompt_total else None,
        "first_req": ({"prompt_total": first["prompt_total"], "cache_read": first["cache_read"],
                       "hit_rate": (first["cache_read"] / first["prompt_total"]) if first["prompt_total"] else None}
                      if first else None),
        "cost_usd": compute_cost(tot, price), "price_model": (price or {}).get("name"),
        "reported_cost_usd": trace["reported"].get("cost_usd"),
        "aux_prompt_tokens": trace["aux"].get("prompt_total", 0),
        "diff": {k: diff.get(k) for k in ("files", "added", "removed", "src_lines", "test_lines")},
        "diff_paths": diff.get("paths", [])[:40],
        "minimality": (diff.get("src_lines") / ref) if (ref and diff.get("src_lines") is not None) else None,
        "tests_ran": ver.get("tests_ran"), "tests_failed": ver.get("tests_failed"),
        "verify_notes": ver.get("notes") or [],
        "tampered": ver.get("tampered", []),
        "cliffs": cliffs, "lost_tokens": lost,
        "retries": trace["retries"], "compactions": trace["compactions"],
        "series": [[c["prompt_total"], c["cache_read"], c["cache_write"], c["input"], c["output"]] for c in main],
        "guard": meta.get("guard") or parse_guard(""),
        "tools_exposed": trace["meta"].get("tools_exposed"),
        "n_tools_exposed": len(trace["meta"].get("tools_exposed") or []),
        "thinking_level": trace["meta"].get("thinking"),
        "usage_semantics": trace["meta"].get("usage_semantics"),
        "usage_missing": bool(main) and any(c["prompt_total"] == 0 for c in main),
        "events": trace["meta"].get("n_events"), "bad_lines": trace["meta"].get("bad_lines"),
        "final_text": (trace.get("final_text") or "")[:300],
    }
    return row


# ------------------------------------------------------------------------------------------ one complete run
def execute_run(arena_dir, cfg_root, ws_root, runs_dir, label, seq, agent, task, rep, bins, opts, prices,
                timeout, attempt=1, keep_dirs=False, allow_net=False, price_override=None, versions=None):
    """prepare -> run agent -> verify -> parse -> row.  Writes <run_dir>/result.json and returns the row."""
    run_id = "%03d_%s_%s_r%d" % (seq, agent, task["id"], rep) + ("" if attempt == 1 else "_a%d" % attempt)
    run_dir = os.path.join(runs_dir, label, run_id)
    if os.path.exists(run_dir):
        safe_rmtree(run_dir, runs_dir)
    os.makedirs(run_dir)
    real_home = bool(opts.get("real_home"))
    envd = fresh_env_dir(ws_root, agent)                # HOME/TMPDIR/config: empty, at the same path on every run
    env = (pi_env(envd, cfg_root, allow_net, opts.get("pi_template"), real_home) if agent == "pi"
           else cc_env(envd, cfg_root, allow_net, real_home))
    ws = os.path.join(ws_root, task["id"])
    base = prepare_workspace(arena_dir, task, ws, ws_root, env)
    protected = protected_hashes(arena_dir, task)
    argv = agent_argv(agent, bins, task["prompt"], opts)
    effort = ("pi:" + (opts.get("pi_thinking") or "default")) if agent == "pi" else ("cc:" + (opts.get("cc_effort") or "default"))
    meta = {"label": label, "seq": seq, "run_id": run_id, "attempt": attempt, "agent": agent, "rep": rep,
            "agent_version": (versions or {}).get(agent), "effort": effort, "toolset": opts.get("toolset", "default"),
            "started_at": now_iso(), "ws": ws, "base_commit": base, "timeout_s": timeout,
            "variant": {"pi_overlay": opts.get("pi_template") if agent == "pi" else None,
                        "pi_overlay_sha": opts.get("pi_overlay_sha") if agent == "pi" else None,
                        "extra_args": list(opts.get("extra_args") or [])},
            "argv": [a if a != task["prompt"] else "<task prompt>" for a in argv], "env_keys": sorted(env.keys()),
            "env_dir": envd}
    outcome = run_agent(argv, env, ws, run_dir, timeout)
    meta["stray_killed"] = outcome.get("stray_killed", 0)

    raw = open(os.path.join(run_dir, "events.jsonl"), "rb").read().decode("utf-8", "replace")
    ts = [float(x) for x in open(os.path.join(run_dir, "events.ts")).read().split()]
    trace = arena_parse.parse(agent, raw, ts, cc_inclusive=bool(opts.get("cc_inclusive")))
    meta["stderr_tail"] = tail(os.path.join(run_dir, "stderr.txt"), 1500)
    meta["guard"] = parse_guard(tail(os.path.join(run_dir, "stderr.txt"), 200000))
    ver = verify(arena_dir, task, ws, base, env, run_dir, protected, trace.get("final_text") or "")
    meta["model"] = trace["meta"].get("model")
    row = build_row(meta, trace, outcome, ver, task, prices, price_override)
    save_json(os.path.join(run_dir, "meta.json"), {k: v for k, v in meta.items()})
    save_json(os.path.join(run_dir, "result.json"), row)
    if agent == "cc":                                   # keep Claude Code's own transcript for debugging
        proj = os.path.join(envd, "cc-config", "projects")
        if os.path.isdir(proj):
            for dp, _, fns in os.walk(proj):
                for fn in fns:
                    if fn.endswith(".jsonl") and os.path.getsize(os.path.join(dp, fn)) < 8_000_000:
                        shutil.copy(os.path.join(dp, fn), os.path.join(run_dir, "cc-transcript.jsonl"))
    retire_env_dir(envd, run_dir, keep_dirs)
    return row


# ------------------------------------------------------------------------------------------ task self-check
def check_task(arena_dir, task_id, tmp_root, write_ref=False):
    """Unsolved repo must fail the verifier, repo + reference solution must pass.  Returns a dict."""
    task = load_task(arena_dir, task_id)
    td = task_dir(arena_dir, task_id)
    work = os.path.join(tmp_root, "check-" + task_id)
    os.makedirs(tmp_root, exist_ok=True)
    out = {"task": task_id}
    run_dir = os.path.join(work, "run")
    for label, solve in (("unsolved", False), ("solved", True)):
        if os.path.exists(work):
            safe_rmtree(work, tmp_root)
        os.makedirs(run_dir)
        env = base_env(run_dir, allow_net=False)
        ws = os.path.join(work, "ws", task_id)
        base = prepare_workspace(arena_dir, task, ws, os.path.join(work, "ws"), env)
        final = ""
        if solve:
            if os.path.isdir(os.path.join(td, "_ref", "files")):
                # shutil.copy, not copy2: a copy that keeps the old mtime can make git believe a same-size file is
                # unchanged; shutil.copy still keeps the permission bits (p06's scripts must stay executable)
                shutil.copytree(os.path.join(td, "_ref", "files"), ws, dirs_exist_ok=True, copy_function=shutil.copy)
            ref_answer = os.path.join(td, "_ref", "final.txt")                  # question-answering tasks: the right answer
            if os.path.isfile(ref_answer):
                final = open(ref_answer, encoding="utf-8").read()
        v = verify(arena_dir, task, ws, base, env, run_dir, protected_hashes(arena_dir, task), final)
        out[label] = {"solved": v["solved"], "tests_ran": v["tests_ran"], "tests_failed": v["tests_failed"],
                      "reason": v["reason"]}
        if solve:
            out["ref_diff_lines"] = v["diff"]["src_lines"]
    out["ok"] = (not out["unsolved"]["solved"]) and out["solved"]["solved"]
    if write_ref and out["ok"]:
        task["ref_diff_lines"] = out["ref_diff_lines"]
        save_json(os.path.join(td, "task.json"), task)
    safe_rmtree(work, tmp_root)
    return out


# ------------------------------------------------------------------------------------------ effort calibration
CALIB_PROMPT = ("Write a Python function nth_distinct(n) that returns the n-th integer (0-based, ascending) among the "
                "non-negative integers whose decimal digits are all different, so the sequence starts "
                "0, 1, 2, ..., 9, 10, 12, 13, ... Do not use any tools and do not run anything. "
                "Reply with only the code.")


def run_calibration(cfg_root, ws_root, runs_dir, label, bins, prices, plan, timeout, real_home=False,
                    allow_net=False, price_override=None, progress=None, cc_inclusive=False):
    """Same short reasoning-heavy prompt through each (agent, effort level, repetition) of `plan`, in an empty
    workspace, so output/reasoning tokens show what an effort setting really does on the wire.
    plan: list of (agent, level, rep).  Returns a list of rows (also written to runs/_calib/<label>/calib.jsonl)."""
    base = os.path.join(runs_dir, "_calib", label)
    if os.path.exists(base):
        safe_rmtree(base, runs_dir)
    os.makedirs(base)
    rows = []
    for idx, (agent, level, rep) in enumerate(plan, 1):
        run_dir = os.path.join(base, "%02d_%s_%s_r%d" % (idx, agent, level, rep))
        os.makedirs(run_dir)
        envd = fresh_env_dir(ws_root, agent)
        env = pi_env(envd, cfg_root, allow_net, None, real_home) if agent == "pi" else cc_env(envd, cfg_root, allow_net, real_home)
        ws = os.path.join(ws_root, "_calib")
        if os.path.exists(ws):
            safe_rmtree(ws, ws_root)
        os.makedirs(ws)
        opts = {"pi_thinking": level} if agent == "pi" else {"cc_effort": level}
        argv = agent_argv(agent, bins, CALIB_PROMPT, opts)
        out = run_agent(argv, env, ws, run_dir, timeout)
        raw = open(os.path.join(run_dir, "events.jsonl"), "rb").read().decode("utf-8", "replace")
        ts = [float(x) for x in open(os.path.join(run_dir, "events.ts")).read().split()]
        tr = arena_parse.parse(agent, raw, ts, cc_inclusive=cc_inclusive)
        tot = tr["totals"]
        price = price_for(prices, tr["meta"].get("model"), price_override)
        row = {"agent": agent, "level": level, "rep": rep, "wall_s": out["wall_s"], "timed_out": out["timed_out"],
               "calls": len([c for c in tr["calls"] if not c["sub"]]), "tool_calls": len(tr["tool_calls"]),
               "output": tot["output"], "reasoning": tot["reasoning"],
               "prompt_total": tot["input"] + tot["cache_read"] + tot["cache_write"],
               "thinking_level": tr["meta"].get("thinking"), "answer_chars": len(tr["final_text"] or ""),
               "cost_usd": compute_cost(tot, price), "error": tr["agent_error"]}
        rows.append(row)
        save_json(os.path.join(run_dir, "result.json"), row)
        retire_env_dir(envd, run_dir)
        if progress:
            progress(idx, len(plan), row)
    with open(os.path.join(base, "calib.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return rows


def calibration_table(rows):
    import statistics as st
    groups = {}
    for r in rows:
        groups.setdefault((r["agent"], r["level"]), []).append(r)

    def med(xs):
        xs = [x for x in xs if x is not None]
        return st.median(xs) if xs else None

    def f(v, spec="{:.0f}"):
        return "-" if v is None else spec.format(v)
    lines = ["agent   level    n  output tok (median)  [min-max]       reasoning tok  wall s  tool calls  answer chars  wire level"]
    for (agent, level), rs in groups.items():
        outs = [r["output"] for r in rs]
        lines.append("%-7s %-7s %2d  %18s  %-14s  %13s  %6s  %10s  %12s  %s" % (
            agent, level, len(rs), f(med(outs)), "[%d-%d]" % (min(outs), max(outs)), f(med([r["reasoning"] for r in rs])),
            f(med([r["wall_s"] for r in rs]), "{:.1f}"), f(med([r["tool_calls"] for r in rs]), "{:.0f}"),
            f(med([r["answer_chars"] for r in rs])), rs[0].get("thinking_level") or "-"))
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------ usage semantics
def judge_usage(first, later):
    """How does a gateway report Claude Code's input_tokens?  `first` and `later` are the RAW totals (input, cache_read,
    cache_write as reported) of two identical requests in a row; the later one should be almost entirely a cache hit.

      additive  : input counts only the tokens that were not cached (Anthropic style), so with a hit it is small
                  next to cache_read, and prompt = input + cache_read + cache_write
      inclusive : input is the whole prompt and cache_read is a part of it (OpenAI style), so cache_read <= input,
                  close to it, and prompt = input
      unknown   : no clear cache hit (or numbers that fit neither): treated as additive, flagged in the reports

    Two identical requests have the same prompt size, so the right reading is the one under which the two requests
    agree: additive -> input + cache_read + cache_write is the same for both; inclusive -> input is the same for both
    and cache_read <= input.  (The hit rate does not matter: a 70% hit is judged as well as a 99% one.)  Only when the
    requests were not really identical and neither reading agrees do we fall back on the shape of the later request.
    Returns (verdict, evidence string)."""
    inp, cr = later["input"], later["cache_read"]
    ev = "later request: input=%d cache_read=%d cache_write=%d; first request: input=%d cache_read=%d cache_write=%d" % (
        inp, cr, later["cache_write"], first["input"], first["cache_read"], first["cache_write"])

    def total(u):
        return u["input"] + u["cache_read"] + u["cache_write"]
    tol = max(64, 0.005 * max(total(first), total(later)))
    if cr < max(512, 2 * tol):
        return "unknown", ev + " (no clear cache hit on the later request)"
    additive_fits = abs(total(first) - total(later)) <= tol
    inclusive_fits = abs(first["input"] - inp) <= tol and cr <= inp + 64
    if additive_fits and not inclusive_fits:
        return "additive", ev + " (the two identical requests have the same prompt size only when read as input + cache)"
    if inclusive_fits and not additive_fits:
        return "inclusive", ev + " (the two identical requests have the same prompt size only when read as input alone)"
    if inp <= 0.5 * cr:                                   # not identical requests after all: the shape of the later one
        return "additive", ev + " (by the shape of the later request)"
    if 0.8 * inp <= cr <= inp + 64:
        return "inclusive", ev + " (by the shape of the later request)"
    return "unknown", ev + " (fits neither convention)"
