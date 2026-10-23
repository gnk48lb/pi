"""cacheprobe: how reliable is the gateway's prompt cache, independent of any agent?

Two experiments per protocol (OpenAI /chat/completions as pi uses it, Anthropic /v1/messages as Claude Code uses it):

  repeat  the SAME request again and again at growing gaps (1 s ... 160 s).  A working prefix cache should serve
          everything but the last partial block of every repetition.
  grow    an append-only conversation (each request = the previous request + one more turn), which is exactly what an
          agent loop sends.  Every request should hit the cache for everything the previous request contained.

Whatever is lost here is the gateway's doing, not a harness's: it is the noise floor under every cache-hit-rate and
cost comparison the arena makes.  Standard library only; never goes through your HTTP proxy."""
import json
import os
import random
import re
import time
import urllib.error
import urllib.request

import arena_core as core

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # the gateway is local: no proxy
GRANULARITY = 64            # DeepSeek caches in 64-token blocks
WORDS = ("alpha beta gamma delta server client request response buffer stream token cache prefix window module "
         "record field value index queue thread signal budget policy report ticket result status config option "
         "target source output input header footer branch commit merge review deploy build test fixture mock stub "
         "parser lexer render layout style color shape image audio video frame packet socket route proxy session").split()


def filler(n_tokens, seed):
    """Deterministic English-like text of about n_tokens tokens (4 chars per token is close enough: the gateway reports
    the real count)."""
    rnd = random.Random(seed)
    out, size, i = [], 0, 0
    while size < n_tokens * 4:
        s = "Item %04d: %s." % (i, " ".join(rnd.choice(WORDS) for _ in range(rnd.randint(8, 14))))
        out.append(s)
        size += len(s) + 1
        i += 1
    return "\n".join(out)


def strip_suffix(m):
    return re.sub(r"\[.*?\]$", "", str(m or ""))


def endpoints_from_configs(cfg_root):
    """The two endpoints exactly as `setup` recorded them (what the agents will use)."""
    out = {}
    pm = core.load_json(os.path.join(cfg_root, "pi", "models.json")) or {}
    for pname, prov in (pm.get("providers") or {}).items():
        models = prov.get("models") or []
        if models and prov.get("baseUrl"):
            out["openai"] = {"url": prov["baseUrl"].rstrip("/") + "/chat/completions",
                             "headers": {"Authorization": "Bearer %s" % prov.get("apiKey", "")},
                             "model": models[0]["id"], "label": "%s (%s)" % (pname, prov.get("api"))}
    env = core.load_json(os.path.join(cfg_root, "cc", "env.json")) or {}
    if env.get("ANTHROPIC_BASE_URL"):
        hdr = {"anthropic-version": "2023-06-01"}
        if env.get("ANTHROPIC_AUTH_TOKEN"):
            hdr["Authorization"] = "Bearer %s" % env["ANTHROPIC_AUTH_TOKEN"]
        elif env.get("ANTHROPIC_API_KEY"):
            hdr["x-api-key"] = env["ANTHROPIC_API_KEY"]
        out["anthropic"] = {"url": env["ANTHROPIC_BASE_URL"].rstrip("/") + "/v1/messages", "headers": hdr,
                            "model": strip_suffix(env.get("ANTHROPIC_MODEL")), "label": "anthropic messages"}
    return out


# ------------------------------------------------------------------------------------------ one request
def build_body(proto, model, system_text, turns):
    if proto == "openai":
        msgs = [{"role": "system", "content": system_text}] + [{"role": r, "content": t} for r, t in turns]
        return {"model": model, "stream": True, "stream_options": {"include_usage": True}, "max_tokens": 16,
                "messages": msgs}
    return {"model": model, "max_tokens": 16, "stream": True,
            "system": [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": r, "content": t} for r, t in turns]}


def usage_of(proto, events):
    """(prompt_tokens, cached_tokens, output_tokens, raw usage) from the streamed events; None where unknown."""
    if proto == "openai":
        raw = None
        for ev in events:
            if isinstance(ev, dict) and isinstance(ev.get("usage"), dict):
                raw = ev["usage"]
        if raw is None:
            return None, None, None, None
        det = raw.get("prompt_tokens_details") or {}
        cached = det.get("cached_tokens")
        if cached is None:
            cached = raw.get("prompt_cache_hit_tokens")
        return raw.get("prompt_tokens"), cached, raw.get("completion_tokens"), raw
    merged = {}
    for ev in events:
        if not isinstance(ev, dict):
            continue
        u = (ev.get("message") or {}).get("usage") if ev.get("type") == "message_start" else (
            ev.get("usage") if ev.get("type") == "message_delta" else None)
        for k, v in (u or {}).items():
            if isinstance(v, int):
                merged[k] = max(merged.get(k, 0), v)
    if not merged:
        return None, None, None, None
    cr = merged.get("cache_read_input_tokens", 0)
    prompt = merged.get("input_tokens", 0) + cr + merged.get("cache_creation_input_tokens", 0)   # Anthropic convention
    return prompt, cr, merged.get("output_tokens"), merged


def post(ep, body, timeout):
    t0 = time.time()
    hdr = dict(ep["headers"], **{"Content-Type": "application/json", "Accept": "text/event-stream"})
    req = urllib.request.Request(ep["url"], data=json.dumps(body).encode(), headers=hdr, method="POST")
    rec = {"status": None, "error": None, "headers": {}, "ttfb_s": None, "latency_s": None, "events": []}
    try:
        resp = OPENER.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        rec.update(status=e.code, error=e.read(1500).decode("utf-8", "replace"), headers=dict(e.headers),
                   latency_s=time.time() - t0)
        return rec
    except Exception as e:  # noqa
        rec.update(error="%s: %s" % (type(e).__name__, e), latency_s=time.time() - t0)
        return rec
    rec["status"] = resp.status
    rec["headers"] = dict(resp.headers)
    try:
        for raw in resp:
            if rec["ttfb_s"] is None:
                rec["ttfb_s"] = time.time() - t0
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    try:
                        rec["events"].append(json.loads(payload))
                    except ValueError:
                        pass
    except Exception as e:  # noqa
        rec["error"] = "stream broke: %s: %s" % (type(e).__name__, e)
    rec["latency_s"] = time.time() - t0
    return rec


# ------------------------------------------------------------------------------------------ experiments
SAFE_HEADERS = ("server", "via", "x-request-id", "request-id", "x-provider", "x-upstream", "x-served-by", "x-backend",
                "cf-ray", "x-ratelimit-remaining", "date")


def one(proto, ep, kind, idx, gap, system_text, turns, timeout, sink, say, expected=None, extra=None):
    body = build_body(proto, ep["model"], system_text, turns)
    r = post(ep, body, timeout)
    prompt, cached, out, raw = usage_of(proto, r["events"])
    rec = {"proto": proto, "kind": kind, "idx": idx, "gap_s": gap, "t": time.strftime("%H:%M:%S"), "status": r["status"],
           "prompt": prompt, "cached": cached, "output": out, "usage_raw": raw, "expected_cached": expected,
           "ttfb_s": r["ttfb_s"], "latency_s": r["latency_s"], "error": r["error"],
           "headers": {k: v for k, v in r["headers"].items() if k.lower() in SAFE_HEADERS}}
    if extra:
        rec.update(extra)
    lost = (expected - cached) if (expected is not None and cached is not None) else None
    rec["lost"] = lost
    sink.write(json.dumps(rec) + "\n")
    sink.flush()
    note = ""
    if r["status"] != 200 or r["error"]:
        note = "  ERROR %s %s" % (r["status"], (r["error"] or "")[:160].replace("\n", " "))
    elif prompt is None:
        note = "  (no usage in the response)"
    elif lost is not None and lost > 3 * GRANULARITY:
        note = "  <-- lost %d cached tokens" % lost
    say("  %s #%-2d %-6s gap %5s  prompt %6s  cached %6s  (%s)  ttfb %.1fs total %.1fs%s" % (
        proto[:3], idx, kind, ("%g" % gap) if gap is not None else "-", prompt, cached,
        ("%.0f%%" % (100.0 * cached / prompt)) if prompt and cached is not None else "-",
        r["ttfb_s"] or 0, r["latency_s"] or 0, note))
    return rec


def probe_protocol(proto, ep, tokens, gaps, grow_runs, grow_turns, grow_gap, timeout, sink, say):
    recs = []
    say("\n=== %s  %s  model %s  prefix ~%d tokens" % (proto, ep["label"], ep["model"], tokens))
    # ---- repeat: the same request at growing gaps -----------------------------------------------------------
    system_text = "probe-%s-%s\n%s" % (proto, os.urandom(4).hex(), filler(tokens, 7))
    turns = [("user", "Reply with exactly: OK")]
    say("repeat: one cold request, then the identical request after each gap (seconds): %s" % ",".join("%g" % g for g in gaps))
    first = one(proto, ep, "repeat", 1, None, system_text, turns, timeout, sink, say)
    recs.append(first)
    if first["status"] != 200 or first["prompt"] is None:
        say("  the first request failed or reported no usage: skipping this protocol")
        return recs
    for i, g in enumerate(gaps, 2):
        core.nap(g)
        recs.append(one(proto, ep, "repeat", i, g, system_text, turns, timeout, sink, say, expected=first["prompt"]))
    # ---- grow: append-only conversation, like an agent loop -------------------------------------------------
    say("grow: %d append-only conversations of %d turns, %g s between turns (assistant turns are fixed text)" % (
        grow_runs, grow_turns, grow_gap))
    for run in range(1, grow_runs + 1):
        sys_g = "probe-%s-grow-%s\n%s" % (proto, os.urandom(4).hex(), filler(tokens, 11 + run))
        turns_g, prev = [], None
        for k in range(1, grow_turns + 1):
            turns_g.append(("user", "Turn %d. %s\nReply with exactly: OK" % (k, filler(250, 1000 * run + k))))
            r = one(proto, ep, "grow", k, grow_gap if k > 1 else None, sys_g, turns_g, timeout, sink, say,
                    expected=(prev["prompt"] if prev and prev["prompt"] is not None else None), extra={"run": run})
            recs.append(r)
            turns_g.append(("assistant", "OK"))
            prev = r
            if k < grow_turns:
                core.nap(grow_gap)
    return recs


def summarize(proto, recs):
    """Text summary of one protocol's records."""
    L = []
    ok = [r for r in recs if r["status"] == 200 and r["prompt"] is not None]
    errs = [r for r in recs if r["status"] != 200 or r["prompt"] is None]
    rep = [r for r in ok if r["kind"] == "repeat" and r["idx"] > 1]
    grow = [r for r in ok if r["kind"] == "grow" and r["expected_cached"] is not None]

    def cls(r):
        lost = r["lost"] if r["lost"] is not None else 0
        if lost <= 3 * GRANULARITY:
            return "hit"
        return "cliff" if lost >= max(3000, 0.4 * r["expected_cached"]) else "partial"

    L.append("--- %s: %d requests, %d errors/without usage" % (proto, len(recs), len(errs)))
    if rep:
        L.append("repeat (identical request): by gap")
        buckets = [(0, 2), (2, 10), (10, 40), (40, 1000)]
        for lo, hi in buckets:
            rs = [r for r in rep if lo < (r["gap_s"] or 0) <= hi] if lo else [r for r in rep if (r["gap_s"] or 0) <= hi]
            if not rs:
                continue
            L.append("  gap %s-%s s: %d requests, %d full hits, %d partial, %d cliffs; mean cached %.1f%%" % (
                lo, hi, len(rs), sum(cls(r) == "hit" for r in rs), sum(cls(r) == "partial" for r in rs),
                sum(cls(r) == "cliff" for r in rs),
                100 * sum(r["cached"] / r["prompt"] for r in rs) / len(rs)))
    if grow:
        n_hit, n_part, n_cliff = (sum(cls(r) == k for r in grow) for k in ("hit", "partial", "cliff"))
        lost_total = sum(max(0, r["lost"]) for r in grow)
        exp_total = sum(r["expected_cached"] for r in grow)
        L.append("grow (append-only, what an agent sends): %d requests: %d clean hits, %d partial losses, %d cliffs; "
                 "%.2f%% of the tokens that should have been cache hits were not (%d of %d)" % (
                     len(grow), n_hit, n_part, n_cliff, 100.0 * lost_total / max(1, exp_total), lost_total, exp_total))
    lat = sorted(r["latency_s"] for r in ok if r["latency_s"])
    ttfb = sorted(r["ttfb_s"] for r in ok if r["ttfb_s"])
    if lat:
        L.append("latency: median %.1fs, max %.1fs; time to first byte median %.1fs" % (
            lat[len(lat) // 2], lat[-1], ttfb[len(ttfb) // 2] if ttfb else 0))
    hdrs = {}
    for r in ok:
        for k, v in (r.get("headers") or {}).items():
            if k.lower() in ("server", "via", "x-provider", "x-upstream", "x-served-by", "x-backend"):
                hdrs.setdefault(k.lower(), set()).add(v)
    for k, v in hdrs.items():
        L.append("response header %s: %s" % (k, ", ".join(sorted(v))[:200]))
    for r in errs[:5]:
        L.append("error sample: status %s %s" % (r["status"], (r["error"] or "no usage in response")[:200].replace("\n", " ")))
    return L


def run(cfg_root, out_dir, protos, tokens, gaps, grow_runs, grow_turns, grow_gap, timeout, say=print, endpoints=None):
    """Run the probe for each protocol.  Returns (records, summary text).  Files: out_dir/probe.jsonl, summary.txt."""
    os.makedirs(out_dir, exist_ok=True)
    eps = endpoints or endpoints_from_configs(cfg_root)
    all_recs, lines = [], []

    def tee(msg=""):
        say(msg)
        lines.append(msg)
    tee("cacheprobe %s (local time %s)" % (time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()), time.strftime("%H:%M %Z")))
    with open(os.path.join(out_dir, "probe.jsonl"), "w") as sink:
        for proto in protos:
            if proto not in eps:
                tee("\n=== %s: no endpoint configured, skipped" % proto)
                continue
            recs = probe_protocol(proto, eps[proto], tokens, gaps, grow_runs, grow_turns, grow_gap, timeout, sink, tee)
            all_recs += recs
    tee("\n==== summary ====")
    for proto in protos:
        recs = [r for r in all_recs if r["proto"] == proto]
        if recs:
            for l in summarize(proto, recs):
                tee(l)
    text = "\n".join(lines)
    with open(os.path.join(out_dir, "summary.txt"), "w") as f:
        f.write(text + "\n")
    return all_recs, text
