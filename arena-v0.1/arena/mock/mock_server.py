#!/usr/bin/env python3
"""Arena mock gateway: OpenAI chat-completions + Anthropic messages, scripted "model", simulated prefix cache.

It never calls a real model.  A *script* decides what the fake model does, so the arena's
runner/parser/verifier can be tested end-to-end with the real `pi` and `claude` binaries for $0.

Endpoints
  POST /v1/chat/completions         OpenAI wire (what pi's openai-completions provider speaks)
  POST /v1/messages                 Anthropic wire (what Claude Code speaks), streaming and not
  POST /v1/messages/count_tokens    Anthropic token counting (estimate)
  GET  /v1/models                   model list
  POST /__reset                     clear cache simulation + request log
  GET  /__health

Env
  MOCK_PORT     listen port (default 18081)
  MOCK_LOG      per-request log, JSONL (default ./mock-requests.jsonl)
  MOCK_SCRIPT   path of the script file, re-read on every request (see below)
  MOCK_DUMP     if set, append every full request body (JSONL) there
  MOCK_TTL      simulated cache lifetime in seconds (default 300)

Script file: a JSON list of steps (or {"steps": [...], "final": "text"}).  Step i is what the model
does on the (i+1)-th *assistant turn that uses a tool*: i == number of tool calls already present in
the conversation.  Requests that carry no tools (Claude Code's auxiliary calls) just get a short text
reply and do not consume a step.  A step is a dict:
  {"tool": "bash", "arguments": {"command": "..."}}   call a tool (name matched case-insensitively,
                                                       so "bash" finds pi's `bash` and Claude Code's `Bash`)
  "say": "text"            optional text emitted before the tool call
  "delay": 1.5             seconds to wait before answering
  "think": "text"          the model "reasons" first: OpenAI reasoning_content deltas / Anthropic thinking block
  "reasoning_tokens": 120  reported as reasoning tokens (OpenAI usage detail), counted inside the output tokens
                           (defaults to len(think)/4 when "think" is given)
After the last step the model answers with plain text and the agent finishes.

Simulated cache: longest common prefix against earlier requests (<= MOCK_TTL old), 64-token granularity,
4 chars ~ 1 token.  Order is tools -> system -> messages (cache_control markers are ignored for matching).
Anthropic usage reports input_tokens (fresh) + cache_creation_input_tokens + cache_read_input_tokens;
OpenAI usage reports prompt_tokens (all) + prompt_tokens_details.cached_tokens.
"""
import hashlib
import json
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("MOCK_PORT", "18081"))
LOG = os.environ.get("MOCK_LOG", "mock-requests.jsonl")
TTL = float(os.environ.get("MOCK_TTL", "300"))
SCRIPT_PATH = os.environ.get("MOCK_SCRIPT")
DUMP = os.environ.get("MOCK_DUMP")
# How the Anthropic endpoint reports usage (gateways differ, and the arena must cope with each):
#   MOCK_USAGE    anthropic (default): input = fresh, cache_creation + cache_read reported separately
#                 exclusive: input = cache misses, cache_creation always 0   (what a DeepSeek-backed gateway may do)
#                 inclusive: input = the WHOLE prompt, cache_read is a part of it, cache_creation 0
#   MOCK_USAGE_AT start (default): full usage in message_start | delta: zeros in message_start, full usage in message_delta
USAGE_MODE = os.environ.get("MOCK_USAGE", "anthropic")
USAGE_AT = os.environ.get("MOCK_USAGE_AT", "start")
GRAN = 64

LOCK = threading.Lock()
CACHE = []   # [(timestamp, seq, prefix_string)]
HASHES = {}  # seq -> (tools_hash, system_hash, [msg hashes])
SEQ = [0]

DEFAULT_SCRIPT = [{"tool": "bash", "arguments": {"command": "echo hello from the mock model"}}]


def canon(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=False)


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:10]


def lcp(a, b):
    lo, hi = 0, min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def has_cc(obj):
    if isinstance(obj, dict):
        return "cache_control" in obj or any(has_cc(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_cc(v) for v in obj)
    return False


def strip_cc(obj):
    if isinstance(obj, dict):
        return {k: strip_cc(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [strip_cc(v) for v in obj]
    return obj


def load_script():
    if not SCRIPT_PATH or not os.path.exists(SCRIPT_PATH):
        return DEFAULT_SCRIPT, "Done."
    try:
        data = json.load(open(SCRIPT_PATH))
    except Exception:  # noqa
        return DEFAULT_SCRIPT, "Done."
    if isinstance(data, dict):
        return data.get("steps") or [], data.get("final") or "Done."
    return data, "Done."


def map_args(props, args):
    out = {}
    for k, v in (args or {}).items():
        if props and k not in props:
            if k == "path" and "file_path" in props:
                k = "file_path"
            elif k == "file_path" and "path" in props:
                k = "path"
        out[k] = v
    return out


def simulate_cache(elements, bp_index):
    """elements: canonical strings in prefix order.  bp_index: index of the last element carrying a
    cache_control marker (or None).  Returns dict with token numbers and diff info (also stores prefix)."""
    prefix = "\n".join(elements)
    offs, pos = [], 0
    for e in elements:
        pos += len(e) + 1
        offs.append(pos)
    now = time.time()
    best, best_seq = 0, None
    for ts, s, p in CACHE:
        if now - ts > TTL:
            continue
        k = lcp(p, prefix)
        if k > best:
            best, best_seq = k, s
    prompt_tokens = max(1, (len(prefix) + 3) // 4)
    cached = min(prompt_tokens, (best // 4 // GRAN) * GRAN)
    creation = 0
    if bp_index is not None:
        bp_tokens = min(prompt_tokens, offs[bp_index] // 4)
        creation = max(0, bp_tokens - cached)
    SEQ[0] += 1
    seq = SEQ[0]
    CACHE.append((now, seq, prefix))
    return {"seq": seq, "now": now, "prompt": prompt_tokens, "cached": cached, "creation": creation,
            "lcp": best, "best_seq": best_seq}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a, **k):
        pass

    # ------------------------------------------------------------ plumbing
    def _json(self, code, obj, extra_headers=None):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self):
        if (self.headers.get("Transfer-Encoding") or "").lower() == "chunked":
            data = b""
            while True:
                line = self.rfile.readline().strip()
                if not line:
                    break
                n = int(line.split(b";")[0], 16)
                if n == 0:
                    self.rfile.readline()
                    break
                data += self.rfile.read(n)
                self.rfile.readline()
            return data
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b"{}"

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/__health"):
            return self._json(200, {"ok": True, "seq": SEQ[0]})
        if path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": "mock-model", "object": "model", "type": "model", "display_name": "Mock Model"}]})
        return self._json(404, {"error": "not found: " + path})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")
        raw = self._read_body()
        if path.startswith("/__reset"):
            with LOCK:
                CACHE.clear()
                HASHES.clear()
                SEQ[0] = 0
                open(LOG, "w").close()
            return self._json(200, {"ok": True})
        try:
            body = json.loads(raw or b"{}")
        except Exception as e:  # noqa
            return self._json(400, {"error": "bad json: %s" % e})
        if path.endswith("/chat/completions"):
            return self.chat_openai(body)
        if path.endswith("/messages/count_tokens"):
            est = (len(canon(body.get("tools") or [])) + len(canon(body.get("system") or ""))
                   + len(canon(body.get("messages") or [])) + 3) // 4
            return self._json(200, {"input_tokens": max(1, est)})
        if path.endswith("/messages"):
            return self.chat_anthropic(body)
        return self._json(404, {"error": "not found: " + path})

    # ------------------------------------------------------------ the fake model
    def plan(self, tool_defs, n_calls):
        """-> (text, call|None, step) ; call = {"name","args"}; tool_defs: [(name, props)]"""
        if not tool_defs:
            return "OK", None, None
        steps, final = load_script()
        if n_calls >= len(steps):
            return final, None, None
        step = steps[n_calls]
        text = step.get("say")
        want = step.get("tool")
        if not want:
            return text or final, None, step
        real, props = want, {}
        for name, p in tool_defs:
            if name.lower() == want.lower():
                real, props = name, p
                break
        return text, {"name": real, "args": map_args(props, step.get("arguments"))}, step

    def finish_log(self, rec, body):
        with LOCK:
            with open(LOG, "a") as f:
                f.write(json.dumps(rec) + "\n")
            if DUMP:
                with open(DUMP, "a") as f:
                    f.write(json.dumps(body) + "\n")

    @staticmethod
    def params_of(body):
        keys = ("max_tokens", "max_completion_tokens", "temperature", "reasoning_effort", "thinking",
                "output_config", "reasoning", "tool_choice", "stream", "metadata")
        out = {}
        for k in keys:
            if k in body:
                v = body[k]
                out[k] = v if len(canon(v)) < 300 else "<%d chars>" % len(canon(v))
        return out

    # ------------------------------------------------------------ OpenAI wire
    def chat_openai(self, body):
        tools = body.get("tools") or []
        messages = body.get("messages") or []
        tools_c = canon(tools)
        msg_c = [canon(m) for m in messages]
        with LOCK:
            sim = simulate_cache([tools_c] + msg_c, None)
            tools_h, msg_h = sha(tools_c), [sha(c) for c in msg_c]
            HASHES[sim["seq"]] = (tools_h, "", msg_h)
            append_only, first_diff, tools_changed = self.diff_info(sim["best_seq"], tools_h, "", msg_h)
        n_calls = sum(len(m.get("tool_calls") or []) for m in messages if m.get("role") == "assistant")
        tool_defs = []
        for t in tools:
            fn = (t.get("function") or {}) if isinstance(t, dict) else {}
            if fn.get("name"):
                tool_defs.append((fn["name"], (fn.get("parameters") or {}).get("properties") or {}))
        text, call, step = self.plan(tool_defs, n_calls)
        if step and step.get("delay"):
            time.sleep(float(step["delay"]))
        seq = sim["seq"]
        if call:
            call["id"] = "call_%d_%s" % (seq, sha(str(sim["now"]))[:6])
            call["json"] = json.dumps(call["args"])
            out_tokens = max(1, len(call["json"]) // 4) + (len(text or "") // 4)
        else:
            out_tokens = max(1, len(text or "") // 4)
        think = (step or {}).get("think")
        reasoning = int((step or {}).get("reasoning_tokens") or (max(1, len(think) // 4) if think else 0))
        out_tokens += reasoning
        usage = {"prompt_tokens": sim["prompt"], "completion_tokens": out_tokens,
                 "total_tokens": sim["prompt"] + out_tokens,
                 "prompt_tokens_details": {"cached_tokens": sim["cached"]}}
        if reasoning:
            usage["completion_tokens_details"] = {"reasoning_tokens": reasoning}
        rec = {"seq": seq, "proto": "openai", "t": round(sim["now"], 3), "stream": bool(body.get("stream")),
               "model": body.get("model"), "n_messages": len(messages), "n_tools": len(tools),
               "tool_names": [n for n, _ in tool_defs], "tools_hash": tools_h, "msg_hashes": msg_h,
               "prompt_tokens": sim["prompt"], "cached_tokens": sim["cached"], "cache_creation_tokens": 0,
               "input_tokens": sim["prompt"] - sim["cached"], "output_tokens": out_tokens,
               "lcp_chars": sim["lcp"], "best_prev_seq": sim["best_seq"], "append_only": append_only,
               "first_diff": first_diff, "tools_changed": tools_changed, "n_calls_before": n_calls,
               "main": bool(tool_defs), "params": self.params_of(body), "reasoning_tokens": reasoning,
               "reply": "tool_call" if call else "text"}
        self.finish_log(rec, body)
        if body.get("stream"):
            return self.stream_openai(body, call, text, usage, seq, think)
        msg = {"role": "assistant", "content": text}
        if think:
            msg["reasoning_content"] = think
        if call:
            msg["tool_calls"] = [{"id": call["id"], "type": "function",
                                  "function": {"name": call["name"], "arguments": call["json"]}}]
        self._json(200, {"id": "chatcmpl-mock-%d" % seq, "object": "chat.completion",
                         "created": int(sim["now"]), "model": body.get("model") or "mock-model",
                         "choices": [{"index": 0, "message": msg,
                                      "finish_reason": "tool_calls" if call else "stop"}],
                         "usage": usage})

    def stream_openai(self, body, call, text, usage, seq, think=None):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        model = body.get("model") or "mock-model"
        cid = "chatcmpl-mock-%d" % seq
        created = int(time.time())

        def send(obj):
            self.wfile.write(b"data: " + json.dumps(obj).encode() + b"\n\n")
            self.wfile.flush()

        def chunk(delta, finish=None):
            return {"id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}

        send(chunk({"role": "assistant", "content": ""}))
        if think:
            for i in range(0, len(think), 40):
                send(chunk({"reasoning_content": think[i:i + 40]}))
        if text:
            words = text.split(" ")
            for i, w in enumerate(words):
                send(chunk({"content": w + (" " if i < len(words) - 1 else "")}))
        if call:
            send(chunk({"tool_calls": [{"index": 0, "id": call["id"], "type": "function",
                                        "function": {"name": call["name"], "arguments": ""}}]}))
            args = call["json"]
            mid = max(1, len(args) // 2)
            for part in (args[:mid], args[mid:]):
                send(chunk({"tool_calls": [{"index": 0, "function": {"arguments": part}}]}))
            send(chunk({}, "tool_calls"))
        else:
            send(chunk({}, "stop"))
        if (body.get("stream_options") or {}).get("include_usage", True):
            send({"id": cid, "object": "chat.completion.chunk", "created": created, "model": model,
                  "choices": [], "usage": usage})
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    # ------------------------------------------------------------ Anthropic wire
    @staticmethod
    def norm_msg(m):
        """Anthropic treats content "text" and [{"type":"text","text":"text"}] alike; Claude Code switches
        between the two forms when it moves cache breakpoints, so normalise before comparing prefixes."""
        if isinstance(m, dict) and isinstance(m.get("content"), str):
            m = dict(m)
            m["content"] = [{"type": "text", "text": m["content"]}]
        return m

    def chat_anthropic(self, body):
        tools = body.get("tools") or []
        system = body.get("system")
        messages = [self.norm_msg(m) for m in (body.get("messages") or [])]
        elements = [canon(strip_cc(t)) for t in tools]
        sys_blocks = system if isinstance(system, list) else (
            [{"type": "text", "text": system}] if system else [])
        elements += [canon(strip_cc(b)) for b in sys_blocks]
        n_head = len(elements)
        elements += [canon(strip_cc(m)) for m in messages]
        raw_elems = list(tools) + list(sys_blocks) + list(messages)
        bp = None
        for i, e in enumerate(raw_elems):
            if has_cc(e):
                bp = i
        tools_h = sha(canon(strip_cc(tools)))
        sys_h = sha(canon(strip_cc(system)))
        msg_h = [sha(c) for c in elements[n_head:]]
        with LOCK:
            sim = simulate_cache(elements, bp)
            HASHES[sim["seq"]] = (tools_h, sys_h, msg_h)
            append_only, first_diff, tools_changed = self.diff_info(sim["best_seq"], tools_h, sys_h, msg_h)
        n_calls = 0
        for m in messages:
            if m.get("role") == "assistant" and isinstance(m.get("content"), list):
                n_calls += sum(1 for b in m["content"] if isinstance(b, dict) and b.get("type") == "tool_use")
        tool_defs = [(t.get("name"), (t.get("input_schema") or {}).get("properties") or {})
                     for t in tools if isinstance(t, dict) and t.get("name")]
        text, call, step = self.plan(tool_defs, n_calls)
        if step and step.get("delay"):
            time.sleep(float(step["delay"]))
        seq = sim["seq"]
        if call:
            call["id"] = "toolu_%d_%s" % (seq, sha(str(sim["now"]))[:6])
            out_tokens = max(1, len(json.dumps(call["args"])) // 4) + (len(text or "") // 4)
        else:
            out_tokens = max(1, len(text or "") // 4)
        think = (step or {}).get("think")
        reasoning = int((step or {}).get("reasoning_tokens") or (max(1, len(think) // 4) if think else 0))
        out_tokens += reasoning
        if USAGE_MODE == "inclusive":
            usage = {"input_tokens": sim["prompt"], "cache_creation_input_tokens": 0,
                     "cache_read_input_tokens": sim["cached"], "output_tokens": out_tokens}
        elif USAGE_MODE == "exclusive":
            usage = {"input_tokens": sim["prompt"] - sim["cached"], "cache_creation_input_tokens": 0,
                     "cache_read_input_tokens": sim["cached"], "output_tokens": out_tokens}
        else:
            usage = {"input_tokens": sim["prompt"] - sim["cached"] - sim["creation"],
                     "cache_creation_input_tokens": sim["creation"],
                     "cache_read_input_tokens": sim["cached"], "output_tokens": out_tokens}
        rec = {"seq": seq, "proto": "anthropic", "t": round(sim["now"], 3), "stream": bool(body.get("stream")),
               "model": body.get("model"), "n_messages": len(messages), "n_tools": len(tools),
               "tool_names": [n for n, _ in tool_defs], "tools_hash": tools_h, "system_hash": sys_h,
               "msg_hashes": msg_h, "prompt_tokens": sim["prompt"], "cached_tokens": sim["cached"],
               "cache_creation_tokens": sim["creation"], "input_tokens": usage["input_tokens"],
               "output_tokens": out_tokens, "lcp_chars": sim["lcp"], "best_prev_seq": sim["best_seq"],
               "append_only": append_only, "first_diff": first_diff, "tools_changed": tools_changed,
               "n_calls_before": n_calls, "main": bool(tool_defs), "params": self.params_of(body),
               "reasoning_tokens": reasoning, "reply": "tool_call" if call else "text",
               "has_cache_control": bp is not None,
               "query": urllib.parse.urlparse(self.path).query}
        self.finish_log(rec, body)
        content = []
        if think:
            content.append({"type": "thinking", "thinking": think, "signature": "mocksig"})
        if text:
            content.append({"type": "text", "text": text})
        if call:
            content.append({"type": "tool_use", "id": call["id"], "name": call["name"], "input": call["args"]})
        if not content:
            content.append({"type": "text", "text": "OK"})
        stop = "tool_use" if call else "end_turn"
        msg_id = "msg_mock_%d" % seq
        model = body.get("model") or "mock-model"
        if not body.get("stream"):
            return self._json(200, {"id": msg_id, "type": "message", "role": "assistant", "model": model,
                                    "content": content, "stop_reason": stop, "stop_sequence": None,
                                    "usage": usage}, {"request-id": "req_mock_%d" % seq})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("request-id", "req_mock_%d" % seq)
        self.end_headers()

        def send(ev, obj):
            self.wfile.write(("event: %s\ndata: %s\n\n" % (ev, json.dumps(obj))).encode())
            self.wfile.flush()

        start_usage = dict(usage)
        start_usage["output_tokens"] = 1
        if USAGE_AT == "delta":
            start_usage.update(input_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0)
        send("message_start", {"type": "message_start", "message": {
            "id": msg_id, "type": "message", "role": "assistant", "model": model, "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": start_usage}})
        send("ping", {"type": "ping"})
        for idx, block in enumerate(content):
            if block["type"] == "thinking":
                send("content_block_start", {"type": "content_block_start", "index": idx,
                                             "content_block": {"type": "thinking", "thinking": "", "signature": ""}})
                for i in range(0, len(block["thinking"]), 40):
                    send("content_block_delta", {"type": "content_block_delta", "index": idx, "delta": {
                        "type": "thinking_delta", "thinking": block["thinking"][i:i + 40]}})
                send("content_block_delta", {"type": "content_block_delta", "index": idx, "delta": {
                    "type": "signature_delta", "signature": block["signature"]}})
            elif block["type"] == "text":
                send("content_block_start", {"type": "content_block_start", "index": idx,
                                             "content_block": {"type": "text", "text": ""}})
                words = block["text"].split(" ")
                for i, w in enumerate(words):
                    send("content_block_delta", {"type": "content_block_delta", "index": idx, "delta": {
                        "type": "text_delta", "text": w + (" " if i < len(words) - 1 else "")}})
            else:
                send("content_block_start", {"type": "content_block_start", "index": idx, "content_block": {
                    "type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}})
                args = json.dumps(block["input"])
                mid = max(1, len(args) // 2)
                for part in (args[:mid], args[mid:]):
                    send("content_block_delta", {"type": "content_block_delta", "index": idx, "delta": {
                        "type": "input_json_delta", "partial_json": part}})
            send("content_block_stop", {"type": "content_block_stop", "index": idx})
        send("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
                               "usage": (dict(usage) if USAGE_AT == "delta" else {"output_tokens": out_tokens})})
        send("message_stop", {"type": "message_stop"})
        self.close_connection = True

    @staticmethod
    def diff_info(best_seq, tools_h, sys_h, msg_h):
        if best_seq is None:
            return None, None, None
        pt, ps, pm = HASHES[best_seq]
        tools_changed = pt != tools_h
        sys_changed = ps != sys_h
        k = 0
        while k < len(pm) and k < len(msg_h) and pm[k] == msg_h[k]:
            k += 1
        append_only = (not tools_changed) and (not sys_changed) and k == len(pm)
        first_diff = None
        if not append_only:
            first_diff = "tools" if tools_changed else ("system" if sys_changed else k)
        return append_only, first_diff, tools_changed


def main():
    open(LOG, "a").close()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    srv.daemon_threads = True
    print("mock listening on 127.0.0.1:%d log=%s ttl=%ss" % (PORT, LOG, TTL), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
