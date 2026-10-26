import { api } from '#lib/api/client.ts';
import type { PageLoad } from './$types';

const SCOPES = ['area', 'germany', 'all'] as const;
export type Scope = (typeof SCOPES)[number];

export const load: PageLoad = async ({ fetch, url }) => {
	const raw = url.searchParams.get('umfang');
	const role = url.searchParams.get('rolle');
	const filters = {
		scope: SCOPES.includes(raw as Scope) ? (raw as Scope) : ('area' as Scope),
		// Default: the families of the profile's desired roles; "alle" lifts the filter.
		role: role === 'alle' ? '' : (role ?? 'mine'),
		seniority: url.searchParams.get('stufe') ?? '',
		source: url.searchParams.get('quelle') ?? '',
		weeks: Number(url.searchParams.get('wochen')) || 0
	};
	const { data } = await api.GET('/api/market', {
		fetch,
		params: { query: filters }
	});
	return { filters, market: data ?? null };
};
