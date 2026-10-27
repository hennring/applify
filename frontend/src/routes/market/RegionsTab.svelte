<script lang="ts">
	import type { Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import BarList from '#lib/viz/BarList.svelte';
	import GermanyMap from '#lib/viz/GermanyMap.svelte';
	import { formatPercent } from '#lib/viz/tooltip.ts';

	let { regions }: { regions: Schemas['MarketRegions'] } = $props();

	let measure = $state<'jobs' | 'per_100k'>('jobs');

	const byCode = $derived(Object.fromEntries(regions.states.map((s) => [s.state_code, s])));
	const located = $derived(regions.states.reduce((sum, s) => sum + s.jobs, 0));
	const decimal = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 });
	const format = (value: number) =>
		measure === 'jobs' ? `${Math.round(value)}` : decimal.format(value);
	const value = (s: Schemas['StateJobs']) => (measure === 'jobs' ? s.jobs : s.per_100k);

	function detail(code: string): string {
		const s = byCode[code];
		if (!s) return code;
		return [
			s.state_name,
			`${s.jobs} Stellen (${formatPercent(located ? s.jobs / located : 0)} der verorteten)`,
			`${decimal.format(s.per_100k)} je 100.000 Einwohner`,
			s.remote ? `davon ${s.remote} remote` : ''
		]
			.filter(Boolean)
			.join('\n');
	}

	const distanceTotal = $derived(regions.distances.reduce((sum, d) => sum + d.jobs, 0));
</script>

<div class="tiles">
	<div class="tile">
		<span class="big">{located}</span>
		<span class="muted">Stellen mit Ort in Deutschland</span>
	</div>
	<div class="tile">
		<span class="big">{regions.remote_without_place}</span>
		<span class="muted">remote ohne Ort</span>
	</div>
	<div class="tile">
		<span class="big">{regions.abroad}</span>
		<span class="muted">im Ausland</span>
	</div>
	<div class="tile">
		<span class="big">{regions.unknown}</span>
		<span class="muted">Ort nicht erkannt</span>
	</div>
</div>
<p class="muted small">
	Die Verteilung spiegelt auch, wo du suchst: Suchläufe fragen deine Orte und Remote-Stellen ab. Für
	ein Bild ganz Deutschlands den Umfang „Deutschland“ wählen.
</p>

<div class="grid">
	<section class="card">
		<h2><Icon name="map-pin" size={18} /> Stellen nach Bundesland</h2>
		<div class="segmented" role="group" aria-label="Maß">
			<button
				type="button"
				class:on={measure === 'jobs'}
				aria-pressed={measure === 'jobs'}
				onclick={() => (measure = 'jobs')}>Anzahl</button
			>
			<button
				type="button"
				class:on={measure === 'per_100k'}
				aria-pressed={measure === 'per_100k'}
				onclick={() => (measure = 'per_100k')}>je 100.000 Einwohner</button
			>
		</div>
		<GermanyMap
			values={Object.fromEntries(regions.states.map((s) => [s.state_code, value(s)]))}
			{format}
			{detail}
			label="Karte der Bundesländer nach {measure === 'jobs'
				? 'Anzahl der Stellen'
				: 'Stellen je 100.000 Einwohner'}"
		/>
	</section>

	<section class="card">
		<h2><Icon name="building" size={18} /> Bundesländer</h2>
		<BarList
			bars={regions.states
				.filter((s) => s.jobs > 0)
				.sort((a, b) => value(b) - value(a))
				.map((s) => ({
					label: s.state_name,
					value: value(s),
					valueText: format(value(s)),
					detail: detail(s.state_code)
				}))}
			empty="Keine Stelle dieser Auswahl hat einen Ort in Deutschland."
		/>
	</section>

	<section class="card">
		<h2><Icon name="map-pin" size={18} /> Städte</h2>
		<BarList
			bars={regions.cities.map((c) => ({
				label: c.city,
				value: c.jobs,
				valueText: `${c.jobs}`,
				detail: `${c.city} (${byCode[c.state_code]?.state_name ?? c.state_code}): ${c.jobs} Stellen`
			}))}
			empty="Keine Städte in dieser Auswahl."
		/>
	</section>

	<section class="card">
		<h2><Icon name="target" size={18} /> Entfernung zu deinen Orten</h2>
		<BarList
			bars={regions.distances.map((d) => ({
				label: d.bucket,
				value: d.jobs,
				valueText: `${d.jobs}`,
				detail: `${d.bucket}: ${d.jobs} Stellen (${formatPercent(distanceTotal ? d.jobs / distanceTotal : 0)})`
			}))}
			empty="Keine Orte im Profil."
		/>
		<p class="muted small">Luftlinie zum nächsten Ort aus deinem Profil.</p>
	</section>
</div>

<style>
	.segmented {
		margin-bottom: 0.75rem;
	}
</style>
