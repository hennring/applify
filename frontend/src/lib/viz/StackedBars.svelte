<script lang="ts" module>
	export type Segment = { key: string; label: string; color: string };
	export type StackRow = { label: string; total: number; counts: Record<string, number> };
</script>

<script lang="ts">
	import { formatPercent, tooltip } from './tooltip';

	let { rows, segments }: { rows: StackRow[]; segments: Segment[] } = $props();
</script>

<ul class="legend" aria-label="Legende">
	{#each segments as s (s.key)}
		<li><span class="swatch" style:background={s.color}></span>{s.label}</li>
	{/each}
</ul>
<ul class="rows">
	{#each rows as row (row.label)}
		<li>
			<span class="label">{row.label}</span>
			<span class="bar">
				{#each segments as s (s.key)}
					{@const n = row.counts[s.key] ?? 0}
					{#if n > 0}
						<!-- Focusable so keyboard users get the details too; the tooltip action sets aria-label. -->
						<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
						<span
							class="segment"
							style:flex-grow={n}
							style:background={s.color}
							tabindex="0"
							role="img"
							use:tooltip={`${row.label} · ${s.label}\n${n} von ${row.total} Stellen (${formatPercent(n / row.total)})`}
						></span>
					{/if}
				{/each}
			</span>
			<span class="total">{row.total}</span>
		</li>
	{/each}
</ul>

<style>
	.legend {
		list-style: none;
		margin: 0 0 0.6rem;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 0.9rem;
		font-size: 0.85rem;
	}
	.legend li {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.swatch {
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 3px;
	}
	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: minmax(6rem, max-content) 1fr auto;
		gap: 0.4rem 0.75rem;
		align-items: center;
	}
	.rows li {
		display: grid;
		grid-template-columns: subgrid;
		grid-column: 1 / -1;
		align-items: center;
	}
	.label {
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.bar {
		display: flex;
		gap: 2px;
		height: 0.9rem;
	}
	.segment {
		flex-basis: 0;
		min-width: 3px;
	}
	.segment:first-child {
		border-radius: 4px 0 0 4px;
	}
	.segment:last-child {
		border-radius: 0 4px 4px 0;
	}
	.segment:only-child {
		border-radius: 4px;
	}
	.segment:hover,
	.segment:focus-visible {
		filter: brightness(1.12);
		outline: none;
	}
	.total {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
		font-size: 0.9rem;
	}
</style>
