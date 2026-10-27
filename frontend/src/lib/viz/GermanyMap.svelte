<script lang="ts">
	import { MAP_HEIGHT, MAP_WIDTH, STATES } from './germanyStates';
	import { tooltip } from './tooltip';

	let {
		values,
		format,
		detail,
		label
	}: {
		/** Value per state code ("DE-SN"); missing states count as 0. */
		values: Record<string, number>;
		format: (value: number) => string;
		/** Tooltip text per state code. */
		detail: (code: string) => string;
		label: string;
	} = $props();

	const CLASSES = 5;
	// City states lie inside Brandenburg and Niedersachsen: drawn last, so they stay on top.
	const CITY_STATES = ['DE-BE', 'DE-HB', 'DE-HH'];
	const shapes = [...STATES].sort(
		(a, b) => Number(CITY_STATES.includes(a.code)) - Number(CITY_STATES.includes(b.code))
	);

	const max = $derived(Math.max(0, ...Object.values(values)));
	// Equal steps up to the largest value; light = few, dark = many (ordinal ramp).
	const step = (value: number) => (max ? Math.min(CLASSES, Math.ceil((value / max) * CLASSES)) : 0);
	const fill = (value: number) =>
		step(value) ? `var(--ordinal-${step(value)})` : 'var(--viz-unknown)';
	const legend = $derived(
		Array.from({ length: CLASSES }, (_, i) => ({
			color: `var(--ordinal-${i + 1})`,
			text: `${format((max * i) / CLASSES)}–${format((max * (i + 1)) / CLASSES)}`
		}))
	);
</script>

<figure>
	<svg viewBox="0 0 {MAP_WIDTH} {MAP_HEIGHT}" role="img" aria-label={label}>
		{#each shapes as state (state.code)}
			<!-- Focusable so keyboard users get the details too; the tooltip action sets aria-label. -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<path
				d={state.path}
				fill={fill(values[state.code] ?? 0)}
				fill-rule="evenodd"
				tabindex="0"
				role="img"
				use:tooltip={detail(state.code)}
			/>
		{/each}
	</svg>
	<figcaption>
		<ul class="legend" aria-label="Legende">
			<li><span class="swatch" style:background="var(--viz-unknown)"></span>keine</li>
			{#each legend as item (item.color)}
				<li><span class="swatch" style:background={item.color}></span>{item.text}</li>
			{/each}
		</ul>
	</figcaption>
</figure>

<style>
	figure {
		margin: 0;
	}
	svg {
		display: block;
		width: 100%;
		max-width: 420px;
		height: auto;
		margin: 0 auto;
	}
	path {
		stroke: var(--surface);
		stroke-width: 1.5;
		stroke-linejoin: round;
		outline: none;
	}
	path:hover,
	path:focus-visible {
		stroke: var(--text);
		stroke-width: 2;
	}
	.legend {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.25rem 0.8rem;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.legend li {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.swatch {
		width: 0.8rem;
		height: 0.8rem;
		border-radius: 2px;
	}
</style>
