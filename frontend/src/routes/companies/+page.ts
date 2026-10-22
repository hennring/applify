import { api } from '#lib/api/client.ts';
import type { PageLoad } from './$types';

const STATUSES = ['candidate', 'watch', 'ignore'] as const;
type Status = (typeof STATUSES)[number];

export const load: PageLoad = async ({ fetch, url }) => {
	const raw = url.searchParams.get('status');
	const filters = {
		status: STATUSES.includes(raw as Status) ? (raw as Status) : null,
		feed: url.searchParams.get('feed') === '1',
		q: url.searchParams.get('q') ?? ''
	};
	const { data } = await api.GET('/api/companies', {
		fetch,
		params: {
			query: {
				status: filters.status ?? undefined,
				feed: filters.feed,
				q: filters.q || undefined
			}
		}
	});
	return {
		filters,
		page: data ?? { total: 0, with_feed: 0, watched: 0, pending: 0, items: [] }
	};
};
