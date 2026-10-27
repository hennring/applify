import type { IconName } from '#lib/components/Icon.svelte';
import { seniorityLabels } from '#lib/labels.ts';
import type { Segment } from '#lib/viz/StackedBars.svelte';

export const SCOPES = ['area', 'germany', 'all'] as const;
export type Scope = (typeof SCOPES)[number];

// Tabs of the market page (§5.9); the key is the value of ?reiter= in the URL.
export const TABS = [
	{ key: 'ueberblick', label: 'Überblick', icon: 'activity' },
	{ key: 'daten', label: 'Daten', icon: 'file-text' }
] as const satisfies readonly { key: string; label: string; icon: IconName }[];
export type Tab = (typeof TABS)[number]['key'];

export type Filters = {
	scope: Scope;
	role: string;
	seniority: string;
	source: string;
	weeks: number;
	// False hides staffing agencies and recruiters.
	agencies: boolean;
};

export const WEEKS = [
	{ value: 0, label: 'Gesamter Zeitraum' },
	{ value: 4, label: 'Letzte 4 Wochen' },
	{ value: 12, label: 'Letzte 12 Wochen' }
];

// student → lead from light to dark (ordinal ramp), unknown in gray.
export const SENIORITY: Segment[] = [
	...(['student', 'junior', 'mid', 'senior', 'lead'] as const).map((key, i) => ({
		key,
		label: seniorityLabels[key],
		color: `var(--ordinal-${i + 1})`
	})),
	{ key: 'unknown', label: seniorityLabels.unknown, color: 'var(--viz-unknown)' }
];

export function formatDays(days: number | null | undefined): string {
	if (days === null || days === undefined) return '–';
	return days === 1 ? '1 Tag' : `${days} Tage`;
}
