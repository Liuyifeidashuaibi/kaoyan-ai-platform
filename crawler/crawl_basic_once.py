#!/usr/bin/env python3
"""
crawl_basic_once.py — 一次性基础数据采集脚本
============================================================
采集内容（只需运行一次）：
  1. 院校基础信息（简介、地址、院校代码、研究生院链接）← Jina Reader + 通义千问
  2. 研招专业目录（专业代码、名称、学位类型）          ← 研招网 API + 官网兜底

完成后生成 .basic_done 标志文件，防止重复运行。
使用 --force 强制重跑所有院校，使用 --school 指定单所院校。

依赖：pip install aiohttp openai supabase python-dotenv
"""

import argparse
import asyncio
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp import TCPConnector, ClientSession
from dotenv import load_dotenv
from openai import AsyncOpenAI
from supabase import create_client, Client

# ── 环境变量（优先 crawler/.env，其次项目根目录 .env）─────────────────────────
_here = Path(__file__).parent
load_dotenv(_here / ".env")
load_dotenv(_here.parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DASHSCOPE_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
CRAWLER_MODEL = os.environ.get("CRAWLER_PARSE_MODEL", "qwen-turbo")
CRAWLER_FALLBACK_MODEL = os.environ.get("CRAWLER_FALLBACK_MODEL", "qwen-plus")
DONE_FLAG = _here / ".basic_done"
SCHOOL_CODES_PATH = _here / "data" / "school_codes.json"
_qwen_disabled = False


def load_school_codes() -> dict[str, str]:
    try:
        data = json.loads(SCHOOL_CODES_PATH.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:
        log.warning("无法加载 school_codes.json: %s", exc)
        return {}


SCHOOL_CODES: dict[str, str] = load_school_codes()

# ── 日志 ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_here / "basic_crawl.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("basic")

# ── 完整 985 / 211 / 双一流 种子数据（第二轮双一流 147 所）───────────────────
UNIVERSITIES: list[dict] = [
    # ── 985 院校（39 所）──────────────────────────────────────────────────────
    {"name": "北京大学",       "province": "北京", "city": "北京", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.pku.edu.cn"},
    {"name": "清华大学",       "province": "北京", "city": "北京", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.tsinghua.edu.cn"},
    {"name": "中国人民大学",   "province": "北京", "city": "北京", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.ruc.edu.cn"},
    {"name": "北京航空航天大学","province": "北京", "city": "北京", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.buaa.edu.cn"},
    {"name": "北京理工大学",   "province": "北京", "city": "北京", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.bit.edu.cn"},
    {"name": "中国农业大学",   "province": "北京", "city": "北京", "school_type": "农林", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.cau.edu.cn"},
    {"name": "北京师范大学",   "province": "北京", "city": "北京", "school_type": "师范", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.bnu.edu.cn"},
    {"name": "中央民族大学",   "province": "北京", "city": "北京", "school_type": "民族", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.muc.edu.cn"},
    {"name": "南开大学",       "province": "天津", "city": "天津", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.nankai.edu.cn"},
    {"name": "天津大学",       "province": "天津", "city": "天津", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.tju.edu.cn"},
    {"name": "大连理工大学",   "province": "辽宁", "city": "大连", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.dlut.edu.cn"},
    {"name": "东北大学",       "province": "辽宁", "city": "沈阳", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.neu.edu.cn"},
    {"name": "吉林大学",       "province": "吉林", "city": "长春", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.jlu.edu.cn"},
    {"name": "哈尔滨工业大学", "province": "黑龙江","city": "哈尔滨","school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.hit.edu.cn"},
    {"name": "复旦大学",       "province": "上海", "city": "上海", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.fudan.edu.cn"},
    {"name": "同济大学",       "province": "上海", "city": "上海", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.tongji.edu.cn"},
    {"name": "上海交通大学",   "province": "上海", "city": "上海", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.sjtu.edu.cn"},
    {"name": "华东师范大学",   "province": "上海", "city": "上海", "school_type": "师范", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.ecnu.edu.cn"},
    {"name": "南京大学",       "province": "江苏", "city": "南京", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.nju.edu.cn"},
    {"name": "东南大学",       "province": "江苏", "city": "南京", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.seu.edu.cn"},
    {"name": "浙江大学",       "province": "浙江", "city": "杭州", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.zju.edu.cn"},
    {"name": "中国科学技术大学","province": "安徽", "city": "合肥", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.ustc.edu.cn"},
    {"name": "厦门大学",       "province": "福建", "city": "厦门", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.xmu.edu.cn"},
    {"name": "山东大学",       "province": "山东", "city": "济南", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.sdu.edu.cn"},
    {"name": "中国海洋大学",   "province": "山东", "city": "青岛", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.ouc.edu.cn"},
    {"name": "武汉大学",       "province": "湖北", "city": "武汉", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.whu.edu.cn"},
    {"name": "华中科技大学",   "province": "湖北", "city": "武汉", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.hust.edu.cn"},
    {"name": "湖南大学",       "province": "湖南", "city": "长沙", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.hnu.edu.cn"},
    {"name": "中南大学",       "province": "湖南", "city": "长沙", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.csu.edu.cn"},
    {"name": "国防科技大学",   "province": "湖南", "city": "长沙", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.nudt.edu.cn"},
    {"name": "中山大学",       "province": "广东", "city": "广州", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.sysu.edu.cn"},
    {"name": "华南理工大学",   "province": "广东", "city": "广州", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.scut.edu.cn"},
    {"name": "四川大学",       "province": "四川", "city": "成都", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.scu.edu.cn"},
    {"name": "电子科技大学",   "province": "四川", "city": "成都", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.uestc.edu.cn"},
    {"name": "重庆大学",       "province": "重庆", "city": "重庆", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.cqu.edu.cn"},
    {"name": "西安交通大学",   "province": "陕西", "city": "西安", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.xjtu.edu.cn"},
    {"name": "西北工业大学",   "province": "陕西", "city": "西安", "school_type": "理工", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.nwpu.edu.cn"},
    {"name": "西北农林科技大学","province": "陕西", "city": "杨凌", "school_type": "农林", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.nwafu.edu.cn"},
    {"name": "兰州大学",       "province": "甘肃", "city": "兰州", "school_type": "综合", "level_985": True,  "level_211": True,  "double_first_class": "一流大学A", "website": "https://www.lzu.edu.cn"},
    # ── 211（非 985）重点院校（69 所）────────────────────────────────────────
    # 北京
    {"name": "北京交通大学",   "province": "北京", "city": "北京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.bjtu.edu.cn"},
    {"name": "北京工业大学",   "province": "北京", "city": "北京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.bjut.edu.cn"},
    {"name": "北京科技大学",   "province": "北京", "city": "北京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.ustb.edu.cn"},
    {"name": "北京化工大学",   "province": "北京", "city": "北京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.buct.edu.cn"},
    {"name": "北京邮电大学",   "province": "北京", "city": "北京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.bupt.edu.cn"},
    {"name": "北京林业大学",   "province": "北京", "city": "北京", "school_type": "农林", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.bjfu.edu.cn"},
    {"name": "中国传媒大学",   "province": "北京", "city": "北京", "school_type": "语言", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cuc.edu.cn"},
    {"name": "中央财经大学",   "province": "北京", "city": "北京", "school_type": "财经", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cufe.edu.cn"},
    {"name": "对外经济贸易大学","province": "北京", "city": "北京", "school_type": "财经", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.uibe.edu.cn"},
    {"name": "北京外国语大学", "province": "北京", "city": "北京", "school_type": "语言", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.bfsu.edu.cn"},
    {"name": "中国政法大学",   "province": "北京", "city": "北京", "school_type": "政法", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cupl.edu.cn"},
    {"name": "北京中医药大学", "province": "北京", "city": "北京", "school_type": "医药", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.bucm.edu.cn"},
    {"name": "中国矿业大学（北京）","province": "北京","city": "北京","school_type": "理工","level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cumtb.edu.cn"},
    {"name": "中国地质大学（北京）","province": "北京","city": "北京","school_type": "理工","level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cugb.edu.cn"},
    {"name": "中国石油大学（北京）","province": "北京","city": "北京","school_type": "理工","level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cup.edu.cn"},
    {"name": "华北电力大学",   "province": "北京", "city": "北京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.ncepu.edu.cn"},
    # 河北
    {"name": "河北工业大学",   "province": "河北", "city": "天津", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.hebut.edu.cn"},
    # 山西
    {"name": "太原理工大学",   "province": "山西", "city": "太原", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.tyut.edu.cn"},
    # 内蒙古
    {"name": "内蒙古大学",     "province": "内蒙古","city": "呼和浩特","school_type": "综合","level_985": False, "level_211": True,  "double_first_class": "一流大学B", "website": "https://www.imu.edu.cn"},
    # 辽宁
    {"name": "辽宁大学",       "province": "辽宁", "city": "沈阳", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": None,        "website": "https://www.lnu.edu.cn"},
    {"name": "大连海事大学",   "province": "辽宁", "city": "大连", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.dlmu.edu.cn"},
    # 吉林
    {"name": "东北师范大学",   "province": "吉林", "city": "长春", "school_type": "师范", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.nenu.edu.cn"},
    {"name": "延边大学",       "province": "吉林", "city": "延吉", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": None,        "website": "https://www.ybu.edu.cn"},
    # 黑龙江
    {"name": "哈尔滨工程大学", "province": "黑龙江","city": "哈尔滨","school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.hrbeu.edu.cn"},
    {"name": "东北农业大学",   "province": "黑龙江","city": "哈尔滨","school_type": "农林", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.neau.edu.cn"},
    {"name": "东北林业大学",   "province": "黑龙江","city": "哈尔滨","school_type": "农林", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.nefu.edu.cn"},
    # 上海
    {"name": "上海财经大学",   "province": "上海", "city": "上海", "school_type": "财经", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.sufe.edu.cn"},
    {"name": "上海外国语大学", "province": "上海", "city": "上海", "school_type": "语言", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.shisu.edu.cn"},
    {"name": "华东理工大学",   "province": "上海", "city": "上海", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.ecust.edu.cn"},
    {"name": "东华大学",       "province": "上海", "city": "上海", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.dhu.edu.cn"},
    {"name": "上海大学",       "province": "上海", "city": "上海", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.shu.edu.cn"},
    {"name": "上海中医药大学", "province": "上海", "city": "上海", "school_type": "医药", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.shutcm.edu.cn"},
    # 江苏
    {"name": "苏州大学",       "province": "江苏", "city": "苏州", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.suda.edu.cn"},
    {"name": "南京航空航天大学","province": "江苏", "city": "南京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.nuaa.edu.cn"},
    {"name": "南京理工大学",   "province": "江苏", "city": "南京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.njust.edu.cn"},
    {"name": "中国矿业大学",   "province": "江苏", "city": "徐州", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cumt.edu.cn"},
    {"name": "河海大学",       "province": "江苏", "city": "南京", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.hhu.edu.cn"},
    {"name": "江南大学",       "province": "江苏", "city": "无锡", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.jiangnan.edu.cn"},
    {"name": "中国药科大学",   "province": "江苏", "city": "南京", "school_type": "医药", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cpu.edu.cn"},
    {"name": "南京农业大学",   "province": "江苏", "city": "南京", "school_type": "农林", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.njau.edu.cn"},
    {"name": "南京师范大学",   "province": "江苏", "city": "南京", "school_type": "师范", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.njnu.edu.cn"},
    # 安徽
    {"name": "合肥工业大学",   "province": "安徽", "city": "合肥", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.hfut.edu.cn"},
    {"name": "安徽大学",       "province": "安徽", "city": "合肥", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.ahu.edu.cn"},
    # 福建
    {"name": "福州大学",       "province": "福建", "city": "福州", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.fzu.edu.cn"},
    # 江西
    {"name": "南昌大学",       "province": "江西", "city": "南昌", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.ncu.edu.cn"},
    # 山东
    {"name": "中国石油大学（华东）","province": "山东","city": "青岛","school_type": "理工","level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.upc.edu.cn"},
    # 河南
    {"name": "郑州大学",       "province": "河南", "city": "郑州", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流大学B", "website": "https://www.zzu.edu.cn"},
    # 湖北
    {"name": "中国地质大学（武汉）","province": "湖北","city": "武汉","school_type": "理工","level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.cug.edu.cn"},
    {"name": "武汉理工大学",   "province": "湖北", "city": "武汉", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.whut.edu.cn"},
    {"name": "华中农业大学",   "province": "湖北", "city": "武汉", "school_type": "农林", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.hzau.edu.cn"},
    {"name": "华中师范大学",   "province": "湖北", "city": "武汉", "school_type": "师范", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.ccnu.edu.cn"},
    {"name": "中南财经政法大学","province": "湖北", "city": "武汉", "school_type": "财经", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.zuel.edu.cn"},
    # 湖南
    {"name": "湖南师范大学",   "province": "湖南", "city": "长沙", "school_type": "师范", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.hunnu.edu.cn"},
    # 广东
    {"name": "暨南大学",       "province": "广东", "city": "广州", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.jnu.edu.cn"},
    {"name": "华南师范大学",   "province": "广东", "city": "广州", "school_type": "师范", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.scnu.edu.cn"},
    # 广西
    {"name": "广西大学",       "province": "广西", "city": "南宁", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流大学B", "website": "https://www.gxu.edu.cn"},
    # 四川
    {"name": "西南交通大学",   "province": "四川", "city": "成都", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.swjtu.edu.cn"},
    {"name": "西南财经大学",   "province": "四川", "city": "成都", "school_type": "财经", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.swufe.edu.cn"},
    {"name": "四川农业大学",   "province": "四川", "city": "雅安", "school_type": "农林", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.sicau.edu.cn"},
    # 云南
    {"name": "云南大学",       "province": "云南", "city": "昆明", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流大学B", "website": "https://www.ynu.edu.cn"},
    # 贵州
    {"name": "贵州大学",       "province": "贵州", "city": "贵阳", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流大学B", "website": "https://www.gzu.edu.cn"},
    # 陕西
    {"name": "西北大学",       "province": "陕西", "city": "西安", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.nwu.edu.cn"},
    {"name": "西安电子科技大学","province": "陕西", "city": "西安", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.xidian.edu.cn"},
    {"name": "长安大学",       "province": "陕西", "city": "西安", "school_type": "理工", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.chd.edu.cn"},
    {"name": "陕西师范大学",   "province": "陕西", "city": "西安", "school_type": "师范", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.snnu.edu.cn"},
    # 海南
    {"name": "海南大学",       "province": "海南", "city": "海口", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流大学B", "website": "https://www.hainu.edu.cn"},
    # 宁夏
    {"name": "宁夏大学",       "province": "宁夏", "city": "银川", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流大学B", "website": "https://www.nxu.edu.cn"},
    # 新疆
    {"name": "新疆大学",       "province": "新疆", "city": "乌鲁木齐","school_type": "综合","level_985": False, "level_211": True,  "double_first_class": "一流大学B", "website": "https://www.xju.edu.cn"},
    {"name": "石河子大学",     "province": "新疆", "city": "石河子", "school_type": "综合","level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.shzu.edu.cn"},
    # ── 遗漏的 211 院校 ────────────────────────────────────────────────────────
    # 天津
    {"name": "天津医科大学",   "province": "天津", "city": "天津", "school_type": "医药", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.tmu.edu.cn"},
    {"name": "天津中医药大学", "province": "天津", "city": "天津", "school_type": "医药", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.tjutcm.edu.cn"},
    # 上海
    {"name": "上海体育大学",   "province": "上海", "city": "上海", "school_type": "体育", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.sus.edu.cn"},
    # 重庆
    {"name": "西南大学",       "province": "重庆", "city": "重庆", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.swu.edu.cn"},
    # 西藏
    {"name": "西藏大学",       "province": "西藏", "city": "拉萨", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.utibet.edu.cn"},
    # 青海
    {"name": "青海大学",       "province": "青海", "city": "西宁", "school_type": "综合", "level_985": False, "level_211": True,  "double_first_class": "一流学科",  "website": "https://www.qhu.edu.cn"},
    # ── 双一流专项（非 985 非 211，35 所新增）────────────────────────────────
    # 北京（公安/外交/体育/艺术类）
    {"name": "外交学院",       "province": "北京", "city": "北京", "school_type": "综合", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.cfau.edu.cn"},
    {"name": "中国人民公安大学","province": "北京", "city": "北京", "school_type": "政法", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.ppsuc.edu.cn"},
    {"name": "北京体育大学",   "province": "北京", "city": "北京", "school_type": "体育", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.bsu.edu.cn"},
    {"name": "北京协和医学院", "province": "北京", "city": "北京", "school_type": "医药", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.pumc.edu.cn"},
    {"name": "首都师范大学",   "province": "北京", "city": "北京", "school_type": "师范", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.cnu.edu.cn"},
    {"name": "中央音乐学院",   "province": "北京", "city": "北京", "school_type": "艺术", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.ccom.edu.cn"},
    {"name": "中国音乐学院",   "province": "北京", "city": "北京", "school_type": "艺术", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.ccmusic.edu.cn"},
    {"name": "中央美术学院",   "province": "北京", "city": "北京", "school_type": "艺术", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.cafa.edu.cn"},
    {"name": "中央戏剧学院",   "province": "北京", "city": "北京", "school_type": "艺术", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.chntheatre.edu.cn"},
    # 河北
    {"name": "燕山大学",       "province": "河北", "city": "秦皇岛","school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.ysu.edu.cn"},
    # 山西
    {"name": "山西大学",       "province": "山西", "city": "太原", "school_type": "综合", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.sxu.edu.cn"},
    # 上海
    {"name": "上海科技大学",   "province": "上海", "city": "上海", "school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.shanghaitech.edu.cn"},
    {"name": "上海音乐学院",   "province": "上海", "city": "上海", "school_type": "艺术", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.shcmusic.edu.cn"},
    {"name": "上海海洋大学",   "province": "上海", "city": "上海", "school_type": "农林", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.shou.edu.cn"},
    {"name": "上海戏剧学院",   "province": "上海", "city": "上海", "school_type": "艺术", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.sta.edu.cn"},
    # 浙江
    {"name": "中国美术学院",   "province": "浙江", "city": "杭州", "school_type": "艺术", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.caa.edu.cn"},
    {"name": "宁波大学",       "province": "浙江", "city": "宁波", "school_type": "综合", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.nbu.edu.cn"},
    # 江苏
    {"name": "南京医科大学",   "province": "江苏", "city": "南京", "school_type": "医药", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.njmu.edu.cn"},
    {"name": "南京邮电大学",   "province": "江苏", "city": "南京", "school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.njupt.edu.cn"},
    {"name": "南京林业大学",   "province": "江苏", "city": "南京", "school_type": "农林", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.njfu.edu.cn"},
    {"name": "南京信息工程大学","province": "江苏","city": "南京", "school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.nuist.edu.cn"},
    {"name": "南京中医药大学", "province": "江苏", "city": "南京", "school_type": "医药", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.njucm.edu.cn"},
    # 河南
    {"name": "河南大学",       "province": "河南", "city": "开封", "school_type": "综合", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.henu.edu.cn"},
    # 湖北
    {"name": "湖北大学",       "province": "湖北", "city": "武汉", "school_type": "综合", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.hubu.edu.cn"},
    # 湖南
    {"name": "湘潭大学",       "province": "湖南", "city": "湘潭", "school_type": "综合", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.xtu.edu.cn"},
    # 广东
    {"name": "南方科技大学",   "province": "广东", "city": "深圳", "school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.sustech.edu.cn"},
    {"name": "华南农业大学",   "province": "广东", "city": "广州", "school_type": "农林", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.scau.edu.cn"},
    {"name": "广州医科大学",   "province": "广东", "city": "广州", "school_type": "医药", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.gzhmu.edu.cn"},
    {"name": "汕头大学",       "province": "广东", "city": "汕头", "school_type": "综合", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.stu.edu.cn"},
    {"name": "广州中医药大学", "province": "广东", "city": "广州", "school_type": "医药", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.gzucm.edu.cn"},
    # 四川
    {"name": "成都理工大学",   "province": "四川", "city": "成都", "school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.cdut.edu.cn"},
    {"name": "西南石油大学",   "province": "四川", "city": "成都", "school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.swpu.edu.cn"},
    # 云南
    {"name": "昆明理工大学",   "province": "云南", "city": "昆明", "school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.kmust.edu.cn"},
    # 陕西
    {"name": "西安建筑科技大学","province": "陕西", "city": "西安", "school_type": "理工", "level_985": False, "level_211": False, "double_first_class": "一流学科",  "website": "https://www.xauat.edu.cn"},
]

# ── 网页抓取（Jina Reader + HTTP 回退）────────────────────────────────────────
JINA_BASE = "https://r.jina.ai/"
MAX_CHARS = 12_000  # ~3000 tokens，控制成本
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (compatible; KaoyanBot/2.0)",
]
_RETRY_STATUS = {429, 500, 502, 503, 504}


def is_error_page(text: str) -> bool:
    head = (text or "")[:400]
    return "404 Not Found" in head or "403 Forbidden" in head or "openresty" in head and len(text) < 500


async def jina_fetch(session: ClientSession, url: str) -> Optional[str]:
    """通过 Jina Reader 获取网页 Markdown 内容"""
    try:
        async with session.get(
            f"{JINA_BASE}{url}",
            headers={
                "Accept": "text/plain",
                "X-Timeout": "30",
                "User-Agent": random.choice(USER_AGENTS),
            },
            timeout=aiohttp.ClientTimeout(total=55),
        ) as resp:
            if resp.status == 200:
                text = await resp.text()
                if is_error_page(text):
                    return None
                return text[:MAX_CHARS]
            log.debug("Jina %s → HTTP %s", url, resp.status)
    except Exception as exc:
        log.debug("Jina fetch error %s: %s", url, exc)
    return None


async def http_get(session: ClientSession, url: str, retries: int = 2) -> Optional[str]:
    """直接 HTTP 抓取 HTML（Jina 失败时的回退）"""
    for attempt in range(retries):
        try:
            await asyncio.sleep(random.uniform(0.5, 1.5))
            async with session.get(
                url,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
                timeout=aiohttp.ClientTimeout(total=30),
                allow_redirects=True,
            ) as resp:
                if resp.status in _RETRY_STATUS:
                    await asyncio.sleep(2 ** attempt)
                    continue
                if resp.status == 200:
                    raw = await resp.text(errors="ignore")
                    # 粗略去标签，保留可读文本
                    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
                    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text).strip()
                    return text[:MAX_CHARS] if text else None
        except Exception as exc:
            log.debug("HTTP error %s: %s", url, exc)
    return None


async def fetch_page(session: ClientSession, url: str) -> Optional[str]:
    text = await jina_fetch(session, url)
    if text and len(text) >= 200:
        return text
    return await http_get(session, url)


# ── 通义千问（DashScope OpenAI 兼容接口）─────────────────────────────────────
_qwen: Optional[AsyncOpenAI] = None


def get_qwen() -> AsyncOpenAI:
    global _qwen
    if _qwen is None:
        _qwen = AsyncOpenAI(
            api_key=DASHSCOPE_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _qwen


def _is_qwen_quota_error(exc: Exception) -> bool:
    msg = str(exc)
    return "403" in msg or "FreeTierOnly" in msg or "quota" in msg.lower()


async def ask_qwen(prompt: str, max_retries: int = 3) -> Optional[str]:
    global _qwen_disabled
    if _qwen_disabled or not DASHSCOPE_KEY:
        return None
    models = [CRAWLER_MODEL]
    if CRAWLER_FALLBACK_MODEL and CRAWLER_FALLBACK_MODEL != CRAWLER_MODEL:
        models.append(CRAWLER_FALLBACK_MODEL)
    for model in models:
        for attempt in range(max_retries):
            try:
                resp = await get_qwen().chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=3000,
                    temperature=0.05,
                )
                return resp.choices[0].message.content
            except Exception as exc:
                if _is_qwen_quota_error(exc):
                    log.warning("模型 %s 额度不足，尝试备用", model)
                    break
                wait = 2 ** attempt
                if attempt < max_retries - 1:
                    log.warning("Qwen retry %d/%d after %ds: %s", attempt + 1, max_retries, wait, exc)
                    await asyncio.sleep(wait)
                else:
                    log.error("Qwen failed model=%s: %s", model, exc)
    _qwen_disabled = True
    log.warning("通义千问均不可用，后续将跳过 AI 步骤")
    return None


def parse_json_safe(text: Optional[str]) -> Optional[Any]:
    """从 AI 响应中安全提取 JSON（容错）"""
    if not text:
        return None
    text = text.strip()
    for candidate in [
        text,
        re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text) and
        re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text).group(1),
        re.search(r"\[[\s\S]*\]", text) and re.search(r"\[[\s\S]*\]", text).group(),
        re.search(r"\{[\s\S]*\}", text) and re.search(r"\{[\s\S]*\}", text).group(),
    ]:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


# ── Prompts ───────────────────────────────────────────────────────────────────
BASIC_INFO_PROMPT = """\
你是高校信息提取专家。请从以下网页内容中提取学校信息，严格输出 JSON 对象，不输出其他内容。

需要提取的字段：
- intro: 学校简介（150字以内，概括学校历史、特色、优势方向）
- address: 学校通讯地址（省市区街道）
- school_code: 教育部院校代码（5位数字字符串，如"10001"，找不到填 null）
- graduate_url: 研究生院/研招网完整 URL（如能找到链接则填写，否则 null）

无法提取的字段填 null，只输出 JSON，不输出其他内容。

网页内容：
{content}"""

MAJOR_EXTRACT_PROMPT = """\
你是考研招生信息提取专家。请从以下网页中提取硕士研究生招生专业目录，输出 JSON 数组。

每个专业对象包含：
- college: 所属学院（字符串，找不到填"未知学院"）
- code: 专业代码（6 位数字字符串，如"085401"、"081200"）
- name: 专业名称（不含代码）
- degree_type: "学硕" 或 "专硕"
- study_mode: "全日制" 或 "非全日制"（默认全日制）
- enrollment_count: 计划招生人数（整数，不确定填 null）

注意：
1. 招生章程、专业目录表、院系招生说明中的专业都要提取
2. 同一专业代码不同学院/方向可分别列出
3. 只提取硕士专业，忽略博士
4. 若页面确实无任何专业信息，返回 []

只输出 JSON 数组，不输出其他内容。

网页内容：
{content}"""

CATALOG_URL_PROMPT = """\
你是考研信息专家。从以下研究生院网页中，找出最可能包含「硕士研究生招生专业目录/招生简章」的链接。

输出 JSON 字符串数组（完整 URL，最多 8 个），按可能性从高到低排序。
优先含「专业目录」「招生简章」「硕士招生」「zszyml」「zyml」「zsjzjml」的链接。
只输出 JSON 数组，不输出其他内容。

网页内容：
{content}"""


# ── Supabase 写入 ─────────────────────────────────────────────────────────────
def _sb_retry(fn, label: str, retries: int = 4, base_delay: float = 2.0):
    """Supabase 写入重试（应对 SSL 断连 / 连接被重置）"""
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                delay = base_delay * (attempt + 1)
                log.warning("%s 失败，%ds 后重试 (%d/%d): %s", label, delay, attempt + 1, retries, exc)
                time.sleep(delay)
    log.error("%s: %s", label, last_exc)
    return None


class DB:
    def __init__(self) -> None:
        self._sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def upsert_university(self, row: dict) -> Optional[str]:
        res = _sb_retry(
            lambda: self._sb.table("universities").upsert(row, on_conflict="name").execute(),
            f"upsert_university [{row.get('name')}]",
        )
        if res is None:
            return None
        return (res.data or [{}])[0].get("id")

    def get_university_id(self, name: str) -> Optional[str]:
        try:
            res = (self._sb.table("universities").select("id")
                   .eq("name", name).maybe_single().execute())
            return res.data["id"] if res.data else None
        except Exception:
            return None

    def get_university_meta(self, name: str) -> dict:
        try:
            res = (self._sb.table("universities")
                   .select("id,graduate_url,website,school_code")
                   .eq("name", name).maybe_single().execute())
            return res.data or {}
        except Exception:
            return {}

    def upsert_majors(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        deduped: dict[tuple[str, str, str, str], dict] = {}
        for r in rows:
            key = (
                r["university_id"],
                r["code"],
                r["degree_type"],
                r["study_mode"],
            )
            prev = deduped.get(key)
            if not prev or len(r.get("name", "")) > len(prev.get("name", "")):
                deduped[key] = r
        payload = list(deduped.values())
        res = _sb_retry(
            lambda: self._sb.table("majors").upsert(
                payload, on_conflict="university_id,code,degree_type,study_mode"
            ).execute(),
            "upsert_majors",
        )
        if res is None:
            return 0
        return len(res.data or [])

    def get_names_without_majors(self) -> set[str]:
        """返回 majors 表中尚无记录的院校名称集合"""
        try:
            uni_res = self._sb.table("universities").select("id,name").execute()
            if not uni_res.data:
                return set()
            has_majors: set[str] = set()
            offset = 0
            page = 1000
            while True:
                major_res = (
                    self._sb.table("majors")
                    .select("university_id")
                    .range(offset, offset + page - 1)
                    .execute()
                )
                rows = major_res.data or []
                has_majors.update(r["university_id"] for r in rows)
                if len(rows) < page:
                    break
                offset += page
            return {
                u["name"] for u in uni_res.data
                if u["id"] not in has_majors
            }
        except Exception as exc:
            log.warning("get_names_without_majors: %s", exc)
            return set()


# ── 专业目录 URL 发现与解析 ───────────────────────────────────────────────────
_GRAD_PATH_SUFFIXES = [
    "/zsgz/sszs/zyml/",
    "/zsgz/sszs/zsjzjml/",
    "/zsxx/sszs/zszyml/",
    "/yjszs/zsxx/sszszyml/",
    "/yjszs/",
    "/yjsy/",
    "/graduate/",
    "/gs/",
    "/zsxx/sszs/",
]

_CATALOG_KEYWORDS = (
    "专业目录", "招生专业", "招生简章", "硕士招生", "硕士研究生",
    "招生章程", "目录", "zyml", "zszy", "zsjzj", "zsml", "sszs",
)

_MAJOR_PREFIXES = frozenset(
    f"{a}{b}" for a in "0123456789" for b in "123456789"
) | frozenset(("10", "11", "12", "13", "14", "15"))

_PROF_CODES = {"025", "035", "045", "055", "065", "075", "085", "095", "105", "115", "125", "135", "145"}


def normalize_major_code(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) >= 6:
        return digits[:6]
    return ""


def is_likely_major_code(code: str) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    if code[:2] not in _MAJOR_PREFIXES and code[:3] not in _PROF_CODES:
        return False
    # 排除常见 CMS 文章 ID（如 105271、107781）
    if code.startswith("10") and int(code[2:4]) >= 50:
        return False
    return True


_INVALID_MAJOR_RE = re.compile(
    r"电话|手机|@\d|https?://|\.com|!\[|IE|浏览器|验证码|温馨提示|招生办|联系老师|导师"
    r"|可接收|考生|本科毕业|浏览效果|建议使用|招生简章|专业目录|请点击",
    re.I,
)


def is_valid_major_name(name: str) -> bool:
    n = (name or "").strip()
    if not n or len(n) < 2 or len(n) > 35:
        return False
    if _INVALID_MAJOR_RE.search(n):
        return False
    if re.match(r"^电话[：:]", n):
        return False
    if re.match(r"^0\d{2,3}[-\s]?\d{7,}", n):
        return False
    if re.match(r"^!\[", n):
        return False
    if re.match(r"^[\u4e00-\u9fa5]{1,3}老师$", n):
        return False
    if re.search(r"[\u4e00-\u9fa5]{1,2}老师", n) and len(n) <= 6:
        return False
    chinese = len(re.findall(r"[\u4e00-\u9fa5]", n))
    if chinese < len(n) * 0.5:
        return False
    return True


def _is_likely_college_name(name: str) -> bool:
    return bool(re.search(r"学院|系|中心|部|研究所|研究院|实验室", name or ""))


_ARTICLE_TITLE_KEYS = ("招生章程", "招生简章", "专业目录", "硕士招生", "招生计划", "招生专业")


def discover_links_from_markdown(md: str, base_url: str) -> list[str]:
    urls: list[str] = []
    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", md):
        low = (title + href).lower()
        if any(k in title or k in low for k in _CATALOG_KEYWORDS):
            urls.append(href.split("?")[0])
    for href in re.findall(r"\((https?://[^\)]+\.(?:htm|html|shtml)[^\)]*)\)", md):
        low = href.lower()
        if any(k in low for k in ("zyml", "zszy", "zsjzj", "zsml", "sszs", "zsxx", "zsgz", "yjszs")):
            urls.append(href.split("?")[0])
    base = base_url.rstrip("/") + "/"
    for suffix in _GRAD_PATH_SUFFIXES:
        urls.append(urljoin(base, suffix.lstrip("/")))
    return _dedupe_urls(urls)


def discover_article_links(md: str) -> list[str]:
    """从列表页中发现招生章程/专业目录详情页链接（高价值）"""
    urls: list[str] = []
    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", md):
        if not any(k in title for k in _ARTICLE_TITLE_KEYS):
            continue
        if "博士" in title and "硕士" not in title:
            continue
        clean = href.split("?")[0]
        if clean.endswith((".htm", ".html", ".shtml")):
            urls.append(clean)
    return _dedupe_urls(urls)


def prioritize_urls(urls: list[str]) -> list[str]:
    """招生目录类 URL 优先抓取"""

    def rank(u: str) -> int:
        low = u.lower()
        score = 0
        for i, frag in enumerate((
            "zsjzjml", "zyml", "zszyml", "sszs", "/info/",
            "招生", "zsgz", "yjszs", "yz.chsi",
        )):
            if frag in low:
                score += 20 - i
        return score

    return sorted(urls, key=rank, reverse=True)


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if not u.startswith("http"):
            continue
        key = u.rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            out.append(u)
    return out


def guess_grad_subdomains(website: str) -> list[str]:
    """根据官网域名猜测研究生院子域名（如 www.whu.edu.cn → gs.whu.edu.cn）"""
    parsed = urlparse(website)
    host = parsed.netloc
    if not host or "." not in host:
        return []
    parts = host.split(".")
    base_domain = ".".join(parts[1:]) if parts[0] in ("www", "www2") else host
    scheme = parsed.scheme or "https"
    return [
        f"{scheme}://{prefix}.{base_domain}"
        for prefix in ("gs", "grs", "yjs", "graduate", "yz", "gsao", "admission")
    ]


def is_grad_portal_url(url: str) -> bool:
    """判断 URL 是否像研究生院官网，而非新闻/文章页"""
    if not url or not url.startswith("http"):
        return False
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if any(b in host for b in ("news.", "blog.", "media.", "xinwen", "xw.")):
        return False
    if re.search(r"/info/\d+/\d+\.htm", path):
        return False
    if any(p in host for p in ("gs.", "grs.", "yjs", "graduate", "gsao", "admission", "yz.")):
        return True
    return any(k in path for k in ("yjszs", "zsgz", "graduate", "sszs"))


def discover_grad_portal_url(md: str) -> Optional[str]:
    """从主页 Markdown 链接中识别研究生院官网"""
    ranked: list[tuple[int, str]] = []
    for title, href in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", md):
        if not href.startswith("http"):
            continue
        clean = href.split("?")[0].rstrip("/")
        if not is_grad_portal_url(clean):
            continue
        blob = title + href
        if not any(k in blob for k in ("研究生院", "研究生招生", "研究生部", "研招")):
            continue
        if "博士" in title and "硕士" not in title:
            continue
        score = 0
        host = urlparse(clean).netloc.lower()
        if "研究生院" in title:
            score += 10
        if any(p in host for p in ("gs.", "grs.", "gsao")):
            score += 15
        ranked.append((score, clean))
    if not ranked:
        return None
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


def build_grad_candidate_urls(
    website: str,
    grad_url: Optional[str],
    school_name: str,
    extra: Optional[list[str]] = None,
) -> list[str]:
    urls: list[str] = []
    if extra:
        urls.extend(extra)
    if grad_url and grad_url.startswith("http"):
        urls.append(grad_url.rstrip("/"))
    if website and website.startswith("http"):
        for guessed in guess_grad_subdomains(website):
            urls.append(guessed)
        base = website.rstrip("/")
        for suffix in _GRAD_PATH_SUFFIXES:
            urls.append(urljoin(base + "/", suffix.lstrip("/")))
    urls.append(
        f"https://yz.chsi.com.cn/sch/schInfo.do?searchType=1&keyword={school_name}"
    )
    return _dedupe_urls(urls)


def score_catalog_page(text: str) -> int:
    if not text or is_error_page(text) or len(text) < 200:
        return 0
    score = 0
    for kw, pts in (
        ("专业代码", 8), ("招生专业", 6), ("学科门类", 5), ("一级学科", 5),
        ("招生人数", 4), ("学制", 3), ("硕士研究生", 4), ("专业目录", 6),
        ("招生简章", 8), ("招生章程", 10), ("附表", 4), ("招生计划", 5),
    ):
        if kw in text:
            score += pts
    codes = re.findall(r"\b\d{6}\b", text)
    score += min(sum(1 for c in codes if is_likely_major_code(c)), 25)
    return score


def _subject_category_from_code(code: str) -> Optional[str]:
    prefix = re.sub(r"\D", "", code)[:2]
    for name, cat_code in (
        ("哲学", "01"), ("经济学", "02"), ("法学", "03"), ("教育学", "04"),
        ("文学", "05"), ("历史学", "06"), ("理学", "07"), ("工学", "08"),
        ("农学", "09"), ("医学", "10"), ("军事学", "11"), ("管理学", "12"),
        ("艺术学", "13"),
    ):
        if cat_code == prefix:
            return name
    return None


def majors_to_rows(majors_list: list, uid: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for m in majors_list:
        if not isinstance(m, dict):
            continue
        code = normalize_major_code(str(m.get("code", "")))
        mname = str(m.get("name", "")).strip()
        if not code or not mname or not is_likely_major_code(code):
            continue
        if not is_valid_major_name(mname):
            continue
        raw_degree = str(m.get("degree_type", ""))
        degree = raw_degree if raw_degree in ("学硕", "专硕") else (
            "专硕" if code[:3] in _PROF_CODES else "学硕"
        )
        raw_mode = str(m.get("study_mode", ""))
        mode = raw_mode if raw_mode in ("全日制", "非全日制") else "全日制"
        key = (code, degree, mode)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "university_id": uid,
            "college": str(m.get("college") or "")[:100],
            "name": mname[:100],
            "code": code,
            "degree_type": degree,
            "study_mode": mode,
            "subject_category": (
                str(m.get("subject_category") or "")[:50]
                or _subject_category_from_code(code)
            ),
            "first_discipline": (
                str(m.get("first_discipline") or "")[:100] or None
            ),
            "enrollment_count": (
                m.get("enrollment_count")
                if isinstance(m.get("enrollment_count"), int) else None
            ),
        })
    return rows


def regex_extract_majors(text: str) -> list[dict]:
    """AI 失败时，用正则从表格/列表文本中兜底提取"""
    found: list[dict] = []
    seen: set[str] = set()
    patterns = [
        re.compile(r"[\(（](\d{6})[\)）]\s*([^\s\(\[（\|,\n]{2,40})"),
        re.compile(r"(?<![/\d])(0[1-9]\d{4})(?!\d)\s+([^\d\n\|]{2,40})"),
        re.compile(r"(\d{6})\s*[|｜]\s*([^\|｜\n]{2,40})"),
    ]
    for pat in patterns:
        for code, name in pat.findall(text):
            code = normalize_major_code(code)
            name = re.sub(r"\s+", " ", name).strip(" ：:，,")
            if not is_likely_major_code(code) or len(name) < 2 or code in seen:
                continue
            seen.add(code)
            found.append({
                "college": "未知学院",
                "code": code,
                "name": name[:100],
                "degree_type": "专硕" if code[:3] in _PROF_CODES else "学硕",
                "study_mode": "全日制",
            })
    return found


async def _score_urls(
    session: ClientSession,
    urls: list[str],
    limit: int,
) -> list[tuple[int, str, str]]:
    scored: list[tuple[int, str, str]] = []
    for url in urls[:limit]:
        content = await fetch_page(session, url)
        if not content:
            continue
        score = score_catalog_page(content)
        if score > 0:
            scored.append((score, url, content))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


async def collect_majors(
    session: ClientSession,
    uid: str,
    name: str,
    website: str,
    grad_url: Optional[str],
) -> tuple[list[dict], str]:
    """抓取并解析专业目录，返回 (rows, debug_note)"""
    candidate_urls = prioritize_urls(
        build_grad_candidate_urls(website, grad_url, name)
    )
    article_urls: list[str] = []

    # 研究生院首页 → 发现列表页链接
    portal_bases: list[str] = []
    if grad_url:
        portal_bases.append(grad_url)
    if website:
        portal_bases.extend(guess_grad_subdomains(website))
    portal_bases = _dedupe_urls(portal_bases)

    portal_content: Optional[str] = None
    portal_base = ""
    for candidate in portal_bases[:3]:
        content = await fetch_page(session, candidate)
        if content and not is_error_page(content) and len(content) >= 200:
            portal_content = content
            portal_base = candidate
            grad_url = grad_url or candidate
            break

    if portal_content and portal_base:
        discovered = discover_links_from_markdown(portal_content, portal_base)
        article_urls.extend(discover_article_links(portal_content))
        candidate_urls = prioritize_urls(_dedupe_urls(discovered + candidate_urls))

        for list_url in discovered[:5]:
            if any(k in list_url for k in ("zsjzj", "zyml", "zszy", "sszs", "a20")):
                list_md = await fetch_page(session, list_url)
                if list_md:
                    article_urls.extend(discover_article_links(list_md))

        if len(discovered) < 4:
            url_raw = await ask_qwen(
                CATALOG_URL_PROMPT.format(content=portal_content[:8000])
            )
            url_list = parse_json_safe(url_raw)
            if isinstance(url_list, list):
                candidate_urls = prioritize_urls(_dedupe_urls(
                    [str(u) for u in url_list
                     if isinstance(u, str) and u.startswith("http")]
                    + candidate_urls
                ))

    # 招生章程详情页最优先
    candidate_urls = prioritize_urls(_dedupe_urls(article_urls + candidate_urls))
    fetch_limit = min(len(candidate_urls), 12)
    scored_pages = await _score_urls(session, candidate_urls, fetch_limit)

    # 若首轮无高分页，再抓一批招生章程详情
    if not scored_pages and article_urls:
        scored_pages = await _score_urls(session, article_urls, 6)

    if not scored_pages:
        note = f"未找到含专业目录特征的页面（尝试 {fetch_limit} 个 URL）"
        log.warning("[%s] %s", name, note)
        return [], note

    all_rows: list[dict] = []
    tried_ai = 0
    best_url = scored_pages[0][1]

    for score, url, content in scored_pages[:5]:
        if tried_ai >= 3 and all_rows:
            break
        maj_raw = await ask_qwen(MAJOR_EXTRACT_PROMPT.format(content=content))
        tried_ai += 1
        majors_list = parse_json_safe(maj_raw)
        if isinstance(majors_list, list) and majors_list:
            rows = majors_to_rows(majors_list, uid)
            if rows:
                log.info("[%s] AI 从 %s 提取 %d 个专业 (score=%d)",
                         name, url[-55:], len(rows), score)
                all_rows.extend(rows)

    if not all_rows:
        combined = "\n\n".join(c for _, _, c in scored_pages[:3])
        regex_majors = regex_extract_majors(combined)
        all_rows = majors_to_rows(regex_majors, uid)
        if all_rows:
            log.info("[%s] 正则兜底提取 %d 个专业 (from %s)",
                     name, len(all_rows), best_url[-55:])

    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for row in all_rows:
        key = (row["code"], row["degree_type"], row["study_mode"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    note = f"最佳页面 score={scored_pages[0][0]}, 候选={fetch_limit}"
    return deduped, note


# ── 研招网专业目录 API（yz.chsi.com.cn/zsml）──────────────────────────────────
CHSI_ZSML = "https://yz.chsi.com.cn/zsml"
_CHSI_MLDMS = [f"{i:02d}" for i in range(1, 15)]
_chsi_sem = asyncio.Semaphore(1)  # 研招网全局限流，避免并发触发「访问太频繁」


def _chsi_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": f"{CHSI_ZSML}/",
        "Accept": "application/json, text/plain, */*",
    }


async def _chsi_init(session: ClientSession) -> None:
    async with session.get(
        f"{CHSI_ZSML}/",
        headers=_chsi_headers(),
        timeout=aiohttp.ClientTimeout(total=20),
    ):
        pass


async def _chsi_query(
    session: ClientSession,
    dwdm: str,
    dwmc: str,
    mldm: str,
    start: int,
) -> Optional[dict]:
    params = {
        "dwdm": dwdm,
        "dwmc": dwmc,
        "mldm": mldm,
        "xxfs": "1",
        "start": str(start),
    }
    for attempt in range(3):
        try:
            async with session.get(
                f"{CHSI_ZSML}/rs/zys.do",
                params=params,
                headers=_chsi_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    await asyncio.sleep(2)
                    continue
                data = await resp.json(content_type=None)
                msg = data.get("msg")
                if isinstance(msg, str):
                    if "频繁" in msg:
                        await asyncio.sleep(3 * (attempt + 1))
                        continue
                    return None
                if isinstance(msg, dict) and msg.get("list"):
                    return msg
                return None
        except Exception as exc:
            log.debug("chsi %s mldm=%s: %s", dwmc, mldm, exc)
        await asyncio.sleep(1.5)
    return None


def _chsi_items_to_rows(items: list[dict], uid: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        code = normalize_major_code(str(item.get("zydm", "")))
        name = str(item.get("zymc", "")).strip()
        if not code or not name or not is_likely_major_code(code):
            continue
        if not is_valid_major_name(name):
            continue
        xwlx = str(item.get("xwlx", ""))
        degree = "专硕" if xwlx == "zyxw" else "学硕"
        mode = "全日制" if str(item.get("mxxfs", "1")) == "1" else "非全日制"
        key = (code, degree, mode)
        if key in seen:
            continue
        seen.add(key)
        yxsmc = str(item.get("yxsmc") or item.get("xymc") or "").strip()
        college = yxsmc[:100] if _is_likely_college_name(yxsmc) else ""
        first_disc = str(item.get("yjxkmc") or "").strip()[:100] or None
        subject_cat = str(item.get("mlmc") or "").strip()[:50] or None
        rows.append({
            "university_id": uid,
            "college": college,
            "name": name[:100],
            "code": code,
            "degree_type": degree,
            "study_mode": mode,
            "subject_category": subject_cat,
            "first_discipline": first_disc,
        })
    return rows


async def fetch_majors_from_chsi(
    session: ClientSession,
    uid: str,
    school_name: str,
    dwdm: str,
) -> list[dict]:
    """从研招网按门类拉取院校硕士专业目录（需教育部院校代码 5 位）"""
    code = re.sub(r"\D", "", dwdm)[:5]
    if len(code) < 5:
        return []

    async with _chsi_sem:
        return await _fetch_majors_from_chsi_locked(session, uid, school_name, code)


async def _fetch_majors_from_chsi_locked(
    session: ClientSession,
    uid: str,
    school_name: str,
    code: str,
) -> list[dict]:
    await _chsi_init(session)
    all_items: list[dict] = []

    for mldm in _CHSI_MLDMS:
        start = 0
        while True:
            msg = await _chsi_query(session, code, school_name, mldm, start)
            if not msg:
                break
            batch = msg.get("list") or []
            all_items.extend(batch)
            total_page = int(msg.get("totalPage") or 1)
            if start // 10 + 1 >= total_page:
                break
            start += 10
            await asyncio.sleep(1.0)
        await asyncio.sleep(1.2)

    rows = _chsi_items_to_rows(all_items, uid)
    if rows:
        log.info("[%s] 研招网共获取 %d 个专业 (dwdm=%s)", school_name, len(rows), code)
    return rows  # noqa: RET504 — locked helper


def resolve_school_code(
    name: str,
    uni: dict,
    existing: dict,
    info: Optional[dict] = None,
) -> str:
    for src in (
        (info or {}).get("school_code"),
        existing.get("school_code"),
        uni.get("school_code"),
        SCHOOL_CODES.get(name),
    ):
        code = re.sub(r"\D", "", str(src or ""))[:5]
        if len(code) >= 5:
            return code
    return ""


async def process_university(
    session: ClientSession,
    db: DB,
    uni: dict,
    sem: asyncio.Semaphore,
    majors_only: bool = False,
) -> dict:
    name = uni["name"]
    website = uni.get("website", "")
    stats = {"name": name, "ok": False, "majors": 0, "error": None}

    async with sem:
        try:
            # ── Step 1: 写入种子基础字段 ───────────────────────────────────────
            base_row = {k: uni[k] for k in
                        ("name", "province", "city", "school_type",
                         "level_985", "level_211", "double_first_class", "website")}
            existing = db.get_university_meta(name)
            uid = db.upsert_university(base_row) or existing.get("id")
            if not uid:
                uid = db.get_university_id(name)
            if not uid:
                stats["error"] = "cannot get university_id"
                return stats
            log.info("[%s] 基础记录 uid=%s…", name, uid[:8])

            seed_code = SCHOOL_CODES.get(name) or uni.get("school_code")
            if seed_code and not existing.get("school_code"):
                db.upsert_university({**base_row, "school_code": str(seed_code)[:10]})
                existing = {**existing, "school_code": str(seed_code)[:10]}

            raw_grad = existing.get("graduate_url") or ""
            grad_url = raw_grad if is_grad_portal_url(raw_grad) else ""
            info: dict = {}

            # ── Step 2: 抓取主页 → Qwen 提取 intro/address/graduate_url ────────
            if website and not majors_only:
                hp_content = await fetch_page(session, website)
                if hp_content:
                    if not grad_url:
                        portal = discover_grad_portal_url(hp_content)
                        if portal:
                            grad_url = portal
                            log.info("[%s] 从主页发现研究生院 %s", name, portal[:60])

                    ai_raw = await ask_qwen(BASIC_INFO_PROMPT.format(content=hp_content))
                    parsed = parse_json_safe(ai_raw)
                    if isinstance(parsed, dict):
                        info = parsed
                        patch: dict = {**base_row}
                        if info.get("intro"):
                            patch["intro"] = str(info["intro"])[:500]
                        if info.get("address"):
                            patch["address"] = str(info["address"])[:200]
                        if info.get("school_code"):
                            patch["school_code"] = str(info["school_code"])[:10]
                        ai_grad = str(info.get("graduate_url") or "")
                        if is_grad_portal_url(ai_grad):
                            patch["graduate_url"] = ai_grad[:300]
                            grad_url = ai_grad
                        elif grad_url and is_grad_portal_url(grad_url):
                            patch["graduate_url"] = grad_url[:300]
                        updated = [k for k in ("intro", "address", "school_code", "graduate_url")
                                   if patch.get(k) and patch.get(k) != existing.get(k)]
                        if updated:
                            db.upsert_university(patch)
                            log.info("[%s] 详细信息更新 (%s)", name, ", ".join(updated))

            # ── Step 3: 专业目录（研招网优先，官网兜底）────────────────────────
            school_code = resolve_school_code(name, uni, existing, info)
            rows: list[dict] = []

            if len(school_code) >= 5:
                log.info("[%s] 研招网专业采集 dwdm=%s", name, school_code)
                rows = await fetch_majors_from_chsi(
                    session, uid, name, school_code,
                )

            if not rows and not majors_only and (website or grad_url):
                log.info("[%s] 官网兜底采集 grad_url=%s",
                         name, (grad_url or website)[:60])
                rows, note = await collect_majors(
                    session, uid, name, website, grad_url or None,
                )
                if not rows:
                    log.warning("[%s] 未提取到专业 (%s)", name, note)

            chsi_count = len(rows)
            # 研招网通常只抓到每校约 90 条（分页受限），用 AI 多源补全官网目录
            if chsi_count <= 95 and (website or grad_url):
                log.info("[%s] 研招网 %d 个专业，启动 AI 多源补采", name, chsi_count)
                ai_rows, ai_note = await collect_majors(
                    session, uid, name, website, grad_url or None,
                )
                if ai_rows:
                    merged: dict[tuple[str, str, str], dict] = {}
                    for r in rows + ai_rows:
                        k = (r["code"], r["degree_type"], r["study_mode"])
                        prev = merged.get(k)
                        if not prev or len(r.get("name", "")) > len(prev.get("name", "")):
                            merged[k] = r
                    rows = list(merged.values())
                    log.info("[%s] 合并后共 %d 个专业 (研招网 %d + AI %d)",
                             name, len(rows), chsi_count, len(ai_rows))
                elif chsi_count == 0:
                    log.warning("[%s] AI 也未提取到专业 (%s)", name, ai_note)

            if rows:
                cnt = db.upsert_majors(rows)
                stats["majors"] = cnt
                log.info("[%s] 写入专业 %d 个", name, cnt)
            elif len(school_code) < 5:
                log.warning("[%s] 缺少 school_code，无法查询研招网专业", name)

            stats["ok"] = True

        except Exception as exc:
            stats["error"] = str(exc)
            log.exception("[%s] 处理异常: %s", name, exc)

    return stats


# ── 主入口 ────────────────────────────────────────────────────────────────────
async def main(
    force: bool,
    only_school: Optional[str],
    majors_only: bool,
    resume_missing: bool,
) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    if not majors_only and not DASHSCOPE_KEY:
        log.error("缺少 DASHSCOPE_API_KEY（专业补采请加 --majors-only）")
        sys.exit(1)

    if DONE_FLAG.exists() and not force and not only_school and not resume_missing:
        log.info(".basic_done 已存在，跳过（用 --force 或 --resume-missing）")
        return

    unis = UNIVERSITIES
    if only_school:
        unis = [u for u in UNIVERSITIES if only_school in u["name"]]
        if not unis:
            log.error("未找到包含 '%s' 的院校", only_school)
            sys.exit(1)

    db = DB()
    if resume_missing:
        missing = db.get_names_without_majors()
        unis = [u for u in unis if u["name"] in missing]
        log.info("续跑模式：%d 所院校尚无专业数据", len(unis))
        if not unis:
            log.info("所有院校均已有专业，无需续跑")
            return

    mode = "仅专业" if majors_only else "完整"
    log.info("开始基础数据采集（%s），共 %d 所院校", mode, len(unis))
    start = time.time()
    sem = asyncio.Semaphore(1 if majors_only else 2)

    connector = TCPConnector(limit=20, ttl_dns_cache=300, enable_cleanup_closed=True)
    async with ClientSession(connector=connector) as session:
        results = await asyncio.gather(
            *[process_university(session, db, u, sem, majors_only) for u in unis],
            return_exceptions=True,
        )

    ok = sum(1 for r in results if isinstance(r, dict) and r.get("ok"))
    total_majors = sum(r.get("majors", 0) for r in results if isinstance(r, dict))
    elapsed = time.time() - start

    log.info("=" * 60)
    log.info("完成 %d/%d  |  专业共写入 %d 个  |  耗时 %.1fs", ok, len(unis), total_majors, elapsed)

    failed = [r["name"] for r in results if isinstance(r, dict) and not r.get("ok")]
    if failed:
        log.warning("失败院校（%d 所）: %s", len(failed), "、".join(failed))

    if ok == len(unis) and not only_school and not resume_missing:
        DONE_FLAG.write_text(f"completed at {datetime.now().isoformat()}\n", encoding="utf-8")
        log.info("已写入 %s，下次运行将自动跳过", DONE_FLAG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一次性基础数据爬虫（研招网 + Jina + 通义千问）")
    parser.add_argument("--force", action="store_true", help="强制重跑所有院校，忽略 .basic_done")
    parser.add_argument("--school", default=None, help="只处理指定院校（模糊匹配名称）")
    parser.add_argument(
        "--majors-only", action="store_true",
        help="仅采集专业（走研招网，不调用通义千问）",
    )
    parser.add_argument(
        "--resume-missing", action="store_true",
        help="只处理 majors 表中尚无数据的院校",
    )
    args = parser.parse_args()
    asyncio.run(main(
        force=args.force,
        only_school=args.school,
        majors_only=args.majors_only,
        resume_missing=args.resume_missing,
    ))
