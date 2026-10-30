"""Turn the raw output stream of one agent run into a uniform "trace".

pi      : `pi -p --mode json`                       -> JSONL events (docs/json.md)
claude  : `claude -p --output-format stream-json --verbose --include-partial-messages`

Both parsers are pure functions of (raw text, optional per-line arrival times) so they can be tested
against saved logs.  Token conventions of the trace (same for both agents):

    input        fresh (uncached) prompt tokens
    cache_read   prompt tokens served from the cache
    cache_write  prompt tokens written to the cache (only some providers report it)
    prompt_total = input + cache_read + cache_write
    output       generated tokens, *including* reasoning tokens
    reasoning    the part of `output` that was reasoning (None when the agent does not report it)

A trace is a dict:
    agent, meta{...}, calls[...], totals{...}, tool_calls[...], final_text, agent_error,
    reported{...}   (numbers the agent itself reported, informational only)
    aux{...}        (claude only: billed prompt tokens that belong to no visible LLM call)
"""
import json

TEXT_LIMIT = 20000


def _new_trace(agent):
    return {
        "agent": agent,
        "meta": {"bad_lines": 0, "n_events": 0},
        "calls": [],
        "totals": {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "reasoning": None},
        "tool_calls": [],
        "final_text": "",
        "agent_error": None,
        "reported": {},
        "retries": 0,
        "compactions": 0,
        "aux": {"prompt_total": 0},
        "timing": {"startup_s": None, "llm_s": None, "tool_s": None},
    }


def _records(raw, ts):
    """Yield (event_dict, arrival_time|None).  Records are split on LF only (pi docs: never use splitlines)."""
    for idx, line in enumerate(raw.split("\n")):
        line = line.strip("\r")
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:  # noqa
            yield None, None
            continue
        if not isinstance(obj, dict):
            yield None, None
            continue
        t = ts[idx] if ts is not None and idx < len(ts) else None
        yield obj, t


def _text_of(blocks):
    if isinstance(blocks, str):
        return blocks
    out = []
    for b in blocks or []:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text") or "")
    return "".join(out)


def _sum_totals(tr, calls):
    t = tr["totals"]
    for k_src, k_dst in (("input", "input"), ("cache_read", "cache_read"),
                         ("cache_write", "cache_write"), ("output", "output")):
        t[k_dst] = sum(c[k_src] for c in calls)
    rs = [c["reasoning"] for c in calls if c.get("reasoning") is not None]
    t["reasoning"] = sum(rs) if rs else None


# ----------------------------------------------------------------------------- pi
def parse_pi(raw, ts=None):
    tr = _new_trace("pi")
    meta = tr["meta"]
    trig = None            # arrival time of the event that triggers the next LLM call
    first_t = None
    llm_s = 0.0
    tool_s = 0.0
    have_t = ts is not None
    last_assistant = None
    for ev, t in _records(raw, ts):
        if ev is None:
            meta["bad_lines"] += 1
            continue
        meta["n_events"] += 1
        if first_t is None and t is not None:
            first_t = t
        typ = ev.get("type")
        if typ == "session":
            meta["cwd"] = ev.get("cwd")
            meta["session_version"] = ev.get("version")
            if trig is None:
                trig = t
        elif typ == "agent_start":
            if trig is None:
                trig = t
        elif typ in ("message_start", "message_end"):
            m = ev.get("message") or {}
            role = m.get("role")
            if role == "system" and "tools_exposed" not in meta:
                meta["tools_exposed"] = [x.get("name") for x in (m.get("toolsAdded") or []) if isinstance(x, dict)]
                secs = m.get("sections") or {}
                meta["system_sections_chars"] = {k: len(v) for k, v in secs.items() if isinstance(v, str)}
            if typ == "message_end" and role == "assistant":
                u = m.get("usage") or {}
                inp = int(u.get("input") or 0)
                cr = int(u.get("cacheRead") or 0)
                cw = int(u.get("cacheWrite") or 0)
                out = int(u.get("output") or 0)
                rs = u.get("reasoning")
                call = {
                    "input": inp, "cache_read": cr, "cache_write": cw, "output": out,
                    "reasoning": int(rs) if rs is not None else None,
                    "prompt_total": inp + cr + cw,
                    "stop": m.get("stopReason"), "error": None, "sub": False,
                    "llm_s": None,
                }
                if m.get("stopReason") in ("error", "aborted") or m.get("errorMessage"):
                    call["error"] = str(m.get("errorMessage") or m.get("stopReason"))[:300]
                if t is not None and trig is not None:
                    call["llm_s"] = max(0.0, t - trig)
                    llm_s += call["llm_s"]
                cost = (u.get("cost") or {}).get("total")
                if isinstance(cost, (int, float)):
                    tr["reported"]["cost_usd"] = tr["reported"].get("cost_usd", 0.0) + cost
                meta["model"] = m.get("model") or meta.get("model")
                meta["provider"] = m.get("provider") or meta.get("provider")
                meta["thinking"] = m.get("thinkingLevel") or meta.get("thinking")
                tr["calls"].append(call)
                last_assistant = m
            elif typ == "message_end" and role == "toolResult":
                trig = t if t is not None else trig
        elif typ == "tool_execution_end":
            d = ev.get("durationMs")
            tr["tool_calls"].append({"name": ev.get("toolName"), "is_error": bool(ev.get("isError")),
                                     "duration_ms": d})
            if isinstance(d, (int, float)):
                tool_s += d / 1000.0
        elif typ == "auto_retry_start":
            tr["retries"] += 1
        elif typ == "compaction_end":
            if ev.get("result"):
                tr["compactions"] += 1
        elif typ == "agent_settled":
            meta["settled"] = True
            meta["aborted"] = bool(ev.get("aborted"))
    _sum_totals(tr, tr["calls"])
    if last_assistant is not None:
        tr["final_text"] = _text_of(last_assistant.get("content"))[:TEXT_LIMIT]
    errs = [c["error"] for c in tr["calls"] if c["error"]]
    if errs:
        tr["agent_error"] = "llm error: " + errs[-1]
    elif not tr["calls"]:
        tr["agent_error"] = "no LLM call was made"
    elif meta.get("aborted"):
        tr["agent_error"] = "aborted"
    if have_t:
        tr["timing"] = {"startup_s": (first_t if first_t is not None else None),
                        "llm_s": round(llm_s, 3), "tool_s": round(tool_s, 3)}
    else:
        tr["timing"]["tool_s"] = round(tool_s, 3)
    return tr


# ----------------------------------------------------------------------------- claude
USAGE_FIELDS = (("input_tokens", "input"), ("cache_read_input_tokens", "cache_read"),
                ("cache_creation_input_tokens", "cache_write"), ("output_tokens", "output"))


def parse_cc(raw, ts=None, inclusive=False):
    """`claude -p --output-format stream-json --verbose --include-partial-messages`.

    Per-call usage comes from the raw API stream events (`stream_event`: message_start + message_delta), because the
    `assistant` events only carry the message_start snapshot, which is all zeros when a gateway reports usage at the
    end of the stream.  Totals come from the final `result.usage` (it also covers auxiliary and sub-agent calls).
    `inclusive`: the gateway's input_tokens already contains the cached tokens (OpenAI style); the parser then
    subtracts them so that, as everywhere else, input = fresh tokens only."""
    tr = _new_trace("cc")
    meta = tr["meta"]
    by_id, order = {}, []
    tool_names, tool_start = {}, {}
    first_t = None
    llm_s = 0.0
    tool_s = 0.0
    result = None
    last_text = ""
    cur_mid = None

    def call_for(mid, sub, t):
        c = by_id.get(mid)
        if c is None:
            c = {"id": mid, "input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "reasoning": None,
                 "stop": None, "error": None, "sub": sub, "llm_s": None, "t_first": t, "ttft_ms": None}
            by_id[mid] = c
            order.append(mid)
        return c

    def merge_usage(c, u):
        for src, dst in USAGE_FIELDS:        # usage is cumulative: the largest value seen is the final one
            try:
                c[dst] = max(c[dst], int(u.get(src) or 0))
            except (TypeError, ValueError):
                pass

    for ev, t in _records(raw, ts):
        if ev is None:
            meta["bad_lines"] += 1
            continue
        meta["n_events"] += 1
        if first_t is None and t is not None:
            first_t = t
        typ, st = ev.get("type"), ev.get("subtype")
        if typ == "system" and st == "init":
            meta["model"] = ev.get("model")
            meta["version"] = ev.get("claude_code_version")
            meta["cwd"] = ev.get("cwd")
            meta["permission_mode"] = ev.get("permissionMode")
            meta["tools_exposed"] = list(ev.get("tools") or [])
            meta["mcp_servers"] = [s.get("name") if isinstance(s, dict) else s for s in (ev.get("mcp_servers") or [])]
            meta["plugins"] = [p.get("name") if isinstance(p, dict) else p for p in (ev.get("plugins") or [])]
            meta["n_skills"] = len(ev.get("skills") or [])
            meta["n_slash_commands"] = len(ev.get("slash_commands") or [])
            meta["agents"] = list(ev.get("agents") or [])
        elif typ == "stream_event":
            meta["has_stream_events"] = True
            e = ev.get("event") or {}
            et = e.get("type")
            sub = ev.get("parent_tool_use_id") is not None
            if et == "message_start":
                m = e.get("message") or {}
                cur_mid = m.get("id") or ev.get("api_message_id") or ("noid-%d" % len(order))
                c = call_for(cur_mid, sub, t)
                merge_usage(c, m.get("usage") or {})
                if ev.get("ttft_ms") is not None:
                    c["ttft_ms"] = ev.get("ttft_ms")
            elif et == "message_delta":
                mid = ev.get("api_message_id") or cur_mid
                if mid in by_id:
                    merge_usage(by_id[mid], e.get("usage") or {})
                    if (e.get("delta") or {}).get("stop_reason"):
                        by_id[mid]["stop"] = e["delta"]["stop_reason"]
        elif typ == "assistant":
            m = ev.get("message") or {}
            mid = m.get("id") or ev.get("request_id") or ("noid-%d" % len(order))
            c = call_for(mid, ev.get("parent_tool_use_id") is not None, t)
            merge_usage(c, m.get("usage") or {})          # only a fallback: the snapshot can be all zeros
            if m.get("stop_reason") and not c["stop"]:
                c["stop"] = m.get("stop_reason")
            for b in m.get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    tool_names[b.get("id")] = b.get("name")
                    tool_start[b.get("id")] = t
                elif b.get("type") == "text" and not c["sub"]:
                    last_text = b.get("text") or last_text
        elif typ == "user":
            content = (ev.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    tid = b.get("tool_use_id")
                    d = None
                    if t is not None and tool_start.get(tid) is not None:
                        d = max(0.0, t - tool_start[tid]) * 1000.0
                        tool_s += d / 1000.0
                    tr["tool_calls"].append({"name": tool_names.get(tid, "?"), "is_error": bool(b.get("is_error")),
                                             "duration_ms": d})
        elif typ == "result":
            result = ev
    # per-call bookkeeping
    calls = []
    for mid in order:
        c = by_id[mid]
        if inclusive:
            c["input"] = max(0, c["input"] - c["cache_read"] - c["cache_write"])
        c["prompt_total"] = c["input"] + c["cache_read"] + c["cache_write"]
        calls.append(c)
    tr["calls"] = calls
    # llm latency per main-thread call: arrival(end of the call) - arrival(previous trigger)
    if ts is not None:
        for mid, dt in _cc_trigger_pass(raw, ts, by_id).items():
            by_id[mid]["llm_s"] = dt
            llm_s += dt
    main = [c for c in calls if not c["sub"]]
    # authoritative totals: result.usage (covers auxiliary + sub-agent calls); fall back to the visible calls
    _sum_totals(tr, calls)
    if result is not None:
        u = result.get("usage") or {}
        meta["result_usage"] = {k: u.get(k) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens",
                                                       "output_tokens")}
        tot = tr["totals"]
        tot["input"] = int(u.get("input_tokens") or 0)
        tot["cache_read"] = int(u.get("cache_read_input_tokens") or 0)
        tot["cache_write"] = int(u.get("cache_creation_input_tokens") or 0)
        if inclusive:
            tot["input"] = max(0, tot["input"] - tot["cache_read"] - tot["cache_write"])
        tot["output"] = int(u.get("output_tokens") or 0)
        det = u.get("output_tokens_details") or {}
        tot["reasoning"] = det.get("thinking_tokens") if isinstance(det, dict) else None
        # Prompt tokens that were billed but belong to no visible call = auxiliary requests (title generation,
        # classifiers, ...).
        vis_prompt = sum(c["prompt_total"] for c in calls)
        tr["aux"] = {"prompt_total": max(0, tot["input"] + tot["cache_read"] + tot["cache_write"] - vis_prompt)}
        tr["reported"] = {"cost_usd": result.get("total_cost_usd"), "duration_ms": result.get("duration_ms"),
                          "duration_api_ms": result.get("duration_api_ms"), "num_turns": result.get("num_turns"),
                          "ttft_ms": result.get("ttft_ms"), "time_to_request_ms": result.get("time_to_request_ms")}
        mu = result.get("modelUsage") or {}
        meta["models_billed"] = sorted(mu.keys())
        meta["subagent_stats"] = result.get("subagent_stats")
        if result.get("is_error") or result.get("subtype") not in (None, "success"):
            tr["agent_error"] = "result %s: %s" % (result.get("subtype"), str(result.get("result") or "")[:200])
        elif result.get("terminal_reason") not in (None, "completed"):
            tr["agent_error"] = "terminal_reason=%s" % result.get("terminal_reason")
        tr["final_text"] = str(result.get("result") or "")[:TEXT_LIMIT]
    else:
        tr["agent_error"] = "no result event (run was cut off)"
        tr["final_text"] = last_text[:TEXT_LIMIT]
        meta["no_result"] = True
    if not main and tr["agent_error"] is None:
        tr["agent_error"] = "no LLM call was made"
    meta["usage_semantics"] = "inclusive" if inclusive else "additive"
    if ts is not None:
        tr["timing"] = {"startup_s": first_t, "llm_s": round(llm_s, 3), "tool_s": round(tool_s, 3)}
    else:
        tr["timing"]["tool_s"] = round(tool_s, 3)
    return tr


def _cc_trigger_pass(raw, ts, by_id):
    """llm latency per main-thread call = arrival(end of the call) - arrival(previous trigger).  The end of a call is
    its message_stop stream event when there is one, else its last assistant event."""
    out = {}
    trig = None
    cur_mid = None
    for ev, t in _records(raw, ts):
        if ev is None or t is None:
            continue
        typ, st = ev.get("type"), ev.get("subtype")
        if typ == "system" and st == "init":
            trig = t
        elif typ == "stream_event":
            e = ev.get("event") or {}
            if e.get("type") == "message_start":
                cur_mid = (e.get("message") or {}).get("id") or ev.get("api_message_id")
            elif e.get("type") == "message_stop":
                mid = ev.get("api_message_id") or cur_mid
                if mid in by_id and not by_id[mid]["sub"] and trig is not None:
                    out[mid] = max(0.0, t - trig)
        elif typ == "assistant":
            m = ev.get("message") or {}
            mid = m.get("id") or ev.get("request_id")
            if mid in by_id and not by_id[mid]["sub"] and trig is not None:
                out[mid] = max(0.0, t - trig)      # overwritten by later blocks / message_stop: last wins
        elif typ == "user" and ev.get("parent_tool_use_id") is None:
            trig = t
    return out


# ----------------------------------------------------------------------------- shared analysis
def find_cliffs(calls, min_lost=3000, frac=0.4, slack=64):
    """Cache cliffs between consecutive main-thread calls.

    Every request normally re-sends the previous one plus a bit more, so the whole previous prompt should
    be a cache hit.  `lost` is how much of it was not.  A *cliff* is a loss >= max(min_lost, frac * previous
    prompt).  Returns (cliffs, lost_tokens) where lost_tokens sums every loss above the granularity slack."""
    main = [c for c in calls if not c.get("sub")]
    cliffs, lost_total = [], 0
    for i in range(1, len(main)):
        prev, cur = main[i - 1], main[i]
        expected = prev["prompt_total"]
        lost = expected - cur["cache_read"]
        if lost > slack:
            lost_total += lost
        if lost >= max(min_lost, frac * expected):
            cliffs.append({"call": i + 1, "lost": lost, "prev_prompt": expected, "cache_read": cur["cache_read"]})
    return cliffs, lost_total


def parse(agent, raw, ts=None, cc_inclusive=False):
    return parse_pi(raw, ts) if agent == "pi" else parse_cc(raw, ts, inclusive=cc_inclusive)
