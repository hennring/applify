import { api } from '#lib/api/client.ts';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const jobId = Number(params.id);
	if (!Number.isInteger(jobId)) error(404, 'Stelle nicht gefunden');
	const { data, response } = await api.GET('/api/matches/{job_id}', {
		fetch,
		params: { path: { job_id: jobId } }
	});
	if (!data) error(response.status === 404 ? 404 : 503, 'Stelle konnte nicht geladen werden');
	return { match: data };
};
