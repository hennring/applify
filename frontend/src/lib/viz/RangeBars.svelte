<script lang="ts" module>
	export type Range = {
		label: string;
		p25: number;
		median: number;
		p75: number;
		/** Jobs stating a salary, and all jobs in the group. */
		n: number;
		total: number;
	};
</script>

<script lang="ts">
	import { formatEuro, formatPercent, formatThousands, tooltip } from './tooltip';

	let { ranges }: { ranges: Range[] } = $props();

	const low = $derived(Math.floor(Math.min(...ranges.map((r) => r.p25)) / 10_000) * 10_000);
	const high = $derived(Math.ceil(Math.max(...ranges.map((r) => r.p75)) / 10_000) * 10_000);
	const pos = (value: number) => (high > low ? ((value - low) / (high - low)) * 100 : 50);
	const ticks = $derived.by(() => {
		const step = high - low > 60_000 ? 20_000 : 10_000;
		const values: number[] = [];
		for (let v = low; v <= high; v += step) values.push(v);
		return values;
	});
</script>

<ul class="rows">
	{#each ranges as r (r.label)}
		<!-- Focusable so keyboard users get the details too; the tooltip action sets aria-label. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<li
			tabindex="0"
			use:tooltip={`${r.label}\nMedian ${formatEuro(r.median)}\nMittlere Hälfte ${formatEuro(r.p25)} – ${formatEuro(r.p75)}\n${r.n} von ${r.total} Stellen nennen ein Gehalt (${formatPercent(r.n / r.total)})`}
		>
			<span class="label">{r.label}</span>
			<span class="track">
				<span
					class="band"
					style:left="{pos(r.p25)}%"
					style:width="{Math.max(pos(r.p75) - pos(r.p25), 0.8)}%"
				></span>
				<span class="median" style:left="{pos(r.median)}%"></span>
			</span>
			<span class="value">{formatThousands(r.median)}</span>
			<span class="n">n = {r.n}</span>
		</li>
	{/each}
	<li class="axis" aria-hidden="true">
		<span></span>
		<span class="ticks">
			{#each ticks as t (t)}
				<span style:left="{pos(t)}%">{formatThousands(t)}</span>
			{/each}
		</span>
		<span></span>
		<span></span>
	</li>
</ul>
<p class="muted note">
	Balken: mittlere Hälfte der Gehälter (25.–75. Perzentil), Strich: Median, brutto pro Jahr. Nur
	Angaben in Euro.
</p>

<style>
	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: minmax(6rem, max-content) 1fr auto auto;
		gap: 0.45rem 0.75rem;
		align-items: center;
	}
	.rows li {
		display: grid;
		grid-template-columns: subgrid;
		grid-column: 1 / -1;
		align-items: center;
		border-radius: 4px;
	}
	.rows li:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.label {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.track {
		position: relative;
		height: 0.9rem;
		border-radius: 4px;
		background: color-mix(in srgb, var(--border) 45%, transparent);
	}
	.band {
		position: absolute;
		top: 0;
		bottom: 0;
		background: var(--series-1);
		border-radius: 4px;
	}
	.median {
		position: absolute;
		top: -3px;
		bottom: -3px;
		width: 3px;
		margin-left: -1.5px;
		background: var(--text);
		border: 1px solid var(--surface);
		border-radius: 2px;
	}
	.value,
	.n {
		font-variant-numeric: tabular-nums;
		font-size: 0.9rem;
	}
	.n {
		color: var(--muted);
	}
	.axis .ticks {
		position: relative;
		height: 1rem;
		font-size: 0.75rem;
		color: var(--muted);
	}
	.axis .ticks span {
		position: absolute;
		transform: translateX(-50%);
		white-space: nowrap;
	}
	.note {
		font-size: 0.8rem;
		margin: 0.75rem 0 0;
	}
</style>
