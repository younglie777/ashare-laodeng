#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 Wind MCP 分红历史（每股派息）生成 graham_westock.py 所需的 div.txt。

为什么需要它（根因 · 坑 7）：
  westock 1.0.4 的 dividend 接口残——批量 `dividend list --all` 只回状态行、
  单只 `dividend list <code> --all` 也只回当年，都拿不到 Graham 第4条要的
  「10年中≥6年分红(近3年≥2年) + 近3年平均分红率≥10%」。故分红史改由 Wind MCP 提供：
  AI 用 mcp__wind-finance__get_stock_events 拉每只幸存者的年度每股派息(元)，
  写成 JSON，本脚本把它转成 graham 兼容的 div.txt。

输入 JSON 格式（AI 用 Wind 拉好后写出，路径默认 ./wind_dividends.json）：
  {
    "sh600757": {"name": "长江传媒", "dividends": {"2016": 0.05, "2017": 0.10, ..., "2025": 0.41}},
    "sz000661": {"name": "长春高新", "dividends": {"2024": 0.80, "2025": 0.80}}
  }
  - dividends 的 key 支持 "2016" / "2016-12-31" / 2016，value 为当年每股现金红利（元/股）。
  - 【缺某年就不写该年】→ 第二遍 graham 会判为「缺分红年」而淘汰（与真实历史一致）。

输出：<raw>/div.txt
  totalCashDiviComRMB = 每股派息 × 总股本(股，取自同目录 quo.txt)
  列名对齐 graham_westock.parse_dividends：
    reportEndDate | dividendFlag | dividendType | procedure | proposalSn |
    rightRegDate | exDiviDate | bonusShareRatio | tranAddShareRatio |
    cashDiviRMB | totalCashDiviComRMB | dividendPlan
"""
import os
import sys
import json
import argparse


def parse_shares(quo_path):
    """从 quo.txt 解析 symbol -> total_shares(股)。"""
    if not os.path.exists(quo_path):
        return {}
    txt = open(quo_path, encoding='utf-8').read()
    lines = [l for l in txt.split('\n') if l.lstrip().startswith('|')]
    if not lines:
        return {}
    hdr = [c.strip() for c in lines[0].strip().strip('|').split('|')]
    si = hdr.index('symbol') if 'symbol' in hdr else (hdr.index('code') if 'code' in hdr else 0)
    if 'total_shares' not in hdr:
        return {}
    ti = hdr.index('total_shares')
    out = {}
    for l in lines[1:]:
        c = [x.strip() for x in l.strip().strip('|').split('|')]
        try:
            out[c[si]] = float(c[ti])
        except Exception:
            pass
    return out


def norm_year(k):
    s = str(k).replace('-', '')[:4]
    return int(s) if s.isdigit() else None


def build(json_path, raw_dir, quo_path=None):
    with open(json_path, encoding='utf-8') as fh:
        data = json.load(fh)
    quo_path = quo_path or os.path.join(raw_dir, 'quo.txt')
    shares = parse_shares(quo_path)
    parts = []
    for code, info in data.items():
        name = info.get('name', '') if isinstance(info, dict) else ''
        divs = info.get('dividends', info) if isinstance(info, dict) else {}
        sh = shares.get(code)
        if not sh:
            print(f'  ⚠ {code} 未在 quo.txt 找到总股本，跳过（第二遍将被条件4淘汰）')
            continue
        rows = []
        for yk, dps in divs.items():
            y = norm_year(yk)
            if y is None or not dps:
                continue
            dps = float(dps)
            total = round(dps * sh, 2)
            rows.append(
                f'| {y}1231 | 是 | 有分红 | 方案实施 | 1 |  |  |  |  | {dps} | {total} | 10派{round(dps*10,2)}元 |')
        if not rows:
            print(f'  ⚠ {code} {name} 无分红记录，跳过')
            continue
        block = (
            f'#### {code} {name}\n\n**分红历史**\n\n'
            f'| reportEndDate | dividendFlag | dividendType | procedure | proposalSn | rightRegDate | exDiviDate | bonusShareRatio | tranAddShareRatio | cashDiviRMB | totalCashDiviComRMB | dividendPlan |\n'
            f'| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n'
            + '\n'.join(rows) + '\n')
        parts.append(block)
        print(f'  {code} {name}: {len(rows)} 年分红 (总股本 {sh:,.0f} 股)')
    out_path = os.path.join(raw_dir, 'div.txt')
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(parts))
    print(f'✅ 写出 {out_path}（{len(parts)} 只）')
    return out_path


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Wind 分红 JSON → graham div.txt')
    ap.add_argument('json', nargs='?', default='wind_dividends.json', help='Wind 分红 JSON 路径')
    ap.add_argument('--raw', default=os.path.join(os.getcwd(), 'raw'), help='raw 目录（含 quo.txt，写入 div.txt）')
    ap.add_argument('--quo', default=None, help='quo.txt 路径（默认 <raw>/quo.txt）')
    a = ap.parse_args()
    build(a.json, a.raw, a.quo)
