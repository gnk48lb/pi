---
name: refactor
description: Behavior-preserving refactoring playbook - pin behavior with tests, change in small steps, run the tests after each step.
disable-model-invocation: true
---

# Refactoring playbook

Goal: change structure without changing behavior.

1. State the goal and the boundaries: what must NOT change (public API, outputs, file formats).
2. Pin current behavior. Run the existing tests; if coverage of this area is thin, first write characterization tests that assert what the code does today, odd or not.
3. Work in small steps (rename, extract, move, simplify). Run the tests after EACH step. If one fails, undo that step instead of piling fixes on top.
4. Do not mix in bug fixes or features. If you find a bug, note it and keep going.
5. Keep the diff reviewable: no gratuitous reformatting, one concern per step.
6. Finish: run the full test suite, then summarize the before/after structure and anything you left alone on purpose.
