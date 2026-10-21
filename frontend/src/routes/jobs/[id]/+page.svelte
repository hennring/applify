<script lang="ts">
	import { resolve } from '$app/paths';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import ScoreBadge from '#lib/components/ScoreBadge.svelte';
	import { formatDate, formatSalary, jobRemoteLabels, sourceLabels } from '#lib/labels.ts';
	import { textBlocks } from '#lib/text.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Updated in place after marking as seen or pasting a text; reset on navigation.
	let updated = $state<Schemas['MatchDetail'] | null>(null);
	const match = $derived(updated?.job.id === data.match.job.id ? updated : data.match);
	const job = $derived(match.job);
	const salary = $derived(formatSalary(job.salary_min, job.salary_max));
	const blocks = $derived(textBlocks(job.description));

	let editing = $state(false);
	let draft = $state('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	// Opening the detail view marks the job as seen (F10).
	$effect(() => {
		const jobId = data.match.job.id;
		if (data.match.status !== 'new') return;
		api
			.POST('/api/matches/{job_id}/seen', { params: { path: { job_id: jobId } } })
			.then(({ data: seen }) => {
				if (seen) updated = seen;
			});
	});

	async function saveText() {
		saving = true;
		error = null;
		const { data: rescored, error: err } = await api.PUT('/api/matches/{job_id}/text', {
			params: { path: { job_id: job.id } },
			body: { text: draft }
		});
		saving = false;
		if (err || !rescored) {
			error = errorMessage(err);
			return;
		}
		updated = rescored;
		editing = false;
		draft = '';
	}
</script>

<div class="pagehead">
	<a class="back" href={resolve('/')}
		><Icon name="chevron-up" size={16} class="left" /> Tagesliste</a
	>
	<div class="headline">
		<ScoreBadge score={match.score} size="lg" />
		<div>
			<h1>{job.title}</h1>
			<div class="meta">
				<span><Icon name="building" size={16} /> {job.company || '–'}</span>
				{#if job.location_raw}<span><Icon name="map-pin" size={16} /> {job.location_raw}</span>{/if}
				{#if job.remote_type}<span
						><Icon name="house" size={16} /> {jobRemoteLabels[job.remote_type]}</span
					>{/if}
				{#if salary}<span><Icon name="wallet" size={16} /> {salary}</span>{/if}
				{#if job.posted_at}<span
						><Icon name="calendar" size={16} /> {formatDate(job.posted_at)}</span
					>{/if}
			</div>
		</div>
		<button type="button" class="primary apply" disabled title="Kommt in M5"
			><Icon name="check" size={18} /> Zusagen</button
		>
	</div>
</div>

{#if match.excluded_reason}
	<p class="card banner excluded">
		<Icon name="ban" />
		Ausgeblendet: {match.excluded_reason}
	</p>
{/if}

<div class="layout">
	<article class="card text">
		<div class="texthead">
			<h2><Icon name="file-text" size={20} /> Anzeigentext</h2>
			{#if !editing}
				<button type="button" onclick={() => ((editing = true), (draft = ''))}>
					<Icon name={job.has_full_text ? 'pencil' : 'plus'} size={15} />
					{job.has_full_text ? 'Text ersetzen' : 'Text einfügen'}
				</button>
			{/if}
		</div>

		{#if editing}
			<form
				class="paste"
				onsubmit={(e) => {
					e.preventDefault();
					saveText();
				}}
			>
				<p class="muted">
					Anzeigentext aus der Originalanzeige hier einfügen – die Stelle wird danach neu bewertet.
				</p>
				<!-- svelte-ignore a11y_autofocus -->
				<textarea bind:value={draft} rows="14" aria-label="Anzeigentext" autofocus></textarea>
				<div class="row">
					<button type="submit" class="primary" disabled={saving || draft.trim().length < 100}>
						<Icon name={saving ? 'loader' : 'save'} size={16} class={saving ? 'spin' : ''} />
						Speichern und neu bewerten
					</button>
					<button type="button" onclick={() => (editing = false)}>Abbrechen</button>
					{#if draft.trim() && draft.trim().length < 100}<span class="muted"
							>mindestens 100 Zeichen</span
						>{/if}
					{#if error}<span class="error">{error}</span>{/if}
				</div>
			</form>
		{/if}

		{#if !job.has_full_text}
			<p class="banner muted">
				<Icon name="circle-alert" />
				Nur Kurzinfo – die Quelle liefert keinen Anzeigentext. Der Score beruht vor allem auf Titel, Ort
				und Seniorität.
			</p>
		{/if}
		{#each blocks as block, i (i)}
			{#if block.kind === 'heading'}
				<h3>{block.text}</h3>
			{:else if block.kind === 'list'}
				<ul>
					{#each block.items as item, j (j)}<li>{item}</li>{/each}
				</ul>
			{:else}
				<p>{block.text}</p>
			{/if}
		{/each}
	</article>

	<aside>
		<section class="card">
			<h2><Icon name="activity" size={20} /> Bewertung</h2>
			<ul class="components">
				{#each match.breakdown.components as c (c.key)}
					<li>
						<div class="chead">
							<strong>{c.label}</strong>
							<span class="muted">
								{c.points === null ? 'unbekannt' : `${Math.round(c.points)} Pkt.`} · Gewicht {c.weight}
							</span>
						</div>
						<div class="cbar" class:unknown={c.value === null}>
							<div style:width="{Math.round((c.value ?? 0) * 100)}%"></div>
						</div>
						<ul class="evidence">
							{#each c.evidence as e, i (i)}
								<li class={e.kind}>
									<Icon
										name={e.kind === 'hit' ? 'check' : e.kind === 'miss' ? 'x' : 'circle-alert'}
										size={14}
									/>
									{e.text}
								</li>
							{/each}
						</ul>
					</li>
				{/each}
			</ul>
			<p class="muted small">
				Unbekannte Angaben zählen nicht mit; die übrigen werden auf 100 hochgerechnet.
			</p>
		</section>

		<section class="card">
			<h2><Icon name="external-link" size={20} /> Quellen</h2>
			<ul class="sources">
				{#each job.sources as source (source.url)}
					<li>
						<!-- External link to the posting, not an app route. -->
						<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
						<a href={source.url} target="_blank" rel="noopener noreferrer"
							>{sourceLabels[source.source] ?? source.source}
							<Icon name="external-link" size={14} /></a
						>
					</li>
				{/each}
			</ul>
		</section>
	</aside>
</div>

<style>
	.pagehead {
		position: sticky;
		top: 0;
		z-index: 10;
		margin: -1.5rem 0 1rem;
		padding: 1rem 0 0.9rem;
		background: var(--bg);
		border-bottom: 1px solid var(--border);
	}
	@media (max-width: 700px) {
		.pagehead {
			margin-top: -1rem;
			padding-top: 0.75rem;
		}
	}
	.back {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		margin-bottom: 0.6rem;
		color: var(--muted);
		text-decoration: none;
		font-size: 0.9rem;
	}
	.back:hover {
		color: var(--accent);
	}
	.back :global(.left) {
		transform: rotate(-90deg);
	}
	.headline {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		gap: 1rem;
		align-items: center;
	}
	h1 {
		margin: 0 0 0.35rem;
		font-size: 1.5rem;
	}
	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.2rem;
		color: var(--muted);
	}
	.meta span,
	.banner,
	.texthead button,
	.apply,
	.paste button,
	.sources a {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.apply {
		padding: 0.55rem 1.3rem;
		font-size: 1.05rem;
		font-weight: 600;
		border-radius: 999px;
	}
	.banner.excluded {
		border-color: var(--error);
		color: var(--error);
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 3fr) minmax(20rem, 2fr);
		gap: 1rem;
		align-items: start;
	}
	@media (max-width: 1100px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
		.headline {
			grid-template-columns: auto minmax(0, 1fr);
		}
		.apply {
			grid-column: 1 / -1;
			justify-self: start;
		}
	}
	aside {
		position: sticky;
		top: 9rem;
	}
	.card h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 1.15rem;
	}
	.texthead {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}
	.texthead h2 {
		margin: 0;
	}
	.text {
		line-height: 1.6;
	}
	.text h3 {
		margin: 1.25rem 0 0.4rem;
		font-size: 1.05rem;
	}
	.text ul {
		padding-left: 1.3rem;
	}
	.paste {
		display: grid;
		gap: 0.6rem;
		margin: 1rem 0;
	}
	.paste textarea {
		width: 100%;
		box-sizing: border-box;
		font: inherit;
		resize: vertical;
	}
	.components {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 1rem;
	}
	.chead {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		font-size: 0.95rem;
	}
	.cbar {
		height: 0.4rem;
		margin: 0.35rem 0 0.4rem;
		border-radius: 999px;
		background: var(--chip);
		overflow: hidden;
	}
	.cbar div {
		height: 100%;
		background: var(--accent);
	}
	.cbar.unknown {
		background: repeating-linear-gradient(
			45deg,
			var(--chip),
			var(--chip) 4px,
			transparent 4px,
			transparent 8px
		);
	}
	.evidence {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.2rem;
		font-size: 0.88rem;
	}
	.evidence li {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}
	.evidence .hit {
		color: var(--ok);
	}
	.evidence .miss {
		color: var(--error);
	}
	.evidence .unknown {
		color: var(--muted);
	}
	.small {
		font-size: 0.8rem;
		margin: 1rem 0 0;
	}
	.sources {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.4rem;
	}
	.sources a {
		color: var(--accent);
		text-decoration: none;
	}
</style>
