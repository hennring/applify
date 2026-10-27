<script lang="ts">
	import type { Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { formatDate } from '#lib/labels.ts';
	import BarList from '#lib/viz/BarList.svelte';
	import { formatPercent } from '#lib/viz/tooltip.ts';
	import { formatDays } from './market';

	let { dynamics }: { dynamics: Schemas['MarketDynamics'] } = $props();

	const lifespan = $derived(dynamics.lifespan);
	const skills = $derived(dynamics.skills);
	const points = (delta: number) =>
		`${delta > 0 ? '+' : '−'}${Math.abs(delta * 100)
			.toFixed(1)
			.replace('.', ',')} Pkt.`;

	function changeBars(changes: Schemas['SkillChange'][]) {
		return changes.map((c) => ({
			label: c.skill,
			value: Math.abs(c.delta),
			valueText: points(c.delta),
			detail: [
				c.skill,
				`Letzte ${skills.recent_from ? `Wochen ab ${formatDate(skills.recent_from)}` : 'Wochen'}: ${formatPercent(c.recent_share)} der Stellen`,
				`Davor: ${formatPercent(c.previous_share)}`
			].join('\n')
		}));
	}
</script>

<p class="note">
	<Icon name="clock" size={16} />
	<span>
		Historie seit {dynamics.history_start ? formatDate(dynamics.history_start) : '–'}
		({dynamics.history_days} Tage).
		{#if dynamics.trend_ready_on}
			Vergleiche über zweimal vier Wochen sind ab etwa {formatDate(dynamics.trend_ready_on)} belastbar.
		{/if}
		Stellen aus der Zeit vor der Umstellung auf die Raw-Schicht zählen mit dem Tag ihrer ersten Sichtung.
	</span>
</p>

<div class="grid">
	<section class="card">
		<h2><Icon name="activity" size={18} /> Zu- und Abgang pro Woche</h2>
		{#if dynamics.flow.length}
			<table>
				<thead>
					<tr>
						<th>Woche</th>
						<th class="num">Neu</th>
						<th class="num">Verschwunden</th>
						<th class="num">Saldo</th>
					</tr>
				</thead>
				<tbody>
					{#each dynamics.flow as w (w.week)}
						<tr>
							<td>KW ab {formatDate(w.week)}</td>
							<td class="num">{w.new}</td>
							<td class="num">{w.gone}</td>
							<td class="num">{w.new - w.gone > 0 ? '+' : ''}{w.new - w.gone}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{:else}
			<p class="muted">Keine Stellen in dieser Auswahl.</p>
		{/if}
		<p class="muted small">
			Verschwunden: seit mehr als einer Woche in keinem Suchlauf mehr gesehen. Gezählt in der Woche
			der letzten Sichtung.
		</p>
	</section>

	<section class="card">
		<h2><Icon name="calendar" size={18} /> Wie lange Stellen online bleiben</h2>
		{#if lifespan.median_days !== null}
			<p class="headline">
				<strong>{formatDays(Math.round(lifespan.median_days))}</strong>
				<span class="muted">Median über {lifespan.closed} verschwundene Stellen</span>
			</p>
			<BarList
				bars={lifespan.by_role.map((g) => ({
					label: g.label,
					value: g.median_days,
					valueText: formatDays(Math.round(g.median_days)),
					detail: `${g.label}: Median ${formatDays(Math.round(g.median_days))} über ${g.closed} Stellen`
				}))}
				empty="Noch keine Rolle mit genug verschwundenen Stellen."
			/>
		{:else}
			<p class="muted">
				Noch zu wenige verschwundene Stellen ({lifespan.closed} von mindestens {lifespan.min_closed}).
				{lifespan.open} Stellen sind noch online; ihre Laufzeit zählt erst, wenn sie verschwinden.
			</p>
		{/if}
	</section>

	{#if lifespan.by_skill.length}
		<section class="card wide">
			<h2><Icon name="target" size={18} /> Laufzeit nach Skill</h2>
			<BarList
				bars={lifespan.by_skill.map((g) => ({
					label: g.label,
					value: g.median_days,
					valueText: formatDays(Math.round(g.median_days)),
					detail: `${g.label}: Median ${formatDays(Math.round(g.median_days))} über ${g.closed} verschwundene Stellen`
				}))}
			/>
			<p class="muted small">
				Kurze Laufzeit: schnell besetzt oder stark gefragt. Lange Laufzeit: schwer zu besetzen –
				oder eine Daueranzeige.
			</p>
		</section>
	{/if}

	<section class="card wide">
		<h2><Icon name="activity" size={18} /> Steigende und fallende Skills</h2>
		{#if skills.ready}
			<div class="changes">
				<div>
					<h3>Steigend</h3>
					<BarList bars={changeBars(skills.rising)} empty="Kein Skill legt deutlich zu." />
				</div>
				<div>
					<h3>Fallend</h3>
					<BarList bars={changeBars(skills.falling)} empty="Kein Skill verliert deutlich." />
				</div>
			</div>
			<p class="muted small">
				Anteil der Volltext-Stellen in den letzten vier Wochen ({skills.recent_jobs} Stellen) gegenüber
				den vier Wochen davor ({skills.previous_jobs} Stellen), in Prozentpunkten.
			</p>
		{:else}
			<p class="muted">
				Für den Vergleich braucht jedes der beiden Vier-Wochen-Fenster mindestens {skills.min_window_jobs}
				Volltext-Stellen. Bisher: letzte vier Wochen {skills.recent_jobs}, davor {skills.previous_jobs}.
			</p>
		{/if}
	</section>
</div>

<style>
	.note {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.changes {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1.5rem;
	}
	@media (max-width: 1000px) {
		.changes {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	h3 {
		font-size: 0.95rem;
		margin: 0 0 0.4rem;
	}
</style>
