---
name: debug
description: Systematic debugging playbook - reproduce, form hypotheses, test them one at a time, fix the root cause, add a regression test.
disable-model-invocation: true
---

# Debugging playbook

Follow these steps in order and report briefly after each.

1. **Reproduce.** Get a failing command or test that shows the bug. If you cannot reproduce it, say so and ask for what is missing; do not guess a fix.
2. **Read the evidence.** Read the whole error or stack trace, then the code at the failing line and its callers. Keep what you *observed* separate from what you *infer*.
3. **Hypothesize.** Write down 2-3 candidate causes, most likely first. For each, name one cheap check that would confirm or kill it (a print, an assertion, a smaller input; `git log -p` or `git bisect` for regressions).
4. **Test one hypothesis at a time.** Run its check and drop the ones the evidence kills. Do not change code "to see if it helps" before you have a hypothesis.
5. **Fix the root cause**, not the symptom, with the smallest diff that makes the failing case pass for the right reason.
6. **Prove it.** Add or extend a test that fails without the fix and passes with it, run the relevant suite, and remove debug output.
7. **Report:** the root cause, the fix (files), how you verified it, and anything suspicious you noticed but did not change.

If two hypotheses in a row fail, stop and summarize what is known and what is not.
