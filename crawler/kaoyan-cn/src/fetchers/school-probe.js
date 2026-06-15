import { config } from "../../config.js";
import { sleep, postJson, getInfoJson } from "../lib/http.js";
import {
  fingerprintOverview,
  fingerprintPlans,
  fingerprintScores,
} from "../lib/fingerprint.js";

async function fetchPlansSignature(schoolId) {
  const referer = `https://www.kaoyan.cn/school/${schoolId}/plan`;
  const all = [];
  let page = 1;
  let total = Infinity;

  while (all.length < total) {
    const data = await postJson(
      config.planApi,
      {
        school_id: String(schoolId),
        recruit_type: "",
        page,
        limit: 200,
        keyword: "",
        is_apply: 2,
        degree_type: "",
        first_class: "",
        second_class: "",
      },
      referer,
    );
    const batch = data?.data ?? [];
    total = data?.total ?? batch.length;
    all.push(...batch);
    if (batch.length === 0) break;
    page += 1;
    await sleep(50);
  }

  return fingerprintPlans({ year: config.planYear, total: all.length, items: all });
}

async function fetchScoresSignature(schoolId) {
  const referer = `https://www.kaoyan.cn/school/${schoolId}/score`;
  const years = {};

  for (const year of config.scoreYears) {
    try {
      const data = await postJson(
        config.scoreApi,
        { school_id: String(schoolId), year, degree_type: "" },
        referer,
      );
      const items = Array.isArray(data) ? data : Object.values(data ?? {});
      years[String(year)] = items;
    } catch (err) {
      years[String(year)] = { error: String(err) };
    }
    await sleep(40);
  }

  return fingerprintScores({ years });
}

/** 轻量探测：只拉指纹，不存正文 */
export async function probeSchoolFingerprints(schoolId) {
  const overviewData = await getInfoJson(schoolId);
  const [plans, scores] = await Promise.all([
    fetchPlansSignature(schoolId),
    fetchScoresSignature(schoolId),
  ]);

  return {
    overview: fingerprintOverview(overviewData),
    plans,
    scores,
  };
}
