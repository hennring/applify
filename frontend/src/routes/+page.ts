import { api } from '#lib/api/client.ts';
import { JOB_PAGE_SIZE } from '#lib/jobs.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const filters = {
		onlyNew: url.searchParams.get('neu') === '1',
		excluded: url.searchParams.get('ausgeblendet') === '1',
		sort: url.searchParams.get('sort') === 'datum' ? ('date' as const) : ('score' as const)
	};
	const [health, run, matches] = await Promise.all([
		api.GET('/api/health', { fetch }),
		api.GET('/api/runs/latest', { fetch }),
		api.GET('/api/matches', {
			fetch,
			params: {
				query: {
					only_new: filters.onlyNew,
					excluded: filters.excluded,
					sort: filters.sort,
					limit: JOB_PAGE_SIZE
				}
			}
		})
	]);
	return {
		filters,
		health: health.data ?? null,
		run: run.data ?? null,
		matches: matches.data ?? { total: 0, new: 0, excluded: 0, items: [] }
	};
};
