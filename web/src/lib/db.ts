import postgres from "postgres"

// Server-only secret: read from the Node process env, NOT import.meta.env
// (Vite inlines import.meta.env.* at build time, which could bake the
// credential into output if this module were ever imported client-side).
const url = process.env.DATABASE_URL
if (!url) throw new Error("DATABASE_URL is not set (server-only)")

// The production DB lives on Coolify's internal Docker network with no TLS, so
// SSL is off by default. Set DATABASE_SSL=require to force TLS (e.g. if the DB is
// ever reached over a public, TLS-terminated port).
const ssl = process.env.DATABASE_SSL === "require" ? "require" : false

// One connection for the build process.
export const sql = postgres(url, { ssl })
