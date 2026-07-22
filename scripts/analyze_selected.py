#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""老登股推荐 — 分析阶段数据准备。

读取 Graham 选股 Markdown 中间产物的「入选」股票，为每只补全：
  1. westock 已算好的 Graham 七条件指标（PE/PB/近3年扣非PE/分红率/扣非EPS增长/市值/营收）
  2. ai-berkshire tools/ashare_data.py 实时行情 + 52周高低 + 推算总股本
  3. ai-berkshire tools/financial_rigor.py 三情景估值（精确十进制）
产出 analysis_cards.json（供 AI 撰写四大师分析叙事）+ analysis_draft.md（数据卡草稿）。

用法:
  python3 analyze_selected.py [graham_选股.md] [out_dir=.]
  - 不选时自动取当前目录最新 A股防御型选股_*.md
"""
import json, os, re, sys, subprocess, datetime, shutil, glob as _glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(SCRIPT_DIR), 'tools')
PY = sys.executable
ASHARE = os.path.join(TOOLS, 'ashare_data.py')
RIGOR = os.path.join(TOOLS, 'financial_rigor.py')
sys.path.insert(0, TOOLS)
import location  # 注册地省·市解析（仅标注用，不参与筛选）


def _find_node():
    for c in _glob.glob(os.path.expanduser('~/.workbuddy/binaries/node/versions/*/node.exe')) + \
             _glob.glob(os.path.expanduser('~/.workbuddy/binaries/node/versions/*/bin/node')):
        return c
    return shutil.which('node') or 'node'


def _find_westock():
    base = os.path.expanduser('~/AppData/Local/Programs/WorkBuddy/resources/app.asar.unpacked/resources/builtin-skills')
    hits = _glob.glob(os.path.join(base, 'westock-data', 'scripts', 'index.js'))
    if hits:
        return hits[0]
    hits = _glob.glob(os.path.expanduser('~/**/westock-data/scripts/index.js'), recursive=True)
    return hits[0] if hits else None


NODE = _find_node()
WESTOCK = _find_westock()


def westock_profile_addr(sym):
    """经 westock-data profile 拉注册地址(regAddress)。失败返回 ''。"""
    if not WESTOCK:
        return ''
    code = sym.strip().lower()
    if not code.startswith(('sh', 'sz', 'bj')):
        code = ('sh' if code.startswith(('6', '9')) else 'sz') + code
    try:
        out = subprocess.run([NODE, WESTOCK, 'profile', code],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ''
    for line in out.splitlines():
        if line.lstrip().startswith('|') and code[2:] in line:
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            # regAddress 是第 12 列(0基11): code,name,listedDate,business,website,industry,
            # sector,issuePrice,regCapital,establishDate,chairman,regAddress,...
            if len(cells) > 11:
                return cells[11]
    return ''


def find_selection(arg):
    if arg and os.path.exists(arg):
        return arg
    import glob
    cands = sorted(glob.glob('A股防御型选股_*.md'), reverse=True)
    # 排除分析产物自身
    cands = [c for c in cands if 'analysis' not in c.lower()]
    return cands[0] if cands else None


def read_selected(md_path):
    """解析 Graham 选股 Markdown 中间产物，返回「是否入选=✓」的股票列表。"""
    text = open(md_path, encoding='utf-8').read()
    lines = text.split('\n')
    # 定位 选股结果 表头行（含「代码」与「是否入选」）
    header_i = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith('|') and '代码' in ln and '是否入选' in ln:
            header_i = i
            break
    if header_i is None:
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith('|') and '代码' in ln:
                header_i = i
                break
    if header_i is None:
        return []
    head = [c.strip() for c in lines[header_i].strip().strip('|').split('|')]
    idx = {h: i for i, h in enumerate(head)}

    def g(k):
        i = idx.get(k)
        return cells[i] if i is not None else None

    def num(v):
        v = (v or '').strip()
        if v in ('', '-', '—', 'None'):
            return None
        try:
            return float(v.replace(',', ''))
        except Exception:
            return None

    out = []
    for ln in lines[header_i + 2:]:  # 跳过表头与分隔行
        if not ln.lstrip().startswith('|'):
            continue
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if len(cells) != len(head):
            continue
        passed = (g('是否入选') or '').strip()
        if passed not in ('✓', 'True', 'TRUE', '1'):
            continue
        out.append({
            'code': str(g('代码') or '').strip(),
            'name': str(g('名称') or '').strip(),
            'industry': str(g('申万行业') or '').strip(),
            'prev_close': num(g('昨收价(元)')),
            'mktcap_yi': num(g('总市值(亿)')),
            'rev_yi': num(g('2025营收(亿)')),
            'pe': num(g('PE(TTM)')),
            'pb': num(g('PB')),
            'pe3_kf': num(g('近3年扣非PE')),
            'div_rate': num(g('近3平均分红率(%)')),
            'eps_growth': num(g('扣非EPS增长(%)')),
        })
    return out


def code6(sym):
    return re.sub(r'^(sh|sz|bj)', '', sym.strip().lower())


def enrich_ashare(sym):
    """返回 dict: price/pe/pb/h52/h52_low/shares_yi 或空。"""
    d = {}
    try:
        out = subprocess.run([PY, ASHARE, 'valuation', code6(sym)],
                             capture_output=True, text=True, timeout=30).stdout
        for line in out.splitlines():
            m = re.search(r'当前价:\s*([\d.]+)', line);  d['price'] = float(m.group(1)) if m else d.get('price')
            m = re.search(r'PE\(动\):\s*([\d.]+)', line);  d['pe'] = float(m.group(1)) if m else d.get('pe')
            m = re.search(r'PB:\s*([\d.]+)', line);        d['pb'] = float(m.group(1)) if m else d.get('pb')
            m = re.search(r'52周最高:\s*([\d.]+)', line);  d['h52'] = float(m.group(1)) if m else d.get('h52')
            m = re.search(r'52周最低:\s*([\d.]+)', line);  d['h52_low'] = float(m.group(1)) if m else d.get('h52_low')
            m = re.search(r'推算总股本:\s*([\d.]+)亿股', line); d['shares_yi'] = float(m.group(1)) if m else d.get('shares_yi')
    except Exception:
        pass
    return d


WIND_CACHE = os.path.join(os.path.dirname(SCRIPT_DIR), 'wind_cache')
SOURCE = 'auto'  # 数据源策略: auto(Wind优先/公开兜底) | wind(强制) | public(强制)


def load_wind_cache(sym):
    """读取 Wind MCP 预拉取的归一化数据（由 AI 通过 mcp__wind-stock 写入 wind_cache/<code>.json）。"""
    p = os.path.join(WIND_CACHE, f'{code6(sym)}.json')
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding='utf-8'))
        except Exception:
            return None
    return None


def enrich(sym, source='auto'):
    """数据源策略（Wind 优先，公开接口兜底，不强制）：
      auto  : 优先读 wind_cache/<code>.json（Wind 权威财务/估值 pe/pb/div_yield/roe）；
              缺失则整体回退 ashare_data（腾讯行情+东财52周）；
      wind  : 强制 Wind，缓存缺失则返回空并标注 wind-missing；
      public: 强制公开接口。
    Wind 提供 pe/pb/div_yield/roe；实时价与52周高低由公开接口(腾讯/东财)补充。"""
    wind = load_wind_cache(sym) if source in ('auto', 'wind') else None
    if wind and (wind.get('pe') is not None or wind.get('pb') is not None):
        pub = enrich_ashare(sym)  # 公开接口补充实时价 + 52周高低
        enr = {
            'price': wind.get('price') or pub.get('price'),
            'pe': wind.get('pe') or pub.get('pe'),
            'pb': wind.get('pb') or pub.get('pb'),
            'div_yield': wind.get('div_yield'),
            'roe': wind.get('roe'),
            'h52': pub.get('h52'),
            'h52_low': pub.get('h52_low'),
            'shares_yi': pub.get('shares_yi'),
        }
        return enr, 'wind+public'
    if source == 'wind':
        return {}, 'wind-missing'
    pub = enrich_ashare(sym)
    return pub, 'public'


def three_scenario(price, base_pe, eps_growth_pct):
    """用 financial_rigor 三情景估值。base_pe 用归一化近3年扣非PE(避免TTM为负)。
    返回 (stdout_text, parsed_targets)。"""
    if not (price and base_pe):
        return '', {}
    eps = price / base_pe
    # 前向增速：用历史扣非EPS增长做阻尼映射，避免把历史高增长当前瞻增速外推
    hist = (eps_growth_pct or 0) / 100.0
    neutral_g = max(-0.05, min(0.18, hist * 0.3))
    opt_g = min(0.28, neutral_g + 0.08) if neutral_g > 0 else 0.05
    pes_g = max(0.0, neutral_g - 0.07)
    neutral_pe = base_pe
    opt_pe = min(30.0, base_pe * 1.15)
    pes_pe = min(base_pe * 0.8, 15.0)
    cmd = [PY, RIGOR, 'three-scenario', '--price', str(price), '--eps', str(round(eps, 4)),
           '--shares', '1',
           '--growth', f'{opt_g:.3f}', f'{neutral_g:.3f}', f'{pes_g:.3f}',
           '--pe', f'{opt_pe:.1f}', f'{neutral_pe:.1f}', f'{pes_pe:.1f}',
           '--years', '3', '--currency', 'CNY']
    try:
        txt = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        return f'(三情景估算失败: {e})', {}
    targets = {}
    for line in txt.splitlines():
        m = re.search(r'(乐观|中性|悲观).*?([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)%', line)
        if m:
            targets[m.group(1)] = {'growth': float(m.group(2)), 'pe': float(m.group(3)),
                                   'eps': float(m.group(4)), 'target_price': float(m.group(5).replace(',', ''))}
    return txt, targets


def shares_yi_dummy():
    return 1.0


def build_card(stk):
    card = dict(stk)
    # 注册地省·市解析（仅作中性产地标注，不参与任何筛选/剔除）
    addr = westock_profile_addr(stk['code'])
    prov, city = location.parse_location(addr)
    card['reg_addr'] = addr
    card['province'] = prov
    card['city'] = city
    enr, used = enrich(stk['code'], SOURCE)
    card['realtime'] = enr
    card['data_source'] = used
    price = enr.get('price') or stk.get('prev_close')
    pe = enr.get('pe') or stk.get('pe')
    pb = enr.get('pb') or stk.get('pb')
    card['price_used'] = price
    card['pe_used'] = pe
    card['pb_used'] = pb
    card['pe3kf_used'] = stk.get('pe3_kf')
    card['h52'] = enr.get('h52')
    card['h52_low'] = enr.get('h52_low')
    card['shares_yi'] = enr.get('shares_yi')
    # 估值位置（相对52周）
    if price and enr.get('h52') and enr.get('h52_low'):
        rng = enr['h52'] - enr['h52_low']
        if rng:
            card['pos_in_52w'] = round((price - enr['h52_low']) / rng * 100, 1)
    # 三情景用归一化近3年扣非PE作基准（避免 TTM 为负，如长春高新）
    base_pe = stk.get('pe3_kf') or pe
    scen_txt, scen = three_scenario(price, base_pe, stk.get('eps_growth'))
    card['three_scenario_text'] = scen_txt
    card['three_scenario'] = scen
    # 红线否决速查（基于 Graham 指标 + 估值位置）
    red_flags = []
    if pb and pb > 1.5 and pe and pb * pe > 22.5:
        red_flags.append('估值双闸门超 Graham 数(PB>1.5 且 PE×PB>22.5)')
    if stk.get('div_rate') is not None and stk['div_rate'] < 30:
        red_flags.append('近3年平均分红率<30%')
    if stk.get('eps_growth') is not None and stk['eps_growth'] < 33.3:
        red_flags.append('扣非EPS增长<1/3（防御型门槛）')
    if card.get('pos_in_52w') is not None and card['pos_in_52w'] > 90:
        red_flags.append('股价处于52周高位区(>90%)，安全边际薄')
    card['red_flags'] = red_flags
    return card


def main():
    global SOURCE
    args = sys.argv[1:]
    if '--source' in args:
        i = args.index('--source')
        SOURCE = args[i + 1]
        args = args[:i] + args[i + 2:]
    selection = find_selection(args[0]) if args else None
    if not selection:
        print('❌ 未找到 Graham 选股结果 Markdown（请传入路径或确保当前目录有 A股防御型选股_*.md）')
        sys.exit(1)
    out_dir = args[1] if len(args) > 1 else '.'
    os.makedirs(out_dir, exist_ok=True)
    print(f'读取入选股: {selection} ｜ 数据源策略: {SOURCE}（Wind优先/公开兜底）')
    selected = read_selected(selection)
    print(f'Graham 入选 {len(selected)} 只: ' + ', '.join(s["name"] or s["code"] for s in selected))
    cards = [build_card(s) for s in selected]
    print(f'✅ 入选 {len(cards)} 只（仅按 Graham 条件，地域仅作省·市中性标注）')

    # 写 JSON
    json_path = os.path.join(out_dir, 'analysis_cards.json')
    with open(json_path, 'w', encoding='utf-8') as fh:
        json.dump({'source_md': os.path.abspath(selection),
                   'generated': datetime.date.today().strftime('%Y-%m-%d'),
                   'count': len(cards), 'cards': cards},
                  fh, ensure_ascii=False, indent=2)

    # 写 Markdown 数据卡草稿
    md_path = os.path.join(out_dir, 'analysis_draft.md')
    L = []
    L.append(f'# Graham 入选股 · 分析数据卡（{datetime.date.today().strftime("%Y-%m-%d")}）')
    L.append(f'来源: {os.path.basename(selection)} ｜ Graham入选 {len(cards)} 只\n')
    L.append('')
    for c in cards:
        loc = f'{c.get("province")}·{c.get("city")}' if c.get('province') and c.get('city') and c.get('province') != c.get('city') else (c.get('province') or c.get('city') or '—')
        L.append(f'\n## {c["name"]}（{c["code"]}） · {c.get("industry","")}')
        L.append(f'- 注册地(产地): {loc}')
        L.append(f'- 数据源: {c.get("data_source")}')
        L.append(f'- 现价: {c.get("price_used")} ｜ PE(TTM): {c.get("pe_used")} ｜ PB: {c.get("pb_used")}')
        L.append(f'- 52周区间: {c.get("h52_low")} ~ {c.get("h52")} ｜ 当前位置: {c.get("pos_in_52w")}%')
        L.append(f'- 总市值: {c.get("mktcap_yi")}亿 ｜ 2025营收: {c.get("rev_yi")}亿')
        L.append(f'- 近3年扣非PE: {c.get("pe3_kf")} ｜ 近3平均分红率: {c.get("div_rate")}% ｜ 扣非EPS增长: {c.get("eps_growth")}%')
        L.append(f'- 总股本: {c.get("shares_yi")}亿股')
        L.append(f'- 红线速查: {("；".join(c["red_flags"]) if c["red_flags"] else "无明显红线")}')
        L.append(f'\n**三情景估值（精确十进制）**\n```\n{c.get("three_scenario_text","").strip()}\n```')
    with open(md_path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L))

    print(f'✅ 数据卡: {json_path}')
    print(f'✅ 草稿:   {md_path}')
    print(json.dumps({'count': len(cards), 'json': json_path, 'draft': md_path}, ensure_ascii=False))


if __name__ == '__main__':
    main()
