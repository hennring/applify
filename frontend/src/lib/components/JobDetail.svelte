<script lang="ts">
	import { untrack } from 'svelte';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import { formatDate, formatSalary, jobRemoteLabels, sourceLabels } from '#lib/labels.ts';
	import { textBlocks } from '#lib/text.ts';
	import Icon from './Icon.svelte';
	import ScoreBadge from './ScoreBadge.svelte';

	type Match = Schemas['MatchDetail'];

	let {
		jobId,
		layout = 'page',
		onclose,
		onupdate
	}: {
		jobId: number;
		/** 'panel': one column beside the list; 'page': text and rating side by side. */
		layout?: 'panel' | 'page';
		onclose?: () => void;
		/** Called when status or score change (seen, pasted text), so a list can follow. */
		onupdate?: (match: Match) => void;
	} = $props();

	let match = $state<Match | null>(null);
	let loadError = $state<string | null>(null);
	let editing = $state(false);
	let draft = $state('');
	let saving = $state(false);
	let saveError = $state<string | null>(null);
	let container = $state<HTMLElement>();

	const job = $derived(match?.job);
	const salary = $derived(job ? formatSalary(job.salary_min, job.salary_max) : null);
	const blocks = $derived(job ? textBlocks(job.description) : []);

	function show(next: Match) {
		match = next;
		onupdate?.(next);
	}

	// (Re)load whenever another job is selected; opening it marks it as seen (F10).
	$effect(() => {
		const id = jobId;
		let current = true;
		loadError = null;
		editing = false;
		draft = '';
		saveError = null;
		untrack(() => container?.scrollTo({ top: 0 }));
		api.GET('/api/matches/{job_id}', { params: { path: { job_id: id } } }).then(async (res) => {
			if (!current) return;
			if (!res.data) {
				match = null;
				loadError =
					res.response.status === 404
						? 'Stelle nicht gefunden.'
						: 'Stelle konnte nicht geladen werden.';
				return;
			}
			match = res.data;
			if (res.data.status === 'new') {
				const seen = await api.POST('/api/matches/{job_id}/seen', {
					params: { path: { job_id: id } }
				});
				if (current && seen.data) show(seen.data);
			}
		});
		return () => {
			current = false;
		};
	});

	async function saveText() {
		if (!job) return;
		saving = true;
		saveError = null;
		const { data: rescored, error } = await api.PUT('/api/matches/{job_id}/text', {
			params: { path: { job_id: job.id } },
			body: { text: draft }
		});
		saving = false;
		if (error || !rescored) {
			saveError = errorMessage(error);
			return;
		}
		show(rescored);
		editing = false;
		draft = '';
	}
</script>

<div class="detail {layout}" bind:this={container}>
	{#if loadError}
		<div class="head">
			<p class="error">{loadError}</p>
			{#if onclose}
				<button type="button" class="icon close" aria-label="Schließen" onclick={onclose}
					><Icon name="x" /></button
				>
			{/if}
		</div>
	{:else if !match || !job || match.job.id !== jobId}
		<p class="muted loading"><Icon name="loader" class="spin" /> Lädt …</p>
	{:else}
		<header class="head">
			<ScoreBadge score={match.score} size="lg" />
			<div class="headtext">
				<h2 class="title">{job.title}</h2>
				<div class="meta">
					<span><Icon name="building" size={16} /> {job.company || '–'}</span>
					{#if job.location_raw}<span><Icon name="map-pin" size={16} /> {job.location_raw}</span
						>{/if}
					{#if job.remote_type}<span
							><Icon name="house" size={16} /> {jobRemoteLabels[job.remote_type]}</span
						>{/if}
					{#if salary}<span><Icon name="wallet" size={16} /> {salary}</span>{/if}
					{#if job.posted_at}<span
							><Icon name="calendar" size={16} /> {formatDate(job.posted_at)}</span
						>{/if}
				</div>
			</div>
			<div class="actions">
				<button type="button" class="primary apply" disabled title="Kommt in M5"
					><Icon name="check" size={18} /> Zusagen</button
				>
				{#if onclose}
					<button type="button" class="round close" aria-label="Schließen" onclick={onclose}
						><Icon name="x" /></button
					>
				{/if}
			</div>
		</header>

		{#if match.excluded_reason}
			<p class="banner excluded"><Icon name="ban" /> Ausgeblendet: {match.excluded_reason}</p>
		{/if}

		<div class="columns">
			<article class="text">
				<div class="texthead">
					<h3><Icon name="file-text" size={20} /> Anzeigentext</h3>
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
							Anzeigentext aus der Originalanzeige hier einfügen – die Stelle wird danach neu
							bewertet.
						</p>
						<!-- svelte-ignore a11y_autofocus -->
						<textarea bind:value={draft} rows="12" aria-label="Anzeigentext" autofocus></textarea>
						<div class="row">
							<button type="submit" class="primary" disabled={saving || draft.trim().length < 100}>
								<Icon name={saving ? 'loader' : 'save'} size={16} class={saving ? 'spin' : ''} />
								Speichern und neu bewerten
							</button>
							<button type="button" onclick={() => (editing = false)}>Abbrechen</button>
							{#if draft.trim() && draft.trim().length < 100}<span class="muted"
									>mindestens 100 Zeichen</span
								>{/if}
							{#if saveError}<span class="error">{saveError}</span>{/if}
						</div>
					</form>
				{/if}

				{#if !job.has_full_text}
					<p class="banner muted">
						<Icon name="circle-alert" />
						Nur Kurzinfo – die Quelle liefert keinen Anzeigentext. Der Score beruht vor allem auf Titel,
						Ort und Seniorität.
					</p>
				{/if}
				{#each blocks as block, i (i)}
					{#if block.kind === 'heading'}
						<h4>{block.text}</h4>
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
				<section class="rating">
					<h3><Icon name="activity" size={20} /> Bewertung</h3>
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

				<section>
					<h3><Icon name="external-link" size={20} /> Quellen</h3>
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
	{/if}
</div>

<style>
	.detail {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 1.25rem 1.5rem;
	}
	.loading {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0;
	}
	.head {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		gap: 1rem;
		align-items: start;
		padding-bottom: 1rem;
		border-bottom: 1px solid var(--border);
	}
	.title {
		margin: 0 0 0.35rem;
		font-size: 1.4rem;
	}
	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.2rem;
		color: var(--muted);
	}
	.actions {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.meta span,
	.banner,
	.texthead button,
	.apply,
	.paste button,
	.sources a,
	h3 {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.apply {
		padding: 0.5rem 1.2rem;
		font-weight: 600;
		border-radius: 999px;
	}
	.banner {
		margin: 1rem 0 0;
	}
	.banner.excluded {
		color: var(--error);
	}
	.columns {
		display: grid;
		gap: 1.5rem;
		margin-top: 1rem;
	}
	/* Full page: text and rating side by side; panel: rating first, then the text. */
	.page .columns {
		grid-template-columns: minmax(0, 3fr) minmax(18rem, 2fr);
		align-items: start;
	}
	.panel .columns aside {
		order: -1;
	}
	@media (max-width: 1100px) {
		.page .columns {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	h3 {
		margin: 0 0 0.75rem;
		font-size: 1.1rem;
	}
	.texthead {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}
	.texthead h3 {
		margin: 0;
	}
	.text {
		line-height: 1.6;
	}
	.text h4 {
		margin: 1.25rem 0 0.4rem;
		font-size: 1.02rem;
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
		resize: vertical;
	}
	aside {
		display: grid;
		gap: 1.25rem;
	}
	.panel .rating {
		padding-bottom: 1.25rem;
		border-bottom: 1px solid var(--border);
	}
	.components {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.9rem;
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
		margin: 0.75rem 0 0;
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
