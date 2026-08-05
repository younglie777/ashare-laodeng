#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股 Graham 防御型选股 — 整理版（westock 原生后端，修正 CLI 调用 + markdown 解析）。

流程: westock-tool filter 粗筛 -> westock-data 批量拉取(finance/quote/dividend/profile, markdown)
       -> 解析 -> 7条条件精算 -> Markdown(中间产物统一 MD，省 token、易解析)
数据源: 腾讯自选股(westock) 公开接口；财务=近 WIN 个完整年报（默认10年 2016-2025）。
       注：本脚本只负责「筛选」（需多年原始财报，故走 westock）；估值 PE/PB/股息率/ROE/实时价/52周
       在下游 analyze_selected.py 阶段【优先用 Wind】（wind_cache），westock/公开接口仅兜底。
产出: A股防御型选股_YYYYMMDD_w<WIN><OUT_SUF>.md + JSON 摘要(打印末行)。

用法:
  python3 graham_westock.py <WIN=10> [codes_file] [raw_dir] [out_suffix] [mv_gate=50] [rev_gate=20]
    WIN       时间窗口年数（默认10；2026-08-05 放宽：盈利持续允许10年中1年非正/缺年，分红改为10年≥6年(近3年≥2年)；盈利增长仍≥1/3）
    codes_file 候选代码列表(每行一个 sh/sz 代码)；默认 <skill>/data/codes.txt
    raw_dir    westock-data 拉取的原始 markdown 目录；默认 <skill>/data/raw
    out_suffix 输出文件名后缀（避免覆盖）；默认 ''
    mv_gate    规模闸门-总市值下限(亿)；默认50（2026-08-05 由150下调：原值挡掉太多中小盘）
    rev_gate   规模闸门-营收下限(亿)；默认20（2026-08-05 由60下调）
"""
import json, re, os, datetime, glob, sys

# --skip-dividend：两遍法第一遍专用——先按除「连续分红」外的 6 条 Graham 条件缩窄候选，
# 避免对全市场几千只逐只拉分红（批量分红接口不吐表）。第二遍再对幸存者补分红后终审。
SKIP_DIV = '--skip-dividend' in sys.argv
if SKIP_DIV:
    sys.argv.remove('--skip-dividend')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'data')
TOOLS = os.path.join(os.path.dirname(SCRIPT_DIR), 'tools')
# 注册地省·市解析
# 用户 2026-07-31 要求：按统一条件一视同仁判定
sys.path.insert(0, TOOLS)
import location  # 解析 province/city（见 tools/location.py）

# 用法: python graham_westock.py <WIN=10> [codes_file] [raw_dir] [out_suffix] [mv_gate=50] [rev_gate=20]
WIN = int(sys.argv[1]) if len(sys.argv) > 1 else 10  # 默认10年：Graham原教旨；2026-07-31用户确认回到10年（5年窗口会把盈利增长对比基期前移反而更严，故退回10年）
CODES_FILE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(DATA_DIR, 'codes.txt')
BASE = sys.argv[3] if len(sys.argv) > 3 else os.path.join(DATA_DIR, 'raw')
OUT_SUF = sys.argv[4] if len(sys.argv) > 4 else ''
MV_GATE = float(sys.argv[5]) if len(sys.argv) > 5 else 50.0  # 默认50亿：2026-08-05 由150下调，纳入中小盘
REV_GATE = float(sys.argv[6]) if len(sys.argv) > 6 else 20.0  # 默认20亿：2026-08-05 由60下调
YEARS = list(range(2026 - WIN, 2026))
G = 3 if WIN >= 10 else 2
FIRST3 = list(range(2026 - WIN, 2026 - WIN + G))
LAST3 = list(range(2026 - G, 2026))
RECENT3 = [2023, 2024, 2025]   # 分红率/3年均PE 用固定近3年(不随窗口缩放)
DIV_RATE_MIN = 10   # 近3年平均分红率下限(%)：2026-08-05 由 30% 下调至 10%（用户非红利风格；重大投资期低分红合理）
DIV_MIN_YEARS = 6    # 分红：10年中至少分红年数（60%）
RECENT_DIV_MIN = 2   # 分红：近3年至少分红年数
KF_MAX_MISS = 1      # 盈利持续：10年最多允许扣非数据缺失年数
KF_MAX_BAD = 1       # 盈利持续：10年最多允许扣非非正年数（周期低谷/一次性减值）
PE3_MAX = 20         # 近3年均扣非PE上限：2026-08-05 由 15 放宽至 20
CR_MIN = 1.5         # 流动比率下限：2026-08-05 由 2.0 放宽至 1.5
GW_NE_MAX = 0.25      # 商誉/净资产上限：2026-08-05 由 20% 放宽至 25%（用户厌恶高商誉暴雷，但不宜过松）
FIN_INDUSTRIES = {'银行', '非银金融', '证券', '保险', '多元金融', '证券Ⅱ', '保险Ⅱ', '多元金融Ⅱ'}


def f(x):
    try:
        if x in (None, '', '-', '—', 'None'):
            return None
        return float(str(x).replace(',', ''))
    except Exception:
        return None


# ---------- markdown 表解析 ----------
def parse_md_tables(text):
    """返回 [ [rowdict, ...], ... ]，每个元素是一张表的行列表。"""
    lines = text.split('\n')
    tables, i, n = [], 0, len(lines)
    while i < n:
        if lines[i].lstrip().startswith('|'):
            block = []
            while i < n and lines[i].lstrip().startswith('|'):
                block.append(lines[i]);
                i += 1
            if len(block) >= 2:
                headers = [c.strip() for c in block[0].strip().strip('|').split('|')]
                rows = []
                for r in block[2:]:
                    cells = [c.strip() for c in r.strip().strip('|').split('|')]
                    if len(cells) == len(headers):
                        rows.append(dict(zip(headers, cells)))
                if rows:
                    tables.append(rows)
        else:
            i += 1
    return tables


def parse_dividends(text):
    """dividend list 批量输出: '#### shXXX 名称' 后跟 **分红历史** 表。返回 {symbol:[rowdict]}。"""
    lines = text.split('\n')
    result, cur, i, n = {}, None, 0, len(lines)
    while i < n:
        m = re.match(r'#+\s+(\S+)\s+(\S+)', lines[i].strip())
        if m:
            cur = m.group(1)
            i += 1
            continue
        if lines[i].lstrip().startswith('|'):
            block = []
            while i < n and lines[i].lstrip().startswith('|'):
                block.append(lines[i]);
                i += 1
            if len(block) >= 2:
                headers = [c.strip() for c in block[0].strip().strip('|').split('|')]
                for r in block[2:]:
                    cells = [c.strip() for c in r.strip().strip('|').split('|')]
                    if len(cells) == len(headers) and cur:
                        result.setdefault(cur, []).append(dict(zip(headers, cells)))
        else:
            i += 1
    return result


def load_raw():
    raw = {}
    for kind in ('pro', 'quo', 'fin_lrb', 'fin_zcfz', 'div'):
        p = os.path.join(BASE, kind + '.txt')
        raw[kind] = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
    return raw


def annual(d):
    out = {}
    for dt, row in d.items():
        if dt and dt.endswith('12-31'):
            try:
                out[int(dt[:4])] = row
            except Exception:
                pass
    return out


def analyze(sym, profiles, quotes, lrb, zcfz, dividends):
    R = {'code': sym, 'name': '', 'industry': '', 'pass': False, 'fail': []}
    pro = profiles.get(sym, {})
    R['name'] = pro.get('name', '')
    R['industry'] = pro.get('industry') or pro.get('sector', '')
    if R['industry'] in FIN_INDUSTRIES:
        R['fail'].append('金融行业')
    if 'ST' in (R['name'] or '').upper():
        R['fail'].append('ST股')

    # 产地(省·市): 客观信息
    addr = pro.get('regAddress') or pro.get('officeAddress') or ''
    prov, city = location.parse_location(addr)
    R.update(reg_addr=addr, province=prov, city=city)

    quo = quotes.get(sym, {})
    prev = f(quo.get('prev_close'))
    tmc = f(quo.get('total_market_cap'))          # 单位: 亿元
    mktcap_yi = tmc                               # 已是亿元, 不再除1e8
    mktcap_yuan = (tmc * 1e8) if tmc else None    # 转回元用于PE计算
    pe = f(quo.get('pe_ratio'))
    pb = f(quo.get('pb_ratio'))
    shares = f(quo.get('total_shares'))           # 单位: 股
    R.update(prev_close=prev, mktcap_yi=mktcap_yi, pe=pe, pb=pb)

    lrb_a = annual(lrb.get(sym, {}))
    zcfz_a = annual(zcfz.get(sym, {}))

    # 条件1 规模
    rev = None
    for y in (2025, 2024, 2023):
        if y in lrb_a:
            rev = f(lrb_a[y].get('OperatingRevenue')) or f(lrb_a[y].get('TotalOperatingRevenue'))
            if rev is not None:
                break
    rev_yi = (rev / 1e8) if rev else None
    R['rev2025_yi'] = rev_yi
    if not ((rev_yi and rev_yi >= REV_GATE) or (mktcap_yi and mktcap_yi >= MV_GATE)):
        R['fail'].append('营收<%.0f亿且市值<%.0f亿' % (REV_GATE, MV_GATE))

    # 条件2 财务稳健
    z = zcfz_a.get(2025) or (zcfz_a.get(max(zcfz_a.keys())) if zcfz_a else None)
    if z:
        ca = f(z.get('TotalCurrentAssets'));
        cl = f(z.get('TotalCurrentLiability'));
        tl = f(z.get('TotalLiability'))
        ibd = f(z.get('InterestBearDebt')) or 0
        gw = f(z.get('GoodWill')) or 0
        ne = f(z.get('SEWithoutMI')) or f(z.get('TotalShareholderEquity'))
        cr = (ca / cl) if (ca and cl) else None
        nca = (ca - tl) if (ca is not None and tl is not None) else None
        R.update(current_ratio=cr, ibd_yi=(ibd / 1e8) if ibd else 0,
                 nca_yi=(nca / 1e8) if nca is not None else None,
                 gw_ne_pct=(gw / ne * 100) if ne else None)
        if not (cr and cr >= CR_MIN):
            R['fail'].append('流动比率<%.1f' % CR_MIN)
        if not (nca is not None and ibd <= nca):
            R['fail'].append('有息负债>净流动资产')
        if not (ne and gw / ne <= GW_NE_MAX):
            R['fail'].append('商誉/净资产>%.0f%%' % (GW_NE_MAX * 100))
    else:
        R['fail'].append('缺资产负债表')

    # 条件3 盈利持续 (近WIN年扣非>0)，取自 zcfz/lrb 的 NPDeductNonRecurringPL
    kf = {}
    for y in YEARS:
        v = f(zcfz_a[y].get('NPDeductNonRecurringPL')) if y in zcfz_a else None
        if v is None and y in lrb_a:
            v = f(lrb_a[y].get('NPDeductNonRecurringPL'))
        kf[y] = v
    R['kf_years'] = {y: (round(kf[y] / 1e8, 2) if kf[y] is not None else None) for y in YEARS}
    miss = [y for y in YEARS if kf[y] is None]
    bad = [y for y in YEARS if kf[y] is not None and kf[y] <= 0]
    # 放宽（2026-08-05）：允许最多 1 年数据缺失、最多 1 年扣非非正（周期低谷/一次性减值）
    if len(miss) > KF_MAX_MISS:
        R['fail'].append('扣非数据缺年>%d:%s' % (KF_MAX_MISS, ','.join(map(str, miss))))
    if len(bad) > KF_MAX_BAD:
        R['fail'].append('扣非非正年>%d:%s' % (KF_MAX_BAD, ','.join(map(str, bad))))

    # 条件5 扣非EPS增长≥1/3
    eps = {}
    for y in YEARS:
        be = f(lrb_a[y].get('BasicEPS')) if y in lrb_a else None
        np_ = f(lrb_a[y].get('NPParentCompanyOwners')) if y in lrb_a else None
        if be is not None and np_ and np_ > 0 and kf.get(y) is not None:
            eps[y] = be * (kf[y] / np_)
        elif kf.get(y) is not None and shares:
            eps[y] = kf[y] / shares
        else:
            eps[y] = None
    f3 = [eps[y] for y in FIRST3 if eps[y] is not None]
    l3 = [eps[y] for y in LAST3 if eps[y] is not None]
    if len(f3) == G and len(l3) == G:
        fa, la = sum(f3) / G, sum(l3) / G
        raw_g = (la / fa - 1) * 100 if fa > 0 else None
        # 防基数极小导致增长%爆炸（如 2016-2018 扣非EPS≈0 的公司，la/fa 会得出上百万%）。
        # 仅对【展示值】封顶 999.99%，不影响下方条件5 通过判定（仍用真实 la/fa-1 与 1/3 比较）。
        R['eps_growth_pct'] = round(min(raw_g, 999.99), 2) if raw_g is not None else None
        if not (fa > 0 and la / fa - 1 >= 1 / 3):
            R['fail'].append('扣非EPS增长<1/3')
    else:
        R['fail'].append('扣非EPS数据不全')

    # 条件6 近3年均扣非PE（2026-08-05 上限由15放宽至20）
    kf3 = [kf[y] for y in RECENT3 if kf.get(y) is not None]
    if len(kf3) == 3 and mktcap_yuan and prev:
        avg_kf = sum(kf3) / 3
        R['pe3_kf'] = round(mktcap_yuan / avg_kf, 2) if avg_kf > 0 else None
        if not (R['pe3_kf'] and R['pe3_kf'] <= PE3_MAX):
            R['fail'].append('3年均扣非PE>%d' % PE3_MAX)
    else:
        R['fail'].append('3年扣非PE算不全')

    # 条件7 PB≤1.5 或 PE×PB≤22.5
    R['pe_pb'] = round(pe * pb, 2) if (pe is not None and pb is not None) else None
    if not ((pb is not None and pb <= 1.5) or (pe is not None and pb is not None and pe * pb <= 22.5)):
        R['fail'].append('PB>1.5且PE*PB>22.5')

    # 条件4 分红（2026-08-05 放宽：10年≥6年分红、且近3年≥2年；仍保留分红率≥DIV_RATE_MIN%）
    if SKIP_DIV:
        # 两遍法第一遍：暂不以分红淘汰，避免对全市场逐只拉分红
        R['div_years'] = list(YEARS)
    else:
        div = dividends.get(sym, [])
        div_year = {}
        for r in div:
            red = str(r.get('reportEndDate', ''))
            if len(red) < 4:
                continue
            y = int(red[:4])
            amt = f(r.get('totalCashDiviComRMB')) or 0
            if (r.get('dividendType') == '有分红' or r.get('dividendFlag') == '是' or amt > 0):
                div_year[y] = div_year.get(y, 0) + amt
        div_years_list = sorted(y for y in div_year if div_year[y] > 0)
        R['div_years'] = div_years_list
        # 新规则：10年中至少 DIV_MIN_YEARS 年分红(60%)，且近3年至少 RECENT_DIV_MIN 年分红
        if len(div_years_list) < DIV_MIN_YEARS:
            R['fail'].append('分红年数<%d(实%d)' % (DIV_MIN_YEARS, len(div_years_list)))
        recent_div = [y for y in div_years_list if y in RECENT3]
        if len(recent_div) < RECENT_DIV_MIN:
            R['fail'].append('近3年分红年数<%d' % RECENT_DIV_MIN)
        # 近3年平均分红率（未分红年按0%计入，更保守）
        payout_rates = []
        for y in RECENT3:
            np_ = f(lrb_a[y].get('NPParentCompanyOwners')) if y in lrb_a else None
            if np_ and np_ > 0:
                payout_rates.append(div_year.get(y, 0) / np_ * 100)
        if len(payout_rates) == 3:
            R['div_rate_avg3'] = round(sum(payout_rates) / 3, 2)
            if R['div_rate_avg3'] < DIV_RATE_MIN:
                R['fail'].append('近3年平均分红率<%d%%' % DIV_RATE_MIN)
        else:
            R['fail'].append('近3年分红率算不全')

    R['pass'] = not R['fail']
    return R




def make_md(res, out_path, run_date):
    """以 Markdown 输出筛选结果（替代 XLSX：AI 直接读 MD 省 token、易解析）。"""
    res = [r for r in res if 'name' in r]
    res.sort(key=lambda r: (not r.get('pass'), -(r.get('mktcap_yi') or 0)))
    HEAD = ['代码', '名称', '申万行业', '昨收价(元)', '总市值(亿)', '2025营收(亿)',
            '流动比率', '有息负债(亿)', '净流动资产(亿)', '商誉/净资产(%)',
            'PE(TTM)', 'PB', 'PE×PB', '近3年扣非PE', '近3平均分红率(%)',
            '扣非EPS增长(%)', f'{WIN}年扣非正年数', f'{WIN}年分红年数', '是否入选', '淘汰原因']
    lines = ['# A股类Graham防御型选股 - 筛选结果', '']
    passed = [r for r in res if r.get('pass')]
    lines += [
        f'- 生成日期: {run_date}',
        f'- 数据来源: 腾讯自选股(westock)；财务=近{WIN}个完整年报',
        f'- 候选池: {len(res)} 只（规模闸门：营收≥{REV_GATE:.0f}亿 或 总市值≥{MV_GATE:.0f}亿）',
        f'- 入选: {len(passed)} 只', '',
        '## 选股结果', '',
        '| ' + ' | '.join(HEAD) + ' |',
        '| ' + ' | '.join(['---'] * len(HEAD)) + ' |',
    ]
    yn = lambda b: '✓' if b else '✗'
    for r in res:
        ky = r.get('kf_years', {})
        pos_kf = sum(1 for v in ky.values() if v is not None and v > 0)
        divy = set(int(x) for x in r.get('div_years', []))
        cells = [r['code'], r.get('name', ''), r.get('industry', ''), r.get('prev_close'),
                 r.get('mktcap_yi'), r.get('rev2025_yi'), r.get('current_ratio'), r.get('ibd_yi'),
                 r.get('nca_yi'), r.get('gw_ne_pct'), r.get('pe'), r.get('pb'), r.get('pe_pb'),
                 r.get('pe3_kf'), r.get('div_rate_avg3'), r.get('eps_growth_pct'),
                 f'{pos_kf}/{WIN}', f'{len(divy)}/{WIN}', yn(r.get('pass')), '；'.join(r.get('fail', [])) or '—']
        cells = ['' if c is None else c for c in cells]
        lines.append('| ' + ' | '.join(str(c) for c in cells) + ' |')
    lines += ['', '## 入选名单', '']
    for p in passed:
        lines.append(f'- {p["code"]}  {p.get("name", "")}')
    open(out_path, 'w', encoding='utf-8').write('\n'.join(lines))


def main():
    t0 = datetime.datetime.now()
    run_date = datetime.date.today().strftime('%Y-%m-%d')
    ymd = datetime.date.today().strftime('%Y%m%d')
    raw = load_raw()

    profiles, quotes, lrb, zcfz, dividends = {}, {}, {}, {}, {}
    for table in parse_md_tables(raw['pro']):
        for row in table:
            sym = row.get('symbol') or row.get('code')
            if sym:
                profiles[sym] = row
    for table in parse_md_tables(raw['quo']):
        for row in table:
            sym = row.get('symbol') or row.get('code')
            if sym:
                quotes[sym] = row
    for table in parse_md_tables(raw['fin_lrb']):
        for row in table:
            sym = row.get('symbol') or row.get('SecuCode')
            d = row.get('_date') or row.get('EndDate')
            if sym and d:
                lrb.setdefault(sym, {})[d] = row
    for table in parse_md_tables(raw['fin_zcfz']):
        for row in table:
            sym = row.get('symbol') or row.get('SecuCode')
            d = row.get('_date') or row.get('EndDate')
            if sym and d:
                zcfz.setdefault(sym, {})[d] = row
    dividends = parse_dividends(raw['div'])

    codes = [c.strip().replace('\r', '') for c in open(CODES_FILE, encoding='utf-8') if c.strip()]
    res = []
    for sym in codes:
        try:
            res.append(analyze(sym, profiles, quotes, lrb, zcfz, dividends))
        except Exception as e:
            res.append({'code': sym, 'name': '', 'pass': False, 'fail': ['引擎异常:%s' % e]})
    passed = [r for r in res if r.get('pass')]
    out = f'A股防御型选股_{ymd}_w{WIN}{OUT_SUF}.md'
    make_md(res, out, run_date)
    print(f"[{(datetime.datetime.now()-t0).seconds}s] MD: {out}  候选 {len(res)} -> 入选 {len(passed)}")
    print(json.dumps({'date': run_date, 'total': len(res), 'passed': len(passed),
                      'stocks': [{'code': p['code'], 'name': p.get('name', ''), 'industry': p.get('industry', ''),
                                  'pe': p.get('pe'), 'pb': p.get('pb'), 'pe3_kf': p.get('pe3_kf'),
                                  'div_rate_avg3': p.get('div_rate_avg3'), 'eps_growth_pct': p.get('eps_growth_pct'),
                                  'province': p.get('province'), 'city': p.get('city')}
                                 for p in passed], 'md': out}, ensure_ascii=False))


if __name__ == '__main__':
    main()
