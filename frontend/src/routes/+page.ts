import { api } from '#lib/api/client.ts';
import type { PageLoad } from './$types';

export const PAGE_SIZE = 50;

export const load: PageLoad = async ({ fetch }) => {
	const [health, run, jobs] = await Promise.all([
		api.GET('/api/health', { fetch }),
		api.GET('/api/runs/latest', { fetch }),
		api.GET('/api/jobs', { fetch, params: { query: { limit: PAGE_SIZE } } })
	]);
	return {
		health: health.data ?? null,
		run: run.data ?? null,
		jobs: jobs.data ?? { total: 0, items: [] }
	};
};
