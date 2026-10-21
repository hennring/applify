export type TextBlock =
	| { kind: 'heading'; text: string }
	| { kind: 'list'; items: string[] }
	| { kind: 'paragraph'; text: string };

const BULLET = /^\s*(?:[-*•–]|\d+[.)])\s+/;

/** Strip inline Markdown that would show up as noise (**bold**, __bold__, `code`). */
function inline(text: string): string {
	return text
		.replace(/(\*\*|__)(.+?)\1/g, '$2')
		.replace(/`([^`]+)`/g, '$1')
		.trim();
}

/**
 * Posting text (plain or light Markdown, as from the BA) as blocks for safe rendering
 * without {@html}: headings, bullet lists and paragraphs.
 */
export function textBlocks(text: string): TextBlock[] {
	const blocks: TextBlock[] = [];
	let paragraph: string[] = [];
	let list: string[] = [];
	const flush = () => {
		if (paragraph.length) blocks.push({ kind: 'paragraph', text: inline(paragraph.join(' ')) });
		if (list.length) blocks.push({ kind: 'list', items: list });
		paragraph = [];
		list = [];
	};
	for (const raw of text.replace(/\r\n?/g, '\n').split('\n')) {
		const line = raw.trim();
		if (!line) {
			flush();
		} else if (/^#{1,6}\s/.test(line)) {
			flush();
			blocks.push({ kind: 'heading', text: inline(line.replace(/^#+\s*/, '')) });
		} else if (BULLET.test(line)) {
			if (paragraph.length) flush();
			list.push(inline(line.replace(BULLET, '')));
		} else {
			if (list.length) flush();
			paragraph.push(line);
		}
	}
	flush();
	return blocks;
}
