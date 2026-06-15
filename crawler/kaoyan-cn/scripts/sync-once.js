import { runDailySync } from "../src/jobs/daily-sync.js";

runDailySync()
  .then(({ report, success }) => {
    const s = report.summary;
    console.log(`\n同步完成: 新增 ${s.added} | 删除 ${s.removed} | 更新 ${s.updated} | 无变化 ${s.unchanged}`);
    if (s.added + s.removed + s.updated === 0) {
      console.log("官方数据无变化，本地文件未重写详情。");
    }
    if (!success) process.exit(1);
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
