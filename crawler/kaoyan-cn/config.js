import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('./src/types.js').CrawlerConfig} */
export const config = {
  /** 数据输出根目录（项目内 crawler/data/kaoyan-cn） */
  outputDir: join(__dirname, "..", "data", "kaoyan-cn"),

  sourceUrl: "https://www.kaoyan.cn/school-list/0-0-syl",
  listApi: "https://api.kaoyan.cn/pc/school/schoolList",
  planApi: "https://api.kaoyan.cn/pc/school/planListV2",
  scoreApi: "https://api.kaoyan.cn/pc/school/schoolScore",
  infoApiBase: "https://static.kaoyan.cn/json/school",

  feature: "syl",
  expectedSchoolCount: 147,

  planYear: 2026,
  scoreYears: [2022, 2023, 2024, 2025, 2026],

  delayBetweenSchools: 200,
  delayBetweenPages: 100,
  delayBetweenScoreYears: 80,

  cronSchedule: "0 0 * * *",
  timezone: "Asia/Shanghai",

  paths: {
    latest: "latest",
    history: "history",
    logs: "logs",
    checkpoint: ".checkpoint.json",
    manifest: "manifest.json",
  },
};

export function resolveOutput(...segments) {
  return join(config.outputDir, ...segments);
}
