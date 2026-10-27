<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { formatDate, sourceLabels } from '#lib/labels.ts';
	import type { PageProps } from './$types';

	type Sample = Schemas['SampleOut'];

	let { data }: PageProps = $props();

	const PORTALS = ['StepStone', 'LinkedIn', 'Indeed', 'XING', 'Glassdoor', 'Sonstiges'];
	// Target of the coverage measurement (§5.7, acceptance M4).
	const TARGET = 0.7;
	const SAMPLE_SIZE = 30;

	let draft = $state({ company: '', title: '', location: '', url: '', found_via: 'StepStone' });
	let saving = $state(false);
	let checking = $state(false);
	let error = $state<string | null>(null);

	const coverage = $derived(data.coverage);
	const percent = $derived(
		coverage?.rate === null || coverage?.rate === undefined ? null : Math.round(coverage.rate * 100)
	);

	async function add(e: SubmitEvent) {
		e.preventDefault();
		saving = true;
		error = null;
		const response = await api.POST('/api/coverage', { body: draft });
		saving = false;
		if (response.error) {
			error = errorMessage(response.error);
			return;
		}
		draft = { ...draft, company: '', title: '', location: '', url: '' };
		await invalidateAll();
	}

	async function recheck() {
		checking = true;
		error = null;
		const response = await api.POST('/api/coverage/check');
		checking = false;
		if (!response.response.ok) error = 'Prüfung fehlgeschlagen.';
		await invalidateAll();
	}

	async function remove(sample: Sample) {
		if (!confirm(`„${sample.title}“ bei ${sample.company} entfernen?`)) return;
		await api.DELETE('/api/coverage/{sample_id}', {
			params: { path: { sample_id: sample.id } }
		});
		await invalidateAll();
	}

	function sourceName(key: string): string {
		return sourceLabels[key] ?? key;
	}
</script>

<div class="pagehead">
	<h1><Icon name="target" size={28} /> Abdeckung</h1>
	{#if coverage?.total}
		<button type="button" onclick={recheck} disabled={checking}>
			<Icon name={checking ? 'loader' : 'search'} size={16} class={checking ? 'spin' : ''} />
			Erneut prüfen
		</button>
	{/if}
</div>

{#if !coverage}
	<p class="card error">Abdeckung konnte nicht geladen werden.</p>
{:else}
	<div class="layout">
		<div class="col">
			<section class="card">
				<h2><Icon name="plus" size={18} /> Stelle aus einem Portal eintragen</h2>
				<p class="muted small">
					Suche auf StepStone, LinkedIn, Indeed &amp; Co. von Hand nach passenden Stellen in deinen
					Orten und trage etwa {SAMPLE_SIZE} davon ein. Applify ruft dabei keine Portalseiten ab, sondern
					prüft nur, ob es die Stelle selbst kennt.
				</p>
				<form class="form" onsubmit={add}>
					<label>
						Firma
						<input type="text" bind:value={draft.company} required maxlength="300" />
					</label>
					<label>
						Stellentitel
						<input type="text" bind:value={draft.title} required maxlength="300" />
					</label>
					<label>
						Ort
						<input type="text" bind:value={draft.location} maxlength="200" />
					</label>
					<label>
						Gefunden auf
						<select bind:value={draft.found_via}>
							{#each PORTALS as portal (portal)}<option>{portal}</option>{/each}
						</select>
					</label>
					<label class="wide">
						Link zur Anzeige (optional, z. B. der Karriereseite)
						<input type="url" bind:value={draft.url} maxlength="1000" />
					</label>
					<div class="wide">
						<button
							type="submit"
							class="primary"
							disabled={saving || !draft.company.trim() || !draft.title.trim()}
						>
							<Icon name={saving ? 'loader' : 'check'} size={16} class={saving ? 'spin' : ''} />
							Eintragen und prüfen
						</button>
					</div>
				</form>
				{#if error}<p class="error" role="alert">{error}</p>{/if}
			</section>
		</div>

		<div class="col">
			<section class="card result">
				<h2><Icon name="activity" size={18} /> Ergebnis</h2>
				{#if !coverage.total}
					<p class="muted">Noch keine Stichprobe eingetragen.</p>
				{:else}
					<div class="rate">
						<strong class:ok={coverage.rate !== null && coverage.rate >= TARGET}>{percent} %</strong
						>
						<span class="muted">
							{coverage.found} von {coverage.total} Stellen im Bestand · Ziel {TARGET * 100} %
						</span>
					</div>
					<div class="bar" aria-hidden="true">
						<div style:width="{percent ?? 0}%"></div>
						<span class="target" style:left="{TARGET * 100}%"></span>
					</div>
					{#if coverage.total < SAMPLE_SIZE}
						<p class="muted small">
							Noch {SAMPLE_SIZE - coverage.total} Einträge bis zur empfohlenen Stichprobe.
						</p>
					{/if}
					{#if coverage.found > coverage.visible}
						<p class="small warn">
							{coverage.found - coverage.visible} gefundene Stellen sind in der Jobsuche ausgeblendet.
						</p>
					{/if}

					{#if Object.keys(coverage.by_source).length}
						<h3>Je Quelle</h3>
						<ul class="shares">
							{#each Object.entries(coverage.by_source).sort((a, b) => b[1].count - a[1].count) as [key, share] (key)}
								<li>
									<span>{sourceName(key)}</span>
									<span>
										<strong>{share.count}</strong>
										<span class="muted small">({share.only} nur hier)</span>
									</span>
								</li>
							{/each}
						</ul>
					{/if}
					{#if Object.keys(coverage.reasons).length}
						<h3>Verpasst, vermuteter Grund</h3>
						<ul class="shares">
							{#each Object.entries(coverage.reasons).sort((a, b) => b[1] - a[1]) as [reason, n] (reason)}
								<li>
									<span>{coverage.reason_labels[reason] ?? reason}</span><strong>{n}</strong>
								</li>
							{/each}
						</ul>
					{/if}
				{/if}
			</section>
		</div>
	</div>

	{#if coverage.samples.length}
		<section class="card">
			<h2><Icon name="file-text" size={18} /> Stichprobe</h2>
			<ul class="samples">
				{#each coverage.samples as sample (sample.id)}
					{@const found = sample.matched_job_id !== null}
					<li>
						<span
							class="state"
							class:ok={found && !sample.miss_reason}
							class:warn={found && !!sample.miss_reason}
							class:error={!found}
						>
							<Icon name={found ? 'circle-check' : 'circle-alert'} size={18} />
						</span>
						<div class="what">
							<strong>{sample.title}</strong>
							<span class="muted">
								{sample.company}{sample.location ? ` · ${sample.location}` : ''}
								{sample.found_via ? ` · ${sample.found_via}` : ''} · {formatDate(sample.created_at)}
							</span>
							{#if found && sample.matched_job_id !== null}
								<span class="small">
									Gefunden:
									<a href={resolve('/jobs/[id]', { id: String(sample.matched_job_id) })}
										>{sample.matched_title}</a
									>
									über {sample.matched_sources.map(sourceName).join(', ')}
								</span>
							{/if}
							{#if sample.miss_reason}
								<span class="small" class:warn={found} class:error={!found}
									>{coverage.reason_labels[sample.miss_reason] ?? sample.miss_reason}</span
								>
							{/if}
						</div>
						<button
							type="button"
							class="icon"
							aria-label="Eintrag entfernen"
							onclick={() => remove(sample)}><Icon name="trash" size={16} /></button
						>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
{/if}

<style>
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1rem;
		align-items: start;
	}
	@media (max-width: 1100px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.pagehead button {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.card h2 {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 1.1rem;
	}
	h3 {
		margin: 1.25rem 0 0.4rem;
		font-size: 0.95rem;
	}
	.small {
		font-size: 0.85rem;
	}
	.form {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.6rem 0.9rem;
	}
	.form .wide {
		grid-column: 1 / -1;
	}
	.form button {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.rate {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 0.4rem 0.9rem;
	}
	.rate strong {
		font-size: 2.2rem;
	}
	.bar {
		position: relative;
		height: 0.6rem;
		margin: 0.6rem 0;
		border-radius: 999px;
		background: var(--chip);
	}
	.bar div {
		height: 100%;
		border-radius: 999px;
		background: var(--accent);
	}
	.target {
		position: absolute;
		top: -0.25rem;
		bottom: -0.25rem;
		width: 2px;
		background: var(--text);
	}
	.shares {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.shares li {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.3rem 0;
		border-top: 1px solid var(--border);
	}
	.samples {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.samples li {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		gap: 0.75rem;
		align-items: start;
		padding: 0.7rem 0;
		border-top: 1px solid var(--border);
	}
	.state {
		padding-top: 0.1rem;
	}
	.what {
		display: grid;
		gap: 0.15rem;
	}
	.what a {
		color: var(--accent);
	}
</style>
