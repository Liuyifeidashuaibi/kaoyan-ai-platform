# 部署指南 — 考研 AI 平台

Vercel 只托管 **Next.js 前端**。AI 聊天与错题本依赖 **FastAPI 后端**（千问 API），需单独部署。

## 架构

```
浏览器 → Vercel (Next.js) → 代理 /api/chat、/api/wrong-questions → Render/Railway (FastAPI)
         ↓
      Supabase 登录
```

## 一、部署后端（Render 推荐）

1. 将代码推送到 GitHub
2. 打开 [Render](https://render.com) → **New Blueprint** → 选择本仓库（使用根目录 `render.yaml`）
3. 在 Render 环境变量中设置：
   - `DASHSCOPE_API_KEY` = 你的千问 API Key
   - `PUBLIC_BASE_URL` = `https://你的-render-服务.onrender.com`（**图片问答必配**，供 qwen2.5-vl 拉取 `/uploads` 图片）
   - `LLM_MODEL` = `qwen-max-latest`（默认已在 render.yaml）
   - `VL_MODEL` = `qwen2.5-vl-72b-instruct`（预算不足可改为 `qwen2.5-vl-7b-instruct`）
   - `CORS_ORIGINS` = `https://kaoyan-ai-platform.vercel.app,http://localhost:3000`
4. 部署完成后记下 URL，例如 `https://kaoyan-ai-api.onrender.com`

本地测试后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 二、配置 Vercel 环境变量

在 [Vercel 项目 Settings → Environment Variables](https://vercel.com) 添加：

| 变量 | 值 |
|------|-----|
| `BACKEND_URL` | `https://你的-render-服务.onrender.com` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |
| `DASHSCOPE_API_KEY` | 仅后端需要；Vercel 可不填 |

可选：若 SSE 流式在代理下超时，可额外设置  
`NEXT_PUBLIC_API_URL=https://你的-render-服务.onrender.com`（浏览器直连后端）。

## 三、推送前端代码

确保以下目录已提交并 push 到 GitHub，Vercel 会自动重新部署：

- `src/components/chat/`
- `src/components/wrong-questions/`
- `src/lib/api/`
- `backend/`
- `next.config.ts`（API 代理）

## 四、验证

1. 打开 `https://kaoyan-ai-platform.vercel.app`
2. 登录后进入 **AI 聊天** / **错题本**
3. 检查 `https://你的域名/api/backend-health` 应返回 `success: true`

本地开发：先启动后端 `uvicorn`，再 `npm run dev`，访问 http://localhost:3000

---

## 本地后端 + Cloudflare Tunnel（Vercel 连本机）

适合：**前端在 Vercel，后端跑在自己电脑上**，通过 Cloudflare 把 `localhost:8000` 暴露为固定 HTTPS 域名。

### 架构

```
浏览器 → Vercel (Next.js)
              ↓ 代理 /api/*
         https://api.你的域名.com (Cloudflare Tunnel)
              ↓
         本机 FastAPI :8000
```

### 一、安装 cloudflared（Windows）

```powershell
winget install --id Cloudflare.cloudflared
```

或从 [Cloudflare 下载页](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) 安装。

### 二、创建固定隧道（只需做一次）

前提：有一个已接入 [Cloudflare](https://dash.cloudflare.com) 的域名（可在 Cloudflare 购买或转入 NS）。

```powershell
# 1. 登录 Cloudflare（会打开浏览器）
cloudflared tunnel login

# 2. 创建隧道
cloudflared tunnel create kaoyan-api

# 3. 绑定 DNS（将 api.你的域名.com 指到该隧道）
cloudflared tunnel route dns kaoyan-api api.你的域名.com
```

创建成功后，凭证文件在 `C:\Users\<用户名>\.cloudflared\<tunnel-id>.json`。

### 三、配置隧道

```powershell
copy cloudflare-tunnel\config.yml.example cloudflare-tunnel\config.yml
```

编辑 `cloudflare-tunnel/config.yml`，填写 `credentials-file` 路径和 `hostname`（与上一步 DNS 一致）。

### 四、配置本地 .env

项目根目录 `.env` 至少包含：

```env
DASHSCOPE_API_KEY=你的千问API密钥
CORS_ORIGINS=http://localhost:3000,https://你的vercel项目.vercel.app
```

`CORS_ORIGINS` 必须包含 **Vercel 前端域名**（浏览器 SSE 直连 Tunnel 时会校验来源）。

### 五、配置 Vercel 环境变量

| 变量 | 值 |
|------|-----|
| `BACKEND_URL` | `https://api.你的域名.com` |
| `NEXT_PUBLIC_API_URL` | `https://api.你的域名.com`（**聊天流式建议必配**） |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |

保存后在 Vercel **Redeploy** 一次。

### 六、每次使用前启动

**方式 A — 一键启动（两个新窗口）：**

```powershell
.\scripts\start-local-stack.ps1
```

**方式 B — 分步启动：**

```powershell
# 窗口 1：后端
.\scripts\start-backend.ps1

# 窗口 2：隧道
.\scripts\start-tunnel.ps1
```

### 七、验证

1. 本机：`http://127.0.0.1:8000/api/health` → `success: true`
2. 公网：`https://api.你的域名.com/api/health` → `success: true`
3. Vercel：`https://你的vercel域名.vercel.app/api/backend-health` → `success: true`

### 快速测试（无自有域名）

若暂时没有域名，可用临时隧道（**每次 URL 会变**，需同步改 Vercel 环境变量）：

```powershell
.\scripts\start-backend.ps1
# 另开窗口：
.\scripts\start-tunnel-quick.ps1
```

将输出的 `https://xxxx.trycloudflare.com` 填入 Vercel 的 `BACKEND_URL` 与 `NEXT_PUBLIC_API_URL`。

### 注意事项

- 电脑需保持开机，且后端 + `cloudflared` 进程都在运行。
- 固定域名方案下，Tunnel URL 不变，**无需每次改 Vercel**。
- 当前后端无 API 鉴权，暴露公网仅适合个人/demo；正式对外请用上文 Render 部署或自行加鉴权。
