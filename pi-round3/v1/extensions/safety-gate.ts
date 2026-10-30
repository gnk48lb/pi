/**
 * safety-gate.ts: a seatbelt, not a sandbox.
 *
 * Runs before every tool call. A call that matches a rule needs your OK (interactive mode) or is refused with
 * a reason the model can read (print / json mode, where nobody can answer). It costs 0 prompt tokens:
 * an extension is code that runs in pi's process, not text in the model's context.
 *
 *   bash          rm -r, sudo, git push / reset --hard / clean -f / branch -D / stash drop, curl | sh,
 *                 mkfs / dd, publishing a package, dumping the environment ...
 *   write / edit  .git/, node_modules/, .env*, key files, and anything outside the project folder (/tmp is fine)
 *   read / bash   files that hold secrets (.env, ~/.ssh, cloud credentials): whatever the model reads is
 *                 sent to the model provider
 *
 * What it cannot do: a determined or confused model can get around a pattern list (a script that deletes things,
 * `find -delete`, ...). For real isolation run pi inside a container or VM (see examples/extensions/sandbox).
 * Tune it: edit the tables below. Switch it off for one run: PI_SAFETY_GATE=off pi
 */
import { existsSync, realpathSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, resolve, sep } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

interface Rule {
	id: string;
	why: string;
	re: RegExp;
	/** return true to let a command through even though `re` matched */
	exempt?: (command: string) => boolean;
}

// ---- 1. bash commands that need a yes -----------------------------------------------------------------------
// `git -C repo -c k=v --no-pager <subcommand> ...`: skip git's own options, then match the subcommand.
const git = (sub: string) =>
	new RegExp(String.raw`\bgit\s+(?:(?:-[Cc]|--git-dir|--work-tree|--namespace)\s+\S+\s+|--[\w-]+(?:=\S+)?\s+|-[a-zA-Z]\s+)*` + sub);

// `rm -rf build dist` is routine clean-up: let it through when every target is a relative path that names a
// regenerable folder (or a /tmp path). Anything else, or anything we cannot read with confidence, asks.
const RM_RECURSIVE = /\brm\s+(?:-\S+\s+)*(?:-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)(?=\s|$)/;
const REGENERABLE = new Set([
	"build", "dist", "target", "out", "obj", "tmp", ".tmp", ".cache", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache",
	".ruff_cache", ".next", ".nuxt", ".turbo", ".parcel-cache", "coverage", ".coverage", "htmlcov",
]);

function rmTargetIsRegenerable(raw: string): boolean {
	const w = raw.replace(/^['"]+|['"]+$/g, "").replace(/\/+$/, "");
	if (!w || w === "." || w.includes("..") || w.startsWith("~")) return false;
	if (w.startsWith("/")) return /^\/tmp\/[^/]/.test(w) || w.startsWith(`${tmpdir().replace(/\/+$/, "")}/`);
	const parts = w.split("/");
	const last = parts[parts.length - 1];
	return parts.some((p) => REGENERABLE.has(p)) || /\.py[co]$/.test(last) || last === ".DS_Store";
}

export function rmOnlyRegenerable(command: string): boolean {
	for (const seg of command.split(/&&|\|\||[;|\n]/)) {
		if (!RM_RECURSIVE.test(seg)) continue;
		if (/[$`(]/.test(seg)) return false; // substitution: cannot judge
		const words = seg.trim().split(/\s+/);
		const targets = words.slice(words.indexOf("rm") + 1).filter((w) => !w.startsWith("-"));
		if (targets.length === 0 || !targets.every(rmTargetIsRegenerable)) return false;
	}
	return true;
}

export const BASH_RULES: Rule[] = [
	{ id: "rm-recursive", why: "recursive delete", re: RM_RECURSIVE, exempt: rmOnlyRegenerable },
	{ id: "sudo", why: "runs with root rights", re: /(?:^|[\s;&|(])(?:sudo|doas)\s/ },
	{ id: "git-reset-hard", why: "throws away uncommitted work", re: git(String.raw`reset\s+(?:\S+\s+)*--hard\b`) },
	{ id: "git-clean", why: "deletes untracked files", re: git(String.raw`clean\s+(?:\S+\s+)*-[a-zA-Z]*f`) },
	{ id: "git-discard", why: "throws away uncommitted changes", re: git(String.raw`(?:checkout|restore)\b[^;&|]*\s\.(?:\s|$)`) },
	{ id: "git-delete", why: "deletes branches or stashes", re: git(String.raw`(?:branch\s+(?:\S+\s+)*-D\b|stash\s+(?:drop|clear)\b)`) },
	{ id: "git-push", why: "publishes commits to a remote", re: git(String.raw`push(?=\s|$)`) },
	{ id: "pipe-to-shell", why: "runs downloaded code", re: /\b(?:curl|wget)\b[^|;&]*\|\s*(?:sudo\s+)?(?:sh|bash|zsh|python3?|node)\b/ },
	{ id: "disk", why: "can destroy a disk", re: /\bmkfs(?:\.\w+)?\b|\bdd\b[^;&|]*\bof=\/dev\/|>\s*\/dev\/(?:sd|nvme|vd|disk)/ },
	{ id: "power", why: "stops the machine", re: /(?:^|[\s;&|(])(?:shutdown|reboot|halt|poweroff)\b/ },
	{
		id: "publish",
		why: "publishes a package or image",
		re: /\b(?:npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b|\bdocker\s+push\b|\bgh\s+release\s+create\b/,
	},
	{ id: "chmod-r", why: "recursive permission change", re: /\b(?:chmod|chown|chgrp)\s+(?:-\S+\s+)*-[a-zA-Z]*R\b|\bchmod\s+(?:-\S+\s+)*[0-7]?777\b/ },
	{ id: "kill-by-name", why: "kills processes by name", re: /\b(?:pkill|killall)\b/ },
	{ id: "fork-bomb", why: "fork bomb", re: /:\(\)\s*\{/ },
	{ id: "env-dump", why: "prints every environment variable (API keys included) into the model context", re: /^\s*(?:printenv|env)\s*(?:$|[|>;&])/ },
];

// ---- 2. paths that hold secrets (read tool, and any path-looking word in a bash command) ----------------------
const TEMPLATE_SUFFIX = /^(?:example|sample|template|dist|defaults?)$/i;
const SECRET_BASENAMES = new Set([
	".netrc", ".npmrc", ".pypirc", ".git-credentials", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
	"credentials", "credentials.json", "secrets.json", "secrets.yml", "secrets.yaml", "service-account.json",
]);
const SECRET_EXT = new Set([".pem", ".key", ".p12", ".pfx", ".kdbx", ".ppk"]);
const SECRET_DIRS = ["/.ssh/", "/.aws/", "/.gnupg/", "/.kube/", "/.config/gh/", "/.config/gcloud/", "/.docker/config.json"];

export function isSecretPath(p: string): boolean {
	const norm = p.replace(/\\/g, "/");
	const name = basename(norm);
	if (name === ".env") return true;
	if (name.startsWith(".env.")) return !TEMPLATE_SUFFIX.test(name.slice(5));
	if (SECRET_BASENAMES.has(name)) return true;
	const dot = name.lastIndexOf(".");
	if (dot > 0 && SECRET_EXT.has(name.slice(dot).toLowerCase())) return true;
	return SECRET_DIRS.some((d) => (`/${norm}`).includes(d));
}

// A word in a bash command counts only if it looks like a path (has a "/" or "~") or names a file that exists here;
// otherwise `grep "x.key" src` or `obj.key` in a script would trip the .key rule.
export function secretIn(command: string, cwd: string): string | undefined {
	for (const raw of command.split(/[\s;&|<>()]+/)) {
		const word = raw.replace(/^['"]+|['"]+$/g, "");
		if (!word || !isSecretPath(word)) continue;
		if (/[\/~]/.test(word) || existsSync(resolve(cwd, word))) return word;
	}
	return undefined;
}

// ---- 3. where write / edit may not go without a yes ----------------------------------------------------------
function resolveTarget(p: string, cwd: string): string {
	let q = p.replace(/^@/, "");
	if (q === "~" || q.startsWith("~/")) q = homedir() + q.slice(1);
	const abs = resolve(cwd, q);
	try {
		return realpathSync(abs); // follow symlinks if the file exists
	} catch {
		try {
			return resolve(realpathSync(dirname(abs)), basename(abs)); // new file: resolve its folder
		} catch {
			return abs;
		}
	}
}

function inside(child: string, parent: string): boolean {
	const p = parent.endsWith(sep) ? parent : parent + sep;
	return child === parent || child.startsWith(p);
}

export function writeProblem(path: string, cwd: string): { id: string; why: string } | undefined {
	const target = resolveTarget(path, cwd);
	const t = target.replace(/\\/g, "/");
	if (/(?:^|\/)\.git(?:\/|$)/.test(t)) return { id: "write-git", why: "inside .git/ (repository internals)" };
	if (/(?:^|\/)node_modules\//.test(t)) return { id: "write-node-modules", why: "inside node_modules/ (generated)" };
	if (isSecretPath(t)) return { id: "write-secret", why: "a file that holds secrets" };
	const roots = [cwd, tmpdir(), "/tmp"].map((r) => {
		try {
			return realpathSync(r);
		} catch {
			return r;
		}
	});
	if (!roots.some((r) => inside(target, r))) return { id: "write-outside", why: "outside the project folder" };
	return undefined;
}

export default function (pi: ExtensionAPI) {
	const allowed = new Set<string>(); // rule ids you said "allow for this session" to

	pi.on("session_start", async () => {
		allowed.clear();
	});

	async function decide(ctx: any, id: string, what: string, detail: string, why: string) {
		if (allowed.has(id)) return undefined;
		if (!ctx.hasUI) {
			// One line on stderr per block, so a test harness (or a log) can count what was blocked.
			console.error(`[safety-gate] blocked ${id}: ${detail.replace(/\s+/g, " ").slice(0, 200)}`);
			return {
				block: true,
				reason: `Blocked by safety-gate (${id}: ${why}). Nobody is available to approve it. Use a safer alternative, or tell the user what you wanted to do and why.`,
			};
		}
		const choice = await ctx.ui.select(`Safety gate: ${what}\n\n  ${detail}\n\nReason: ${why}`, [
			"Allow once",
			`Allow "${id}" for the rest of this session`,
			"Deny",
		]);
		if (choice === "Allow once") return undefined;
		if (choice?.startsWith("Allow")) {
			allowed.add(id);
			return undefined;
		}
		return { block: true, reason: `Denied by the user (${id}: ${why}). Do not retry the same action; ask what they prefer.` };
	}

	pi.on("tool_call", async (event, ctx) => {
		if (process.env.PI_SAFETY_GATE === "off") return undefined;
		const input = event.input as Record<string, unknown>;

		if (event.toolName === "bash") {
			const command = String(input.command ?? "");
			for (const rule of BASH_RULES) {
				if (rule.re.test(command) && !rule.exempt?.(command)) return decide(ctx, rule.id, "bash command", command, rule.why);
			}
			const secret = secretIn(command, ctx.cwd);
			if (secret) return decide(ctx, "read-secret", "bash command touches a secret", command, `mentions ${secret}`);
			return undefined;
		}

		if (event.toolName === "read") {
			const path = String(input.path ?? "");
			if (isSecretPath(resolveTarget(path, ctx.cwd))) {
				return decide(ctx, "read-secret", "read a file that holds secrets", path, "its text would be sent to the model provider");
			}
			return undefined;
		}

		if (event.toolName === "write" || event.toolName === "edit") {
			const path = String(input.path ?? "");
			const problem = writeProblem(path, ctx.cwd);
			if (problem) return decide(ctx, problem.id, `${event.toolName} a protected location`, path, problem.why);
		}
		return undefined;
	});
}
