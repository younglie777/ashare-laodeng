# 老登股推荐（Graham 防御型 → 四大师分析）

把 **Graham 防御型选股** 筛出的"又便宜又稳"的股票，套用 **ai-berkshire 四大师框架**（巴菲特 / 芒格 / 段永平 / 李录）做深度分析总结，自动产出带产地（省·市）中性标注、三情景估值的 HTML 投研报告。

> "老登股" = 低估值、高分红、经营稳健的成熟公司。Graham 防御型七条件筛出来的就是这一类。

---

## 〇、小白用户怎么用（先看这个）

**不会写代码也完全能用。** 这套东西的设计目标，就是让你**只用大白话跟 AI 聊**，就能拿到一份完整的投研报告。

### 最简路径（推荐）

1. **装好本仓库（单仓即可）**：
   - 直接克隆本仓库：`git clone https://github.com/younglie777/ashare-laodeng.git`
   - **Graham 筛选器（`graham_westock.py` + `region_filter.py`）已内置打包在 `scripts/` 下**，无需再单独克隆 `ashare-graham-screener`，克隆这一个仓库就能跑全流程。
   - 但本仓库依赖 WorkBuddy 内置的 `westock-data` / `westock-tool` 来拉数据（见下方「前置环境准备」），请先确认它们已启用、且本机装了 Node.js 与 Python 3。
2. **直接跟 AI 说一句话**，例如：
   > "帮我用老登股推荐，跑一份今天的防御型选股四大师分析报告"
3. AI 会自动完成「筛选 → 分析 → 出 HTML 报告」三步，你**什么都不用配**。
4. 报告生成后，打开 `Graham入选股_四大师分析_<日期>.html` 就能看。

### 常见疑问

- **不会命令行？** 没关系，上面这种"对话式"用法不需要你敲任何命令。
- **没有 Wind MCP？** 完全没影响。默认自动回退公开接口（腾讯行情 + 东方财富），零配置、照常出报告。
- **只想分析别人给的选股结果？** 如果手头已经有一个 `A股防御型选股_*.md` 文件，跑一条命令即可（见第四节、第八节）：
  ```bash
  python scripts/run_pipeline.py analyze 你的选股.md ./out --source public
  ```
- **只做分析、不想跑筛选？** 如果你手头已有一份 `A股防御型选股_*.md`，直接 `python scripts/run_pipeline.py analyze 你的选股.md ./out --source public` 即可（跳过筛选步骤）。需要全自动时，本仓库已内置筛选器，跑 `all` 就行。

> 一句话总结：**克隆本仓库（筛选器已内置）→ 启用 westock 内置技能 + 装好 Node/Python → 跟 AI 说一句话 → 拿 HTML 报告**。就这么简单。

---

## 前置环境准备（安装前必读 · Checklist）

本技能现在**单仓即可跑通全流程**（Graham 筛选器 `graham_westock.py` + `region_filter.py` 已打包进 `scripts/`，不再强依赖外部仓库 `ashare-graham-screener`）。但要顺利出报告，请逐项确认以下前置：

- [ ] **1. 克隆本仓库**：`git clone https://github.com/younglie777/ashare-laodeng.git`（仓库内已含筛选器，无需再克隆 ashare-graham-screener）。
- [ ] **2. 启用 WorkBuddy 内置技能 `westock-data` 与 `westock-tool`**（仅 `fetch` / `all` 全自动模式需要）：这两个是 WorkBuddy 内置技能，默认可能**未启用**，请在技能面板搜索并启用。没启用 → `all`/`fetch` 会报"未找到 westock"。只做 `analyze`（分析已有 md）则不需要。
- [ ] **3. 安装 Node.js 18+**（westock 基于 Node，仅 `fetch`/`all` 需要）：装完终端 `node -v` 能出版本即可。
- [ ] **4. 安装 Python 3.10+**（本技能脚本基于 Python 标准库）：终端 `python3 --version` / Windows `python --version` 能出 3.10+ 即可。
- [ ] **5. Wind MCP（可选）**：没装 → 脚本自动回退公开接口（腾讯行情 + 东方财富），零配置照常出报告（详见第五节）。

> ✅ **最简验收**：克隆仓库 + 启用两个 westock 内置技能 + 装好 Node/Python 后，跑 `python scripts/run_pipeline.py all --win 10 --mv 150 --rev 60 --out ./out --source public` 一路跑通，即说明前置齐了。

> 🤖 **自动自检**：本技能的 `run_pipeline.py` 在每次运行时（尤其是 `fetch` / `screen` / `all`）会**先自动检测上述前置**。若缺失，会在开头直接打印「缺了什么 + 怎么装」，补齐后重新运行同一条命令即可继续——无需手动排查。

---

## 一、这套东西怎么串起来的

```
① 筛选  (ashare-graham-screener)  →  A股防御型选股_YYYYMMDD_w<WIN><SUF>.md（入选✓）
        ↓
② 分析  (本技能 analyze_selected.py)  →  analysis_cards.json + analysis_draft.md
        ↓   Wind MCP 优先 / 公开接口兜底 / 产地省·市标注
③ 报告  (本技能 gen_report.py)  →  Graham入选股_四大师分析_<日期>.html
```

- **① 筛选** 用 Graham 七条件精算，**筛选器 `graham_westock.py` 已内置打包在本仓库 `scripts/` 下**（无需再装 `ashare-graham-screener`）。
- **② ③ 分析与报告** 由本技能完成。
- 一键脚本 `scripts/run_pipeline.py` 把三步串起来（详见第四节）。

---

## 二、目录结构

```
老登股推荐/
├── SKILL.md                  # 技能说明（四大师分析协议、红线、数据源策略）
├── README.md                 # 本文件
├── LICENSE                   # MIT（注明第三方组件来源）
├── scripts/
│   ├── run_pipeline.py       # ★ 一键流水线（fetch/screen/analyze/report/all）
│   ├── graham_westock.py     # ★ 已内置打包的 Graham 七条件筛选器（无需另装仓库）
│   ├── region_filter.py      # graham_westock.py 依赖（地域闸门，发布版默认不筛选）
│   ├── analyze_selected.py   # ② 数据卡：读 md 入选股 → 实时行情/52周 + 三情景估值 + 产地省·市标注
│   └── gen_report.py         # ③ 报告：读 analysis_cards.json → HTML
├── tools/
│   ├── ashare_data.py        # 腾讯行情 + 东方财富（公开接口，零依赖；Windows-GitBash 已适配）
│   ├── financial_rigor.py    # 精确十进制三情景估值验算（stdlib）
│   └── location.py           # 公司注册地省·市解析（仅标注用）
└── wind_cache/               # 可选：Wind 预取样例（8 只）。没有 Wind MCP 可删除，不影响功能
```

> `tools/ashare_data.py` 与 `tools/financial_rigor.py` 源自 [ai-berkshire](https://github.com/xbtlin/ai-berkshire)（MIT），本技能复用其 A 股支持。

---

## 三、依赖

| 阶段 | 需要什么 | 说明 |
|------|----------|------|
| 分析 + 报告（② ③） | Python 3 + 本技能 `tools/`（自带） | **零外部依赖**，开箱即用 |
| 筛选 fetch/screen（① 自动建池+抓数） | WorkBuddy 内置 `westock-data` / `westock-tool`（Node）+ Python 3 | 仅 `fetch` / `all` 需要；**Graham 筛选器已内置打包，无需另装仓库** |
| Wind MCP | **可选** | 见第四节，没有也 100% 可用 |

---

## 四、一键运行（run_pipeline.py）

脚本位置：`老登股推荐/scripts/run_pipeline.py`。用 Python 3 运行。

### 场景 A：我**没有 Wind MCP**（最常见，也是默认值）✅

你什么都不用装、不用配。直接分析已有的选股结果：

```bash
# 分析某个 Graham 选股 md，只用公开接口（腾讯/东财）
python run_pipeline.py analyze /path/to/A股防御型选股_20260722_w10_150w10.md \
       --out ./out --source public
```

- `--source public`：强制只用公开接口（腾讯行情 + 东方财富 52 周）。
- 省略 `--source` 时默认 `auto`：有 `wind_cache/*.json` 就用 Wind，否则自动回退公开接口——**即使忘了加参数也不会卡**。
- 不传 md 时，会自动在「当前目录 / 技能 data」里找最新的 `A股防御型选股_*.md`。

### 场景 B：我有 westock（WorkBuddy 内置），想全自动从选股到报告

```bash
# 全自动：建池 + 抓数 + 筛选 + 分析 + 报告（Wind 仍可选，默认 auto 回退）
python run_pipeline.py all --win 10 --mv 150 --rev 60 --out ./out
```

- `--win 10` 上市≥10 年（改 `5` 放宽到≥5 年）；`--mv 150` 市值≥150 亿；`--rev 60` 营收≥60 亿（中盘口径）。
- `all` 内部自动跑 `fetch`（建中盘池+抓 raw）→ `screen` → `analyze` → `report`。
- `fetch` 会向腾讯接口请求约 1600+ 只股票的多项数据，**首次可能要几分钟**，属正常。

### 场景 C：只跑某一步

```bash
python run_pipeline.py fetch  --rev 60 --out ./out     # 只建池+抓 raw
python run_pipeline.py screen --win 10 --mv 150 --rev 60 --out ./out   # 只筛选
python run_pipeline.py analyze --out ./out --source auto               # 只分析+报告
```

---

## 五、⚠️ 没有 Wind MCP 怎么办（重点说明）

**结论：完全没有影响，零配置，照常用。**

本技能的数据源优先级是：

1. **Wind MCP（可选，优先）**：由带 Wind 连接器的 AI 预先把财务/估值拉进 `wind_cache/<code>.json`。
2. **公开接口（兜底，必有用）**：腾讯行情（实时价/PE/PB）+ 东方财富（52 周高低），走 `tools/ashare_data.py`，**纯标准库、零依赖、不依赖任何连接器**。

因此：

- 没有 Wind MCP → 脚本自动只用公开接口，**结果照常产出**，只是财务精度以公开源为准（报告里用"归一化扣非 PE"作估值基准，避免单一源误导）。
- `wind_cache/` 目录是**可选的 Wind 预取样例（8 只）**。你克隆下来后：
  - 留着：对你这 8 只直接用里面的 Wind 数值；
  - **删掉也行**：脚本会自动改用公开接口，功能不受影响。
- 筛选阶段（`fetch`/`screen`）只用 westock 公开接口，**跟 Wind 毫无关系**。

> 一句话：对方没装 Wind MCP，你只要 `python run_pipeline.py analyze 你的md --source public` 即可，啥都不用管。

---

## 六、报告与免责声明

报告含：横向对比总表（含**产地省·市**标注）、逐只六模块（段/巴/芒/李）、红线否决、三情景价格区间、组合行动清单。

> ⚠️ 本报告为 **AI 框架化推理 + 机械估值模型输出，非投资建议**。定性部分（护城河/管理层/文明趋势）非一手调研；三情景目标价为估值模型结果，非收益预测。投资有风险，决策需独立判断。

---

## 七、开源与致谢

- 本技能采用 **MIT 协议**（见 `LICENSE`）。
- 核心分析框架与方法论来自 [ai-berkshire](https://github.com/xbtlin/ai-berkshire)（xbtlin，MIT）：巴菲特护城河 + 芒格逆向 + 段永平生意本质 + 李录文明趋势。
- `tools/ashare_data.py`、`tools/financial_rigor.py` 为 ai-berkshire 原生工具，本技能仅做 Windows-GitBash 适配（curl 路径）与接入。

如用于二次分发，请保留上述来源署名。

---

## 八、在其他 AI Agent 中使用

本技能可以在任何支持 Python 3 的 AI Agent 环境中运行，不依赖 WorkBuddy 平台。

### 前提条件

1. **Python 3.8+**（脚本仅用标准库，无需 openpyxl）
2. **Node.js**（仅 `fetch` / `all` 全自动模式需要，用于调用 westock）
3. 已有 **Graham 选股结果 Markdown**（由本仓库内置的 Graham 筛选器自动产出，或手动准备；跑 `all` 会自动生成）

### 最简用法（分析已有 Markdown → 出报告）

```bash
# 1. 克隆本仓库
git clone https://github.com/younglie777/ashare-laodeng.git
cd ashare-laodeng

# 2. 无需外部依赖（标准库即可，已不再依赖 openpyxl）

# 3. 把你的 Graham 选股 md 放进来，运行分析+出报告
python scripts/run_pipeline.py analyze 你的选股.md ./out --source public

# 4. 报告在 ./out/Graham入选股_四大师分析_YYYYMMDD.html
```

### 在 Agent 工作流中集成

如果你在开发自己的 AI Agent，可以把本技能作为**后处理模块**嵌入：

```
你的 Agent 主流程
  │
  ├─ 选股模块（任意方式，产出 md 即可）
  │     └─ 要求：md 含「选股结果」表格，含「是否入选」列（✓/True）
  │
  ├─ 【接入点】调用本技能
  │     └─ python scripts/analyze_selected.py <md> <输出目录> --source public
  │     └─ python scripts/gen_report.py   （在输出目录中执行）
  │
  └─ 拿到 HTML 报告 → 展示给用户 / 进一步分析
```

关键约定：
- `analyze_selected.py` 读 md 的「选股结果」表格，取「是否入选」= ✓ 的行。
- 输出 `analysis_cards.json`（结构化数据）+ `analysis_draft.md`（草稿）。
- `gen_report.py` 读 `analysis_cards.json` → 输出日期命名的 HTML 报告。
- 所有路径均为相对路径，Agent 只需 `cwd` 设到输出目录即可。

### 不用 WorkBuddy 也行吗？

**完全可以。** 本技能的核心（`analyze_selected.py` + `gen_report.py` + `tools/`）是纯 Python，零平台依赖：

| 组件 | 是否需要 WorkBuddy |
|------|-------------------|
| `analyze_selected.py` | ❌ 不需要 |
| `gen_report.py` | ❌ 不需要 |
| `tools/ashare_data.py` | ❌ 不需要（公开接口直连） |
| `tools/financial_rigor.py` | ❌ 不需要（纯 stdlib） |
| `tools/location.py` | ❌ 不需要（纯 stdlib） |
| `run_pipeline.py fetch/screen` | ✅ 需要 westock（WorkBuddy 内置或自行安装） |

所以：**分析 + 报告**在任何环境都能跑；**筛选**才需要 westock。
