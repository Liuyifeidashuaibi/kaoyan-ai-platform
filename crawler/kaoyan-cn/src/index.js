import cron from "node-cron";
import { config } from "../config.js";
import { runDailySync } from "./jobs/daily-sync.js";
import { logger } from "./lib/logger.js";

let running = false;

async function safeRun() {
  if (running) {
    logger.warn("Previous sync still running, skip this tick");
    return;
  }
  running = true;
  try {
    const { report } = await runDailySync();
    const s = report.summary;
    logger.info(`Sync summary: +${s.added} -${s.removed} ~${s.updated} =${s.unchanged}`);
  } catch (err) {
    logger.error(`Sync crashed: ${err}`);
  } finally {
    running = false;
  }
}

logger.info("Kaoyan SYL incremental sync daemon starting");
logger.info(`Schedule: ${config.cronSchedule} (${config.timezone})`);
logger.info(`Output: ${config.outputDir}`);
logger.info("Mode: daily probe + fetch only changed schools");

cron.schedule(config.cronSchedule, safeRun, { timezone: config.timezone });

logger.info("Waiting for next scheduled sync. Press Ctrl+C to stop.");

process.on("SIGINT", () => {
  logger.info("Shutting down");
  process.exit(0);
});
