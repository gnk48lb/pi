#!/usr/bin/env python3
"""arena - a small, fair harness for comparing coding-agent harnesses (pi vs Claude Code) on the same model.

  python3 arena.py day1 [--quick]        the whole first session in one resumable command, ending with ONE file to send back
  python3 arena.py pack                  (re)build that results file from whatever exists
  python3 arena.py setup                 read your pi / Claude Code gateway config, write blank arena configs
  python3 arena.py selftest              end-to-end test against a mock gateway (no tokens are spent)
  python3 arena.py smoke                 one tiny real request per agent through your real gateway
  python3 arena.py calib                 what do pi --thinking and claude --effort levels really do? (same short question)
  python3 arena.py cacheprobe            how reliable is the gateway's prompt cache? (no agent involved)
  python3 arena.py tasks [--check]       list tasks / verify "unsolved fails, reference solution passes"
  python3 arena.py suite [--label L]     the task suite in one resumable command: check tasks -> run -> report -> ONE file to send back
  python3 arena.py run --label L ...     run the tasks (see --help)
  python3 arena.py report --label L      tables, noise statistics, provisional W/T/L
  python3 arena.py prices                show the single price table

Python >= 3.9, standard library only.  See README.md.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import signal
import sys
import time
import traceback

import arena_core as core
import arena_day1
import arena_parse
import arena_probe
import arena_report

ARENA_DIR = core.ARENA_DIR
CFG_ROOT = os.path.join(ARENA_DIR, "configs")
RUNS_DIR = os.path.join(ARENA_DIR, "runs")
DEFAULT_WS_ROOT = os.environ.get("ARENA_WS", "/tmp/arena-ws")

SECRET_RE = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD|AUTH)", re.I)
CC_ENV_WHITELIST = re.compile(r"^(ANTHROPIC_(BASE_URL|AUTH_TOKEN|API_KEY|MODEL|SMALL_FAST_MODEL|CUSTOM_HEADERS|"
                              r"DEFAULT_[A-Z0-9_]+_MODEL)|API_TIMEOUT_MS)$")


def die(msg):
    print("error: " + msg, file=sys.stderr)
    sys.exit(2)


def redact(key, value):
    return "<set, %d chars>" % len(str(value)) if SECRET_RE.search(key) else str(value)


def bare_model(m):
    """workbuddy-ai/deepseek-v4.1-flash[1m] -> deepseek-v4.1-flash"""
    return re.sub(r"\[.*?\]$", "", str(m or "")).split("/")[-1]


def tmp_run_dir(name):
    d = os.path.join(RUNS_DIR, "_tmp", name)
    if os.path.exists(d):
        core.safe_rmtree(d, RUNS_DIR)
    os.makedirs(d)
    return d


# ------------------------------------------------------------------------------------------ setup
def strip_suffix(m):
    """workbuddy-ai/deepseek-v4.1-flash[1m] -> workbuddy-ai/deepseek-v4.1-flash"""
    return re.sub(r"\[.*?\]$", "", str(m or ""))


def setup_pi(args, cc_model):
    """Copy ONE provider and ONE model entry of your pi models.json: the entry that is the same model Claude Code uses.
    (Your magpie provider has look-alikes such as opencode-zen/deepseek-v4.1-flash-free: never pick by substring.)"""
    src = os.path.expanduser(args.pi_models or "~/.pi/agent/models.json")
    data = core.load_json(src)
    if not data or not data.get("providers"):
        die("cannot read providers from %s (use --pi-models)" % src)
    providers = data["providers"]
    pname = args.pi_provider or ("magpie" if "magpie" in providers else (list(providers)[0] if len(providers) == 1 else None))
    if pname not in providers:
        die("pick a provider with --pi-provider; your models.json has: %s" % ", ".join(providers))
    prov = providers[pname]
    models = prov.get("models") or []
    ids = [str(m.get("id")) for m in models]
    if args.pi_model:
        chosen, why = [m for m in models if m.get("id") == args.pi_model], "--pi-model"
    else:
        chosen, why = [m for m in models if strip_suffix(m.get("id")) == strip_suffix(cc_model)], "same id as Claude Code's model"
        if not chosen:
            chosen, why = [m for m in models if bare_model(m.get("id")) == bare_model(cc_model)], "same model name as Claude Code's model"
    if len(chosen) != 1:
        near = [i for i in ids if bare_model(cc_model) in i] or ids
        die("cannot tell which pi model is the same as Claude Code's %r (%d candidates). Pass --pi-model <id>. Provider %s has: %s"
            % (cc_model, len(chosen), pname, ", ".join(near)))
    pm = chosen[0]
    os.makedirs(os.path.join(CFG_ROOT, "pi"), exist_ok=True)
    core.save_json(os.path.join(CFG_ROOT, "pi", "models.json"), {"providers": {pname: dict(prov, models=[pm])}})
    core.save_json(os.path.join(CFG_ROOT, "pi", "settings.json"), {
        "defaultProvider": pname, "defaultModel": pm["id"], "packages": [], "enableInstallTelemetry": False})
    key = prov.get("apiKey")
    shape = ("looks like an environment-variable name" if isinstance(key, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", key)
             else "literal")
    print("pi      provider %s (%s) -> %s" % (pname, prov.get("api"), prov.get("baseUrl")))
    print("        model %s  [%s]  ctx=%s maxTokens=%s reasoning=%s   apiKey: %s, %s" % (
        pm["id"], why, pm.get("contextWindow"), pm.get("maxTokens"), pm.get("reasoning", "unset"),
        "set, %d chars" % len(key) if isinstance(key, str) else "missing", shape))
    if shape.startswith("looks like"):
        print("        note: the arena passes no environment variables through. Put a literal key in the template or use --pi-models.")
    if pm.get("reasoning") is not True:
        print("        WARNING: this model entry has no \"reasoning\": true, so pi sends NO reasoning_effort and pi's --thinking levels\n"
              "        change nothing on the wire, while Claude Code always sends adaptive thinking + effort. The comparison would\n"
              "        not be at the same effort. Set reasoning: true in your models.json (if the model supports it) and rerun setup.")
    return pm, {"provider": pname, "model": pm["id"], "api": prov.get("api"), "base_url": prov.get("baseUrl"),
                "reasoning_flag": pm.get("reasoning"), "context_window": pm.get("contextWindow"), "max_tokens": pm.get("maxTokens")}


def cmd_setup(args):
    os.makedirs(CFG_ROOT, exist_ok=True)
    os.chmod(CFG_ROOT, 0o700)
    setup = {"created": core.now_iso(), "python": sys.version.split()[0]}
    probe_env = core.base_env(tmp_run_dir("setup-probe"))

    # ---- the tools the tasks need ---------------------------------------------------------------
    for tool in ("git", "bash", "python3", "node", "npm", "make", "tar"):
        path = shutil.which(tool)
        print("%-8s %s" % (tool, path or "NOT FOUND on PATH"))
        if not path and tool in ("git", "bash", "python3"):
            die("%s is required" % tool)
        if not path:
            print("         warning: some tasks need %s (see `python3 arena.py tasks`); they are left out until it is installed%s" % (
                tool, " (sudo apt install make)" if tool == "make" else ""))
        elif path.startswith("/mnt/"):
            print("         WARNING: %s resolves to a Windows program (%s). The tasks need the Linux one: put it first on PATH." % (tool, path))
    setup["tools"] = {t: shutil.which(t) for t in ("git", "bash", "python3", "node", "npm", "make", "tar")}

    # ---- binaries ------------------------------------------------------------------------------
    pi_bin = args.pi_bin or os.environ.get("ARENA_PI_BIN") or shutil.which("pi")
    cc_bin = args.cc_bin or os.environ.get("ARENA_CC_BIN") or shutil.which("claude")
    if not pi_bin:
        die("pi not found on PATH (pass --pi-bin)")
    if not cc_bin:
        die("claude not found on PATH (pass --cc-bin)")
    for name, b in (("pi", pi_bin), ("claude", cc_bin)):
        if os.path.realpath(b).startswith("/mnt/"):
            die("%s resolves to a Windows program (%s). Use the Linux install (--%s-bin <path>)." % (
                name, os.path.realpath(b), "pi" if name == "pi" else "cc"))
    pi_ver, cc_ver = core.tool_version(pi_bin, probe_env), core.tool_version(cc_bin, probe_env)
    home_mode = "isolated"
    if "unknown" in pi_ver or "unknown" in cc_ver:
        print("a binary does not start with a fresh HOME (pi: %s | claude: %s)\ntrying again with your real HOME ..." % (pi_ver, cc_ver))
        probe_env = core.base_env(tmp_run_dir("setup-probe-real"), real_home=True)
        pi_ver, cc_ver = core.tool_version(pi_bin, probe_env), core.tool_version(cc_bin, probe_env)
        home_mode = "real"
        if "unknown" in pi_ver or "unknown" in cc_ver:
            die("pi or claude does not start even with your real HOME: pi=%s claude=%s" % (pi_ver, cc_ver))
        print("ok with your real HOME: runs will use it (config dirs stay isolated through PI_CODING_AGENT_DIR / CLAUDE_CONFIG_DIR)")
    setup["home_mode"] = home_mode
    print("pi      %s  %s" % (pi_bin, pi_ver))
    print("claude  %s  %s" % (cc_bin, cc_ver))

    # ---- claude code: only the gateway variables -------------------------------------------------
    cs = os.path.expanduser(args.cc_settings or "~/.claude/settings.json")
    env_in = (core.load_json(cs, {}) or {}).get("env", {}) or {}
    cc_env, dropped = {}, []
    for k, v in env_in.items():
        if CC_ENV_WHITELIST.match(k):
            cc_env[k] = str(v)
        else:
            dropped.append(k)
    for k, v in os.environ.items():                     # shell exports count too, settings.json wins
        if CC_ENV_WHITELIST.match(k) and k not in cc_env:
            cc_env[k] = v
    settings_model = (core.load_json(cs, {}) or {}).get("model")
    if args.cc_model:
        cc_env["ANTHROPIC_MODEL"] = args.cc_model
    elif "ANTHROPIC_MODEL" not in cc_env and settings_model:
        cc_env["ANTHROPIC_MODEL"] = str(settings_model)             # the "model" key of settings.json
        print("        (model taken from the \"model\" key of %s)" % cs)
    elif "ANTHROPIC_MODEL" not in cc_env and cc_env.get("ANTHROPIC_DEFAULT_SONNET_MODEL"):
        cc_env["ANTHROPIC_MODEL"] = cc_env["ANTHROPIC_DEFAULT_SONNET_MODEL"]
        print("        (model taken from ANTHROPIC_DEFAULT_SONNET_MODEL)")
    for need in ("ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL"):
        if need not in cc_env:
            die("%s not found in %s or the environment (use --cc-settings / --cc-model)" % (need, cs))
    if not ({"ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"} & set(cc_env)):
        print("        warning: no ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY found; a local gateway may not need one")
    os.makedirs(os.path.join(CFG_ROOT, "cc"), exist_ok=True)
    core.save_json(os.path.join(CFG_ROOT, "cc", "env.json"), cc_env)
    core.save_json(os.path.join(CFG_ROOT, "cc", "settings.json"), {})
    print("claude  env from %s:" % cs)
    for k in sorted(cc_env):
        print("          %s=%s" % (k, redact(k, cc_env[k])))
    if dropped:
        print("        not copied (blank baseline): %s" % ", ".join(sorted(dropped)))
    setup["cc"] = {"bin": cc_bin, "version": cc_ver, "model": cc_env["ANTHROPIC_MODEL"],
                   "base_url": cc_env["ANTHROPIC_BASE_URL"], "env_keys": sorted(cc_env)}
    # ---- pi: the SAME model, from your models.json ---------------------------------------------------
    pm, pi_info = setup_pi(args, cc_env["ANTHROPIC_MODEL"])
    pname = pi_info["provider"]
    setup["pi"] = dict(pi_info, bin=pi_bin, version=pi_ver)
    if bare_model(pm["id"]) != bare_model(cc_env["ANTHROPIC_MODEL"]):
        print("\nWARNING: pi model %r and Claude Code model %r are not the same model." % (pm["id"], cc_env["ANTHROPIC_MODEL"]))
    core.save_json(os.path.join(CFG_ROOT, "setup.json"), setup)
    print("\nwrote %s  (contains your gateway placeholders: never upload it)" % CFG_ROOT)
    print("next: python3 arena.py selftest   then   python3 arena.py smoke")


def load_setup():
    s = core.load_json(os.path.join(CFG_ROOT, "setup.json"))
    if not s:
        die("run `python3 arena.py setup` first")
    return s


# ------------------------------------------------------------------------------------------ tasks
def cmd_tasks(args):
    for tid in core.list_tasks(ARENA_DIR):
        t = core.load_task(ARENA_DIR, tid)
        miss = core.missing_tools(t)
        print("%-4s %-5s %-6s %-9s ref_diff=%-5s %s%s" % (tid, t.get("split", "dev"), t.get("lang"), t.get("category"),
                                                         t.get("ref_diff_lines"), t["title"],
                                                         ("   [NEEDS %s: not on PATH]" % ", ".join(miss)) if miss else ""))
    if args.check:
        ok_all = True
        tmp = tmp_run_dir("task-check")
        for tid in core.expand_tasks(ARENA_DIR, args.tasks):
            miss = core.missing_tools(core.load_task(ARENA_DIR, tid))
            if miss:
                print("check %s: SKIPPED (%s not on PATH)" % (tid, ", ".join(miss)))
                continue
            r = core.check_task(ARENA_DIR, tid, tmp, write_ref=args.write_ref)
            ok_all &= r["ok"]
            print("check %s: %s | unsolved: solved=%s failed=%s/%s | reference: solved=%s failed=%s/%s | ref diff lines=%s"
                  % (tid, "OK" if r["ok"] else "BROKEN", r["unsolved"]["solved"], r["unsolved"]["tests_failed"],
                     r["unsolved"]["tests_ran"], r["solved"]["solved"], r["solved"]["tests_failed"],
                     r["solved"]["tests_ran"], r.get("ref_diff_lines")))
        sys.exit(0 if ok_all else 1)


# ------------------------------------------------------------------------------------------ prices
def cmd_prices(args):
    p = core.load_prices(ARENA_DIR)
    print(p.get("_comment", ""))
    for k, v in p["models"].items():
        print("%-22s in %-6s cache_read %-6s cache_write %-6s out %-6s  (USD / 1M tokens) match=%s" % (
            k, v["input"], v["cache_read"], v["cache_write"], v["output"], v["match"]))


# ------------------------------------------------------------------------------------------ smoke
def cmd_smoke(args):
    """A few tiny identical requests per agent through the real gateway.  Shows what each agent reports, and settles
    how the gateway reports Claude Code's token usage (input_tokens with or without the cached part)."""
    setup = load_setup()
    core.arena_lock(args.ws_root, "smoke")
    bins = {"pi": setup["pi"]["bin"], "cc": setup["cc"]["bin"]}
    prices = core.load_prices(ARENA_DIR)
    real_home = setup.get("home_mode") == "real"
    base = os.path.join(RUNS_DIR, "_smoke")
    if os.path.exists(base):
        core.safe_rmtree(base, RUNS_DIR)
    os.makedirs(base)
    os.makedirs(args.ws_root, exist_ok=True)
    log = []

    def say(msg=""):
        print(msg, flush=True)
        log.append(msg)

    ok_all = True
    for agent in args.agents.split(","):
        traces, raws, verdict = [], [], None
        for i in range(1, args.repeat + 1):
            run_dir = os.path.join(base, "%s-%d" % (agent, i))
            os.makedirs(run_dir)
            envd = core.fresh_env_dir(args.ws_root, agent)      # same path every time: identical prompts stay identical
            env = (core.pi_env(envd, CFG_ROOT, real_home=real_home) if agent == "pi"
                   else core.cc_env(envd, CFG_ROOT, real_home=real_home))
            ws = os.path.join(args.ws_root, "_smoke")
            if os.path.exists(ws):
                core.safe_rmtree(ws, args.ws_root)
            os.makedirs(ws)
            argv = core.agent_argv(agent, bins, "Reply with exactly: PONG",
                                   {"pi_thinking": args.pi_thinking, "cc_effort": args.cc_effort})
            if i == 1:
                say("[%s] %s ..." % (agent, " ".join(shlex.quote(a) for a in argv[:3])))
            out = core.run_agent(argv, env, ws, run_dir, args.timeout)
            raw = open(os.path.join(run_dir, "events.jsonl"), "rb").read().decode("utf-8", "replace")
            ts = [float(x) for x in open(os.path.join(run_dir, "events.ts")).read().split()]
            tr = arena_parse.parse(agent, raw, ts)              # RAW numbers: the usage convention is judged below
            tot = tr["totals"]
            price = core.price_for(prices, tr["meta"].get("model"))
            good = "PONG" in (tr["final_text"] or "") and not out["timed_out"] and not tr["agent_error"]
            ok_all &= good
            say("  #%d %s  exit=%s  %.1fs  model=%s  thinking=%s  tools_exposed=%s" % (
                i, "OK  " if good else "FAIL", out["exit_code"], out["wall_s"], tr["meta"].get("model"),
                tr["meta"].get("thinking"), len(tr["meta"].get("tools_exposed") or [])))
            say("      calls=%d  reported usage: input %d, cache_read %d, cache_write %d, output %d, reasoning %s" % (
                len([c for c in tr["calls"] if not c["sub"]]), tot["input"], tot["cache_read"], tot["cache_write"],
                tot["output"], tot["reasoning"]))
            if agent == "cc":
                say("      per-call usage from the API stream: %s   billed outside visible calls: %d   stream events: %s" % (
                    [(c["input"], c["cache_read"], c["cache_write"], c["output"]) for c in tr["calls"]],
                    tr["aux"]["prompt_total"], tr["meta"].get("has_stream_events", False)))
                if not tr["meta"].get("has_stream_events"):
                    say("      WARNING: no stream events: per-call usage falls back to the assistant events' snapshot")
            say("      answer: %r" % (tr["final_text"] or "")[:100])
            core.retire_env_dir(envd, run_dir)
            if not good:
                say("      error: %s" % tr["agent_error"])
                say("      stderr: %s" % core.tail(os.path.join(run_dir, "stderr.txt"), 600).strip()[:600])
                break
            traces.append(tr)
            raws.append(raw)
            if i < args.repeat:
                core.nap(args.gap)
        if agent == "cc" and len(traces) >= 2:
            verdict, evidence = "unknown", ""
            for later in reversed(traces[1:]):
                verdict, evidence = core.judge_usage(traces[0]["totals"], later["totals"])
                if verdict != "unknown":
                    break
            setup["usage"] = {"cc": verdict, "evidence": evidence, "checked": core.now_iso()}
            core.save_json(os.path.join(CFG_ROOT, "setup.json"), setup)
            say("")
            say("  claude input_tokens convention: %s   (%s)" % (verdict.upper(), evidence))
            if verdict == "unknown":
                say("  -> could not tell; the arena assumes Anthropic style (input = fresh tokens only). Run smoke again in a minute,")
                say("     and send me this output: I will settle it from the numbers.")
            else:
                say("  -> saved in configs/setup.json; `run` and `calib` read Claude Code's usage accordingly")
        if traces:                                   # what one tiny request costs, with the convention now known
            final = (arena_parse.parse(agent, raws[-1], None, cc_inclusive=(agent == "cc" and verdict == "inclusive"))
                     if agent == "cc" else traces[-1])
            ft = final["totals"]
            say("  cost of the last request at the price table's rates: $%.6f  (prompt %d tokens, %d of them cached)" % (
                core.compute_cost(ft, core.price_for(prices, final["meta"].get("model"))) or 0.0,
                ft["input"] + ft["cache_read"] + ft["cache_write"], ft["cache_read"]))
        say("")
    say("smoke %s" % ("passed" if ok_all else "FAILED"))
    with open(os.path.join(base, "summary.txt"), "w") as f:
        f.write("\n".join(log) + "\n")
    print("\n(raw event streams are kept in %s; the summary is %s)" % (base, os.path.join(base, "summary.txt")))
    sys.exit(0 if ok_all else 1)


# ------------------------------------------------------------------------------------------ calib
def cmd_calib(args):
    """Effort calibration: one short reasoning-heavy prompt, every effort level of both agents, in an empty workspace."""
    setup = load_setup()
    core.arena_lock(args.ws_root, "calib")
    bins = {"pi": setup["pi"]["bin"], "cc": setup["cc"]["bin"]}
    prices = core.load_prices(ARENA_DIR)
    plan = []
    for rep in range(1, args.reps + 1):
        for agent, levels in (("pi", args.pi_levels), ("cc", args.cc_levels)):
            if agent in args.agents.split(","):
                for lv in filter(None, levels.split(",")):
                    plan.append((agent, lv, rep))
    print("calibration %s: %d runs (this is cheap: one short question per run)\n" % (args.label, len(plan)))

    def progress(i, n, r):
        print("[%2d/%d] %-3s %-7s r%d  %5.0fs  output %6d  reasoning %6s  calls %d  tools %d%s" % (
            i, n, r["agent"], r["level"], r["rep"], r["wall_s"], r["output"], r["reasoning"], r["calls"], r["tool_calls"],
            "  [timeout]" if r["timed_out"] else ("  [error: %s]" % r["error"] if r["error"] else "")), flush=True)
    rows = core.run_calibration(CFG_ROOT, args.ws_root, RUNS_DIR, args.label, bins, prices, plan, args.timeout,
                                real_home=setup.get("home_mode") == "real", price_override=args.price_model,
                                progress=progress, cc_inclusive=(setup.get("usage") or {}).get("cc") == "inclusive")
    text = core.calibration_table(rows)
    print("\n" + text)
    out = os.path.join(RUNS_DIR, "_calib", args.label, "calib.txt")
    with open(out, "w") as f:
        f.write(text + "\n")
    print("\nsaved %s (+ calib.jsonl); send me that folder's two files" % os.path.dirname(out))


# ------------------------------------------------------------------------------------------ cacheprobe
def cmd_cacheprobe(args):
    """How reliable is the gateway's prompt cache (no agent involved)?  See arena_probe.py."""
    load_setup()
    gaps = [float(x) for x in args.gaps.split(",") if x.strip()]
    runs, turns = args.grow_runs, args.grow_turns
    if args.quick:
        gaps, runs, turns = [1.0, 2.0, 5.0, 10.0, 20.0, 40.0], 1, 8
    out_dir = os.path.join(RUNS_DIR, "_cacheprobe", args.label)
    if os.path.exists(out_dir):
        core.safe_rmtree(out_dir, RUNS_DIR)
    est = (sum(gaps) + 6 * len(gaps) + runs * turns * (args.grow_gap + 6)) * len(args.protos.split(",")) / 60.0
    print("cacheprobe %s: about %.0f minutes (%d identical requests + %d x %d append-only turns per protocol)\n" % (
        args.label, est, len(gaps) + 1, runs, turns), flush=True)
    arena_probe.run(CFG_ROOT, out_dir, [p for p in args.protos.split(",") if p], args.tokens, gaps, runs, turns,
                    args.grow_gap, args.timeout, say=lambda m="": print(m, flush=True))
    print("\nsaved %s (probe.jsonl + summary.txt): send me both files" % out_dir)


# ------------------------------------------------------------------------------------------ run
def cmd_run(args):
    setup = load_setup()
    core.arena_lock(args.ws_root, "run " + args.label)
    bins = {"pi": setup["pi"]["bin"], "cc": setup["cc"]["bin"]}
    prices = core.load_prices(ARENA_DIR)
    tasks = core.select_tasks(ARENA_DIR, args.tasks)
    agents = args.agents.split(",")
    for a in agents:
        if a not in ("pi", "cc"):
            die("agents are pi and cc")
    task_defs = {t: core.load_task(ARENA_DIR, t) for t in tasks}
    if args.pi_config:
        args.pi_config = os.path.abspath(os.path.expanduser(args.pi_config))
    plan = {"tasks": tasks, "agents": agents, "reps": args.reps, "pi_thinking": args.pi_thinking,
            "cc_effort": args.cc_effort, "toolset": args.toolset, "pi_extra": args.pi_extra, "cc_extra": args.cc_extra,
            "pi_config": args.pi_config, "pi_config_sha": core.tree_digest(args.pi_config), "timeout": args.timeout,
            "order": "task-major"}
    if args.pi_config and not os.path.isdir(args.pi_config):
        die("--pi-config %s is not a directory" % args.pi_config)
    label_dir = os.path.join(RUNS_DIR, args.label)
    plan_path = os.path.join(label_dir, "plan.json")
    if os.path.exists(label_dir):
        if not args.resume:
            die("label %r already exists; use --resume to continue it or pick another label" % args.label)
        old = core.load_json(plan_path)
        if old and old != plan and not args.force:
            die("--resume with a different plan than the one stored in %s (use --force to override)" % plan_path)
    os.makedirs(label_dir, exist_ok=True)
    core.save_json(plan_path, plan)

    usage_cc = (setup.get("usage") or {}).get("cc")
    cc_inclusive = usage_cc == "inclusive"
    if "cc" in agents and not usage_cc:
        print("NOTE: run `python3 arena.py smoke` first: it checks how the gateway reports Claude Code's token usage "
              "(assuming Anthropic style until then)\n")
    elif "cc" in agents and usage_cc == "unknown":
        print("NOTE: smoke could not tell how the gateway reports Claude Code's token usage (assuming Anthropic style)\n")

    # versions: pinned in every row; changing mid-batch is flagged by the report
    real_home = setup.get("home_mode") == "real"
    probe_env = core.base_env(tmp_run_dir("version-probe"), real_home=real_home)
    versions = {"pi": core.tool_version(bins["pi"], probe_env), "cc": core.tool_version(bins["cc"], probe_env)}
    for k in ("pi", "cc"):
        if versions[k] != setup[k]["version"]:
            print("WARNING: %s is %s now, setup recorded %s" % (k, versions[k], setup[k]["version"]))

    # Task by task, and within a task the repetitions back to back with the two agents interleaved (order alternates
    # A B / B A / A B ...).  Back to back matters: a repetition of the same task a minute or two later finds the
    # gateway's cache warm, whereas with all tasks in between (rep-major order) the gap would be many minutes and
    # we would measure the cache's time-to-live instead of the harness.
    schedule, seq = [], 0
    for ti, tid in enumerate(tasks):
        for rep in range(1, args.reps + 1):
            order = agents if (rep + ti) % 2 == 1 else list(reversed(agents))
            for ag in order:
                seq += 1
                schedule.append((seq, ag, tid, rep))
    print("label %s: %d runs  agents=%s tasks=%s reps=%d  timeout=%ds" % (args.label, len(schedule), agents, tasks, args.reps, args.timeout))
    print("effort: pi --thinking %s | claude --effort %s | toolset %s | workspaces under %s\n" % (
        args.pi_thinking or "default", args.cc_effort or "default", args.toolset, args.ws_root))

    t_start, done, durations, errors, interrupted = time.time(), 0, [], 0, False
    infra_streak, infra_stop = 0, False
    stop_after_infra = getattr(args, "stop_after_infra", 0) or 0
    redo_infra = bool(getattr(args, "redo_infra", False))
    try:
        for (seq, ag, tid, rep) in schedule:
            run_id = "%03d_%s_%s_r%d" % (seq, ag, tid, rep)
            attempt = 1
            existing = [d for d in (os.listdir(label_dir) if os.path.isdir(label_dir) else [])
                        if d == run_id or d.startswith(run_id + "_a")]      # the first attempt, or a later one (_a2, _a3 ...)
            if args.resume:
                have = []                                                    # the rows of the finished attempts
                for d in existing:
                    rp = os.path.join(label_dir, d, "result.json")
                    if os.path.isfile(rp):
                        try:
                            have.append(core.load_json(rp, {}) or {})
                        except ValueError:                                   # a damaged file still counts as a finished run
                            have.append({})
                if have:
                    newest = max(have, key=lambda r: r.get("attempt", 1))
                    if redo_infra and newest.get("infra_error"):
                        attempt = newest.get("attempt", 1) + 1               # the flagged attempt stays on disk, superseded
                        print("redoing %s as attempt %d (the last one hit a gateway/infra problem)" % (run_id, attempt), flush=True)
                    else:
                        done += 1
                        continue
            opts = {"pi_thinking": args.pi_thinking, "cc_effort": args.cc_effort, "toolset": args.toolset,
                    "extra_args": shlex.split(args.pi_extra if ag == "pi" else args.cc_extra),
                    "pi_template": args.pi_config, "pi_overlay_sha": plan["pi_config_sha"], "real_home": real_home,
                    "cc_inclusive": cc_inclusive}
            row = None
            while True:
                t0 = time.time()
                try:
                    row = core.execute_run(ARENA_DIR, CFG_ROOT, args.ws_root, RUNS_DIR, args.label, seq, ag,
                                           task_defs[tid], rep, bins, opts, prices, args.timeout, attempt=attempt,
                                           keep_dirs=args.keep_dirs, allow_net=args.allow_net,
                                           price_override=args.price_model, versions=versions)
                except Exception:  # noqa
                    errors += 1
                    with open(os.path.join(label_dir, "errors.log"), "a") as ef:
                        ef.write("%s attempt %d\n%s\n" % (run_id, attempt, traceback.format_exc()))
                    print("[%2d/%d] %-3s %s r%d  RUNNER ERROR (see runs/%s/errors.log)" % (seq, len(schedule), ag, tid, rep, args.label))
                    break
                dt = time.time() - t0
                durations.append(dt)
                tok = row["tokens"]
                print("[%2d/%d] %-3s %s r%d  %-4s %5.0fs  calls %2d  tools %d/%d  prompt %7d (hit %3s)  out %6d  $%s%s" % (
                    seq, len(schedule), ag, tid, rep, "PASS" if row["pass"] else "fail", row["wall_s"], row["turns"],
                    row["tool_calls"], row["tool_errors"], tok["prompt_total"],
                    "%.0f%%" % (100 * row["cache_hit_rate"]) if row["cache_hit_rate"] is not None else "-", tok["output"],
                    "%.5f" % row["cost_usd"] if row["cost_usd"] is not None else "?",
                    "  [timeout]" if row["timed_out"] else ("  [infra: %s]" % (row["agent_error"] or "no LLM call")
                                                            if row["infra_error"] else "")), flush=True)
                if row["infra_error"] and attempt <= args.retry_infra:
                    attempt += 1
                    print("        gateway/infra problem: retrying (attempt %d) in 20s" % attempt)
                    core.nap(20)
                    continue
                break
            done += 1
            left = len(schedule) - done
            if durations and left:
                print("        ~%d min left" % round(left * (sum(durations) / len(durations)) / 60))
            infra_streak = infra_streak + 1 if (row is not None and row["infra_error"]) else 0
            if stop_after_infra and infra_streak >= stop_after_infra:
                infra_stop = True
                print("\nSTOP: %d runs in a row got no usable answer from the model (gateway down? quota used up? the agent failing to start?).\n"
                      "      Stopping here instead of burning through the remaining %d runs. Fix the cause, then run the same command again:\n"
                      "      the runs flagged I are redone (with --resume --redo-infra), everything else is kept." % (infra_streak, left), flush=True)
                break
    except KeyboardInterrupt:
        interrupted = True
        print("\ninterrupted. Continue with the same command plus --resume.")
    rows, sup = arena_report.collect_rows(RUNS_DIR, args.label)
    arena_report.write_results_jsonl(RUNS_DIR, args.label, rows)
    listing = os.listdir(label_dir)
    missing = [(sq, ag, tid, rep) for (sq, ag, tid, rep) in schedule
               if not any(d.startswith("%03d_%s_%s_r%d" % (sq, ag, tid, rep)) and
                          os.path.isfile(os.path.join(label_dir, d, "result.json")) for d in listing)]
    print("\n%d/%d runs finished in %.0f min%s. Next: python3 arena.py report --label %s" % (
        len(schedule) - len(missing), len(schedule), (time.time() - t_start) / 60,
        " (%d runner errors)" % errors if errors else "", args.label))
    if interrupted:
        sys.exit(130)
    if infra_stop:                                       # exit code 4: stopped on purpose, the gateway (or the agent start-up) is failing
        sys.exit(4)
    if missing:                                          # exit code 3: some scheduled runs have no result (runner errors)
        print("NOT FINISHED: %d runs have no result (%s). Run the same command plus --resume." % (
            len(missing), ", ".join("%03d_%s_%s_r%d" % m for m in missing[:6]) + (" ..." if len(missing) > 6 else "")))
        sys.exit(3)


# ------------------------------------------------------------------------------------------ report
def cmd_report(args):
    bands = {}
    for kv in filter(None, (args.bands or "").split(",")):
        k, v = kv.split("=")
        bands[k.strip()] = float(v)
    text, rows = arena_report.build_report(RUNS_DIR, args.label, bands)
    print(text)
    if rows:
        for lb in args.label:
            rs, _ = arena_report.collect_rows(RUNS_DIR, lb)
            arena_report.write_results_jsonl(RUNS_DIR, lb, rs)
        out = os.path.join(RUNS_DIR, args.label[0], "report.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print("\nsaved %s and %s" % (out, os.path.join(RUNS_DIR, args.label[0], "results.jsonl")))


# ------------------------------------------------------------------------------------------ suite
def suite_steps(args):
    """The steps of `suite`: [(name, argv after arena.py, rough minutes, role)]."""
    run = ["run", "--label", args.label, "--tasks", args.tasks, "--agents", args.agents, "--reps", str(args.reps),
           "--timeout", str(args.timeout), "--toolset", args.toolset, "--ws-root", os.path.abspath(args.ws_root),
           "--retry-infra", str(args.retry_infra)]
    for opt, flag in (("pi_thinking", "--pi-thinking"), ("cc_effort", "--cc-effort"), ("pi_extra", "--pi-extra"),
                      ("cc_extra", "--cc-extra"), ("price_model", "--price-model")):
        if getattr(args, opt):
            run += [flag, getattr(args, opt)]
    if args.pi_config:                                  # the steps run in arena/, so a relative path must be made absolute now
        run += ["--pi-config", os.path.abspath(os.path.expanduser(args.pi_config))]
    for opt, flag in (("force", "--force"), ("keep_dirs", "--keep-dirs"), ("allow_net", "--allow-net"), ("redo_infra", "--redo-infra")):
        if getattr(args, opt):
            run.append(flag)
    if getattr(args, "stop_after_infra", 0):
        run += ["--stop-after-infra", str(args.stop_after_infra)]
    ids = core.select_tasks(ARENA_DIR, args.tasks, say=lambda *_: None)
    per_run = sum(5.0 if core.load_task(ARENA_DIR, t).get("split") == "hard" else 1.5 for t in ids)   # minutes per run, rough
    minutes = max(5, round(per_run * len(args.agents.split(",")) * args.reps))
    return [("tasks", ["tasks", "--check", "--tasks", args.tasks], 3, "base"),
            ("run", run, minutes, "agents"),
            ("report", ["report", "--label", args.label], 1, "agents")]


def cmd_suite(args):
    if not os.path.isfile(os.path.join(CFG_ROOT, "setup.json")):
        die("no configs/setup.json yet: run `python3 arena.py day1` first (it sets everything up and checks the agents)")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.label):
        die("--label may only contain letters, digits, '_', '.' and '-'")
    sys.exit(arena_day1.main(ARENA_DIR, args, steps=suite_steps(args), session="suite/" + args.label, labels={args.label}))


# ------------------------------------------------------------------------------------------ day1 / pack
def cmd_day1(args):
    sys.exit(arena_day1.main(ARENA_DIR, args))


def cmd_pack(args):
    txt, tgz, n = arena_day1.pack_results(ARENA_DIR, labels=set(args.label or []) or None)
    arena_day1.announce(ARENA_DIR, txt, tgz, n)


# ------------------------------------------------------------------------------------------ selftest
def cmd_selftest(args):
    import arena_selftest
    sys.exit(arena_selftest.run(ARENA_DIR, keep=args.keep))


# ------------------------------------------------------------------------------------------ main
def add_run_options(p, suite=False):
    """The options of `run`, which `suite` shares (there --label and --tasks have defaults)."""
    if suite:
        p.add_argument("--label", default="suite1", help="name of this batch (default suite1); a new name for every experiment")
        p.add_argument("--tasks", default="dev", help="comma list, or all / dev (default: the tasks to iterate on) / held (held-out: look rarely) / hard (harder tasks, a separate group)")
    else:
        p.add_argument("--label", required=True)
        p.add_argument("--tasks", default="all", help="comma list, or all / dev (the tasks to iterate on) / held (held-out: look rarely) / hard (harder tasks, a separate group)")
    p.add_argument("--agents", default="pi,cc")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--pi-thinking", help="pi --thinking level (off|minimal|low|medium|high|xhigh|max); default: pi's own default")
    p.add_argument("--cc-effort", help="claude --effort level (low|medium|high|xhigh|max); default: Claude Code's own default")
    p.add_argument("--toolset", choices=["default", "aligned"], default="default",
                   help="default: each agent's own tools (Claude Code minus web tools); aligned: read/bash/edit/write only")
    p.add_argument("--timeout", type=int, default=900, help="wall-clock limit per run, seconds")
    p.add_argument("--ws-root", default=DEFAULT_WS_ROOT, help="where task workspaces are created (default /tmp/arena-ws)")
    p.add_argument("--pi-config", help="a pi VARIANT: a directory layered on top of the blank baseline configs/pi "
                                       "(settings.json merged key by key; AGENTS.md, extensions/, ... added)")
    p.add_argument("--pi-extra", default="", help="extra pi arguments, e.g. '-e /path/ext.ts'")
    p.add_argument("--cc-extra", default="", help="extra claude arguments")
    p.add_argument("--price-model", help="force this key of prices.json for every row")
    p.add_argument("--retry-infra", type=int, default=1, help="re-run a run that hit a gateway problem (default 1)")
    p.add_argument("--stop-after-infra", type=int, default=0, metavar="N",
                   help="stop the batch (exit code 4) when N runs in a row hit a gateway/infra problem, e.g. the gateway is down; default 0: never")
    p.add_argument("--redo-infra", action="store_true",
                   help="with --resume: also redo the runs whose newest attempt hit a gateway/infra problem (flag I); the old attempt stays on disk, superseded")
    p.add_argument("--force", action="store_true")
    p.add_argument("--keep-dirs", action="store_true", help="keep each run's HOME / config dir (large)")
    p.add_argument("--allow-net", action="store_true", help="do not blackhole the proxy variables")


def build_parser():
    ap = argparse.ArgumentParser(prog="arena.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("day1", help="setup, selftest, smoke, cacheprobe, calib, pilot, report in one resumable command, then pack")
    p.add_argument("--quick", action="store_true", help="roughly half the time: short cacheprobe, 1 calibration rep, 3 pilot reps")
    p.add_argument("--pilot-reps", type=int, help="repetitions of the pilot (default 5, or 3 with --quick)")
    p.add_argument("--skip", default="", help="comma list of steps to leave out (setup,selftest,smoke,cacheprobe,calib,pilot,report)")
    p.add_argument("--only", default="", help="run only these steps")
    p.add_argument("--redo", default="", help="run these steps again even if they are done")
    p.set_defaults(fn=cmd_day1)

    p = sub.add_parser("pack", help="bundle summaries, reports and result rows into ONE text file (+ a .tgz) to send back")
    p.add_argument("--label", action="append", help="only these run labels (default: all); smoke/calib/cacheprobe are always included")
    p.set_defaults(fn=cmd_pack)

    p = sub.add_parser("setup", help="write blank arena configs from your gateway config")
    p.add_argument("--pi-models", help="path of your pi models.json (default ~/.pi/agent/models.json)")
    p.add_argument("--pi-provider", help="provider name in models.json (default: magpie)")
    p.add_argument("--pi-model", help="model id in that provider (default: the entry with the same id as Claude Code's model)")
    p.add_argument("--cc-settings", help="Claude Code settings.json holding the gateway env (default ~/.claude/settings.json)")
    p.add_argument("--cc-model", help="override ANTHROPIC_MODEL for Claude Code")
    p.add_argument("--pi-bin")
    p.add_argument("--cc-bin")
    p.set_defaults(fn=cmd_setup)

    p = sub.add_parser("selftest", help="end-to-end test with a mock gateway (free)")
    p.add_argument("--keep", action="store_true", help="keep the temporary directory")
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser("smoke", help="a few tiny identical requests per agent through your real gateway")
    p.add_argument("--agents", default="pi,cc")
    p.add_argument("--repeat", type=int, default=3, help="identical requests per agent (the later ones show cache behaviour)")
    p.add_argument("--gap", type=float, default=4.0, help="seconds between them")
    p.add_argument("--pi-thinking")
    p.add_argument("--cc-effort")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--ws-root", default=DEFAULT_WS_ROOT)
    p.set_defaults(fn=cmd_smoke)

    p = sub.add_parser("calib", help="effort calibration: same short question at every effort level of both agents")
    p.add_argument("--label", default="calib1")
    p.add_argument("--agents", default="pi,cc")
    p.add_argument("--pi-levels", default="off,low,medium,high,xhigh")
    p.add_argument("--cc-levels", default="low,medium,high,xhigh,max")
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--ws-root", default=DEFAULT_WS_ROOT)
    p.add_argument("--price-model")
    p.set_defaults(fn=cmd_calib)

    p = sub.add_parser("cacheprobe", help="how reliable is the gateway's prompt cache? (no agent involved)")
    p.add_argument("--label", default="probe1")
    p.add_argument("--protos", default="openai,anthropic", help="openai = what pi uses, anthropic = what Claude Code uses")
    p.add_argument("--tokens", type=int, default=8000, help="size of the shared prefix in tokens (approximate)")
    p.add_argument("--gaps", default="1,1,2,2,5,5,10,10,20,20,40,40,80,80,160", help="seconds between the identical requests")
    p.add_argument("--grow-runs", type=int, default=3, help="append-only conversations")
    p.add_argument("--grow-turns", type=int, default=12)
    p.add_argument("--grow-gap", type=float, default=3.0, help="seconds between turns")
    p.add_argument("--quick", action="store_true", help="about 4 minutes instead of about 25")
    p.add_argument("--timeout", type=int, default=180)
    p.set_defaults(fn=cmd_cacheprobe)

    p = sub.add_parser("tasks", help="list tasks; --check verifies them")
    p.add_argument("--check", action="store_true")
    p.add_argument("--tasks", default="all", help="with --check: which tasks (all / dev / held / hard / comma list)")
    p.add_argument("--write-ref", action="store_true", help="store the reference diff size in task.json")
    p.set_defaults(fn=cmd_tasks)

    p = sub.add_parser("prices", help="show the price table")
    p.set_defaults(fn=cmd_prices)

    p = sub.add_parser("run", help="run tasks")
    add_run_options(p)
    p.add_argument("--resume", action="store_true")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("suite", help="the task suite in one resumable command: check tasks, run, report, then pack ONE file to send back")
    add_run_options(p, suite=True)
    p.add_argument("--no-pack", action="store_true", help="do not write the results files at the end (a script that runs several batches packs them itself with `pack`)")
    p.add_argument("--skip", default="", help="comma list of steps to leave out (tasks,run,report)")
    p.add_argument("--only", default="", help="run only these steps")
    p.add_argument("--redo", default="", help="run these steps again even if they are done (the batch itself continues: delete runs/<label> for a fresh one)")
    p.set_defaults(fn=cmd_suite)

    p = sub.add_parser("report", help="tables and provisional W/T/L")
    p.add_argument("--label", action="append", required=True)
    p.add_argument("--bands", help="tie-band overrides, e.g. cost=0.2,wall=0.3")
    p.set_defaults(fn=cmd_report)
    return ap


def main():
    args = build_parser().parse_args()
    for name in ("SIGTERM", "SIGHUP"):            # `kill`, or a closed terminal, end like Ctrl-C: agents are stopped, state is saved
        try:
            signal.signal(getattr(signal, name), _as_interrupt)
        except (AttributeError, ValueError, OSError):
            pass
    args.fn(args)


def _as_interrupt(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    main()
