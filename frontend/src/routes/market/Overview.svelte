<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { formatDate, seniorityLabels, skillCategoryLabels, weightBadges } from '#lib/labels.ts';
	import BarList, { type Bar } from '#lib/viz/BarList.svelte';
	import RangeBars from '#lib/viz/RangeBars.svelte';
	import StackedBars from '#lib/viz/StackedBars.svelte';
	import TrendChart from '#lib/viz/TrendChart.svelte';
	import { formatPercent } from '#lib/viz/tooltip.ts';
	import { SENIORITY, formatDays, type Filters } from './market';

	type SkillDemand = Schemas['SkillDemand'];

	let {
		market,
		filters,
		roleLabel
	}: { market: Schemas['MarketOverview']; filters: Filters; roleLabel: string } = $props();

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

	let ageOrder = $state<'oldest' | 'newest'>('oldest');

	// --- skill candidates -------------------------------------------------------------------

	let categoryOf = $state<Record<string, string>>({});
	const categoryLabel = (key: string) => skillCategoryLabels[key] ?? key;
	const categoryOptions = $derived(
		[...(market?.categories ?? [])].sort((a, b) =>
			categoryLabel(a).localeCompare(categoryLabel(b), 'de')
		)
	);
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

		{#if market.age}
			{@const age = market.age}
			<section class="card wide">
				<h2><Icon name="calendar" size={18} /> Alter der offenen Stellen</h2>
				<div class="age">
					<div>
						<p class="headline">
							<strong>{formatDays(age.median_days)}</strong>
							<span class="muted">Median über {age.open} offene Stellen</span>
						</p>
						<BarList
							bars={age.buckets.map((b) => ({
								label: b.bucket,
								value: b.jobs,
								valueText: `${b.jobs}`,
								detail: `${b.bucket} online: ${b.jobs} Stellen (${formatPercent(age.open ? b.jobs / age.open : 0)})`
							}))}
						/>
						<p class="muted small">
							Seit Veröffentlichung laut Quelle, sonst seit der ersten Sichtung. Sehr alte Anzeigen
							sind oft Dauer- oder Initiativausschreibungen.
						</p>
					</div>
					<div>
						<div class="segmented" role="group" aria-label="Sortierung">
							{#each [['oldest', 'Älteste'], ['newest', 'Neueste']] as const as [value, label] (value)}
								<button
									type="button"
									class:on={ageOrder === value}
									aria-pressed={ageOrder === value}
									onclick={() => (ageOrder = value)}>{label}</button
								>
							{/each}
						</div>
						<table>
							<thead>
								<tr><th>Stelle</th><th>Rolle</th><th>Online seit</th><th class="num">Tage</th></tr>
							</thead>
							<tbody>
								{#each age[ageOrder] as job (job.job_id)}
									<tr>
										<td>
											<a href="{resolve('/')}?stelle={job.job_id}">{job.title}</a>
											<span class="muted small block"
												>{job.company}{job.location_raw ? ` · ${job.location_raw}` : ''}</span
											>
										</td>
										<td class="small">{job.role_label}</td>
										<td class="small">{formatDate(job.online_since)}</td>
										<td class="num">{job.age_days}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			</section>
		{/if}

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
										{#each categoryOptions as category (category)}
											<option value={category}>{categoryLabel(category)}</option>
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

<style>
	.age {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
		gap: 1.5rem;
		align-items: start;
	}
	@media (max-width: 1000px) {
		.age {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.age .segmented {
		margin-bottom: 0.5rem;
	}
	td button {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
</style>
