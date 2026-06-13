import fs from "node:fs";
import path from "node:path";
import { config as loadEnv } from "dotenv";
import pg from "pg";

const { Client } = pg;

loadEnv({ path: path.join(process.cwd(), ".env.local") });
loadEnv({ path: path.join(process.cwd(), ".env") });
loadEnv({ path: path.join(process.cwd(), "crawler", ".env") });

const PROJECT_REF = "zlgogxuzkmirxinorert";
const migrationArg = process.argv[2] ?? "001_core_schema.sql";
const SQL_PATH = path.join(
  process.cwd(),
  "supabase",
  "migrations",
  migrationArg
);

function getConnectionCandidates() {
  const candidates = [];

  const dbUrl = process.env.DATABASE_URL || "";
  if (dbUrl.startsWith("postgresql")) {
    candidates.push(dbUrl);
  }

  const password = process.env.SUPABASE_DB_PASSWORD;
  if (password) {
    candidates.push(
      `postgresql://postgres.${PROJECT_REF}:${encodeURIComponent(password)}@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres`,
      `postgresql://postgres.${PROJECT_REF}:${encodeURIComponent(password)}@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`,
      `postgresql://postgres.${PROJECT_REF}:${encodeURIComponent(password)}@aws-0-us-east-1.pooler.supabase.com:6543/postgres`,
      `postgresql://postgres:${encodeURIComponent(password)}@db.${PROJECT_REF}.supabase.co:5432/postgres`
    );
  }

  return candidates;
}

async function runWithClient(connectionString, sql) {
  const client = new Client({
    connectionString,
    ssl: { rejectUnauthorized: false },
  });

  await client.connect();
  try {
    await client.query(sql);
  } finally {
    await client.end();
  }
}

async function runWithManagementApi(accessToken, sql) {
  const response = await fetch(
    `https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query: sql }),
    }
  );

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Management API ${response.status}: ${body}`);
  }
}

async function main() {
  if (!fs.existsSync(SQL_PATH)) {
    throw new Error(`Migration file not found: ${SQL_PATH}`);
  }

  const sql = fs.readFileSync(SQL_PATH, "utf8");
  console.log(`Running migration: ${migrationArg}`);

  const accessToken = process.env.SUPABASE_ACCESS_TOKEN;
  if (accessToken) {
    console.log("Running migration via Supabase Management API...");
    await runWithManagementApi(accessToken, sql);
    console.log("Migration completed via Management API.");
    return;
  }

  const candidates = getConnectionCandidates();
  if (candidates.length === 0) {
    throw new Error(
      "Missing DATABASE_URL, SUPABASE_DB_PASSWORD, or SUPABASE_ACCESS_TOKEN.\n" +
        "Add one to .env.local — see .env.local.example"
    );
  }

  let lastError;
  for (const connectionString of candidates) {
    try {
      console.log("Trying database connection...");
      await runWithClient(connectionString, sql);
      console.log("Migration completed via direct Postgres connection.");
      return;
    } catch (error) {
      lastError = error;
      console.warn(
        `Connection failed: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  throw lastError;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
