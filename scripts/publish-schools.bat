@echo off
REM 手动将 E:\Kaoyan\re 数据发布到网站（Supabase）
cd /d E:\Kaoyan\kaoyan-ai-platform
python crawler\sync_kaoyan_cn.py --import-only
if errorlevel 1 (
  echo 发布失败
  exit /b 1
)
echo 发布完成
