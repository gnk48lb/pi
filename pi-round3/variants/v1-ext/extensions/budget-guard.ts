/**
 * budget-guard.ts: stops a runaway before it eats your wallet.
 *
 * One "run" = everything the agent does for one message you send. While it runs, this extension adds up what the
 * model has generated (output tokens, reasoning included), the number of model calls and, if your models.json
 * has prices, the dollars. Then:
 *
 *   soft limit  tell the model, once, to wrap up or report the blocker
 *   hard limit  abort the run (send another message to continue with a fresh budget)
 *
 * Why it exists: in one of 24 default-thinking test runs the model produced 134k output tokens over 27 turns without
 * converging, 17x the cost of that task's median run. Most of that was thinking, with turns of 14-19k tokens each:
 * not an endless loop, just "keeps thinking and never converges", which a per-request cap would not catch.
 * Normal runs on the 8 test tasks used 2-15k output tokens at thinking=low and 3-22k at the default.
 *
 * Costs 0 prompt tokens (the nudge is sent only when the soft limit is hit). Tune the numbers below,
 * or switch it off for one run: PI_BUDGET_GUARD=off pi
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export const LIMITS = {
	softOutputTokens: 40_000,
	hardOutputTokens: 80_000,
	softTurns: 30,
	hardTurns: 60,
	softUsd: 1.0, // only counts if your model has prices in models.json
	hardUsd: 3.0,
};

export interface Tally {
	output: number;
	turns: number;
	usd: number;
	softSent: boolean;
}

export type Verdict = "ok" | "soft" | "hard";

export function judge(t: Tally, lim = LIMITS): { verdict: Verdict; why: string } {
	const facts = `${t.output.toLocaleString("en-US")} output tokens, ${t.turns} model calls, $${t.usd.toFixed(2)}`;
	if (t.output >= lim.hardOutputTokens || t.turns >= lim.hardTurns || t.usd >= lim.hardUsd) return { verdict: "hard", why: facts };
	if (!t.softSent && (t.output >= lim.softOutputTokens || t.turns >= lim.softTurns || t.usd >= lim.softUsd)) return { verdict: "soft", why: facts };
	return { verdict: "ok", why: facts };
}

export default function (pi: ExtensionAPI) {
	let tally: Tally = { output: 0, turns: 0, usd: 0, softSent: false };
	let aborted = false;

	pi.on("before_agent_start", async (event) => {
		if (event.messageType === "user") {
			tally = { output: 0, turns: 0, usd: 0, softSent: false };
			aborted = false;
		}
	});

	pi.on("message_end", async (event, ctx) => {
		if (process.env.PI_BUDGET_GUARD === "off") return undefined;
		const m: any = event.message;
		if (m?.role !== "assistant" || !m.usage || aborted) return undefined;
		tally.output += Number(m.usage.output) || 0;
		tally.turns += 1;
		tally.usd += Number(m.usage.cost?.total) || 0;

		const { verdict, why } = judge(tally);
		if (verdict === "hard") {
			aborted = true;
			if (ctx.hasUI) ctx.ui.notify(`Budget guard: stopped this run (${why}). Send a message to continue with a fresh budget.`, "warning");
			else console.error(`[budget-guard] stopped this run (${why})`);
			ctx.abort();
		} else if (verdict === "soft") {
			tally.softSent = true;
			if (ctx.hasUI) ctx.ui.notify(`Budget guard: ${why}. Asking the model to wrap up.`, "warning");
			else console.error(`[budget-guard] soft limit reached (${why})`);
			pi.sendUserMessage(
				`[budget-guard] This task has already used ${why}. Stop exploring. If you are nearly done, finish and report. ` +
					"If you are blocked, stop now and tell me what you tried, what you saw and your best hypothesis.",
				{ deliverAs: "steer" },
			);
		}
		return undefined;
	});
}
