# -*- coding: utf-8 -*-
"""老登股推荐 · Graham 筛选逻辑边界自测（合成数据，不改真实数据）。
验证 2026-08-05 多轮放宽后，analyze() 的 7 条件 + 两遍法 skip 分支判断正确。
"""
import sys, copy, json
sys.path.insert(0, r'C:/Users/a2821/.workbuddy/skills/老登股推荐/scripts')
import graham_westock as gw

YEARS = list(range(2016, 2026))

def base(sym='sh600000'):
    profiles = {sym: {'name': sym, 'industry': '制造业', 'regAddress': '四川省成都市高新区'}}
    quotes = {sym: {'total_market_cap': 100.0, 'prev_close': 10.0,
                    'pe_ratio': 8.0, 'pb_ratio': 1.0, 'total_shares': 10e8}}
    lrb = {}
    for y in YEARS:
        lrb[sym] = lrb.get(sym, {})
        lrb[sym][f'{y}-12-31'] = {'OperatingRevenue': 30e8,
                                   'NPParentCompanyOwners': 20e8, 'BasicEPS': None}
    zcfz = {}
    for y in YEARS:
        kf = 10e8 if y <= 2018 else 15e8
        zcfz[sym] = zcfz.get(sym, {})
        zcfz[sym][f'{y}-12-31'] = {'TotalCurrentAssets': 200e8, 'TotalCurrentLiability': 100e8,
                                    'TotalLiability': 120e8, 'InterestBearDebt': 50e8,
                                    'GoodWill': 10e8, 'SEWithoutMI': 100e8,
                                    'NPDeductNonRecurringPL': kf}
    divs = []
    for y in [2016, 2017, 2018, 2019, 2020, 2021, 2024, 2025]:
        divs.append({'reportEndDate': f'{y}1231', 'totalCashDiviComRMB': 3e8,
                     'dividendType': '有分红'})
    return profiles, quotes, lrb, zcfz, {sym: divs}

def run(name, mut=None, skip=False, expect_pass=None):
    gw.SKIP_DIV = skip
    p, q, l, z, d = base()
    if mut:
        mut(p, q, l, z, d)
    sym = 'sh600000'
    R = gw.analyze(sym, p, q, l, z, d)
    ok = (R['pass'] == expect_pass) if expect_pass is not None else True
    flag = '✓' if ok else '✗'
    print(f'[{flag}] {name:28s} pass={R["pass"]}  fails={R["fail"]}')
    return ok, R

results = []
# 1. 全条件通过（基准）
results.append(run('基准(应过)', expect_pass=True))
# 2. 商誉 26% 应淘汰 / 24% 应过
results.append(run('商誉26%(应fail)',
    mut=lambda p,q,l,z,d: z['sh600000']['2025-12-31'].__setitem__('GoodWill',26e8),
    expect_pass=False))
results.append(run('商誉24%(应过)',
    mut=lambda p,q,l,z,d: z['sh600000']['2025-12-31'].__setitem__('GoodWill',24e8),
    expect_pass=True))
# 3. 规模：营收10亿+市值40亿 应淘汰
results.append(run('规模不足(应fail)',
    mut=lambda p,q,l,z,d: (q['sh600000'].__setitem__('total_market_cap',40.0),
                            l['sh600000']['2025-12-31'].__setitem__('OperatingRevenue',10e8)),
    expect_pass=False))
# 4. 分红仅 5 年 应淘汰
def div_n(years):
    return lambda p,q,l,z,d: d.__setitem__('sh600000',
        [{'reportEndDate':f'{y}1231','totalCashDiviComRMB':3e8,'dividendType':'有分红'} for y in years])
results.append(run('分红5年(应fail)', mut=div_n([2016,2017,2018,2019,2020]), expect_pass=False))
# 5. 分红恰好 6 年(含近3年2年) 应过
results.append(run('分红6年含近3年2(应过)',
    mut=div_n([2019,2020,2021,2022,2024,2025]), expect_pass=True))
# 6. 扣非 1缺1非正 应过 / 2非正 应淘汰
def kf_mut(spec):
    def f(p,q,l,z,d):
        for y,v in spec.items():
            z['sh600000'][f'{y}-12-31']['NPDeductNonRecurringPL'] = v
    return f
results.append(run('扣非1缺1非正(应过,缺口在中间年份)',
    mut=kf_mut({2020: None, 2021: 0}), expect_pass=True))
results.append(run('扣非2非正(应fail)',
    mut=kf_mut({2020: 0, 2021: 0}), expect_pass=False))
# 7. 流动比率 1.4 应淘汰 / 1.5 应过
results.append(run('流动比率1.4(应fail)',
    mut=lambda p,q,l,z,d: (z['sh600000']['2025-12-31'].__setitem__('TotalCurrentAssets',140e8),
                            z['sh600000']['2025-12-31'].__setitem__('TotalLiability',30e8)),
    expect_pass=False))
results.append(run('流动比率1.5(应过)',
    mut=lambda p,q,l,z,d: (z['sh600000']['2025-12-31'].__setitem__('TotalCurrentAssets',150e8),
                            z['sh600000']['2025-12-31'].__setitem__('TotalLiability',30e8)),
    expect_pass=True))
# 8. 近3年扣非PE=21 应淘汰 / =20 应过
results.append(run('PE3=21(应fail)',
    mut=lambda p,q,l,z,d: q['sh600000'].__setitem__('total_market_cap',315.0),
    expect_pass=False))
results.append(run('PE3=20(应过)',
    mut=lambda p,q,l,z,d: q['sh600000'].__setitem__('total_market_cap',300.0),
    expect_pass=True))
# 9. 扣非EPS增长 32% 应淘汰 / 34% 应过
results.append(run('EPS增长32%(应fail)',
    mut=lambda p,q,l,z,d: [z['sh600000'][f'{y}-12-31'].__setitem__('NPDeductNonRecurringPL',13.2e8) for y in (2023,2024,2025)],
    expect_pass=False))
results.append(run('EPS增长34%(应过)',
    mut=lambda p,q,l,z,d: [z['sh600000'][f'{y}-12-31'].__setitem__('NPDeductNonRecurringPL',13.4e8) for y in (2023,2024,2025)],
    expect_pass=True))
# 10. 两遍法 skip 分支：无分红数据 + skip=True 应过
results.append(run('skip+无分红(应过)',
    mut=lambda p,q,l,z,d: d.__setitem__('sh600000',[]), skip=True, expect_pass=True))
# 11. 不 skip + 无分红 应淘汰
results.append(run('无分红不skip(应fail)',
    mut=lambda p,q,l,z,d: d.__setitem__('sh600000',[]), skip=False, expect_pass=False))

passed = sum(1 for r,_ in results if r)
print(f'\n=== 自测结果: {passed}/{len(results)} 通过 ===')
sys.exit(0 if passed == len(results) else 1)
