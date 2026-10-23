'use strict';

const round2 = (x) => Math.round((x + Number.EPSILON) * 100) / 100;

const sum = (values) => round2(values.reduce((a, b) => a + b, 0));

module.exports = { round2, sum };
