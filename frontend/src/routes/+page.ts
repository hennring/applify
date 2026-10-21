import { api } from '#lib/api/client.ts';
import { JOB_PAGE_SIZE } from '#lib/jobs.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [health, run, jobs] = await Promise.all([
		api.GET('/api/health', { fetch }),
		api.GET('/api/runs/latest', { fetch }),
		api.GET('/api/jobs', { fetch, params: { query: { limit: JOB_PAGE_SIZE } } })
	]);
	return {
		health: health.data ?? null,
		run: run.data ?? null,
		jobs: jobs.data ?? { total: 0, items: [] }
	};
};
