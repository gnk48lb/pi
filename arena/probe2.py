#!/usr/bin/env python3
"""probe2 - read-only diagnostics for pi: config, prompt-cache health, WSL limits.

Stdlib only. Prints ONE redacted report (API keys/tokens are never printed, see scrub()).
  python3 ~/arena/probe2.py 2>&1 | tee ~/arena/probe2.out
Optional live check (sends 3 tiny requests, ~13k input tokens, well under $0.01, to YOUR
pi default provider, to see whether the gateway reports prompt-cache hits):
  PROBE_NET=1 python3 ~/arena/probe2.py 2>&1 | tee ~/arena/probe2.net.out
Nothing is written to disk by this script. It never executes "!command" apiKeys.
"""
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HOME = Path(os.path.expanduser("~"))
AGENT = Path(os.path.expanduser(os.environ.get("PI_CODING_AGENT_DIR") or str(HOME / ".pi" / "agent")))
OUT = []
SECRETS = set()
BORING = {"true", "false", "enabled", "disabled", "required", "optional", "password", "undefined"}
SECRET_KEY = re.compile(r"key|token|secret|passw|auth|cookie|credential|bearer|signature", re.I)
SECRET_TREES = {"env", "headers", "environment", "extraheaders", "extra_headers", "defaultheaders"}
ENVREF = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")
ENV_SECRET = re.compile(SECRET_KEY.pattern + r"|private|pwd|(?:^|_)sk(?:_|$)|(?:^|_)pat(?:_|$)", re.I)
SAFE_KEYS = {"id", "name", "model", "modelid", "defaultmodel", "defaultprovider", "provider", "api", "type", "source",
             "command", "baseurl", "url", "description", "version", "cwd", "path", "enabledmodels",
             "defaultthinkinglevel", "thinkinglevel", "transport", "theme", "reasoning"}


def token_like(s):
    return (len(s) >= 20 and not re.search(r"[\s/:\\]", s) and re.fullmatch(r"[A-Za-z0-9_\-.=+]+", s) is not None
            and re.search(r"\d", s) is not None and re.search(r"[A-Za-z]", s) is not None)


# ----------------------------------------------------------------- output / redaction
def emit(*a):
    OUT.append(" ".join(str(x) for x in a))


def hdr(t):
    emit("")
    emit("=== " + t + " ===")


def reg(v):
    """Remember a secret value so scrub() removes it from the whole report."""
    if isinstance(v, str):
        v = v.strip()
        if len(v) >= 8 and v.lower() not in BORING and not ENVREF.fullmatch(v):
            SECRETS.add(v)


def sp(p):
    s, h = str(p), str(HOME)
    return "~" + s[len(h):] if (s == h or s.startswith(h + os.sep)) else s


def sanitize_url(u):
    m = re.match(r"^([A-Za-z][A-Za-z0-9+.\-]*://)([^/?#]*)([^?#]*)(\?[^#]*)?(#.*)?$", u or "")
    if not m:
        return u
    scheme, auth, path, query, frag = m.groups()
    segs = path.split("/")
    for i, sg in enumerate(segs):             # long mixed alnum path segments look like embedded keys
        if len(sg) >= 20 and re.search(r"\d", sg) and re.search(r"[A-Za-z]", sg):
            reg(sg)
            segs[i] = "<segment redacted>"
    path = "/".join(segs)
    if "@" in auth:
        userinfo, host = auth.rsplit("@", 1)
        reg(userinfo)
        reg(userinfo.split(":", 1)[-1])
        auth = "<userinfo>@" + host
    if query:
        parts = []
        for kv in query[1:].split("&"):
            k, _, v = kv.partition("=")
            if v:
                reg(v)
                parts.append(k + "=<redacted>")
            else:
                parts.append(k)
        query = "?" + "&".join(parts)
    return scheme + auth + path + (query or "") + (frag or "")


def redact_json(o, key=None, secret=False):
    """Structural redaction: values under secret-looking keys (or env/headers trees) are hidden."""
    if isinstance(o, dict):
        return {k: redact_json(v, k, secret or (isinstance(k, str) and k.lower() in SECRET_TREES))
                for k, v in o.items()}
    if isinstance(o, list):
        out, hide_next = [], False
        for x in o:
            if isinstance(x, str):
                if hide_next and not x.startswith("-"):
                    hide_next = False
                    if ENVREF.fullmatch(x.strip()):
                        out.append(x)
                    else:
                        reg(x)
                        out.append("<redacted %d chars>" % len(x))
                    continue
                hide_next = False
                m = re.match(r"^(--?[\w\-]*(?:key|token|secret|passw\w*|auth\w*)[\w\-]*)(=(.*))?$", x, re.I)
                if m:
                    if m.group(2):                 # --api-key=VALUE
                        reg(m.group(3))
                        out.append(m.group(1) + "=<redacted>")
                        continue
                    hide_next = True               # --api-key VALUE (value is the next element)
            out.append(redact_json(x, key, secret))
        return out
    if isinstance(o, str):
        if secret or (key is not None and SECRET_KEY.search(str(key))):
            if ENVREF.fullmatch(o.strip()):
                return o                      # "$MY_ENV_VAR" names an env var, not a secret
            reg(o)
            return "<shell command hidden>" if o.startswith("!") else "<redacted %d chars>" % len(o)
        if re.match(r"^[A-Za-z][A-Za-z0-9+.\-]*://", o):
            return sanitize_url(o)
        if token_like(o) and str(key).lower() not in SAFE_KEYS:
            reg(o)                             # unknown field holding a key-looking string
            return "<token-like value hidden, %d chars>" % len(o)
        return o
    return o                                   # numbers / bools / null pass through


PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "sk-<redacted>"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"), "gh_<redacted>"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "github_pat_<redacted>"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"), "AIza<redacted>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "xox-<redacted>"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=\-]{8,}", re.I), "Bearer <redacted>"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "<jwt redacted>"),
    (re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"), "<userinfo>"),
    (re.compile(r"""(?i)((?:[\w\-]*(?:key|token|secret|passw(?:or)?d|pwd|auth|credential|bearer|signature)[\w\-]*)["']?\s*[:=]\s*["'`])(?![<$])([^"'`\n]{8,})(["'`])"""),
     r"\1<redacted>\3"),
    (re.compile(r"\bBasic\s+(?=[A-Za-z0-9._~+/=\-]*[0-9=+/])[A-Za-z0-9._~+/=\-]{12,}"), "Basic <redacted>"),
    (re.compile(r"(?i)(--?[\w\-]*(?:key|token|secret|passw\w*)[\w\-]*[=\s]+)(\S{6,})"), r"\1<redacted>"),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "<hex redacted>"),
    (re.compile(r"\b(?![0-9a-fA-F]{8}-[0-9a-fA-F]{4}-)(?=[A-Za-z0-9_\-]*[A-Za-z])(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{32,}\b"),
     "<token-like redacted>"),
    (re.compile(r"\b(?:tvly|gsk|hf|glpat|pplx|xai|nvapi|fc|r8|sk_live|sk_test|pk_live|rk_live)[-_][A-Za-z0-9_\-]{16,}"), "<key redacted>"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "<aws key redacted>"),
    (re.compile(r"\bya29\.[A-Za-z0-9_\-]{20,}"), "<google token redacted>"),
    (re.compile(r"(?i)([?&;](?:api[_\-]?key|key|token|access_token|secret|password|auth|sig|signature)=)[^&\s\"'<>]+"), r"\1<redacted>"),
    (re.compile(r"(?i)((?:api[_\-]?key|x-api-key|secret|token|passw(?:or)?d|authorization|bearer)[A-Za-z0-9_\-]*\s*[:=]\s*)(?![<$\"'`])([A-Za-z0-9_\-=+/]{12,})"),
     lambda m: m.group(1) + ("<redacted>" if re.search(r"\d", m.group(2)) else m.group(2))),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"), r"C:\\Users\\<user>"),
]


def scrub(text):
    for s in sorted(SECRETS, key=len, reverse=True):
        text = text.replace(s, "<redacted>")
    for rx, rep in PATTERNS:
        text = rx.sub(rep, text)
    text = re.sub(r"/mnt/c/Users/[^/\s]+", "/mnt/c/Users/<user>", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)      # no terminal escape sequences from file contents
    return text.replace(str(HOME), "~")


def collect_env_secrets():
    for k, v in os.environ.items():
        if ENV_SECRET.search(k):
            reg(v)


# ----------------------------------------------------------------- small helpers
def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except FileNotFoundError:
        return "<not found>"
    except subprocess.TimeoutExpired:
        return "<timeout>"
    except Exception as e:
        return "<error %s>" % type(e).__name__


def read_text(p, limit=3_000_000):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except Exception:
        return None


def read_json(p):
    t = read_text(p)
    if t is None:
        return None, "absent"
    try:
        return json.loads(t), None
    except Exception as e:
        t2 = re.sub(r"^\s*//.*$", "", t, flags=re.M)
        t2 = re.sub(r",(\s*[}\]])", r"\1", t2)
        try:
            return json.loads(t2), None
        except Exception:
            return None, "invalid JSON (%s) - not printed" % type(e).__name__


def est_tokens(s):
    a = sum(1 for ch in s if ord(ch) < 128)
    return int(a / 4 + (len(s) - a) / 1.5)


def cap_text(t, cap):
    if len(t) <= cap:
        return t
    head, tail = t[: cap * 2 // 3], t[-(cap // 3):]
    return head + "\n...[%d chars omitted]...\n" % (len(t) - len(head) - len(tail)) + tail


def show_text(label, path, cap):
    t = read_text(path)
    if t is None:
        emit("%s: (absent)" % label)
        return 0
    emit("%s: %d chars ~ %d tokens" % (label, len(t), est_tokens(t)))
    emit("--- begin %s ---" % label)
    emit(cap_text(t, cap).rstrip())
    emit("--- end %s ---" % label)
    return min(len(t), cap)


def show_json(label, obj, cap=6000):
    emit(label + ":")
    emit(cap_text(json.dumps(redact_json(obj), indent=2, ensure_ascii=False), cap))


def tree(path, depth=2, cap=50):
    lines = []

    def walk(p, d, prefix):
        try:
            ents = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        except Exception:
            return
        for e in ents:
            if len(lines) >= cap:
                return
            if e.name in ("node_modules", ".git", "__pycache__"):
                lines.append(prefix + e.name + "/ (skipped)")
                continue
            try:
                size = e.stat().st_size if e.is_file() else None
            except Exception:
                size = None
            lines.append(prefix + e.name + ("/" if e.is_dir() else " (%d B)" % size))
            if e.is_dir() and d > 1:
                walk(e, d - 1, prefix + "  ")

    walk(path, depth, "  ")
    if len(lines) >= cap:
        lines.append("  ...(truncated)")
    return lines


def safe(fn):
    try:
        fn()
    except Exception as e:
        emit("!! section %s failed: %s: %s" % (fn.__name__, type(e).__name__, e))


# ----------------------------------------------------------------- section: overview
def sec_overview():
    hdr("overview")
    emit("time:", datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
    emit("python:", sys.version.split()[0], "| home:", "~", "| pi agent dir:", sp(AGENT), "(exists)" if AGENT.is_dir() else "(MISSING)")
    for exe in ("pi", "claude", "node", "docker"):
        w = shutil.which(exe)
        v = run([exe, "--version"], 20).splitlines()[:1] if w else ["-"]
        emit("%-7s %s  %s" % (exe, sp(w) if w else "NOT FOUND", v[0] if v else ""))
    emit("PI_CODING_AGENT_DIR set:", bool(os.environ.get("PI_CODING_AGENT_DIR")))


# ----------------------------------------------------------------- section: pi config
def load_cfg(name):
    obj, err = read_json(AGENT / name)
    return obj, err


def sec_pi_config():
    hdr("pi config dir listing: " + sp(AGENT))
    try:
        ents = sorted(AGENT.iterdir(), key=lambda x: x.name)
        for e in ents[:60]:
            emit("  %s%s" % (e.name, "/" if e.is_dir() else " (%d B)" % e.stat().st_size))
    except Exception as ex:
        emit("cannot list:", type(ex).__name__)

    settings, err = load_cfg("settings.json")
    hdr("settings.json")
    if settings is None:
        emit(err)
        settings = {}
    else:
        show_json("settings.json (redacted)", settings)

    models, err = load_cfg("models.json")
    hdr("models.json")
    if models is None:
        emit(err)
        models = {}
    else:
        provs = models.get("providers") or {}
        for name, p in provs.items():
            if not isinstance(p, dict):
                continue
            key = p.get("apiKey")
            reg(key if isinstance(key, str) and not key.startswith("$") else "")
            if isinstance(key, str) and ENVREF.fullmatch(key.strip()):
                var = key.strip().strip("${}")
                kind = "env %s (%s)" % (key, "SET, %d chars" % len(os.environ[var]) if os.environ.get(var) else "NOT SET")
            elif isinstance(key, str) and key.startswith("!"):
                kind = "shell command (hidden, not executed)"
            elif isinstance(key, str):
                kind = "literal key in file (%d chars)" % len(key)
            else:
                kind = "none"
            emit("provider %s: baseUrl=%s api=%s apiKey=%s" % (name, sanitize_url(str(p.get("baseUrl", ""))), p.get("api"), kind))
            for m in p.get("models") or []:
                if isinstance(m, dict):
                    mm = redact_json(m)
                    emit("   model %s ctx=%s maxTokens=%s reasoning=%s cost=%s promptCache=%s" % (
                        mm.get("id"), mm.get("contextWindow"), mm.get("maxTokens"), mm.get("reasoning"),
                        json.dumps(mm.get("cost")), json.dumps(mm.get("promptCache"))))
        show_json("models.json (redacted)", models, 5000)

    mcp, err = load_cfg("mcp.json")
    if mcp is not None:
        hdr("mcp.json")
        show_json("mcp.json (redacted)", mcp, 4000)

    hdr("auth.json (provider names only)")
    auth, err = load_cfg("auth.json")
    if auth is None:
        emit(err)
    else:
        def leaves(o):
            if isinstance(o, dict):
                for v in o.values():
                    yield from leaves(v)
            elif isinstance(o, list):
                for v in o:
                    yield from leaves(v)
            elif isinstance(o, str):
                yield o
        for v in leaves(auth):
            reg(v)
        emit("providers with stored credentials:", sorted(auth.keys()) if isinstance(auth, dict) else "?")

    hdr("context files (part of the static prompt prefix)")
    for nm, cap in (("AGENTS.md", 7000), ("SYSTEM.md", 7000), ("APPEND_SYSTEM.md", 7000)):
        show_text(nm, AGENT / nm, cap)
    for nm in ("AGENTS.md", "CLAUDE.md", "SYSTEM.md", "APPEND_SYSTEM.md"):
        pth = Path.cwd() / nm
        if pth.exists():
            emit("(note: cwd also has %s, %d chars)" % (nm, len(read_text(pth) or "")))
    pdot = Path.cwd() / ".pi"
    if pdot.is_dir():
        emit("(note: cwd has a .pi/ directory:", ", ".join(sorted(x.name for x in pdot.iterdir())[:20]) + ")")

    hdr("extensions")
    budget = 26000
    ext_dir = AGENT / "extensions"
    if not ext_dir.is_dir():
        emit("(none)")
    else:
        srcs = []
        for p in sorted(ext_dir.iterdir()):
            if p.is_file() and p.suffix in (".ts", ".js", ".mjs", ".cjs"):
                srcs.append(p)
            elif p.is_dir():
                emit("dir", p.name + "/")
                for ln in tree(p, 2, 30):
                    emit(ln)
                cands = []
                for root, dirs, fnames in os.walk(str(p)):          # bounded; never follows symlinks, skips node_modules
                    dirs[:] = sorted(x for x in dirs if x not in ("node_modules", ".git"))[:20]
                    if root[len(str(p)):].count(os.sep) >= 3:
                        dirs[:] = []
                    cands += [Path(root) / f for f in sorted(fnames) if f.endswith((".ts", ".js", ".mjs", ".cjs"))]
                    if len(cands) >= 3:
                        break
                srcs.extend(cands[:3])
        for p in srcs:
            if budget <= 500:
                emit("(budget exhausted; skipped %s)" % sp(p))
                continue
            budget -= show_text("extension " + sp(p), p, min(budget, 14000))

    hdr("packages (settings.json -> packages)")
    pk = settings.get("packages") if isinstance(settings, dict) else None
    if not pk:
        emit("(none)")
    for item in pk or []:
        src = item if isinstance(item, str) else (item.get("source") if isinstance(item, dict) else None)
        emit("package:", json.dumps(redact_json(item), ensure_ascii=False)[:300])
        if not isinstance(src, str):
            continue
        cand = None
        if src.startswith(("/", "~", "./", "../")):
            for base in (Path(os.path.expanduser(src)), AGENT / src, Path.cwd() / src):
                if base.is_dir():
                    cand = base.resolve()
                    break
            if cand is None:
                emit("  local path NOT FOUND:", sp(src))
                continue
            emit("  local dir:", sp(cand))
            pj, _ = read_json(cand / "package.json")
            if isinstance(pj, dict):
                keep = {k: pj.get(k) for k in ("name", "version", "description", "main", "type", "pi", "keywords") if k in pj}
                keep["dependencies"] = sorted((pj.get("dependencies") or {}).keys())
                keep["scripts"] = sorted((pj.get("scripts") or {}).keys())
                emit("  package.json (whitelisted):", json.dumps(redact_json(keep), ensure_ascii=False)[:1200])
            for ln in tree(cand, 2, 45):
                emit(ln)

    for sub in ("skills", "prompts", "themes"):
        d = AGENT / sub
        if d.is_dir():
            names = sorted(x.name for x in d.iterdir())
            emit("%s/: %s" % (sub, ", ".join(names[:40]) or "(empty)"))


# ----------------------------------------------------------------- section: sessions / cache health
def parse_ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def num(x):
    try:
        return int(x)
    except Exception:
        return 0


def fnum(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def fmt_ts(t, fmt):
    try:
        return datetime.datetime.fromtimestamp(t).strftime(fmt) if t else "?"
    except (OverflowError, OSError, ValueError, TypeError):
        return "?"


def scan_session(path):
    ev, cwd = [], None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if len(line) < 2 or len(line) > 30_000_000:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            t, ts = d.get("type"), parse_ts(d.get("timestamp"))
            if t == "session":
                cwd = d.get("cwd")
            elif t == "message":
                m = d.get("message")
                if not isinstance(m, dict):
                    continue
                role = m.get("role")
                if role == "assistant":
                    u = m.get("usage") if isinstance(m.get("usage"), dict) else {}
                    c = u.get("cost") if isinstance(u.get("cost"), dict) else {}
                    ev.append(("req", ts, m.get("model"), m.get("thinkingLevel"),
                               num(u.get("input")), num(u.get("cacheRead")), num(u.get("cacheWrite")),
                               num(u.get("output")), fnum(c.get("total")), m.get("stopReason")))
                elif role == "system":
                    secs = m.get("sections") if isinstance(m.get("sections"), dict) else {}
                    info = {"sections": {k: len(v) for k, v in secs.items() if isinstance(v, str)},
                            "content_chars": len(m.get("content") or "") if isinstance(m.get("content"), str) else 0,
                            "added": [(x.get("name"), len(json.dumps(x))) for x in (m.get("toolsAdded") or []) if isinstance(x, dict)],
                            "removed": [(x if isinstance(x, str) else x.get("name")) for x in (m.get("toolsRemoved") or [])
                                        if isinstance(x, (str, dict))]}
                    ev.append(("sys", ts, info))
                else:
                    ev.append(("in", ts))
            elif t == "compaction":
                ev.append(("compaction", ts, d.get("tokensBefore")))
            elif t == "model_change":
                ev.append(("model_change", ts, "%s/%s" % (d.get("provider"), d.get("modelId"))))
            elif t == "thinking_level_change":
                ev.append(("thinking", ts, d.get("thinkingLevel")))
            elif t == "context_edit":
                ev.append(("context_edit", ts, None))
    return cwd, ev


CAUSE_ORDER = ["compaction", "model_change", "thinking", "system", "context_edit"]


def analyze(ev):
    reqs, cliffs = [], []
    prev, pending, last_in, comps = None, [], None, []
    for e in ev:
        k = e[0]
        if k == "req":
            _, ts, model, think, inp, cr, cw, out, cost, stop = e
            total = inp + cr + cw
            if total <= 0:
                pending = []
                continue
            start = last_in if last_in is not None else ts
            gap = (start - prev["end"]) if (prev and prev["end"] and start) else None
            flag = ""
            if prev:
                lost = prev["total"] - cr
                if lost >= max(3000, 0.4 * prev["total"]):
                    cause = next((c for c in CAUSE_ORDER if c in pending), None)
                    if cause is None:
                        cause = "idle>5min" if (gap is not None and gap > 290) else "unexplained"
                    cliffs.append({"i": len(reqs), "lost": lost, "cause": cause, "gap": gap, "total": total})
                    flag = cause
            reqs.append({"i": len(reqs), "total": total, "cr": cr, "cw": cw, "inp": inp, "out": out,
                         "cost": cost, "model": model, "think": think, "gap": gap, "flag": flag, "ts": ts})
            prev = {"total": total, "end": ts}
            pending = []
        elif k == "in":
            last_in = e[1]
        elif k == "compaction":
            pending.append("compaction")
            comps.append(e[2])
        else:
            pending.append("system" if k == "sys" else k)
    if not any(r["cr"] > 0 for r in reqs):         # cache never worked/was never reported -> "cliffs" are meaningless
        cliffs = []
        for r in reqs:
            r["flag"] = ""
    return reqs, cliffs, comps


def fmt_k(n):
    return "%.1fk" % (n / 1000.0) if n >= 1000 else str(int(n))


def sec_sessions():
    settings, _ = load_cfg("settings.json")
    sdir = AGENT / "sessions"
    if isinstance(settings, dict) and isinstance(settings.get("sessionDir"), str):
        sdir = Path(os.path.expanduser(settings["sessionDir"]))
    stats = []
    try:
        for p in (sdir.rglob("*.jsonl") if sdir.is_dir() else []):
            try:
                stt = p.stat()
                stats.append((stt.st_mtime, stt.st_size, p))
            except OSError:
                continue                       # dangling symlink / permission problem
    except OSError:
        pass
    stats.sort(key=lambda x: x[0], reverse=True)
    files = [p for _, _, p in stats]
    mtimes = {p: mt for mt, _, p in stats}
    hdr("sessions: " + sp(sdir))
    if not files:
        emit("no session files found")
        return
    emit("%d session files, %.1f MB total; newest %s; oldest %s" % (
        len(files), sum(s for _, s, _ in stats) / 1e6, fmt_ts(stats[0][0], "%Y-%m-%d %H:%M"), fmt_ts(stats[-1][0], "%Y-%m-%d %H:%M")))
    files = files[:150]

    rows, glob_c = [], {"req": 0, "inp": 0, "cr": 0, "cw": 0, "out": 0, "cost": 0.0, "cliffs": 0, "lost": 0}
    by_cause, no_acct = {}, 0
    firsts = []
    for p in files:
        try:
            cwd, ev = scan_session(p)
        except Exception as e:
            emit("  (cannot read %s: %s)" % (p.name[:19], type(e).__name__))
            continue
        reqs, cliffs, comps = analyze(ev)
        if not reqs:
            continue
        sysev = [e for e in ev if e[0] == "sys"]
        tot_in = sum(r["inp"] for r in reqs)
        tot_cr = sum(r["cr"] for r in reqs)
        tot_cw = sum(r["cw"] for r in reqs)
        prompt = tot_in + tot_cr + tot_cw
        hit = (100.0 * tot_cr / prompt) if prompt else 0.0
        if len(reqs) >= 3 and tot_cr == 0 and tot_cw == 0:
            no_acct += 1
        firsts.append(reqs[0]["total"])
        for r in reqs:
            glob_c["req"] += 1
        glob_c["inp"] += tot_in
        glob_c["cr"] += tot_cr
        glob_c["cw"] += tot_cw
        glob_c["out"] += sum(r["out"] for r in reqs)
        glob_c["cost"] += sum(r["cost"] for r in reqs)
        for c in cliffs:
            glob_c["cliffs"] += 1
            glob_c["lost"] += c["lost"]
            by_cause[c["cause"]] = by_cause.get(c["cause"], 0) + 1
        models = sorted({str(r["model"]) for r in reqs})
        rows.append({"p": p, "cwd": cwd, "models": models, "reqs": reqs, "comps": comps, "cliffs": cliffs,
                     "hit": hit, "cost": sum(r["cost"] for r in reqs), "sysev": sysev,
                     "start": reqs[0]["ts"] or mtimes.get(p, 0)})
    rows.sort(key=lambda x: x["start"], reverse=True)
    latest_reqs = next((x for x in rows if len(x["reqs"]) >= 4), None)
    latest_with_sys = next((x for x in rows if x["sysev"]), None)

    emit("")
    emit("GLOBAL (latest %d files): requests=%d | prompt tokens=%s (cached %s = %.1f%%, cache-write %s) | output=%s | pi-computed cost=$%.4f" % (
        len(files), glob_c["req"], fmt_k(glob_c["inp"] + glob_c["cr"] + glob_c["cw"]), fmt_k(glob_c["cr"]),
        100.0 * glob_c["cr"] / max(1, glob_c["inp"] + glob_c["cr"] + glob_c["cw"]), fmt_k(glob_c["cw"]),
        fmt_k(glob_c["out"]), glob_c["cost"]))
    if firsts:
        firsts.sort()
        emit("first-request prompt size (static prefix + first user message): min %s, median %s, max %s tokens" % (
            fmt_k(firsts[0]), fmt_k(firsts[len(firsts) // 2]), fmt_k(firsts[-1])))
    emit("sessions with >=3 requests but ZERO cache accounting (cacheRead=cacheWrite=0 everywhere): %d of %d" % (no_acct, len(rows)))
    if glob_c["cost"] == 0 and glob_c["req"]:
        emit("NOTE: pi-computed cost is $0 everywhere -> models.json has no `cost` prices for this model; cost numbers are meaningless until added.")
    emit("cache cliffs (lost >= max(3k, 40%% of previous prompt)): %d, lost tokens %s; by cause: %s" % (
        glob_c["cliffs"], fmt_k(glob_c["lost"]), json.dumps(by_cause, sort_keys=True)))

    emit("")
    emit("PER SESSION (newest first, up to 14):  start | model | reqs | first->peak ctx | cache hit% | compactions | cliffs(cause) | $ | cwd")
    for x in rows[:14]:
        cwd, models, reqs, comps, cliffs, hit, cost = x["cwd"], x["models"], x["reqs"], x["comps"], x["cliffs"], x["hit"], x["cost"]
        st = fmt_ts(reqs[0]["ts"], "%m-%d %H:%M")
        cl = ",".join("#%d:%s(-%s)" % (c["i"], c["cause"], fmt_k(c["lost"])) for c in cliffs[:5]) + ("..." if len(cliffs) > 5 else "")
        emit("  %s | %s | %3d | %s->%s | %5.1f%% | %d%s | %s | $%.4f | %s" % (
            st, ",".join(models)[:40], len(reqs), fmt_k(reqs[0]["total"]), fmt_k(max(r["total"] for r in reqs)),
            hit, len(comps), ("(" + ",".join(fmt_k(x or 0) for x in comps[:3]) + ")") if comps else "",
            cl or "-", cost, sp(cwd or "?")[-40:]))

    if latest_reqs:
        reqs = latest_reqs["reqs"]
        emit("")
        emit("LATEST SESSION WITH >=4 REQUESTS, request-by-request (first 45):")
        emit("   #   prompt   cacheRead   hit%   fresh(in+write)  gap_s  note")
        for r in reqs[:45]:
            emit("  %3d  %7s  %9s  %5.1f  %14s  %5s  %s" % (
                r["i"], fmt_k(r["total"]), fmt_k(r["cr"]), 100.0 * r["cr"] / r["total"], fmt_k(r["inp"] + r["cw"]),
                ("%d" % r["gap"]) if r["gap"] is not None else "-", r["flag"]))
        if len(reqs) > 45:
            emit("  ... %d more requests" % (len(reqs) - 45))

    if latest_with_sys:
        sysev = latest_with_sys["sysev"]
        emit("")
        hdr("static prefix anatomy (from the newest session that logged its system message)")
        first = sysev[0][2]
        secs = first["sections"]
        tot = sum(secs.values())
        emit("system message sections (chars, ~tokens @ ~3.5 chars/token):")
        for k, n in secs.items():
            emit("  %-12s %7d chars  ~%d tokens" % (k, n, n / 3.5))
        if first["content_chars"]:
            emit("  (plain content: %d chars)" % first["content_chars"])
        emit("  total sections: %d chars ~ %d tokens" % (tot, tot / 3.5))
        tl = first["added"]
        tsum = sum(n for _, n in tl)
        emit("tools registered at start (%d): %s" % (len(tl), ", ".join("%s(%d B)" % (a, b) for a, b in tl)))
        emit("  tool schemas total: %d chars ~ %d tokens" % (tsum, tsum / 3.5))
        if len(sysev) > 1:
            emit("later system-message entries in that session: %d (each is a prefix change -> cache break)" % (len(sysev) - 1))
            for e in sysev[1:4]:
                emit("   added=%s removed=%s" % ([a for a, _ in e[2]["added"]], e[2]["removed"]))


# ----------------------------------------------------------------- section: WSL / docker / proxy
def sec_wsl():
    hdr("machine / WSL")
    mi = read_text("/proc/meminfo") or ""

    def kb(name):
        m = re.search(r"^%s:\s+(\d+) kB" % name, mi, re.M)
        return int(m.group(1)) if m else None
    mt, st = kb("MemTotal"), kb("SwapTotal")
    emit("MemTotal %.2f GB | SwapTotal %.2f GB | cpus %s | kernel %s" % (
        (mt or 0) / 1048576.0, (st or 0) / 1048576.0, os.cpu_count(), run(["uname", "-r"])))
    wc = read_text("/etc/wsl.conf")
    emit("/etc/wsl.conf:", "(absent)" if wc is None else "")
    if wc:
        emit(cap_text(wc.strip(), 1500))
    cfgs = glob.glob(os.environ.get("PROBE_WSLCONFIG_GLOB", "/mnt/c/Users/*/.wslconfig"))
    for c in cfgs:
        emit(".wslconfig (/mnt/c/Users/<user>/.wslconfig):")
        emit(cap_text((read_text(c) or "").strip(), 2000))
    if not cfgs:
        emit(".wslconfig: none found under /mnt/c/Users/*/ -> WSL defaults apply (memory = 50% of host RAM, swap = 25% of memory) - or the file lives elsewhere")
    emit("wslinfo --networking-mode:", run(["wslinfo", "--networking-mode"], 5))
    if shutil.which("docker"):
        out = run(["docker", "info", "--format", "server={{.ServerVersion}} ncpu={{.NCPU}} mem_bytes={{.MemTotal}} os={{.OperatingSystem}}"], 12)
        m = re.search(r"mem_bytes=(\d+)", out)
        if m and re.search(r"server=\S", out):
            emit("docker:", out.splitlines()[0][:300], "(= %.2f GB)" % (int(m.group(1)) / 1e9))
        else:
            emit("docker: installed but the daemon is not reachable:", (out.splitlines() or ["?"])[-1][:200])
    else:
        emit("docker: not installed in this distro")
    emit("disk free in ~: %.0f GB" % (shutil.disk_usage(str(HOME)).free / 1e9))


def proxy_clean(v):
    m = re.match(r"^([A-Za-z][A-Za-z0-9+.\-]*://)?(?:([^@/]*)@)?([^/\s]+)", v.strip())
    if not m:
        return "<unparsed>"
    scheme, userinfo, host = m.groups()
    if userinfo:
        reg(userinfo)
        reg(userinfo.split(":", 1)[-1])
    return (scheme or "") + host


def sec_proxy():
    hdr("proxy env (host:port only)")
    seen = False
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        for n in (name, name.lower()):
            v = os.environ.get(n)
            if v:
                seen = True
                emit("%s = %s" % (n, v[:300] if name == "NO_PROXY" else proxy_clean(v)))
    if not seen:
        emit("(no proxy variables set)")


# ----------------------------------------------------------------- optional live cache probe
def usage_numbers(u, prefix=""):
    out = {}
    if isinstance(u, dict):
        for k, v in u.items():
            out.update(usage_numbers(v, prefix + k + "."))
    elif isinstance(u, (int, float)) and not isinstance(u, bool):
        out[prefix.rstrip(".")] = u
    return out


def sec_net():
    hdr("live cache probe (PROBE_NET=1): 3 identical-prefix requests to your pi default provider")
    settings, _ = load_cfg("settings.json")
    models, _ = load_cfg("models.json")
    settings, models = settings or {}, models or {}
    prov, mid = settings.get("defaultProvider"), settings.get("defaultModel")
    p = (models.get("providers") or {}).get(prov)
    if not isinstance(p, dict):
        emit("default provider %r is not defined in models.json (built-in provider?) -> skipped" % prov)
        return
    if p.get("api") != "openai-completions":
        emit("api=%r is not openai-completions -> skipped" % p.get("api"))
        return
    key = p.get("apiKey")
    if isinstance(key, str) and ENVREF.fullmatch(key.strip()):
        key = os.environ.get(key.strip().strip("${}"))
    elif isinstance(key, str) and key.startswith("!"):
        emit("apiKey is a shell command; the probe never executes those -> skipped")
        return
    if not key:
        emit("no usable apiKey (env var unset?) -> skipped")
        return
    reg(key)
    ids = [m.get("id") for m in (p.get("models") or []) if isinstance(m, dict)]
    model = mid if (mid in ids or not ids) else ids[0]
    url = str(p.get("baseUrl", "")).rstrip("/") + "/chat/completions"
    emit("target:", sanitize_url(url), "| model:", model)
    filler = "".join("Section %04d: stable filler text used only to build a long identical prefix for a cache test.\n" % i for i in range(330))
    got_hit = False
    for n in range(1, int(os.environ.get("PROBE_NET_CALLS", "3")) + 1):
        body = {"model": model, "stream": False, "max_tokens": 16,
                "messages": [{"role": "system", "content": filler},
                             {"role": "user", "content": "Reply with one word: ok (%d)" % n}]}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + key, "User-Agent": "probe2/1.0"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
                status = r.status
        except urllib.error.HTTPError as e:
            raw = (e.read() or b"").decode("utf-8", "replace")
            try:
                ej = json.loads(raw)
                er = ej.get("error", ej) if isinstance(ej, dict) else {}
                msg = " ".join(str(er.get(k)) for k in ("type", "code", "message") if isinstance(er, dict) and er.get(k))
            except Exception:
                msg = raw
            msg = " ".join(w for w in msg.split() if "*" not in w and "…" not in w)[:160]   # drop masked-key echoes
            emit("call %d: HTTP %s %s" % (n, e.code, msg))
            break
        except Exception as e:
            emit("call %d: %s: %s" % (n, type(e).__name__, str(e)[:200]))
            break
        nums = usage_numbers(data.get("usage") or {})
        cached = {k: v for k, v in nums.items()
                  if "cache" in k.lower() and "miss" not in k.lower() and any(w in k.lower() for w in ("hit", "cached", "read"))}
        if any(v > 0 for v in cached.values()):
            got_hit = True
        emit("call %d: HTTP %s %.1fs usage=%s" % (n, status, time.time() - t0, json.dumps(nums, sort_keys=True)))
        time.sleep(float(os.environ.get("PROBE_NET_SLEEP", "4")))
    emit("VERDICT:", "cache hit reported by the gateway" if got_hit else
         "NO cache hit reported (gateway may not pass cache fields through, caching may be off on this route, or the prefix is below the provider minimum)")


# ----------------------------------------------------------------- main
def main():
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        return
    collect_env_secrets()
    for fn in (sec_overview, sec_pi_config, sec_sessions, sec_wsl, sec_proxy):
        safe(fn)
    if os.environ.get("PROBE_NET") == "1":
        safe(sec_net)
    hdr("end of report")
    print(scrub("\n".join(OUT)))


if __name__ == "__main__":
    main()
