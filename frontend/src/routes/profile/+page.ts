import { api } from '#lib/api/client.ts';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [profile, changes, documents] = await Promise.all([
		api.GET('/api/profile', { fetch }),
		api.GET('/api/profile/cv-changes', { fetch }),
		api.GET('/api/documents', { fetch })
	]);
	if (!profile.data) error(503, 'Profil konnte nicht geladen werden');
	return {
		profile: profile.data,
		changes: changes.data ?? null,
		extracting: (documents.data ?? []).some(
			(d) => d.type === 'cv' && d.extraction_status === 'running'
		)
	};
};
