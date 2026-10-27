<script lang="ts">
	import { resolve } from '$app/paths';
	import type { Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { formatDate, skillCategoryLabels } from '#lib/labels.ts';
	import BarList from '#lib/viz/BarList.svelte';
	import { formatEuro, formatPercent } from '#lib/viz/tooltip.ts';

	let { me }: { me: Schemas['MarketMe'] } = $props();

	const share = (part: number | null | undefined, whole: number) =>
		part === null || part === undefined || !whole ? null : part / whole;
	const lever = $derived(me.lever.filter((s) => s.new_good > 0).slice(0, 15));
	const yearsFit = $derived(share(me.fit.years_fit, me.fit.years_known));
	const salaryFit = $derived(share(me.fit.salary_fit, me.fit.salary_known));
	const gain = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(1).replace('.', ',')}`;
</script>

<div class="tiles">
	<div class="tile">
		<span class="big">{me.good}</span>
		<span class="muted"
			>gute Treffer (Score ≥ {me.good_score}) von {me.jobs} Stellen ({formatPercent(
				share(me.good, me.jobs) ?? 0
			)})</span
		>
	</div>
	<div class="tile">
		<span class="big">{yearsFit === null ? '–' : formatPercent(yearsFit)}</span>
		<span class="muted">
			{#if me.fit.years === null}
				Berufsjahre fehlen im Profil
			{:else}
				verlangen höchstens deine {me.fit.years} Jahre ({me.fit.years_known} Stellen mit Angabe)
			{/if}
		</span>
	</div>
	<div class="tile">
		<span class="big">{salaryFit === null ? '–' : formatPercent(salaryFit)}</span>
		<span class="muted">
			{#if me.fit.salary_min === null}
				Kein Mindestgehalt im Profil – <a href={resolve('/profile')}>eintragen</a>
			{:else}
				bieten mindestens {formatEuro(me.fit.salary_min)} ({me.fit.salary_known} Stellen mit Angabe)
			{/if}
		</span>
	</div>
	<div class="tile">
		<span class="big">{me.excluded}</span>
		<span class="muted">durch deine Ausschlüsse aussortiert</span>
	</div>
</div>
<p class="muted small">
	Live aus deinem aktuellen Profil berechnet; Profiländerungen wirken sofort.
</p>

<div class="grid">
	<section class="card wide">
		<h2><Icon name="target" size={18} /> Skills mit dem größten Hebel</h2>
		<BarList
			bars={lever.map((s) => ({
				label: s.skill,
				value: s.new_good,
				valueText: `+${s.new_good}`,
				badge: s.category ? (skillCategoryLabels[s.category] ?? s.category) : undefined,
				detail: [
					s.skill,
					`In ${s.jobs} Stellen der Auswahl gefragt`,
					`${s.new_good} davon würden zu guten Treffern (Score ≥ ${me.good_score})`,
					`Score dieser Stellen im Schnitt ${gain(s.avg_gain)} Punkte`
				].join('\n')
			}))}
			empty="Kein einzelner Skill würde zusätzliche gute Treffer bringen."
		/>
		<p class="muted small">
			Für die {me.lever.length} häufigsten Skills, die nicht in deinem Profil stehen, ist dein Matching
			neu gerechnet, als stünde der Skill mit Gewicht „gern“ im Profil. Gezählt sind Stellen, die dadurch
			die Grenze für gute Treffer überschreiten.
		</p>
	</section>

	<section class="card">
		<h2><Icon name="activity" size={18} /> Wie gut der Markt zu dir passt</h2>
		<BarList
			bars={me.scores.map((b) => ({
				label: `Score ${b.bucket}`,
				value: b.jobs,
				valueText: `${b.jobs}`,
				detail: `Score ${b.bucket}: ${b.jobs} Stellen (${formatPercent(share(b.jobs, me.jobs) ?? 0)})`
			}))}
		/>
	</section>

	<section class="card">
		<h2><Icon name="calendar" size={18} /> Gute Treffer pro Woche</h2>
		<BarList
			bars={me.weekly.map((w) => ({
				label: `KW ab ${formatDate(w.week)}`,
				value: w.good,
				valueText: `${w.good} / ${w.jobs}`,
				detail: `${w.good} gute Treffer unter ${w.jobs} neuen Stellen (${formatPercent(share(w.good, w.jobs) ?? 0)})`
			}))}
			empty="Noch keine Stellen in dieser Auswahl."
		/>
		<p class="muted small">Nach der Woche, in der eine Stelle zuerst gesehen wurde.</p>
	</section>
</div>
