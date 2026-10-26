<script lang="ts" module>
	export type Bar = {
		label: string;
		value: number;
		/** Shown at the bar's end, e.g. "34 %". */
		valueText: string;
		/** Hover and focus details. */
		detail: string;
		/** Small mark after the label, e.g. "im Profil". */
		badge?: string;
	};
</script>

<script lang="ts">
	import { tooltip } from './tooltip';

	let { bars, empty = 'Keine Daten' }: { bars: Bar[]; empty?: string } = $props();

	const max = $derived(Math.max(...bars.map((b) => b.value), 0));
</script>

{#if bars.length === 0}
	<p class="muted">{empty}</p>
{:else}
	<ul class="bars">
		{#each bars as bar (bar.label)}
			<!-- Focusable so keyboard users get the details too; the tooltip action sets aria-label. -->
			<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
			<li use:tooltip={bar.detail} tabindex="0">
				<span class="label"
					>{bar.label}{#if bar.badge}<span class="badge">{bar.badge}</span>{/if}</span
				>
				<span class="track">
					<span class="fill" style:width="{max ? (bar.value / max) * 100 : 0}%"></span>
				</span>
				<span class="value">{bar.valueText}</span>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.bars {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: minmax(6rem, max-content) 1fr auto;
		gap: 0.35rem 0.75rem;
		align-items: center;
	}
	li {
		display: grid;
		grid-template-columns: subgrid;
		grid-column: 1 / -1;
		align-items: center;
		border-radius: 4px;
	}
	li:hover .fill,
	li:focus-visible .fill {
		filter: brightness(1.12);
	}
	li:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.label {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.badge {
		font-size: 0.72rem;
		padding: 0.05rem 0.4rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		color: var(--muted);
	}
	.track {
		display: block;
		height: 0.75rem;
	}
	.fill {
		display: block;
		height: 100%;
		min-width: 2px;
		background: var(--series-1);
		border-radius: 0 4px 4px 0;
	}
	.value {
		color: var(--muted);
		font-variant-numeric: tabular-nums;
		text-align: right;
		font-size: 0.9rem;
	}
</style>
