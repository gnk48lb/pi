"""Read result.json files, print per-run / per-task tables, noise statistics and a provisional W/T/L scoreboard.

Everything here is derived from the result rows; nothing is measured again.  The W/T/L board compares the
*median over repetitions* of each metric per task, pi against Claude Code, with a tie band so that noise is not
reported as a win.  Default tie bands are guesses until the pilot's noise table (CV) says otherwise.

An *arm* is one configuration of one agent.  Normally that is just "pi" and "cc".  When several labels hold
different configurations of the same agent (a pi variant next to the pi baseline), the arms are named
"pi@<label>", and the report also compares every later arm with the first one of its agent (variant vs baseline)."""
import json
import os
import statistics as st

AGENT_NAMES = {"pi": "pi", "cc": "claude"}

# key, label, extractor(row) -> number|None, better ('low'|'high'), tie band (kind, value), format
METRICS = [
    ("pass", "pass rate", lambda r: 1.0 if r["pass"] else 0.0, "high", ("runs", 1), "{:.0%}"),
    ("cost", "cost (USD)", lambda r: r.get("cost_usd"), "low", ("rel", 0.15), "{:.5f}"),
    ("cache", "cache hit rate", lambda r: r.get("cache_hit_rate"), "high", ("abs", 0.02), "{:.1%}"),
    ("first", "first-request prompt tokens",
     lambda r: (r.get("first_req") or {}).get("prompt_total"), "low", ("rel", 0.05), "{:.0f}"),
    ("prompt", "total prompt tokens", lambda r: r["tokens"]["prompt_total"], "low", ("rel", 0.15), "{:.0f}"),
    ("out", "output tokens", lambda r: r["tokens"]["output"], "low", ("rel", 0.20), "{:.0f}"),
    ("turns", "LLM calls", lambda r: r.get("turns"), "low", ("rel", 0.15), "{:.1f}"),
    ("wall", "wall seconds", lambda r: r.get("wall_s"), "low", ("rel", 0.20), "{:.1f}"),
    ("toolerr", "tool error rate",
     lambda r: (r["tool_errors"] / r["tool_calls"]) if r.get("tool_calls") else 0.0, "low", ("abs", 0.05), "{:.1%}"),
    ("minimal", "minimality (diff / reference diff)", lambda r: r.get("minimality"), "low", ("rel", 0.20), "{:.2f}"),
    ("hang", "timeout rate", lambda r: 1.0 if r.get("timed_out") else 0.0, "low", ("abs", 0.0), "{:.0%}"),
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
def run_table(rows, with_label=False):
    out = []
    for r in rows:
        flags = "".join(c for c, on in (("T", r.get("timed_out")), ("I", r.get("infra_error")),
                                        ("X", bool(r.get("tampered"))), ("E", bool(r.get("agent_error")) and not r.get("infra_error")),
                                        ("C", bool(r.get("cliffs")))) if on)
        fr = r.get("first_req") or {}
        out.append([(r["label"] + "/" if with_label else "") + r["run_id"], "PASS" if r["pass"] else "fail", f(r["wall_s"], "{:.0f}s"), r["turns"],
                    "%d/%d" % (r["tool_calls"], r["tool_errors"]), r["tokens"]["prompt_total"],
                    f(r.get("cache_hit_rate"), "{:.0%}"), f(fr.get("hit_rate"), "{:.0%}"), r["tokens"]["output"],
                    f(r.get("cost_usd"), "{:.5f}"), f(r.get("minimality"), "{:.2f}"), flags])
    return table(["run", "result", "wall", "calls", "tools/err", "prompt tok", "hit", "1st hit", "out tok", "cost $",
                  "diff/ref", "flags"], out, ["l", "l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "l"])


def group_table(rows):
    groups = {}
    for r in rows:
        groups.setdefault((r["task"], r["arm"]), []).append(r)
    out = []
    for (task, arm), rs in sorted(groups.items()):
        n = len(rs)
        npass = sum(1 for r in rs if r["pass"])
        out.append([task, arm_label(arm), n, "%d/%d" % (npass, n),
                    f(median([r["wall_s"] for r in rs]), "{:.0f}s"), f(median([r["turns"] for r in rs]), "{:.0f}"),
                    f(median([r["tokens"]["prompt_total"] for r in rs]), "{:.0f}"),
                    f(median([(r.get("first_req") or {}).get("prompt_total") for r in rs]), "{:.0f}"),
                    f(median([r.get("cache_hit_rate") for r in rs]), "{:.0%}"),
                    f(median([r["tokens"]["output"] for r in rs]), "{:.0f}"),
                    f(median([r.get("cost_usd") for r in rs]), "{:.5f}"),
                    f(median([r.get("minimality") for r in rs]), "{:.2f}")])
    return table(["task", "agent", "n", "pass", "wall", "calls", "prompt tok", "1st req tok", "hit", "out tok",
                  "cost $", "diff/ref"], out, ["l", "l", "r", "r", "r", "r", "r", "r", "r", "r", "r", "r"])


def noise_table(rows):
    """Coefficient of variation across repetitions, per metric; the median over (task, agent) groups."""
    groups = {}
    for r in rows:
        groups.setdefault((r["task"], r["arm"]), []).append(r)
    out, advice = [], {}
    for key, label, ex, better, (kind, band), spec in METRICS:
        if key in ("pass", "hang"):
            continue
        cvs = [cv([ex(r) for r in rs]) for rs in groups.values()]
        cvs = [c for c in cvs if c is not None]
        if not cvs:
            continue
        med, mx = st.median(cvs), max(cvs)
        out.append([label, len(cvs), "%.0f%%" % (100 * med), "%.0f%%" % (100 * mx),
                    ("%.0f%%" % (100 * band)) if kind == "rel" else "-"])
        if kind == "rel":
            advice[key] = max(band, round(1.5 * med, 2))
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
    totals = {m[0]: [0, 0, 0] for m in METRICS}
    detail = []
    for task in tasks:
        a_rows, b_rows = by.get((task, arm_a)), by.get((task, arm_b))
        if not a_rows or not b_rows:
            continue
        n_runs = min(len(a_rows), len(b_rows))
        line = [task]
        for key, label, ex, better, (kind, band), spec in METRICS:
            band = (bands or {}).get(key, band)
            if key == "pass":
                a = sum(1 for r in a_rows if r["pass"]) / len(a_rows)
                b = sum(1 for r in b_rows if r["pass"]) / len(b_rows)
            else:
                a, b = median([ex(r) for r in a_rows]), median([ex(r) for r in b_rows])
            if a is None or b is None:
                line.append("n/a")
                continue
            if tie(kind, band, a, b, n_runs):
                res, idx = "T", 1
            else:
                a_better = (a < b) if better == "low" else (a > b)
                res, idx = ("W", 0) if a_better else ("L", 2)
            totals[key][idx] += 1
            line.append("%s %s/%s" % (res, spec.format(a), spec.format(b)))
        detail.append(line)
    head = ["task"] + [m[1] for m in METRICS]
    lines = table(head, detail, ["l"] + ["l"] * len(METRICS)) if detail else ["(need both arms on a task)"]
    summary = [[m[1], *totals[m[0]], ("lower" if m[3] == "low" else "higher") + " is better"] for m in METRICS]
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
    add("flags: T timeout, I infra error, X protected test file modified, E agent error, C cache cliff")
    add("")
    add("== runs ==")
    L += run_table(rows, with_label=len(labels) > 1)
    add("")
    add("== per task x agent (median over repetitions) ==")
    L += group_table(rows)
    add("")
    add("== noise: coefficient of variation across repetitions ==")
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
    add("note: with only a couple of tasks this board is a rehearsal of the machinery, not a verdict.")
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
