# -*- coding: utf-8 -*-
"""根据 analysis_cards.json 生成速览 Markdown 表（含「靠手段才过」警示列）。
用法（在含 analysis_cards.json 的目录下执行）：
    python gen_summary_table.py [out_md]
默认输出 summary_table.md。按 PB 由低到高排序。
"""
import json, os, sys


def f(x, nd=2):
    if x is None:
        return '-'
    try:
        return f'{float(x):.{nd}f}'
    except Exception:
        return str(x)


def main():
    base = os.getcwd()
    jpath = os.path.join(base, 'analysis_cards.json')
    # 防呆：argv[1] 是「输出文件」，绝不能指向输入文件本身（否则会把数据卡覆盖成速览表）
    _PROTECTED = {'analysis_cards.json', 'analysis_draft.md', 'four_masters.json'}
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, 'summary_table.md')
    if os.path.basename(out) in _PROTECTED or os.path.abspath(out) == os.path.abspath(jpath):
        print(f'ERROR: 输出文件不能是输入文件（{os.path.basename(out)}）。'
              f'用法: python gen_summary_table.py [out_md]，默认输出 summary_table.md',
              file=sys.stderr)
        sys.exit(2)
    d = json.load(open(jpath, encoding='utf-8'))
    cards = d['cards']

    rows = []
    for c in cards:
        rt = c.get('realtime') or {}
        ts = c.get('three_scenario') or {}
        opt = ts.get('乐观', {}).get('target_price')
        neu = ts.get('中性', {}).get('target_price')
        pes = ts.get('悲观', {}).get('target_price')
        up = ts.get('乐观', {}).get('upside_pct')
        soft = '；'.join(c.get('soft_pass') or [])
        rows.append([
            c['name'], c['code'], rt.get('price'), c.get('pe3_kf'), c.get('pb'),
            c.get('div_rate'), c.get('eps_growth'), c.get('mktcap_yi'), c.get('pos_in_52w'),
            opt, neu, pes, up, soft,
        ])
    rows.sort(key=lambda r: (float(r[4]) if r[4] is not None else 99))

    head = ['名称', '代码', '现价', '近3Y扣非PE', 'PB', '分红率%', '扣非EPS增%', '市值亿',
            '52w位置%', '乐观价', '中性价', '悲观价', '乐观涨%', '靠手段警示']
    lines = ['# Graham 入选股速览（按 PB 升序，最便宜排前）', '']
    lines.append('| ' + ' | '.join(head) + ' |')
    lines.append('|' + '---|' * len(head))
    for r in rows:
        soft = r[13]
        soft_disp = ('⚠️ ' + soft) if soft else '—'
        disp = [str(r[0]), str(r[1]), f(r[2]), f(r[3], 1), f(r[4]), f(r[5], 1), f(r[6], 1),
                f(r[7], 0), f(r[8], 0), f(r[9]), f(r[10]), f(r[11]), f(r[12]), soft_disp]
        lines.append('| ' + ' | '.join(disp) + ' |')
    lines.append('')
    lines.append('> ⚠️「靠手段才过」：放宽/平滑口径才达 Graham 标准（如当前TTM PE亏损但靠3年均值过线、或EPS增长靠低基数），非干净通过，需额外警惕。')
    open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    n_soft = sum(1 for c in cards if c.get('soft_pass'))
    print(f'written: {out} | {len(cards)} 只 | 靠手段才过 {n_soft} 只')


if __name__ == '__main__':
    main()
