# -*- coding: utf-8 -*-
"""
公司注册地(省·市)解析 —— 仅用于报告中的中性地理位置标注（产地 / 省·市）。

重要：本技能对所有入选股一视同仁，地域只作为客观信息标注，
不参与任何筛选、打分、偏好或剔除。
数据源: westock-data `profile` 的 regAddress(注册地) 字段。
"""

# 省份别名归一
PROV_ALIAS = {
    "内蒙古自治区": "内蒙古", "内蒙古": "内蒙古",
    "广西壮族自治区": "广西", "广西": "广西",
    "宁夏回族自治区": "宁夏", "宁夏": "宁夏",
    "新疆维吾尔自治区": "新疆", "新疆": "新疆",
    "西藏自治区": "西藏", "西藏": "西藏",
    "香港特别行政区": "香港", "澳门特别行政区": "澳门",
}

# 省份归一(用于从地址识别省名)
ALL_PROVS = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
    "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西", "海南",
    "四川", "重庆", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
    "香港", "澳门", "台湾",
]


def _norm_prov(raw):
    for a, p in PROV_ALIAS.items():
        if raw.startswith(a):
            return p
    # 去掉 省/市/自治区 后缀匹配
    for p in ALL_PROVS:
        if raw.startswith(p):
            return p
    return None


def parse_location(addr):
    """从注册地址解析 (province, city)。返回归一后的省名与市名(去'市')。

    返回 (None, None) 表示无法解析。直辖市省=市。
    """
    if not addr:
        return None, None
    addr = addr.strip()
    prov = _norm_prov(addr)
    if prov is None:
        return None, None
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
    city = cm.group(1) if cm else None
    return prov, city


if __name__ == "__main__":
    import sys
    tests = sys.argv[1:] or [
        "山东省烟台市龙口市东江镇前宋村",
        "吉林省长春市高新区海容酒店",
        "北京市东城区永定门西滨河路8号院",
        "上海市黄浦区南京西路190号",
        "湖北省武汉市武昌雄楚大街268号",
        "江苏省无锡市新吴区里河东路58号",
    ]
    for t in tests:
        prov, city = parse_location(t)
        print(f"省={prov} 市={city}  <- {t[:24]}")
