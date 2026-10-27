import { api } from '#lib/api/client.ts';
import type { PageLoad } from './$types';
import { SCOPES, TABS, type Filters, type Scope, type Tab } from './market';

export const load: PageLoad = async ({ fetch, url }) => {
	const raw = url.searchParams.get('umfang');
	const role = url.searchParams.get('rolle');
	const tabParam = url.searchParams.get('reiter');
	const tab: Tab = TABS.find((t) => t.key === tabParam)?.key ?? 'ueberblick';
	const filters: Filters = {
		scope: SCOPES.includes(raw as Scope) ? (raw as Scope) : 'area',
		// Default: the families of the profile's desired roles; "alle" lifts the filter.
		role: role === 'alle' ? '' : (role ?? 'mine'),
		seniority: url.searchParams.get('stufe') ?? '',
		source: url.searchParams.get('quelle') ?? '',
		weeks: Number(url.searchParams.get('wochen')) || 0,
		agencies: url.searchParams.get('pd') !== 'nein'
	};
	// The overview carries status and filter options for every tab; each tab loads its own data.
	const [overview, tabData] = await Promise.all([
		api.GET('/api/market', { fetch, params: { query: filters } }),
		tab === 'daten' ? api.GET('/api/market/data', { fetch }) : null
	]);
	return {
		tab,
		filters,
		market: overview.data ?? null,
		marketData: tabData?.data ?? null
	};
};
