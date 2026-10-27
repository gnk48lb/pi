# pi 定制与评测路线图

Oct 17, 2026 · @gnk48lb

## 一页纸摘要

**目标。** 把 pi 调成“同模型、同思考强度下，在常见编码任务的多数指标上不输 Claude Code”的 harness，同时守住 pi 最大的卖点：省钱。省钱靠 KV 缓存命中，所以前缀（工具、系统提示、历史）只能追加、不能改写；缓存断一次，那一轮的输入费是正常读缓存的 25–50 倍。

**策略。** 先量后改。先建本地裁判台（12 题，每题至少 3 次，固定版本，按题记胜/平/负），再一次只改一处，先配置层、后扩展层，每次改动都要过缓存回归测试。压缩阈值、预算这类数字用自己的任务量出来，不照搬别人的。

**现状。** pi 能跑：1.3.0 已在本地模拟服务器上跑通真实会话，前缀逐轮严格追加，系统提示加 4 个内置工具只有 1.5k token 左右；经 magpie 的真实会话稳态缓存命中 93–97%。10 月 17 日你已定下模型（开发期 DeepSeek、期末小规模 Claude）、预算与“基线用空白配置”。评测环境已就位：WSL 里的 Claude Code 已升到 2.1.302 并锁定，经 magpie 可用；评测台 arena v0.1 已写好，第一轮（day1）已在你的 WSL 里跑完：magpie 的用量可加、网关缓存稳（命中 95–98%，没有整段未命中）、两边默认强度大体对得上；2 题试点里 pi 比 Claude Code 便宜 17–31%，但小于单次波动（变异系数约 30%），还不能算赢；12 题套件（8 题开发、4 题留出，留出的先不碰）也已做好，等你在 WSL 里用一条命令 suite 跑开发集。

**接下来三步。**

1. 在 WSL 里跑开发集：python3 arena.py suite（8 道开发题 × 2 个 agent × 3 次 = 48 次运行，约 1–1.5 小时，放进 tmux，可断点续跑），把它生成的结果文件发回来（不含密钥）。
2. 看套件数据，定三件事：每道题的难度合不合适（太易或太难的题分不出高下）、3 次重复下的噪声与平局带、pi 与 Claude Code 在 8 道开发题上的第一张完整记分板。
3. 噪声量出来后，先做一个精简默认档案，再一次只加一项（扩展、技能、工具），每项过缓存回归与胜负表。

## 目标与“胜”的定义

“胜”= 同模型、同思考强度、同任务集下，pi 在记分板的多数指标上不输 Claude Code，并有几项明显领先。不要求全胜，也不比模型本身、界面或生态。

| 指标 | 怎么量 | 方向 | 初始假设（基线跑完才算数） |
| --- | --- | --- | --- |
| 通过率 | 每题至少 3 次，隐藏验证器判分 | 越高越好 | 持平或略低；长任务 Claude Code 更稳 |
| 每题成本 | 事件流里的 token × 同一张价目表重算 | 越低越好 | pi 更低 |
| 未命中缓存的输入 token | 每次请求里没被缓存接住的输入 token（Claude Code 的用量按“可加”读）；首个请求（冷启动）与其余请求分开记 | 越高越好 | pilot 实测：冷启动时 pi 远低于 Claude Code（约 1.1–1.6k 对 1.8 万）；其余请求每次约 500–800（pi 略多）；以 suite 的数据为准 |
| 缓存命中率（诊断） | cacheRead ÷（input + cacheRead + cacheWrite） | 只作诊断，不判胜负 | 前缀越大命中率越高（pilot：Claude Code 97%、pi 82%，成本却是 pi 更低），所以不拿它比两边；用来发现缓存断崖 |
| 首轮前缀体积 | 第一次请求里 system + tools 的 token 数 | 越低越好 | pi 更小 |
| 耗时与轮数 | 墙钟秒数、LLM 调用次数 | 越低越好 | 未知 |
| 工具失败率 | 编辑未命中、命令报错 ÷ 工具调用数 | 越低越好 | 未知；pi 的 edit 要求精确匹配 |
| 改动最小性 | diff 行数 ÷ 参考解行数，有无误改测试 | 越低越好 | 未知 |
| 卡死率 | 超时、死循环、需人工介入的运行数 ÷ 总运行数 | 越低越好 | 未知 |

判胜负按题配对：同一题取 3 次的中位数，差距超过 Claude Code 自己两次运行的波动才算胜或负，否则算平。暂定阈值是成本 ±10%、通过率 ±1 题，基线跑完后用实测噪声校准。

三条底线，任何改动都不能破：

- 未命中缓存的输入 token 不高于基线（命中率只作诊断），这是 pi 的护城河。
- 通过率不因省钱而掉出噪声范围。
- 不为评测题写死答案：开发集上调参，留出集只在阶段末考一次。

“同强度”不等于旗标同名：pi 的 `--thinking` 与 Claude Code 的 `--effort` 档位未必对应。第一轮校准（calib，每档 3 次）的结果：pi 默认的 medium 在线上变成 high（线上实测只出现 low、high、max 三档），Claude Code 默认是 adaptive thinking 加 effort high，两边默认档大体对得上；各档输出 token 的差距小于同档 3 次之间的波动，只有 Claude Code 的 xhigh 明显更多。所以评测先用默认档对默认档；Claude Code 的 effort 到了网关那头变成什么，从这边看不到，待查。

## 现状快照与待办

截至 2026-10-23：pi 1.3.0 能跑，缓存体检通过（稳态命中 93–97%）；WSL 内存已调到 7.8 GB；模型、预算、“基线用空白配置”都已定。评测环境已就位：WSL 里的 Claude Code 2.1.302 已锁定，经 magpie 的 /v1/messages 实测可用（用量按“只计未命中部分”汇报，一个裸请求约 1.8 万 token）。评测台 v0.1 的第一轮（day1）你已在 10 月 21 日跑完，结论见“实验日志”；12 题套件（8 开发 + 4 留出）与一条命令 suite 已做好，等你在 WSL 里跑开发集。

| 项目 | 现状 | 为什么要紧 | 动作 |
| --- | --- | --- | --- |
| WSL 资源 | 2 CPU、7.8 GB 内存、8 GB swap；宿主机 16 GB | 跑评测够用；跑容器任务仍偏紧 | 已调好；需要容器时再把处理器加到 4。不要动 `networkingMode`（现在在 `[experimental]` 下，工作正常） |
| pi | 1.3.0（`~/.local/bin/pi`，安装器管理） | 近 30 天发了 15 个版本，评测前必须锁版本 | 评测前锁定；每次 `pi update` 之前先跑缓存回归 |
| Claude Code | WSL 里已是原生安装的 2.1.302，自动更新已锁定；Windows 版同为 2.1.302。官方 npm 最新 2.1.301，stable 渠道 2.1.292（10-16 查询）。day1 实测：默认暴露 19 个工具，首个请求约 1.77 万 token | 对照组已就位；近 30 天又发了 26 个版本，评测前要锁版本 | 已完成：用 `DISABLE_AUTOUPDATER=1` 锁定，配置目录单独隔离 |
| 模型与网关 | pi 经 magpie 用 `workbuddy-ai/deepseek-v4.1-flash`（上下文 100 万）；Claude Code 经 magpie 的 /v1/messages 用同一个模型（\[1m\] 后缀只在客户端，线上会被去掉）；magpie 回传缓存字段，Anthropic 协议的 input\_tokens 只计未命中部分 | 开发期两边都用 DeepSeek，期末再用 Claude 小规模考一次 | 已验证：`/v1/messages` 可用，用量字段按“可加”解读；cacheprobe 量过（104 个请求，两种协议各半，间隔 1–160 秒）：重复请求命中 97.8%，追加式增长 95–97%，没有整段未命中（10-19 手测见过一次），命中量都是 128 token 的整数倍 |
| 代理 | WSL 内走 127.0.0.1:7897，`NO_PROXY` 含 127.\* | 容器里默认用不了这个代理；改 `.wslconfig` 时别动网络模式 | 先记录，上容器时再处理 |
| Docker | 已安装，Docker Desktop 的 WSL 集成目前关闭，连不上 | 容器任务（Harbor）现在跑不了；本地跑分器也用不着 | 需要容器任务时再打开 |
| Gemini 写的 pi 配置 | pi-web 已卸载、packages 已清空；还剩 AGENTS.md、APPEND\_SYSTEM.md、models.json、context-guard.ts | 基线用空白配置；这几项逐个当实验 | 审查结论见本节末尾 |
| jq | 缺失 | 无碍 | 用 python 代替，不必装 |

待办：

- [x] 运行第二个探针脚本，把输出贴回来（脱敏配置 + 缓存体检）
- [x] 定下模型、预算与“基线用空白配置”（10-17）
- [x] 升级 pi 到 1.3.0；WSL 内存调到 8 GB；卸载 pi-web、清空 packages
- [x] 补上 Claude Code 连 magpie 的 base URL 与模型名（不要贴 key）
- [x] 把 WSL 里的 Claude Code 升到 2.1.302 并锁定（`DISABLE_AUTOUPDATER=1`），配置目录隔离
- [x] 验证 magpie 是否支持 `/v1/messages`
- [ ] 把评测用的配置（空白基线与各档案）放进一个 git 仓库，方便回滚和对比
- [x] 搭评测 v0：运行器、两个 agent 的日志归一化、2 题 × 5 次噪声校准（day1 已在 10-21 跑完，数据见实验日志）
- [x] 做 12 题套件（8 开发 + 4 留出）和 suite 命令（v0.1），模拟网关自测全过
- [ ] 在 WSL 里跑 suite，把结果文件发回来
- [ ] 按套件数据校准题目难度，重估噪声与平局带

来源：npm 注册表（2026-10-16 查询）、[WSL 配置文档](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)、你贴的诊断输出。

### Gemini 写的配置：审查结论

这些配置都不破坏缓存前缀（静态文字，或只改新结果、不改旧历史），缓存体检里命中率稳定在 93–97% 也印证了这一点。真正要问的是它们对通过率和轮数的影响。基线一律用空白配置；下面每一项只是候选，实验证明有益才进默认档案。

| 文件 | 做了什么 | 担心什么 | 处理 |
| --- | --- | --- | --- |
| AGENTS.md（约 60 token） | 声明运行环境是 WSL2；项目里没有自己的 AGENTS.md 时，先看清单文件再跑构建与测试 | “先看清单文件”会让每个任务多一轮工具调用 | 候选：当作一个实验，看轮数与通过率 |
| APPEND\_SYSTEM.md（约 157 token） | 四条规则：别整读大文件；日志只留末尾；精准编辑；有歧义先问一个问题 | “有歧义先问”在非交互评测里等于认输；日志只留末尾 80 行会藏掉报错开头，还与 context-guard 重复 | 拿掉“先问”那条；其余三条各当一个实验 |
| context-guard.ts（扩展，不进提示词） | 拦截不带范围的锁文件与依赖目录读取；bash 输出超过 160 行或 8000 字符只留头 40 行与尾 100 行，read 超过 300 行只留头 220 行与尾 40 行，完整输出存到临时文件 | 比 pi 内置截断更严，read 会藏起文件中段，模型可能多读几轮，通过率下降 | 最有价值的候选：当作“更严截断”实验，量每轮新增 token、轮数与通过率 |
| models.json | magpie 的模型清单；开了 sendSessionAffinityHeaders（让网关把同一会话路由到同一后端，有利于缓存命中） | 无 | 保留；DeepSeek 价格填对了（输入 0.15、输出 0.6、缓存读 0.003 美元每百万 token） |
| 两个 pi-web 包 | 网页界面，注册了 8 个会话与中继工具 | 首个请求的前缀从 1.6k 涨到 4.9k token（约多 3.3k） | 已卸载 |

## KV 缓存与省钱护城河

你的直觉大体对：前缀保持不变、历史只追加、压缩要少而狠。要修正三点：“静态”指不改写，不是不更新；压缩阈值该测出来，不能凭感觉；缓存断一次，那一轮的输入费是正常读缓存的 25 倍（Sonnet 5.5）到 50 倍（DeepSeek V4.1 Flash）。

### 三条铁律

| 铁律 | 具体做法 | 依据 |
| --- | --- | --- |
| 前缀逐字节相同 | 缓存按“从开头到某一点”的完全相同前缀匹配，顺序是 tools → system → messages；前面一变，后面全废 | [Anthropic 文档](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)、[Claude Code 博客](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything) |
| 历史只追加，动态信息放尾部 | 时间、被改动的文件等放进下一条消息（Claude Code 用 `<system-reminder>`）；序列化要确定，不改写旧消息 | [Claude Code 博客](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything)、[Manus](https://manus.im/en/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus) |
| 会话中途不动工具、模型、思考参数 | 改工具定义会让整个缓存失效；缓存按模型隔离，换模型要重建；思考参数变化会让消息缓存失效，部分模型连 system 和 tools 也失效 | [Anthropic 文档](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)、[Claude Code 博客](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything) |

### 价格：断一次有多贵

| 项目 | Anthropic（Sonnet 5.5） | DeepSeek V4.1 Flash（错峰价） |
| --- | --- | --- |
| 命中缓存（读） | 基础输入价 × 0.05 | $0.003 / 百万 token |
| 未命中或首次写入 | 5 分钟缓存写 × 1.25，1 小时缓存写 × 2 | $0.15 / 百万 token，无写入加价 |
| 断一次 ÷ 正常读 | 25 倍 | 50 倍 |
| 缓存机制 | 显式断点（最多 4 个）或自动缓存，向前回看 20 块 | 自动，磁盘缓存，尽力而为 |
| 保留时间 | 默认 5 分钟，每次命中续期；可选 1 小时 | 不再使用后数小时到数天内清除 |
| 最小可缓存长度 | 512 token | 页面未给出 |
| 用量字段 | cache\_read\_input\_tokens、cache\_creation\_input\_tokens | prompt\_cache\_hit\_tokens、prompt\_cache\_miss\_tokens |

来源：[Anthropic 提示缓存](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)、[DeepSeek 价格页](https://api-docs.deepseek.com/quick_start/pricing/)、[DeepSeek 上下文缓存](https://api-docs.deepseek.com/guides/kv_cache/)。DeepSeek 错峰价是高峰价的一半；高峰为周一至周五 UTC 01–04 点和 06–10 点（台北时间 09–12 点、14–18 点，中国法定假日除外）。跑评测请放在错峰时段，或全程用同一张价目表重算。你的 magpie 网关是否透传缓存字段、是否按此计价，还没验证。

### 阶梯式压缩：方向对，阈值要测

压缩会重写前缀，每次都要付一笔固定费用：生成摘要，再把新上下文重新写进缓存。所以“少压几次、一次压到位”比“勤压”便宜，这点你对。但最优阈值并不贴着窗口上沿。我用一个简化模型测算：400 轮、每轮新增 2,000 token、压缩后保留 27k、摘要 3k token；Anthropic 的输出价按基础输入价的 5 倍假设，其余价格取自上表。

- 基准参数下，阈值在 100k–160k 之间任取，总成本都在最优值的 9% 以内；曲线底部很平。但把每轮新增改成 1,000–4,000 token、压缩后保留量改成 15k–50k，最优点会在 60k–300k 之间移动，100k–160k 的最差偏离升到 29%。
- 基准参数下，从不压缩贵 1.5–2.7 倍；每 40k 就压一次贵 1.4–1.9 倍。
- 基准参数下，Claude Code 式的“复用主对话前缀”做摘要，比 pi 默认的“独立请求做摘要”便宜约 20–25%。pi 的文档写明摘要请求会关闭缓存写入，且把对话序列化成文本另发。

两点提醒：这是形状，不是精确数字；若某模型在 pi 里登记的窗口是 1M，默认要到约 98 万 token 才压缩，远在最优点之后，需要用 pi 的按模型压缩覆盖项单独设置。常见任务多在 20–60 轮内结束，大多碰不到压缩，所以它是长任务阶段的杠杆，不是第一优先。

### pi 已经做对的和可以改的

- 已做对：会话是只追加的 JSONL 树；中途改提示词或工具时只追加差异（0.86.0 起）；MCP 连接变化不再改写 codemode 描述（0.99.2）。
- 已有保温：`cacheWarming` 默认 `streaming`，运行中保温；设为 `idle` 连空闲期也保温。它要求模型声明 `promptCache` 寿命，且预估能省 ≥ $0.05 才触发。
- 已有提示：`showCacheMissNotices` 默认关，打开后会提示明显的缓存未命中。
- 可以改：摘要走“复用前缀”的分叉，做成扩展实验；给大窗口模型设更早的压缩点。
- 前车之鉴：1.2.0 修了一个 bug——扩展触发的回合会在第一次工具调用后撤掉 `before_agent_start` 加的 system 段，每次运行断两次缓存。扩展一动提示词，就可能丢掉护城河。

### 会破坏护城河的清单

- [ ] AGENTS.md、APPEND\_SYSTEM.md 里写了日期、时间、git 状态等每次会变的内容
- [ ] 扩展在 `context` 事件里每轮裁剪或改写历史消息（名叫 context-guard 的扩展要先审这一条）
- [ ] 扩展或包在会话中途增删工具、改工具描述（实测：tool\_search 或 setActiveTools 加载一个工具，tools 数组多一项，其后的前缀失效一次；/reload 只会新增工具，不会关掉已移除的，要关就得重启会话）
- [ ] 中途切换模型或思考强度
- [ ] 工具列表顺序或 JSON 键序不稳定
- [ ] 人停顿超过缓存寿命（Anthropic 默认 5 分钟），下一轮整段重写
- [ ] 网关或代理改写请求，或不回传缓存字段，让你看不见命中率

### 守门：缓存回归测试

每次改 harness 都过两关。静态关：用本地仿真服务连发 N 轮，断言每轮请求体以上一轮为严格前缀，tools、system、旧消息逐字节一致，秒级、免费。动态关：在真实端点跑固定的 8 轮任务，断言第 3 轮起的命中率不低于基线减 2 个百分点。命中率定义同上：cacheRead ÷（input + cacheRead + cacheWrite）。

## 评测方案（裁判台）

先用不依赖 Docker 的本地跑分器，搭一个 12 题的小裁判台；WSL 调大内存后再接 Harbor。每次改动先过缓存回归测试，再看记分板。

### 一次跑分的流水线

1. 取题：把该题的初始仓库拷进一个全新的临时目录；题面文字两边逐字相同。
2. 启动被测 agent：pi 用 `pi -p --mode json --no-session`，Claude Code 用 `claude -p --output-format stream-json`；各自指向全新的空白配置目录，权限全开，不联网，不接 MCP。
3. 记事件流：每次 LLM 调用的 input、cacheRead、cacheWrite、output，每次工具调用的耗时与是否出错。
4. 跑隐藏验证器：记通过与否、diff 行数、有没有改测试。
5. 归一成一行：agent、版本、模型、强度、题、第几次、通过、耗时、各类 token，成本按统一价目表重算。
6. 汇总记分板：逐指标按题配对，判胜、平、负。

### 题库 v0.1：12 题，已做好

| 题 | 语言 | 类别 | 内容 | 验证方式 | 集 |
| --- | --- | --- | --- | --- | --- |
| p01 | Python | 修 bug | pager：让库的行为与 README 一致，测试全过 | 隐藏规格测试，原有测试不破 | 开发 |
| p02 | Node | 加功能 | csvstat：加 `--format` 选项（json、table、text），含测试与文档 | 隐藏规格测试，原有测试不破 | 开发 |
| p03 | Python | 重构 | invtrack：函数与参数改名，保留带弃用警告的旧名 | 隐藏改名检查，原有测试不破 | 开发 |
| p04 | Node | 调试 | shelfwise：五个测试失败，在分层仓库里找根因，通用地修好 | 隐藏测试 | 开发 |
| p05 | Python | 性能 | nightly：四个慢函数在大输入上变快（每例限 25 秒），结果不变 | 隐藏性能与正确性测试 | 开发 |
| p06 | bash | 构建 | logrotate-lite：修好 make test、lint、dist | 隐藏验证脚本 | 开发 |
| p07 | Python | 写测试 | discounts：给没有测试的模块补单测 | 变异检验：至少 8 个测试，13 个故意写错的版本里抓到 10 个 | 开发 |
| p11 | Python | 多层功能 | bookshop：软删除与恢复，跨迁移、仓储、服务、接口四层 | 隐藏规格测试，原有测试与旧迁移不破 | 开发 |
| p08 | Node | 从零写 | logsum：按规格写访问日志汇总命令行工具，含测试与文档 | 隐藏测试 | 留出 |
| p09 | Python | 安全修复 | notes\_app：存储层的路径穿越与符号链接逃逸 | 隐藏攻击测试 | 留出 |
| p10 | Python | 代码库问答 | taskq：文档过时，只读回答 5 个问题 | 答案要点逐条判，且不得改动任何文件 | 留出 |
| p12 | Node | 调试 | spendsum：Excel 风格 CSV 导出导致崩溃，根因在栈追踪下面三层 | 隐藏测试，且要求补上新测试 | 留出 |

开发集 8 题（p01–p07、p11），留出集 4 题（p08、p09、p10、p12）；留出集只在阶段末考一次。语言是 7 题 Python、4 题 Node（纯 JavaScript，node --test）、1 题 bash，没有 TypeScript。每题都验证过“未解必败、参考解必过”，隐藏验证器还用故意写错的解检验过能分辨对错。题目难度还没校准，要等 suite 的第一批数据。

### 公平规则

- 同一模型 ID（在日志里核对）、同一端点；强度先在探针题上校准。
- 版本锁定并写进每行结果；Claude Code 用独立的 `CLAUDE_CONFIG_DIR`，pi 用独立的 `PI_CODING_AGENT_DIR`。
- 题面、超时、最大轮数相同；两边交替运行（A B A B），避开服务端波动。
- 每题至少 3 次；先拿 2 道题各跑 5 次测噪声，再定“平局带”。
- 价目表只用一张；DeepSeek 在错峰时段跑。
- 日志全留。网关报错、限流的运行标记后重跑，不静默丢弃。
- 基线用各自的默认工具集，但去掉联网类工具；再另做一轮“工具集对齐”，分开看提示词差异和工具差异。

### 16 GB 笔记本能不能跑 Harbor

Harbor 本身只是 Python 调度器，吃内存的是每个任务的容器。把 WSL 调到约 8 GB / 4 CPU，一次跑 1–2 个小任务可以。Terminal-Bench 4.0 现在不适合：它有 66 题，每题中位估时 4 小时，Claude 级模型每题约 $13–16，还含 GPU 题（[Vals AI](https://vals.ai/benchmarks/terminal-bench-4)）。所以先本地跑分器，后接 Harbor 的小题集。

### 业界怎么比

Artificial Analysis 的 [Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents/comparisons/claude-code-vs-opencode) 同样报每题成本、耗时、轮数、token 和缓存命中率，我们的记分板列与它对齐；它也提醒缓存命中率会随服务商路由大幅变化。它的头条对比里 Claude Code 跑 Sonnet 5.5、Opencode 跑 GLM-5.3，模型不同，所以我们坚持同模型。

### arena v0.1：已经做出来的部分

评测台是纯标准库 Python，放在 WSL 的 `~/pi/arena`。第一轮用一条命令 `python3 arena.py day1` 按下表前五步跑完（已跑完）；第二轮用一条命令 `python3 arena.py suite` 跑开发集的 8 道题（表里最后一行）；4 道留出题要显式加 --tasks held，阶段末才用。两条命令都可断点续跑，结束时把结果打成一个文本文件，你只需回传这一个文件。

| 步骤 | 回答什么问题 | 约耗时 |
| --- | --- | --- |
| setup + selftest | 读你的 pi 与 Claude Code 网关配置，生成空白基线；用模拟网关自测整条流水线（不花 token） | 3 分钟 |
| smoke | 两边各问 3 次 PONG：首个请求多大、缓存命中多少，并自动判定 magpie 怎样汇报 Claude Code 的用量 | 2 分钟 |
| cacheprobe | 不经过 agent，直接量网关缓存：相同请求隔多久还命中、追加式对话的命中率、有没有整段未命中 | 25 分钟 |
| calib | 同一道短题跑遍两边所有强度档位（pi 的 `--thinking`、Claude Code 的 `--effort`），看线上差多少，选出“同强度”的配对 | 约 20 分钟 |
| pilot | 2 题 × 2 个 agent × 5 次，隐藏测试判卷：单次成本、各指标的波动（决定平手带宽）、流程是否跑通 | 约 90 分钟 |
| suite（第二条命令） | 8 道开发题 × 2 个 agent × 3 次 = 48 次运行，隐藏验证器判卷；同一题的几次连着跑，每题只有一次冷启动；留出的 4 题要加 --tasks held 单独跑，阶段末才用。回答：每题难度合不合适，pi 与 Claude Code 的第一张完整记分板 | 约 1–1.5 小时 |

对比 pi 的定制版本时，变体是一个目录，叠加在空白基线之上（`AGENTS.md`、扩展、skills、`settings.json` 逐键合并），用 `--pi-config` 指向它。报告把 `pi@base`、`pi@v1` 分成不同的臂，各自对 Claude Code 比，再把 v1 对 base 比。

状态：day1 已在你的 WSL 里跑完。v0.1 已全部在模拟网关上用真实的 pi 1.3.0 与 Claude Code 2.1.308、2.1.309 自测（283 项检查全过，Python 3.12 与 3.11 各一遍），另做过含 Ctrl-C 中断续跑和 suite 的整条用户流程演练，以及 v0 装着 day1 数据时解压 v0.1 覆盖再跑 suite 的升级演练；arena-v0.1.tar.gz 已交给你，等你在 WSL 里跑 suite，把结果文件发回。

## 阶段路线图

先建裁判台、再改 pi：七个阶段，每段有出口标准，过关才往下走；第 3–5 阶段可反复迭代。

&#91;embedded content: 路线图 · 7 个阶段、7 个出口标准、1 条持续通道\]

蓝色三段是可反复迭代的定制层，一次只改一处；持续通道贯穿全程，不属于任何阶段。

## 定制杠杆清单

杠杆按风险从小到大排：先动配置，再写扩展，最后才加包。每一项都先过缓存回归测试，再看记分板。

| 层 | 杠杆 | 主要动的指标 | 缓存风险 | 阶段 |
| --- | --- | --- | --- | --- |
| 运行方式 | print、JSON 事件流、RPC、SDK，用来自动化评测 | 评测效率 | 无 | 1 |
| 配置 | 默认思考档与按模型思考档（`defaultThinkingLevel`、`modelThinkingLevels`） | 通过率、成本、耗时 | 会话中途改会断缓存，开局定好 | 3 |
| 配置 | 压缩阈值与按模型覆盖（`compaction.reserveTokens`、`compaction.modelOverrides`） | 长任务成本与稳定性 | 低，压缩本来就重写前缀 | 3 |
| 配置 | 工具集（`defaultTools`、`--tools`） | 前缀体积、工具失败率 | 会话中不动就无风险 | 3 |
| 配置 | 缓存保温（`cacheWarming`、模型的 `promptCache` 寿命） | 间歇使用时的成本 | 本身就是保缓存 | 3 |
| 上下文 | 精简、静态的 AGENTS.md 与 APPEND\_SYSTEM.md | 前缀体积、行为 | 内容必须静态，不写日期与状态 | 3 |
| 上下文 | 在 AGENTS.md 里写明“互不依赖的读取与搜索放进同一轮并行调用” | 轮数、成本（每轮都要重读整个上下文，少一轮就少一次） | 静态文字，无风险 | 3 |
| 上下文 | 整体替换 SYSTEM.md | 前缀体积、行为 | 同上；可能丢掉默认的工具用法指引 | 4 |
| 扩展 | 验证回路：编辑后自动跑测试，在 `agent_before_settle` 里请求续跑一次 | 通过率 | 续跑内容追加在尾部，不碰前缀；要防无限续跑 | 4 |
| 扩展 | 防卡死：同一工具调用反复出现时提醒或终止（`tool_call`） | 卡死率、成本 | 低 | 4 |
| 扩展 | 更严的输出截断与分段读取提示（`tool_result`）；先量内置截断够不够 | 每轮新增 token、成本 | 只改新结果，不改旧历史，安全 | 4 |
| 扩展 | 缓存安全的压缩：摘要复用主对话前缀 | 长任务成本（仿真基准参数下约 −20–25%） | 请求前缀须与主对话逐字节一致才有收益 | 4 |
| 扩展 | 空闲压缩：缓存过期后下一轮本来就要整段重写，趁此压缩 | 间歇使用时的成本 | 低 | 4 |
| 扩展 | codemode（`defaultTools: ["+codemode"]`） | 多步调用的轮数与 token | 多一个工具的前缀；要实测 | 4 |
| 技能 | Agent Skills：前缀里只有名称与描述，正文按需加载 | 通过率（领域经验） | 前缀只增名称和描述 | 5 |
| 包 | pi 包与 MCP（如现有的两个 pi-web 包） | 能力面 | 每个工具都是前缀税；会话中途才连接会断缓存 | 5 |
| 配置 | 能力档案：每个档案是一个配置目录或一组启动参数（--no-extensions -e …、--tools），会话开始前选定 | 通过率、前缀体积、成本 | 档案在会话内不变就无风险；中途切换 = 一次整段重计费（已实测） | 5 |
| 配置 | 路由：会话外按任务预选档案（人工、规则或一次小模型调用） | 通过率与成本的差、选档准确率 | 无，发生在会话开始之前 | 5 |
| 包 | MCP 与扩展工具设成 codemode 或 deferred 暴露，而不是 direct | 前缀体积、工具选择准确率 | codemode 的前缀基本不变；deferred 每加载一个工具断一次缓存（已实测） | 5 |

字段与事件名取自 pi 1.3.0 随包文档（settings.md、compaction.md、extensions.md）。空闲压缩借鉴 Claude Code 2.1.299 的 idleCompaction（见趋势雷达）。

### 能力档案：装得多、开得少

你提的想法：把常用的扩展、技能、提示模板、工具、MCP 先装好，默认关着，任务开始前判断开哪几个。结论：方向对，pi 已经自带这套机制；要改的是“什么时候切”和“谁来判断”。

| 类型 | 装了不用，占前缀吗 | 要不要逐个选 | 机制（pi 1.3.0 文档） |
| --- | --- | --- | --- |
| 提示模板 | 不占；你敲 `/名字` 才展开 | 不用，全装 | prompts 目录；`--prompt-template` |
| 技能 | 只占名称、描述与路径，正文按需读；装太多会拉长前缀、让选择变差 | 基本不用；可用 `disable-model-invocation` 隐藏 | skills 目录；`--skill` |
| 只挂钩子、不注册工具的扩展 | 不占 | 不用 | `extensions` 设置里的 `+`、`-`、`!` 过滤；`-e` |
| 注册了 direct 工具的扩展、direct 的 MCP | 每个工具的定义都占（pi-web 实测多出约 3.3k token） | 要选 | `--tools`、`defaultTools` 的 `+`/`-`、`-xt` |
| 设成 codemode 或 deferred 的 MCP 与扩展工具 | codemode 只占一个工具；deferred 平时不占，用时由 tool\_search 加载 | 少选：用懒加载代替开关 | `exposure` 设置；`codemode`、`tool_search` |
| AGENTS.md、APPEND\_SYSTEM.md | 全占 | 要选 | 每个档案放自己的版本 |

**切换的规则（实测加文档）**

- 一次工具集变化 = 一次整段重计费。模拟服务器实测：tool\_search 或 setActiveTools 在会话中途加载一个工具，tools 数组多出一项，该请求的仿真命中率只有 48%，下一个请求回到 96%。代价与当时的上下文成正比：第 1 轮（约 2k token）几乎为零；上下文 10 万 token 时约等于 50 个正常轮次的输入成本（DeepSeek）。
- `/reload` 只会把新加进 `defaultTools` 的工具开起来，不会关掉已移除的（settings.md）：“取消注释”可以 reload，“注释掉”要重启会话。
- 所以：档案在会话开始前定好；想换档案就开新会话，需要接力就让它先写一份交接摘要。
- Anthropic 自家的工具搜索声称不破坏提示缓存（被推迟的工具不进初始提示，搜到后才展开）；pi 的 tool\_search 在 openai-completions 这条路径上实测是改 tools 数组，要按上面的规则对待。

**谁来判断（按成本从低到高）**

1. 你自己：看一眼清单，5 秒，零 token。
2. 规则：任务里的关键词对应档案（如“查 issue、查网页”加 web 档）。
3. 会话外的一次小模型调用：输入能力清单（每项一句话、前缀成本、副作用）加任务描述，输出要开的清单，再用清单校验；约 1–2k token，DeepSeek 下不到 0.001 美元。评测里这一步必须自动化，并单独记账。

**怎么验证它值得**

- 三组对照：固定精简默认、全开、路由选档。看通过率、总成本（含路由那一步）、轮数、前缀 token、选档准确率（对照人工标注）。
- 顺序：空白基线、精简默认、逐个加包、最后才上路由。现在先装一堆，后面的增量就没法归因。
- 安全：每个第三方扩展、技能、MCP 都是用你的凭据运行的任意代码，先读源码再装，锁版本。
- 旁证：Anthropic 的数据里，5 个 MCP 服务器 58 个工具的定义约 55k token；改用工具搜索后，Opus 4 的 MCP 评测准确率从 49% 升到 74%，Opus 4.5 从 79.5% 升到 88.1%。来源：[Anthropic 工程博客](https://anthropic.com/engineering/advanced-tool-use)。

## 跟进 pi 更新

pi 近 30 天发了 15 个版本，Claude Code 发了 26 个（npm，截至 10 月 15 日）；两边都在快速变，所以评测必须锁版本，升级要走固定演练。

&#91;embedded content: npm 注册表 · @earendil-works/pi-coding-agent · 2026 年第 27–42 周（截至 10 月 15 日）\]

Pi 1.0 的发布文章称它是人和企业都能依赖的稳定软件，但没有给出语义化版本或扩展 API 稳定性承诺（[Earendil](https://earendil.com/posts/pi-1-0/)）；此后的 1.2.0 仍有破坏性变更。

### 近期破坏性变更（扩展作者必读）

| 版本 | 日期 | 变更（节选） | 对我们的影响 |
| --- | --- | --- | --- |
| 1.2.0 | 10-12 | `before_agent_start` 也会在 `triggerTurn` 触发的运行里触发，要按 `messageType` 区分；`pi.sendUserMessage()` 必须带 `deliverAs`；会话启动期间算“忙” | 用到这些的扩展要改；先查 context-guard.ts |
| 1.0.3 | 10-05 | provider `azure-openai-responses` 改名 `azure`，`auth.json`、`models.json`、`settings.json` 里的键都要改；旧会话恢复后缓存不复用 | 只用 Azure 才受影响 |
| 0.87.0 | 09-21 | 移除 `shouldStopAfterTurn`，改用 `finishTurn`；给 `session.agent.state.messages` 赋值不再改变后续请求的历史；新增 `agent_before_settle` 事件 | 若 context-guard.ts 靠赋值改历史，它在此之后已不起作用 |
| 0.86.0 | 09-19 | 自定义 provider 改为收到规范化的 transcript context，要用 `getCurrentSystemPrompt()` 和 `getCurrentTools()` 读取；工具参数与结果须可 JSON 化；`user_bash` 出错即拒绝执行 | 写过自定义 provider 扩展的要看 |

来源：pi 1.3.0 随包 CHANGELOG 与 [pi.dev/changelog](https://pi.dev/changelog)。

### 升级演练

1. 固定：pi 用 `npm i -g @earendil-works/pi-coding-agent@<版本>` 安装并记录；Claude Code 升到 stable 渠道后设 `DISABLE_AUTOUPDATER=1`；版本号写进每条评测结果。
2. 看变更：发版时读 changelog 的 Breaking Changes、Caching、Compaction 三段；用 `npm view @earendil-works/pi-coding-agent dist-tags` 看有没有新版。
3. 隔离试装：在独立的 `PI_CODING_AGENT_DIR` 里装新版，跑缓存回归测试加 3 道冒烟题。
4. 过关再升，并写入实验日志：旧版 → 新版，指标变化。
5. 写扩展的纪律：只用文档里写明的事件和 API；每个扩展配一个“契约测试”，用 `--mode json` 装载并断言行为；语义变过的事件（如 `before_agent_start`）一律当高危处理。

## 编程 agent 趋势雷达

八条趋势里，三条直接决定评测怎么设计，两条给出 pi 可以尝试的扩展，其余是背景。优先级 P0 = 现在就做，P1 = 阶段 4 实验，P2 = 观察；每个季度复查一次。

| 趋势 | 证据 | 对 pi 的含义 | 行动 |
| --- | --- | --- | --- |
| 缓存命中率成了一等指标 | Claude Code 团队把缓存未命中当事故，命中率过低就报 SEV（[Anthropic](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything)）；Manus 称它是最重要的指标（[Manus](https://manus.im/en/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)）；Artificial Analysis 公布各 harness 的缓存命中率，Claude Code 95%、Opencode 97%（[AA](https://artificialanalysis.ai/agents/coding-agents/comparisons/claude-code-vs-opencode)） | 这是 pi 的卖点，也是最容易被扩展弄坏的地方 | 缓存回归测试，阶段 1，P0 |
| harness 被单独评测 | Coding Agent Index 综合 DeepSWE、Terminal-Bench 4.0、SWE-Atlas-QnA，并报每题成本、耗时、轮数、token（[AA](https://artificialanalysis.ai/agents/coding-agents/comparisons/claude-code-vs-opencode)） | 记分板的列与业界对齐，便于外部对照 | 阶段 1，P0 |
| 外部基准在变 | Terminal-Bench 4.0 换用 mini-swe-agent、换了题集，分数不能与 2.1 比较（[Vals AI](https://vals.ai/benchmarks/terminal-bench-4)） | 外部基准只做参照，不当目标 | 自建记分板，P0 |
| 对照组也在飞快迭代 | Claude Code 近 30 天 26 个版本；10 月以来新增 Mods、hooks 的 `onFailure: "block"`、默认 Haiku 5.5（[havoptic](https://www.havoptic.com/releases/claude-code/2026/10)） | 对照组会漂移 | 锁版本、定期复测，P0 |
| 压缩更懂缓存 | Claude Code 的摘要复用主对话前缀（[Anthropic](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything)）；2.1.299 加了空闲压缩：200K+ token 的对话闲置约 54 分钟后压缩（[havoptic](https://www.havoptic.com/releases/claude-code/2026/10)） | pi 的摘要是独立请求，且只在逼近窗口时压缩 | 扩展实验，阶段 4，P1 |
| 用代码编排工具 | Anthropic 报告把 MCP 当代码 API 后，一个流程从约 150,000 token 降到 2,000，省 98.7%（[Anthropic](https://www.anthropic.com/engineering/code-execution-with-mcp)）；pi 1.0 起内置 codemode | 多步调用可省轮数与 token，但要沙箱并实测 | 试 `+codemode`，阶段 4，P1 |
| 技能与渐进披露 | Agent Skills 启动时只放名称与描述，相关时才读 SKILL.md（[Anthropic](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)）；pi 的 skills 沿用同一规范 | 领域经验可加，前缀只增一点 | 阶段 5，P2 |
| 长时程 harness | Anthropic 的做法是初始化 agent 加 `claude-progress.txt`、JSON 特性清单，每次只做一个特性并提交（[Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)）；Pi Durable 提供崩溃恢复与检查点，仍是实验性、API 可能变（[Earendil](https://earendil.com/posts/pi-durable/)） | 长任务稳定性是 Claude Code 的强项，pi 要靠扩展补 | 进度文件扩展，阶段 4，P2；Pi Durable 先观望 |

## 风险与待决事项

10 月 17 日你已定下：开发期用 DeepSeek、期末小规模用 Claude 考一次；Claude Code 走 magpie；Gemini 的配置审完再定，基线用空白配置；DeepSeek 预算不设限。还差一件事才能搭评测：Claude Code 连 magpie 的 base URL 与模型名。

### 待你决定

| 问题 | 选项 | 决定 / 我的建议 |
| --- | --- | --- |
| 同模型用哪个 | A. 两边都用 DeepSeek V4.1 Flash：Claude Code 走网关或官方 Anthropic 兼容端点，pi 走 magpie；B. 两边都用 Claude（Sonnet 5.5 或 Haiku 5.5） | 已定（10-17）：开发期用 A，期末小规模用 B 考一次。A 下 Claude Code 的提示词为 Claude 调过，可能吃亏，结论里要注明 |
| Claude Code 接什么 key | Anthropic 官方 key、某个网关的 key、DeepSeek 的 key | 已定：走 magpie。WSL 里的 Claude Code 2.1.302 经 magpie 的 /v1/messages 用同一个模型，已跑通（10-19、10-21） |
| magpie 网关 | 是否支持 `/v1/messages`、是否回传缓存字段、是否按 DeepSeek 价格计价 | 已验证回传缓存字段（探针三次相同前缀请求命中 6784 / 6944 token，真实会话稳态 93–97%）；`/v1/messages` 已验证可用；网关自己的计价不影响评测（成本按统一价目表由 token 重算） |
| Gemini 写的配置 | 保留、改写或推翻 | 已定：审完再定，基线一律用空白配置。审查结论见“现状快照与待办”一节 |
| 预算上限 | 基线一轮 = 12 题 × 3 次 × 2 个 agent = 72 次运行 | 已定：DeepSeek 不设限（免费）；Claude 每月 10 美元额度，本月已用完，期末考试可以晚一点。仍先在 2 道题上各跑 5 次，量出每次花费 |
| 工具箱怎么管（10-17 新增） | A. 先装一批扩展、技能、MCP，默认关，每个任务挑着开（你的想法）；B. 空白基线，再逐个加、每个都量增量 | A 的形态加 B 的顺序：先基线，再一次加一项，通过缓存回归与胜负表的才进“能力清单”，由档案选用。档案在会话开始前定好，不在会话中途切（见“定制杠杆清单”一节） |

DeepSeek 官方的 [Claude Code 接入指南](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/) 用 `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`、模型 `deepseek-flash[1m]`，并建议 `CLAUDE_CODE_AUTO_COMPACT_WINDOW=786432`。但它的 [Anthropic 兼容说明](https://api-docs.deepseek.com/guides/anthropic_api/)没写用量字段里有没有缓存命中数，所以 Claude Code 一侧的缓存命中率可能算不出来，要先实测。已实测（10-19、10-21）：magpie 回传缓存字段，按“可加”汇报，算得出来。

### 风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 对照组随版本漂移 | 结论过期 | 锁版本；每次升级后复测 |
| 过拟合评测题 | 开发集上赢、真实任务上不赢 | 开发集与留出集分开，留出集只考一次 |
| 噪声大于差距 | 判胜负变成抛硬币 | 每题至少 3 次，先测噪声再定平局带；day1 实测单次波动（变异系数）：成本 30%、输出 token 28%，所以 8 道开发题 × 3 次大约能分出 15–18% 的系统差距（12 题约 12–15%），更小的差距要再多 4 倍的次数 |
| 网关改写请求或不回传缓存字段 | 无法验证护城河 | 直连官方端点做缓存对照 |
| pi 的破坏性变更让扩展失效 | 扩展静默失效 | 契约测试；升级演练 |
| “pi 比 Claude Code 省”只是社交媒体上的说法 | 方向可能判错 | 我没法核实推特上的测评，Artificial Analysis 的对比页也没收录 pi；用你自己的数据验证 |
| 题目难度没校准 | 太容易（全过）或太难（全挂）的题分不出高下，白花预算 | suite 跑完先看每题的通过率与成本分布，调题或换题；留出集不参与调整 |
| 冷启动偏差 | 每个新缓存前缀的第一次运行要多付未命中 token（Claude Code 约 1.8 万，pi 约 1.1–1.6k），当成常态会放大差距 | 同题的几次连着跑，取中位数；报告把首个请求与其余请求的未命中 token 分开记，冷启动单列并剔出噪声统计 |

## 实验日志

每个实验一行：日期、做了什么、看到什么、结论。基线跑完后，每次改动都在这里追加，旧的在下。

| 日期 | 实验 | 结果 | 结论 |
| --- | --- | --- | --- |
| 2026-10-16 | 压缩阈值成本仿真（见“KV 缓存”一节） | 基准参数下最优阈值在 100k–160k 的平缓区；扫参后最优点在 60k–300k 之间移动 | 阈值要用自己的任务数据测，不照搬 |
| 2026-10-16 | 版本与发布节奏核查 | pi 1.3.0 前一天发布，近 30 天 15 版；Claude Code 最新 2.1.301，近 30 天 26 版 | 评测前锁版本 |
| 2026-10-16 | 环境诊断（第一个探针） | WSL 2 CPU / 0.9 GB；Docker 可连；Claude Code 2.1.128 未登录；pi 经 magpie 用 deepseek-v4.1-flash | 先修环境、定模型 |
| 2026-10-17 | 本地模拟服务器 + pi 1.3.0 真实会话；探针脚本自测 | 4 轮请求，前缀逐轮严格追加（仿真缓存命中 1472 / 1600 / 1664 token）；系统提示里没有日期等动态内容；pi -p 在 stdin 不是终端时会一直等输入；探针对假密钥、坏文件、缓存断崖归因的自测全过，独立审查被额度打断，没做完 | 评测脚本里 pi -p 一律加 < /dev/null；缓存回归测试可以直接用这个模拟服务器做；探针可以交给你运行 |
| 2026-10-17 | 你运行第二个探针；我分析输出 | magpie 回传缓存字段（探针三次相同前缀请求命中 6784 / 6944 token）；真实会话稳态命中 93–97%；装着 pi-web 时首个请求的前缀 4.9k token，空白时 1.6k；WSL 已是 7.8 GB 内存；Docker 的 WSL 集成关闭；WSL 里的 Claude Code 仍是 2.1.128 | 缓存护城河目前完好；pi-web 已卸载；下一步让 Claude Code 就位，再搭评测 v0 |
| 2026-10-17 | 模拟服务器实测：会话中途加载工具（tool\_search 与扩展里的 setActiveTools 各一次） | 两种方式结果相同：请求里 tools 数组多出一项（排在最后），消息不变；该请求仿真命中率 48%（前几个工具的定义仍命中，其后的系统提示与历史全部失效），下一个请求回到 96%。会话文件里记为一条 system 消息。仿真按 tools、system、messages 的顺序算前缀 | 工具集变化 = 一次整段重计费，代价随上下文变大；能力档案要在会话开始前定好；探针把这类断崖归因为 system。真实网关上的行为待评测里用命中率验证 |
| 2026-10-18–19 | 用模拟服务器看 Claude Code 与 pi 1.3.0 发出的原始请求（评测台开发中） | Claude Code 默认带 adaptive thinking + effort high，pi 默认 medium（day1 实测线上发出的是 high），且 pi 只有在模型条目写了 reasoning: true 时才发 reasoning\_effort；Claude Code 默认 19–21 个工具、首个请求约 17.5k token，只留 Bash/Read/Edit/Write 约 3.7k，pi 约 1.5k；设 CLAUDE\_CODE\_DISABLE\_NONESSENTIAL\_TRAFFIC 会悄悄去掉一个工具并少约 2.3k token；Claude Code 报的 thinking\_tokens 恒为 0；逐次用量要加 --include-partial-messages 才拿得到 | “同强度”要用 calib 实测配对，不能只看旗标；对比分“默认工具集”与“对齐工具集”两轮；评测里不设 NONESSENTIAL\_TRAFFIC；比较推理量看输出 token |
| 2026-10-19 | 你在 WSL 里让 Claude Code 2.1.302 经 magpie 的 /v1/messages 连问“Reply with exactly: PONG” | 通；Anthropic 协议的用量是“可加”的：input\_tokens 只计未命中部分（210 + 缓存 18,048 = 18,258；冷请求 input 18,258、缓存 0）；裸请求 18,258 token，pi 同条件约 1.5k；缓存粒度当时估为 64 token（day1 的 cacheprobe 改量为 128，见 10-21 行）；相同请求隔几秒出现过一次整段未命中（cache\_read 0） | 评测台按“可加”读 Claude Code 的用量（smoke 自动判定）；网关缓存并非每次都命中，缓存类指标要看多次的中位数，波动用 cacheprobe 量化 |
| 2026-10-20 | 评测台 arena v0 完成度盘点 | 已有：隔离运行器、隐藏测试判卷、两个 agent 事件流归一化、报告（噪声、暂定胜平负）、smoke、calib、cacheprobe、pi 变体叠加（--pi-config）、day1 一条命令跑完并打包结果；两道试点题均“未解必败、参考解必过”；真实的 pi 1.3.0 与 Claude Code 2.1.304 对模拟网关自测，239 项检查全过（Python 3.12 与 3.11），另做过含 Ctrl-C 中断续跑的整条用户流程演练 | arena-v0.tar.gz 已交付；等你在 WSL 里跑 day1 拿第一批真实数据 |
| 2026-10-20 | 用真实的 Claude Code 2.1.304 与 pi 1.3.0 对模拟网关连续运行同一道题，逐字节比较相邻两次的第一个请求 | Claude Code 会把自己的记忆目录路径写进系统提示、把最近的 git 提交 hash 写进第一条消息；评测台原先每次运行用不同的临时目录，基线提交的 hash 又随时间变，所以第二次运行的第一个请求只命中工具定义那一段（7552 / 10813 token）。改成每个 agent 的目录路径固定（内容每次清空）、基线提交日期固定后，相邻两次的第一个请求逐字节相同，只差最后一个不满 64 token 的块（pi 1472 / 1527，Claude Code 11008 / 11009）；较新的 Claude Code（2.1.304）还会多发一个占位工具 DeferredToolPlaceholder，--tools 去不掉 | 评测台自己不能往提示词里带每次都变的东西（路径、时间、hash），否则缓存指标量到的是评测台；自测已加这条回归检查，并加了“同一时间只允许一个 arena 命令”的锁。你的 2.1.302 是否也带记忆路径还不知道，新方案对两种情况都成立；第一批数据里看 smoke 的 tools\_exposed 与首个请求的命中 |
| 2026-10-21 | 你在 WSL 里跑完 day1 的前三步：smoke（各 3 次 PONG）、cacheprobe、calib | smoke：Claude Code 的用量按“可加”读（第二个请求 input 210 + 缓存 17,536），暴露 19 个工具、首个请求 17,746 token；pi 暴露 4 个工具，首个请求 1,606 token，之后 198 + 缓存 1,408。cacheprobe（104 个请求，openai 与 anthropic 两种协议各 52 个，间隔 1–160 秒，零报错）：相同请求命中 97.8%，追加式增长命中 95–97%，没有整段未命中；命中量全是 128 的整数倍，每个请求总有 140–350 token 不命中。calib（每档 3 次）：pi 的 off、low、medium、high、xhigh 在线上对应 low、low、high、high、max，默认 medium 实际发出 high；输出 token 中位数 pi 1.5k–2.7k、Claude Code 2.1k–4.5k，档位间的差距小于同档 3 次的波动，只有 Claude Code 的 xhigh 明显更多 | magpie 的用量是可加的，评测台已自动按此读；网关缓存稳，按 128 粒度算，仍保留缓存断崖标记；两边先用默认档对默认档，不再逐档配对；Claude Code 的 effort 在网关那头变成什么还不知道 |
| 2026-10-21 | day1 的 pilot：p01（修 bug）、p02（加功能），pi 与 Claude Code 各 5 次，共 20 次 | 通过 18/20：Claude Code 与 pi 各挂一次 p02，原因相同，都是表格分隔行最后一列的宽度（题面里的一条隐含规则）。单次成本 pi $0.0016–0.0104、Claude Code $0.0023–0.0082；中位数 p01 0.00197 对 0.00284、p02 0.00519 对 0.00625（pi 低 31% / 17%）。输出 token 占成本六成多（pi 69%、Claude Code 62%），未命中的输入占 23–28%，缓存读取只占 2%（pi）与 13%（Claude Code）。冷启动：每个（题，agent）的第一次运行首个请求几乎没命中，Claude Code 多付约 1.74–1.79 万未命中 token（约 $0.0026），pi 约 1.1–1.6k，其余运行只有 230–250；首个请求之后每个请求的未命中量中位数 Claude Code 约 530、pi 约 780（本轮新增的工具结果和回复）。命中率 Claude Code 97%、pi 82%，成本却是 pi 更低。单次波动（变异系数，4 组各 5 次）：成本 30%（最大 44%）、输出 token 28%、总输入 24%、LLM 调用数与耗时 19%、首个请求大小 0% | 命中率偏向大前缀，不能拿来比两边，头条指标改为“未命中缓存的输入 token”（首个请求与其余分开记），命中率降为诊断；冷启动是一次性的，同题的几次要连着跑、取中位数；pi 的成本优势（17–31%）小于单次波动（约 30%），2 题 × 5 次分不出谁更省；12 题 × 3 次大约能分出 12–15% 的系统差距（只跑开发集 8 题约 15–18%），更小的要再多 4 倍的次数；失败原因要写进报告（验证器备注） |
| 2026-10-22–23 | 做 12 题套件（新增 p03–p12）与 suite 命令（v0.1），全部在模拟网关上自测 | 12 题：开发集 p01–p07、p11，留出集 p08、p09、p10、p12；Python 7 题、Node 4 题、bash 1 题；类型含重构、调试、性能、构建、写测试（变异检验）、从零写、安全修复、只读问答、四层功能。每题都验证“未解必败、参考解必过”，并用故意写错的解检验隐藏验证器；验证器能输出备注（例如“答案对 4/5”），报告新增“失败原因”一节；同一题的几次运行连着跑，每题只有一次冷启动。suite 默认只跑 8 道开发题，留出的 4 题要显式加 --tasks held。自测 283 项全过；整条用户流程演练（含 suite、Ctrl-C 续跑，以及 v0 装着 day1 数据时解压 v0.1 覆盖再跑 suite）0 失败 | 题目难度还没校准，只有你跑完 suite 才知道哪些题太易或太难；下一步在 WSL 里跑 suite，拿到数据后校准难度、重估噪声，再开始逐项改 pi，一次只改一项 |
