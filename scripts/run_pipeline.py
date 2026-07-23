#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""老登股推荐 · 一键流水线

把「Graham 防御型选股 → 四大师分析 → HTML 报告」串成一步。

子命令
------
  analyze  [选股结果MD路径]  [--out 目录] [--source auto|wind|public]
        # 已有 Graham 选股 MD → 分析 + 报告（无需 westock / 无需 Wind）
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
# Graham 筛选器：优先用本仓库内置打包副本（单仓即可跑），
# 找不到时回退到兄弟技能 ashare-graham-screener（保持向后兼容）
SIBLING_SCREENER = os.path.join(os.path.dirname(SKILL_DIR), 'ashare-graham-screener')
LOCAL_SCREENER = os.path.join(SCRIPT_DIR, 'graham_westock.py')
GRAHAM = LOCAL_SCREENER if os.path.exists(LOCAL_SCREENER) else os.path.join(SIBLING_SCREENER, 'scripts', 'graham_westock.py')


def _default_data(name):
    """codes.txt / raw 默认路径：优先本仓库 data/，回退兄弟技能 data/。"""
    local = os.path.join(SKILL_DIR, 'data', name)
    if os.path.exists(local):
        return local
    return os.path.join(SIBLING_SCREENER, 'data', name)
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


# ------------------------- 运行前环境自检（前置依赖） -------------------------
def preflight_check(need_westock=True, source='public'):
    """运行前自检。返回 (issues, tips)。
    need_westock=False（analyze 模式）时跳过 Node/westock 检查。
    """
    issues, tips = [], []
    # Python 版本（脚本本身能跑起来说明至少有 3.x，这里给温和提示）
    if sys.version_info < (3, 8):
        issues.append('Python 版本过低（需 3.8+，推荐 3.10+）')
        tips.append('下载安装 Python 3.10+：https://www.python.org/downloads/')
    if need_westock:
        if not find_node():
            issues.append('未检测到 Node.js（westock 依赖 Node 运行）')
            tips.append('安装 Node.js 18+：https://nodejs.org ；装完后终端执行 `node -v` 能出版本号即成功')
        if not find_westock():
            issues.append('未找到行情/财务数据组件（westock-data / westock-tool 或 Wind MCP）')
            tips.append('需要 A 股行情/财务数据。建议优先通过 MCP 接入：在 WorkBuddy 启用「Wind MCP」等行情/财务类连接器即可；'
                        '若用 WorkBuddy 内置技能：在技能面板启用 westock-data、westock-tool；'
                        '其他 Agent / 环境：用 npm 安装（或克隆其仓库）westock-data 与 westock-tool，'
                        '把各自的 scripts/index.js 路径设到环境变量 WESTOCK_DATA、WESTOCK_TOOL（或加入 PATH），脚本会自动探测。')
    if source == 'wind':
        tips.append('⚠️ 你指定了 --source wind，请确保 Wind MCP 已连接；否则改用 --source public 走公开接口')
    return issues, tips


def run_preflight(need_westock, source):
    """打印自检结果。通过返回 True；不通过打印指引并返 False（调用方应 sys.exit(1)）。

    额外打印一行机器可读标记 `>>> PREFLEFT: ok|fail`，便于任意 Agent 解析成败。
    """
    issues, tips = preflight_check(need_westock, source)
    print('🔍 运行前环境自检（前置依赖）...')
    if not issues:
        print('   ✅ 前置依赖齐全，可以继续。')
        if source != 'wind':
            print('   ℹ️ Wind MCP 未连接 → 自动使用公开接口（腾讯行情 + 东方财富），无需配置。')
        print('>>> PREFLEFT: ok')
        return True
    print('   ❌ 环境自检未通过，缺失以下前置：')
    for i in issues:
        print(f'     • {i}')
    print('   请按以下指引补齐后，重新运行本命令即可继续：')
    for t in tips:
        print(f'     → {t}')
    print(f'>>> PREFLEFT: fail | missing={",".join(issues)}')
    return False


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
    # codes_first=True 表示 westock-data 要求代码放在 --type/--num 等旗标之前
    # （finance 子命令的特殊约定；profile/quote/dividend 则代码放最后即可）
    jobs = [
        ('profile', ['profile'], 'pro.txt', False),
        ('quote', ['quote'], 'quo.txt', False),
        ('finance lrb', ['finance', '--type', 'lrb', '--num', '48'], 'fin_lrb.txt', True),
        ('finance zcfz', ['finance', '--type', 'zcfz', '--num', '48'], 'fin_zcfz.txt', True),
        ('dividend', ['dividend', 'list', '--years', '12'], 'div.txt', False),
    ]
    chunk = 150
    for label, sub, fname, codes_first in jobs:
        path = os.path.join(raw_dir, fname)
        print(f'② 抓 {label} → {fname}（分块 {chunk}/批）...')
        with open(path, 'w', encoding='utf-8') as fh:
            for i in range(0, len(codes), chunk):
                batch = codes[i:i + chunk]
                if codes_first:
                    cmd = [node, data_js] + sub[:1] + [','.join(batch)] + sub[1:]
                else:
                    cmd = [node, data_js] + sub + [','.join(batch)]
                rc, out = run(cmd, capture=True, silent=True)
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
    codes = args.codes or _default_data('codes.txt')
    raw = args.raw or _default_data('raw')
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
    # 从末行 JSON 取 md 名
    md = None
    for line in reversed(out.strip().split('\n')):
        line = line.strip()
        if line.startswith('{'):
            try:
                md = json.loads(line).get('md')
            except Exception:
                pass
            break
    if not md:
        # 兜底：按命名规则猜
        ymd = datetime.date.today().strftime('%Y%m%d')
        md = f'A股防御型选股_{ymd}_w{args.win}{args.suffix or ""}.md'
    return os.path.join(work, md)


def run_analyze(md, out_dir, source):
    if not os.path.exists(md):
        print(f'❌ 找不到选股结果：{md}')
        sys.exit(1)
    os.makedirs(out_dir, exist_ok=True)
    run([PY, ANALYZE, md, out_dir, '--source', source])
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
    if not run_preflight(need_westock=False, source=a.source):
        sys.exit(1)
    md = a.selection or find_md(a.out)
    if not md:
        print('❌ 未指定 md，且当前目录/技能 data 下未找到 Graham 选股结果（*_w*_*.md）。')
        sys.exit(1)
    print(f'▶ 分析 + 报告：{md}  (source={a.source})')
    run_analyze(md, a.out, a.source)
    run_report(a.out)
    print(f'✅ 完成。报告在：{a.out}')


def cmd_screen(a):
    if not run_preflight(need_westock=True, source='public'):
        sys.exit(1)
    md = run_screen(a)
    print(f'✅ 筛选完成：{md}')


def cmd_fetch(a):
    if not run_preflight(need_westock=True, source='public'):
        sys.exit(1)
    fetch_universe(a.rev, a.codes or _default_data('codes.txt'),
                  a.raw or _default_data('raw'),
                  a.limit, a.market)


def cmd_all(a):
    if not run_preflight(need_westock=True, source=a.source):
        sys.exit(1)
    print('▶ 全自动流水线：fetch → screen → analyze → report')
    work = a.out
    os.makedirs(work, exist_ok=True)
    codes = os.path.join(work, 'codes.txt')
    raw = os.path.join(work, 'raw')
    fetch_universe(a.rev, codes, raw, 8000, 'hs')
    a.codes, a.raw = codes, raw
    md = run_screen(a)
    run_analyze(md, work, a.source)
    run_report(work)
    print(f'✅ 全流程完成。报告在：{work}')


def find_md(dirs):
    cands = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.startswith('A股防御型选股_') and f.endswith('.md'):
                cands.append(os.path.join(d, f))
    cands.sort(key=os.path.getmtime, reverse=True)
    return cands[0] if cands else None


def build_parser():
    p = argparse.ArgumentParser(prog='run_pipeline', description='老登股推荐 一键流水线')
    sub = p.add_subparsers(dest='cmd')

    pa = sub.add_parser('analyze', help='已有选股MD → 分析+报告（无需 westock/Wind）')
    pa.add_argument('selection', nargs='?', default=None,
                    help='Graham 选股结果 Markdown 路径（默认自动找最新 A股防御型选股_*.md）')
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
    pl.add_argument('--suffix', default='')
    pl.set_defaults(func=cmd_all)
    return p


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, 'cmd', None):
        parser.print_help()
        sys.exit(0)
    args.func(args)
