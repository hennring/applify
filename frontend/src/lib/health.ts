import type { Schemas } from './api/client.ts';

export interface HealthRow {
	label: string;
	ok: boolean;
	detail: string | null;
}

export function healthRows(health: Schemas['Health']): HealthRow[] {
	return [
		{ label: 'Datenbank', component: health.database },
		{ label: 'Ollama', component: health.ollama }
	].map(({ label, component }) => ({
		label,
		ok: component.status === 'ok',
		detail: component.detail ?? null
	}));
}
