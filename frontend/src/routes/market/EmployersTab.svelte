<script lang="ts">
	import type { Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { formatDate } from '#lib/labels.ts';
	import BarList from '#lib/viz/BarList.svelte';
	import { formatPercent } from '#lib/viz/tooltip.ts';

	let { employers, agencies }: { employers: Schemas['MarketEmployers']; agencies: number } =
		$props();

	const share = (n: number) => (employers.jobs ? n / employers.jobs : 0);
</script>

<div class="tiles">
	<div class="tile">
		<span class="big">{employers.companies}</span>
		<span class="muted">Arbeitgeber mit {employers.jobs} Stellen</span>
	</div>
	<div class="tile">
		<span class="big">{formatPercent(employers.top10_share)}</span>
		<span class="muted">der Stellen stammen von den 10 größten Arbeitgebern</span>
	</div>
	<div class="tile">
		<span class="big">{formatPercent(share(agencies))}</span>
		<span class="muted">von Personaldienstleistern ({agencies} Stellen)</span>
	</div>
</div>

<div class="grid">
	<section class="card">
		<h2><Icon name="building" size={18} /> Wer am meisten ausschreibt</h2>
		<BarList
			bars={employers.top.map((e) => ({
				label: e.company,
				value: e.jobs,
				valueText: `${e.jobs}`,
				badge: e.agency ? 'Personaldienstleister' : undefined,
				detail: [
					e.company,
					`${e.jobs} Stellen (${formatPercent(share(e.jobs))} der Auswahl), ${e.active} offen`,
					e.roles.length ? `Vor allem: ${e.roles.join(', ')}` : ''
				]
					.filter(Boolean)
					.join('\n')
			}))}
			empty="Keine Stellen in dieser Auswahl."
		/>
		<p class="muted small">
			Wenige große Arbeitgeber können Skill- und Gehaltszahlen prägen; mit dem Quellen-Filter lässt
			sich das prüfen.
		</p>
	</section>

	<section class="card">
		<h2><Icon name="briefcase" size={18} /> Personaldienstleister</h2>
		<BarList
			bars={employers.agencies.map((a) => ({
				label: a.company,
				value: a.jobs,
				valueText: `${a.jobs}`,
				detail: `${a.company}: ${a.jobs} Stellen`
			}))}
			empty="Keine Personaldienstleister in dieser Auswahl."
		/>
		<p class="muted small">
			Erkannt an Namen und typischen Formulierungen („Arbeitnehmerüberlassung“, „für unseren
			Kunden“). Der Filter oben blendet sie überall aus.
		</p>
	</section>

	<section class="card wide">
		<h2><Icon name="clock" size={18} /> Mehrfach ausgeschriebene Stellen</h2>
		{#if employers.repeated.length}
			<table>
				<thead>
					<tr>
						<th>Stelle</th>
						<th class="num">Anzeigen</th>
						<th class="num">Orte</th>
						<th class="num">Erneut</th>
						<th>Zeitraum</th>
					</tr>
				</thead>
				<tbody>
					{#each employers.repeated as r (`${r.company}|${r.title}`)}
						<tr>
							<td>
								{r.title}
								<span class="muted small block">{r.company}</span>
							</td>
							<td class="num">{r.jobs}</td>
							<td class="num">{r.places}</td>
							<td class="num">{r.reposts || '–'}</td>
							<td class="small">{formatDate(r.first_seen_at)} – {formatDate(r.last_seen_at)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{:else}
			<p class="muted">Keine Firma schreibt in dieser Auswahl denselben Titel mehrfach aus.</p>
		{/if}
		<p class="muted small">
			Gleicher Titel bei derselben Firma. „Orte“: parallel für mehrere Standorte ausgeschrieben.
			„Erneut“: wieder aufgetaucht, nachdem alle früheren Anzeigen mindestens eine Woche
			verschwunden waren – ein Hinweis auf schwer besetzbare Stellen.
		</p>
	</section>
</div>
