"""day1: the whole first measurement session in one command, and ONE file to send back.

    python3 arena.py day1            setup (if needed) -> selftest -> smoke -> cacheprobe -> calib -> pilot -> report -> results file
    python3 arena.py day1 --quick    roughly half the time (shorter probe, 1 calibration rep, 3 pilot reps)
    python3 arena.py pack            just (re)build the results file from whatever exists

Every step's output goes to day1/<step>.log; finished steps are remembered in day1/state.json, so after an interruption
(Ctrl-C, closed terminal, reboot) the same command carries on: done steps are skipped and the pilot continues where it stopped.
The results file is a plain-text digest (arena-results-*.txt: every summary, the report and the data rows) plus a .tgz
with the same and a few raw event streams.  Both are assembled from an allowlist: configs/ (your gateway placeholders)
is never included, and anything that looks like a key is masked anyway."""
import io
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time

import arena_core as core

# name, argv after "arena.py", rough minutes, role
#   base   : everything needs it; a failure stops the session
#   check  : a failure is recorded and shown, the session goes on
#   gate   : a failure skips the steps that need working agents (the "agents" role)
#   free   : needs no agent (the probe talks to the gateway directly): runs regardless
#   agents : needs working agents
STEPS = [
    ("setup", ["setup"], 1, "base"),
    ("selftest", ["selftest"], 2, "check"),
    ("smoke", ["smoke"], 2, "gate"),
    ("cacheprobe", ["cacheprobe"], 25, "free"),
    ("calib", ["calib"], 20, "agents"),
    ("pilot", ["run", "--label", "pilot1", "--tasks", "p01,p02", "--agents", "pi,cc", "--reps", "5"], 90, "agents"),
    ("report", ["report", "--label", "pilot1"], 1, "agents"),
]
STEP_NAMES = [s[0] for s in STEPS]
INTERRUPTED = (130, -2)

# ------------------------------------------------------------------------------------------ masking
RE_SECRETS = [
    (re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{8,}"), "sk-<masked>"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1<masked>"),
    (re.compile(r"(?i)((?:\"?api[_-]?key\"?|ANTHROPIC_AUTH_TOKEN|ANTHROPIC_API_KEY|x-api-key|authorization)[\"']?\s*[:=]\s*[\"']?)"
                r"[^\"'\s,}<]{4,}"), r"\1<masked>"),
]


def mask(text):
    for rx, rep in RE_SECRETS:
        text = rx.sub(rep, text)
    return text


# ------------------------------------------------------------------------------------------ what to send back
SMALL = {"result.json", "meta.json", "stderr.txt", "verify.txt", "diff.patch", "summary.txt", "calib.txt", "calib.jsonl",
         "probe.jsonl", "plan.json", "results.jsonl", "report.txt", "errors.log"}
RAW = {"events.jsonl", "events.ts", "cc-transcript.jsonl"}              # only for the first repetition of each run
SKIP_DIRS = {"env", "home", "tmp", "pi-agent", "cc-config", "_tmp", "__pycache__"}  # a kept HOME / config dir is never packed
TEXT_EXT = (".txt", ".log", ".json", ".jsonl", ".patch", ".ts")
MAX_FILE = 25_000_000


def system_info(setup):
    def run(cmd):
        try:
            out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30,
                                 stdin=subprocess.DEVNULL).stdout.strip().splitlines()
            return out[0] if out else "?"
        except Exception as e:  # noqa
            return "? (%s)" % e
    lines = ["time    : %s %s (local)  =  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), time.strftime("%Z %z"),
                                                 time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())),
             "kernel  : %s" % platform.platform(), "python  : %s" % sys.version.split()[0],
             "node    : %s" % run(["node", "--version"]), "npm     : %s" % run(["npm", "--version"]),
             "git     : %s" % run(["git", "--version"]), "cpus    : %s" % os.cpu_count()]
    try:
        for l in open("/proc/meminfo"):
            if l.startswith("MemTotal"):
                lines.append("memory  : %s" % l.split(":")[1].strip())
                break
    except OSError:
        pass
    for k in ("pi", "cc"):
        v = (setup.get(k) or {})
        lines.append("%-8s: %s  %s" % (k, v.get("bin"), v.get("version")))
    lines.append("setup   : home_mode=%s  claude usage convention=%s" % (setup.get("home_mode"), (setup.get("usage") or {}).get("cc")))
    return "\n".join(lines)


def windows_path(p):
    """\\\\wsl.localhost\\Ubuntu\\home\\... for a WSL path (None outside WSL)."""
    w = shutil.which("wslpath")
    if not w:
        return None
    try:
        out = subprocess.run([w, "-w", p], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=10).stdout.strip()
        return out or None
    except Exception:  # noqa
        return None


def read_text(path, limit=400_000, tail=False):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = f.read()
    except OSError:
        return None
    if len(data) > limit:
        data = ("[... truncated; the .tgz has the whole file ...]\n" + data[-limit:]) if tail else \
            (data[:limit] + "\n[... truncated; the .tgz has the whole file ...]\n")
    return data


def last_lines(path, n):
    t = read_text(path, tail=True)
    return None if t is None else "\n".join(t.rstrip("\n").split("\n")[-n:])


def collect_files(arena_dir, labels=None):
    """[(absolute path, name inside the archive)] -- an allowlist, never the configs/ directory."""
    files = []
    d1 = os.path.join(arena_dir, "day1")
    for fn in sorted(os.listdir(d1)) if os.path.isdir(d1) else []:
        if os.path.isfile(os.path.join(d1, fn)):
            files.append((os.path.join(d1, fn), "day1/" + fn))
    sj = os.path.join(arena_dir, "configs", "setup.json")          # versions, paths, the usage verdict: no secrets in it
    if os.path.isfile(sj):
        files.append((sj, "setup.json"))
    runs = os.path.join(arena_dir, "runs")
    for top in sorted(os.listdir(runs)) if os.path.isdir(runs) else []:
        if top == "_tmp" or not os.path.isdir(os.path.join(runs, top)):
            continue
        if labels and not top.startswith("_") and top not in labels:
            continue
        for dp, dns, fns in os.walk(os.path.join(runs, top)):
            dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
            rel = os.path.relpath(dp, runs)
            first = rel.startswith("_smoke") or re.search(r"_r1(_a\d+)?$", rel) is not None
            for fn in sorted(fns):
                p = os.path.join(dp, fn)
                if (fn in SMALL or (first and fn in RAW)) and os.path.isfile(p) and os.path.getsize(p) <= MAX_FILE:
                    files.append((p, "runs/%s/%s" % (rel, fn)))
    return files


def digest(arena_dir, state, files, labels=None):
    """One plain-text file with everything needed to analyse the session (no raw event streams)."""
    runs = os.path.join(arena_dir, "runs")
    setup = core.load_json(os.path.join(arena_dir, "configs", "setup.json"), {}) or {}
    out = ["arena day1 results   (made %s)" % time.strftime("%Y-%m-%d %H:%M:%S %Z %z")]

    def sec(title, text):
        out.append("\n" + "=" * 100 + "\n== " + title + "\n" + "=" * 100 + "\n" + (text.rstrip("\n") if text else "(not there)"))

    sec("system", system_info(setup))
    sec("steps", steps_table(state))
    if setup:
        sec("configs/setup.json (versions and paths; no secrets)", mask(read_text(os.path.join(arena_dir, "configs", "setup.json"))))
    for name in ("setup", "selftest", "smoke", "cacheprobe", "calib"):
        lg = os.path.join(arena_dir, "day1", name + ".log")
        failed = str((state.get("steps", {}).get(name) or {}).get("status", "")).startswith(("failed", "interrupted"))
        if os.path.isfile(lg) and (failed or name in ("setup", "selftest")):
            sec("console output of step %s (%s)" % (name, "last 120 lines" if failed else "last 45 lines"),
                last_lines(lg, 120 if failed else 45))
    sm = read_text(os.path.join(runs, "_smoke", "summary.txt"))
    if sm is not None:
        sec("smoke summary", sm)
    probe_root = os.path.join(runs, "_cacheprobe")
    for lb in sorted(os.listdir(probe_root)) if os.path.isdir(probe_root) else []:
        sec("cacheprobe %s: summary" % lb, read_text(os.path.join(probe_root, lb, "summary.txt")))
    calib_root = os.path.join(runs, "_calib")
    for lb in sorted(os.listdir(calib_root)) if os.path.isdir(calib_root) else []:
        sec("calibration %s: table" % lb, read_text(os.path.join(calib_root, lb, "calib.txt")))
    label_dirs = [d for d in sorted(os.listdir(runs)) if not d.startswith("_") and os.path.isdir(os.path.join(runs, d))] \
        if os.path.isdir(runs) else []
    if labels:
        label_dirs = [d for d in label_dirs if d in labels]
    for lb in label_dirs:
        sec("run label %s: report" % lb, read_text(os.path.join(runs, lb, "report.txt")) or
            "(no report.txt: run `python3 arena.py report --label %s`)" % lb)
        el = os.path.join(runs, lb, "errors.log")
        if os.path.isfile(el):
            sec("run label %s: runner errors" % lb, read_text(el, 20_000))
    pl = os.path.join(arena_dir, "day1", "pilot.log")
    if os.path.isfile(pl):
        sec("pilot console output (last 70 lines)", last_lines(pl, 70))
    out.append("\n" + "#" * 100 + "\n# DATA (json lines)\n" + "#" * 100)
    for lb in sorted(os.listdir(calib_root)) if os.path.isdir(calib_root) else []:
        sec("data: calibration %s calib.jsonl" % lb, read_text(os.path.join(calib_root, lb, "calib.jsonl")))
    for lb in sorted(os.listdir(probe_root)) if os.path.isdir(probe_root) else []:
        sec("data: cacheprobe %s probe.jsonl" % lb, read_text(os.path.join(probe_root, lb, "probe.jsonl")))
    for lb in label_dirs:
        sec("data: run label %s results.jsonl" % lb, read_text(os.path.join(runs, lb, "results.jsonl")))
    out.append("\n" + "#" * 100 + "\n# files in the .tgz\n" + "#" * 100)
    out.append("\n".join("%9d  %s" % (os.path.getsize(p), n) for p, n in files))
    return mask("\n".join(out) + "\n")


def pack_results(arena_dir, labels=None, state=None, stamp=None):
    """Write arena-results-<stamp>.txt and .tgz next to arena.py.  Returns (txt path, tgz path, number of files)."""
    state = state if state is not None else (core.load_json(os.path.join(arena_dir, "day1", "state.json"), {}) or {})
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    d1 = os.path.join(arena_dir, "day1")
    os.makedirs(d1, exist_ok=True)
    setup = core.load_json(os.path.join(arena_dir, "configs", "setup.json"), {}) or {}
    with open(os.path.join(d1, "system.txt"), "w", encoding="utf-8") as f:
        f.write(system_info(setup) + "\n")
    files = collect_files(arena_dir, labels)
    txt_path = os.path.join(arena_dir, "arena-results-%s.txt" % stamp)
    tgz_path = os.path.join(arena_dir, "arena-results-%s.tgz" % stamp)
    text = digest(arena_dir, state, files, labels)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)
    with tarfile.open(tgz_path, "w:gz") as tar:
        def add_bytes(name, data):
            ti = tarfile.TarInfo("arena-results/" + name)
            ti.size, ti.mtime, ti.mode = len(data), int(time.time()), 0o644
            tar.addfile(ti, io.BytesIO(data))
        add_bytes("RESULTS.txt", text.encode("utf-8"))
        for path, name in files:
            with open(path, "rb") as f:
                data = f.read()
            if name.endswith(TEXT_EXT):
                data = mask(data.decode("utf-8", "replace")).encode("utf-8")
            add_bytes(name, data)
    return txt_path, tgz_path, len(files) + 1


def steps_table(state):
    rows = ["%-11s %-26s %8s" % ("step", "status", "minutes")]
    st = state.get("steps", {})
    for name in STEP_NAMES:
        s = st.get(name) or {}
        mins = s.get("minutes")
        rows.append("%-11s %-26s %8s" % (name, s.get("status", "not run"), "-" if mins is None else mins))
    return "\n".join(rows)


# ------------------------------------------------------------------------------------------ running
def run_step(arena_dir, name, argv, log_path):
    """Run `arena.py <argv>`, copy its output to the terminal and to the log.  Returns the exit code."""
    cmd = [sys.executable, os.path.join(arena_dir, "arena.py")] + argv
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    with open(log_path, "w", encoding="utf-8") as log:
        log.write("$ %s\n" % " ".join(cmd))
        p = subprocess.Popen(cmd, cwd=arena_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, env=env,
                             stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
        try:
            for line in p.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
                log.flush()
            p.wait()
        except KeyboardInterrupt:
            # the child got the same Ctrl-C: give it time to save what it has (the pilot writes its rows), then stop it
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.terminate()
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
            log.write("\n[interrupted]\n")
            raise
        log.write("\n[exit code %d]\n" % p.returncode)
    return p.returncode


def plan_steps(args):
    quick = bool(getattr(args, "quick", False))
    reps = getattr(args, "pilot_reps", None) or (3 if quick else 5)
    steps = []
    for name, argv, minutes, role in STEPS:
        argv = list(argv)
        if name == "pilot":
            argv[argv.index("--reps") + 1] = str(reps)
            minutes = 18 * reps
        if name == "cacheprobe" and quick:
            argv.append("--quick")
            minutes = 5
        if name == "calib" and quick:
            argv += ["--reps", "1"]
            minutes = 7
        steps.append((name, argv, minutes, role))
    return steps


def names_arg(value, what):
    names = [x for x in (value or "").split(",") if x]
    bad = [n for n in names if n not in STEP_NAMES]
    if bad:
        print("error: --%s: unknown step %s (steps: %s)" % (what, ", ".join(bad), ", ".join(STEP_NAMES)), file=sys.stderr)
        sys.exit(2)
    return set(names)


def main(arena_dir, args, steps=None, runner=None):
    d1 = os.path.join(arena_dir, "day1")
    os.makedirs(d1, exist_ok=True)
    state_path = os.path.join(d1, "state.json")
    state = core.load_json(state_path, {}) or {}
    state.setdefault("steps", {})
    state.setdefault("started", core.now_iso())
    skip, only, redo = names_arg(args.skip, "skip"), names_arg(args.only, "only"), names_arg(args.redo, "redo")
    if "setup" in redo:
        redo.add("smoke")                                   # setup.json is rewritten: the usage verdict is gone with it
    steps = steps or plan_steps(args)
    runner = runner or (lambda name, argv, log: run_step(arena_dir, name, argv, log))
    have_setup = os.path.isfile(os.path.join(arena_dir, "configs", "setup.json"))

    todo = []
    for name, argv, minutes, role in steps:
        if name in skip or (only and name not in only):
            continue
        if name == "setup":                                 # decided by the file, not by the remembered state
            if have_setup and "setup" not in redo:
                if not (state["steps"].get("setup") or {}).get("status", "").startswith("done"):
                    state["steps"]["setup"] = {"status": "done (existing)", "minutes": None}
                continue
        elif (state["steps"].get(name) or {}).get("status", "").startswith("done") and name not in redo:
            continue
        todo.append((name, argv, minutes, role))
    total = sum(s[2] for s in todo)
    print("day1: %s" % (" -> ".join(s[0] for s in todo) or "nothing left to do"))
    if todo:
        print("  about %d minutes (%.1f hours), no input needed. If it stops for any reason, run the same command again:\n"
              "  finished steps are skipped and the pilot continues where it stopped. Inside tmux it survives a closed terminal.\n" % (
                  total, total / 60.0), flush=True)

    gate_ok, stopped, result = True, None, 0
    try:
        for name, argv, minutes, role in todo:
            rec = state["steps"].setdefault(name, {})
            if role == "agents" and not gate_ok:
                rec.update(status="skipped (smoke failed)", minutes=None)
                core.save_json(state_path, state)
                print("\n-- skipping %s: smoke failed, so the agents do not work yet\n" % name, flush=True)
                result = 1
                continue
            print("=" * 100 + "\n== %s   (about %d min)\n" % (name, minutes) + "=" * 100, flush=True)
            if name == "pilot" and os.path.isdir(os.path.join(arena_dir, "runs", argv[argv.index("--label") + 1])):
                argv = argv + ["--resume"]
            t0 = time.time()
            try:
                rc = runner(name, argv, os.path.join(d1, name + ".log"))
            except KeyboardInterrupt:
                rec.update(status="interrupted", minutes=round((time.time() - t0) / 60, 1))
                core.save_json(state_path, state)
                stopped = "interrupted"
                break
            minutes_taken = round((time.time() - t0) / 60, 1)
            if rc == 0:
                rec.update(status="done", minutes=minutes_taken, finished=core.now_iso())
            elif rc in INTERRUPTED:
                rec.update(status="interrupted", minutes=minutes_taken)
                stopped = "interrupted"
            else:
                rec.update(status="failed (exit %s)" % rc, minutes=minutes_taken)
                result = 1
            core.save_json(state_path, state)
            if stopped:
                break
            if rc != 0:
                print("\n!! step %s exited with code %s (see day1/%s.log)\n" % (name, rc, name), flush=True)
                if role == "base":
                    stopped = name
                    break
                if role == "gate":
                    gate_ok = False
    except KeyboardInterrupt:                                  # Ctrl-C between two steps
        stopped = "interrupted"
    core.save_json(state_path, state)

    txt, tgz, n = pack_results(arena_dir, state=state)
    print("\n" + "=" * 100)
    print(steps_table(state))
    if stopped == "interrupted":
        print("\nStopped by you. Nothing is lost: run the same command again to continue.")
        result = 130
    elif stopped:
        print("\nThe session stopped at step %r (see day1/%s.log). Send me the results file anyway: I will tell you what to do." % (stopped, stopped))
    elif result:
        print("\nSome steps failed or were skipped (table above). Send me the results file anyway.")
    else:
        print("\nAll steps finished.")
    announce(arena_dir, txt, tgz, n)
    return result


def announce(arena_dir, txt, tgz, n):
    print("\nresults to send back (no keys inside):")
    print("  %s   (%.0f KB)  <- this one: plain text, everything needed" % (txt, os.path.getsize(txt) / 1024.0))
    print("  %s   (%.1f MB, %d files; the same plus a few raw event streams)" % (tgz, os.path.getsize(tgz) / 1e6, n))
    w = windows_path(txt)
    if w:
        print("in Windows:  %s\nopen the folder:  cd %s && explorer.exe ." % (w, arena_dir))
