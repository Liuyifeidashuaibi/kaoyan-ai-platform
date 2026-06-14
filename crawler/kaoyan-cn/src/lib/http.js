import { config } from "../../config.js";

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function apiHeaders(referer) {
  return {
    "Content-Type": "application/json",
    Origin: "https://www.kaoyan.cn",
    Referer: referer,
  };
}

export async function postJson(url, body, referer, retries = 3) {
  let lastErr;
  for (let attempt = 1; attempt <= retries; attempt += 1) {
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: apiHeaders(referer),
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(30000),
      });
      const json = await res.json();
      if (json.code !== "0000") {
        throw new Error(`${url} failed: ${json.message ?? json.code}`);
      }
      return json.data;
    } catch (err) {
      lastErr = err;
      if (attempt < retries) await sleep(1000 * attempt);
    }
  }
  throw lastErr;
}

export async function getInfoJson(schoolId, retries = 3) {
  const url = `${config.infoApiBase}/${schoolId}/info.json?a=www.kaoyan.cn`;
  let lastErr;
  for (let attempt = 1; attempt <= retries; attempt += 1) {
    try {
      const res = await fetch(url, {
        headers: { Referer: `https://www.kaoyan.cn/school/${schoolId}` },
        signal: AbortSignal.timeout(30000),
      });
      const json = await res.json();
      if (json.code !== "0000") {
        throw new Error(`info.json ${schoolId}: ${json.message ?? json.code}`);
      }
      return json.data;
    } catch (err) {
      lastErr = err;
      if (attempt < retries) await sleep(1000 * attempt);
    }
  }
  throw lastErr;
}
