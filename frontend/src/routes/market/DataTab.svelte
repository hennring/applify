<script lang="ts">
	import type { Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { formatDateTime, sourceLabels } from '#lib/labels.ts';
	import StackedBars, { type Segment } from '#lib/viz/StackedBars.svelte';
	import TrendChart from '#lib/viz/TrendChart.svelte';
	import { formatPercent } from '#lib/viz/tooltip.ts';

	let { data }: { data: Schemas['MarketData'] } = $props();

	const SOURCE_PARTS: Segment[] = [
		{ key: 'only', label: 'Nur in dieser Quelle', color: 'var(--series-1)' },
		{ key: 'shared', label: 'Auch in anderen Quellen', color: 'var(--ordinal-2)' }
	];

	// Features in fixed order, so each keeps its color.
	const FEATURES = [
		['role_family', 'Rollenfamilie'],
		['seniority', 'Seniorität'],
		['skills', 'Skills'],
		['years', 'Berufsjahre'],
		['salary_eur', 'Gehalt (EUR)']
	] as const;

	const CHECKS: Record<string, string> = {
		feature_coverage: 'Rollenfamilie und Seniorität für mindestens 80 % bestimmt',
		llm_failures: 'Höchstens 10 % ungültige LLM-Antworten'
	};

	const RUN_STATUS: Record<string, string> = {
		running: 'läuft',
		success: 'erfolgreich',
		failed: 'fehlgeschlagen',
		canceled: 'abgebrochen'
	};

	const latest = $derived(data.history.at(-1));
	const sourceLabel = (key: string) => sourceLabels[key] ?? key;
</script>

<div class="tiles">
	<div class="tile">
		<span class="big">{data.sources.length}</span>
		<span class="muted">Quellen mit Stellen</span>
	</div>
	<div class="tile">
		<span class="big">{latest ? latest.llm_queue : '–'}</span>
		<span class="muted">Volltext-Stellen warten auf das LLM</span>
	</div>
	<div class="tile">
		<span class="big">{latest ? formatPercent(latest.coverage.seniority ?? 0) : '–'}</span>
		<span class="muted">mit bestimmter Seniorität (Ziel 80 %)</span>
	</div>
</div>
<p class="muted small">
	Dieser Bereich beschreibt den gesamten Datenbestand; die Filter oben wirken hier nicht.
</p>

<div class="grid">
	<section class="card wide">
		<h2><Icon name="search" size={18} /> Was jede Quelle beiträgt</h2>
		<StackedBars
			segments={SOURCE_PARTS}
			rows={data.sources.map((s) => ({
				label: sourceLabel(s.source),
				total: s.jobs,
				counts: { only: s.only_here, shared: s.jobs - s.only_here }
			}))}
		/>
		<table>
			<thead>
				<tr>
					<th>Quelle</th>
					<th class="num">Stellen</th>
					<th class="num">Nur hier</th>
					<th class="num">Mit Volltext</th>
				</tr>
			</thead>
			<tbody>
				{#each data.sources as s (s.source)}
					<tr>
						<td>{sourceLabel(s.source)}</td>
						<td class="num">{s.jobs}</td>
						<td class="num">{s.only_here} ({formatPercent(s.jobs ? s.only_here / s.jobs : 0)})</td>
						<td class="num">{formatPercent(s.jobs ? s.full_text / s.jobs : 0)}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="muted small">
			„Nur hier“: keine andere Quelle hat dieselbe Stelle geliefert. Eine Quelle mit wenigen
			eindeutigen Stellen bringt vor allem Dubletten.
		</p>
	</section>

	<section class="card wide">
		<h2><Icon name="activity" size={18} /> Abdeckung der Merkmale je Pipeline-Lauf</h2>
		<TrendChart
			weeks={data.history.map((h) => h.recorded_at)}
			series={FEATURES.map(([key, label]) => ({
				skill: label,
				shares: data.history.map((h) => h.coverage[key] ?? 0)
			}))}
			pointLabel={formatDateTime}
			pointName="Pipeline-Lauf"
			ariaLabel="Anteil der Volltext-Stellen mit bestimmtem Merkmal je Pipeline-Lauf"
		/>
		<p class="muted small">Anteil der Volltext-Stellen, bei denen das Merkmal bestimmt ist.</p>
	</section>

	<section class="card">
		<h2><Icon name="circle-check" size={18} /> Prüfungen des letzten Laufs</h2>
		{#if data.checks.length}
			<ul class="checks">
				{#each data.checks as c (c.check_name)}
					<li>
						<Icon
							name={c.passed ? 'circle-check' : 'circle-alert'}
							size={16}
							class={c.passed ? 'ok' : 'warn'}
						/>
						<span>
							{CHECKS[c.check_name] ?? c.check_name}
							<span class="muted small block"
								>{c.passed ? 'erfüllt' : 'nicht erfüllt'} · {formatDateTime(c.checked_at)}</span
							>
						</span>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="muted">Noch keine Prüfergebnisse; sie entstehen beim nächsten Pipeline-Lauf.</p>
		{/if}
		<p class="muted small">Die dbt-Tests stehen zusätzlich in Dagster.</p>
	</section>

	<section class="card">
		<h2><Icon name="clock" size={18} /> Letzte Pipeline-Läufe</h2>
		{#if data.runs.length}
			<table>
				<thead>
					<tr><th>Start</th><th>Status</th><th>Suchlauf</th></tr>
				</thead>
				<tbody>
					{#each data.runs as run (run.started_at)}
						<tr>
							<td>{formatDateTime(run.started_at)}</td>
							<td class:error={run.status === 'failed'}>{RUN_STATUS[run.status] ?? run.status}</td>
							<td class="small">{run.search_run_at ? formatDateTime(run.search_run_at) : '–'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{:else}
			<p class="muted">Noch keine Läufe aufgezeichnet.</p>
		{/if}
	</section>
</div>

<style>
	.checks {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.6rem;
	}
	.checks li {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
	}
</style>
