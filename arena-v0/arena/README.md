# arena v0 — pi vs Claude Code 评测台

同一个模型、同一段提示词、同样的隔离环境，让 **pi** 和 **Claude Code** 各自把同一批编程任务做一遍，
然后由**隐藏的测试**判卷，并记录：通过率、成本、缓存命中率、首个请求的提示词体积、耗时、LLM 调用数、
工具失败率、改动是否精简、是否卡死。纯标准库 Python（≥3.9），不装任何包。

这是 v0：先把“尺子”做准（试点题只有 2 道，用来量噪声、校准强度、量网关缓存的可靠度），不是正式比赛。

## 目录

```
arena.py            命令行入口（day1 / pack / setup / selftest / smoke / calib / cacheprobe / tasks / run / report / prices）
arena_day1.py       day1：一条命令跑完第一轮，并把结果打成一个文件；pack：只打包
arena_core.py       隔离环境、运行 agent、判卷、结果行
arena_parse.py      把 pi 的 JSON 事件流 / Claude Code 的 stream-json 解析成统一格式
arena_probe.py      cacheprobe：不经过 agent，直接量网关的提示缓存
arena_report.py     报告：逐次明细、每题汇总、噪声(CV)、暂定 胜/平/负
arena_selftest.py   自测（对模拟网关，不花 token）
prices.json         唯一的价目表（所有 agent 共用，成本一律由 token 数重算）
mock/mock_server.py 模拟网关（OpenAI + Anthropic 两种协议，可脚本化“解题”）
tasks/p01, p02      试点题：repo/（给 agent 的）、hidden/（隐藏测试）、_ref/（参考解）、task.json
configs/            setup 生成（含你的网关占位符，不要上传，打包时也不会带上）
runs/<label>/       每次运行的日志和结果
day1/               day1 每一步的完整输出（<步骤>.log）和进度记录（state.json）
```

## 第一次使用：一条命令

在 WSL 里，把压缩包放到 `~/pi` 下解开，然后跑 `day1`：

```bash
cd ~/pi && tar xzf arena-v0.tar.gz && cd arena
tmux new -s arena               # 可选但推荐：关掉终端也不会中断（装了 tmux 的话）
python3 arena.py day1           # 约 2.5 小时，全程不需要输入；加 --quick 约 1.2 小时
```

它依次做这些事（每一步的完整输出都存在 `day1/<步骤>.log`）：

| 步骤 | 做什么 | 约耗时 |
|---|---|---|
| `setup` | 读取你现有的 pi / Claude Code 网关配置，生成“空白基线”配置。pi 的模型按“和 Claude Code 同一个 id”精确匹配（不会误选 `opencode-zen/...-free` 这类相似模型）。已有 `configs/setup.json` 就跳过 | 1 分钟 |
| `selftest` | 对模拟网关把整条流水线自测一遍，不花 token。全是 PASS 才算对 | 2 分钟 |
| `smoke` | 每个 agent 通过你的真实网关连问 3 次相同的 “Reply with exactly: PONG”：看首个请求多大、缓存命中多少，并自动判定 magpie 怎样汇报 Claude Code 的 token 用量（`input_tokens` 含不含缓存部分） | 2 分钟 |
| `cacheprobe` | 不经过 agent，直接量网关缓存：相同请求隔 1 秒到 160 秒后还命中吗？追加式对话（像 agent 循环那样）的命中率？有没有整段未命中？两种协议各测一遍 | 25 分钟（`--quick` 5 分钟） |
| `calib` | 同一道短题在两边所有“强度档位”下各跑 3 次（共 30 次短请求），看档位在线上到底差多少 | 20 分钟（`--quick` 7 分钟） |
| `pilot` | 2 题 × 2 个 agent × 5 次 = 20 次运行，隐藏测试判卷。量单次成本和各指标的噪声 | 约 90 分钟（`--quick` 3 次，约 55 分钟） |
| `report` | 生成 pilot 的报告：逐次明细、每题汇总、噪声表、暂定胜平负 | 1 分钟 |

最后它会把结果打成**一个文本文件** `arena-results-<时间>.txt`（还有一个 `.tgz`，内容相同，外加每个任务第一次运行的原始事件流），
并打印它的位置（在 WSL 里会同时打印 Windows 路径；`cd ~/pi/arena && explorer.exe .` 可以在资源管理器里打开该目录）。
**把这个 `.txt` 发给我就行**：它是纯文本，里面有各步骤的摘要、报告和全部数据行，没有密钥（`configs/` 不会被打包，疑似密钥的字符串也会被遮掉）。

### 中断、失败、重来

* 中途停了（Ctrl-C、关终端、重启）：再运行**同一条命令**。已完成的步骤会跳过，pilot 从断点继续。
* 某一步失败不会拖垮无关的步骤：`selftest` 失败会记录并继续；`smoke` 失败会跳过需要 agent 的步骤（`calib`、`pilot`、`report`），但 `cacheprobe` 照跑；只有 `setup` 失败才整体停止。无论如何最后都会打包，把结果文件发给我，我来看原因。
* 只跑某几步：`--only calib,pilot`；跳过某几步：`--skip selftest`；已完成但要重来：`--redo cacheprobe`（`--redo setup` 会连带重跑 `smoke`）。
* 想看进度：另开一个终端 `tail -f ~/pi/arena/day1/pilot.log`。想看某一次运行发生了什么：`runs/pilot1/<序号_agent_题_rN>/` 里有 `events.jsonl`（原始事件流）、`events.ts`（每行到达时间）、`stderr.txt`、`diff.patch`（agent 改了什么）、`verify.txt`（判卷输出）、`result.json`（归一化的一行）。
* 只重新打包：`python3 arena.py pack`（`--label pilot1` 只带某个标签的运行）。

### 单独运行某一步

`day1` 只是把下面这些命令按顺序串起来；需要调参或重跑某一步时可以单独用：

```bash
python3 arena.py setup        # --pi-model/--cc-model 等见 --help
python3 arena.py selftest
python3 arena.py smoke        # --repeat 3 --gap 4
python3 arena.py cacheprobe   # --quick；--tokens 8000 控制共享前缀大小
python3 arena.py calib        # --reps 3
python3 arena.py run --label pilot1 --tasks p01,p02 --agents pi,cc --reps 5
python3 arena.py report --label pilot1
```

`run` 是阻塞的，几十分钟到一两个小时：放进 tmux，或者 `nohup python3 arena.py run ... > pilot1.log 2>&1 &` 后台跑
（后台的用 `kill <pid>` 停，arena 会杀掉在跑的 agent 并收尾）；
中途停了加 `--resume` 继续（计划变了会拒绝，`--force` 可覆盖）。有运行没出结果时退出码是 3，`--resume` 会补跑。

## 公平与隔离：它做了什么

| 做法 | 为什么 |
|---|---|
| 每次运行前清空 agent 自己的 `HOME`、`TMPDIR`、配置目录（`PI_CODING_AGENT_DIR` / `CLAUDE_CONFIG_DIR`） | 你自己的 AGENTS.md、扩展、skills、记忆、历史都进不来；基线 = 空白配置 |
| 这些目录的**路径每次相同**：`/tmp/arena-ws-env/<agent>/…`（内容每次清空） | agent 会把自己的路径写进系统提示（Claude Code 的记忆目录、pi 的 AGENTS.md 路径）。路径每次不同，每次运行的第一个请求就会白白丢掉缓存，和 harness 好坏无关。真实安装里 `~/.claude`、`~/.pi` 也是固定的 |
| 基线提交的日期固定（hash 每次相同） | Claude Code 会把最近的 git 提交（`f37febe baseline`）写进第一条消息；hash 随时间变，缓存又会断一次 |
| 同一时间只允许一个跑 agent 的 arena 命令（锁文件 `/tmp/arena-ws-env/.lock`） | 工作区和 agent 目录路径固定，两个同时跑会互相覆盖。要并行请给另一个命令单独的 `--ws-root` |
| 环境变量白名单，只继承 `PATH` | 你 shell 里的各种 key 不会泄漏给 agent |
| 代理变量指向一个必拒绝的端口，只放行 `127.0.0.1` | 评测期间 agent 联不了外网，只能找本地网关 |
| 工作区固定在 `/tmp/arena-ws/<题>`，每次重建并 `git init` 提交基线 | 两个 agent 的 cwd 完全相同；便于量 diff |
| 提示词原样相同；无 `--max-turns`；同样的超时 | 规则对称 |
| 交错运行 A B / B A / A B …（按 重复×题 轮换先后手） | 抵消时间漂移（网关忙闲、缓存预热） |
| 判卷在 agent 退出之后，用 agent 看不到的隐藏测试；改动受保护的测试文件直接判负 | 防作弊、防“改测试蒙混” |
| 成本一律用 `prices.json` 按 token 重算；agent 自己报的成本只作参考 | Claude Code 不认识这个模型，自报的价格是错的 |
| 运行结束后杀掉整个进程组，再按环境标记扫一遍逃逸的子进程 | 不留后台进程污染下一次 |
| Claude Code **不**设 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 实测它会悄悄去掉一个工具、少约 2.3k 提示词，不再是“开箱即用”的行为 |
| 默认工具集：各用各的默认（Claude Code 去掉 WebFetch/WebSearch）；`--toolset aligned` 则双方都只留 read/bash/edit/write | 先比整机，再比“循环和提示词本身”。注意：较新的 Claude Code（实测 2.1.304）即使加了 `--tools` 也还会多发一个占位工具 `DeferredToolPlaceholder`，去不掉；报告里 `tools_exposed` 会如实显示 |
| Claude Code 带 `--include-partial-messages`（只改输出，不改发给模型的请求） | 读取每次 API 调用的原始用量。网关若把用量只放在流末尾，不加这个开关逐次数据会全是 0 |
| `smoke` 判定网关的 `input_tokens` 含不含缓存，写入 `configs/setup.json`，之后 `run`/`calib` 按此解读 | 解读错了，Claude Code 的命中率和成本都会错（magpie 的实测是“只计未命中部分”） |
| `cacheprobe` 直接用 HTTP 访问网关，不走代理 | 量的是网关本身的缓存，不掺进 agent 的行为 |

## 强度（effort）怎么对齐

两边的默认并不一致：pi 默认 `thinking=medium`（仅当模型条目 `reasoning: true` 才会发 `reasoning_effort`），
Claude Code 默认发 `thinking: adaptive` + `output_config.effort=high`。网关（magpie）怎么把它们翻译给 DeepSeek 我们还不知道。
所以：

1. `calib` 用同一道短题测每个档位的输出 token（含推理）。
2. 根据结果选出“线上效果相近”的两档，再用 `--pi-thinking X --cc-effort Y` 跑正式对比。
3. 每一行结果都记录了 effort 和 pi 实际生效的 thinking 等级。

注意：Claude Code 报的 `thinking_tokens` 不可信（自测里模拟网关发了推理块它仍报 0），比较推理量请看 `output tokens`。

## 指标

| 指标 | 含义 | 好的方向 |
|---|---|---|
| pass rate | 隐藏验收 + 可见测试全过，且未超时、未改受保护文件 | 高 |
| cost | 由 token 数和 `prices.json` 重算，单位 USD | 低 |
| cache hit rate | `cache_read ÷ (input + cache_read + cache_write)` | 高 |
| first-request prompt tokens | 第一个请求的提示词体积（系统提示 + 工具定义） | 低 |
| total prompt tokens / output tokens | 全程累计 | 低 |
| LLM calls | 主线程的 LLM 请求数 | 低 |
| wall seconds | 墙钟时间（含启动） | 低 |
| tool error rate | 工具调用里报错的比例 | 低 |
| minimality | 非测试文件的 diff 行数 ÷ 参考解的 diff 行数 | 低（≈1 最好） |
| timeout rate | 撞到超时被杀 | 低 |

结果行里的 flags：`T` 超时，`I` 网关/基础设施错误（会自动重跑一次，报告里仍标出），`X` 改了受保护测试，
`E` agent 报错，`C` 出现缓存断崖（本该命中的上一轮前缀没命中，阈值 `≥ max(3000, 40%)` tokens）。

`report` 里的 **noise** 表给出各指标的变异系数（重复运行之间的波动），“暂定 W/T/L”用的平手带宽是猜的，
等试点数据出来再按噪声改（`--bands cost=0.2,wall=0.3` 可覆盖）。题目太少时这张表只是在演练流程，不是结论。

## 已知局限（v0）

* **不是沙箱**：agent 以你的账号、免确认权限运行（pi 本来就没有确认；Claude Code 用 `bypassPermissions`）。
  `HOME`/环境变量/代理做了隔离，但一个铁了心的 agent 仍可能 `rm -rf` 你有权限的地方。试点题很温和，别把重要文件放进 `/tmp/arena-ws`。
* **网关缓存并不总是命中**：magpie 上出现过“完全相同的请求隔几秒却一点缓存都没命中”的情况，缓存粒度是 64 token。
  所以缓存类指标（命中率、成本）要看多次运行的中位数，波动有多大由 `cacheprobe` 和 pilot 的噪声表来量。
* **缓存跨次预热**：同一 agent 同一题的相邻两次，第一个请求逐字节相同（目录路径、基线 hash 都固定了，自测会验证），
  所以在网关侧是热的（DeepSeek 磁盘缓存），和你平时在同一个项目里连开两次会话一样。双方对称，但第 1 次比后面更冷；
  报告里每次运行都显示 “1st hit”。Claude Code 的第一个系统块里带一个按首条消息算出来的指纹，
  所以换题时它的整段前缀大概率是冷的——这正是我们要用数据验证的假设。
* **价格表**只有 DeepSeek V4.1 Flash 的牌价，高峰时段的 ×2 没建模（请在非高峰时段跑）。
* 目前只有 2 道试点题；正式的 12 道（8 开发 + 4 留出）要等试点的噪声数据。
* 只支持 Linux / WSL（用了进程组、`/proc`）。

## 常见问题

* `setup` 说某个程序在新 HOME 下起不来：它会自动退回真实 HOME 再试，并记在 `configs/setup.json`（配置目录仍然隔离）。
* `setup` 拒绝了 `/mnt/...` 下的 pi 或 claude：那是 Windows 的程序；用 WSL 里的 Linux 安装（`--pi-bin` / `--cc-bin` 指定路径）。
* pi 的 apiKey 如果是环境变量名而不是字面量：arena 不透传环境变量，请在 models.json 里写字面量（本地网关的占位符即可）。
* 网关限流/报错：该次运行会被标 `I` 并自动重跑一次（`--retry-infra N` 可调）。大批量时建议错峰。
* 改了版本：每一行都记录了 pi / claude 的版本号；批次中途版本变了报告会警告。Claude Code 已锁定自动更新。
* `--keep-dirs` 把每次运行的 HOME 和配置目录留在 `runs/<label>/<run>/env/`（很大，只在排查时用；不会被打包）。
* 提示 “another arena command (...) is already using the workspace root”：另一个 `day1`/`run`/`smoke`/`calib` 还在跑
  （比如别的终端窗口、tmux 里的会话）。等它结束或 Ctrl-C 它；进程一结束锁就自动释放，不会残留。
* 结果文件怎么拿出 WSL：`day1`/`pack` 结束时会打印 Windows 路径（`\\wsl.localhost\...`），在资源管理器地址栏粘贴即可；或者 `explorer.exe .`。

## 以后：对比 pi 的一个定制变体

变体 = 一个目录，里面只放你要改的东西，叠加在空白基线之上（模型/网关配置保持不变）。目录结构就是 pi 的 agent 目录：
`AGENTS.md`、`APPEND_SYSTEM.md`、`SYSTEM.md`、`extensions/`、`skills/`、`prompts/`、`mcp.json`，以及 `settings.json`
（和基线的 settings.json 逐键合并，变体里的键优先）。

```bash
python3 arena.py run --label base --agents pi,cc --reps 5                                   # 基线（pi 和 claude 一起）
python3 arena.py run --label v1 --agents pi --reps 5 --pi-config ~/pi/variants/v1           # 只跑 pi 变体
python3 arena.py run --label v2 --agents pi --reps 5 --pi-extra "-e /绝对路径/ext.ts"        # 也可以只加一个扩展（用绝对路径）
python3 arena.py report --label base --label v1 --label v2
python3 arena.py pack                                                                       # 把这些一起打包发我
```

报告会把同一个 agent 的不同配置分成不同的“臂”（`pi@base`、`pi@v1` …），分别对 claude 比，
并且把 `v1` 对 `base` 比（变体 vs 基线）。每一行结果都记录了变体目录的指纹和额外参数；
`--resume` 时如果变体内容变了会拒绝继续。局限：基线与变体是分开的两批，不是同一轮里交错跑的，
网关忙闲造成的耗时漂移不会被抵消（token / 缓存 / 成本不受影响）；v1 版本会支持在同一轮里交错多条“臂”。
