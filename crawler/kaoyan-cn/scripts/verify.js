import { readFileSync, existsSync, statSync } from "fs";
import { resolveOutput, config } from "../config.js";

function load(relativePath) {
  const full = resolveOutput(relativePath);
  if (!existsSync(full)) return null;
  return JSON.parse(readFileSync(full, "utf8"));
}

function checkSchoolDetail(school, index) {
  const issues = [];
  const prefix = `[#${index + 1} ${school.name}]`;

  if (!school.overview?.school_name) issues.push(`${prefix} 缺少 overview`);
  if (!school.plans?.items?.length) issues.push(`${prefix} 招生计划为空`);
  if (!school.scores?.years || Object.keys(school.scores.years).length === 0) {
    issues.push(`${prefix} 历年分数为空`);
  } else {
    const yearEntries = Object.entries(school.scores.years);
    const failedYears = yearEntries.filter(([, data]) => data && typeof data === "object" && data.error);
    const okYears = yearEntries.length - failedYears.length;
    if (okYears === 0) {
      issues.push(`${prefix} 历年分数全部失败`);
    } else if (failedYears.length > 0) {
      issues.push(`${prefix} ${failedYears.length} 个年份分数缺失（源站 API 异常，非致命）`);
    }
  }
  if (!school.labels?.includes("双一流")) {
    issues.push(`${prefix} 不含双一流标签`);
  }
  return issues;
}

export function verifyData() {
  const result = {
    ok: true,
    checks: [],
    warnings: [],
    errors: [],
  };

  const add = (level, msg) => {
    result.checks.push({ level, msg });
    if (level === "error") {
      result.errors.push(msg);
      result.ok = false;
    } else if (level === "warn") {
      result.warnings.push(msg);
    }
  };

  const listPath = `${config.paths.latest}/schools.json`;
  const fullPath = `${config.paths.latest}/syl-schools-full.json`;
  const checkpointPath = config.paths.checkpoint;

  if (existsSync(resolveOutput(checkpointPath))) {
    const cp = load(checkpointPath);
    const done = cp?.completedIds?.length ?? 0;
    if (done > 0 && done < (cp?.listPayload?.schools?.length ?? config.expectedSchoolCount)) {
      add("warn", `抓取进行中：checkpoint 已完成 ${done} 所，尚未结束`);
      result.ok = false;
    }
  }

  const list = load(listPath);
  if (!list) {
    add("error", `缺少文件: ${listPath}`);
    return result;
  }

  add("ok", `schools.json 存在，${list.schools?.length ?? 0} 所`);
  if (list.schools?.length !== config.expectedSchoolCount) {
    add("error", `列表数量应为 ${config.expectedSchoolCount}，实际 ${list.schools?.length}`);
  }
  if (list.meta?.source !== config.sourceUrl) {
    add("warn", "列表 meta.source 与配置不一致");
  }

  const bad = (list.schools ?? []).filter((s) => !s.labels?.includes("双一流"));
  if (bad.length) add("error", `列表含 ${bad.length} 所非双一流院校`);

  const full = load(fullPath);
  if (!full) {
    add("error", `缺少文件: ${fullPath}`);
    return result;
  }

  const stat = statSync(resolveOutput(fullPath));
  add("ok", `syl-schools-full.json 存在，${(stat.size / 1024 / 1024).toFixed(1)} MB`);

  const total = full.schools?.length ?? 0;
  const expected = full.meta?.expectedSchools ?? config.expectedSchoolCount;
  add("ok", `详情 ${total}/${expected} 所，更新时间 ${full.meta?.extractedAt ?? "未知"}`);

  if (total !== config.expectedSchoolCount) {
    add("error", `详情数量应为 ${config.expectedSchoolCount}，实际 ${total}`);
  }

  const apiErrors = full.meta?.errors ?? [];
  if (apiErrors.length > 0) {
    add("error", `有 ${apiErrors.length} 所抓取失败: ${apiErrors.map((e) => e.name).join(", ")}`);
  }

  for (let i = 0; i < (full.schools ?? []).length; i += 1) {
    const issues = checkSchoolDetail(full.schools[i], i);
    for (const msg of issues) {
      if (msg.includes("非致命")) {
        add("warn", msg);
      } else {
        add("error", msg);
      }
    }
  }

  return result;
}

function main() {
  console.log("=== 掌上考研爬虫数据校验 ===\n");
  console.log(`数据目录: ${config.outputDir}\n`);

  const result = verifyData();

  for (const { level, msg } of result.checks) {
    const tag = level === "ok" ? "✓" : level === "warn" ? "!" : "✗";
    console.log(`${tag} ${msg}`);
  }

  if (result.errors.length > 0) {
    console.log("\n--- 问题详情 ---");
    for (const e of result.errors.slice(0, 20)) console.log("✗", e);
    if (result.errors.length > 20) console.log(`... 还有 ${result.errors.length - 20} 条`);
  }

  console.log("\n" + (result.ok ? "结论: 数据完整，任务成功 ✓" : "结论: 数据不完整或有问题 ✗"));
  process.exit(result.ok ? 0 : 1);
}

if (import.meta.url === `file:///${process.argv[1].replace(/\\/g, "/")}` ||
    process.argv[1]?.endsWith("verify.js")) {
  main();
}
