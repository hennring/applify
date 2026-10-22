<script lang="ts">
	import { goto, invalidateAll, replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import JobDetail from '#lib/components/JobDetail.svelte';
	import ScoreBadge from '#lib/components/ScoreBadge.svelte';
	import { healthRows } from '#lib/health.ts';
	import { JOB_PAGE_SIZE } from '#lib/jobs.ts';
	import {
		formatDate,
		formatDateTime,
		formatSalary,
		jobRemoteLabels,
		runStatusLabels,
		sourceLabels
	} from '#lib/labels.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Live copy of the run while it is polled; reset when the page data reloads.
	let polled = $state<Schemas['RunOut'] | null>(null);
	const run = $derived(polled && polled.id === data.run?.id ? polled : data.run);
	const running = $derived(run?.status === 'running');

	let starting = $state(false);
	let error = $state<string | null>(null);
	let more = $state<Schemas['MatchOut'][]>([]);
	let loadingMore = $state(false);
	// Status and score changes from the detail panel, applied to the list right away.
	let patched = $state<Record<number, Schemas['MatchDetail']>>({});
	const matches = $derived(
		[...data.matches.items, ...more].map((m) => {
			const p = patched[m.job.id];
			if (!p) return m;
			return {
				...m,
				score: p.score,
				status: p.status,
				excluded_reason: p.excluded_reason,
				breakdown: p.breakdown,
				job: { ...m.job, has_full_text: p.job.has_full_text }
			};
		})
	);

	// The job open in the panel: set by shallow routing, or from ?stelle= after a reload.
	const selectedId = $derived(
		page.state.jobId !== undefined
			? page.state.jobId
			: Number(page.url.searchParams.get('stelle')) || null
	);

	function href(filters: typeof data.filters, jobId: number | null): string {
		const parts = [
			filters.onlyNew && 'neu=1',
			filters.excluded && 'ausgeblendet=1',
			filters.sort === 'date' && 'sort=datum',
			jobId !== null && `stelle=${jobId}`
		].filter(Boolean);
		return `${resolve('/')}${parts.length ? `?${parts.join('&')}` : ''}`;
	}

	function select(jobId: number | null) {
		// Only the URL and page state change; the list is not loaded again.
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		replaceState(href(data.filters, jobId), { jobId });
	}

	function openJob(event: MouseEvent, jobId: number) {
		// Narrow windows and modifier clicks get the full detail page instead.
		if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
		if (!window.matchMedia('(min-width: 1100px)').matches) return;
		event.preventDefault();
		select(jobId);
	}

	function onkeydown(event: KeyboardEvent) {
		const typing = event.target instanceof HTMLElement && event.target.closest('input, textarea');
		if (event.key === 'Escape' && selectedId !== null && !typing) select(null);
	}

	async function startRun() {
		starting = true;
		error = null;
		const { error: err } = await api.POST('/api/runs');
		starting = false;
		if (err) {
			error = errorMessage(err);
			return;
		}
		polled = null;
		more = [];
		await invalidateAll();
	}

	// While a run is going, refresh its progress every two seconds and the list now and then;
	// jobs are rated after each query, so the list grows during the run.
	$effect(() => {
		const id = run?.id;
		if (!running || id === undefined) return;
		let ticks = 0;
		const timer = setInterval(async () => {
			const { data: fresh } = await api.GET('/api/runs/{run_id}', {
				params: { path: { run_id: id } }
			});
			if (!fresh) return;
			polled = fresh;
			ticks += 1;
			if (fresh.status !== 'running' || ticks % 5 === 0) {
				more = [];
				await invalidateAll();
			}
		}, 2000);
		return () => clearInterval(timer);
	});

	async function loadMore() {
		loadingMore = true;
		const { data: result } = await api.GET('/api/matches', {
			params: {
				query: {
					only_new: data.filters.onlyNew,
					excluded: data.filters.excluded,
					sort: data.filters.sort,
					limit: JOB_PAGE_SIZE,
					offset: matches.length
				}
			}
		});
		loadingMore = false;
		if (result) more = [...more, ...result.items];
	}

	async function markAllSeen() {
		await api.POST('/api/matches/seen');
		more = [];
		await invalidateAll();
	}

	function setFilter(changes: { neu?: boolean; ausgeblendet?: boolean; sort?: 'score' | 'date' }) {
		const next = { ...data.filters };
		if (changes.neu !== undefined) next.onlyNew = changes.neu;
		if (changes.ausgeblendet !== undefined) next.excluded = changes.ausgeblendet;
		if (changes.sort !== undefined) next.sort = changes.sort;
		more = [];
		// Same route, only the query string changes; an open panel stays open.
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		goto(href(next, selectedId), { replace: true, reset: false });
	}

	/** The most telling reasons: hits and misses, by component weight. */
	function highlights(match: Schemas['MatchOut']) {
		return match.breakdown.components
			.toSorted((a, b) => b.weight - a.weight)
			.flatMap((c) => c.evidence.filter((e) => e.kind !== 'unknown'))
			.slice(0, 5);
	}

	const totals = $derived(
		Object.values(run?.stats ?? {}).reduce(
			(sum, s) => ({ found: sum.found + s.found, new: sum.new + s.new }),
			{ found: 0, new: 0 }
		)
	);
</script>

<div class="pagehead">
	<h1><Icon name="briefcase" size={28} /> Tagesliste</h1>
	<button type="button" class="primary start" disabled={starting || running} onclick={startRun}>
		<Icon
			name={starting || running ? 'loader' : 'search'}
			size={18}
			class={starting || running ? 'spin' : ''}
		/>
		{running ? 'Suchlauf läuft …' : 'Suchlauf starten'}
	</button>
	{#if error}<span class="error status"><Icon name="circle-alert" size={16} /> {error}</span>{/if}
	{#if data.health}
		<span class="health">
			{#each healthRows(data.health) as row (row.label)}
				<span class={row.ok ? 'ok' : 'error'} title={row.detail ?? ''}
					><Icon name="activity" size={14} /> {row.label}</span
				>
			{/each}
		</span>
	{:else}
		<span class="health error"><Icon name="circle-alert" size={14} /> Backend nicht erreichbar</span
		>
	{/if}
</div>

{#if run}
	<section class="card run" class:failed={run.status === 'failed'}>
		<div class="runhead">
			<h2>
				<Icon
					name={running ? 'loader' : run.status === 'done' ? 'circle-check' : 'circle-alert'}
					size={20}
					class={running ? 'spin' : run.status === 'done' ? 'ok' : 'error'}
				/>
				Suchlauf {runStatusLabels[run.status] ?? run.status}
			</h2>
			<span class="muted"
				><Icon name="clock" size={14} />
				{formatDateTime(run.started_at)}{run.finished_at
					? ` – ${formatDateTime(run.finished_at).split(', ')[1]}`
					: ''}</span
			>
			{#if !running && run.status === 'done'}
				<span class="summary"><strong>{totals.new}</strong> neu von {totals.found} gefunden</span>
			{/if}
		</div>

		{#if running}
			<div
				class="bar"
				role="progressbar"
				aria-valuemin="0"
				aria-valuemax="100"
				aria-valuenow={Math.round(run.progress * 100)}
			>
				<div style:width="{Math.round(run.progress * 100)}%"></div>
			</div>
			<p class="muted step">{run.step}</p>
		{:else if run.status === 'failed'}
			<p class="error step">{run.step}</p>
		{/if}

		{#if Object.keys(run.stats).length}
			<table class="stats">
				<thead>
					<tr
						><th>Quelle</th><th>gefunden</th><th>neu</th><th>zusammengeführt</th><th>bekannt</th><th
							>Fehler</th
						></tr
					>
				</thead>
				<tbody>
					{#each Object.entries(run.stats) as [key, s] (key)}
						<tr>
							<td>{s.label}</td>
							<td>{s.found}</td>
							<td><strong>{s.new}</strong></td>
							<td>{s.duplicate}</td>
							<td>{s.known}</td>
							<td class:error={s.errors > 0}>{s.errors}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}

		{#if run.errors.length}
			<details class="errors">
				<summary class="error"
					><Icon name="circle-alert" size={14} /> {run.errors.length} Fehler beim Abruf</summary
				>
				<ul>
					{#each run.errors as e, i (i)}
						<li><strong>{e.source}</strong> {e.query}: <span class="muted">{e.message}</span></li>
					{/each}
				</ul>
			</details>
		{/if}
	</section>
{:else}
	<p class="card banner muted">
		<Icon name="search" />
		Noch kein Suchlauf. Gesucht wird mit den Wunschrollen, Pflicht-Skills und Orten aus dem Profil.
	</p>
{/if}

<svelte:window {onkeydown} />

<div class="master" class:split={selectedId !== null}>
	<div class="list">
		<div class="toolbar">
			<div class="segmented" role="group" aria-label="Auswahl">
				<button
					type="button"
					class:on={!data.filters.onlyNew && !data.filters.excluded}
					onclick={() => setFilter({ neu: false, ausgeblendet: false })}>Alle</button
				>
				<button
					type="button"
					class:on={data.filters.onlyNew && !data.filters.excluded}
					onclick={() => setFilter({ neu: true, ausgeblendet: false })}
					>Neu <span class="count">{data.matches.new}</span></button
				>
				<button
					type="button"
					class:on={data.filters.excluded}
					onclick={() => setFilter({ ausgeblendet: true, neu: false })}
					title="Durch harte Filter ausgeblendet"
					>Ausgeblendet <span class="count">{data.matches.excluded}</span></button
				>
			</div>
			<div class="segmented" role="group" aria-label="Sortierung">
				<button
					type="button"
					class:on={data.filters.sort === 'score'}
					onclick={() => setFilter({ sort: 'score' })}>Score</button
				>
				<button
					type="button"
					class:on={data.filters.sort === 'date'}
					onclick={() => setFilter({ sort: 'date' })}>Datum</button
				>
			</div>
			<span class="muted">{data.matches.total} Stellen</span>
			{#if data.matches.new}
				<button type="button" class="seen" onclick={markAllSeen}
					><Icon name="check" size={16} /> Alle als gesehen markieren</button
				>
			{/if}
		</div>

		{#if matches.length}
			<ul class="jobs">
				{#each matches as match (match.job.id)}
					{@const job = match.job}
					{@const salary = formatSalary(job.salary_min, job.salary_max)}
					<li
						class="card job"
						class:seen={match.status !== 'new'}
						class:selected={match.job.id === selectedId}
					>
						<ScoreBadge score={match.score} />
						<div class="body">
							<div class="title">
								<a
									href={resolve('/jobs/[id]', { id: String(job.id) })}
									onclick={(e) => openJob(e, job.id)}>{job.title}</a
								>
								{#if match.status === 'new'}<span class="badge new">neu</span>{/if}
								{#if match.breakdown.low_data}<span
										class="badge"
										title="Kein Anzeigentext – Score v. a. aus Titel, Ort und Seniorität"
										>geringe Datenbasis</span
									>{/if}
							</div>
							<div class="meta">
								<span><Icon name="building" size={15} /> {job.company || '–'}</span>
								{#if job.location_raw}<span
										><Icon name="map-pin" size={15} /> {job.location_raw}</span
									>{/if}
								{#if job.remote_type}<span
										><Icon name="house" size={15} /> {jobRemoteLabels[job.remote_type]}</span
									>{/if}
								{#if salary}<span><Icon name="wallet" size={15} /> {salary}</span>{/if}
								{#if job.posted_at}<span
										><Icon name="calendar" size={15} /> {formatDate(job.posted_at)}</span
									>{/if}
							</div>
							{#if match.excluded_reason}
								<p class="reason error"><Icon name="ban" size={15} /> {match.excluded_reason}</p>
							{:else}
								<ul class="evidence">
									{#each highlights(match) as e, i (i)}
										<li class={e.kind}>
											<Icon name={e.kind === 'hit' ? 'check' : 'x'} size={13} />
											{e.text}
										</li>
									{/each}
								</ul>
							{/if}
						</div>
						<div class="links">
							{#each job.sources as source (source.url)}
								<!-- External link to the posting, not an app route. -->
								<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
								<a href={source.url} target="_blank" rel="noopener noreferrer" class="source"
									>{sourceLabels[source.source] ?? source.source}
									<Icon name="external-link" size={13} /></a
								>
							{/each}
						</div>
					</li>
				{/each}
			</ul>
			{#if matches.length < data.matches.total}
				<button type="button" class="more" disabled={loadingMore} onclick={loadMore}>
					<Icon name={loadingMore ? 'loader' : 'chevron-down'} size={16} />
					Mehr laden ({data.matches.total - matches.length})
				</button>
			{/if}
		{:else}
			<p class="muted">
				{data.filters.onlyNew
					? 'Keine neuen Stellen.'
					: data.filters.excluded
						? 'Keine ausgeblendeten Stellen.'
						: 'Noch keine Stellen bewertet.'}
			</p>
		{/if}
	</div>
	{#if selectedId !== null}
		<div class="panel">
			<JobDetail
				jobId={selectedId}
				layout="panel"
				onclose={() => select(null)}
				onupdate={(m) => (patched[m.job.id] = m)}
			/>
		</div>
	{/if}
</div>

<style>
	/* The list keeps its width when the panel opens; the panel takes the rest. */
	.master {
		display: grid;
		grid-template-columns: minmax(0, 56rem);
		gap: 1rem;
		align-items: start;
	}
	.master.split {
		grid-template-columns: minmax(0, 56rem) minmax(30rem, 1fr);
	}
	/* Below the sticky page header, scrolling on its own. */
	.panel {
		position: sticky;
		top: 5.6rem;
		margin-top: 1.5rem;
	}
	.panel :global(.detail) {
		max-height: calc(100vh - 6.8rem);
		overflow-y: auto;
		box-sizing: border-box;
	}
	@media (max-width: 1100px) {
		.master.split {
			grid-template-columns: minmax(0, 56rem);
		}
		.panel {
			display: none;
		}
	}
	.job.selected {
		border-color: var(--accent);
		box-shadow: inset 3px 0 0 var(--accent);
	}
	.pagehead {
		position: sticky;
		top: 0;
		z-index: 10;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1rem;
		margin: -1.5rem 0 1rem;
		padding: 1.25rem 0 0.9rem;
		background: var(--bg);
		border-bottom: 1px solid var(--border);
	}
	/* Cancel main's top padding (see +layout.svelte) so nothing scrolls above the header. */
	@media (max-width: 700px) {
		.pagehead {
			margin-top: -1rem;
			padding-top: 0.75rem;
		}
	}
	h1 {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin: 0 0.5rem 0 0;
		min-height: 2.7rem;
	}
	.start {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.55rem 1.3rem;
		font-size: 1.05rem;
		font-weight: 600;
		border-radius: 999px;
	}
	.status,
	.health,
	.health span,
	.meta span,
	.runhead span,
	.errors summary,
	.reason,
	.seen {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.health {
		margin-left: auto;
		gap: 0.9rem;
		font-size: 0.85rem;
	}
	.banner {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.run.failed {
		border-color: var(--error);
	}
	.runhead {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1.25rem;
	}
	.runhead h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0;
	}
	.summary {
		margin-left: auto;
	}
	.bar {
		height: 0.5rem;
		margin-top: 1rem;
		border-radius: 999px;
		background: var(--chip);
		overflow: hidden;
	}
	.bar div {
		height: 100%;
		background: var(--accent);
		transition: width 0.4s;
	}
	.step {
		margin: 0.5rem 0 0;
		font-size: 0.9rem;
	}
	.stats {
		margin-top: 1rem;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	.stats th {
		font-weight: 500;
		color: var(--muted);
	}
	.stats th,
	.stats td {
		padding: 0.25rem 0.9rem 0.25rem 0;
		text-align: right;
	}
	.stats th:first-child,
	.stats td:first-child {
		text-align: left;
	}
	.errors {
		margin-top: 0.75rem;
		font-size: 0.9rem;
	}
	.errors summary {
		cursor: pointer;
	}
	.errors ul {
		margin: 0.5rem 0 0;
		padding-left: 1.2rem;
	}
	.toolbar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1rem;
		margin: 1.5rem 0 0.9rem;
	}
	.segmented {
		display: inline-flex;
		border: 1px solid var(--border);
		border-radius: 999px;
		overflow: hidden;
	}
	.segmented button {
		border: none;
		border-radius: 0;
		padding: 0.35rem 0.9rem;
		background: var(--surface);
	}
	.segmented button + button {
		border-left: 1px solid var(--border);
	}
	.segmented button.on {
		background: var(--accent);
		color: var(--accent-text);
	}
	.count {
		font-size: 0.8rem;
		opacity: 0.8;
	}
	.seen {
		margin-left: auto;
	}
	.jobs {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.6rem;
	}
	.job {
		margin: 0;
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		gap: 1rem;
		align-items: start;
	}
	.job.seen .title a {
		font-weight: 500;
	}
	.body {
		display: grid;
		gap: 0.4rem;
		min-width: 0;
	}
	.title {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		font-size: 1.05rem;
		font-weight: 600;
	}
	.title a {
		color: var(--text);
		text-decoration: none;
	}
	.title a:hover {
		color: var(--accent);
	}
	.badge.new {
		background: var(--accent);
		color: var(--accent-text);
	}
	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.1rem;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.evidence {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		list-style: none;
		margin: 0.15rem 0 0;
		padding: 0;
		font-size: 0.82rem;
	}
	.evidence li {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.1rem 0.55rem;
		border-radius: 999px;
		border: 1px solid var(--border);
	}
	.evidence .hit {
		color: var(--ok);
	}
	.evidence .miss {
		color: var(--error);
	}
	.reason {
		margin: 0.15rem 0 0;
		font-size: 0.9rem;
	}
	.links {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.25rem;
	}
	.source {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.85rem;
		color: var(--accent);
		text-decoration: none;
	}
	.more {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin: 1rem auto 0;
	}
	@media (max-width: 700px) {
		.job {
			grid-template-columns: auto minmax(0, 1fr);
		}
		.links {
			grid-column: 2;
			flex-direction: row;
			align-items: center;
		}
	}
</style>
