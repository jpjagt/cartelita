import postgres from "postgres";

const url = import.meta.env.DATABASE_URL ?? process.env.DATABASE_URL;
if (!url) throw new Error("DATABASE_URL is not set (server-only)");

// One connection for the build process; SSL required in production.
export const sql = postgres(url, {
  ssl: url.includes("localhost") ? false : "require",
});
