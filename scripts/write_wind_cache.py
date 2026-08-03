# -*- coding: utf-8 -*-
"""由 AI 在 Wind MCP 拉取估值后调用，把快照干净地写入 wind_cache/<code6>.json。

目的：避免手工写 JSON 导致字段形状错误（漏 source、roe 写成字符串、price 没置 null、
文件名前缀没剥掉导致 analyze_selected 读不到等）。集中唯一正确的写入口径。

用法（单只）：
  python scripts/write_wind_cache.py --code sh600511 --name 国药股份 \
      --pe 10.67 --pb 1.16 --div 2.81 --roe null

  # roe 当天 Wind 未计算时传 --roe null（脚本转成 None）；pe/pb/div 同理可传 null。
  # 实时价留给公开接口补齐，不要在这里填 price（恒为 null）。

用法（批量，避免一只只敲）：
  python scripts/write_wind_cache.py --batch payload.json
  # payload.json: [{"code":"sh600511","name":"国药股份","pe":10.67,"pb":1.16,
  #                  "div":2.81,"roe":null}, ...]
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


def write_one(code, name, pe, pb, div, roe):
    c = code6(code)
    if not re.fullmatch(r'\d{6}', c):
        print(f'ERROR: 解析出的代码 "{c}" 不是 6 位数字，请检查 --code（如 sh600511 / 600511.SH）',
              file=sys.stderr)
        sys.exit(3)
    payload = {
        'code': code,                                              # 尽量保留原始带前缀写法
        'name': name or '',
        'price': None,                                             # 实时价由公开接口补齐
        'pe': _num(pe),
        'pb': _num(pb),
        'div_yield': _num(div),
        'roe': _num(roe),
        'source': 'wind',
    }
    path = os.path.join(WIND_CACHE, f'{c}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'written: {path}  (pe={payload["pe"]} pb={payload["pb"]} '
          f'div={payload["div_yield"]} roe={payload["roe"]})')
    return path


def main():
    ap = argparse.ArgumentParser(description='写入 wind_cache/<code6>.json（Wind MCP 估值快照）')
    ap.add_argument('--code', help='代码，如 sh600511 / 600511.SH / 600511')
    ap.add_argument('--name', default='')
    ap.add_argument('--pe', default='null')
    ap.add_argument('--pb', default='null')
    ap.add_argument('--div', default='null', help='股息率（%）')
    ap.add_argument('--roe', default='null')
    ap.add_argument('--batch', help='批量 JSON 文件：[{code,name,pe,pb,div,roe}, ...]')
    args = ap.parse_args()

    if args.batch:
        rows = json.load(open(args.batch, encoding='utf-8'))
        for row in rows:
            write_one(row.get('code'), row.get('name'), row.get('pe'),
                      row.get('pb'), row.get('div'), row.get('roe'))
        return

    if not args.code:
        print('ERROR: 需提供 --code 或 --batch', file=sys.stderr)
        sys.exit(2)
    write_one(args.code, args.name, args.pe, args.pb, args.div, args.roe)


if __name__ == '__main__':
    main()
