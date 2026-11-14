import createClient from 'openapi-fetch'
import type { paths } from './schema'

// Where the backend runs. Override it with VITE_API_BASE_URL in frontend/.env.local (git-ignored).
const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

// Typed from the backend's OpenAPI schema (src/api/schema.d.ts, made by `npm run generate:api`):
// a wrong path, parameter or response field is a compile error.
export const api = createClient<paths>({ baseUrl })
