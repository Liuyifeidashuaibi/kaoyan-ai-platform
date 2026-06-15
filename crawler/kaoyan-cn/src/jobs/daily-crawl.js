import { config } from "../../config.js";
import { fetchSchoolList } from "../fetchers/school-list.js";
import { fetchSchoolDetail } from "../fetchers/school-details.js";
import {
  ensureDirs,
  publishData,
  loadCheckpoint,
  saveCheckpoint,
  clearCheckpoint,
} from "../lib/storage.js";
import { logger } from "../lib/logger.js";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * @param {{ listOnly?: boolean, resume?: boolean }} [options]
 */
export async function runDailyCrawl(options = {}) {
  const { listOnly = false, resume = true } = options;
  const startedAt = new Date().toISOString();

  logger.info("=== Crawl started ===");
  ensureDirs();

  let checkpoint = resume ? loadCheckpoint() : { completedIds: [], schools: [], errors: [], listSaved: false };
  if (!resume) clearCheckpoint();

  let listPayload;

  if (checkpoint.listSaved && checkpoint.listPayload) {
    listPayload = checkpoint.listPayload;
    logger.info(`Using cached list: ${listPayload.schools.length} schools`);
  } else {
    listPayload = await fetchSchoolList();
    checkpoint.listPayload = listPayload;
    checkpoint.listSaved = true;
    saveCheckpoint(checkpoint);
    logger.info(`School list fetched: ${listPayload.schools.length} schools`);
  }

  if (listOnly) {
    const published = publishData({ "schools.json": listPayload });
    logger.info(`List-only saved to latest/ and history/${published.dateSlug}/`);
    return { listPayload, fullPayload: null, published };
  }

  const completedSet = new Set(checkpoint.completedIds ?? []);
  const schools = listPayload.schools;

  for (let i = 0; i < schools.length; i += 1) {
    const school = schools[i];
    if (completedSet.has(school.id)) continue;

    process.stdout.write(`[${i + 1}/${schools.length}] ${school.name} (${school.id})... `);

    try {
      const detail = await fetchSchoolDetail(school);
      checkpoint.schools.push(detail);
      checkpoint.completedIds.push(school.id);
      completedSet.add(school.id);
      saveCheckpoint(checkpoint);
      console.log("ok");
      logger.info(`Fetched detail: ${school.name} (${school.id})`);
    } catch (err) {
      checkpoint.errors = checkpoint.errors ?? [];
      checkpoint.errors.push({ id: school.id, name: school.name, error: String(err) });
      saveCheckpoint(checkpoint);
      console.log("FAILED:", err);
      logger.error(`Failed ${school.name} (${school.id}): ${err}`);
    }

    await sleep(config.delayBetweenSchools);
  }

  const fullPayload = {
    meta: {
      source: config.sourceUrl,
      extractedAt: new Date().toISOString(),
      startedAt,
      totalSchools: checkpoint.schools.length,
      expectedSchools: schools.length,
      planYear: config.planYear,
      scoreYears: config.scoreYears,
      errors: checkpoint.errors ?? [],
      success:
        checkpoint.schools.length === schools.length &&
        (checkpoint.errors ?? []).length === 0,
    },
    schools: checkpoint.schools.sort((a, b) => a.id - b.id),
  };

  const published = publishData({
    "schools.json": listPayload,
    "syl-schools-full.json": fullPayload,
  });

  if (fullPayload.meta.success) {
    clearCheckpoint();
    logger.info(`=== Crawl finished OK: ${fullPayload.meta.totalSchools}/${schools.length} schools ===`);
  } else {
    logger.warn(
      `=== Crawl finished WITH ERRORS: ${fullPayload.meta.totalSchools}/${schools.length}, failed ${(checkpoint.errors ?? []).length} ===`,
    );
    logger.warn("Checkpoint kept for resume. Run: npm run crawl");
  }
  logger.info(`Data saved to E:\\Kaoyan\\re\\latest and history/${published.dateSlug}/`);

  return { listPayload, fullPayload, published, success: fullPayload.meta.success };
}
