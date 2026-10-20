import { api } from '#lib/api/client.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const { data } = await api.GET('/api/health', { fetch });
	return { health: data ?? null };
};
