/** Jobs per page on the daily list. */
export const JOB_PAGE_SIZE = 50;

/** Minimum score choices on the job search; 0 = all. */
export const MIN_SCORES = [0, 50, 70] as const;

/** Town size choices by inhabitants; null = all. Kleinstadt < 20,000, Mittelstadt < 100,000. */
export const MAX_POPULATIONS = [
	{ value: null, label: 'Alle Orte' },
	{ value: 100_000, label: 'bis 100.000', title: 'Keine Großstädte' },
	{ value: 20_000, label: 'bis 20.000', title: 'Kleinstädte und Dörfer' },
	{ value: 5_000, label: 'bis 5.000', title: 'Dörfer' }
] as const;

/** A number from the query string if it is one of the choices, else the fallback. */
export function choice<T extends number | null>(
	raw: string | null,
	choices: readonly T[],
	fallback: T
): T {
	return choices.find((c) => c !== null && String(c) === raw) ?? fallback;
}

export function formatPopulation(population: number): string {
	return `${population.toLocaleString('de-DE')} Einw.`;
}
