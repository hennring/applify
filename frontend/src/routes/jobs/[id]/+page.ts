import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => {
	const jobId = Number(params.id);
	if (!Number.isInteger(jobId)) error(404, 'Stelle nicht gefunden');
	return { jobId };
};
