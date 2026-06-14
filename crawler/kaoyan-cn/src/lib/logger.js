import { appendFileSync, mkdirSync } from "fs";
import { resolveOutput, config } from "../../config.js";

function logPath() {
  const dir = resolveOutput(config.paths.logs);
  mkdirSync(dir, { recursive: true });
  const date = new Date().toISOString().slice(0, 10);
  return `${dir}/${date}.log`;
}

export function log(level, message) {
  const line = `[${new Date().toISOString()}] [${level}] ${message}`;
  console.log(line);
  try {
    appendFileSync(logPath(), line + "\n", "utf8");
  } catch {
    // ignore log write errors
  }
}

export const logger = {
  info: (msg) => log("INFO", msg),
  warn: (msg) => log("WARN", msg),
  error: (msg) => log("ERROR", msg),
};
