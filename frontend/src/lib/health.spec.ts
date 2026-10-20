import { describe, expect, it } from 'vitest';
import { healthRows } from './health.ts';

describe('healthRows', () => {
	it('maps components to labelled rows', () => {
		const rows = healthRows({
			status: 'error',
			database: { status: 'ok' },
			ollama: { status: 'error', detail: 'Modell qwen3:14b nicht installiert' }
		});

		expect(rows).toEqual([
			{ label: 'Datenbank', ok: true, detail: null },
			{ label: 'Ollama', ok: false, detail: 'Modell qwen3:14b nicht installiert' }
		]);
	});
});
