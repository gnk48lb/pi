"""Read result.json files, print per-run / per-task tables, noise statistics and a provisional W/T/L scoreboard.

Everything here is derived from the result rows; nothing is measured again.  The W/T/L board compares the
*median over repetitions* of each metric per task, pi against Claude Code, with a tie band so that noise is not
reported as a win.  Default tie bands are guesses until the noise table (CV) says otherwise.

An *arm* is one configuration of one agent.  Normally that is just "pi" and "cc".  When several labels hold
different configurations of the same agent (a pi variant next to the pi baseline), the arms are named
"pi@<label>", and the report also compares every later arm with the first one of its agent (variant vs baseline).

Cache metrics.  The cache *hit rate* is only a diagnostic (it depends on how big the prompt is: a small prompt
that grows by the same number of new tokens per call always looks worse).  What is compared is the number of
input tokens that were NOT served from the cache ("fresh"), split in two because they have different causes:
  * the first request of a run: a *cold start* (hit < 50%) pays for the whole prompt, a warm start almost nothing;
  * everything after the first request: the new tokens each call adds (tool results, the assistant's own
    message) plus the uncached tail the gateway leaves behind.
Cold runs are flagged K and are left out of the noise table (one cold run in five would otherwise dominate the CV)."""
import json
import os
import statistics as st

AGENT_NAMES = {"pi": "pi", "cc": "claude"}
COLD_HIT = 0.5            # first-request hit rate below this = the run started with a cold cache


# ------------------------------------------------------------------------------------------ derived numbers
def fresh_total(r):
    """Input tokens not served from the cache, whole run (input + cache_write, whichever way the agent reports it)."""
    if r.get("usage_missing"):
        return None
    t = r["tokens"]
    return t["prompt_total"] - t["cache_read"]


def first_fresh(r):
    fr = r.get("first_req") or {}
    if r.get("usage_missing") or not fr.get("prompt_total"):
        return None
    return fr["prompt_total"] - (fr.get("cache_read") or 0)


def fresh_rest(r):
    a, b = fresh_total(r), first_fresh(r)
    return None if a is None or b is None else a - b


def is_cold(r):
    h = (r.get("first_req") or {}).get("hit_rate")
    return h is not None and h < COLD_HIT


def worst(xs):
    xs = [x for x in xs if x is not None]
    return max(xs) if xs else None


class Metric:
    """key, label, extractor(row) -> number|None, better ('low'|'high'), tie band (kind, value), format.
    short: the column heading on the per-task board.  agg: how the repetitions of one (task, arm) are combined for
    the W/T/L board ('median' unless stated).  noisy: whether the noise table (CV across repetitions) makes sense."""
    def __init__(self, key, label, short, ex, better, tie, spec, agg=None, noisy=True):
        self.key, self.label, self.short, self.ex, self.better, self.tie, self.spec = key, label, short, ex, better, tie, spec
        self.agg, self.noisy = agg, noisy

    def combine(self, rows):
        xs = [self.ex(r) for r in rows]
        return (self.agg or median)(xs)


METRICS = [
    Metric("pass", "pass rate", "pass", lambda r: 1.0 if r["pass"] else 0.0, "high", ("runs", 1), "{:.0%}"),
    Metric("cost", "cost (USD)", "cost $", lambda r: r.get("cost_usd"), "low", ("rel", 0.15), "{:.5f}"),
    Metric("fresh", "uncached input tokens after the 1st request", "rest unc", fresh_rest, "low", ("rel", 0.20), "{:.0f}"),
    Metric("cold", "1st-request uncached tokens (worst run)", "cold 1st unc", first_fresh, "low", ("rel", 0.10), "{:.0f}",
           agg=worst, noisy=False),
    Metric("first", "first-request prompt tokens", "1st prompt",
           lambda r: (r.get("first_req") or {}).get("prompt_total"), "low", ("rel", 0.05), "{:.0f}"),
    Metric("prompt", "total prompt tokens", "all prompt", lambda r: r["tokens"]["prompt_total"], "low", ("rel", 0.15), "{:.0f}"),
    Metric("out", "output tokens", "out tok", lambda r: r["tokens"]["output"], "low", ("rel", 0.20), "{:.0f}"),
    Metric("turns", "LLM calls", "calls", lambda r: r.get("turns"), "low", ("rel", 0.15), "{:.1f}"),
    Metric("wall", "wall seconds", "wall s", lambda r: r.get("wall_s"), "low", ("rel", 0.20), "{:.1f}"),
    Metric("toolerr", "tool error rate", "tool err",
           lambda r: (r["tool_errors"] / r["tool_calls"]) if r.get("tool_calls") else 0.0, "low", ("abs", 0.05), "{:.1%}",
           noisy=False),
    Metric("minimal", "minimality (diff / reference diff)", "diff/ref", lambda r: r.get("minimality"), "low", ("rel", 0.20), "{:.2f}"),
    Metric("hang", "timeout rate", "timeout", lambda r: 1.0 if r.get("timed_out") else 0.0, "low", ("abs", 0.0), "{:.0%}"),
]


# ------------------------------------------------------------------------------------------ loading
def collect_rows(runs_dir, label):
    """All result.json under runs/<label>/, newest attempt per (agent, task, rep) wins; earlier ones are counted."""
    base = os.path.join(runs_dir, label)
    rows = []
    if not os.path.isdir(base):
        return [], 0
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d, "result.json")
        if os.path.isfile(p):
            try:
                rows.append(json.load(open(p, encoding="utf-8")))
            except Exception:  # noqa
                pass
    best = {}
    for r in rows:
        k = (r["agent"], r["task"], r["rep"])
        if k not in best or r.get("attempt", 1) > best[k].get("attempt", 1):
            best[k] = r
    superseded = len(rows) - len(best)
    return sorted(best.values(), key=lambda r: r["seq"]), superseded


def write_results_jsonl(runs_dir, label, rows):
    p = os.path.join(runs_dir, label, "results.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def assign_arms(rows):
    """Set r["arm"] on every row (see the module docstring).  Returns the arms in first-seen order."""
    by_agent = {}
    for r in rows:
        key = json.dumps([r.get("effort"), r.get("toolset"), r.get("variant")], sort_keys=True)
        labels = by_agent.setdefault(r["agent"], {}).setdefault(key, [])
        if r["label"] not in labels:
            labels.append(r["label"])
    arms = []
    for r in rows:
        key = json.dumps([r.get("effort"), r.get("toolset"), r.get("variant")], sort_keys=True)
        cfgs = by_agent[r["agent"]]
        r["arm"] = r["agent"] if len(cfgs) == 1 else "%s@%s" % (r["agent"], "+".join(cfgs[key]))
        if r["arm"] not in arms:
            arms.append(r["arm"])
    return arms


def arm_label(arm):
    agent, _, rest = arm.partition("@")
    return AGENT_NAMES.get(agent, agent) + (("@" + rest) if rest else "")


# ------------------------------------------------------------------------------------------ formatting
def table(headers, rows, align=None):
    cols = len(headers)
    align = align or ["l"] + ["r"] * (cols - 1)
    cells = [[str(h) for h in headers]] + [[("" if v is None else str(v)) for v in r] for r in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(cols)]

    def fmt(r):
        return "  ".join((r[i].ljust(widths[i]) if align[i] == "l" else r[i].rjust(widths[i])) for i in range(cols)).rstrip()
    out = [fmt(cells[0]), "  ".join("-" * w for w in widths)]
    out += [fmt(r) for r in cells[1:]]
    return out


def f(v, spec):
    return "-" if v is None else spec.format(v)


def median(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def cv(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 3:
        return None
    m = st.mean(xs)
    return (st.stdev(xs) / abs(m)) if m else None


# ------------------------------------------------------------------------------------------ sections
def checks_share(r):
    """Share of the verifier's test cases that passed (1.0 = all), None when the verifier output could not be counted.
    Gives a graded score for tasks that nobody solves completely."""
    ran, failed = r.get("tests_ran"), r.get("tests_failed")
    if not ran:
        return None
    return max(0.0, 1.0 - (failed or 0) / ran)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def guard_lines(rows, with_label=False):
    """Safety-gate blocks and budget-guard events per arm, plus the blocked commands themselves."""
    arms = []
    for r in rows:
        if r["arm"] not in arms:
            arms.append(r["arm"])
    out = []
    for arm in arms:
        rs = [r for r in rows if r["arm"] == arm]
        gs = [r.get("guard") or {} for r in rs]
        out.append([arm_label(arm), len(rs), sum(1 for g in gs if g.get("gate_blocks")), sum(g.get("gate_blocks", 0) for g in gs),
                    sum(g.get("fid_blocks", 0) for g in gs),
                    sum(g.get("budget_soft", 0) for g in gs), sum(g.get("budget_hard", 0) for g in gs)])
    lines = table(["arm", "runs", "runs with a block", "gate blocks", "of them fidelity", "budget soft", "budget hard"], out,
                  ["l", "r", "r", "r", "r", "r", "r"])
    ex = []
    for r in rows:
        for e in (r.get("guard") or {}).get("gate_examples", []):
            ex.append("%s%s: %s" % (r["label"] + "/" if with_label else "", r["run_id"], e))
    if ex:
        lines.append("")
        lines.append("blocked (first 5 per run, at most 40 in all):")
        lines += ex[:40]
        if len(ex) > 40:
            lines.append("... and %d more" % (len(ex) - 40))
    return lines


def result_cell(r):
    """PASS, or fail with the number of failing tests when the verifier output could be counted ("fail 1/29")."""
    if r["pass"]:
        return "PASS"
    ran, failed = r.get("tests_ran"), r.get("tests_failed")
    return "fail %d/%d" % (failed, ran) if ran and failed else "fail"


def run_table(rows, with_label=False):
    out = []
    for r in rows:
        flags = "".join(c for c, on in (("T", r.get("timed_out")), ("I", r.get("infra_error")),
                                        ("X", bool(r.get("tampered"))), ("E", bool(r.get("agent_error")) and not r.get("infra_error")),
                                        ("C", bool(r.get("cliffs"))), ("K", is_cold(r)),
                                        ("G", bool((r.get("guard") or {}).get("gate_blocks"))),
                                        ("B", bool((r.get("guard") or {}).get("budget_soft") or (r.get("guard") or {}).get("budget_hard")))) if on)
        fr = r.get("first_req") or {}
        out.append([(r["label"] + "/" if with_label else "") + r["run_id"], result_cell(r), f(r["wall_s"], "{:.0f}s"), r["turns"],
                    "%d/%d" % (r["tool_calls"], r["tool_errors"]), r["tokens"]["prompt_total"],
                    f(first_fresh(r), "{:.0f}"), f(fresh_rest(r), "{:.0f}"),
                    f(r.get("cache_hit_rate"), "{:.0%}"), f(fr.get("hit_rate"), "{:.0%}"), r["tokens"]["output"],
                    f(r.get("cost_usd"), "{:.5f}"), f(r.get("minimality"), "{:.2f}"), flags])
    return table(["run", "result", "wall", "calls", "tools/err", "prompt tok", "1st unc", "rest unc", "hit", "1st hit",
                  "out tok", "cost $", "diff/ref", "flags"], out,
                 ["l", "l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r", "l"])


def failure_lines(rows, with_label=False, limit=60):
    """One line per failing run: what the verifier said (fail reason and its ARENA_NOTE lines)."""
    out = []
    for r in rows:
        if r["pass"]:
            continue
        bits = [r.get("fail_reason") or "failed"] + [str(n) for n in (r.get("verify_notes") or [])]
        out.append("%s%s: %s" % (r["label"] + "/" if with_label else "", r["run_id"], " | ".join(bits)))
    if len(out) > limit:
        out = out[:limit] + ["... and %d more" % (len(out) - limit)]
    return out


def groups_of(rows):
    groups = {}
    for r in rows:
        groups.setdefault((r["task"], r["arm"]), []).append(r)
    return groups


def group_table(rows):
    out = []
    for (task, arm), rs in sorted(groups_of(rows).items()):
        n = len(rs)
        npass = sum(1 for r in rs if r["pass"])
        out.append([task, arm_label(arm), n, "%d/%d" % (npass, n),
                    f(median([r["wall_s"] for r in rs]), "{:.0f}s"), f(median([r["turns"] for r in rs]), "{:.0f}"),
                    f(median([r["tokens"]["prompt_total"] for r in rs]), "{:.0f}"),
                    f(median([(r.get("first_req") or {}).get("prompt_total") for r in rs]), "{:.0f}"),
                    f(worst([first_fresh(r) for r in rs]), "{:.0f}"),
                    f(median([fresh_rest(r) for r in rs]), "{:.0f}"),
                    f(median([r.get("cache_hit_rate") for r in rs]), "{:.0%}"),
                    f(median([r["tokens"]["output"] for r in rs]), "{:.0f}"),
                    f(median([r.get("cost_usd") for r in rs]), "{:.5f}"),
                    f(median([r.get("minimality") for r in rs]), "{:.2f}"),
                    f(mean([checks_share(r) for r in rs]), "{:.2f}")])
    return table(["task", "agent", "n", "pass", "wall", "calls", "prompt tok", "1st req tok", "cold 1st unc", "rest unc",
                  "hit", "out tok", "cost $", "diff/ref", "checks"], out,
                 ["l", "l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r"])


def warmth_table(rows):
    """How often did a run start cold, and what did that cost in uncached input tokens?"""
    out, bad = [], []
    for (task, arm), rs in sorted(groups_of(rows).items()):
        cold = [r for r in rs if is_cold(r)]
        warm = [r for r in rs if r.get("first_req") and not is_cold(r)]
        later = [r for r in rs[1:] if is_cold(r)]               # a cold start after the group's first run
        out.append([task, arm_label(arm), len(rs), len(cold),
                    f(median([first_fresh(r) for r in cold]), "{:.0f}"), f(median([first_fresh(r) for r in warm]), "{:.0f}"),
                    f(median([(r.get("first_req") or {}).get("hit_rate") for r in rs]), "{:.0%}")])
        if len(rs) >= 3 and len(later) >= max(2, (len(rs) - 1) * 3 // 4):
            bad.append("%s %s" % (task, arm_label(arm)))
    return table(["task", "agent", "runs", "cold", "cold: 1st unc tok", "warm: 1st unc tok", "median 1st hit"], out,
                 ["l", "l", "r", "r", "r", "r", "r"]), bad


def noise_table(rows):
    """Coefficient of variation across repetitions, per metric; the median over (task, agent) groups.
    Cold-start runs (flag K) are left out: one cold run in five would otherwise dominate every token metric."""
    groups = {}
    for key, rs in groups_of(rows).items():
        groups[key] = [r for r in rs if not is_cold(r)]
    out, advice = [], {}
    for m in METRICS:
        if m.key in ("pass", "hang") or not m.noisy:
            continue
        kind, band = m.tie
        cvs = [cv([m.ex(r) for r in rs]) for rs in groups.values()]
        cvs = [c for c in cvs if c is not None]
        if not cvs:
            continue
        med, mx = st.median(cvs), max(cvs)
        out.append([m.label, len(cvs), "%.0f%%" % (100 * med), "%.0f%%" % (100 * mx),
                    ("%.0f%%" % (100 * band)) if kind == "rel" else "-"])
        if kind == "rel":
            advice[m.key] = max(band, round(1.5 * med, 2))
    lines = table(["metric", "groups", "median CV", "max CV", "default tie band"], out, ["l", "r", "r", "r", "r"])
    return lines, advice


def tie(kind, band, a, b, n_runs):
    if kind == "rel":
        scale = max(abs(a), abs(b))
        return scale == 0 or abs(a - b) / scale <= band
    if kind == "runs":                       # pass rate: within `band` runs
        return abs(a - b) <= band / max(1, n_runs) + 1e-9
    return abs(a - b) <= band + 1e-12


def wtl_table(rows, arm_a, arm_b, bands=None):
    """Per task, per metric: arm A vs arm B on the median over repetitions.  W = A better beyond the tie band."""
    tasks = sorted({r["task"] for r in rows})
    by = {}
    for r in rows:
        by.setdefault((r["task"], r["arm"]), []).append(r)
    totals = {m.key: [0, 0, 0] for m in METRICS}
    detail = []
    for task in tasks:
        a_rows, b_rows = by.get((task, arm_a)), by.get((task, arm_b))
        if not a_rows or not b_rows:
            continue
        n_runs = min(len(a_rows), len(b_rows))
        line = [task]
        for m in METRICS:
            kind, band = m.tie
            band = (bands or {}).get(m.key, band)
            if m.key == "pass":
                a = sum(1 for r in a_rows if r["pass"]) / len(a_rows)
                b = sum(1 for r in b_rows if r["pass"]) / len(b_rows)
            else:
                a, b = m.combine(a_rows), m.combine(b_rows)
            if a is None or b is None:
                line.append("n/a")
                continue
            if tie(kind, band, a, b, n_runs):
                res, idx = "T", 1
            else:
                a_better = (a < b) if m.better == "low" else (a > b)
                res, idx = ("W", 0) if a_better else ("L", 2)
            totals[m.key][idx] += 1
            line.append("%s %s/%s" % (res, m.spec.format(a), m.spec.format(b)))
        detail.append(line)
    head = ["task"] + [m.short for m in METRICS]
    lines = table(head, detail, ["l"] + ["l"] * len(METRICS)) if detail else ["(need both arms on a task)"]
    summary = [[m.label, *totals[m.key], ("lower" if m.better == "low" else "higher") + " is better"
                + (" (worst run, not the median)" if m.agg is worst else "")] for m in METRICS]
    return lines, table(["metric", "W", "T", "L", ""], summary, ["l", "r", "r", "r", "l"]), totals


# ------------------------------------------------------------------------------------------ report
def build_report(runs_dir, labels, bands=None):
    rows, superseded = [], 0
    for lb in labels:
        rs, sup = collect_rows(runs_dir, lb)
        rows += rs
        superseded += sup
    if not rows:
        return "no results found for label(s): %s" % ", ".join(labels), []
    arms = assign_arms(rows)
    L = []
    add = L.append
    add("ARENA REPORT  labels=%s  runs=%d  (re-run attempts superseded: %d)" % (",".join(labels), len(rows), superseded))
    if len(arms) > 2 or len(labels) > 1:
        add("arms     : " + ", ".join(arm_label(a) for a in arms))
    vers = sorted({"%s %s" % (AGENT_NAMES.get(r["agent"], r["agent"]), r.get("agent_version")) for r in rows})
    models = sorted({"%s=%s" % (r["agent"], r.get("model")) for r in rows})
    efforts = sorted({"%s" % r.get("effort") for r in rows})
    tools = sorted({"%s toolset=%s tools_exposed=%s" % (r["agent"], r.get("toolset"), r.get("n_tools_exposed")) for r in rows})
    add("versions : " + "; ".join(vers))
    add("models   : " + "; ".join(models))
    add("effort   : " + "; ".join(efforts))
    add("toolsets : " + "; ".join(tools))
    variants = sorted({"%s overlay=%s extra=%s" % (r["agent"], (r.get("variant") or {}).get("pi_overlay_sha") or "none",
                                                   " ".join((r.get("variant") or {}).get("extra_args") or []) or "none")
                       for r in rows})
    add("variants : " + "; ".join(variants))
    usage = sorted({r.get("usage_semantics") for r in rows if r["agent"] == "cc" and r.get("usage_semantics")})
    if usage:
        add("usage    : claude input_tokens read as %s (see `smoke`); pi normalises its own usage" % "/".join(usage))
    add("prices   : " + ", ".join(sorted({str(r.get("price_model")) for r in rows})) + "  (cost recomputed from tokens with prices.json)")
    warn = []
    if len({r.get("agent_version") for r in rows if r["agent"] == "cc"}) > 1 or len({r.get("agent_version") for r in rows if r["agent"] == "pi"}) > 1:
        warn.append("agent version changed during the batch")
    if any(r.get("price_model") in (None, "None") for r in rows):
        warn.append("some rows have no price entry: cost is missing for them")
    if any(r.get("usage_missing") for r in rows):
        warn.append("some runs have LLM calls without usage numbers: first-request tokens and cache-cliff columns are "
                    "unreliable for them (totals come from the agent's final summary)")
    if any(r.get("infra_error") for r in rows):
        warn.append("rows flagged I (gateway/infra error) are still in the tables below; re-run them or drop them")
    add("")
    add("flags: T timeout, I infra error, X protected test file modified, E agent error, C cache cliff, "
        "K cold start (1st-request hit < %d%%), G a gate (safety / fidelity) blocked a tool call, B budget-guard fired" % round(100 * COLD_HIT))
    add("unc = input tokens NOT served from the cache: '1st unc' on the first request, 'rest unc' on all later ones")
    add("")
    add("== runs ==")
    L += run_table(rows, with_label=len(labels) > 1)
    add("")
    add("== per task x agent (median over repetitions; 'cold 1st unc' is the worst run) ==")
    L += group_table(rows)
    fails = failure_lines(rows, with_label=len(labels) > 1)
    if fails:
        add("")
        add("== failing runs: why (verifier notes) ==")
        L += fails
    if any((r.get("guard") or {}).get("gate_blocks") or (r.get("guard") or {}).get("budget_soft") or
           (r.get("guard") or {}).get("budget_hard") or (r.get("variant") or {}).get("pi_overlay_sha") for r in rows):
        add("")
        add("== guard extensions: gate blocks (safety-gate, fidelity-gate) and budget-guard events (from stderr, non-interactive mode) ==")
        L += guard_lines(rows, with_label=len(labels) > 1)
    add("")
    add("== cache warmth: did the run start cold, and what did that cost? ==")
    wl, unstable = warmth_table(rows)
    L += wl
    if unstable:
        warn.append("almost every repeat after the first started cold for: %s. The prompt prefix is not stable between "
                    "runs (something early in the system prompt or tool list changes), which is a cache regression." %
                    ", ".join(unstable))
    add("")
    n_cold = sum(1 for r in rows if is_cold(r))
    add("== noise: coefficient of variation across repetitions (%d cold-start run(s) left out) ==" % n_cold)
    nl, advice = noise_table(rows)
    L += nl
    if advice:
        add("suggested tie bands (1.5 x median CV, never below the default): " +
            ", ".join("%s=%d%%" % (k, round(100 * v)) for k, v in sorted(advice.items())))
    add("")
    pairs = []                                                    # (challenger, reference, title)
    pis, ccs = [a for a in arms if a.split("@")[0] == "pi"], [a for a in arms if a.split("@")[0] == "cc"]
    for a in pis:
        for b in ccs:
            pairs.append((a, b, "pi vs claude" if len(arms) == 2 else "%s vs %s" % (arm_label(a), arm_label(b))))
    for group in (pis, ccs):                                      # variant vs baseline of the same agent
        for a in group[1:]:
            pairs.append((a, group[0], "variant %s vs baseline %s" % (arm_label(a), arm_label(group[0]))))
    if not pairs:
        add("== provisional comparison ==")
        add("(need both agents, or a variant next to its baseline)")
        add("")
    for a, b, title in pairs:
        add("== provisional %s, per task (W/T/L from the first one's side; band = tie) ==" % title)
        dl, sl, totals = wtl_table(rows, a, b, bands)
        L += dl
        add("")
        L += sl
        add("")
    n_tasks = len({r["task"] for r in rows})
    min_reps = min(len(rs) for rs in groups_of(rows).values())
    add("note: %d task(s), at least %d run(s) per task and arm.  The board compares medians, and a gap inside the tie band "
        "is a tie." % (n_tasks, min_reps))
    if n_tasks < 8 or min_reps < 3:
        add("      With fewer than 8 tasks or fewer than 3 repetitions this is a rehearsal of the machinery, not a verdict "
            "(3+ repetitions also keep the median clear of the one cold start per task).")
    cliff_runs = [r for r in rows if r.get("cliffs")]
    if cliff_runs:
        add("")
        add("== cache cliffs (call index, tokens that should have been cache hits but were not) ==")
        for r in cliff_runs:
            add("%s: %s" % (r["run_id"], ", ".join("call %d lost %d" % (c["call"], c["lost"]) for c in r["cliffs"])))
    if warn:
        add("")
        for w in warn:
            add("WARNING: " + w)
    return "\n".join(L), rows
