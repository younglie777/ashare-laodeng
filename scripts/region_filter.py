# -*- coding: utf-8 -*-
"""
地域筛选模块 (北方非省会/非前二城市剔除)
规则 (用户 2026-07-22 定):
  - 北方省份: 只保留【省会】+【全省经济前二城市】, 其余北方城市一律剔除。
  - 南方省份: 全部保留, 不做城市限制。
  - 北方企业若通过筛选: 打上 is_north 标记, 供下游特别标注。
数据源: westock-data `profile` 的 regAddress(注册地) 字段。
"""

# 北方省份 -> 允许保留的城市白名单 (省会 + 经济前二)。
# 直辖市 北京/天津 整体保留。
NORTH_KEEP = {
    "北京": {"北京"},
    "天津": {"天津"},
    "河北": {"石家庄", "唐山"},
    "山西": {"太原", "长治"},
    "内蒙古": {"呼和浩特", "鄂尔多斯", "包头"},
    "辽宁": {"沈阳", "大连"},
    "吉林": {"长春", "吉林"},
    "黑龙江": {"哈尔滨", "大庆"},
    "河南": {"郑州", "洛阳"},
    "陕西": {"西安", "榆林"},
    "甘肃": {"兰州", "庆阳"},
    "青海": {"西宁", "海东"},
    "宁夏": {"银川", "石嘴山"},
    "新疆": {"乌鲁木齐", "昌吉"},
}

# 北方省份整体保留 (用户 2026-07-22 追加: 山东为沿海省份, 全省不按"只留省会/前二"剔除)。
NORTH_FULL = {"山东"}

# 南方省/直辖市/特别行政区 (全留)
SOUTH = {
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "湖北", "湖南",
    "广东", "广西", "海南", "四川", "重庆", "贵州", "云南", "西藏",
    "香港", "澳门", "台湾",
}

# 省份别名归一
PROV_ALIAS = {
    "内蒙古自治区": "内蒙古", "内蒙古": "内蒙古",
    "广西壮族自治区": "广西", "广西": "广西",
    "宁夏回族自治区": "宁夏", "宁夏": "宁夏",
    "新疆维吾尔自治区": "新疆", "新疆": "新疆",
    "西藏自治区": "西藏", "西藏": "西藏",
    "香港特别行政区": "香港", "澳门特别行政区": "澳门",
}

ALL_PROVS = list(NORTH_KEEP.keys()) + list(NORTH_FULL) + list(SOUTH)


def _norm_prov(raw):
    for a, p in PROV_ALIAS.items():
        if raw.startswith(a):
            return p
    # 去掉 省/市/自治区 后缀匹配
    for p in ALL_PROVS:
        if raw.startswith(p):
            return p
    return None


def parse_addr(addr):
    """从注册地址解析 (province, city)。返回归一后的省名与市名(去'市')。"""
    if not addr:
        return None, None
    addr = addr.strip()
    prov = _norm_prov(addr)
    city = None
    # 直辖市: 省即市
    if prov in ("北京", "天津", "上海", "重庆", "香港", "澳门"):
        return prov, prov
    # 提取"XX市"
    import re
    # 先切掉省名部分
    rest = addr
    m = re.search(r"(省|自治区|特别行政区)", addr)
    if m:
        rest = addr[m.end():]
    cm = re.search(r"([\u4e00-\u9fa5]{2,4}?)市", rest)
    if cm:
        city = cm.group(1)
    return prov, city


def classify(addr):
    """
    返回 dict:
      province, city, region('north'/'south'/'unknown'),
      is_north(bool), keep(bool), reason(str)
    """
    prov, city = parse_addr(addr)
    if prov is None:
        return {"province": None, "city": city, "region": "unknown",
                "is_north": False, "keep": True,
                "reason": "地址无法解析省份, 默认保留(待人工核)"}
    if prov in SOUTH:
        return {"province": prov, "city": city, "region": "south",
                "is_north": False, "keep": True, "reason": "南方, 全留"}
    # 北方整体保留省份 (如山东沿海)
    if prov in NORTH_FULL:
        return {"province": prov, "city": city, "region": "north",
                "is_north": True, "keep": True,
                "reason": f"北方[{prov}] 整体保留省份(沿海), 保留(需标注)"}
    # 北方其余省份: 仅省会/前二城市保留
    whitelist = NORTH_KEEP.get(prov, set())
    keep = (city in whitelist) if city else False
    if keep:
        reason = f"北方[{prov}] 省会/前二城市[{city}], 保留(需标注)"
    else:
        reason = f"北方[{prov}] 非省会/前二[{city or '未知市'}], 剔除"
    return {"province": prov, "city": city, "region": "north",
            "is_north": True, "keep": keep, "reason": reason}


if __name__ == "__main__":
    import sys
    tests = sys.argv[1:] or [
        "山东省烟台市龙口市东江镇前宋村",
        "山东省威海市青岛中路56号",
        "吉林省长春市高新区海容酒店",
        "北京市东城区永定门西滨河路8号院",
        "上海市黄浦区南京西路190号",
        "湖北省武汉市武昌雄楚大街268号",
        "江苏省无锡市新吴区里河东路58号",
    ]
    for t in tests:
        r = classify(t)
        flag = "🚩北方" if r["is_north"] and r["keep"] else ("❌剔除" if not r["keep"] else "✅")
        print(f"{flag}  {t[:20]:22} -> 省={r['province']} 市={r['city']} | {r['reason']}")
