"""快速检查 majors 采集进度"""
from dotenv import load_dotenv

load_dotenv()

import os
from supabase import create_client

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

uni_res = sb.table("universities").select("id,name").execute()
unis = uni_res.data or []

has_majors: set[str] = set()
offset = 0
while True:
    r = sb.table("majors").select("university_id").range(offset, offset + 999).execute()
    rows = r.data or []
    has_majors.update(x["university_id"] for x in rows)
    if len(rows) < 1000:
        break
    offset += 1000

maj_count = sb.table("majors").select("id", count="exact").limit(0).execute().count
missing = [u["name"] for u in unis if u["id"] not in has_majors]

print(f"院校总数: {len(unis)}")
print(f"专业记录: {maj_count}")
print(f"已有专业: {len(has_majors)} 所")
print(f"仍缺专业: {len(missing)} 所")
if missing:
    print("缺失院校:", "、".join(missing[:20]))
    if len(missing) > 20:
        print(f"  ... 另有 {len(missing) - 20} 所")
