# -*- coding: utf-8 -*-
"""由 AI 在 Wind MCP 拉取估值/行情后调用，把快照干净地写入 wind_cache/<code6>.json。

目的：避免手工写 JSON 导致字段形状错误（漏 source、roe 写成字符串、price 没置 null、
文件名前缀没剥掉导致 analyze_selected 读不到等）。集中唯一正确的写入口径。

Wind 是【首选】数据源，可同时供给：
  - 估值基本面（get_stock_fundamentals）：PE/PB/股息率/ROE
  - 实时行情（get_stock_quote）：实时价 price / 52周高低 h52,h52_low / 总股本 shares_yi
  后者填了就无需再走公开接口；不填则留 null、由下游公开接口兜底。

用法（单只，估值+行情一次写全）：
  python scripts/write_wind_cache.py --code sh600511 --name 国药股份 \
      --pe 10.67 --pb 1.16 --div 2.81 --roe null \
      --price 30.15 --h52 34.5 --h52_low 24.1 --shares_yi 7.5

  # 任意字段缺失传 null（脚本转成 None）即可；不填 price/h52 等则留 null 由公开接口补。
  # 还可顺带写 --province/--city（注册地省·市），下游 westock profile 偶发取不到时作为兜底标注。

用法（批量，避免一只只敲）：
  python scripts/write_wind_cache.py --batch payload.json
  # payload.json: [{"code":"sh600511","name":"国药股份","pe":10.67,"pb":1.16,
  #                 "div":2.81,"roe":null,
  #                 "price":30.15,"h52":34.5,"h52_low":24.1,"shares_yi":7.5,
  #                 "province":"上海","city":"上海"}, ...]
"""
import argparse, json, os, re, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WIND_CACHE = os.path.join(os.path.dirname(SCRIPT_DIR), 'wind_cache')
os.makedirs(WIND_CACHE, exist_ok=True)


def _num(v):
    """把任意来源的值规整成 float 或 None（null/空/nan 一律 None）。"""
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ('', 'null', 'none', 'nan', 'none'):
        return None
    try:
        return float(s)
    except Exception:
        return None


def code6(sym):
    """与 analyze_selected.code6 完全一致：剥掉 sh/sz/bj 前缀，返回 6 位代码。"""
    return re.sub(r'^(sh|sz|bj)', '', str(sym).strip().lower())


def write_one(code, name, pe, pb, div, roe, price=None, h52=None, h52_low=None, shares_yi=None,
              province=None, city=None):
    c = code6(code)
    if not re.fullmatch(r'\d{6}', c):
        print(f'ERROR: 解析出的代码 "{c}" 不是 6 位数字，请检查 --code（如 sh600511 / 600511.SH）',
              file=sys.stderr)
        sys.exit(3)
    payload = {
        'code': code,                                              # 尽量保留原始带前缀写法
        'name': name or '',
        'price': _num(price),                                      # 实时价：Wind quote 可供给，否则留 null 由公开接口补
        'pe': _num(pe),
        'pb': _num(pb),
        'div_yield': _num(div),
        'roe': _num(roe),
        'h52': _num(h52),
        'h52_low': _num(h52_low),
        'shares_yi': _num(shares_yi),
        'province': province or None,                              # 注册地省·市（中性标注用，westock profile 兜底）
        'city': city or None,
        'source': 'wind',
    }
    path = os.path.join(WIND_CACHE, f'{c}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'written: {path}  (pe={payload["pe"]} pb={payload["pb"]} '
          f'div={payload["div_yield"]} roe={payload["roe"]} '
          f'price={payload["price"]} 52w=[{payload["h52_low"]},{payload["h52"]}])')
    return path


def main():
    ap = argparse.ArgumentParser(description='写入 wind_cache/<code6>.json（Wind MCP 估值快照）')
    ap.add_argument('--code', help='代码，如 sh600511 / 600511.SH / 600511')
    ap.add_argument('--name', default='')
    ap.add_argument('--pe', default='null')
    ap.add_argument('--pb', default='null')
    ap.add_argument('--div', default='null', help='股息率（%）')
    ap.add_argument('--roe', default='null')
    ap.add_argument('--price', default='null', help='实时价（元）；Wind quote 可供给，默认 null 由公开接口补')
    ap.add_argument('--h52', default='null', help='52周最高价（元）')
    ap.add_argument('--h52_low', default='null', help='52周最低价（元）')
    ap.add_argument('--shares_yi', default='null', help='总股本（亿股）')
    ap.add_argument('--province', default=None, help='注册地省份（中性标注，westock profile 兜底用）')
    ap.add_argument('--city', default=None, help='注册地城市（中性标注，westock profile 兜底用）')
    ap.add_argument('--batch', help='批量 JSON 文件：[{code,name,pe,pb,div,roe,price,h52,h52_low,shares_yi,province,city}, ...]')
    args = ap.parse_args()

    if args.batch:
        rows = json.load(open(args.batch, encoding='utf-8'))
        for row in rows:
            write_one(row.get('code'), row.get('name'), row.get('pe'),
                      row.get('pb'), row.get('div'), row.get('roe'),
                      price=row.get('price'), h52=row.get('h52'),
                      h52_low=row.get('h52_low'), shares_yi=row.get('shares_yi'),
                      province=row.get('province'), city=row.get('city'))
        return

    if not args.code:
        print('ERROR: 需提供 --code 或 --batch', file=sys.stderr)
        sys.exit(2)
    write_one(args.code, args.name, args.pe, args.pb, args.div, args.roe,
              price=args.price, h52=args.h52, h52_low=args.h52_low, shares_yi=args.shares_yi,
              province=args.province, city=args.city)


if __name__ == '__main__':
    main()
