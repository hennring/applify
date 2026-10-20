import createClient from 'openapi-fetch';
import type { components, paths } from './schema.d.ts';

// Same origin: in the container FastAPI serves the SPA; in dev mode Vite proxies /api.
export const api = createClient<paths>();

export type Schemas = components['schemas'];
