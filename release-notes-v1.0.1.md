# 老登价值选股 v1.0.1 (2026-07-31)

修复: skill 默认参数过严（连续10年门槛 + 300/100亿规模闸门）。

## 改动
- `scripts/graham_westock.py`: WIN 默认 `10 → 5`；MV_GATE `300 → 150`；REV_GATE `100 → 60`
- `scripts/run_pipeline.py`: `--win` 默认 `10 → 5`（`screen` 与 `all` 两处）
- 脚本 docstring / 用法注释同步更新

## 背景
用户2026-07-22提出"连续10年太苛刻、营收>100亿太苛刻"，但此前仅改了工作区记忆、未真改 skill 源码，默认值仍为 10/300/100；本次（07-31）核实并彻底改 skill 文件，确保不依赖记忆也能跑对。

## 升级
- 下载本 release 的 `laodeng-stock-advisor.zip` 替换旧版；或
- `git pull` 最新 main 分支。
