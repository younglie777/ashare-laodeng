#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""老登股推荐 · 一键流水线

把「Graham 防御型选股 → 四大师分析 → HTML 报告」串成一步。

子命令
------
  pass1    [--win 10] [--mv 50] [--rev 20] [--out 目录]
        # 第一阶段：建中盘池 + 抓 raw(westock) + 第一遍初筛（跳分红条）
  wind-div [--json wind_dividends.json] [--raw raw目录] [--win 10] ...
        # 第二阶段：Wind 分红 JSON → div.txt → 第二遍筛选（带分红条）
  fetch    [--rev 20] [--codes 候选.txt] [--raw raw目录] [--limit 8000] [--market hs]
        # 仅建中盘池 + 抓 raw(westock)：profile/quote/finance；【不含分红，分红走 Wind】
  screen   [--win 10] [--mv 50] [--rev 20] [--raw raw目录] [--skip-dividend]
        # 单跑 Graham 筛选（需 raw/*.txt；带 --skip-dividend 可做第一遍）
  all      [--win 10] [--mv 50] [--rev 20] [--out 目录]
        # = pass1（建池+抓raw+初筛）；分红需 Wind，跑完会打印交接口令
  analyze  [选股结果MD路径]  [--out 目录] [--source auto|wind|public]
        # 已有 Graham 选股 MD → 分析 + 报告（无需 westock；Wind 可选）

标准流程（Graham 分红条依赖 Wind，westock 1.0.4 分红接口残，见 SKILL.md 坑 7）：
  pass1  →   AI 用 Wind MCP get_stock_events 拉幸存者 10 年分红 → wind_dividends.json
        →   wind-div  →  analyze <MD> --source auto  → 报告

关于 Wind MCP（重点 · 首选数据源）
-----------------------------------
  Wind 是【首选】数据源（你有 API 积分，优先从 Wind 抓）：
    - 分析阶段默认 --source auto：有 wind_cache/*.json 用 Wind（估值 PE/PB/股息率/ROE
      + 实时价/52周 均可由 Wind 供给），缺失或 Wind 未连则自动回退 westock/公开接口。
    - 直接 --source public 可强制只用公开接口。
    - 筛选阶段（fetch/screen）因 Graham 七条件需要**多年原始财报**（利润表/资产负债表/
      分红明细），Wind MCP 不擅长稳定吐这堆多年级明细，故仍走 westock；但 westock 已加固
      （批量 50/批 + 截断自动减半重试 + 清 \r 换行符），不再频繁救火。
  所以「对方没装 Wind MCP」仍可用（走公开接口兜底），但装了就优先 Wind。

依赖
----
  - 分析/报告：仅 Python3 + 本技能自带 tools/（零外部依赖）
  - 筛选 fetch：WorkBuddy 内置 westock-data / westock-tool（Node）
"""
import os, sys, json, re, shutil, glob, subprocess, datetime, argparse

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
    # 直接兜底：asar.unpacked 下的 builtin-skills（实测此路径最稳，避免 glob 漏匹配）
    asar = os.path.join(home, 'AppData', 'Local', 'Programs', 'WorkBuddy',
                        'resources', 'app.asar.unpacked', 'resources', 'builtin-skills')
    if os.path.isdir(asar) and asar not in builtin_dirs:
        builtin_dirs.append(asar)
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
    # （finance 子命令的特殊约定；profile/quote 则代码放最后即可）
    # 注意：不再抓 dividend —— westock 1.0.4 的 dividend 接口残（批量只回状态行、
    #   单只只回当年），拿不到 Graham 第4条要的 10 年分红史。分红史改由 Wind MCP
    #   提供：AI 用 get_stock_events 拉幸存者分红 → wind_dividends.json →
    #   scripts/build_div.py 生成 div.txt（见 wind-div 子命令）。
    jobs = [
        ('profile', ['profile'], 'pro.txt', False),
        ('quote', ['quote'], 'quo.txt', False),
        ('finance lrb', ['finance', '--type', 'lrb', '--num', '48'], 'fin_lrb.txt', True),
        ('finance zcfz', ['finance', '--type', 'zcfz', '--num', '48'], 'fin_zcfz.txt', True),
    ]
    # westock-data 单次调用输出有长度上限，大 chunk 会静默截断（batch 状态仍报 success，
    # 导致 div/zcfz 大面积缺失、Graham 筛选全军覆没）。
    # 默认 50/批；并对每批做覆盖率自检：若返回代码数 < 请求数 90%，自动减半重试该批，
    # 直到单只或成功。可用环境变量 WESTOCK_CHUNK 覆盖（建议 20~50）。
    chunk = int(os.environ.get('WESTOCK_CHUNK', '50'))

    def _westock_call(sub, batch, codes_first):
        if codes_first:
            cmd = [node, data_js] + sub[:1] + [','.join(batch)] + sub[1:]
        else:
            cmd = [node, data_js] + sub + [','.join(batch)]
        return run(cmd, capture=True, silent=True)

    def _coverage_ok(out, batch):
        if not (out and out.strip()):
            return False, 0
        got = len(set(re.findall(r'\b(?:sh|sz|bj)\d{6}\b', out)) & set(batch))
        return got >= len(batch) * 0.9, got

    for label, sub, fname, codes_first in jobs:
        path = os.path.join(raw_dir, fname)
        print(f'② 抓 {label} → {fname}（分块 {chunk}/批，截断自动减半重试）...')
        with open(path, 'w', encoding='utf-8') as fh:
            bi = 0
            for i in range(0, len(codes), chunk):
                batch = [c for c in codes[i:i + chunk] if c]
                if not batch:
                    continue
                bi += 1
                rc, out = _westock_call(sub, batch, codes_first)
                ok, got = _coverage_ok(out, batch)
                if not ok:
                    half = max(1, len(batch) // 2)
                    if half < len(batch):
                        print(f'   ⚠ 第 {bi} 批疑似截断/失败（请求 {len(batch)} 只，返回 {got} 只）→ 减半重试')
                        for j in range(0, len(batch), half):
                            sub_b = batch[j:j + half]
                            if not sub_b:
                                continue
                            rc2, out2 = _westock_call(sub, sub_b, codes_first)
                            ok2, got2 = _coverage_ok(out2, sub_b)
                            if ok2:
                                fh.write(out2 + '\n')
                            else:
                                print(f'   ⚠ 第 {bi} 批子批({len(sub_b)}只)仍缺失({got2}/{len(sub_b)})，跳过')
                        continue
                    print(f'   ⚠ 第 {bi} 批失败，跳过')
                    continue
                fh.write(out + '\n')
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
        print(f'❌ raw 数据不全：{raw} 下需有 pro.txt/quo.txt/fin_lrb.txt/fin_zcfz.txt')
        print('   先跑 fetch，或按 README 手动抓取。')
        sys.exit(1)
    skip_div = getattr(args, 'skip_dividend', False)
    # 第二遍（带分红）必须已有 div.txt（由 Wind 分红经 build_div.py 生成）
    if not skip_div and not os.path.exists(os.path.join(raw, 'div.txt')):
        print(f'❌ 第二遍筛选需要 div.txt，但未找到：{os.path.join(raw, "div.txt")}')
        print('   分红史来自 Wind：AI 先用 Wind MCP get_stock_events 拉幸存者分红 →')
        print('   wind_dividends.json，再跑 `wind-div`（内部调 build_div.py 生成 div.txt）。')
        sys.exit(1)
    work = args.out
    os.makedirs(work, exist_ok=True)
    cmd = [PY, GRAHAM, str(args.win), codes, raw, args.suffix or '',
           str(args.mv), str(args.rev)]
    if skip_div:
        cmd.append('--skip-dividend')
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


def cmd_pass1(a):
    """第一阶段：建中盘池 + 抓 raw + 第一遍初筛（跳过分红条）。"""
    if not run_preflight(need_westock=True, source='public'):
        sys.exit(1)
    print('▶ 第一阶段：建池 → 抓 raw → 第一遍初筛（跳分红条）')
    work = a.out
    os.makedirs(work, exist_ok=True)
    codes = os.path.join(work, 'codes.txt')
    raw = os.path.join(work, 'raw')
    fetch_universe(a.rev, codes, raw, 8000, 'hs')
    a.codes, a.raw = codes, raw
    a.skip_dividend = True
    md = run_screen(a)
    print(f'✅ 第一遍初筛完成：{md}')
    print('>>> 下一步（必须）：AI 用 Wind MCP get_stock_events 拉幸存者 10 年分红 →')
    print('    wind_dividends.json，再跑 `wind-div --raw %s`' % raw)
    print('>>> 然后：python run_pipeline.py analyze %s --source auto' % md)


def cmd_wind_div(a):
    """第二阶段：用 Wind 分红 JSON 生成 div.txt，再跑第二遍筛选（带分红条）。"""
    raw = a.raw or _default_data('raw')
    raw_abs = os.path.abspath(raw)
    # codes.txt 与 raw 同级（pass1 写在 <work>/codes.txt，raw 在 <work>/raw）
    a.codes = os.path.join(os.path.dirname(raw_abs), 'codes.txt')
    a.out = os.path.dirname(raw_abs)
    json_path = a.json
    if not os.path.exists(json_path):
        alt = os.path.join(raw, 'wind_dividends.json')
        if os.path.exists(alt):
            json_path = alt
        else:
            print(f'❌ 未找到 Wind 分红 JSON：{a.json}（也未在 {alt} 找到）')
            print('   AI 需先用 Wind MCP get_stock_events 拉幸存者年度每股派息，写成 wind_dividends.json。')
            sys.exit(1)
    # 1) Wind 分红 JSON → div.txt
    rc, _ = run([PY, os.path.join(SCRIPT_DIR, 'build_div.py'), json_path, '--raw', raw])
    if rc != 0:
        print('❌ build_div.py 生成 div.txt 失败，终止。')
        sys.exit(1)
    # 2) 第二遍筛选（带分红条）
    a.skip_dividend = False
    md = run_screen(a)
    print(f'✅ 第二遍筛选（带分红）完成：{md}')
    print('>>> 然后：python run_pipeline.py analyze %s --source auto' % md)


def cmd_all(a):
    # 因 Graham 第4条（10年分红）依赖 Wind MCP（westock 1.0.4 分红接口残），
    # 真正的全自动需 AI 介入拉 Wind 分红，故 all = 第一阶段(建池+抓raw+初筛) + 交接口令。
    if not run_preflight(need_westock=True, source='public'):
        sys.exit(1)
    print('▶ 流水线（第一阶段：建池 + 抓 raw + 第一遍初筛）')
    work = a.out
    os.makedirs(work, exist_ok=True)
    codes = os.path.join(work, 'codes.txt')
    raw = os.path.join(work, 'raw')
    fetch_universe(a.rev, codes, raw, 8000, 'hs')
    a.codes, a.raw = codes, raw
    a.skip_dividend = True
    md = run_screen(a)
    print(f'✅ 第一遍初筛完成：{md}')
    print('>>> 下一步（必须）：AI 用 Wind MCP get_stock_events 拉幸存者 10 年分红 → wind_dividends.json')
    print('    再跑：python run_pipeline.py wind-div --raw %s' % raw)
    print('>>> 然后：python run_pipeline.py analyze %s --source auto' % md)


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
    ps.add_argument('--win', type=int, default=10)  # 默认10年：Graham原教旨；2026-07-31用户确认回到10年
    ps.add_argument('--mv', type=float, default=50.0)
    ps.add_argument('--rev', type=float, default=20.0)
    ps.add_argument('--codes', default=None)
    ps.add_argument('--raw', default=None)
    ps.add_argument('--suffix', default='')
    ps.add_argument('--out', default=os.getcwd())
    ps.add_argument('--skip-dividend', action='store_true',
                    help='两遍法第一遍：跳过分红条（先缩窄候选，再补 Wind 分红做第二遍）')
    ps.set_defaults(func=cmd_screen)

    pf = sub.add_parser('fetch', help='用 westock 自动建池+抓 raw（需 westock+node；不含分红，分红走 Wind）')
    pf.add_argument('--rev', type=float, default=20.0)
    pf.add_argument('--codes', default=None)
    pf.add_argument('--raw', default=None)
    pf.add_argument('--limit', type=int, default=8000)
    pf.add_argument('--market', default='hs')
    pf.set_defaults(func=cmd_fetch)

    pp = sub.add_parser('pass1', help='第一阶段：建池+抓raw+第一遍初筛(跳分红)')
    pp.add_argument('--win', type=int, default=10)
    pp.add_argument('--mv', type=float, default=50.0)
    pp.add_argument('--rev', type=float, default=20.0)
    pp.add_argument('--out', default=os.getcwd())
    pp.add_argument('--suffix', default='')
    pp.set_defaults(func=cmd_pass1)

    pw = sub.add_parser('wind-div', help='第二阶段：Wind 分红JSON→div.txt→第二遍筛选(带分红)')
    pw.add_argument('--json', default='wind_dividends.json', help='Wind 分红 JSON（AI 用 get_stock_events 拉取）')
    pw.add_argument('--raw', default=None, help='raw 目录（含 quo.txt，写入 div.txt）')
    pw.add_argument('--win', type=int, default=10)
    pw.add_argument('--mv', type=float, default=50.0)
    pw.add_argument('--rev', type=float, default=20.0)
    pw.add_argument('--suffix', default='')
    pw.add_argument('--out', default=os.getcwd())
    pw.set_defaults(func=cmd_wind_div)

    pl = sub.add_parser('all', help='第一阶段全自动（建池+抓raw+初筛）；分红需 Wind，见交接口令')
    pl.add_argument('--win', type=int, default=10)  # 默认10年：Graham原教旨；2026-07-31用户确认回到10年
    pl.add_argument('--mv', type=float, default=50.0)
    pl.add_argument('--rev', type=float, default=20.0)
    pl.add_argument('--out', default=os.getcwd())
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
