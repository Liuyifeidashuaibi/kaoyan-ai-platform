"""TOP50 院校研究生院入口（Generic 发现器兜底）。"""

from __future__ import annotations

TOP50_GRADUATE_URLS: dict[str, str] = {
    "清华大学": "https://yz.tsinghua.edu.cn/",
    "北京大学": "https://admission.pku.edu.cn/",
    "上海交通大学": "https://yzb.sjtu.edu.cn/",
    "复旦大学": "https://gsao.fudan.edu.cn/",
    "浙江大学": "https://grs.zju.edu.cn/",
    "南京大学": "https://yzb.nju.edu.cn/",
    "中国科学技术大学": "https://gradschool.ustc.edu.cn/",
    "哈尔滨工业大学": "https://yzb.hit.edu.cn/",
    "武汉大学": "https://wdyz.whu.edu.cn/",
    "华中科技大学": "https://gszs.hust.edu.cn/",
    "西安交通大学": "https://yz.xjtu.edu.cn/",
    "同济大学": "https://yz.tongji.edu.cn/",
    "东南大学": "https://yzb.seu.edu.cn/",
    "中山大学": "https://graduate.sysu.edu.cn/",
    "北京航空航天大学": "https://yzb.buaa.edu.cn/",
    "北京理工大学": "https://grd.bit.edu.cn/",
    "电子科技大学": "https://yz.uestc.edu.cn/",
    "华南理工大学": "https://yz.scut.edu.cn/",
    "天津大学": "https://yzb.tju.edu.cn/",
    "南开大学": "https://yzb.nankai.edu.cn/",
    "中国人民大学": "https://pgs.ruc.edu.cn/",
    "北京师范大学": "https://yz.bnu.edu.cn/",
    "厦门大学": "https://zs.xmu.edu.cn/",
    "山东大学": "https://www.yz.sdu.edu.cn/",
    "四川大学": "https://yz.scu.edu.cn/",
    "吉林大学": "https://yjsy.jlu.edu.cn/",
    "中南大学": "https://yz.csu.edu.cn/",
    "大连理工大学": "https://gs.dlut.edu.cn/",
    "西北工业大学": "https://yzb.nwpu.edu.cn/",
    "重庆大学": "https://yz.cqu.edu.cn/",
    "湖南大学": "https://gra.hnu.edu.cn/",
    "华东师范大学": "https://yjszs.ecnu.edu.cn/",
    "中国农业大学": "https://yz.cau.edu.cn/",
    "东北大学": "https://yz.neu.edu.cn/",
    "兰州大学": "https://yz.lzu.edu.cn/",
    "中国海洋大学": "https://yz.ouc.edu.cn/",
    "中央民族大学": "https://mzxy.muc.edu.cn/",
    "西北农林科技大学": "https://yz.nwsuaf.edu.cn/",
    "国防科技大学": "https://yjsy.nudt.edu.cn/",
    "北京科技大学": "https://yzxc.ustb.edu.cn/",
    "北京邮电大学": "https://yzb.bupt.edu.cn/",
    "上海财经大学": "https://yjszs.shufe.edu.cn/",
    "对外经济贸易大学": "https://yz.uibe.edu.cn/",
    "中央财经大学": "https://gs.cufe.edu.cn/",
    "苏州大学": "https://yz.suda.edu.cn/",
    "南京航空航天大学": "https://www.graduate.nuaa.edu.cn/",
    "南京理工大学": "https://gs.njust.edu.cn/",
    "郑州大学": "https://yz.zzu.edu.cn/",
    "云南大学": "https://gra.ynu.edu.cn/",
    "新疆大学": "https://gs.xju.edu.cn/",
    "中国政法大学": "https://yz.cupl.edu.cn/",
}


def resolve_graduate_url(school: dict) -> str:
    """合并 DB / school_sources / TOP50 兜底。"""
    for key in ("graduate_url", "graduate_site"):
        url = (school.get(key) or "").strip()
        if url:
            return url
    name = school.get("name") or ""
    return TOP50_GRADUATE_URLS.get(name, "")
