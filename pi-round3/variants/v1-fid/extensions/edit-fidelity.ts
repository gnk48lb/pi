/**
 * edit-fidelity.ts: keeps pi's edit / write tools from silently damaging files they cannot round-trip.
 *
 * What pi's tools do (read from pi 1.3.0's source, tools/edit.js and tools/write.js):
 *   edit   decodes the file as UTF-8, applies the replacement on a copy whose line endings were turned into "\n",
 *          then rewrites EVERY line ending with the first style it found in the file (CRLF if the first newline was one),
 *          and writes the result back as UTF-8.
 *   write  writes the text the model gives, as UTF-8. The model's text has "\n" only.
 *
 * So a file that does not survive that round trip is changed in places you never asked for:
 *   not UTF-8        (Latin-1, Windows-125x, UTF-16, ...)   every non-ASCII byte becomes U+FFFD
 *   mixed endings    some lines CRLF, some LF, or a lone CR   the minority lines are rewritten
 *   write over CRLF  a file that is CRLF all through        becomes LF
 * Nothing in the tool result says so; a test suite rarely notices; a byte-for-byte diff does.
 *
 * This extension checks the target file before every `edit` / `write` and, for a file in one of those states, refuses
 * with a reason the model can act on (use a byte-exact command through bash and check `git diff`). In interactive mode
 * it asks you instead. Everything else (UTF-8 files with consistent LF, or CRLF for `edit`, new files) passes untouched.
 * It costs 0 prompt tokens: an extension is code in pi's process, not text in the model's context.
 *
 * Switch it off for one run: PI_EDIT_FIDELITY=off pi
 */
import { readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const MAX_BYTES = 4 * 1024 * 1024; // do not read bigger files

export interface Finding {
	id: "fid-not-utf8" | "fid-mixed-eol" | "fid-write-crlf";
	why: string;
}

/** Line-ending census of a byte buffer: CRLF pairs, bare LF, lone CR. */
export function countEndings(buf: Uint8Array): { crlf: number; lf: number; cr: number } {
	let crlf = 0;
	let lf = 0;
	let cr = 0;
	for (let i = 0; i < buf.length; i++) {
		const b = buf[i];
		if (b === 0x0d) {
			if (buf[i + 1] === 0x0a) {
				crlf++;
				i++;
			} else {
				cr++;
			}
		} else if (b === 0x0a) {
			lf++;
		}
	}
	return { crlf, lf, cr };
}

export function isUtf8(buf: Uint8Array): boolean {
	try {
		new TextDecoder("utf-8", { fatal: true }).decode(buf);
		return true;
	} catch {
		return false;
	}
}

/** What is wrong with using `tool` on a file with these bytes? undefined = nothing. */
export function inspectBytes(tool: "edit" | "write", buf: Uint8Array): Finding | undefined {
	if (!isUtf8(buf)) {
		return {
			id: "fid-not-utf8",
			why:
				tool === "edit"
					? "it is not valid UTF-8 (Latin-1 or another encoding): the edit tool would re-encode the whole file as UTF-8 and turn every non-ASCII byte into U+FFFD"
					: "it is not valid UTF-8 (Latin-1 or another encoding): the text you would write cannot reproduce its bytes",
		};
	}
	const { crlf, lf, cr } = countEndings(buf);
	if (tool === "edit") {
		const styles = (crlf > 0 ? 1 : 0) + (lf > 0 ? 1 : 0) + (cr > 0 ? 1 : 0);
		if (styles > 1 || (cr > 0 && crlf === 0 && lf === 0)) {
			const what = `${crlf} CRLF, ${lf} LF, ${cr} lone CR`;
			return {
				id: "fid-mixed-eol",
				why: `its line endings are mixed (${what}): the edit tool rewrites every line ending with the style of the first one, so lines you did not touch would change`,
			};
		}
	} else if (crlf > 0 || cr > 0) {
		return {
			id: "fid-write-crlf",
			why: "it uses CRLF line endings: the text you would write has LF only, so every line ending of the file would change",
		};
	}
	return undefined;
}

function resolveTarget(p: string, cwd: string): string {
	let q = p.replace(/^@/, "");
	if (q === "~" || q.startsWith("~/")) q = homedir() + q.slice(1);
	return resolve(cwd, q);
}

export function inspectFile(tool: "edit" | "write", path: string, cwd: string): Finding | undefined {
	const abs = resolveTarget(path, cwd);
	try {
		const st = statSync(abs);
		if (!st.isFile() || st.size === 0 || st.size > MAX_BYTES) return undefined;
		return inspectBytes(tool, readFileSync(abs));
	} catch {
		return undefined; // missing file (a new file is fine), unreadable, ...: not our business
	}
}

const HOWTO =
	"Make this change with a byte-exact command through bash instead, for example a short python3 script that reads the file with " +
	"open(path, 'rb'), replaces only the bytes you mean to change (keep each line's own ending, the tabs and the encoding) and writes " +
	"them back with open(path, 'wb'). Then check with `git diff` (or `cmp`) that nothing else changed.";

export default function (pi: ExtensionAPI) {
	const allowed = new Set<string>(); // ids you said "allow for this session" to

	pi.on("session_start", async () => {
		allowed.clear();
	});

	pi.on("tool_call", async (event, ctx) => {
		if (process.env.PI_EDIT_FIDELITY === "off") return undefined;
		if (event.toolName !== "edit" && event.toolName !== "write") return undefined;
		const path = String((event.input as Record<string, unknown>).path ?? "");
		if (!path) return undefined;
		const finding = inspectFile(event.toolName, path, ctx.cwd);
		if (!finding || allowed.has(finding.id)) return undefined;

		if (!ctx.hasUI) {
			// One line on stderr per block, so a test harness (or a log) can count them.
			console.error(`[fidelity-gate] blocked ${finding.id}: ${path}`);
			return {
				block: true,
				reason: `Blocked by fidelity-gate (${finding.id}): ${path}: ${finding.why}. ${HOWTO}`,
			};
		}
		const choice = await ctx.ui.select(`Fidelity gate: ${event.toolName} ${path}\n\nThis file: ${finding.why}.`, [
			"Allow once",
			`Allow "${finding.id}" for the rest of this session`,
			"Deny",
		]);
		if (choice === "Allow once") return undefined;
		if (choice?.startsWith("Allow")) {
			allowed.add(finding.id);
			return undefined;
		}
		return { block: true, reason: `Denied by the user (${finding.id}). ${HOWTO}` };
	});
}
