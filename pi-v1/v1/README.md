# pi v1 配置包

一套"通用底座"配置：前缀成本几乎为零（只多一份约 300 token 的 AGENTS.md），其余全是代码或按需加载。

| 文件 | 它是什么 | 前缀 token | 怎么关 |
|---|---|---|---|
| `settings.json` | 默认思考档位 `low`（实测比默认便宜约四成、快约三成五）；开启缓存未命中提示 | 0 | 删掉对应键；单次用 `pi --thinking high` 或 `Shift+Tab` |
| `AGENTS.md` | 全局工作约定（8 行）：先读后改、最小改动、跑测试验证、并行读取、危险操作先问、两次失败就停下汇报 | ≈300 | 删文件，或 `pi --no-context-files` |
| `extensions/safety-gate.ts` | 安全带：拦危险 bash（`rm -r` 非常规目标、sudo、force-push、`git reset --hard`、`curl｜sh`…）、受保护路径的写入（.git、.env、项目外）、读取密钥文件。交互模式弹窗让你选"允许一次 / 本会话允许 / 拒绝"；非交互模式直接拦并告诉模型原因 | 0 | `PI_SAFETY_GATE=off pi`，或删文件 |
| `extensions/budget-guard.ts` | 防失控：一条消息内输出 token / 调用次数 / 费用超过软限制时提醒模型收尾，超过硬限制就中止（默认 4 万 / 8 万 token，30 / 60 次调用） | 0 | `PI_BUDGET_GUARD=off pi`，或删文件 |
| `extensions/preset.ts` + `presets.json` | 官方示例原样复制：`pi --preset explore`（只读探索）、`pi --preset deep`（高思考）；会话中 `/preset` 切换（会打断一次缓存） | 0 | 删文件 |
| `prompts/*.md` | `/init` `/plan` `/review` `/commit` `/explain`：可复用提示，输入时才展开 | 0 | 删文件 |
| `skills/debug`、`skills/refactor` | 隐藏 skill（`disable-model-invocation`）：不进系统提示，用 `/skill:debug <现象>` 才加载 | 0 | 删目录 |

安装到你的 pi：`bash install.sh`（先 `--dry-run` 看会改什么；被覆盖的文件会备份）。
用于 arena 对比：`python3 arena.py suite --label v1 --agents pi --pi-thinking low --pi-config <本目录>`。
