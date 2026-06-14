import { mkdirSync, writeFileSync, readFileSync, existsSync } from "fs";
import { dirname } from "path";
import { resolveOutput, config } from "../../config.js";

export function ensureDirs() {
  mkdirSync(resolveOutput(config.paths.latest), { recursive: true });
  mkdirSync(resolveOutput(config.paths.history), { recursive: true });
  mkdirSync(resolveOutput(config.paths.logs), { recursive: true });
}

export function beijingDateSlug() {
  return new Intl.DateTimeFormat("sv-SE", {
    timeZone: config.timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export function writeJson(relativePath, data) {
  const full = resolveOutput(relativePath);
  mkdirSync(dirname(full), { recursive: true });
  writeFileSync(full, JSON.stringify(data, null, 2), "utf8");
  return full;
}

export function readJson(relativePath) {
  const full = resolveOutput(relativePath);
  return JSON.parse(readFileSync(full, "utf8"));
}

export function checkpointPath() {
  return resolveOutput(config.paths.checkpoint);
}

export function loadCheckpoint() {
  const path = checkpointPath();
  if (!existsSync(path)) {
    return { completedIds: [], schools: [], errors: [], listSaved: false };
  }
  return JSON.parse(readFileSync(path, "utf8"));
}

export function saveCheckpoint(data) {
  writeFileSync(checkpointPath(), JSON.stringify(data, null, 2), "utf8");
}

export function clearCheckpoint() {
  const path = checkpointPath();
  if (existsSync(path)) {
    writeFileSync(path, "{}", "utf8");
  }
}

/** 写入 latest 并归档到 history/YYYY-MM-DD/ */
export function publishData(files) {
  ensureDirs();
  const dateSlug = beijingDateSlug();
  const historyDir = `${config.paths.history}/${dateSlug}`;

  for (const [name, data] of Object.entries(files)) {
    writeJson(`${config.paths.latest}/${name}`, data);
    writeJson(`${historyDir}/${name}`, data);
  }

  return { dateSlug, historyDir };
}
