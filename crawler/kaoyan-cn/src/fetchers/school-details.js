import { config } from "../../config.js";
import { sleep, postJson, getInfoJson } from "../lib/http.js";

export async function fetchOverview(schoolId) {
  return getInfoJson(schoolId);
}

export async function fetchPlans(schoolId) {
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
    await sleep(config.delayBetweenPages);
  }

  return { year: config.planYear, total: all.length, items: all };
}

export async function fetchScores(schoolId) {
  const referer = `https://www.kaoyan.cn/school/${schoolId}/score`;
  const byYear = {};

  for (const year of config.scoreYears) {
    try {
      const data = await postJson(
        config.scoreApi,
        { school_id: String(schoolId), year, degree_type: "" },
        referer,
      );
      const items = Array.isArray(data) ? data : Object.values(data ?? {});
      if (items.length > 0) byYear[String(year)] = items;
    } catch (err) {
      byYear[String(year)] = { error: String(err) };
    }
    await sleep(config.delayBetweenScoreYears);
  }

  return { years: byYear };
}

export async function fetchSchoolDetail(school) {
  const [overview, plans, scores] = await Promise.all([
    fetchOverview(school.id),
    fetchPlans(school.id),
    fetchScores(school.id),
  ]);

  return {
    id: school.id,
    name: school.name,
    location: school.location,
    type: school.type,
    labels: school.labels,
    logo: school.logo,
    overview,
    plans,
    scores,
  };
}
