/** Jobs per page on the daily list. */
export const JOB_PAGE_SIZE = 50;

/** Minimum score choices on the job search; 0 = all. */
export const MIN_SCORES = [0, 50, 70] as const;

/** Town size ranges by inhabitants, min inclusive and max exclusive; key is the URL value. */
export const TOWN_SIZES = [
	{ key: '150000-300000', label: '150.000–300.000', min: 150_000, max: 300_000 },
	{ key: '100000-150000', label: '100.000–150.000', min: 100_000, max: 150_000 },
	{ key: '0-100000', label: 'unter 100.000', min: undefined, max: 100_000 }
] as const;

export type TownSize = (typeof TOWN_SIZES)[number];

/** A number from the query string if it is one of the choices, else the fallback. */
export function choice<T extends number>(
	raw: string | null,
	choices: readonly T[],
	fallback: T
): T {
	return choices.find((c) => String(c) === raw) ?? fallback;
}

export function formatPopulation(population: number): string {
	return `${population.toLocaleString('de-DE')} Einw.`;
}
