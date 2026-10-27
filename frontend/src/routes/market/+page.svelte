<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Icon, { type IconName } from '#lib/components/Icon.svelte';
	import { formatDateTime, marketScopeLabels, sourceLabels } from '#lib/labels.ts';
	import { formatPercent } from '#lib/viz/tooltip.ts';
	import type { PageProps } from './$types';
	import './market.css';
	import { SENIORITY, TABS, WEEKS, type Filters, type Scope, type Tab } from './market';
	import DataTab from './DataTab.svelte';
	import DynamicsTab from './DynamicsTab.svelte';
	import EmployersTab from './EmployersTab.svelte';
	import MeTab from './MeTab.svelte';
	import Overview from './Overview.svelte';
	import RegionsTab from './RegionsTab.svelte';

	let { data }: PageProps = $props();

	const market = $derived(data.market);
	const filters = $derived(data.filters);
	const tab = $derived(data.tab);

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

	// Query string of the page with changed filters or another tab.
	function query(next: Partial<Filters>, nextTab: Tab = tab): string {
		const f = { ...filters, ...next };
		const params = [
			nextTab !== 'ueberblick' && `reiter=${nextTab}`,
			f.scope !== 'area' && `umfang=${f.scope}`,
			f.role !== 'mine' && `rolle=${encodeURIComponent(f.role || 'alle')}`,
			f.seniority && `stufe=${f.seniority}`,
			f.source && `quelle=${encodeURIComponent(f.source)}`,
			f.weeks && `wochen=${f.weeks}`,
			!f.agencies && 'pd=nein'
		].filter(Boolean);
		return params.length ? `?${params.join('&')}` : '';
	}

	function filter(next: Partial<Filters>) {
		// Same route, only the query string changes.
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		return goto(`${resolve('/market')}${query(next)}`, { replace: true, reset: false });
	}

	const roleLabel = $derived(
		filters.role === 'mine'
			? 'deinen Zielrollen'
			: filters.role
				? (market?.options?.role_families.find((r) => r.key === filters.role)?.label ??
					filters.role)
				: 'allen Rollen'
	);
</script>

<div class="market">
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
				Die Marktanalyse entsteht in der Analyse-Pipeline (Dagster + dbt). Starte sie einmal über
				die Run-Konfiguration <strong>Analytics (Dagster)</strong> und dort den Job
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
			<label class="check">
				<input
					type="checkbox"
					checked={!filters.agencies}
					onchange={(e) => filter({ agencies: !e.currentTarget.checked })}
				/>
				ohne Personaldienstleister
				{#if market.totals && filters.agencies}
					<span class="muted"
						>({market.totals.agencies}, {formatPercent(
							market.totals.jobs ? market.totals.agencies / market.totals.jobs : 0
						)})</span
					>
				{/if}
			</label>
		</div>

		<nav class="tabs" aria-label="Bereiche der Marktanalyse">
			{#each TABS as t (t.key)}
				<a
					href="{resolve('/market')}{query({}, t.key)}"
					aria-current={tab === t.key ? 'page' : undefined}
					data-sveltekit-noscroll><Icon name={t.icon} size={16} /> {t.label}</a
				>
			{/each}
		</nav>

		{#if tab === 'ueberblick'}
			<Overview {market} {filters} {roleLabel} />
		{:else if tab === 'ich' && data.me}
			<MeTab me={data.me} />
		{:else if tab === 'arbeitgeber' && data.employers}
			<EmployersTab employers={data.employers} agencies={market.totals?.agencies ?? 0} />
		{:else if tab === 'regionen' && data.regions}
			<RegionsTab regions={data.regions} />
		{:else if tab === 'dynamik' && data.dynamics}
			<DynamicsTab dynamics={data.dynamics} />
		{:else if tab === 'daten' && data.marketData}
			<DataTab data={data.marketData} />
		{/if}
	{/if}
</div>
