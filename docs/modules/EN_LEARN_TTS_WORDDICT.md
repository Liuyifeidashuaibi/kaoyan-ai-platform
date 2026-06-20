# 英文纠错 + TTS + ECDICT 词库模块

## 新增目录

```
backend/app/modules/
  en_learn/     # 英文纠错 + 增强翻译 Facade（不改 translator_service 内部）
  tts/          # Qwen3-TTS + Piper 兜底
  word_dict/    # ECDICT word_lib + /api/word-query
  shared/       # Ollama 本地调用

scripts/
  sql/word_lib.sql
  import_ecdict.py
  qwen3_tts_synthesize.py
```

## API

| 接口 | 说明 |
|------|------|
| `POST /api/en-learn/translate/text` | 纠错 + 双语翻译，返回 `error_list` |
| `POST /api/en-learn/translate/image` | OCR + 纠错 + 翻译 |
| `GET /api/word-query?word=&mode=hover\|detail` | 词库优先，AI 缓存 |
| `POST /api/tts/synthesize` | 整段 WAV |
| `POST /api/tts/stream` | 分句流式 NDJSON + WAV |
| `POST /api/tts/sentences` | 分句列表（高亮同步） |

## ECDICT 导入

1. 下载 [ecdict.csv](https://github.com/skywind3000/ECDICT) 到 `data/ecdict/ecdict.csv`
2. 执行：

```powershell
python scripts/import_ecdict.py --csv data/ecdict/ecdict.csv
```

测试导入 1 万条：

```powershell
python scripts/import_ecdict.py --csv data/ecdict/ecdict.csv --limit 10000
```

## 环境变量（.env）

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_TEXT_MODEL=qwen2.5-vl:7b-q4_K_M
WORD_LIB_DB_PATH=data/word_lib.db
QWEN3_TTS_ENABLED=false
QWEN3_TTS_SCRIPT=scripts/qwen3_tts_synthesize.py
PIPER_MODEL_US_FEMALE=data/tts/piper/en_US-lessac-medium.onnx
```

## 前端

翻译页已切换为 `EnLearnTranslatorApp`：

- 翻译完成后解锁 **朗读** 与 **学习理解模式**
- 错误词红色 + 灰色修正提示
- 单词 hover 释义 / 点击详情弹窗

## 本地测试

```powershell
# Piper + Qwen3 模型与依赖
.\scripts\setup-tts.ps1
.\scripts\setup-tts.ps1 -DownloadQwen   # 下载 Qwen3 0.6B（ModelScope）

# 启动 Qwen3 GPU/CPU 宿主机服务（Docker backend 经 :8200 调用）
.\scripts\start-tts-host.ps1

cd backend
python ../examples/test_word_query.py
```

`.env` 关键项：

```env
QWEN3_TTS_ENABLED=true
QWEN3_TTS_MODEL=data/tts/qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
QWEN3_TTS_HOST_URL=http://host.docker.internal:8200
```

Qwen3 模型已通过 ModelScope 下载到 `data/tts/qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice/`（与 Ollama 版等价，走 `qwen-tts` Python 包，非 Ollama pull）。
