---
name: 老登股推荐
description: '把 Graham 防御型选股筛出的股票，套用 ai-berkshire 四大师（巴菲特/芒格/段永平/李录）框架做「分析总结」：生意本质、护城河、逆向风险、管理层、文明趋势、估值安全边际 + 红线否决 + 价格区间 + 综合建议，产出结构化投研报告。触发词：分析总结、股票分析、投研报告、四大师分析、Berkshire 分析、把入选股分析一下、筛选后分析、老登股。'
---

# 老登股推荐 · Graham 入选股「分析总结」

## 实时信息检索（强制，先于任何财报结论）

> **痛点**：四大师分析若只基于 Graham 筛选出的历史财务数据，会漏掉「正在变坏」的信号——业绩指引下调、解禁/配售/减持、监管调查、竞品突变，这些**先在公开舆论与新闻里显现**，财报滞后半年。财务指标好看的「价值陷阱」往往就是这么来的。

**对每只入选股做四大师分析前，必须先联网检索实时信息**，至少覆盖四类来源：

1. **雪球（Xueqiu）舆情（重点）→ 调用 `xueqiu-comments` skill**：抓取个股讨论、大 V 观点、散户多空分歧、估值争议、解禁/配售/减持等事件情绪。
   - **首选：调用 `xueqiu-comments` skill**——传入股票代码/名称（如 `智谱`、`06651.HK`、`五一视界`），它会用 WebSearch 并行检索雪球公开评论，输出「多空观点对比表 + 综合情绪 + 争议点」。这是本框架做雪球舆情的标准动作。
   - 备选/补充：`ai-berkshire` 仓库有 `tools/xueqiu_scraper.py` 时（仓库根目录执行）：`python3 tools/xueqiu_scraper.py --keywords {公司名},{股票代码} --output /tmp/xq-{公司名}.md`；无工具时用 WebSearch 检索「雪球 {公司名} {代码}」「{公司名} 股吧 讨论」「{公司名} 目标价 估值 贵/便宜」等。
2. **财经新闻与官方公告**：WebSearch 检索近 3–6 个月的公司新闻、业绩指引、官方公告（港交所/SEC/巨潮）、监管披露。
3. **卖方/机构观点**：摩根、高盛、中金、SimplyWallSt 等评级/目标价变动；对比「机构目标价」与「散户情绪」的分歧。
4. **行业与竞品动态**：技术路线变化、政策、对手进展（AI 赛道尤其重要）。

**信息等级与用法**（遵循 AGENTS.md 交叉验证原则）：
- **A 级（可进结论）**：官方公告、财报、机构研报、可核实的新闻。财报与新闻冲突时，**以更近的时点为准**。
- **B 级（仅作反向验证/情绪参考，不进结论）**：雪球/股吧散户观点、自媒体、未证实传言。须标注来源与情绪倾向，**不得作为估值或买卖依据**。

**硬约束**：
- 对 AI / 半导体 / 机器人 / 创新药 / 高成长未盈利 等高频变化行业，实时检索**不是可选项，是必选项**。
- 若因无网络/无权限未能检索就下结论，必须在报告显式标注：
  > ⚠️ 本报告仅基于静态财报/历史资料，未做雪球与实时新闻交叉验证，对高频变化赛道的可靠性下降。



把 **Graham 防御型选股**（本技能已内置 `scripts/graham_westock.py`，亦可独立用 `ashare-graham-screener`）筛出的防御型股票，按 **ai-berkshire** 的四大师框架做深度分析总结。
筛选负责「又便宜又稳」，本技能负责「为什么值得 / 值多少 / 风险在哪」。

> 方法论源自 ai-berkshire（xbtlin/ai-berkshire，MIT）：巴菲特护城河 + 芒格逆向 + 段永平生意本质/对的人 + 李录文明趋势，四视角对抗、红线否决、精确估值。

## 流水线

```
① 筛选  (本技能内置 graham_westock.py，亦可独立用 ashare-graham-screener)  → A股防御型选股_YYYYMMDD_w<WIN><SUF>.md（入选✓）
        ↓
② 数据卡 scripts/analyze_selected.py <选股MD> [out_dir] [--source auto|wind|public]
        → analysis_cards.json + analysis_draft.md
          (Graham指标[来自筛选Markdown] + **Wind MCP 优先**财务/估值[pe/pb/分红率/ROE]
           + 公开接口[腾讯行情+东财52周]兜底 + financial_rigor三情景估值 + 红线速查
           + **产地(省·市)中性标注**[tools/location.py，仅标注、不参与筛选])
        - --source auto（默认）：Wind 优先；wind_cache 缺失则整体回退公开接口
        - --source wind：强制 Wind；--source public：强制公开接口
        ↓
③ 叙事  AI 读取数据卡 → 按下方「四大师分析协议」写每只的分析 + 组合总结 → 报告(.md/.html)
```

## 运行

> 🤖 运行 `run_pipeline.py` 的 `fetch` / `screen` / `all` 时会**先自动自检前置**（Node.js + westock 数据组件）。缺失会打印安装指引并在末尾输出 `>>> PREFLEFT: fail`（WorkBuddy 走面板启用；其他 Agent 走 npm 安装或设 `WESTOCK_DATA`/`WESTOCK_TOOL` 环境变量），补齐后重跑同一条命令即可继续。

```bash
# ② 生成数据卡（自动取最新 *_w*_*.md，或显式传路径）
python3 scripts/analyze_selected.py                                          # 默认 --source auto（Wind优先/公开兜底）
python3 scripts/analyze_selected.py path/to/A股防御型选股_20260722_w10_150w10.md . --source auto
python3 scripts/analyze_selected.py path/to/xxx.md . --source wind         # 强制 Wind（需 wind_cache 已就绪）
python3 scripts/analyze_selected.py path/to/xxx.md . --source public       # 强制公开接口（腾讯+东财）

# ③ 拿到 analysis_cards.json 后，由 AI 按「四大师分析协议」撰写报告
```

### 数据源优先级：Wind 优先 / 公开接口兜底（不强制）

- **默认 `--source auto`**：脚本先读 `wind_cache/<code6>.json`（由 AI 通过 Wind MCP 预拉取）；命中则用 Wind 的权威 pe/pb/分红率/ROE，实时价与 52 周高低由公开接口（腾讯行情+东方财富）补充；**wind_cache 缺失则整体回退公开接口**——Wind 断连/报错也不阻塞。
- **`--source wind`**：强制只走 Wind，缓存缺失则该股标注 `wind-missing` 跳过。
- **`--source public`**：强制走 `tools/ashare_data.py`（腾讯+东财），完全不用 Wind。

### Wind MCP 预拉取（填充 wind_cache，由 AI 执行）

Wind MCP 工具只能由 AI 调用（子进程脚本无法直接调），所以「Wind 优先」靠 AI 先把数据落下：

```text
对每只入选股，调用 Wind MCP 的「个股基本面」工具（集合里实际名字是 mcp__wind-finance__get_stock_fundamentals，
注意不是 mcp__wind-stock__，旧文档写错过）：
  mcp__wind-finance__get_stock_fundamentals → "X（CODE.SH）2026-08-03 的 PE-TTM、PB、股息率、ROE"
  （实时价/52周高低由公开接口补充，无需 Wind）
写入 wind_cache/<code6>.json，归一化字段：
  { "code","name","price":null,"pe","pb","div_yield","roe","source":"wind" }
  # price 留 null → 脚本自动用公开接口实时价补齐
  # roe 为 null 是常态：Wind 通常不计算「当日」ROE，需指定历史报告期（如 "2025-12-31"）才返回，
  #   故脚本对 roe=null 不回退、不报错，报告里 ROE 列留空即可
```
> ⚠️ **务必用脚本写缓存，别手敲 JSON**。手敲极易出错：漏 `source` 字段、roe 写成字符串、`price` 误填、文件名前缀没剥（应是 `600511.json` 而非 `sh600511.json`）。统一用 `scripts/write_wind_cache.py`：
> ```bash
> python scripts/write_wind_cache.py --code sh600511 --name 国药股份 --pe 10.67 --pb 1.16 --div 2.81 --roe null
> # 或批量：python scripts/write_wind_cache.py --batch payload.json
> #   payload.json: [{"code":"sh600511","name":"国药股份","pe":10.67,"pb":1.16,"div":2.81,"roe":null}, ...]
> ```
> 实测 Wind 与公开接口的 PE/PB 常有差异（如长春高新：Wind PE 39.4 vs 腾讯 -752 vs 归一化扣非 12.3），报告应双源并列、注明口径，不让单一源误导。

### 产地标注（省·市，中性、不参与筛选）

- `analyze_selected.py` 对每只入选股按注册地（westock `profile.regAddress`）解析出 **省·市**，仅作为客观产地信息写入报告，**不参与任何筛选、打分、偏好或剔除**。
- 解析逻辑在 `tools/location.py` 的 `parse_location(addr)`，只是一个省·市解析器。本技能对所有入选股一视同仁。

工具依赖（已随技能附带，Windows-GitBash 适配）：
- `tools/ashare_data.py`（腾讯行情+东方财富，零依赖；已修 curl 路径）— 公开接口兜底源
- `tools/financial_rigor.py`（精确十进制估值验算/三情景，stdlib）
- `tools/location.py`（注册地省·市解析，仅标注用，stdlib）
- **Wind MCP**（环境连接器 `mcp__wind-finance` 系列，如 `mcp__wind-finance__get_stock_fundamentals`）— 优先数据源，断连时自动回退

## 环境坑与避坑（踩坑沉淀 · 必读）

> 这套流水线在 Windows + Git-Bash 上跑过，以下坑都实打实踩过。任何一步报错先回来这里对照。

### 坑 0 · wind_cache 是「AI 手动快照」，每次重跑前必须刷新

- `analyze_selected.py` **不会**自动调 Wind，它只读 `wind_cache/<code>.json`（由 AI 经 Wind MCP 预拉取后写入）。
- 旧缓存（比如昨天 7-22 的 PE）会和**今日实时价**混搭，直接污染 Graham 红线判定（PE×PB 闸门、PB≤1.5）。
- **规则**：每次重跑前，先对当前入选股用 Wind MCP 重新拉一遍、用 `write_wind_cache.py` 重写；不要复用历史 JSON。
- 脚本已加护栏：`analyze_selected.py` 一旦命中 wind_cache 会打印 `⚠️ 采用 wind_cache/...（请确保该缓存为本次最新拉取）`，看到就确认是不是今天的。

### 坑 1 · `python3` 是 Windows 应用商店的「假桩」，会静默退出

- Git-Bash 里裸 `python3` 经常指向 `WindowsApps\python.exe` 桩程序，运行后**退出码 9009/49、无任何输出**，极难排查。
- **解决**：用 hermes 自带的 venv python 绝对路径：
  `C:/Users/a2821/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`
  （也可 `where.exe python` 确认系统真身；用户终端 `python` 解析为 3.11.15，但助手 shell 里 managed 3.13 在前，保险起见直接用上面绝对路径）。
- 跑本技能脚本统一用：`PY="C:/Users/a2821/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" && $PY scripts/analyze_selected.py ...`

### 坑 2 · Git-Bash 把 `/c/Users/...` 路径改写成 `C:\c\Users\...`

- Git-Bash 默认对含 `/c/` 的路径做 MSYS 路径转换，会把 `/c/Users/a2821/...` 变成 `C:\c\Users\...`，脚本找不到文件。
- **解决（两条任选/叠加）**：
  1. 路径一律用**盘符冒号形式** `C:/Users/a2821/...`（不用 `/c/Users/...`）；
  2. 设环境变量 `MSYS_NO_PATHCONV=1` 关掉自动转换。
- 例：`MSYS_NO_PATHCONV=1 $PY scripts/gen_report.py`（工作目录用绝对 `C:/...` 路径）。

### 坑 3 · Chrome headless 渲染 PDF 必须用**绝对输出路径**，相对路径报「拒绝访问」

- `chrome --headless --print-to-pdf=report.pdf`（相对路径）在部分 Windows 环境下会失败报 `拒绝访问`，因为输出落点不明确。
- **解决**：`--print-to-pdf` 给**绝对路径**，并加 `--user-data-dir` 隔离配置、用 `--headless=new`：
  ```bash
  chrome --headless=new --no-sandbox --disable-gpu \
    --user-data-dir=C:/tmp/chrome_wind_profile \
    --no-pdf-header-footer --virtual-time-budget=15000 \
    --print-to-pdf="C:/Users/a2821/WorkBuddy/<run_dir>/wind_final.pdf" \
    "file:///C:/Users/a2821/WorkBuddy/<run_dir>/report.html"
  ```
- 输入 HTML 也用 `file:///` + 绝对路径，避免相对解析问题。

### 坑 4 · `gen_report.py` 输出文件名带日期且会变，下游别写死

- 旧版只写 `Graham入选股_四大师分析_YYYYMMDD.html`，并且标题里的「生成日」硬编码 `2026-07-22`、数据源写死「Wind 未连接，自动回退」——导致 finalize/PDF 步骤天天对不上文件名、且报告永远显示「Wind 未连接」。
- **已修复**：`gen_report.py` 现在
  1. 按 `analysis_cards.json` 里每只的 `data_source` 字段**动态生成**数据源文案（Wind 实时 / Wind+公开 / 公开接口），不再写死「Wind 未连接」；
  2. 同时写出带日期文件 **和** 稳定名 `report.html`。
- **规则**：下游（finalize / PDF 渲染）一律引用 `report.html`（稳定名），不要再去 glob 日期文件名。

### 坑 5 · 跨任务查历史/持仓论文：conversation_search 不可靠，改用本地 Grep

- 今日另一任务（AI Berkshire 持仓分析）踩到：用云端 `conversation_search` 检索「之前做过的某只股票分析/论文」多次都查不到；改用**本地 Grep 搜 `C:\Users\a2821\WorkBuddy`**（按股票代码/关键词）才找到历史报告。
- **规则**（本技能也想召回以前某只票的分析时同样适用）：
  1. 要找「以前做过的分析/论文/报告」，**直接本地 Grep `C:\Users\a2821\WorkBuddy`**（各工作区产出都在这）；
  2. **不要搜 `C:\Users\a2821` 整盘**——会超时；路径必须收窄到 `WorkBuddy` 子目录；
  3. `conversation_search` 仅作兜底，别当首选。

### 坑 6 · Wind/数据连接器是「会话级授权」，重启/删 WSL/关隔离会清掉

- 今日另一任务确认：westock / Wind / github 等连接器是**会话级授权**。删除 WSL（7-23）、关运行时隔离（7-25）、重启 → 授权态被清，连接器全 disconnected，并非配置坏。
- **对本技能含义**：
  1. 跑之前先确认 Wind 连接器是 **connected**；若显示 disconnected，要么让用户去连接器中心重启用，要么直接 `--source public` 走公开接口（脚本 `auto` 模式也会自动回退），**不要反复重试 MCP 调用**；
  2. 本技能的公开接口 `ashare_data.py` 不依赖任何连接器，断网/断连时最稳，可随时兜底。

## 四大师分析协议（写报告时逐只执行）

对每只入选股，按以下 6 模块写，每模块末尾给一句对应大师的「追问」：

1. **生意本质（段永平）**：一句话定义生意；收入结构；毛利率与同行对比；复购/锁定强度。
2. **护城河（巴菲特）**：五类（品牌定价权/转换成本/网络效应/规模效应/技术专利）逐条验证；宽窄趋势。
3. **逆向与风险（芒格）**：列出失败路径（路径/概率/影响）；空方核心论点；历史类比。
4. **管理层（段永平+巴菲特）**：关键决策复盘；资本配置；股东利益一致性（持股/减持）。
5. **文明趋势（李录）**：是否处范式转移；TAM 与天花板；产业链位置。
6. **估值与安全边际（巴菲特+段永平）**：用数据卡的三情景目标价（乐观/中性/悲观）；相对 52 周位置；当前价是否便宜。

**红线否决清单（触发任一条→结论至少「观望/回避」，并在报告显著标注）**：
- 财务造假嫌疑（Benford 异常 / 审计非标）
- 有息负债 > 净流动资产（偿债不安全）
- 连续多年扣非为负 / 盈利质量差
- 商誉/净资产 > 20% 且仍在并购扩张
- 大股东高比例质押 / 频繁减持
- 核心业务遭不可逆技术替代
- 估值处于 52 周 >90% 高位且故事透支

**综合决策表（每只必给）**：

| 维度 | 结论 | 信心度 |
|------|------|--------|
| 生意质量（段永平） | | |
| 护城河（巴菲特） | | |
| 管理层 | | |
| 最大风险（芒格） | | |
| 文明趋势（李录） | | |
| 估值安全边际 | | |

最终给：**空仓者建议 / 持仓者建议 / 卖出信号 / 加仓信号** + 具体价格区间（来自三情景）。

## 输出要求

1. 数据支撑，附来源（westock / 腾讯行情 / 东方财富）。
2. 用表格呈现关键数据；估值部分给具体价格区间（禁止心算，用 financial_rigor 输出）。
3. 报告开头写**信息丰富度评级（A/B/C）** + **AI 研究局限性声明**。
   - A级（大盘蓝筹，信息充裕）：重点做反面检验「聪明人为什么不买」。
   - C级（信息稀缺）：结论区分「有据推算」与「凭空填充」，列一手验证清单。
4. 报告结尾区分 **AI 分析置信度** 与 **投资确定性**。
5. 结论明确：买入 / 观望 / 回避，不回避给建议。
6. 组合层面给一份「入选股横向对比总表」（估值/分红/成长/护城河强弱/建议）。

## 免责声明

本技能仅做客观数据分析与框架化推理，不构成投资建议。数据来自公开接口（腾讯自选股/东方财富），可能延迟或有误差；定性判断为 AI 基于公开信息的推理，非一手调研。投资有风险，决策需谨慎、DYOR。
