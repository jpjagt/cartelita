import postgres from "postgres"

// Server-only secret: read from the Node process env, NOT import.meta.env
// (Vite inlines import.meta.env.* at build time, which could bake the
// credential into output if this module were ever imported client-side).
const url = import.meta.env.DATABASE_URL
if (!url) throw new Error("DATABASE_URL is not set (server-only)")

// One connection for the build process; SSL required in production.
export const sql = postgres(url, {
  ssl: url.includes("localhost") ? false : "require",
})
