---
name: 老登股推荐
description: '把 Graham 防御型选股筛出的股票，套用 ai-berkshire 四大师（巴菲特/芒格/段永平/李录）框架做「分析总结」：生意本质、护城河、逆向风险、管理层、文明趋势、估值安全边际 + 红线否决 + 价格区间 + 综合建议，产出结构化投研报告。触发词：分析总结、股票分析、投研报告、四大师分析、Berkshire 分析、把入选股分析一下、筛选后分析、老登股。'
---

# 老登股推荐 · Graham 入选股「分析总结」

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
对每只入选股，调用：
  mcp__wind-stock__get_stock_fundamentals → "X（CODE.SH）2025-12-31的PE-TTM、PB、ROE、股息率"
  （实时价/52周高低由公开接口补充，无需 Wind）
写入 wind_cache/<code6>.json，归一化字段：
  { "code","name","price":null,"pe","pb","div_yield","roe","source":"wind" }
  # price 留 null → 脚本自动用公开接口实时价补齐
```
> 实测 Wind 与公开接口的 PE/PB 常有差异（如长春高新：Wind PE 39.4 vs 腾讯 -752 vs 归一化扣非 12.3），报告应双源并列、注明口径，不让单一源误导。

### 产地标注（省·市，中性、不参与筛选）

- `analyze_selected.py` 对每只入选股按注册地（westock `profile.regAddress`）解析出 **省·市**，仅作为客观产地信息写入报告，**不参与任何筛选、打分、偏好或剔除**。
- 解析逻辑在 `tools/location.py` 的 `parse_location(addr)`，只是一个省·市解析器。本技能对所有入选股一视同仁。

工具依赖（已随技能附带，Windows-GitBash 适配）：
- `tools/ashare_data.py`（腾讯行情+东方财富，零依赖；已修 curl 路径）— 公开接口兜底源
- `tools/financial_rigor.py`（精确十进制估值验算/三情景，stdlib）
- `tools/location.py`（注册地省·市解析，仅标注用，stdlib）
- **Wind MCP**（环境连接器 `mcp__wind-stock` 等）— 优先数据源，断连时自动回退

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
