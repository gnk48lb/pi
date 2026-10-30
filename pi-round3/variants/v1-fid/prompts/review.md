---
description: 审查当前未提交的改动（正确性、边界情况、安全、缺失的测试）
argument-hint: "[focus]"
---
Review the uncommitted changes in this repository (`git diff HEAD`, plus any untracked files from `git status --short`). Focus on ${1:-correctness, edge cases, security, and missing tests}.

For each real problem give: file:line, what is wrong, why it matters, and a concrete fix. Rank by severity and skip style nitpicks unless they hide bugs. Run the relevant tests if you can. If nothing is wrong, say so and name what you checked. Do not modify any files.
