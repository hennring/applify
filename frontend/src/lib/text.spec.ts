import { describe, expect, it } from 'vitest';
import { textBlocks } from './text.ts';

describe('textBlocks', () => {
	it('splits headings, lists and paragraphs', () => {
		const text =
			'# Deine Aufgaben\n\n- Entwicklung mit **Vue**\n* Code Reviews\n\nWir sind\nein Team.';
		expect(textBlocks(text)).toEqual([
			{ kind: 'heading', text: 'Deine Aufgaben' },
			{ kind: 'list', items: ['Entwicklung mit Vue', 'Code Reviews'] },
			{ kind: 'paragraph', text: 'Wir sind ein Team.' }
		]);
	});

	it('ends a list when a paragraph follows directly', () => {
		expect(textBlocks('• eins\n• zwei\nDanach Text')).toEqual([
			{ kind: 'list', items: ['eins', 'zwei'] },
			{ kind: 'paragraph', text: 'Danach Text' }
		]);
	});
});
