'use strict';
const { cycleBounds } = require('./cycle');
const { prorate } = require('./proration');

// Plays one cycle forward. `plan` is the plan in effect when the cycle starts.
// Returns the invoice lines of the cycle and the plan that is in effect when the next cycle starts.
function replayCycle(sub, plan, bounds) {
  let effective = plan;
  let pending = null;
  const lines = [{ kind: 'base', plan: effective, amountCents: sub.plans[effective] }];
  for (const change of sub.changes) {
    if (change.on < bounds.start || change.on >= bounds.next) continue;
    const from = sub.plans[effective];
    const to = sub.plans[change.plan];
    if (to > from) {
      lines.push({ kind: 'proration', plan: change.plan, on: change.on, amountCents: prorate(from, to, change.on, bounds) });
      effective = change.plan;
      pending = null;
    } else if (to < from) {
      pending = change.plan;
    } else {
      effective = change.plan;
      pending = null;
    }
  }
  return { endPlan: pending || effective, lines };
}

// The invoice of the cycle that starts on `cycleStart`.
function invoice(sub, cycleStart) {
  let plan = sub.initialPlan;
  let day = sub.startedOn;
  for (;;) {
    const bounds = cycleBounds(sub.anchorDay, day);
    if (bounds.start > cycleStart) throw new Error(`not a cycle start: ${cycleStart}`);
    const { endPlan, lines } = replayCycle(sub, plan, bounds);
    if (bounds.start === cycleStart) {
      return { cycleStart, lines, totalCents: lines.reduce((sum, l) => sum + l.amountCents, 0) };
    }
    plan = endPlan;
    day = bounds.next;
  }
}

module.exports = { invoice };
