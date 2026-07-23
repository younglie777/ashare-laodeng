# 老登股推荐（Graham 防御型 → 四大师分析）

把 Graham 防御型选股筛出的「又便宜又稳」的股票，套用四大师框架（巴菲特/芒格/段永平/李录）做分析总结，自动产出带产地标注、三情景估值的 HTML 投研报告。

## 原理
先用 Graham 七条件选出低估值、高分红、经营稳健的「老登股」，再用四大师框架判断它「为什么值得、值多少、风险在哪」。

## 前置（运行时会自检查，缺什么会提示）
- 本仓库（Graham 筛选器已内置，克隆这一个即可）
- 行情/财务数据：建议直接通过 **Wind MCP** 接入；或 WorkBuddy 用户启用内置 westock 技能；其他环境也可 `npm i -g westock-data westock-tool` 并设 `WESTOCK_DATA` / `WESTOCK_TOOL`
- Node.js 18+（仅全自动拉数据时需要）
- Python 3.10+（脚本基于标准库）
- Wind MCP 可选，不装自动用公开接口

## 怎么用
最简：克隆后跟 AI 说「用老登股推荐跑一份今天的防御型选股四大师报告」，AI 会自动跑完出 HTML。
或命令行：
```
python scripts/run_pipeline.py all --win 10 --mv 150 --rev 60 --out ./out --source public
```
只分析已有选股：`python scripts/run_pipeline.py analyze 你的选股.md ./out --source public`

## 缺依赖会怎样
运行自动检测环境。缺 Node / 数据组件时，会打印缺什么 + 怎么装（含 Wind MCP / npm 两种方式），补齐后重跑同一条命令即继续。

## 免责
AI 框架化推理 + 机械估值，非投资建议；数据来自公开接口，可能延迟误差。
