<script lang="ts" module>
	type Shape = [tag: 'path' | 'circle' | 'rect', attrs: Record<string, string | number>];

	const p = (d: string): Shape => ['path', { d }];
	const circle = (cx: number, cy: number, r: number): Shape => ['circle', { cx, cy, r }];

	// Outlines from Lucide (ISC license), 24×24 viewBox, stroke-based.
	const icons = {
		plus: [p('M5 12h14'), p('M12 5v14')],
		x: [p('M18 6 6 18'), p('m6 6 12 12')],
		pencil: [
			p(
				'M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z'
			),
			p('m15 5 4 4')
		],
		check: [p('M20 6 9 17l-5-5')],
		'chevron-down': [p('m6 9 6 6 6-6')],
		'chevron-up': [p('m18 15-6-6-6 6')],
		user: [p('M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2'), circle(12, 7, 4)],
		mail: [
			['rect', { width: 20, height: 16, x: 2, y: 4, rx: 2 }],
			p('m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7')
		],
		phone: [
			p(
				'M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z'
			)
		],
		'map-pin': [
			p(
				'M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0'
			),
			circle(12, 10, 3)
		],
		house: [
			p('M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8'),
			p(
				'M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'
			)
		],
		briefcase: [
			p('M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16'),
			['rect', { width: 20, height: 14, x: 2, y: 6, rx: 2 }]
		],
		target: [circle(12, 12, 10), circle(12, 12, 6), circle(12, 12, 2)],
		wrench: [
			p(
				'M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z'
			)
		],
		'graduation-cap': [
			p(
				'M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z'
			),
			p('M22 10v6'),
			p('M6 12.5V16a6 3 0 0 0 12 0v-3.5')
		],
		languages: [
			p('m5 8 6 6'),
			p('m4 14 6-6 2-3'),
			p('M2 5h12'),
			p('M7 2h1'),
			p('m22 22-5-10-5 10'),
			p('M14 18h6')
		],
		wallet: [
			p(
				'M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1'
			),
			p('M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4')
		],
		ban: [circle(12, 12, 10), p('m4.9 4.9 14.2 14.2')],
		'pen-line': [
			p('M12 20h9'),
			p(
				'M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z'
			)
		],
		'file-text': [
			p('M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z'),
			p('M14 2v4a2 2 0 0 0 2 2h4'),
			p('M10 9H8'),
			p('M16 13H8'),
			p('M16 17H8')
		],
		loader: [p('M21 12a9 9 0 1 1-6.219-8.56')],
		save: [
			p(
				'M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z'
			),
			p('M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7'),
			p('M7 3v4a1 1 0 0 0 1 1h7')
		],
		trash: [
			p('M3 6h18'),
			p('M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6'),
			p('M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2')
		],
		calendar: [
			p('M8 2v4'),
			p('M16 2v4'),
			['rect', { width: 18, height: 18, x: 3, y: 4, rx: 2 }],
			p('M3 10h18')
		],
		'circle-alert': [circle(12, 12, 10), p('M12 8v4'), p('M12 16h.01')],
		'circle-check': [circle(12, 12, 10), p('m9 12 2 2 4-4')],
		upload: [p('M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'), p('m17 8-5-5-5 5'), p('M12 3v12')]
	} satisfies Record<string, Shape[]>;

	export type IconName = keyof typeof icons;
</script>

<script lang="ts">
	let {
		name,
		size = 18,
		class: className = ''
	}: { name: IconName; size?: number; class?: string } = $props();
</script>

<svg
	class="icon-svg {className}"
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="2"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{#each icons[name] as [tag, attrs], i (i)}
		<svelte:element this={tag} {...attrs} />
	{/each}
</svg>

<style>
	.icon-svg {
		flex-shrink: 0;
		vertical-align: -0.15em;
	}
	.spin {
		animation: spin 1s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
