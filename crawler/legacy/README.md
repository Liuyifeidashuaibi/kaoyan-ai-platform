# 已弃用：掌上考研 / 旧版 Python 爬虫

以下脚本已被 `kaoyan-cn/` Node 爬虫 + `import_kaoyan_full.py` 取代。
**请勿再使用这些脚本**，数据请通过 `npm run crawler:kaoyan:sync` 同步。

| 文件 | 说明 | 替代方案 |
|------|------|----------|
| `fast_fill_all.py` | 掌上考研学院 + 复试线批量导入 | `sync_kaoyan_cn.py` |
| `import_kaoyan_scores_csv.py` | CSV 导入复试线 | `import_kaoyan_full.py` |
| `import_kaoyan_scores_batch.py` | 分批 CSV 导入 | `import_kaoyan_full.py` |
| `crawl_kaoyan_scores_csv.py` | 爬取掌上考研 CSV | `kaoyan-cn/` Node 爬虫 |
| `kaoyan_score_sources.py` | 掌上考研数据源 | `kaoyan-cn/src/fetchers/` |
| `crawl_updates_smart.py` | 旧版智能增量爬虫 | `kaoyan-cn/scripts/sync-once.js` |
| `pipeline_enrich.py` | 旧版 enrich 管道 | `import_kaoyan_full.py` |
| `crawler.py` | 更早期的爬虫入口 | `kaoyan-cn/scripts/run-once.js` |

新架构入口：
- **主数据源**：`crawler/kaoyan-cn/` → `import_kaoyan_full.py`
- **官方来源辅助**：`main.py` → `discover/` + `fetchers/` + `parsers/` + `storage/`
