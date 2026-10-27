<script lang="ts">
	import { formatPercent, tooltip } from './tooltip';

	type Series = { skill: string; shares: number[] };
	const dateFormat = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit' });
	const weekLabel = (iso: string) => `KW ab ${dateFormat.format(new Date(iso))}`;

	let {
		weeks,
		series,
		// Points are weeks by default; other callers pass their own labels.
		pointLabel = weekLabel,
		pointName = 'Woche',
		ariaLabel = 'Anteil der Stellen je Skill und Woche'
	}: {
		weeks: string[];
		series: Series[];
		pointLabel?: (iso: string) => string;
		pointName?: string;
		ariaLabel?: string;
	} = $props();

	// Drawn in real pixels at the container's width, so text keeps its size.
	let W = $state(640);
	const H = 240;
	const pad = { top: 12, right: 120, bottom: 26, left: 44 };
	const innerW = $derived(Math.max(W - pad.left - pad.right, 100));
	const innerH = H - pad.top - pad.bottom;

	let asTable = $state(false);
	let hovered = $state<number | null>(null);

	const top = $derived(
		Math.max(0.1, Math.ceil(Math.max(...series.flatMap((s) => s.shares), 0) * 10) / 10)
	);
	const x = (i: number) => pad.left + (weeks.length > 1 ? (i / (weeks.length - 1)) * innerW : 0);
	const y = (share: number) => pad.top + innerH - (share / top) * innerH;
	const ticks = $derived([0, top / 2, top]);

	// Labels at the line ends, pushed apart so they do not overlap.
	const endLabels = $derived.by(() => {
		const labels = series
			.map((s, i) => ({ skill: s.skill, slot: i + 1, y: y(s.shares.at(-1) ?? 0) }))
			.sort((a, b) => a.y - b.y);
		for (let i = 1; i < labels.length; i++) {
			labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 14);
		}
		return labels;
	});

	function weekDetail(i: number): string {
		const lines = series.map((s) => `${s.skill}: ${formatPercent(s.shares[i])}`);
		return [pointLabel(weeks[i]), ...lines].join('\n');
	}
</script>

<div class="head">
	<ul class="legend" aria-label="Legende">
		{#each series as s, i (s.skill)}
			<li><span class="swatch" style:background="var(--series-{i + 1})"></span>{s.skill}</li>
		{/each}
	</ul>
	<button type="button" class="link" onclick={() => (asTable = !asTable)}>
		{asTable ? 'Als Diagramm' : 'Als Tabelle'}
	</button>
</div>

{#if weeks.length < 2 && !asTable}
	<p class="muted">
		Ein Verlauf wird ab zwei Zeitpunkten sichtbar. Bisher: {weeks.length === 1
			? pointLabel(weeks[0])
			: 'keine Daten'}.
	</p>
{:else if asTable}
	<table>
		<thead>
			<tr>
				<th>{pointName}</th>
				{#each series as s (s.skill)}<th>{s.skill}</th>{/each}
			</tr>
		</thead>
		<tbody>
			{#each weeks as week, i (week)}
				<tr>
					<td>{pointLabel(week)}</td>
					{#each series as s (s.skill)}<td>{formatPercent(s.shares[i])}</td>{/each}
				</tr>
			{/each}
		</tbody>
	</table>
{:else}
	<div class="plot" bind:clientWidth={W}>
		<svg width="100%" height={H} viewBox="0 0 {W} {H}" role="img" aria-label={ariaLabel}>
			{#each ticks as tick (tick)}
				<line class="grid" x1={pad.left} x2={pad.left + innerW} y1={y(tick)} y2={y(tick)} />
				<text class="axis" x={pad.left - 6} y={y(tick)} text-anchor="end" dominant-baseline="middle"
					>{formatPercent(tick)}</text
				>
			{/each}
			{#each weeks as week, i (week)}
				<text class="axis" x={x(i)} y={H - 6} text-anchor="middle"
					>{dateFormat.format(new Date(week))}</text
				>
			{/each}
			{#if hovered !== null}
				<line class="cross" x1={x(hovered)} x2={x(hovered)} y1={pad.top} y2={pad.top + innerH} />
			{/if}
			{#each series as s, i (s.skill)}
				<polyline
					class="line"
					style:stroke="var(--series-{i + 1})"
					points={s.shares.map((v, w) => `${x(w)},${y(v)}`).join(' ')}
				/>
				{#if hovered !== null}
					<circle
						class="dot"
						cx={x(hovered)}
						cy={y(s.shares[hovered])}
						r="4"
						style:fill="var(--series-{i + 1})"
					/>
				{/if}
			{/each}
			{#each endLabels as label (label.skill)}
				<text class="end" x={pad.left + innerW + 8} y={label.y} dominant-baseline="middle"
					>{label.skill}</text
				>
			{/each}
			{#each weeks as week, i (week)}
				<rect
					class="hit"
					x={x(i) - innerW / Math.max(weeks.length - 1, 1) / 2}
					y={pad.top}
					width={innerW / Math.max(weeks.length - 1, 1)}
					height={innerH}
					tabindex="0"
					role="button"
					use:tooltip={weekDetail(i)}
					onpointerenter={() => (hovered = i)}
					onpointerleave={() => (hovered = null)}
					onfocus={() => (hovered = i)}
					onblur={() => (hovered = null)}
				/>
			{/each}
		</svg>
	</div>
{/if}

<style>
	.head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 0.5rem;
	}
	.legend {
		list-style: none;
		margin: 0;
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
		width: 0.9rem;
		height: 3px;
		border-radius: 2px;
	}
	.link {
		border: none;
		background: none;
		color: var(--accent);
		cursor: pointer;
		padding: 0;
		font-size: 0.85rem;
		white-space: nowrap;
	}
	svg {
		display: block;
		overflow: visible;
	}
	.grid {
		stroke: var(--border);
		stroke-width: 1;
	}
	.cross {
		stroke: var(--muted);
		stroke-width: 1;
		stroke-dasharray: 3 3;
	}
	.axis {
		fill: var(--muted);
		font-size: 11px;
	}
	.end {
		fill: var(--text);
		font-size: 12px;
	}
	.line {
		fill: none;
		stroke-width: 2;
		stroke-linejoin: round;
		stroke-linecap: round;
	}
	.dot {
		stroke: var(--surface);
		stroke-width: 2;
	}
	.hit {
		fill: transparent;
		outline: none;
	}
	.hit:focus-visible {
		stroke: var(--accent);
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	th,
	td {
		text-align: left;
		padding: 0.3rem 0.5rem;
		border-bottom: 1px solid var(--border);
		font-variant-numeric: tabular-nums;
	}
</style>
