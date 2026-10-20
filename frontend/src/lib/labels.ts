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
