<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { healthRows } from '#lib/health.ts';
	import {
		formatDate,
		formatDateTime,
		formatSalary,
		jobRemoteLabels,
		runStatusLabels,
		sourceLabels
	} from '#lib/labels.ts';
	import { JOB_PAGE_SIZE } from '#lib/jobs.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Live copy of the run while it is polled; reset when the page data reloads.
	let polled = $state<Schemas['RunOut'] | null>(null);
	const run = $derived(polled && polled.id === data.run?.id ? polled : data.run);
	const running = $derived(run?.status === 'running');

	let starting = $state(false);
	let error = $state<string | null>(null);
	let more = $state<Schemas['JobOut'][]>([]);
	let loadingMore = $state(false);
	const jobs = $derived([...data.jobs.items, ...more]);

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

	// While a run is going, refresh its progress every two seconds; reload the list after.
	$effect(() => {
		const id = run?.id;
		if (!running || id === undefined) return;
		const timer = setInterval(async () => {
			const { data: fresh } = await api.GET('/api/runs/{run_id}', {
				params: { path: { run_id: id } }
			});
			if (!fresh) return;
			polled = fresh;
			if (fresh.status !== 'running') {
				more = [];
				await invalidateAll();
			}
		}, 2000);
		return () => clearInterval(timer);
	});

	async function loadMore() {
		loadingMore = true;
		const { data: page } = await api.GET('/api/jobs', {
			params: { query: { limit: JOB_PAGE_SIZE, offset: jobs.length } }
		});
		loadingMore = false;
		if (page) more = [...more, ...page.items];
	}

	// Jobs first seen in the latest run are new (F10).
	const isNew = (job: Schemas['JobOut']) =>
		!!data.run && new Date(job.first_seen_at) >= new Date(data.run.started_at);

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

<section>
	<h2 class="listhead">
		Stellen <span class="count">{data.jobs.total}</span>
		<span class="muted hint">nach Veröffentlichung, neueste zuerst – Ranking folgt in M3</span>
	</h2>
	{#if jobs.length}
		<ul class="jobs">
			{#each jobs as job (job.id)}
				{@const salary = formatSalary(job.salary_min, job.salary_max)}
				<li class="card job">
					<div class="title">
						<!-- External link to the posting, not an app route. -->
						<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
						<a href={job.sources[0]?.url} target="_blank" rel="noopener noreferrer">{job.title}</a>
						{#if isNew(job)}<span class="badge new">neu</span>{/if}
						{#if !job.has_full_text}<span class="badge" title="Kein Anzeigentext verfügbar"
								>nur Kurzinfo</span
							>{/if}
					</div>
					<div class="meta">
						<span><Icon name="building" size={15} /> {job.company || '–'}</span>
						{#if job.location_raw}<span><Icon name="map-pin" size={15} /> {job.location_raw}</span
							>{/if}
						{#if job.remote_type}<span
								><Icon name="house" size={15} /> {jobRemoteLabels[job.remote_type]}</span
							>{/if}
						{#if salary}<span><Icon name="wallet" size={15} /> {salary}</span>{/if}
						{#if job.posted_at}<span
								><Icon name="calendar" size={15} /> {formatDate(job.posted_at)}</span
							>{/if}
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
		{#if jobs.length < data.jobs.total}
			<button type="button" class="more" disabled={loadingMore} onclick={loadMore}>
				<Icon name={loadingMore ? 'loader' : 'chevron-down'} size={16} />
				Mehr laden ({data.jobs.total - jobs.length})
			</button>
		{/if}
	{:else}
		<p class="muted">Noch keine Stellen gespeichert.</p>
	{/if}
</section>

<style>
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
	.errors summary {
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
		text-align: right;
	}
	.stats th:first-child,
	.stats td:first-child {
		text-align: left;
	}
	.stats th,
	.stats td {
		padding: 0.25rem 0.9rem 0.25rem 0;
		text-align: right;
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
	.listhead {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		margin: 1.5rem 0 0.75rem;
	}
	.count {
		font-size: 0.9rem;
		color: var(--muted);
		font-weight: 500;
	}
	.hint {
		font-size: 0.8rem;
		font-weight: 400;
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
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.4rem 1rem;
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
		grid-column: 1;
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.1rem;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.links {
		grid-column: 2;
		grid-row: 1 / span 2;
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
</style>
