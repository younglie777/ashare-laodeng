# 老登价值选股 v2.0.0 发布说明

发布日期：2026-08-05

## 版本定位

从 v1.0.3（2026-07-31）至今，本技能经历了**一次根因级修复 + Wind 数据通路打通 + 大规模口径调整**，改动面远超常规小版本，故直接跳到 v2.0.0。

## 本次主要变动

### 1. 修复 Graham 分红条根因 bug（最重要）
- **问题**：westock 1.0.4 的 `dividend list` 接口残——只回当年分红，拿不到 Graham 第 4 条要求的「10 年中 ≥6 年分红（近 3 年 ≥2 年）」完整历史，导致旧流程筛不出完整入选名单。
- **修复**：改为「两遍筛选 + Wind MCP 分红史」标准流程：
  1. pass1 用 `graham_westock.py --skip-dividend` 跳过分红条、缩窄候选；
  2. 对幸存者用 Wind MCP `get_stock_events` 拉 10 年每股派息（写 `wind_dividends.json`）；
  3. `build_div.py` 转成 graham 兼容的 `div.txt`；
  4. pass2 带分红条复筛得最终入选。
- **实测**：全市场 1456 候选 → 26 幸存 → **24 只最终入选**（如长江传媒、国药股份、北新建材等），结果可复现。

### 2. Wind 估值通路打通
- 新增 `scripts/write_wind_cache.py`（批量写 wind_cache，避免手敲 JSON 出错）。
- 用 `get_stock_price_indicators` 批量拉 PE-TTM / PB / 股息率 / 52 周高低 / 总股本，报告数据源 `data_source=wind+public`（Wind 权威值优先，公开接口兜底）。
- SKILL.md 修正工具名：行情预拉取由 `get_stock_quote`（分钟级行情）改为 `get_stock_price_indicators`。

### 3. 新增脚本与能力
- `scripts/_selftest_gw.py`：16 个边界用例回归自测（覆盖每条件阈值），改筛选逻辑必跑。
- `scripts/build_div.py`：Wind 股息 → graham 兼容 div.txt。
- `scripts/gen_summary_table.py`：速览表（含「靠手段才过」警示列），并加防呆拒绝覆盖输入文件。

### 4. 「靠手段才过」标注
放宽/平滑口径才达 Graham 标准的标的（如当前 TTM PE 亏损但靠 3 年均值过线、或 EPS 增长靠低基数），在表格 + 报告里显著标注，需额外警惕。

### 5. 选股口径调整（用户偏好）
- 规模闸门：市值 ≥50 亿 / 营收 ≥20 亿（v1.0.1 曾放宽到 150/60，本次收回 Graham 原教旨）。
- 分红率门槛：近 3 年平均分红率 ≥10%（由 30% 下调）。

### 6. 四大师解读不再空白
`gen_report.py` 优先读运行目录 `four_masters.json`；缺解读时渲染可见的「⚠️ 四大师解读待补充」黄框，杜绝静默空白。

## 升级方式

下载本 release 的 `laodeng-stock-advisor.zip` 解压即用，无需重装依赖。
运行完整两遍筛选需 Wind MCP（可选手动拉分红）或已有的 `wind_dividends.json`；纯公开接口模式仍可跑（分红条可能筛不出完整入选，建议按 SKILL.md 走 Wind）。

## 与历史版本关系

- v2.0.0：分红根因修复 + Wind 估值通路 + 口径调整（本次）。
- v1.0.3：产地信息统一以中性字段呈现。
- v1.0.2：时间窗口恢复为 10 年。
- v1.0.1：规模闸门放宽（后于 v2.0.0 收回）。
- v1.0.0：初版。
