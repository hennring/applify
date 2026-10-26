import type { Schemas } from './api/client.ts';

type Labels<T extends string> = Record<T, string>;

export const weightLabels: Labels<Schemas['Skill-Output']['weight'] & string> = {
	must: 'Pflicht',
	nice: 'gern',
	avoid: 'will ich nicht'
};

export const skillLevelLabels: Labels<NonNullable<Schemas['Skill-Output']['level']>> = {
	basic: 'Grundlagen',
	good: 'gut',
	expert: 'Experte'
};

export const languageLevelLabels: Labels<Schemas['Language']['level']> = {
	A1: 'A1',
	A2: 'A2',
	B1: 'B1',
	B2: 'B2',
	C1: 'C1',
	C2: 'C2',
	native: 'Muttersprache'
};

export const remoteLabels: Labels<Schemas['ProfileData-Output']['remote_pref'] & string> = {
	no: 'nein, nur vor Ort',
	hybrid: 'hybrid ok',
	remote: 'voll remote ok'
};

export const stationKindLabels: Labels<Schemas['Station-Output']['kind'] & string> = {
	employment: 'Anstellung',
	working_student: 'Werkstudent',
	apprenticeship: 'Ausbildung',
	internship: 'Praktikum'
};

export const jobRemoteLabels: Record<string, string> = {
	hybrid: 'Hybrid',
	remote: 'Remote'
};

export const sourceLabels: Record<string, string> = {
	ba: 'Arbeitsagentur',
	arbeitnow: 'Arbeitnow',
	adzuna: 'Adzuna',
	service_bund: 'service.bund.de',
	careers: 'Karriereseiten',
	'ats:personio': 'Karriereseite (Personio)',
	'ats:greenhouse': 'Karriereseite (Greenhouse)',
	'ats:lever': 'Karriereseite (Lever)',
	'ats:recruitee': 'Karriereseite (Recruitee)',
	'ats:smartrecruiters': 'Karriereseite (SmartRecruiters)',
	'ats:workday': 'Karriereseite (Workday)',
	jsonld: 'Karriereseite'
};

export const atsLabels: Record<string, string> = {
	personio: 'Personio',
	greenhouse: 'Greenhouse',
	lever: 'Lever',
	recruitee: 'Recruitee',
	smartrecruiters: 'SmartRecruiters',
	workday: 'Workday',
	jsonld: 'JSON-LD',
	unknown: 'nicht erkannt'
};

export const companyStatusLabels: Labels<Schemas['CompanyOut']['status']> = {
	candidate: 'Kandidat',
	watch: 'beobachtet',
	ignore: 'ignoriert'
};

export const discoveredLabels: Record<string, string> = {
	jobs: 'aus Stellen',
	github: 'GitHub',
	wikidata: 'Wikidata',
	user: 'manuell'
};

export const runStatusLabels: Record<string, string> = {
	running: 'läuft',
	done: 'fertig',
	failed: 'fehlgeschlagen'
};

export const documentTypeLabels: Labels<Schemas['DocumentOut']['type']> = {
	cv: 'Lebenslauf',
	certificate: 'Zeugnis',
	sample_letter: 'Beispielanschreiben'
};

export const changeFieldLabels: Labels<Schemas['ChangeItem']['field']> = {
	contact: 'Kontakt',
	seniority_years: 'Berufserfahrung',
	roles: 'Wunschrollen',
	skills: 'Skills',
	languages: 'Sprachen',
	experience: 'Werdegang',
	education: 'Ausbildung'
};

export const contactKeyLabels: Record<string, string> = {
	name: 'Name',
	email: 'E-Mail',
	phone: 'Telefon',
	address: 'Adresse'
};

export function formatBytes(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
	return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`;
}

const euro = new Intl.NumberFormat('de-DE', {
	style: 'currency',
	currency: 'EUR',
	maximumFractionDigits: 0
});

/** "50.000 – 60.000 €", "ab 50.000 €", "bis 60.000 €" or null if unknown. */
export function formatSalary(min: number | null, max: number | null): string | null {
	if (min !== null && max !== null) {
		return min === max
			? euro.format(min)
			: `${euro.format(min).replace(/\s?€$/, '')} – ${euro.format(max)}`;
	}
	if (min !== null) return `ab ${euro.format(min)}`;
	if (max !== null) return `bis ${euro.format(max)}`;
	return null;
}

export function formatDate(iso: string): string {
	return new Date(iso).toLocaleDateString('de-DE', { dateStyle: 'medium' });
}

export function formatDateTime(iso: string): string {
	return new Date(iso).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' });
}

/** Human-readable label for a proposed CV change, e.g. "E-Mail" or "Englisch". */
export function changeLabel(change: Schemas['ChangeItem']): string {
	if (change.field === 'contact' && change.key) return contactKeyLabels[change.key] ?? change.key;
	if (change.field === 'languages' && change.key) return change.key;
	return changeFieldLabels[change.field];
}

export function changeValue(change: Schemas['ChangeItem'], value: string): string {
	if (change.field === 'languages') {
		return languageLevelLabels[value as Schemas['Language']['level']] ?? value;
	}
	if (change.field === 'seniority_years') return `${value.replace('.', ',')} Jahre`;
	return value;
}

export const seniorityLabels: Record<string, string> = {
	student: 'Studium/Ausbildung',
	junior: 'Junior',
	mid: 'Mid',
	senior: 'Senior',
	lead: 'Lead',
	unknown: 'Unbekannt'
};

export const marketScopeLabels: Labels<'area' | 'germany' | 'all'> = {
	area: 'Meine Orte',
	germany: 'Deutschland',
	all: 'Alle'
};

export const skillCategoryLabels: Record<string, string> = {
	language: 'Sprache',
	frontend: 'Frontend',
	backend: 'Backend',
	database: 'Datenbank',
	devops: 'DevOps',
	cloud: 'Cloud',
	testing: 'Testing',
	data: 'Data',
	ai: 'KI / ML',
	security: 'Security',
	erp: 'ERP / SAP',
	mobile: 'Mobile',
	cms: 'CMS',
	design: 'Design',
	tool: 'Tool',
	methodology: 'Methode'
};

export const weightBadges: Record<string, string> = {
	must: 'Pflicht',
	nice: 'gern',
	avoid: 'will ich nicht'
};
