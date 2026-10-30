'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { invoice } = require('../src');

const plans = { basic: 1000, pro: 2500, team: 6000 };

test('a subscription without changes is billed its plan price every cycle', () => {
  const sub = { anchorDay: 15, startedOn: '2025-01-15', plans, initialPlan: 'basic', changes: [] };
  assert.deepStrictEqual(invoice(sub, '2025-02-15'), {
    cycleStart: '2025-02-15',
    lines: [{ kind: 'base', plan: 'basic', amountCents: 1000 }],
    totalCents: 1000,
  });
});

test('an upgrade adds a proration line and the new plan is billed from the next cycle', () => {
  const sub = { anchorDay: 1, startedOn: '2025-04-01', plans, initialPlan: 'basic', changes: [{ on: '2025-04-16', plan: 'pro' }] };
  assert.deepStrictEqual(invoice(sub, '2025-04-01'), {
    cycleStart: '2025-04-01',
    lines: [
      { kind: 'base', plan: 'basic', amountCents: 1000 },
      { kind: 'proration', plan: 'pro', on: '2025-04-16', amountCents: 750 },
    ],
    totalCents: 1750,
  });
  assert.deepStrictEqual(invoice(sub, '2025-05-01').lines, [{ kind: 'base', plan: 'pro', amountCents: 2500 }]);
});

test('a downgrade is free and starts with the next cycle', () => {
  const sub = { anchorDay: 1, startedOn: '2025-04-01', plans, initialPlan: 'pro', changes: [{ on: '2025-04-10', plan: 'basic' }] };
  assert.deepStrictEqual(invoice(sub, '2025-04-01').lines, [{ kind: 'base', plan: 'pro', amountCents: 2500 }]);
  assert.deepStrictEqual(invoice(sub, '2025-05-01').lines, [{ kind: 'base', plan: 'basic', amountCents: 1000 }]);
});
