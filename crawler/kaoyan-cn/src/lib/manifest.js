import { config, resolveOutput } from "../../config.js";
import { readJson, writeJson, beijingDateSlug } from "./storage.js";
import { fingerprintSchool } from "./fingerprint.js";

const MANIFEST_PATH = "manifest.json";

export function loadManifest() {
  try {
    return readJson(MANIFEST_PATH);
  } catch {
    return null;
  }
}

export function saveManifest(manifest) {
  manifest.updatedAt = new Date().toISOString();
  writeJson(MANIFEST_PATH, manifest);
}

/** 从已有全量数据构建 manifest（首次同步前执行一次） */
export function buildManifestFromFull(fullPayload, listPayload) {
  const schools = {};
  for (const school of fullPayload.schools ?? []) {
    schools[String(school.id)] = {
      id: school.id,
      name: school.name,
      fingerprints: fingerprintSchool(school),
    };
  }

  return {
    version: 1,
    source: config.sourceUrl,
    schoolIds: (listPayload.schools ?? []).map((s) => s.id).sort((a, b) => a - b),
    schools,
    builtAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

export function initManifestIfNeeded(fullPayload, listPayload) {
  let manifest = loadManifest();
  if (manifest?.schools && Object.keys(manifest.schools).length > 0) {
    return manifest;
  }
  manifest = buildManifestFromFull(fullPayload, listPayload);
  saveManifest(manifest);
  return manifest;
}

export function writeChangeReport(report) {
  const dateSlug = beijingDateSlug();
  writeJson(`${config.paths.logs}/changes-${dateSlug}.json`, report);
  return `${config.paths.logs}/changes-${dateSlug}.json`;
}
