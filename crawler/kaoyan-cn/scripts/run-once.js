import { runDailyCrawl } from "../src/jobs/daily-crawl.js";

const listOnly = process.argv.includes("--list-only");
const fresh = process.argv.includes("--fresh");

runDailyCrawl({ listOnly, resume: !fresh })
  .then(({ published, success }) => {
    if (published) {
      console.log(`Done. Latest data in crawler/data/kaoyan-cn/${published.historyDir}`);
    }
    if (success === false) {
      console.error("Crawl completed with errors. Run: npm run verify");
      process.exit(1);
    }
  })
  .catch((err) => {
    console.error(err);
    process.exit(1);
  });
