# 已弃用：掌上考研 / 旧版全量爬虫

以下脚本为数据重建前的第三方复试线导入链路，**不再被 `main.py patrol/update` 调用**。
仅在使用 `--with-legacy-scores` 时经 `adapters/generic.py` 间接调用 `fast_fill_all.py`。

| 文件 | 说明 |
|------|------|
| `fast_fill_all.py` | 掌上考研学院 + 复试线批量导入 |
| `import_kaoyan_scores_csv.py` | CSV 导入复试线 |
| `import_kaoyan_scores_batch.py` | 分批 CSV 导入 |
| `crawl_kaoyan_scores_csv.py` | 爬取掌上考研 CSV |
| `kaoyan_score_sources.py` | 掌上考研数据源 |
| `crawl_updates_smart.py` | 旧版智能增量爬虫 |
| `pipeline_enrich.py` | 旧版 enrich 管道 |
| `crawler.py` | 更早期的爬虫入口 |

新架构入口：`main.py` → `discover/` + `fetchers/` + `parsers/` + `storage/`。
