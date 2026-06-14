import { readJson, writeJson, ensureDirs } from "../src/lib/storage.js";
import { buildManifestFromFull, saveManifest } from "../src/lib/manifest.js";
import { config } from "../config.js";

ensureDirs();

const list = readJson(`${config.paths.latest}/schools.json`);
const full = readJson(`${config.paths.latest}/syl-schools-full.json`);

const manifest = buildManifestFromFull(full, list);
saveManifest(manifest);

console.log(`Manifest built: ${manifest.schoolIds.length} schools`);
console.log(`Saved to E:\\Kaoyan\\re\\manifest.json`);
