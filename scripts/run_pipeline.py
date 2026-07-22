#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""老登股推荐 · 一键流水线

把「Graham 防御型选股 → 四大师分析 → HTML 报告」串成一步。

子命令
------
  analyze  [xlsx路径]  [--out 目录] [--source auto|wind|public]
        # 已有 Graham 选股 xlsx → 分析 + 报告（无需 westock / 无需 Wind）
  screen   [--win 10] [--mv 150] [--rev 60] [--codes 候选.txt] [--raw raw目录] [--suffix _150]
        # 跑 Graham 筛选（需 raw/*.txt 已存在，见 fetch 或 README）
  fetch    [--rev 60] [--codes 候选.txt] [--raw raw目录] [--limit 8000] [--market hs]
        # 用 WorkBuddy 内置 westock 自动建中盘池 + 抓取 raw（需 westock 内置 skill + node）
  all      [--win 10] [--mv 150] [--rev 60] [--out 目录] [--source auto]
        # fetch + screen + analyze + report 全自动（需 westock；Wind 可选）

关于 Wind MCP（重点）
---------------------
  Wind 是【可选】数据源。没有 Wind MCP 也 100% 可用：
    - 分析阶段默认 --source auto：有 wind_cache/*.json 用 Wind，否则自动回退
      腾讯行情 + 东方财富（公开接口，零依赖、零配置）。
    - 直接 --source public 可强制只用公开接口。
    - 筛选阶段（fetch/screen）只用 westock 公开接口，跟 Wind 无关。
  所以「对方没装 Wind MCP」完全不影响使用，啥都不用配。

依赖
----
  - 分析/报告：仅 Python3 + 本技能自带 tools/（零外部依赖）
  - 筛选 fetch：WorkBuddy 内置 westock-data / westock-tool（Node）
"""
import os, sys, json, shutil, glob, subprocess, datetime, argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
SCREENER_DIR = os.path.join(os.path.dirname(SKILL_DIR), 'ashare-graham-screener')
GRAHAM = os.path.join(SCREENER_DIR, 'scripts', 'graham_westock.py')
ANALYZE = os.path.join(SCRIPT_DIR, 'analyze_selected.py')
GEN_REPORT = os.path.join(SCRIPT_DIR, 'gen_report.py')
PY = sys.executable


# ------------------------- 工具函数 -------------------------
def run(cmd, cwd=None, capture=True, silent=False):
    if not silent:
        print('$', ' '.join(cmd) if isinstance(cmd, list) else cmd)
    p = subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True)
    if not silent and p.stdout:
        print(p.stdout.strip()[-3000:])
    if p.returncode != 0 and p.stderr:
        print('[stderr]', p.stderr.strip()[-2000:])
    return p.returncode, (p.stdout or '')


def find_file(*candidates):
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def find_node():
    return shutil.which('node') or find_file(
        r'C:/Users/a2821/.workbuddy/binaries/node/versions/22.22.2/node.exe')


def find_westock():
    """返回 (westock_data_js, westock_tool_js) 或 None。"""
    env_d = os.environ.get('WESTOCK_DATA')
    env_t = os.environ.get('WESTOCK_TOOL')
    home = os.path.expanduser('~')
    builtin_dirs = glob.glob(os.path.join(home, 'AppData', 'Local', 'Programs',
                                'WorkBuddy', '**', 'builtin-skills'), recursive=True)
    cands_d, cands_t = [], []
    if env_d:
        cands_d.append(env_d)
    if env_t:
        cands_t.append(env_t)
    cands_d += [
        os.path.join(home, '.workbuddy', 'skills', 'westock-data', 'scripts', 'index.js'),
        os.path.join(home, '.workbuddy', 'binaries', 'node', 'workspace', 'westock-data', 'index.js'),
    ]
    cands_t += [
        os.path.join(home, '.workbuddy', 'skills', 'westock-tool', 'scripts', 'index.js'),
    ]
    for b in builtin_dirs:
        cands_d.append(os.path.join(b, 'westock-data', 'scripts', 'index.js'))
        cands_t.append(os.path.join(b, 'westock-tool', 'scripts', 'index.js'))
    d = find_file(*cands_d)
    t = find_file(*cands_t)
    if d and t:
        return d, t
    return None


def parse_codes(text):
    """从 westock-tool filter 的 markdown 表解析首列 code（如 sz002410）。"""
    lines = [l for l in text.split('\n') if l.strip().startswith('|')]
    if len(lines) < 2:
        return []
    headers = [c.strip().lower() for c in lines[0].strip().strip('|').split('|')]
    idx = 0
    for i, h in enumerate(headers):
        if h in ('code', 'symbol', '股票代码'):
            idx = i
            break
    codes = []
    for l in lines[2:]:
        cells = [c.strip() for c in l.strip().strip('|').split('|')]
        if len(cells) > idx and cells[idx]:
            codes.append(cells[idx])
    return codes


# ------------------------- 各阶段 -------------------------
def fetch_universe(rev, codes_file, raw_dir, limit, market):
    node = find_node()
    ws = find_westock()
    if not node or not ws:
        print('❌ 未找到 westock 内置 skill 或 node，无法自动 fetch。')
        print('   请手动按 README「手动筛选」步骤准备 codes.txt 与 raw/，再跑 screen。')
        sys.exit(1)
    data_js, tool_js = ws
    os.makedirs(raw_dir, exist_ok=True)
    rev_e8 = int(rev * 1e8)
    # 1) 建中盘池：营收 ≥ rev 亿
    print(f'① 建中盘池（{market} 营收≥{rev}亿）...')
    rc, out = run([node, tool_js, 'filter',
                   f'intersect([OperatingRevenueTTM>{rev_e8}])',
                   '--market', market, '--limit', str(limit)], silent=True)
    codes = parse_codes(out)
    if not codes:
        print('❌ 未从 filter 解析到股票代码，原始输出如下：')
        print(out[:2000])
        sys.exit(1)
    with open(codes_file, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(codes) + '\n')
    print(f'   候选 {len(codes)} 只 → {codes_file}')

    # 2) 抓 raw（分块，避免单次请求过大）
    jobs = [
        ('profile', ['profile'], 'pro.txt'),
        ('quote', ['quote'], 'quo.txt'),
        ('finance lrb', ['finance', '--type', 'lrb', '--num', '48'], 'fin_lrb.txt'),
        ('finance zcfz', ['finance', '--type', 'zcfz', '--num', '48'], 'fin_zcfz.txt'),
        ('dividend', ['dividend', 'list', '--years', '12'], 'div.txt'),
    ]
    chunk = 150
    for label, sub, fname in jobs:
        path = os.path.join(raw_dir, fname)
        print(f'② 抓 {label} → {fname}（分块 {chunk}/批）...')
        with open(path, 'w', encoding='utf-8') as fh:
            for i in range(0, len(codes), chunk):
                batch = codes[i:i + chunk]
                rc, out = run([node, data_js] + sub + [','.join(batch)],
                              capture=True, silent=True)
                if rc == 0 and out.strip():
                    fh.write(out + '\n')
                else:
                    print(f'   ⚠ 第 {i // chunk + 1} 批失败，跳过')
        print(f'   ✓ {path}')
    print('✅ fetch 完成。可继续 screen。')


def run_screen(args):
    if not os.path.exists(GRAHAM):
        print(f'❌ 未找到筛选脚本：{GRAHAM}')
        print('   老登股推荐 与 ashare-graham-screener 需为同级技能目录（都在 ~/.workbuddy/skills/ 下）。')
        sys.exit(1)
    codes = args.codes or os.path.join(SCREENER_DIR, 'data', 'codes.txt')
    raw = args.raw or os.path.join(SCREENER_DIR, 'data', 'raw')
    if not os.path.exists(codes):
        print(f'❌ 候选代码文件不存在：{codes}')
        print('   先跑 fetch，或按 README 手动准备 codes.txt。')
        sys.exit(1)
    if not (os.path.exists(os.path.join(raw, 'pro.txt')) and
            os.path.exists(os.path.join(raw, 'fin_lrb.txt'))):
        print(f'❌ raw 数据不全：{raw} 下需有 pro.txt/quo.txt/fin_lrb.txt/fin_zcfz.txt/div.txt')
        print('   先跑 fetch，或按 README 手动抓取。')
        sys.exit(1)
    region = '0'  # 发布版一律不做地域筛选（全市场一视同仁）
    work = args.out
    os.makedirs(work, exist_ok=True)
    cmd = [PY, GRAHAM, str(args.win), codes, raw, args.suffix or '',
           str(args.mv), str(args.rev), region]
    rc, out = run(cmd, cwd=work)
    # 从末行 JSON 取 xlsx 名
    xlsx = None
    for line in reversed(out.strip().split('\n')):
        line = line.strip()
        if line.startswith('{'):
            try:
                xlsx = json.loads(line).get('excel')
            except Exception:
                pass
            break
    if not xlsx:
        # 兜底：按命名规则猜
        ymd = datetime.date.today().strftime('%Y%m%d')
        xlsx = f'A股防御型选股_{ymd}_w{args.win}{args.suffix or ""}.xlsx'
    return os.path.join(work, xlsx)


def run_analyze(xlsx, out_dir, source):
    if not os.path.exists(xlsx):
        print(f'❌ 找不到选股结果：{xlsx}')
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    run([PY, ANALYZE, xlsx, out_dir, '--source', source])
    cards = os.path.join(out_dir, 'analysis_cards.json')
    if not os.path.exists(cards):
        print('❌ 分析未生成 analysis_cards.json，请检查 analyze_selected.py 报错。')
        sys.exit(1)
    return cards


def run_report(out_dir):
    rc, _ = run([PY, GEN_REPORT], cwd=out_dir)
    return rc == 0


# ------------------------- 子命令 -------------------------
def cmd_analyze(a):
    xlsx = a.xlsx or find_xlsx(a.out)
    if not xlsx:
        print('❌ 未指定 xlsx，且当前目录/技能 data 下未找到 Graham 选股结果（*_w*_*.xlsx）。')
        sys.exit(1)
    print(f'▶ 分析 + 报告：{xlsx}  (source={a.source})')
    run_analyze(xlsx, a.out, a.source)
    run_report(a.out)
    print(f'✅ 完成。报告在：{a.out}')


def cmd_screen(a):
    xlsx = run_screen(a)
    print(f'✅ 筛选完成：{xlsx}')


def cmd_fetch(a):
    fetch_universe(a.rev, a.codes or os.path.join(SCREENER_DIR, 'data', 'codes.txt'),
                  a.raw or os.path.join(SCREENER_DIR, 'data', 'raw'),
                  a.limit, a.market)


def cmd_all(a):
    print('▶ 全自动流水线：fetch → screen → analyze → report')
    work = a.out
    os.makedirs(work, exist_ok=True)
    codes = os.path.join(work, 'codes.txt')
    raw = os.path.join(work, 'raw')
    fetch_universe(a.rev, codes, raw, 8000, 'hs')
    a.codes, a.raw = codes, raw
    xlsx = run_screen(a)
    run_analyze(xlsx, work, a.source)
    run_report(work)
    print(f'✅ 全流程完成。报告在：{work}')


def find_xlsx(dirs):
    cands = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.startswith('A股防御型选股_') and f.endswith('.xlsx'):
                cands.append(os.path.join(d, f))
    cands.sort(key=os.path.getmtime, reverse=True)
    return cands[0] if cands else None


def build_parser():
    p = argparse.ArgumentParser(prog='run_pipeline', description='老登股推荐 一键流水线')
    sub = p.add_subparsers(dest='cmd')

    pa = sub.add_parser('analyze', help='已有 xlsx → 分析+报告（无需 westock/Wind）')
    pa.add_argument('xlsx', nargs='?', default=None)
    pa.add_argument('--out', default=os.getcwd())
    pa.add_argument('--source', default='auto', choices=['auto', 'wind', 'public'])
    pa.set_defaults(func=cmd_analyze)

    ps = sub.add_parser('screen', help='跑 Graham 筛选（需 raw/*.txt）')
    ps.add_argument('--win', type=int, default=10)
    ps.add_argument('--mv', type=float, default=150.0)
    ps.add_argument('--rev', type=float, default=60.0)
    ps.add_argument('--codes', default=None)
    ps.add_argument('--raw', default=None)
    ps.add_argument('--suffix', default='')
    ps.add_argument('--out', default=os.getcwd())
    ps.set_defaults(func=cmd_screen)

    pf = sub.add_parser('fetch', help='用 westock 自动建池+抓 raw（需 westock+node）')
    pf.add_argument('--rev', type=float, default=60.0)
    pf.add_argument('--codes', default=None)
    pf.add_argument('--raw', default=None)
    pf.add_argument('--limit', type=int, default=8000)
    pf.add_argument('--market', default='hs')
    pf.set_defaults(func=cmd_fetch)

    pl = sub.add_parser('all', help='全自动（需 westock；Wind 可选）')
    pl.add_argument('--win', type=int, default=10)
    pl.add_argument('--mv', type=float, default=150.0)
    pl.add_argument('--rev', type=float, default=60.0)
    pl.add_argument('--out', default=os.getcwd())
    pl.add_argument('--source', default='auto', choices=['auto', 'wind', 'public'])
    pl.set_defaults(func=cmd_all)
    return p


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, 'cmd', None):
        parser.print_help()
        sys.exit(0)
    args.func(args)
