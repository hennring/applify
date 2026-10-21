import { describe, expect, it } from 'vitest';
import { changeLabel, changeValue, formatBytes, formatSalary } from './labels.ts';

describe('formatBytes', () => {
	it('uses German decimal separator', () => {
		expect(formatBytes(512)).toBe('512 B');
		expect(formatBytes(2048)).toBe('2 KB');
		expect(formatBytes(1.5 * 1024 * 1024)).toBe('1,5 MB');
	});
});

describe('change labels', () => {
	it('labels contact changes by sub-field', () => {
		const change = {
			id: 'contact:email',
			field: 'contact',
			kind: 'add',
			key: 'email',
			current: null,
			suggested: 'a@b.de'
		} as const;
		expect(changeLabel(change)).toBe('E-Mail');
	});

	it('labels languages by name and shows level text', () => {
		const change = {
			id: 'language:deutsch',
			field: 'languages',
			kind: 'add',
			key: 'Deutsch',
			current: null,
			suggested: 'native'
		} as const;
		expect(changeLabel(change)).toBe('Deutsch');
		expect(changeValue(change, change.suggested)).toBe('Muttersprache');
	});

	it('formats years', () => {
		const change = {
			id: 'seniority_years',
			field: 'seniority_years',
			kind: 'add',
			key: null,
			current: null,
			suggested: '4.3'
		} as const;
		expect(changeValue(change, change.suggested)).toBe('4,3 Jahre');
	});
});

describe('formatSalary', () => {
	it('formats ranges, single values and open ends', () => {
		// Intl uses a narrow no-break space before the euro sign.
		const plain = (s: string | null) => s?.replace(/\s/g, ' ');
		expect(plain(formatSalary(50000, 60000))).toBe('50.000 – 60.000 €');
		expect(plain(formatSalary(60000, 60000))).toBe('60.000 €');
		expect(plain(formatSalary(48000, null))).toBe('ab 48.000 €');
		expect(plain(formatSalary(null, 70000))).toBe('bis 70.000 €');
		expect(formatSalary(null, null)).toBeNull();
	});
});
