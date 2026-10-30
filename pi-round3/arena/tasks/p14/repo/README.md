# billing

Billing cycles, proration and invoices for a subscription product.

* Money is **integer cents**, always. Rounding is **half up**: 2.5 cents becomes 3, 2.4999 becomes 2.
* Dates are ISO strings `YYYY-MM-DD`. There are no `Date` objects and no time zones.
* `src/dates.js` has the calendar helpers. Leap years are the Gregorian ones: divisible by 4, except centuries, unless
  divisible by 400 (2000 and 2024 are leap years, 1900 and 2100 are not).

```js
const { cycleStarts, cycleBounds, prorate, invoice } = require('./src');
```

## Cycles

A subscription has an `anchorDay` (1-31): the day of the month it was started on. A cycle starts on the anchor day of a
month; in a month that is too short for it, the cycle starts on the last day of that month. **The anchor never drifts**:
the clamping of one month does not carry over to the next. Anchor 31 gives 2025-01-31, 2025-02-28, 2025-03-31,
2025-04-30, 2025-05-31, ...; anchor 29 gives 2024-02-29, 2024-03-29, ..., 2025-02-28, 2025-03-29, ..., 2028-02-29.

A cycle runs from its start date (included) to the start of the next cycle (excluded). Its length in days is the
difference between the two start dates, so it is 28, 29, 30 or 31 days.

* `cycleStarts(anchorDay, firstStart, count)` returns an array with the starts of `count` consecutive cycles, the first
  one being the cycle that starts on `firstStart` (which is itself a valid cycle start for that anchor).
* `cycleBounds(anchorDay, iso)` returns `{ start, next, days }` for the cycle that contains `iso` (`start <= iso < next`).

## Plan changes and proration

A subscription object looks like this:

```js
{
  anchorDay: 31,
  startedOn: '2025-01-31',          // the first cycle starts here
  plans: { basic: 1000, pro: 2500, team: 6000 },   // price per cycle, in cents
  initialPlan: 'basic',
  changes: [ { on: '2025-02-10', plan: 'pro' }, ... ],   // sorted by date; several changes may fall in one cycle
}
```

Changes are processed in order. Inside a cycle, a change is judged against the plan **currently in effect** (the plan the
customer had at the start of the cycle, or the plan of the last upgrade made since), by comparing prices:

* **Upgrade** (the new price is higher): it takes effect immediately and the customer is charged the prorated
  difference, `(newPrice - currentPrice) * remainingDays / cycleDays`, rounded half up to a whole cent. `remainingDays`
  counts the day of the change itself: it is the number of days from the change date (included) to the start of the next
  cycle (excluded); `cycleDays` is the real length of this cycle (not 30). A pending downgrade, if any, is cancelled.
* **Downgrade** (the new price is lower): nothing is charged and nothing is credited. The new plan takes effect at the
  start of the next cycle; until then the current plan stays in effect. If several downgrades are requested in the same
  cycle, the last one wins.
* **Same price**: the plan is switched immediately, nothing is charged, and a pending downgrade is cancelled.

The plan in effect at the start of a cycle is the plan at the end of the previous cycle: a pending downgrade, otherwise
the plan in effect. The first cycle starts with `initialPlan`. A change dated on the first day of a cycle belongs to that
cycle.

* `prorate(oldCents, newCents, changeIso, bounds)` returns the amount to charge now for a change on `changeIso` inside
  the cycle `bounds` (the object `cycleBounds` returns). For an upgrade it is the prorated difference above; for a
  downgrade or an unchanged price it is `0` (never negative).

## Invoices

`invoice(sub, cycleStart)` returns `{ cycleStart, lines, totalCents }` for the cycle that starts on `cycleStart`; it throws
an `Error` if that date is not the start of one of the subscription's cycles. `lines` is, in this order:

1. one `{ kind: 'base', plan, amountCents }` line: the plan in effect at the start of the cycle and its full price;
2. then one `{ kind: 'proration', plan, on, amountCents }` line for every **upgrade** made inside the cycle, in date order
   (`plan` is the new plan, `on` the change date). Downgrades and same-price changes produce no line.

`totalCents` is the sum of the line amounts.

## Tests

`npm test` runs the tests in `test/`. They cover the basics only; the rules above are the specification.
