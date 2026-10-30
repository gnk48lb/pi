"""arena selftest: the real `pi` and `claude` binaries + the real runner/parser/verifier, against a scripted mock
gateway.  Nothing leaves the machine and no tokens are spent.

What it proves (each scenario is one real agent run):
  solve    x {pi, claude} x {p01, p02}   the scripted "model" copies the reference solution -> verifier says PASS;
                                         tool/error counts, token and cache totals equal what the mock sent
  noop     pi p01                        a model that does nothing -> FAIL (tests failed)
  tamper   claude p02                    a model that edits a protected test file -> FAIL (tampered)
  timeout  pi + claude                   a hanging tool -> killed at the timeout, no stray process survives,
                                         not even a child that escaped the process group with setsid
plus: environment isolation (a canary secret in the parent environment must not reach the agent, the proxy
variables must be dead), effort flags reach the wire, the tasks' own unsolved/solved check, and the report."""
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import arena_core as core
import arena_parse
import arena_probe
import arena_report

CANARY = "canary-s3cr3t-do-not-leak"
# The "hanging tool" scenarios look for these in `ps` afterwards.  Odd durations on purpose: an unrelated
# `sleep 120` somewhere on your machine must not look like a process that survived.
HANG_CMD = "sleep 1203"
ESCAPED_CMD = "sleep 1197"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Mock:
    def __init__(self, arena_dir, tmp):
        self.port = free_port()
        self.log = os.path.join(tmp, "mock-requests.jsonl")
        self.dump = os.path.join(tmp, "mock-bodies.jsonl")
        self.script = os.path.join(tmp, "mock-script.json")
        env = dict(os.environ, MOCK_PORT=str(self.port), MOCK_LOG=self.log, MOCK_DUMP=self.dump, MOCK_SCRIPT=self.script)
        self.proc = subprocess.Popen([sys.executable, os.path.join(arena_dir, "mock", "mock_server.py")], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                OPENER.open("http://127.0.0.1:%d/__health" % self.port, timeout=1).read()
                return
            except Exception:  # noqa
                time.sleep(0.1)
        raise RuntimeError("mock gateway did not start")

    def reset(self, steps):
        with open(self.script, "w") as f:
            json.dump(steps, f)
        open(self.dump, "w").close()
        OPENER.open(urllib.request.Request("http://127.0.0.1:%d/__reset" % self.port, data=b"{}", method="POST"), timeout=5).read()

    def fail(self, n):
        """Simulate an outage: the next n model requests (all of them for n=-1) get HTTP 503; 0 ends it."""
        OPENER.open(urllib.request.Request("http://127.0.0.1:%d/__fail?n=%d" % (self.port, n), data=b"{}", method="POST"), timeout=5).read()

    def requests(self):
        return [json.loads(l) for l in open(self.log) if l.strip()]

    def bodies_text(self):
        return open(self.dump, encoding="utf-8", errors="replace").read()

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except Exception:  # noqa
            self.proc.kill()


def write_configs(cfg, base):
    """Blank pi + Claude Code configs (what `setup` writes) pointing at the mock gateway at `base`."""
    os.makedirs(os.path.join(cfg, "pi"))
    os.makedirs(os.path.join(cfg, "cc"))
    core.save_json(os.path.join(cfg, "pi", "models.json"), {"providers": {"mock": {
        "baseUrl": base + "/v1", "api": "openai-completions", "apiKey": "mock-key-123456",
        "models": [{"id": "mock-model", "name": "Mock", "reasoning": True, "contextWindow": 200000, "maxTokens": 8192}]}}})
    core.save_json(os.path.join(cfg, "pi", "settings.json"), {
        "defaultProvider": "mock", "defaultModel": "mock-model", "packages": [], "enableInstallTelemetry": False})
    core.save_json(os.path.join(cfg, "cc", "env.json"), {
        "ANTHROPIC_BASE_URL": base, "ANTHROPIC_AUTH_TOKEN": "mock-token-123456", "ANTHROPIC_MODEL": "mock-model",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "mock-model", "ANTHROPIC_DEFAULT_SONNET_MODEL": "mock-model",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "mock-model", "ANTHROPIC_SMALL_FAST_MODEL": "mock-model"})
    core.save_json(os.path.join(cfg, "cc", "settings.json"), {})


# ------------------------------------------------------------------------------------------ scripts
def steps_for(kind, task, arena_dir):
    ref = os.path.join(core.task_dir(arena_dir, task["id"]), "_ref", "files")
    cp = "cp -r %s/. ." % shlex.quote(ref)
    if kind == "solve":
        return [
            {"say": "Let me look at the project first.", "tool": "bash", "arguments": {"command":
                "head -3 README.md; echo canary_count=$(env | grep -c ARENA_CANARY); env | grep -i '^http_proxy='"}},
            {"tool": "bash", "arguments": {"command": "false"}},
            {"think": "The README says what to do and the reference files are at hand; copying them over is the "
                      "quickest correct fix, then I run the project's own tests to confirm it.",
             "tool": "bash", "arguments": {"command": cp}},
            {"tool": "bash", "arguments": {"command": task["visible_test_cmd"]}},
        ]
    if kind == "noop":
        return [{"tool": "bash", "arguments": {"command": "ls"}}]
    if kind == "tamper":
        return [{"tool": "bash", "arguments": {"command": "%s && printf '\\n' >> %s" % (cp, shlex.quote(task["protected"][0]))}}]
    if kind == "timeout":     # not a bare `sleep N`: Claude Code 2.1.311 refuses a standalone sleep ("Blocked: standalone sleep")
        return [{"tool": "bash", "arguments": {"command": "echo hanging; %s" % HANG_CMD}}]
    if kind == "escape":      # a child that leaves the process group (setsid) must still be cleaned up
        return [{"tool": "bash", "arguments": {"command": "setsid %s >/dev/null 2>&1 & %s" % (ESCAPED_CMD, HANG_CMD)}}]
    raise ValueError(kind)


# ------------------------------------------------------------------------------------------ day1 plumbing
def day1_checks(tmp):
    """Control flow of `day1` (order, failures, skipping, interruption, resuming) and the results bundle, with a fake
    step runner: no agent and no gateway are involved."""
    import argparse
    import contextlib
    import glob
    import io
    import tarfile
    import arena_day1 as d1

    SECRET = "sk-selftest-secret-0123456789"
    c = []

    def ns(**kw):
        a = dict(quick=False, pilot_reps=None, skip="", only="", redo="")
        a.update(kw)
        return argparse.Namespace(**a)

    def fake_arena(name, with_setup=True):
        root = os.path.join(tmp, "day1-" + name)
        for sub in ("configs/cc", "configs/pi", "runs"):
            os.makedirs(os.path.join(root, sub))
        if with_setup:
            core.save_json(os.path.join(root, "configs", "setup.json"), {
                "home_mode": "isolated", "usage": {"cc": "additive"},
                "pi": {"bin": "/x/pi", "version": "1.3.0"}, "cc": {"bin": "/x/claude", "version": "2.1.302"}})
        with open(os.path.join(root, "configs", "cc", "env.json"), "w") as f:
            f.write('{"ANTHROPIC_AUTH_TOKEN": "%s"}' % SECRET)
        with open(os.path.join(root, "configs", "pi", "models.json"), "w") as f:
            f.write('{"providers": {"m": {"apiKey": "%s"}}}' % SECRET)
        return root

    def make_runner(root, rcs, calls):
        def wr(rel, text):
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(text)

        def runner(name, argv, log):
            calls.append((name, list(argv)))
            with open(log, "w") as f:
                f.write("$ fake %s\nleaked key %s\n" % (name, SECRET))
            if name == "setup":
                core.save_json(os.path.join(root, "configs", "setup.json"), {"home_mode": "isolated", "pi": {}, "cc": {}})
            elif name == "smoke":
                wr("runs/_smoke/summary.txt", "smoke summary\n")
            elif name == "cacheprobe":
                wr("runs/_cacheprobe/probe1/summary.txt", "probe summary\n")
                wr("runs/_cacheprobe/probe1/probe.jsonl", '{"proto": "openai"}\n')
            elif name == "calib":
                wr("runs/_calib/calib1/calib.txt", "calib table\n")
                wr("runs/_calib/calib1/calib.jsonl", '{"agent": "pi"}\n')
                wr("runs/_calib/calib1/01_pi_low_r1/events.jsonl", "calib raw 1\n")
                wr("runs/_calib/calib1/02_pi_low_r2/events.jsonl", "calib raw 2\n")
            elif name == "pilot":
                wr("runs/pilot1/plan.json", "{}\n")
                wr("runs/pilot1/results.jsonl", '{"agent": "pi", "pass": true}\n')
                wr("runs/pilot1/001_pi_p01_r1/result.json", "{}\n")
                wr("runs/pilot1/001_pi_p01_r1/events.jsonl", "raw r1\n")
                wr("runs/pilot1/001_pi_p01_r1/stderr.txt", "stderr leaked %s\n" % SECRET)
                wr("runs/pilot1/003_pi_p01_r2/result.json", "{}\n")
                wr("runs/pilot1/003_pi_p01_r2/events.jsonl", "raw r2\n")
                wr("runs/pilot1/003_pi_p01_r2/home/kept/result.json", "{}\n")      # a kept HOME is never packed
                wr("runs/pilot1/003_pi_p01_r2/env/pi-agent/kept/result.json", "{}\n")   # (--keep-dirs moves it to env/)
            elif name == "report":
                wr("runs/pilot1/report.txt", "pilot report\n")
            rc = rcs.get(name, 0)
            if isinstance(rc, BaseException):
                raise rc
            return rc
        return runner

    def go(root, rcs=None, **kw):
        calls = []
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = d1.main(root, ns(**kw), runner=make_runner(root, rcs or {}, calls))
        return rc, calls, buf.getvalue()

    def state(root):
        return core.load_json(os.path.join(root, "day1", "state.json"), {})["steps"]

    def newest(root, ext):
        found = sorted(glob.glob(os.path.join(root, "arena-results-*." + ext)), key=os.path.getmtime)
        return found[-1] if found else None

    def bundle(root):
        with open(newest(root, "txt"), encoding="utf-8") as f:
            txt = f.read()
        with tarfile.open(newest(root, "tgz")) as t:
            mem = {m.name: t.extractfile(m).read().decode("utf-8", "replace") for m in t.getmembers() if m.isfile()}
        return txt, mem

    def ran(calls):
        return [n for n, _ in calls]

    # 1. everything passes -------------------------------------------------------------------------------
    root = fake_arena("ok")
    rc, calls, out = go(root)
    c.append((rc == 0 and ran(calls) == ["selftest", "smoke", "cacheprobe", "calib", "pilot", "report"],
              "all steps run in order, setup skipped because configs/setup.json exists (ran %s, exit %s)" % (ran(calls), rc)))
    st = state(root)
    c.append((all(st.get(n, {}).get("status", "").startswith("done") for n in d1.STEP_NAMES),
              "state remembers every step as done: %s" % {k: v.get("status") for k, v in st.items()}))
    txt, mem = bundle(root)
    c.append((not any(n.startswith("arena-results/configs/") for n in mem) and "arena-results/setup.json" in mem and
              "arena-results/RESULTS.txt" in mem, "bundle has no configs/ directory, but has setup.json and RESULTS.txt"))
    c.append((SECRET not in txt and all(SECRET not in v for v in mem.values()),
              "a key that leaked into a log or into stderr is masked everywhere (the digest and every file of the .tgz)"))
    c.append(("arena-results/runs/pilot1/001_pi_p01_r1/events.jsonl" in mem and
              "arena-results/runs/pilot1/003_pi_p01_r2/events.jsonl" not in mem and
              "arena-results/runs/_calib/calib1/01_pi_low_r1/events.jsonl" in mem and
              "arena-results/runs/_calib/calib1/02_pi_low_r2/events.jsonl" not in mem,
              "raw event streams only for the first repetition"))
    c.append((not any("/home/" in n or "/env/" in n for n in mem), "a kept HOME / agent directory is never packed"))
    want = ["smoke summary", "probe summary", "calib table", "pilot report", "data: run label pilot1 results.jsonl",
            "data: cacheprobe probe1 probe.jsonl", "data: calibration calib1 calib.jsonl", "console output of step selftest"]
    miss = [w for w in want if w not in txt]
    c.append((not miss, "the digest has every section%s" % (" (missing: %s)" % miss if miss else "")))
    rc, calls, out = go(root)
    c.append((rc == 0 and calls == [] and "nothing left to do" in out, "running day1 again skips everything that is done"))

    # 2. smoke fails: the steps that need agents are skipped, the free one still runs; the rerun picks up ------------
    root = fake_arena("smokefail")
    rc, calls, out = go(root, {"smoke": 1})
    st = state(root)
    c.append((ran(calls) == ["selftest", "smoke", "cacheprobe"] and rc == 1,
              "smoke failure: calib, pilot and report are skipped, cacheprobe still runs (ran %s, exit %s)" % (ran(calls), rc)))
    c.append((st["smoke"]["status"].startswith("failed") and st["calib"]["status"].startswith("skipped") and
              st["cacheprobe"]["status"] == "done", "state shows failed / skipped / done: %s" % {k: v.get("status") for k, v in st.items()}))
    c.append((newest(root, "txt") is not None and newest(root, "tgz") is not None, "a results file is written even when a step failed"))
    rc, calls, out = go(root)
    c.append((rc == 0 and ran(calls) == ["smoke", "calib", "pilot", "report"],
              "rerun after the fix: only the failed and the skipped steps run (ran %s)" % ran(calls)))

    # 3. selftest fails: recorded, the session goes on -----------------------------------------------------------
    root = fake_arena("selftestfail")
    rc, calls, out = go(root, {"selftest": 1})
    c.append((ran(calls) == ["selftest", "smoke", "cacheprobe", "calib", "pilot", "report"] and rc == 1,
              "a selftest failure is reported but does not stop the session (exit %s)" % rc))

    # 4. setup fails: stop at once, still bundle ------------------------------------------------------------------
    root = fake_arena("nosetup", with_setup=False)
    rc, calls, out = go(root, {"setup": 2})
    c.append((ran(calls) == ["setup"] and rc == 1 and newest(root, "tgz") is not None,
              "a setup failure stops everything, but the bundle is still written"))

    # 5. interruption: the child exits 130 like the real pilot does; the rerun resumes it -------------------------------
    root = fake_arena("interrupt")
    rc, calls, out = go(root, {"pilot": 130})
    c.append((rc == 130 and ran(calls) == ["selftest", "smoke", "cacheprobe", "calib", "pilot"] and
              state(root)["pilot"]["status"] == "interrupted",
              "an interrupted pilot stops the session with exit 130 (ran %s)" % ran(calls)))
    rc, calls, out = go(root)
    c.append((rc == 0 and ran(calls) == ["pilot", "report"] and "--resume" in dict(calls).get("pilot", []),
              "the rerun continues with pilot --resume, then report (ran %s)" % ran(calls)))

    # 6. Ctrl-C raised inside a step ---------------------------------------------------------------------------------
    root = fake_arena("ctrlc")
    rc, calls, out = go(root, {"calib": KeyboardInterrupt()})
    c.append((rc == 130 and state(root)["calib"]["status"] == "interrupted" and "pilot" not in ran(calls) and
              newest(root, "txt") is not None, "Ctrl-C inside a step: exit 130, later steps do not run, the bundle is written"))

    # 7. choosing steps -------------------------------------------------------------------------------------------------
    root = fake_arena("select")
    rc, calls, out = go(root, only="calib,report")
    c.append((ran(calls) == ["calib", "report"], "--only runs just those steps (ran %s)" % ran(calls)))
    rc, calls, out = go(root, skip="selftest,smoke,cacheprobe,pilot", redo="calib")
    c.append((ran(calls) == ["calib"], "--redo runs a finished step again, --skip leaves steps out (ran %s)" % ran(calls)))
    root = fake_arena("quick")
    rc, calls, out = go(root, quick=True, only="cacheprobe,calib,pilot")
    av = dict(calls)
    pv = av.get("pilot", [])
    c.append(("--quick" in av.get("cacheprobe", []) and av.get("calib", [])[-2:] == ["--reps", "1"] and
              "--reps" in pv and pv[pv.index("--reps") + 1] == "3",
              "--quick shortens cacheprobe, calib and the pilot (got %s)" % av))
    try:
        go(fake_arena("badname"), only="bogus")
        c.append((False, "an unknown step name is refused"))
    except SystemExit as e:
        c.append((e.code == 2, "an unknown step name is refused"))

    # 8. pack on its own, masking -----------------------------------------------------------------------------------------
    root = fake_arena("packonly")
    go(root)
    txt_p, tgz_p, n = d1.pack_results(root, labels={"other"})
    with tarfile.open(tgz_p) as t:
        members = [m.name for m in t.getmembers()]
    c.append((n > 0 and not any("/pilot1/" in x for x in members) and any("/_smoke/" in x for x in members),
              "pack --label leaves other run labels out, keeps smoke / calib / cacheprobe"))
    masked = d1.mask('x-api-key: abcd1234 and "apiKey": "zzzz9999" and Bearer 0123456789abcdef and sk-0123456789ab and '
                     'ANTHROPIC_AUTH_TOKEN=<set, 12 chars>')
    c.append((all(s not in masked for s in ("abcd1234", "zzzz9999", "0123456789abcdef", "sk-0123456789ab")) and
              "<set, 12 chars>" in masked, "mask() hides keys and leaves the already-redacted setup output alone: %s" % masked))
    return c


# ------------------------------------------------------------------------------------------ suite plumbing
def suite_checks(tmp):
    """Control flow of `suite` (tasks check -> run -> report, resuming, selection, failure of the task check) and its
    results file, with a fake step runner: no agent and no gateway are involved."""
    import argparse
    import contextlib
    import glob
    import io
    import tarfile
    import arena
    import arena_day1 as d1

    c = []

    def parse(*argv):
        return arena.build_parser().parse_args(["suite"] + list(argv))

    def fake_arena(name):
        root = os.path.join(tmp, "suite-" + name)
        for sub in ("configs", "runs", "runs/_smoke", "runs/_calib/calib1"):
            os.makedirs(os.path.join(root, sub))
        core.save_json(os.path.join(root, "configs", "setup.json"), {
            "home_mode": "isolated", "usage": {"cc": "additive"},
            "pi": {"bin": "/x/pi", "version": "1.3.0"}, "cc": {"bin": "/x/claude", "version": "2.1.302"}})
        for rel, text in (("runs/_smoke/summary.txt", "smoke summary\n"), ("runs/_calib/calib1/calib.txt", "calib table\n")):
            with open(os.path.join(root, rel), "w") as f:
                f.write(text)
        return root

    def make_runner(root, rcs, calls):
        def wr(rel, text):
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(text)

        def runner(name, argv, log):
            calls.append((name, list(argv)))
            with open(log, "w") as f:
                f.write("$ fake %s\n" % name)
            if name == "run":
                label = argv[argv.index("--label") + 1]
                wr("runs/%s/plan.json" % label, "{}\n")
                wr("runs/%s/001_pi_p01_r1/result.json" % label, "{}\n")
                wr("runs/%s/001_pi_p01_r1/events.jsonl" % label, "raw\n")
                wr("runs/%s/results.jsonl" % label, '{"agent": "pi", "pass": true}\n')
                wr("runs/other/001_pi_p01_r1/result.json", "{}\n")                 # another batch: must stay out
            elif name == "report":
                label = argv[argv.index("--label") + 1]
                wr("runs/%s/report.txt" % label, "suite report\n")
            rc = rcs.get(name, 0)
            if isinstance(rc, BaseException):
                raise rc
            return rc
        return runner

    def go(root, *argv, rcs=None):
        calls = []
        args = parse(*argv)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = d1.main(root, args, steps=arena.suite_steps(args), runner=make_runner(root, rcs or {}, calls),
                         session="suite/" + args.label, labels={args.label})
        return rc, calls, buf.getvalue()

    def ran(calls):
        return [n for n, _ in calls]

    def state(root, label="suite1"):
        return core.load_json(os.path.join(root, "suite", label, "state.json"), {})["steps"]

    def newest(root, ext):
        found = sorted(glob.glob(os.path.join(root, "arena-results-*." + ext)), key=os.path.getmtime)
        return found[-1] if found else None

    # 1. a fresh batch ---------------------------------------------------------------------------------------------
    root = fake_arena("ok")
    rc, calls, out = go(root)
    av = dict(calls)
    run_argv = av.get("run", [])
    c.append((rc == 0 and ran(calls) == ["tasks", "run", "report"],
              "suite runs tasks check, run, report in that order (ran %s, exit %s)" % (ran(calls), rc)))
    c.append((av.get("tasks") == ["tasks", "--check", "--tasks", "dev"], "the task check covers the selected tasks only (%s)" % av.get("tasks")))
    c.append(("--resume" not in run_argv and run_argv[run_argv.index("--label") + 1] == "suite1" and
              run_argv[run_argv.index("--tasks") + 1] == "dev" and run_argv[run_argv.index("--reps") + 1] == "3" and
              run_argv[run_argv.index("--agents") + 1] == "pi,cc",
              "defaults: label suite1, the dev tasks, 3 repetitions, both agents, a new batch is not resumed"))
    c.append((all(v.get("status") == "done" for v in state(root).values()), "state is kept in suite/<label>/state.json"))
    with open(newest(root, "txt"), encoding="utf-8") as f:
        txt = f.read()
    with tarfile.open(newest(root, "tgz")) as t:
        names = [m.name for m in t.getmembers() if m.isfile()]
    c.append((txt.startswith("arena suite results") and "run label suite1: report" in txt and "suite report" in txt and
              "data: run label suite1 results.jsonl" in txt, "the results file has the suite's report and data rows"))
    c.append((not any("/runs/other/" in n or "/_smoke/" in n or "/_calib/" in n for n in names) and
              "smoke summary" not in txt and "calib table" not in txt,
              "the results file is about this batch only: other labels and the smoke / calib data stay out"))
    c.append(("arena-results/runs/suite1/001_pi_p01_r1/events.jsonl" in names, "raw event stream of the first repetition is included"))
    rc, calls, out = go(root)
    c.append((rc == 0 and calls == [] and "nothing left to do" in out, "running suite again skips everything that is done"))
    rc, calls, out = go(root, "--redo", "run")
    c.append((ran(calls) == ["run"] and "--resume" in dict(calls)["run"],
              "--redo run continues the existing batch (--resume), it does not start a new one (%s)" % ran(calls)))
    rc, calls, out = go(root, "--label", "second")
    c.append((ran(calls) == ["tasks", "run", "report"] and "--resume" not in dict(calls)["run"] and
              state(root, "second")["run"]["status"] == "done" and state(root)["run"]["status"] == "done",
              "another label is a new batch with its own state (ran %s)" % ran(calls)))

    # 2. interruption ----------------------------------------------------------------------------------------------
    root = fake_arena("interrupt")
    rc, calls, out = go(root, rcs={"run": 130})
    c.append((rc == 130 and ran(calls) == ["tasks", "run"] and state(root)["run"]["status"] == "interrupted" and
              newest(root, "txt") is not None, "an interrupted run stops the session with exit 130 and still writes the results file"))
    rc, calls, out = go(root)
    c.append((rc == 0 and ran(calls) == ["run", "report"] and "--resume" in dict(calls)["run"],
              "the rerun resumes the run, then reports (ran %s)" % ran(calls)))

    # 3. the task check fails: nothing is spent on agents --------------------------------------------------------------------
    root = fake_arena("badtasks")
    rc, calls, out = go(root, rcs={"tasks": 1})
    c.append((rc == 1 and ran(calls) == ["tasks"] and newest(root, "tgz") is not None and "stopped at step 'tasks'" in out,
              "a failing task check stops before any agent runs, the results file is still written (ran %s)" % ran(calls)))

    # 4. choosing steps, passing options on -----------------------------------------------------------------------------------
    root = fake_arena("select")
    rc, calls, out = go(root, "--only", "report")
    c.append((ran(calls) == ["report"], "--only report just rebuilds the report (ran %s)" % ran(calls)))
    try:
        go(fake_arena("badname"), "--only", "pilot")
        c.append((False, "an unknown step name is refused"))
    except SystemExit as e:
        c.append((e.code == 2, "an unknown step name (a day1 step) is refused"))
    root = fake_arena("options")
    rel = os.path.join("rel", "variant")
    rc, calls, out = go(root, "--label", "v1", "--agents", "pi", "--tasks", "p01,p02", "--reps", "2", "--pi-thinking", "low",
                        "--pi-config", rel, "--pi-extra", "-e /x/ext.ts", "--force", "--only", "run")
    ra = dict(calls).get("run", [])
    c.append((ra[ra.index("--label") + 1] == "v1" and ra[ra.index("--agents") + 1] == "pi" and
              ra[ra.index("--tasks") + 1] == "p01,p02" and ra[ra.index("--reps") + 1] == "2" and
              ra[ra.index("--pi-thinking") + 1] == "low" and ra[ra.index("--pi-extra") + 1] == "-e /x/ext.ts" and "--force" in ra,
              "options of run are passed on (%s)" % " ".join(ra)))
    c.append((os.path.isabs(ra[ra.index("--pi-config") + 1]) and ra[ra.index("--pi-config") + 1].endswith(rel),
              "a relative --pi-config becomes an absolute path (the steps run inside arena/)"))
    # 4b. a script that runs several batches: no results file per batch, no task check after the first ---------------------------
    root = fake_arena("nopack")
    rc, calls, out = go(root, "--label", "a", "--no-pack", "--skip", "tasks")
    c.append((rc == 0 and ran(calls) == ["run", "report"], "--skip tasks leaves the task check out (ran %s)" % ran(calls)))
    c.append((newest(root, "txt") is None and newest(root, "tgz") is None and "results to send back" not in out,
              "--no-pack writes no results file and does not ask for one"))
    c.append((state(root, "a")["run"]["status"] == "done" and "All steps finished." in out, "the batch itself is complete and reported as such"))
    rc, calls, out = go(root, "--label", "b", "--no-pack", "--skip", "tasks", rcs={"run": 1})
    c.append((rc == 1 and "Send me the results file" not in out and newest(root, "txt") is None,
              "a failed batch under --no-pack does not ask for a results file either (exit %s)" % rc))
    # 4c. the gateway-outage guard of `run` is reachable through suite ---------------------------------------------------------
    root = fake_arena("infraopts")
    rc, calls, out = go(root, "--label", "g", "--only", "run", "--stop-after-infra", "3", "--redo-infra")
    ra = dict(calls).get("run", [])
    c.append(("--stop-after-infra" in ra and ra[ra.index("--stop-after-infra") + 1] == "3" and "--redo-infra" in ra,
              "--stop-after-infra and --redo-infra are passed on to run (%s)" % " ".join(ra[-4:])))
    rc, calls, out = go(fake_arena("infradefault"), "--label", "g", "--only", "run")
    ra = dict(calls).get("run", [])
    c.append(("--stop-after-infra" not in ra and "--redo-infra" not in ra, "by default neither option is passed on (a plain suite never stops early)"))
    # 5. refusing to start without setup, odd labels -----------------------------------------------------------------------------
    old_cfg = arena.CFG_ROOT
    arena.CFG_ROOT = os.path.join(tmp, "suite-nosetup-configs")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            arena.cmd_suite(parse())
        c.append((False, "suite without configs/setup.json is refused"))
    except SystemExit as e:
        c.append((e.code == 2, "suite without configs/setup.json is refused (run day1 first)"))
    finally:
        arena.CFG_ROOT = old_cfg
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            arena.cmd_suite(parse("--label", "../evil"))
        c.append((False, "a label with a path in it is refused"))
    except SystemExit as e:
        c.append((e.code == 2, "a label with a path in it is refused"))
    return c


# ------------------------------------------------------------------------------------------ the run
def infra_guard_checks(arena_dir, tmp, mock, base, bins, real_home, versions):
    """`run --stop-after-infra N` and `run --resume --redo-infra` against a mock gateway that simulates an outage
    (HTTP 503 on every model request).  Real pi, the real `cmd_run`, its own configs / runs / workspace directories."""
    import contextlib
    import io
    import arena
    c = []
    if not bins.get("pi"):
        return [(True, "pi not found: skipped")]
    cfgd = os.path.join(tmp, "infra-configs")
    write_configs(cfgd, base)
    core.save_json(os.path.join(cfgd, "setup.json"), {
        "home_mode": "real" if real_home else "isolated", "usage": {"cc": "additive"},
        "pi": {"bin": bins["pi"], "version": versions.get("pi")}, "cc": {"bin": bins.get("cc") or "/nonexistent/claude", "version": versions.get("cc")}})
    runs_d, ws_d = os.path.join(tmp, "infra-runs"), os.path.join(tmp, "ws-infra")
    saved = (arena.CFG_ROOT, arena.RUNS_DIR, os.environ.get("ARENA_SLEEP_SCALE"))
    arena.CFG_ROOT, arena.RUNS_DIR = cfgd, runs_d
    os.environ["ARENA_SLEEP_SCALE"] = "0.02"                  # the 20 s pause before an automatic retry
    task = core.load_task(arena_dir, "p01")

    def go(*argv):
        args = arena.build_parser().parse_args(["run", "--label", "ig", "--agents", "pi", "--tasks", "p01", "--reps", "4",
                                                "--timeout", "120", "--ws-root", ws_d] + list(argv))
        buf = io.StringIO()
        code = None
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                arena.cmd_run(args)
            except SystemExit as e:
                code = e.code
        del core._LOCKS[:]                                      # the workspace lock belongs to the process; release it between calls
        return code, buf.getvalue()

    def rows():
        import arena_report as rep_
        return rep_.collect_rows(runs_d, "ig")

    try:
        t0 = time.time()
        mock.reset(steps_for("solve", task, arena_dir))
        mock.fail(-1)
        code, out = go("--stop-after-infra", "2")
        ld = os.path.join(runs_d, "ig")
        dirs = sorted(d for d in os.listdir(ld) if d[:1].isdigit() and os.path.isdir(os.path.join(ld, d))) if os.path.isdir(ld) else []
        flagged = [d for d in dirs if (core.load_json(os.path.join(runs_d, "ig", d, "result.json"), {}) or {}).get("infra_error")]
        c.append((code == 4, "an outage: the batch stops with exit code 4 after 2 runs in a row hit a gateway problem (exit %s, %.0fs)" % (code, time.time() - t0)))
        c.append(("STOP: 2 runs in a row" in out and "003_" not in out and "004_" not in " ".join(dirs),
                  "it says why, and the 3rd and 4th run were never started (dirs %s)" % dirs))
        c.append((len(flagged) >= 2 and all(d.startswith(("001_", "002_")) for d in flagged),
                  "the runs that hit the outage are flagged infra_error (%s)" % flagged))
        c.append(("001_pi_p01_r1_a2" in dirs, "each was retried once by the automatic retry (attempt 2 exists)"))
        # without --redo-infra a plain --resume leaves flagged runs alone
        mock.fail(0)
        code, out = go("--resume", "--stop-after-infra", "2")
        got, sup = rows()
        c.append((code is None and len(got) == 4 and sum(1 for r in got if r["infra_error"]) >= 2 and "redoing" not in out and
                  not any(r["infra_error"] for r in got if r["seq"] > 2) and sup >= 2,
                  "--resume alone keeps the flagged runs as they are and only runs the rest (%d rows, %d flagged, %d superseded)" % (
                      len(got), sum(1 for r in got if r["infra_error"]), sup)))
        # with --redo-infra the flagged ones are redone as new attempts once the gateway is back
        code, out = go("--resume", "--redo-infra")
        got, sup = rows()
        att = {r["seq"]: r["attempt"] for r in got}
        c.append((code is None and len(got) == 4 and not any(r["infra_error"] for r in got),
                  "--resume --redo-infra redoes them: every run now has an answer (%d rows, flagged: %d)" % (len(got), sum(1 for r in got if r["infra_error"]))))
        c.append((out.count("redoing ") == 2 and att.get(1, 0) >= 3 and att.get(2, 0) >= 3,
                  "the redone runs are attempts 3+ (the flagged attempts stay on disk, superseded): %s" % att))
        c.append((all(r["pass"] for r in got), "and they solve the task like any other run (pass %s)" % [r["pass"] for r in got]))
        code, out = go("--resume", "--redo-infra")
        c.append((code is None and "redoing" not in out and "4/4 runs finished" in out, "run again: nothing left to redo"))
    finally:
        mock.fail(0)
        arena.CFG_ROOT, arena.RUNS_DIR = saved[0], saved[1]
        if saved[2] is None:
            os.environ.pop("ARENA_SLEEP_SCALE", None)
        else:
            os.environ["ARENA_SLEEP_SCALE"] = saved[2]
    return c


def guard_parse_checks():
    """parse_guard on stderr text as the v1 extensions write it (see arena_core.parse_guard)."""
    c = []
    none = core.parse_guard("")
    c.append((none["gate_blocks"] == 0 and none["fid_blocks"] == 0 and none["budget_soft"] == 0 and none["budget_hard"] == 0
              and none["gate_examples"] == [], "no stderr, no events"))
    text = ("pi: some other warning\n"
            "[safety-gate] blocked rm-rf-root: rm -rf /\n"
            "[fidelity-gate] blocked fid-not-utf8: strings.fr\n"
            "[fidelity-gate] blocked fid-mixed-eol: routes.js\n"
            "[fidelity-gate] blocked fid-mixed-eol: routes.js\n"
            "[budget-guard] soft limit: 40000 output tokens\n"
            "[budget-guard] stopped: 80000 output tokens\n"
            "  [safety-gate] blocked indented-line-is-not-a-log: x\n"
            "the model wrote [safety-gate] blocked in the middle of a line\n")
    g = core.parse_guard(text)
    c.append((g["gate_blocks"] == 4, "safety and fidelity gate lines are both counted, nothing else (%s)" % g["gate_blocks"]))
    c.append((g["fid_blocks"] == 3, "fidelity blocks are told apart by their fid- ids (%s)" % g["fid_blocks"]))
    c.append((g["gate_ids"] == {"rm-rf-root": 1, "fid-not-utf8": 1, "fid-mixed-eol": 2}, "ids are tallied (%s)" % g["gate_ids"]))
    c.append((g["gate_examples"][0] == "rm-rf-root: rm -rf /" and len(g["gate_examples"]) == 4, "examples keep the id and the snippet"))
    c.append((g["budget_soft"] == 1 and g["budget_hard"] == 1, "budget-guard soft and hard events (%s/%s)" % (g["budget_soft"], g["budget_hard"])))
    return c


def report_unit_checks(tmp):
    """The report's cache bookkeeping on synthetic rows: cold-start flag, uncached tokens, noise, unstable prefix."""
    runs = os.path.join(tmp, "report-unit", "runs")

    def row(label, agent, task, rep, seq, first, later, out=200, ok=True, tests=None, usage_missing=False, **extra):
        """first = (prompt, cache_read) of the first request; later = [(prompt, cache_read), ...]"""
        calls = [first] + list(later)
        prompt = sum(c[0] for c in calls)
        read = sum(c[1] for c in calls)
        r = {"schema": 1, "label": label, "seq": seq, "run_id": "%03d_%s_%s_r%d" % (seq, agent, task, rep), "attempt": 1,
             "agent": agent, "agent_version": "1", "model": "m", "effort": "e", "toolset": "default", "variant": None,
             "task": task, "rep": rep, "pass": ok, "solved": ok, "timed_out": False, "infra_error": False, "agent_error": None,
             "tampered": [], "wall_s": 20.0 + rep, "turns": len(calls), "tool_calls": 4, "tool_errors": 0,
             "tokens": {"input": prompt - read, "cache_read": read, "cache_write": 0, "output": out, "reasoning": 0,
                        "prompt_total": prompt},
             "cache_hit_rate": read / prompt, "cost_usd": 0.001 + 0.0001 * rep, "price_model": "m", "minimality": 1.0,
             "first_req": {"prompt_total": first[0], "cache_read": first[1], "hit_rate": first[1] / first[0]},
             "tests_ran": (tests or (None, None))[0], "tests_failed": (tests or (None, None))[1],
             "cliffs": [], "usage_missing": usage_missing, "n_tools_exposed": 4}
        r.update(extra)
        d = os.path.join(runs, label, r["run_id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "result.json"), "w") as fh:
            json.dump(r, fh)

    # pi p01: first run cold (512 of 1646 cached), four warm ones;  pi p02: every repeat starts cold (unstable prefix)
    for rep in range(1, 6):
        cold = rep == 1
        row("u1", "pi", "p01", rep, rep, (1646, 512 if cold else 1408), [(2500, 1600), (3000, 2432), (3600, 2944)],
            ok=rep != 4, tests=(29, 1) if rep == 4 else (29, 0),
            fail_reason=None if rep != 4 else "hidden/visible tests failed",
            verify_notes=[] if rep != 4 else ["answers correct 4/5 (wrong: 2)"])
        row("u1", "pi", "p02", rep, 10 + rep, (2149, 512), [(3000, 2100), (3500, 2900)])
        row("u1", "cc", "p01", rep, 20 + rep, (17913, 512 if cold else 17664), [(18400, 17792), (19000, 18304)])
        row("u1", "cc", "p02", rep, 30 + rep, (18415, 512 if rep == 1 else 18176), [(19000, 18304)])
    row("u1", "cc", "p03", 1, 40, (10, 0), [(20, 0)], usage_missing=True)           # no usage numbers: must not crash
    text, rows = arena_report.build_report(runs, ["u1"])
    r = {x["run_id"]: x for x in rows}
    first, second = r["001_pi_p01_r1"], r["002_pi_p01_r2"]
    lines = {ln.split()[0]: ln for ln in text.splitlines() if ln[:3].isdigit()}
    chk = [
        (arena_report.is_cold(first) and not arena_report.is_cold(second), "a first request with 31% hits is cold, 86% is warm"),
        (arena_report.first_fresh(first) == 1646 - 512 and arena_report.first_fresh(second) == 238,
         "uncached tokens of the first request (%s / %s)" % (arena_report.first_fresh(first), arena_report.first_fresh(second))),
        (arena_report.fresh_rest(second) == (2500 - 1600) + (3000 - 2432) + (3600 - 2944),
         "uncached tokens after the first request (%s)" % arena_report.fresh_rest(second)),
        (arena_report.fresh_total(second) == arena_report.first_fresh(second) + arena_report.fresh_rest(second),
         "first + rest = whole run"),
        (arena_report.fresh_rest(r["040_cc_p03_r1"]) is None, "runs without usage numbers have no uncached-token figures"),
        (lines["001_pi_p01_r1"].rstrip().endswith("K") and not lines["002_pi_p01_r2"].rstrip().endswith("K"),
         "run table flags the cold run only"),
        ("fail 1/29" in lines["004_pi_p01_r4"], "a failing run shows how many tests failed"),
        ("cold start (1st-request hit < 50%)" in text and "== cache warmth" in text, "report explains K and has the warmth table"),
        ("almost every repeat after the first started cold for: p02 pi" in text, "unstable prefix is warned about (p02 pi)"),
        ("p01 pi" not in text.split("WARNING:")[-1] if "WARNING:" in text else True, "stable prefix (p01 pi) is not warned about"),
        ("cold-start run(s) left out" in text, "noise table says it leaves cold runs out"),
    ]
    why = text.split("== failing runs: why (verifier notes) ==")[-1].split("==")[0] if "== failing runs" in text else ""
    chk.append(("004_pi_p01_r4: hidden/visible tests failed | answers correct 4/5 (wrong: 2)" in why and "001_pi_p01_r1" not in why,
                "failing runs are listed with the verifier's notes, passing runs are not"))
    nl, advice = arena_report.noise_table(rows)
    chk.append(("fresh" in advice and "cold" not in advice and "toolerr" not in advice, "noise advice covers uncached tokens, not the deterministic ones"))
    dl, sl, totals = arena_report.wtl_table(rows, "pi", "cc")
    chk.append((totals["cold"][0] >= 1, "pi's smaller cold start is a W on the board (%s)" % totals["cold"]))
    chk.append(("worst run" in "\n".join(sl), "the board says the cold metric is the worst run, not the median"))
    return chk


def run(arena_dir, keep=False):
    os.environ["ARENA_CANARY_SECRET"] = CANARY          # must never reach an agent
    tmp = tempfile.mkdtemp(prefix="arena-selftest-")
    results = []                                         # (scenario, [(ok, message)])
    mock = None
    try:
        setup = core.load_json(os.path.join(arena_dir, "configs", "setup.json"), {})
        bins = {"pi": os.environ.get("ARENA_PI_BIN") or (setup.get("pi") or {}).get("bin") or shutil.which("pi"),
                "cc": os.environ.get("ARENA_CC_BIN") or (setup.get("cc") or {}).get("bin") or shutil.which("claude")}
        print("selftest in %s" % tmp)
        real_home = setup.get("home_mode") == "real"           # `setup` found that a binary needs your real HOME
        probe_env = core.base_env(os.path.join(tmp, "probe"), real_home=real_home)
        versions = {}
        for a, b in bins.items():
            if not b or not os.path.exists(b):
                print("  %s: not found (set ARENA_%s_BIN); its scenarios are skipped" % (a, "PI" if a == "pi" else "CC"))
                bins[a] = None
            else:
                versions[a] = core.tool_version(b, probe_env)
                print("  %s: %s %s" % (a, b, versions[a]))
        if not any(bins.values()):
            print("no agent binary found")
            return 1

        # ---- task self-check -----------------------------------------------------------------------
        checks = []
        for tid in core.list_tasks(arena_dir):
            r = core.check_task(arena_dir, tid, os.path.join(tmp, "taskcheck"))
            checks.append((r["ok"], "task %s: unsolved fails (%s/%s tests failed), reference passes (%s tests)" % (
                tid, r["unsolved"]["tests_failed"], r["unsolved"]["tests_ran"], r["solved"]["tests_ran"])))
        results.append(("tasks", checks))

        # ---- mock gateway + blank configs pointing at it ---------------------------------------------
        mock = Mock(arena_dir, tmp)
        base = "http://127.0.0.1:%d" % mock.port
        cfg = os.path.join(tmp, "configs")
        write_configs(cfg, base)
        prices = core.load_prices(arena_dir)
        runs_dir, ws_root = os.path.join(tmp, "runs"), os.path.join(tmp, "ws")

        scenarios = [
            # name, agent, task, kind, opts, timeout
            ("solve pi p01 (thinking low)", "pi", "p01", "solve", {"pi_thinking": "low"}, 240),
            ("solve cc p01 (effort low)", "cc", "p01", "solve", {"cc_effort": "low"}, 240),
            ("solve pi p02 (defaults)", "pi", "p02", "solve", {}, 240),
            ("solve cc p02 (defaults)", "cc", "p02", "solve", {}, 240),
            ("noop pi p01", "pi", "p01", "noop", {}, 240),
            ("tamper cc p02", "cc", "p02", "tamper", {}, 240),
            ("timeout pi p01", "pi", "p01", "timeout", {}, 8),
            ("timeout cc p01", "cc", "p01", "timeout", {}, 8),
            ("timeout+escaped child pi p01", "pi", "p01", "escape", {}, 8),
            ("timeout+escaped child cc p02", "cc", "p02", "escape", {}, 8),
        ]
        for seq, (name, agent, tid, kind, opts, timeout) in enumerate(scenarios, 1):
            if not bins[agent]:
                continue
            task = core.load_task(arena_dir, tid)
            mock.reset(steps_for(kind, task, arena_dir))
            t0 = time.time()
            print("  running %-30s ..." % name, end="", flush=True)
            row = core.execute_run(arena_dir, cfg, ws_root, runs_dir, "selftest", seq, agent, task, seq, bins,
                                   dict(opts, toolset="default", real_home=real_home), prices, timeout, versions=versions)
            print(" %.0fs" % (time.time() - t0))
            results.append((name, evaluate(kind, agent, task, row, mock, runs_dir, ws_root, opts, versions, tmp)))

        # ---- agent directories: same path on every run, emptied each time -> identical first requests ---------------------
        fx = []
        a_dir = core.fresh_env_dir(ws_root, "pi")
        with open(os.path.join(a_dir, "stale.txt"), "w") as f:
            f.write("left over from an earlier run")
        b_dir = core.fresh_env_dir(ws_root, "pi")
        fx.append((a_dir == b_dir and os.listdir(b_dir) == [],
                   "the agent directory has the same path on every run and is emptied each time (%s)" % b_dir))
        core.retire_env_dir(b_dir, tmp)
        fx.append((not os.path.exists(b_dir), "and it is removed again after the run"))
        # Agents print their own paths into the system prompt (Claude Code: its memory directory), so with a path that
        # changes per run the first request of every run would miss the gateway's prompt cache.  Two consecutive runs
        # of one agent on one task must therefore send the same first request, and the cache must serve it.
        task_f = core.load_task(arena_dir, "p01")
        h1 = core.prepare_workspace(arena_dir, task_f, os.path.join(ws_root, "_basecheck"), ws_root, probe_env)
        time.sleep(1.2)
        h2 = core.prepare_workspace(arena_dir, task_f, os.path.join(ws_root, "_basecheck"), ws_root, probe_env)
        fx.append((h1 == h2, "the baseline commit has the same hash on every run, Claude Code prints it in its first message (%s, %s)" % (h1[:7], h2[:7])))
        mock.reset({"steps": [], "final": "PONG"})
        for n, (agent, proto) in enumerate((("pi", "openai"), ("cc", "anthropic"))):
            if not bins[agent]:
                continue
            starts = []
            for k in (1, 2):
                starts.append(len([r for r in mock.requests() if r["proto"] == proto]))
                core.execute_run(arena_dir, cfg, ws_root, runs_dir, "selftest-fixed", 100 + 10 * n + k, agent, task_f, k, bins,
                                 {"toolset": "default", "real_home": real_home}, prices, 240, versions=versions)
            reqs_f = [r for r in mock.requests() if r["proto"] == proto]
            f1 = next((r for r in reqs_f[starts[0]:starts[1]] if r["main"]), None)
            f2 = next((r for r in reqs_f[starts[1]:] if r["main"]), None)
            if not (f1 and f2):
                fx.append((False, "%s: both runs made a main request (run 1: %s, run 2: %s)" % (agent, bool(f1), bool(f2))))
                continue
            same = ["tools" if f1["tools_hash"] == f2["tools_hash"] else "TOOLS DIFFER"]
            if proto == "anthropic":
                same.append("system prompt" if f1["system_hash"] == f2["system_hash"] else "SYSTEM PROMPT DIFFERS")
            same.append("messages" if f1["msg_hashes"] == f2["msg_hashes"] else "MESSAGES DIFFER")
            fx.append((f2["prompt_tokens"] - f2["cached_tokens"] <= 128,      # all but the last partial 64-token block
                       "%s: the second run's first request is served from the cache (%d of %d prompt tokens; identical: %s)" % (
                           agent, f2["cached_tokens"], f2["prompt_tokens"], ", ".join(same))))
        # one agent-running arena command at a time per workspace root (the OS releases the lock when the process ends)
        lock_hold = ("import sys, time; sys.path.insert(0, sys.argv[1]); import arena_core as c; "
                     "c.arena_lock(sys.argv[2], 'holder'); print('locked', flush=True); time.sleep(60)")
        lock_try = "import sys; sys.path.insert(0, sys.argv[1]); import arena_core as c; c.arena_lock(sys.argv[2], 'second'); print('got it')"
        hold = subprocess.Popen([sys.executable, "-c", lock_hold, arena_dir, ws_root], stdout=subprocess.PIPE, text=True)
        try:
            fx.append((hold.stdout.readline().strip() == "locked", "a first command takes the workspace lock"))
            r2 = subprocess.run([sys.executable, "-c", lock_try, arena_dir, ws_root], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=60)
            fx.append((r2.returncode != 0 and "another arena command" in r2.stdout and "holder" in r2.stdout,
                       "a second command on the same workspace root is refused and told who holds it: %s" % r2.stdout.strip()[:120]))
        finally:
            hold.kill()
            hold.wait(10)
        r3 = subprocess.run([sys.executable, "-c", lock_try, arena_dir, ws_root], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=60)
        fx.append((r3.returncode == 0 and "got it" in r3.stdout, "the lock is gone as soon as the first command dies (even killed)"))
        results.append(("fixed agent directories", fx))

        # ---- effort calibration plumbing ---------------------------------------------------------------
        cal = []
        plan = [(a, lv, 1) for a in ("pi", "cc") if bins[a] for lv in ("low", "high")]
        if plan:
            mock.reset([])                       # no script: the mock answers with plain text
            rows_c = core.run_calibration(cfg, ws_root, runs_dir, "selftest-calib", bins, prices, plan, 120, real_home=real_home)
            wire = [r.get("params", {}) for r in mock.requests() if r["main"]]
            cal.append((len(rows_c) == len(plan) and all(r["output"] > 0 and not r["error"] for r in rows_c),
                        "calibration ran %d runs with output tokens" % len(rows_c)))
            efforts = [(p.get("reasoning_effort") or (p.get("output_config") or {}).get("effort")) for p in wire]
            cal.append((efforts == [lv for (_, lv, _) in plan],
                        "effort levels reached the wire in order: %s" % efforts))
            cal.append(("nth_distinct" in core.calibration_table(rows_c) or "output tok" in core.calibration_table(rows_c),
                        "calibration table renders"))
        results.append(("calib", cal))

        # ---- gateways report usage in different ways: judge the convention, then read the numbers right -----------
        uc = []
        if bins["cc"]:
            for style, at, want in (("anthropic", "start", "additive"), ("exclusive", "delta", "additive"),
                                    ("inclusive", "delta", "inclusive")):
                os.environ["MOCK_USAGE"], os.environ["MOCK_USAGE_AT"] = style, at
                m2 = Mock(arena_dir, tmp)
                try:
                    cfg2 = os.path.join(tmp, "configs-%s-%s" % (style, at))
                    write_configs(cfg2, "http://127.0.0.1:%d" % m2.port)
                    m2.reset({"steps": [], "final": "PONG"})
                    traces = []
                    for i in (1, 2, 3):
                        rd = os.path.join(tmp, "usage-%s-%s-%d" % (style, at, i))
                        os.makedirs(rd)
                        env = core.cc_env(rd, cfg2, real_home=real_home)
                        wsu = os.path.join(ws_root, "_usage")
                        os.makedirs(wsu, exist_ok=True)
                        core.run_agent(core.agent_argv("cc", bins, "Reply with exactly: PONG", {}), env, wsu, rd, 120)
                        raw = open(os.path.join(rd, "events.jsonl"), "rb").read().decode("utf-8", "replace")
                        traces.append(arena_parse.parse("cc", raw, None))
                        time.sleep(0.2)
                    verdict, evidence = core.judge_usage(traces[0]["totals"], traces[2]["totals"])
                    uc.append((verdict == want, "gateway usage style %s/usage-at-%s is judged %s (got %s: %s)" % (style, at, want, verdict, evidence)))
                    last = m2.requests()[-1]
                    final = arena_parse.parse("cc", open(os.path.join(tmp, "usage-%s-%s-3" % (style, at), "events.jsonl"), "rb").read().decode("utf-8", "replace"),
                                              None, cc_inclusive=(verdict == "inclusive"))
                    tt, c0 = final["totals"], final["calls"][0]
                    uc.append((tt["input"] + tt["cache_read"] + tt["cache_write"] == last["prompt_tokens"] and tt["cache_read"] == last["cached_tokens"],
                               "  read with that convention, totals equal the gateway's truth (prompt %s == %s, cache_read %s == %s)"
                               % (tt["input"] + tt["cache_read"] + tt["cache_write"], last["prompt_tokens"], tt["cache_read"], last["cached_tokens"])))
                    uc.append((c0["prompt_total"] == last["prompt_tokens"] and c0["cache_read"] == last["cached_tokens"] and c0["output"] == last["output_tokens"],
                               "  per-call usage (raw API stream events) equals the truth even when usage arrives only at the end: %s" %
                               [c0["prompt_total"], c0["cache_read"], c0["output"]]))
                finally:
                    m2.stop()
                    os.environ.pop("MOCK_USAGE", None)
                    os.environ.pop("MOCK_USAGE_AT", None)
        results.append(("usage conventions", uc))

        # ---- the usage judge on plain numbers (the first case is what your magpie really reported) ---------------------
        def U(i, r, w=0):
            return {"input": i, "cache_read": r, "cache_write": w}
        jc = []
        for label, first, later, want in (
                ("magpie, your real numbers (210 + 18048 = 18258)", U(18258, 0), U(210, 18048), "additive"),
                ("magpie, the later request was a total miss", U(18258, 0), U(18258, 0), "unknown"),
                ("Anthropic native, with cache_creation", U(1, 0, 10812), U(1, 7552, 3260), "additive"),
                ("OpenAI style, 99% hit", U(18258, 0), U(18258, 18048), "inclusive"),
                ("OpenAI style, only a 70% hit", U(10813, 0), U(10813, 7552), "inclusive"),
                ("additive, only a 30% hit", U(10813, 0), U(7500, 3313), "additive"),
                ("not identical after all: falls back on the shape of the later request", U(18258, 0), U(500, 17000), "additive")):
            verdict, evidence = core.judge_usage(first, later)
            jc.append((verdict == want, "%s -> %s (got %s)" % (label, want, verdict)))
        results.append(("usage judge", jc))

        # ---- cacheprobe plumbing (SSE parsing and hit classification for both protocols) -----------------------
        cp = []
        mock.reset({"steps": [], "final": "OK"})
        eps = {"openai": {"url": base + "/v1/chat/completions", "headers": {"Authorization": "Bearer k"}, "model": "mock-model", "label": "mock"},
               "anthropic": {"url": base + "/v1/messages", "headers": {"Authorization": "Bearer k", "anthropic-version": "2023-06-01"},
                             "model": "mock-model", "label": "mock"}}
        recs_p, text_p = arena_probe.run(None, os.path.join(tmp, "cacheprobe"), ["openai", "anthropic"], 800, [0.1, 0.1], 1, 4, 0.1, 60,
                                         say=lambda m="": None, endpoints=eps)
        for proto in ("openai", "anthropic"):
            rs = [r for r in recs_p if r["proto"] == proto]
            rep = [r for r in rs if r["kind"] == "repeat" and r["idx"] > 1]
            grow = [r for r in rs if r["kind"] == "grow" and r["expected_cached"] is not None]
            cp.append((len(rs) == 7 and all(r["status"] == 200 and r["prompt"] for r in rs), "%s: 7 requests, all with usage" % proto))
            cp.append((len(rep) == 2 and all(r["cached"] >= 0.9 * r["prompt"] for r in rep), "%s: identical requests hit the cache" % proto))
            cp.append((len(grow) == 3 and all(r["lost"] is not None and r["lost"] <= 192 for r in grow), "%s: append-only turns lose at most one block or two" % proto))
        cp.append(("==== summary ====" in text_p and "append-only" in text_p, "summary text renders"))
        results.append(("cacheprobe", cp))

        # ---- a gateway outage in the middle of a batch: stop early, redo the affected runs afterwards -------------------------
        mock.reset({"steps": [], "final": "ok"})
        results.append(("gateway outage guard", infra_guard_checks(arena_dir, tmp, mock, base, bins, real_home, versions)))

        # ---- day1: step order, failures, interruption, resuming, and the results bundle (fake runner) ------------------
        results.append(("day1 plumbing", day1_checks(tmp)))
        results.append(("suite plumbing", suite_checks(tmp)))

        # ---- guard events in an agent's stderr (safety-gate, fidelity-gate, budget-guard) ------------------------------
        results.append(("guard log parsing", guard_parse_checks()))

        # ---- the report over the self-test rows ------------------------------------------------------
        text, rows = arena_report.build_report(runs_dir, ["selftest"])
        rc = [(bool(rows) and "== runs ==" in text and "per task x agent" in text, "report builds from %d rows" % len(rows))]
        if bins["pi"] and bins["cc"]:
            rc.append(("provisional pi vs claude" in text, "report has the pi-vs-claude board"))
        rc += report_unit_checks(tmp)
        results.append(("report", rc))
        if keep:
            with open(os.path.join(tmp, "report.txt"), "w") as f:
                f.write(text)
    finally:
        if mock:
            mock.stop()

    # ---- verdict -------------------------------------------------------------------------------------
    bad = 0
    print()
    for name, checks in results:
        fails = [m for ok, m in checks if not ok]
        print("%s  %s" % ("PASS" if not fails else "FAIL", name))
        for ok, m in checks:
            if not ok:
                print("        x " + m)
        bad += len(fails)
    n = sum(len(c) for _, c in results)
    print("\n%d checks, %d failed" % (n, bad))
    if keep:
        print("kept %s" % tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------ the checks
def evaluate(kind, agent, task, row, mock, runs_dir, ws_root, opts, versions, tmp):
    c = []

    def ok(cond, msg):
        c.append((bool(cond), msg))

    reqs = mock.requests()
    main = [r for r in reqs if r["main"]]
    run_dir = os.path.join(runs_dir, "selftest", row["run_id"])
    raw = open(os.path.join(run_dir, "events.jsonl"), "rb").read().decode("utf-8", "replace")
    ts = [float(x) for x in open(os.path.join(run_dir, "events.ts")).read().split()]
    tr = arena_parse.parse(agent, raw, ts)
    ok(row["agent_version"] == versions.get(agent), "agent version is pinned in the row (%s)" % row["agent_version"])
    ok(row["model"] == "mock-model", "model id recorded (%r)" % row["model"])
    ok(row["bad_lines"] == 0 and (row["events"] or 0) > 3, "event stream parsed (%s events, %s bad lines)" % (row["events"], row["bad_lines"]))
    ok(len(ts) == len([l for l in raw.split("\n") if l.strip()]), "one arrival time per event line")
    ok(os.path.realpath(tr["meta"].get("cwd") or "") == os.path.realpath(os.path.join(ws_root, task["id"])),
       "agent ran in the fixed workspace %s (reported %s)" % (os.path.join(ws_root, task["id"]), tr["meta"].get("cwd")))
    ok(CANARY not in raw and CANARY not in mock.bodies_text() and CANARY not in core.tail(os.path.join(run_dir, "stderr.txt"), 20000),
       "canary secret from the parent environment never reached the agent or the gateway")
    if agent == "cc":
        ok(tr["meta"].get("mcp_servers") == [], "no MCP servers in the blank Claude Code config")
    if kind in ("timeout", "escape"):
        ok(row["timed_out"] and not row["pass"] and row["fail_reason"] == "timeout", "hanging tool: run marked timed_out and failed")
        ok(row["wall_s"] < 8 + 12, "killed promptly (%.1fs for an 8s limit)" % row["wall_s"])
        time.sleep(0.5)
        ps = subprocess.run(["ps", "-eo", "args"], stdout=subprocess.PIPE, text=True).stdout
        ok(HANG_CMD not in ps, "no '%s' process survived the run" % HANG_CMD)
        if kind == "escape":
            meta = core.load_json(os.path.join(run_dir, "meta.json"), {})
            ok(ESCAPED_CMD not in ps, "a child that escaped the process group (setsid) was killed too")
            if agent == "pi":      # Claude Code cleans up its own children on SIGTERM, pi does not: the sweep must catch it
                ok((meta.get("stray_killed") or 0) >= 1, "the environment-marker sweep found it (stray_killed=%s)" % meta.get("stray_killed"))
        return c
    # ---- accounting must equal what the mock actually served ------------------------------------------
    t = row["tokens"]
    ok(row["turns"] == len(main) and len(main) > 0, "LLM calls: row %s == mock %s" % (row["turns"], len(main)))
    ok(t["prompt_total"] == sum(r["prompt_tokens"] for r in reqs), "prompt tokens: row %s == mock %s" % (t["prompt_total"], sum(r["prompt_tokens"] for r in reqs)))
    ok(t["cache_read"] == sum(r["cached_tokens"] for r in reqs), "cache-read tokens: row %s == mock %s" % (t["cache_read"], sum(r["cached_tokens"] for r in reqs)))
    ok(t["cache_write"] == sum(r["cache_creation_tokens"] for r in reqs), "cache-write tokens: row %s == mock %s" % (t["cache_write"], sum(r["cache_creation_tokens"] for r in reqs)))
    ok(t["output"] == sum(r["output_tokens"] for r in reqs), "output tokens: row %s == mock %s" % (t["output"], sum(r["output_tokens"] for r in reqs)))
    ok(row["first_req"] and row["first_req"]["prompt_total"] == main[0]["prompt_tokens"], "first-request prompt size matches the mock")
    ok(row["cost_usd"] is not None and row["cost_usd"] > 0, "cost recomputed from the price table (%s)" % row["cost_usd"])
    ok(row["cache_hit_rate"] is not None and row["cache_hit_rate"] > 0.3, "cache hit rate looks sane (%s)" % row["cache_hit_rate"])
    ok(row["cliffs"] == [] and all(r["append_only"] in (True, None) for r in main), "requests are append-only (no cache cliff)")
    if kind == "solve":
        ok(row["pass"], "solve: verifier says PASS")
        ok(row["tool_calls"] == 4 and row["tool_errors"] == 1, "tool accounting: %s calls, %s errors (expected 4 and 1)" % (row["tool_calls"], row["tool_errors"]))
        ok(row["turns"] == 5, "5 LLM calls (4 tool rounds + final answer): %s" % row["turns"])
        body = mock.bodies_text()
        ok("canary_count=0" in body, "agent environment has no inherited secrets")
        ok("http://127.0.0.1:9" in body, "proxy variables are blackholed inside the agent's shell")
        mock_reasoning = sum(r.get("reasoning_tokens", 0) for r in reqs)
        if agent == "pi":
            ok(t["reasoning"] == mock_reasoning and mock_reasoning > 0,
               "pi reasoning tokens: row %s == mock %s (and counted inside output)" % (t["reasoning"], mock_reasoning))
        else:
            ok(t["reasoning"] is not None, "claude reasoning tokens field present (%s; the mock sent %s inside output)" % (t["reasoning"], mock_reasoning))
        ok(row["diff"]["files"] >= 1 and row["minimality"] is not None, "diff measured (%s files, minimality %s)" % (row["diff"]["files"], row["minimality"]))
        ok(row["tests_ran"] and row["tests_failed"] == 0, "verifier counted tests: %s ran, %s failed" % (row["tests_ran"], row["tests_failed"]))
        first = main[0]["params"]
        if agent == "pi":
            want = opts.get("pi_thinking") or "medium"
            ok(first.get("reasoning_effort") == want, "pi effort on the wire: reasoning_effort=%r (wanted %r)" % (first.get("reasoning_effort"), want))
            ok(row["thinking_level"] == want, "pi thinking level recorded (%s)" % row["thinking_level"])
        else:
            want = opts.get("cc_effort") or "high"
            got = (first.get("output_config") or {}).get("effort")
            ok(got == want, "claude effort on the wire: output_config.effort=%r (wanted %r)" % (got, want))
        ok(row["n_tools_exposed"] >= (4 if agent == "pi" else 10), "tool list captured (%s tools)" % row["n_tools_exposed"])
    elif kind == "noop":
        ok(not row["pass"] and row["tests_failed"], "noop: verifier says FAIL (%s)" % row["fail_reason"])
    elif kind == "tamper":
        ok(not row["pass"] and row["tampered"], "tamper: FAIL because a protected test file was modified (%s)" % row["fail_reason"])
    return c
