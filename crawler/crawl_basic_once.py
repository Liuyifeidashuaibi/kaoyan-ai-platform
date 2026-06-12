#!/usr/bin/env python3
"""
crawl_basic_once.py — 一次性基础数据采集脚本
============================================================
采集内容（只需运行一次）：
  1. 院校基础信息（简介、地址、院校代码、研究生院链接）← Jina Reader + 通义千问
  2. 研招专业目录（专业代码、名称、学制、招生人数）    ← Jina Reader + 通义千问

完成后生成 .basic_done 标志文件，防止重复运行。
使用 --force 强制重跑所有院校，使用 --school 指定单所院校。

依赖：pip install aiohttp openai supabase python-dotenv
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

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
DONE_FLAG = _here / ".basic_done"

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

# ── Jina Reader（免 API Key，将任意网页转为 Markdown）────────────────────────
JINA_BASE = "https://r.jina.ai/"
MAX_CHARS = 12_000  # ~3000 tokens，控制成本


async def jina_fetch(session: ClientSession, url: str) -> Optional[str]:
    """通过 Jina Reader 获取网页 Markdown 内容"""
    try:
        async with session.get(
            f"{JINA_BASE}{url}",
            headers={"Accept": "text/plain", "X-Timeout": "25",
                     "User-Agent": "Mozilla/5.0 (compatible; KaoyanBot/2.0)"},
            timeout=aiohttp.ClientTimeout(total=45),
        ) as resp:
            if resp.status == 200:
                text = await resp.text()
                return text[:MAX_CHARS]
            log.debug("Jina %s → HTTP %s", url, resp.status)
    except Exception as exc:
        log.debug("Jina fetch error %s: %s", url, exc)
    return None


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


async def ask_qwen(prompt: str, max_retries: int = 3) -> Optional[str]:
    for attempt in range(max_retries):
        try:
            resp = await get_qwen().chat.completions.create(
                model="qwen-max",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.05,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            wait = 2 ** attempt
            if attempt < max_retries - 1:
                log.warning("Qwen retry %d/%d after %ds: %s", attempt + 1, max_retries, wait, exc)
                await asyncio.sleep(wait)
            else:
                log.error("Qwen failed after %d retries: %s", max_retries, exc)
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
你是考研招生信息提取专家。请从以下网页中提取研究生招生专业目录，输出 JSON 数组。

每个专业对象包含：
- college: 所属学院（字符串）
- code: 专业代码（6 位数字字符串，如"085401"）
- name: 专业名称
- degree_type: "学硕" 或 "专硕"
- study_mode: "全日制" 或 "非全日制"
- enrollment_count: 计划招生人数（整数，不确定填 null）

若页面无专业目录信息，返回 []。只输出 JSON 数组，不输出其他内容。

网页内容：
{content}"""


# ── Supabase 写入 ─────────────────────────────────────────────────────────────
class DB:
    def __init__(self) -> None:
        self._sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def upsert_university(self, row: dict) -> Optional[str]:
        try:
            res = self._sb.table("universities").upsert(row, on_conflict="name").execute()
            return (res.data or [{}])[0].get("id")
        except Exception as exc:
            log.error("upsert_university [%s]: %s", row.get("name"), exc)
            return None

    def get_university_id(self, name: str) -> Optional[str]:
        try:
            res = (self._sb.table("universities").select("id")
                   .eq("name", name).maybe_single().execute())
            return res.data["id"] if res.data else None
        except Exception:
            return None

    def upsert_majors(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        try:
            res = self._sb.table("majors").upsert(
                rows, on_conflict="university_id,code,degree_type,study_mode"
            ).execute()
            return len(res.data or [])
        except Exception as exc:
            log.error("upsert_majors: %s", exc)
            return 0


# ── 单所院校处理 ──────────────────────────────────────────────────────────────
_GRAD_PATHS = ["/yjszs/", "/yjsy/", "/graduate/", "/gs/", "/yjszs/zsxx/"]

_PROF_CODES = {"085", "125", "135", "045", "055", "065", "075", "095", "105"}


async def process_university(
    session: ClientSession,
    db: DB,
    uni: dict,
    sem: asyncio.Semaphore,
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
            uid = db.upsert_university(base_row)
            if not uid:
                uid = db.get_university_id(name)
            if not uid:
                stats["error"] = "cannot get university_id"
                return stats
            log.info("[%s] 基础记录 uid=%s…", name, uid[:8])

            # ── Step 2: Jina 抓取主页 → Qwen 提取 intro/address/graduate_url ──
            if website:
                hp_content = await jina_fetch(session, website)
                if hp_content:
                    ai_raw = await ask_qwen(BASIC_INFO_PROMPT.format(content=hp_content))
                    info = parse_json_safe(ai_raw) or {}
                    if isinstance(info, dict):
                        patch: dict = {"name": name}
                        if info.get("intro"):
                            patch["intro"] = str(info["intro"])[:500]
                        if info.get("address"):
                            patch["address"] = str(info["address"])[:200]
                        if info.get("school_code"):
                            patch["school_code"] = str(info["school_code"])[:10]
                        if info.get("graduate_url"):
                            patch["graduate_url"] = str(info["graduate_url"])[:300]
                        if len(patch) > 1:
                            db.upsert_university(patch)
                            log.info("[%s] 详细信息更新 (%s)", name,
                                     ", ".join(k for k in patch if k != "name"))

                        # ── Step 3: 抓取研招页面 → Qwen 提取专业目录 ──────────
                        grad_url = info.get("graduate_url") or ""
                        # 若 AI 未找到，尝试常见路径
                        grad_content: Optional[str] = None
                        if grad_url and grad_url.startswith("http"):
                            grad_content = await jina_fetch(session, grad_url)
                        if not grad_content:
                            for path in _GRAD_PATHS:
                                candidate = website.rstrip("/") + path
                                gc = await jina_fetch(session, candidate)
                                if gc and len(gc) > 300:
                                    grad_content = gc
                                    break

                        if grad_content:
                            maj_raw = await ask_qwen(
                                MAJOR_EXTRACT_PROMPT.format(content=grad_content)
                            )
                            majors_list = parse_json_safe(maj_raw)
                            if isinstance(majors_list, list) and majors_list:
                                rows = []
                                for m in majors_list:
                                    if not isinstance(m, dict):
                                        continue
                                    code = str(m.get("code", "")).strip()
                                    mname = str(m.get("name", "")).strip()
                                    if not code or not mname or len(code) < 6:
                                        continue
                                    raw_degree = str(m.get("degree_type", ""))
                                    degree = raw_degree if raw_degree in ("学硕", "专硕") else (
                                        "专硕" if code[:3] in _PROF_CODES else "学硕"
                                    )
                                    raw_mode = str(m.get("study_mode", ""))
                                    mode = raw_mode if raw_mode in ("全日制", "非全日制") else "全日制"
                                    rows.append({
                                        "university_id": uid,
                                        "college": str(m.get("college") or "未知学院")[:100],
                                        "name": mname[:100],
                                        "code": code[:10],
                                        "degree_type": degree,
                                        "study_mode": mode,
                                        "enrollment_count": (
                                            m.get("enrollment_count")
                                            if isinstance(m.get("enrollment_count"), int) else None
                                        ),
                                    })
                                if rows:
                                    cnt = db.upsert_majors(rows)
                                    stats["majors"] = cnt
                                    log.info("[%s] 写入专业 %d 个", name, cnt)

            stats["ok"] = True

        except Exception as exc:
            stats["error"] = str(exc)
            log.exception("[%s] 处理异常: %s", name, exc)

    return stats


# ── 主入口 ────────────────────────────────────────────────────────────────────
async def main(force: bool, only_school: Optional[str]) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("缺少 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    if not DASHSCOPE_KEY:
        log.error("缺少 DASHSCOPE_API_KEY")
        sys.exit(1)

    if DONE_FLAG.exists() and not force and not only_school:
        log.info(".basic_done 已存在，跳过（用 --force 强制重跑）")
        return

    unis = UNIVERSITIES
    if only_school:
        unis = [u for u in UNIVERSITIES if only_school in u["name"]]
        if not unis:
            log.error("未找到包含 '%s' 的院校", only_school)
            sys.exit(1)

    log.info("开始基础数据采集，共 %d 所院校", len(unis))
    start = time.time()
    db = DB()
    sem = asyncio.Semaphore(3)  # Qwen API 并发限制

    connector = TCPConnector(limit=20, ttl_dns_cache=300, enable_cleanup_closed=True)
    async with ClientSession(connector=connector) as session:
        results = await asyncio.gather(
            *[process_university(session, db, u, sem) for u in unis],
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

    if ok == len(unis) and not only_school:
        DONE_FLAG.write_text(f"completed at {datetime.now().isoformat()}\n", encoding="utf-8")
        log.info("已写入 %s，下次运行将自动跳过", DONE_FLAG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一次性基础数据爬虫（Jina + 通义千问）")
    parser.add_argument("--force",  action="store_true", help="强制重跑所有院校，忽略 .basic_done")
    parser.add_argument("--school", default=None,        help="只处理指定院校（模糊匹配名称）")
    args = parser.parse_args()
    asyncio.run(main(force=args.force, only_school=args.school))
