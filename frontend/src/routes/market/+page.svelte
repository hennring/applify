<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import Icon, { type IconName } from '#lib/components/Icon.svelte';
	import {
		formatDateTime,
		marketScopeLabels,
		seniorityLabels,
		skillCategoryLabels,
		sourceLabels,
		weightBadges
	} from '#lib/labels.ts';
	import BarList, { type Bar } from '#lib/viz/BarList.svelte';
	import RangeBars from '#lib/viz/RangeBars.svelte';
	import StackedBars, { type Segment } from '#lib/viz/StackedBars.svelte';
	import TrendChart from '#lib/viz/TrendChart.svelte';
	import { formatPercent } from '#lib/viz/tooltip.ts';
	import type { PageProps } from './$types';
	import type { Scope } from './+page';

	type Filters = PageProps['data']['filters'];
	type SkillDemand = Schemas['SkillDemand'];

	let { data }: PageProps = $props();

	const market = $derived(data.market);
	const filters = $derived(data.filters);

	const DAGSTER_RUNS = 'http://localhost:3000/runs';

	// Where the analysis pipeline stands relative to the newest search run.
	type AnalysisLine = {
		icon: IconName;
		tone: string;
		text: string;
		since: string;
		failed?: boolean;
	};

	const analysis = $derived.by((): AnalysisLine | null => {
		const a = market?.analysis;
		if (!a) return null;
		const at = (iso: string | null | undefined) => (iso ? formatDateTime(iso) : '–');
		const since = a.analyzed_at
			? `Stand ${at(a.analyzed_at)}` + (a.search_run_at ? ` (Suchlauf ${at(a.search_run_at)})` : '')
			: '';
		switch (a.state) {
			case 'running':
				return {
					icon: 'loader',
					tone: 'spin',
					text: `Analyse läuft seit ${at(a.started_at)}`,
					since
				};
			case 'failed':
				return {
					icon: 'circle-alert',
					tone: 'error',
					text: `Letzte Analyse vom ${at(a.started_at)} fehlgeschlagen`,
					failed: true,
					since
				};
			case 'pending':
				return {
					icon: 'clock',
					tone: 'warn',
					text: `Suchlauf ${at(a.latest_search_run_at)} wartet auf die Analyse – läuft Analytics (Dagster)?`,
					since
				};
			case 'current':
				return { icon: 'circle-check', tone: 'ok', text: 'Analyse aktuell', since };
			default:
				// Runs before the status was recorded: only the extraction time is known.
				return market?.status?.extracted_at
					? {
							icon: 'clock',
							tone: 'muted',
							text: `Stand ${at(market.status.extracted_at)}`,
							since: ''
						}
					: null;
		}
	});

	// Reload while the pipeline works or is about to start; it records its end itself.
	$effect(() => {
		const state = market?.analysis.state;
		if (state !== 'running' && state !== 'pending') return;
		const timer = setInterval(() => invalidateAll(), 15000);
		return () => clearInterval(timer);
	});

	const WEEKS = [
		{ value: 0, label: 'Gesamter Zeitraum' },
		{ value: 4, label: 'Letzte 4 Wochen' },
		{ value: 12, label: 'Letzte 12 Wochen' }
	];
	// student → lead from light to dark (ordinal ramp), unknown in gray.
	const SENIORITY: Segment[] = [
		...(['student', 'junior', 'mid', 'senior', 'lead'] as const).map((key, i) => ({
			key,
			label: seniorityLabels[key],
			color: `var(--ordinal-${i + 1})`
		})),
		{ key: 'unknown', label: seniorityLabels.unknown, color: 'var(--viz-unknown)' }
	];

	function href(next: Partial<Filters>): string {
		const f = { ...filters, ...next };
		const params = [
			f.scope !== 'area' && `umfang=${f.scope}`,
			f.role !== 'mine' && `rolle=${encodeURIComponent(f.role || 'alle')}`,
			f.seniority && `stufe=${f.seniority}`,
			f.source && `quelle=${encodeURIComponent(f.source)}`,
			f.weeks && `wochen=${f.weeks}`
		].filter(Boolean);
		return `${resolve('/market')}${params.length ? `?${params.join('&')}` : ''}`;
	}

	function filter(next: Partial<Filters>) {
		// Same route, only the query string changes.
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		return goto(href(next), { replace: true, reset: false });
	}

	function skillBars(skills: SkillDemand[]): Bar[] {
		return skills.map((s) => ({
			label: s.skill,
			value: s.share,
			valueText: formatPercent(s.share),
			badge: s.profile_weight ? weightBadges[s.profile_weight] : undefined,
			detail: [
				s.skill,
				`${s.jobs} Stellen (${formatPercent(s.share)} der Auswahl)`,
				`Kategorie: ${skillCategoryLabels[s.category] ?? s.category}`,
				s.profile_weight
					? `In deinem Profil: ${weightBadges[s.profile_weight]}`
					: 'Nicht in deinem Profil'
			].join('\n')
		}));
	}

	const roleLabel = $derived(
		filters.role === 'mine'
			? 'deinen Zielrollen'
			: filters.role
				? (market?.options?.role_families.find((r) => r.key === filters.role)?.label ??
					filters.role)
				: 'allen Rollen'
	);

	// --- skill candidates -------------------------------------------------------------------
	let categoryOf = $state<Record<string, string>>({});
	let accepting = $state<string | null>(null);
	let candidateMessage = $state<{ kind: 'ok' | 'error'; text: string } | null>(null);

	async function accept(name: string) {
		const category = categoryOf[name];
		if (!category) return;
		accepting = name;
		candidateMessage = null;
		const { data: result, error } = await api.POST('/api/market/skill-candidates', {
			body: { name, category }
		});
		accepting = null;
		if (error || !result) {
			candidateMessage = { kind: 'error', text: errorMessage(error) };
			return;
		}
		candidateMessage = {
			kind: 'ok',
			text: `${result.name} ist jetzt in der Taxonomie (${result.jobs_rescanned} Stellen neu bewertet). In der Auswertung erscheint der Skill nach dem nächsten Pipeline-Lauf.`
		};
		await invalidateAll();
	}
</script>

<div class="pagehead">
	<h1><Icon name="activity" size={28} /> Markt</h1>
	{#if market?.totals}
		<span class="muted status">{market.totals.jobs} Stellen</span>
	{/if}
</div>

{#if analysis}
	<p class="analysis" role="status">
		<Icon name={analysis.icon} size={16} class={analysis.tone} />
		<span>
			{analysis.text}
			{#if analysis.failed}
				– Details in <a href={DAGSTER_RUNS} target="_blank" rel="noreferrer">Dagster</a>.
			{/if}
			{#if analysis.since}<span class="muted"> · {analysis.since}</span>{/if}
		</span>
	</p>
{/if}

{#if !market}
	<p class="card error">Die Marktdaten konnten nicht geladen werden.</p>
{:else if !market.available}
	<section class="card empty">
		<h2>Noch keine Auswertung</h2>
		<p>
			Die Marktanalyse entsteht in der Analyse-Pipeline (Dagster + dbt). Starte sie einmal über die
			Run-Konfiguration <strong>Analytics (Dagster)</strong> und dort den Job
			<code>market_pipeline</code>; danach läuft sie nach jedem Suchlauf automatisch.
		</p>
	</section>
{:else}
	<div class="filters">
		<div class="segmented" role="group" aria-label="Umfang">
			{#each Object.entries(marketScopeLabels) as [value, label] (value)}
				<button
					type="button"
					class:on={filters.scope === value}
					aria-pressed={filters.scope === value}
					onclick={() => filter({ scope: value as Scope })}>{label}</button
				>
			{/each}
		</div>
		<select
			aria-label="Rolle"
			value={filters.role}
			onchange={(e) => filter({ role: e.currentTarget.value })}
		>
			<option value="mine">Meine Zielrollen</option>
			<option value="">Alle Rollen</option>
			{#each market.options?.role_families ?? [] as family (family.key)}
				<option value={family.key}>{family.label}</option>
			{/each}
		</select>
		<select
			aria-label="Seniorität"
			value={filters.seniority}
			onchange={(e) => filter({ seniority: e.currentTarget.value })}
		>
			<option value="">Alle Stufen</option>
			{#each SENIORITY as s (s.key)}<option value={s.key}>{s.label}</option>{/each}
		</select>
		<select
			aria-label="Quelle"
			value={filters.source}
			onchange={(e) => filter({ source: e.currentTarget.value })}
		>
			<option value="">Alle Quellen</option>
			{#each market.options?.sources ?? [] as source (source)}
				<option value={source}>{sourceLabels[source] ?? source}</option>
			{/each}
		</select>
		<select
			aria-label="Zeitraum"
			value={filters.weeks}
			onchange={(e) => filter({ weeks: Number(e.currentTarget.value) })}
		>
			{#each WEEKS as w (w.value)}<option value={w.value}>{w.label}</option>{/each}
		</select>
	</div>

	{#if market.totals && market.coverage}
		<div class="tiles">
			<div class="tile">
				<span class="big">{market.totals.jobs}</span>
				<span class="muted">Stellen, davon {market.totals.full_text} mit Volltext</span>
			</div>
			{#each [['Rollenfamilie', market.coverage.role_family], ['Seniorität', market.coverage.seniority], ['Berufsjahre', market.coverage.years], ['Gehalt', market.coverage.salary]] as [label, share] (label)}
				<div class="tile">
					<span class="big">{formatPercent(share as number)}</span>
					<span class="muted">mit Angabe zu {label}</span>
				</div>
			{/each}
		</div>
		<p class="muted small">
			Anteile beziehen sich auf die Volltext-Stellen der Auswahl. Fehlende Angaben werden nicht
			geschätzt, nur ausgelassen.
		</p>
	{/if}

	{#if market.totals?.full_text === 0}
		<p class="card muted">Für diese Auswahl gibt es keine Stellen mit Volltext.</p>
	{:else}
		<div class="grid">
			<section class="card">
				<h2><Icon name="target" size={18} /> Gefragte Skills in {roleLabel}</h2>
				<BarList bars={skillBars(market.skills.slice(0, 15))} />
			</section>

			<section class="card">
				<h2><Icon name="circle-alert" size={18} /> Gefragt, aber nicht in deinem Profil</h2>
				<BarList
					bars={skillBars(market.gaps.slice(0, 10))}
					empty="Alle gefragten Skills stehen in deinem Profil."
				/>
				<p class="muted small">
					Skills, die du ausdrücklich nicht willst, zählen als „im Profil“. <a
						href={resolve('/profile')}>Profil bearbeiten</a
					>
				</p>
			</section>

			<section class="card wide">
				<h2><Icon name="activity" size={18} /> Verlauf der Top-Skills</h2>
				{#if market.trend}
					<TrendChart weeks={market.trend.weeks} series={market.trend.series} />
				{/if}
				<p class="muted small">Anteil der Stellen je Woche ihrer ersten Sichtung.</p>
			</section>

			<section class="card">
				<h2><Icon name="briefcase" size={18} /> Seniorität je Rollenfamilie</h2>
				<StackedBars
					segments={SENIORITY}
					rows={market.seniority.slice(0, 10).map((r) => ({
						label: r.label,
						total: r.total,
						counts: r.counts
					}))}
				/>
			</section>

			<section class="card">
				<h2><Icon name="clock" size={18} /> Geforderte Berufserfahrung</h2>
				<BarList
					bars={market.years.map((b) => {
						const total = market.years.reduce((sum, y) => sum + y.jobs, 0);
						const share = total ? b.jobs / total : 0;
						return {
							label: `${b.bucket} Jahre`,
							value: b.jobs,
							valueText: `${b.jobs}`,
							detail: `${b.bucket} Jahre: ${b.jobs} Stellen (${formatPercent(share)} der Stellen mit Angabe)`
						};
					})}
				/>
				<p class="muted small">
					Mindestanforderung laut Anzeige; {formatPercent(market.coverage?.years ?? 0)} der Stellen nennen
					eine.
				</p>
			</section>

			<section class="card">
				<h2><Icon name="wallet" size={18} /> Gehälter</h2>
				{#if market.salary.length}
					<RangeBars
						ranges={market.salary.map((s) => ({
							...s,
							label:
								filters.role && filters.role !== 'mine'
									? (seniorityLabels[s.label] ?? s.label)
									: s.label
						}))}
					/>
				{:else}
					<p class="muted">Keine Stelle dieser Auswahl nennt ein Gehalt in Euro.</p>
				{/if}
			</section>

			<section class="card">
				<h2><Icon name="languages" size={18} /> Oft zusammen gefragt</h2>
				{#if market.pairs.length}
					<BarList
						bars={market.pairs.map((p) => ({
							label: `${p.skill_a} + ${p.skill_b}`,
							value: p.jobs,
							valueText: `${p.jobs}`,
							detail: `${p.skill_a} und ${p.skill_b} in ${p.jobs} Stellen`
						}))}
					/>
				{:else}
					<p class="muted">Zu wenige Stellen für Kombinationen.</p>
				{/if}
			</section>

			<section class="card wide">
				<h2><Icon name="plus" size={18} /> Neue Skill-Kandidaten</h2>
				<p class="muted small">
					Technologien, die das lokale LLM in Anzeigen gefunden hat und die noch nicht in der
					Skill-Taxonomie stehen. Übernommene Skills zählen ab dann auch im Matching.
				</p>
				{#if candidateMessage}
					<p class={candidateMessage.kind}>{candidateMessage.text}</p>
				{/if}
				{#if market.candidates.length}
					<table>
						<thead>
							<tr><th>Technologie</th><th>Stellen</th><th>Kategorie</th><th></th></tr>
						</thead>
						<tbody>
							{#each market.candidates as c (c.name)}
								<tr>
									<td>{c.name}</td>
									<td class="num">{c.jobs}</td>
									<td>
										<select aria-label="Kategorie für {c.name}" bind:value={categoryOf[c.name]}>
											<option value={undefined}>wählen …</option>
											{#each market.categories as category (category)}
												<option value={category}>{skillCategoryLabels[category] ?? category}</option
												>
											{/each}
										</select>
									</td>
									<td>
										<button
											type="button"
											disabled={!categoryOf[c.name] || accepting !== null}
											onclick={() => accept(c.name)}
										>
											<Icon name={accepting === c.name ? 'loader' : 'check'} size={14} />
											Übernehmen
										</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{:else}
					<p class="muted">
						Noch keine Kandidaten. Sie entstehen, sobald das lokale LLM Anzeigen ausgewertet hat
						(bisher {market.status?.jobs_with_llm ?? 0} Stellen).
					</p>
				{/if}
			</section>
		</div>
	{/if}
{/if}

<style>
	.status {
		font-size: 0.9rem;
	}
	.analysis {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin: -0.5rem 0 1rem;
		font-size: 0.9rem;
	}
	.filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		margin-bottom: 1rem;
	}
	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
		gap: 0.75rem;
	}
	.tile {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.8rem 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	.big {
		font-size: 1.6rem;
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
	.small {
		font-size: 0.85rem;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
		align-items: start;
		margin-top: 1rem;
	}
	.grid .card {
		margin: 0;
	}
	.wide {
		grid-column: 1 / -1;
	}
	@media (max-width: 1000px) {
		.grid {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.card h2 {
		display: flex;
		align-items: center;
		gap: 0.45rem;
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		text-align: left;
		padding: 0.35rem 0.5rem;
		border-bottom: 1px solid var(--border);
	}
	.num {
		font-variant-numeric: tabular-nums;
	}
	td button {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.empty code {
		font-size: 0.9em;
	}
</style>
