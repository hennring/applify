import createClient from 'openapi-fetch';
import type { components, paths } from './schema.d.ts';

// Same origin: in the container FastAPI serves the SPA; in dev mode Vite proxies /api.
export const api = createClient<paths>();

export type Schemas = components['schemas'];

/** User-facing message from a FastAPI error body ({detail: string | validation errors}). */
export function errorMessage(error: unknown): string {
	const detail = (error as { detail?: unknown } | undefined)?.detail;
	if (typeof detail === 'string') return detail;
	if (Array.isArray(detail) && detail.length > 0) {
		return detail
			.map(
				(d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`
			)
			.join('; ');
	}
	return 'Unbekannter Fehler';
}

/** Multipart upload; openapi-fetch does not type FormData bodies. */
export async function uploadDocument(
	type: Schemas['DocumentOut']['type'],
	file: File
): Promise<{ data?: Schemas['DocumentOut']; error?: string }> {
	const body = new FormData();
	body.append('type', type);
	body.append('file', file);
	const response = await fetch('/api/documents', { method: 'POST', body });
	const json: unknown = await response.json().catch(() => undefined);
	return response.ok ? { data: json as Schemas['DocumentOut'] } : { error: errorMessage(json) };
}
