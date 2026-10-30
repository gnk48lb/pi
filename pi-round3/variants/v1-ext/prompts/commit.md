---
description: 根据当前改动写提交信息并提交（只提交，不推送、不改历史）
---
Create a git commit for the current changes.

1. Run `git status --short` and `git diff HEAD` to see what changed. If unrelated changes are mixed together, stage only the related ones and tell me what you left out.
2. Write the message: an imperative subject line of at most 72 characters, a blank line, then a short body explaining why if it is not obvious. Follow the style of `git log -5 --oneline`.
3. Commit. Do NOT push, amend or rewrite history. Finish by showing `git log -1 --stat`.
