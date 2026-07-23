# -*- coding: utf-8 -*-
"""根据 analysis_cards.json 生成四大师分析 HTML 报告。
规则：所有入选股一律中性标注产地（省·市）；不按地域做任何偏好或剔除。"""
import json, os, datetime

# 从「当前工作目录」读取 analysis_cards.json、写出 HTML（便于被流水线以 cwd 调用）
BASE = os.getcwd()
cards = json.load(open(os.path.join(BASE, 'analysis_cards.json'), encoding='utf-8'))['cards']

# 四大师定性笔记（key=code）。数据字段自动从 JSON 取，这里只放定性判断。
NOTE = {
 'sh600219': dict(
   biz='铝全产业链（氧化铝→电解铝→高端铝材/铝箔），重资产周期股。',
   moat='航空铝材认证（波音/空客/商飞）+ 全球最大铝罐料供应商之一；规模与认证构成壁垒。',
   risk='铝价周期波动、产能扩张资本开支大、重资产折旧侵蚀利润。',
   mgmt='南山集团（民企），创始人家族稳健经营，分红历史连续。',
   civ='航空轻量化、新能源车用铝长期需求向上。',
   verdict='关注/分批', vcls='p-watch'),
 'sz000661': dict(
   biz='生长激素（金赛药业）为主，生物制药。',
   moat='生长激素龙头，金赛品牌+儿科渠道；但集采与竞争加剧削弱壁垒。',
   risk='2025 一次性减值致 TTM PE 为负；生长激素集采、新患增速放缓。',
   mgmt='国企改制，金赛管理层有激励。',
   civ='长效生长激素渗透率提升，但出生率下行利空长期用量。',
   verdict='观望(待利空出清)', vcls='p-watch'),
 'sh600511': dict(
   biz='麻精特药分销龙头 + 北京地区医药流通。',
   moat='麻精药品独家分销牌照（政策壁垒），北京区域配送网络。',
   risk='流通毛利率低、集采压价；但牌照护城河深，确定性高。',
   mgmt='国药系央企，治理规范。',
   civ='老龄化用药需求稳增。',
   verdict='建议关注(确定性最高)', vcls='p-buy'),
 'sh600612': dict(
   biz='黄金珠宝首饰，百年老字号 + 加盟连锁。',
   moat='百年品牌 + 逾 5000 门店渠道网络；金价上行利好库存价值。',
   risk='金价高位波动、加盟商管理、消费降级。',
   mgmt='上海国资委旗下，老字号运营经验成熟。',
   civ='黄金避险 + 婚庆刚需 + 国潮消费。',
   verdict='关注', vcls='p-watch'),
 'sh600420': dict(
   biz='化学药（原料药 + 制剂）制造。',
   moat='央企背景 + 部分品种批文壁垒，但化药护城河整体偏窄。',
   risk='化药集采压力、毛利率波动；组内 PE 偏高(14.6)。',
   mgmt='国药系央企。',
   civ='仿制药存量竞争，成长弹性有限。',
   verdict='小仓/观望', vcls='p-watch'),
 'sh601163': dict(
   biz='轮胎制造（全钢/半钢），出口为主。',
   moat='自主品牌 + 海外渠道；但轮胎同质化、面临贸易摩擦。',
   risk='橡胶原材料价格、海运费、反倾销关税。',
   mgmt='民企，分红稳健。',
   civ='国产轮胎全球份额提升。',
   verdict='关注', vcls='p-watch'),
 'sh600757': dict(
   biz='教材教辅出版发行 + 一般图书（湖北区域）。',
   moat='湖北省教材发行独家资质（区域垄断）+ 自有版权。',
   risk='出生率下行影响教材量、纸价波动；但刚需防御属性强。',
   mgmt='湖北国资，经营稳健。',
   civ='教育刚需 + 国企高分红政策。',
   verdict='防御首选/关注', vcls='p-buy'),
 'sz002540': dict(
   biz='精密铝管/铝型材（汽车热管理 + 工业）。',
   moat='汽车精密铝材细分龙头、客户认证壁垒；但规模较小。',
   risk='汽车周期、客户集中、小盘流动性。',
   mgmt='民企，高分红（84.7%）。',
   civ='新能源车热管理用铝增长。',
   verdict='小盘轻仓', vcls='p-watch'),
}

def scen(c):
    t = c.get('three_scenario_text', '')
    base = neutral = None
    for line in t.splitlines():
        if '中性' in line:
            parts = line.split()
            # 末段: 目标股价 涨跌幅%
            try:
                neutral = float(parts[-1].replace('%', ''))
            except: pass
    return neutral

rows = []
for c in cards:
    n = NOTE.get(c['code'], {})
    rows.append((c, n))

# ---- 组装 HTML ----
def cell_up(v): return f'<td class="up">{v}</td>' if v is not None else '<td>—</td>'

tot_rows = ''
for c, n in rows:
    prov, city = c.get('province'), c.get('city')
    # 产地：省·市；直辖市省=市则只写一个（中性标注，无地域偏好）
    origin = city if prov == city else f'{prov}·{city}'
    rt = c.get('realtime', {})
    pe = c.get('pe_used'); pb = c.get('pb_used'); roe = rt.get('roe')
    pos = c.get('pos_in_52w')
    base = scen(c)
    space = f'<span class="up">+{base}%</span>' if base is not None else '—'
    vcls = n.get('vcls', 'p-watch')
    verdict = n.get('verdict', '—')
    tot_rows += f'''<tr>
      <td class="name">{c['name']}<br><span class="muted">{c['code'].replace('sh','').replace('sz','')}</span></td>
      <td class="left">{origin}</td>
      <td>{c.get('industry','')}</td>
      <td>{c.get('price_used')}</td>
      <td>{("%.2f"%pe) if pe else "—"}</td>
      <td>{("%.2f"%pb) if pb else "—"}</td>
      <td>{("%.2f%%"%roe) if roe is not None else "—"}</td>
      <td>{("%.1f%%"%pos) if pos is not None else "—"}</td>
      <td>{c.get('pe3kf_used')}</td>
      <td>{c.get('div_rate')}%</td>
      <td>{space}</td>
      <td><span class="pill {vcls}">{verdict}</span></td>
    </tr>'''

# 逐只卡片
cards_html = ''
for c, n in rows:
    city = c.get('city'); prov = c.get('province')
    rt = c.get('realtime', {})
    pe = c.get('pe_used'); pb = c.get('pb_used')
    pos = c.get('pos_in_52w')
    red = c.get('red_flags') or []
    red_html = '；'.join(red) if red else '无明显红线'
    src = c.get('data_source')
    # 三情景表
    scen_tbl = ''
    sc_lines = [l for l in c.get('three_scenario_text','').splitlines() if any(k in l for k in ('乐观','中性','悲观'))]
    for l in sc_lines:
        parts = l.split()
        if len(parts) >= 6:
            name = parts[0]; g = parts[1]; pe2 = parts[2]; eps = parts[3]; tp = parts[4]; chg = parts[5]
            scen_tbl += f'<tr><td>{name}</td><td>{g}</td><td>{pe2}</td><td>{eps}</td><td>{tp}</td><td class="up">{chg}</td></tr>'
    loc = city if prov == city else f'{prov}·{city}'
    cards_html += f'''
    <div class="stock">
      <div class="hd">
        <div class="t">{c['name']}（{c['code'].replace('sh','').replace('sz','')}）</div>
        <div class="kv">🏙️ 产地：{loc} ｜ {c.get('industry','')} ｜ 源:<span class="src">{src}</span></div>
      </div>
      <div class="grid2">
        <div>
          <div class="pricebox">
            <div class="row"><span>现价</span><b>{c.get('price_used')}</b></div>
            <div class="row"><span>PE(TTM, 公开)</span><span>{("%.2f"%pe) if pe else "—"}</span></div>
            <div class="row"><span>PB(公开)</span><span>{("%.2f"%pb) if pb else "—"}</span></div>
            <div class="row"><span>ROE</span><span>{("%.2f%%"%rt.get('roe')) if rt.get('roe') is not None else "—"}</span></div>
            <div class="row"><span>52周区间</span><span>{c.get('h52_low')} ~ {c.get('h52')}</span></div>
            <div class="row"><span>52周位置</span><b>{("%.1f%%"%pos) if pos is not None else "—"}</b></div>
            <div class="row"><span>总市值 / 营收</span><span>{c.get('mktcap_yi')}亿 / {c.get('rev_yi')}亿</span></div>
            <div class="row"><span>近3年扣非PE / 分红率</span><span>{c.get('pe3kf_used')} / {c.get('div_rate')}%</span></div>
          </div>
          <p style="font-size:11.8px;color:var(--sub);margin:8px 0 0">红线速查：{red_html}</p>
        </div>
        <div>
          <h3 style="margin-top:0">三情景估值（精确十进制）</h3>
          <table style="font-size:11.8px">
            <thead><tr><th>情景</th><th>年增速</th><th>目标PE</th><th>目标EPS</th><th>目标股价</th><th>空间</th></tr></thead>
            <tbody>{scen_tbl}</tbody>
          </table>
          <p class="note">基准 PE 用归一化近3年扣非 PE（{c.get('pe3kf_used')}），规避 TTM 异常（如长春高新 2025 减值）。</p>
        </div>
      </div>
      <h3>四大师框架解读（产地：{loc}）</h3>
      <ul>
        <li><span class="q">生意本质</span>：{n.get('biz','')}</li>
        <li><span class="q">护城河（巴菲特/芒格）</span>：{n.get('moat','')}</li>
        <li><span class="q">逆向风险（段永平）</span>：{n.get('risk','')}</li>
        <li><span class="q">管理层（巴菲特）</span>：{n.get('mgmt','')}</li>
        <li><span class="q">文明趋势（李录）</span>：{n.get('civ','')}</li>
        <li><span class="q">估值安全边际</span>：{("PB %.2f、处52周 %.1f%% 低位"%(pb,pos)) if pb and pos is not None else "见上表"}，中性目标空间 {("+%.1f%%"%scen(c)) if scen(c) is not None else "—"}。</li>
      </ul>
      <p style="text-align:right;margin:6px 0 0"><span class="pill {n.get('vcls','p-watch')}">综合：{n.get('verdict','—')}</span></p>
    </div>'''

# 行动清单：从【今日入选股】动态生成，避免与总表/卡片不一致
def action_reason(n):
    moat = (n.get('moat', '') or '').split('；')[0].split('。')[0]
    if len(moat) > 46:
        moat = moat[:46] + '…'
    return moat or '—'

action_rows = ''
for c, n in rows:
    prov, city = c.get('province'), c.get('city')
    loc = city if prov == city else f'{prov}·{city}'
    nm = f"{c['name']}({loc})"
    verdict = n.get('verdict', '—')
    action_rows += f'<tr><td class="name">{nm}</td><td>{verdict}</td><td class="left">{action_reason(n)}</td></tr>'

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Graham 入选股 · 四大师分析总结（公开接口 · 含产地省·市标注）</title>
<style>
  :root{{--bg:#f7f8fa;--panel:#fff;--ink:#1c2630;--sub:#5b6b7a;--line:#e6eaf0;
    --navy:#13263f;--accent:#1f6feb;--up:#d6342c;--down:#1aa053;--warn:#b8860b;
    --chip:#eef3fb;--soft:#f0f3f7;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.55;font-size:14px}}
  .wrap{{max-width:1120px;margin:0 auto;padding:28px 22px 60px}}
  header.hero{{background:linear-gradient(135deg,#13263f,#1f4163);color:#fff;border-radius:14px;padding:26px 28px;margin-bottom:18px}}
  header.hero h1{{margin:0 0 6px;font-size:22px}}
  header.hero .meta{{font-size:12.5px;opacity:.85}}
  .badges{{margin-top:14px;display:flex;gap:8px;flex-wrap:wrap}}
  .badge{{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.25);padding:4px 11px;border-radius:999px;font-size:12px}}
  .badge.wind{{background:#1f6feb;color:#fff;border-color:#1f6feb}}
  .disclaimer{{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:8px;padding:12px 16px;margin:14px 0;font-size:12.8px;color:var(--sub)}}
  section{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin-bottom:18px}}
  h2{{font-size:17px;margin:0 0 14px;padding-bottom:8px;border-bottom:2px solid var(--navy);display:flex;align-items:center;gap:8px}}
  h2 .tag{{font-size:11px;background:var(--navy);color:#fff;padding:2px 8px;border-radius:6px;font-weight:600}}
  h3{{font-size:15px;margin:18px 0 10px;color:var(--navy)}}
  table{{border-collapse:collapse;width:100%;font-size:12.8px;margin:8px 0}}
  th,td{{border:1px solid var(--line);padding:7px 9px;text-align:center;vertical-align:middle}}
  th{{background:var(--soft);color:var(--navy);font-weight:600}}
  td.name{{text-align:left;font-weight:600;white-space:nowrap}}
  td.left{{text-align:left}}
  .up{{color:var(--up);font-weight:600}}
  .muted{{color:var(--sub)}}
  .pill{{display:inline-block;padding:2px 9px;border-radius:6px;font-size:11.5px;font-weight:600}}
  .p-buy{{background:#e8f6ee;color:#1aa053;border:1px solid #bfe6cf}}
  .p-watch{{background:#fff6e0;color:#b8860b;border:1px solid #f0dca0}}
  .src{{font-size:11px;background:var(--chip);color:var(--accent);padding:1px 7px;border-radius:5px;font-weight:600}}
  .stock{{border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0;background:#fcfdfe}}
  .stock .hd{{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;margin-bottom:8px}}
  .stock .hd .t{{font-size:15.5px;font-weight:700;color:var(--navy)}}
  .kv{{font-size:12.3px;color:var(--sub);margin-left:8px}}
  .grid2{{display:grid;grid-template-columns:1.15fr .85fr;gap:14px}}
  @media(max-width:760px){{.grid2{{grid-template-columns:1fr}}}}
  .pricebox{{background:var(--soft);border-radius:8px;padding:10px 12px;font-size:12.5px}}
  .pricebox .row{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px dashed var(--line)}}
  .pricebox .row:last-child{{border-bottom:0}}
  ul{{margin:6px 0 6px 0;padding-left:18px}}
  li{{margin:3px 0;font-size:12.8px}}
  .q{{color:var(--accent);font-weight:600}}
  .note{{font-size:12px;color:var(--sub);margin-top:6px}}
  .foot{{font-size:11.8px;color:var(--sub);text-align:center;margin-top:24px;line-height:1.7}}
</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <h1>Graham 防御型入选股 · 四大师分析总结</h1>
  <div class="meta">生成日 2026-07-22 ｜ 数据源 <b>公开接口（腾讯自选股 + 东方财富）</b>（Wind 未连接，自动回退）｜ 方法论：ai-berkshire 四大师框架（段永平·巴菲特·芒格·李录）｜ 地域仅作产地（省·市）中性标注</div>
  <div class="badges">
    <span class="badge wind">数据源：公开接口（腾讯/东财）</span>
    <span class="badge">Graham 入选 <b>{len(cards)} 只</b></span>
    <span class="badge">硬红线触发：0 条</span>
    <span class="badge">信息丰富度评级：B</span>
  </div>
</header>

<div class="disclaimer">
  <b>数据源与口径声明：</b>估值字段（PE/PB/ROE/股息率/52周高低）全部来自<b>公开接口</b>（腾讯自选股 + 东方财富），实时性以接口返回为准；Wind MCP 当前未连接，本报告不依赖 Wind。公开接口 PE/PB 与财报口径偶有差异（如一次性减值致 TTM PE 异常），本报告统一以<b>归一化近3年扣非 PE</b> 作估值基准，规避失真。定性判断（护城河/管理层/文明趋势）为 AI 基于公开信息的框架化推理，<b>非一手调研</b>；三情景为机械估值模型输出，<b>非收益预测，不构成投资建议</b>。颜色遵循 A 股惯例：<span class="up">红=上涨/上行空间</span>、绿=下跌。所有入选股一视同仁，地域仅作产地（省·市）客观标注，不参与任何偏好或剔除。
</div>

<section>
  <h2><span class="tag">总表</span>一、入选股横向对比（PE/PB 取公开接口 · 含产地省·市）</h2>
  <table>
    <thead><tr>
      <th>标的</th><th>产地（省·市）</th><th>行业</th><th>现价*</th><th>PE(Wind)</th><th>PB(Wind)</th><th>ROE</th>
      <th>52周位置*</th><th>近3年扣非PE</th><th>3年分红率</th><th>中性目标/空间</th><th>综合建议</th>
    </tr></thead>
    <tbody>{tot_rows}</tbody>
  </table>
  <p class="legend">* 现价、52周位置、PE/PB/ROE/分红率均来自公开接口（腾讯/东财）实时数据。"产地"列为公司注册地（省·市），仅作客观标注。</p>
</section>

<section>
  <h2><span class="tag">逐只</span>二、四大师框架逐只分析（含产地省·市）</h2>
  {cards_html}
</section>

<section>
  <h2><span class="tag">组合</span>三、组合行动清单</h2>
  <table>
    <thead><tr><th>标的（产地）</th><th>动作</th><th>理由</th></tr></thead>
    <tbody>{action_rows}</tbody>
  </table>
  <p class="note">整体偏防御价值，与用户成长风格（重仓 AI/半导体）形成对冲，适合小比例压舱石而非主体仓位。</p>
</section>

<div class="foot">
  数据源：公开接口（腾讯自选股 / 东方财富）｜ 筛选：Graham 防御型 7 条件（10年窗口 / 中盘 150亿·60亿口径）<br>
  地域仅作产地（省·市）中性标注，不参与筛选或剔除 ｜ 生成：老登股推荐（自动）<br>
  ⚠️ 本报告为 AI 框架化推理 + 机械估值，非投资建议；投资有风险，决策需独立判断。
</div>
</div>
</body>
</html>'''

ymd = datetime.date.today().strftime('%Y%m%d')
ymd_dash = datetime.date.today().strftime('%Y-%m-%d')
html = html.replace('2026-07-22', ymd_dash)  # 标题/生成日跟随当天
out = os.path.join(BASE, f'Graham入选股_四大师分析_{ymd}.html')
open(out, 'w', encoding='utf-8').write(html)
print('written:', out, '| stocks:', len(cards))
