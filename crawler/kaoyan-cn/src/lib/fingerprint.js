import { createHash } from "crypto";

export function hashValue(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex").slice(0, 16);
}

export function fingerprintOverview(data) {
  if (!data) return null;
  return hashValue({
    content_id: data.content_id,
    intro: data.intro,
    num_master: data.num_master,
    num_doctor: data.num_doctor,
    num_subject: data.num_subject,
    rank: data.rank,
    school_address: data.school_address,
    feature: data.feature,
  });
}

export function fingerprintPlans(plans) {
  if (!plans?.items) return null;
  return hashValue({
    total: plans.total,
    year: plans.year,
    items: plans.items
      .map((p) => `${p.plan_id}:${p.special_code}:${p.recruit_number}:${p.depart_name}`)
      .sort(),
  });
}

export function fingerprintScores(scores) {
  if (!scores?.years) return null;
  const byYear = {};
  for (const [year, items] of Object.entries(scores.years)) {
    if (Array.isArray(items)) {
      byYear[year] = items
        .map((s) => `${s.code ?? s.name}:${s.total}:${s.depart_id}:${s.degree_type}`)
        .sort();
    } else {
      byYear[year] = items?.error ?? "empty";
    }
  }
  return hashValue(byYear);
}

export function fingerprintSchool(stored) {
  return {
    overview: fingerprintOverview(stored.overview),
    plans: fingerprintPlans(stored.plans),
    scores: fingerprintScores(stored.scores),
  };
}

export function diffFingerprints(oldFp, newFp) {
  const changes = [];
  if (oldFp?.overview !== newFp?.overview) changes.push("overview");
  if (oldFp?.plans !== newFp?.plans) changes.push("plans");
  if (oldFp?.scores !== newFp?.scores) changes.push("scores");
  return changes;
}
