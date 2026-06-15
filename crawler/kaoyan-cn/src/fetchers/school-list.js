import { config } from "../../config.js";
import { sleep, apiHeaders } from "../lib/http.js";
import { mapSchoolRecord } from "../lib/school-mapper.js";
import { logger } from "../lib/logger.js";

const FILTERS = {
  types: [
    "综合类", "理工类", "农林类", "医药类", "师范类", "语言类", "财经类",
    "政法类", "体育类", "艺术类", "民族类", "军事类", "其他",
  ],
  levels: ["全部", "985", "211"],
};

export async function fetchSchoolList() {
  const headers = apiHeaders(config.sourceUrl);
  /** @type {Record<string, unknown>[]} */
  const allRaw = [];
  let page = 1;
  let total = Infinity;

  while (allRaw.length < total) {
    const body = {
      page,
      limit: 100,
      province_id: 0,
      type: 0,
      level: 0,
      is_apply: 0,
      name: "",
      feature: config.feature,
    };

    const res = await fetch(config.listApi, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const json = await res.json();
    if (json.code !== "0000") {
      throw new Error(`schoolList failed: ${json.message ?? json.code}`);
    }

    const batch = json.data?.data ?? [];
    total = json.data?.total ?? batch.length;
    allRaw.push(...batch);
    logger.info(`List page ${page}: +${batch.length}, total ${allRaw.length}/${total}`);

    if (batch.length === 0) break;
    page += 1;
    await sleep(config.delayBetweenPages);
  }

  const sylOnly = allRaw.filter((s) => s.syl === 1);
  const rejected = allRaw.filter((s) => s.syl !== 1);

  if (rejected.length > 0) {
    logger.warn(`Rejected non-syl: ${rejected.map((s) => s.school_name).join(", ")}`);
  }
  if (sylOnly.length !== config.expectedSchoolCount) {
    logger.warn(`Expected ${config.expectedSchoolCount} schools, got ${sylOnly.length}`);
  }

  const schools = sylOnly.map(mapSchoolRecord);

  return {
    meta: {
      source: config.sourceUrl,
      filter: "双一流 (feature=syl)",
      total: schools.length,
      updatedAt: new Date().toISOString(),
    },
    schools,
    filters: { location: [], ...FILTERS },
  };
}
