import type { Action } from 'svelte/action';

/** Hover and focus tooltip for chart marks; the text may contain line breaks. */
export const tooltip: Action<HTMLElement | SVGElement, string> = (node, text) => {
	let current = text;
	let tip: HTMLDivElement | null = null;

	function place(x: number, y: number) {
		if (!tip) return;
		const { width, height } = tip.getBoundingClientRect();
		const left = Math.min(x + 12, window.innerWidth - width - 8);
		const top = y - height - 10 < 8 ? y + 16 : y - height - 10;
		tip.style.left = `${Math.max(8, left)}px`;
		tip.style.top = `${top}px`;
	}
	function show(x: number, y: number) {
		tip ??= document.body.appendChild(document.createElement('div'));
		tip.className = 'viz-tip';
		tip.setAttribute('role', 'tooltip');
		tip.textContent = current;
		place(x, y);
	}
	function hide() {
		tip?.remove();
		tip = null;
	}
	const enter = (e: Event) => {
		const { clientX, clientY } = e as PointerEvent;
		show(clientX, clientY);
	};
	const move = (e: Event) => {
		const { clientX, clientY } = e as PointerEvent;
		place(clientX, clientY);
	};
	const focus = () => {
		const r = node.getBoundingClientRect();
		show(r.left + r.width / 2, r.top);
	};

	node.setAttribute('aria-label', text.replace(/\n/g, ', '));
	node.addEventListener('pointerenter', enter);
	node.addEventListener('pointermove', move);
	node.addEventListener('pointerleave', hide);
	node.addEventListener('focus', focus);
	node.addEventListener('blur', hide);
	return {
		update(next) {
			current = next;
			node.setAttribute('aria-label', next.replace(/\n/g, ', '));
			if (tip) tip.textContent = next;
		},
		destroy() {
			hide();
			node.removeEventListener('pointerenter', enter);
			node.removeEventListener('pointermove', move);
			node.removeEventListener('pointerleave', hide);
			node.removeEventListener('focus', focus);
			node.removeEventListener('blur', hide);
		}
	};
};

const percent = new Intl.NumberFormat('de-DE', { style: 'percent', maximumFractionDigits: 0 });
const euro = new Intl.NumberFormat('de-DE', {
	style: 'currency',
	currency: 'EUR',
	maximumFractionDigits: 0
});

export const formatPercent = (share: number) => percent.format(share);
export const formatEuro = (value: number) => euro.format(Math.round(value / 500) * 500);
export const formatThousands = (value: number) => `${Math.round(value / 1000)} k`;
