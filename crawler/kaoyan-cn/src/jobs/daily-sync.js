import { config } from "../../config.js";
import { fetchSchoolList } from "../fetchers/school-list.js";
import { fetchSchoolDetail } from "../fetchers/school-details.js";
import { probeSchoolFingerprints } from "../fetchers/school-probe.js";
import { diffFingerprints, fingerprintOverview, fingerprintPlans, fingerprintScores } from "../lib/fingerprint.js";
import {
  loadManifest,
  saveManifest,
  initManifestIfNeeded,
  writeChangeReport,
  buildManifestFromFull,
} from "../lib/manifest.js";
import {
  ensureDirs,
  readJson,
  writeJson,
  publishData,
  beijingDateSlug,
} from "../lib/storage.js";
import { logger } from "../lib/logger.js";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function loadLocalData() {
  const list = readJson(`${config.paths.latest}/schools.json`);
  const full = readJson(`${config.paths.latest}/syl-schools-full.json`);
  return { list, full };
}

function mergeSchool(fullPayload, schoolDetail) {
  const idx = fullPayload.schools.findIndex((s) => s.id === schoolDetail.id);
  if (idx >= 0) fullPayload.schools[idx] = schoolDetail;
  else fullPayload.schools.push(schoolDetail);
  fullPayload.schools.sort((a, b) => a.id - b.id);
}

function removeSchool(fullPayload, schoolId) {
  fullPayload.schools = fullPayload.schools.filter((s) => s.id !== schoolId);
}

/**
 * 每日增量同步：对比官方指纹，只更新有变化的院校
 */
export async function runDailySync() {
  const startedAt = new Date().toISOString();
  logger.info("=== Daily sync started ===");
  ensureDirs();

  let { list: listPayload, full: fullPayload } = loadLocalData();

  if (!fullPayload?.schools?.length) {
    throw new Error("本地无全量数据，请先运行: npm run crawl");
  }

  let manifest = loadManifest();
  if (!manifest?.schools || Object.keys(manifest.schools).length === 0) {
    logger.info("Building manifest from local full data...");
    manifest = buildManifestFromFull(fullPayload, listPayload);
    saveManifest(manifest);
  }

  const liveList = await fetchSchoolList();
  const liveIds = new Set(liveList.schools.map((s) => s.id));
  const localIds = new Set(manifest.schoolIds ?? []);

  const added = liveList.schools.filter((s) => !localIds.has(s.id));
  const removed = (manifest.schoolIds ?? [])
    .filter((id) => !liveIds.has(id))
    .map((id) => ({
      id,
      name: manifest.schools[String(id)]?.name ?? `id:${id}`,
    }));

  const updated = [];
  const unchanged = [];

  for (const school of liveList.schools) {
    if (added.some((a) => a.id === school.id)) continue;

    const oldFp = manifest.schools[String(school.id)]?.fingerprints;
    process.stdout.write(`Probe ${school.name}... `);

    try {
      const newFp = await probeSchoolFingerprints(school.id);
      const changes = oldFp ? diffFingerprints(oldFp, newFp) : ["overview", "plans", "scores"];

      if (changes.length > 0) {
        updated.push({ id: school.id, name: school.name, changes, fingerprints: newFp });
        console.log(`CHANGED: ${changes.join(", ")}`);
        logger.info(`${school.name} changed: ${changes.join(", ")}`);
      } else {
        unchanged.push({ id: school.id, name: school.name });
        console.log("ok");
      }
    } catch (err) {
      console.log("PROBE FAILED:", err);
      logger.error(`Probe failed ${school.name}: ${err}`);
      updated.push({
        id: school.id,
        name: school.name,
        changes: ["overview", "plans", "scores"],
        error: String(err),
      });
    }

    await sleep(config.delayBetweenSchools);
  }

  const toFetch = [...added, ...updated];
  const fetchErrors = [];

  for (const item of toFetch) {
    const schoolMeta = liveList.schools.find((s) => s.id === item.id);
    if (!schoolMeta) continue;

    process.stdout.write(`Fetch ${schoolMeta.name}... `);
    try {
      const detail = await fetchSchoolDetail(schoolMeta);
      mergeSchool(fullPayload, detail);
      manifest.schools[String(item.id)] = {
        id: item.id,
        name: schoolMeta.name,
        fingerprints: {
          overview: fingerprintOverview(detail.overview),
          plans: fingerprintPlans(detail.plans),
          scores: fingerprintScores(detail.scores),
        },
      };
      console.log("ok");
    } catch (err) {
      fetchErrors.push({ id: item.id, name: schoolMeta.name, error: String(err) });
      console.log("FAILED:", err);
    }
    await sleep(config.delayBetweenSchools);
  }

  for (const r of removed) {
    removeSchool(fullPayload, r.id);
    delete manifest.schools[String(r.id)];
    logger.info(`Removed school: ${r.name} (${r.id})`);
  }

  manifest.schoolIds = liveList.schools.map((s) => s.id).sort((a, b) => a - b);
  listPayload = liveList;

  fullPayload.meta = {
    ...fullPayload.meta,
    source: config.sourceUrl,
    extractedAt: new Date().toISOString(),
    lastSyncAt: startedAt,
    totalSchools: fullPayload.schools.length,
    expectedSchools: liveList.schools.length,
    planYear: config.planYear,
    scoreYears: config.scoreYears,
    syncMode: "incremental",
  };

  saveManifest(manifest);

  const hasChanges =
    added.length > 0 ||
    removed.length > 0 ||
    updated.length > 0 ||
    fetchErrors.length > 0;

  if (hasChanges) {
    publishData({
      "schools.json": listPayload,
      "syl-schools-full.json": fullPayload,
    });
    logger.info("Local data updated (changes detected)");
  } else {
    writeJson(`${config.paths.latest}/schools.json`, listPayload);
    logger.info("No changes from official site — full detail files kept as-is");
  }

  const report = {
    date: beijingDateSlug(),
    startedAt,
    finishedAt: new Date().toISOString(),
    summary: {
      added: added.length,
      removed: removed.length,
      updated: updated.length,
      unchanged: unchanged.length,
      fetchErrors: fetchErrors.length,
    },
    added: added.map((s) => ({ id: s.id, name: s.name })),
    removed,
    updated: updated.map((u) => ({
      id: u.id,
      name: u.name,
      changes: u.changes,
      error: u.error,
    })),
    fetchErrors,
  };

  const reportPath = writeChangeReport(report);

  logger.info(
    `=== Sync done: +${added.length} -${removed.length} ~${updated.length} =${unchanged.length} ===`,
  );
  logger.info(`Change report: ${reportPath}`);

  return { report, success: fetchErrors.length === 0 };
}
