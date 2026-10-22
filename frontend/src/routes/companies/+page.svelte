<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import { atsLabels, companyStatusLabels, discoveredLabels, formatDateTime } from '#lib/labels.ts';
	import type { PageProps } from './$types';

	type Company = Schemas['CompanyOut'];
	type Status = Company['status'];

	let { data }: PageProps = $props();

	let url = $state('');
	let name = $state('');
	let adding = $state(false);
	let error = $state<string | null>(null);
	let busy = $state<number | null>(null);
	let query = $derived(data.filters.q);
	// Rows changed on this page, until the next load.
	let patched = $state<Record<number, Company>>({});

	const items = $derived(data.page.items.map((c) => patched[c.id] ?? c));

	function href(next: { status?: Status | null; feed?: boolean; q?: string }) {
		const f = { ...data.filters, ...next };
		const params = [
			f.status ? `status=${f.status}` : '',
			f.feed ? 'feed=1' : '',
			f.q ? `q=${encodeURIComponent(f.q)}` : ''
		].filter(Boolean);
		return `${resolve('/companies')}${params.length ? `?${params.join('&')}` : ''}`;
	}

	function filter(next: { status?: Status | null; feed?: boolean; q?: string }) {
		patched = {};
		// Same route, only the query string changes.
		// eslint-disable-next-line svelte/no-navigation-without-resolve
		return goto(href(next), { replace: true, reset: false });
	}

	async function add(e: SubmitEvent) {
		e.preventDefault();
		adding = true;
		error = null;
		const response = await api.POST('/api/companies', { body: { url, name } });
		adding = false;
		if (response.error) {
			error = errorMessage(response.error);
			return;
		}
		url = '';
		name = '';
		await invalidateAll();
	}

	async function setStatus(company: Company, status: Status) {
		busy = company.id;
		const response = await api.PATCH('/api/companies/{company_id}', {
			params: { path: { company_id: company.id } },
			body: { status }
		});
		busy = null;
		if (response.data) patched[company.id] = response.data;
		else error = errorMessage(response.error);
	}

	async function redetect(company: Company) {
		busy = company.id;
		const response = await api.POST('/api/companies/{company_id}/detect', {
			params: { path: { company_id: company.id } }
		});
		busy = null;
		if (response.data) patched[company.id] = response.data;
		else error = errorMessage(response.error);
	}

	function external(link: string | null): string | null {
		if (!link) return null;
		return link.startsWith('http') ? link : `https://${link}`;
	}
</script>

<div class="pagehead">
	<h1><Icon name="building" size={28} /> Firmen</h1>
	<p class="muted summary">
		{data.page.total} Firmen · <strong>{data.page.with_feed} mit Karriereseite</strong> ·
		{data.page.watched} beobachtet
		{#if data.page.pending}· {data.page.pending} warten auf Erkennung{/if}
	</p>
</div>

<section class="card">
	<form class="add" onsubmit={add}>
		<label class="grow">
			Karriereseite oder Website
			<input
				type="text"
				bind:value={url}
				placeholder="z. B. firma.de/karriere oder firma.jobs.personio.de"
				required
			/>
		</label>
		<label>
			Name (optional)
			<input type="text" bind:value={name} placeholder="aus der URL" />
		</label>
		<button type="submit" class="primary" disabled={adding || url.trim().length < 4}>
			<Icon name={adding ? 'loader' : 'plus'} size={16} class={adding ? 'spin' : ''} />
			{adding ? 'Erkennt …' : 'Hinzufügen'}
		</button>
	</form>
	<p class="muted small">
		Das Bewerbersystem wird automatisch erkannt (Personio, Greenhouse, Lever, Recruitee,
		SmartRecruiters, Workday oder JSON-LD). Manuell hinzugefügte Firmen werden beobachtet.
	</p>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<div class="toolbar">
	<div class="segmented" role="group" aria-label="Status">
		<button type="button" class:on={!data.filters.status} onclick={() => filter({ status: null })}
			>Alle</button
		>
		{#each ['watch', 'candidate', 'ignore'] as const as status (status)}
			<button
				type="button"
				class:on={data.filters.status === status}
				onclick={() => filter({ status })}>{companyStatusLabels[status]}</button
			>
		{/each}
	</div>
	<label class="check">
		<input
			type="checkbox"
			checked={data.filters.feed}
			onchange={(e) => filter({ feed: e.currentTarget.checked })}
		/>
		nur mit Karriereseite
	</label>
	<form
		class="search"
		onsubmit={(e) => {
			e.preventDefault();
			filter({ q: query.trim() });
		}}
	>
		<input type="search" bind:value={query} placeholder="Firma suchen" aria-label="Firma suchen" />
	</form>
</div>

{#if !items.length}
	<p class="card banner muted">
		<Icon name="building" />
		{data.page.total
			? 'Keine Firmen für diesen Filter.'
			: 'Noch keine Firmen. Sie kommen mit dem nächsten Suchlauf aus den Treffern und der Discovery – oder hier per URL.'}
	</p>
{:else}
	<ul class="companies">
		{#each items as company (company.id)}
			{@const site = external(company.website)}
			{@const careers = external(company.careers_url)}
			<li class="card" class:ignored={company.status === 'ignore'}>
				<div class="main">
					<div class="name">
						<strong>{company.name}</strong>
						{#if site}
							<!-- External company site, not an app route. -->
							<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
							<a class="muted small" href={site} target="_blank" rel="noopener noreferrer"
								>{site.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')}</a
							>
						{/if}
					</div>
					<div class="meta small">
						<span
							class="badge ats"
							class:found={company.ats_type !== 'unknown'}
							title={company.ats_token ?? ''}
						>
							{atsLabels[company.ats_type] ?? company.ats_type}
						</span>
						{#if careers}
							<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
							<a href={careers} target="_blank" rel="noopener noreferrer"
								>Karriereseite <Icon name="external-link" size={12} /></a
							>
						{/if}
						<span class="muted">{discoveredLabels[company.discovered_from]}</span>
						{#if company.detection_status === 'pending'}
							<span class="muted"><Icon name="clock" size={13} /> wartet auf Erkennung</span>
						{/if}
						{#if company.last_checked_at}
							<span class="muted">abgerufen {formatDateTime(company.last_checked_at)}</span>
						{/if}
					</div>
					{#if company.last_error}
						<p class="error small lasterror">
							<Icon name="circle-alert" size={13} />
							{company.last_error}
						</p>
					{/if}
				</div>
				<div class="jobs" title="Stellen in der Tagesliste / im Bestand">
					<strong>{company.visible_jobs}</strong>
					<span class="muted small">/ {company.jobs} Stellen</span>
				</div>
				<div class="actions">
					<div class="segmented small" role="group" aria-label="Status von {company.name}">
						{#each ['watch', 'candidate', 'ignore'] as const as status (status)}
							<button
								type="button"
								class:on={company.status === status}
								disabled={busy === company.id}
								onclick={() => setStatus(company, status)}>{companyStatusLabels[status]}</button
							>
						{/each}
					</div>
					<button
						type="button"
						class="icon"
						title="Karriereseite neu erkennen"
						aria-label="{company.name}: Karriereseite neu erkennen"
						disabled={busy === company.id}
						onclick={() => redetect(company)}
					>
						<Icon
							name={busy === company.id ? 'loader' : 'search'}
							size={16}
							class={busy === company.id ? 'spin' : ''}
						/>
					</button>
				</div>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.summary {
		margin: 0;
	}
	.small {
		font-size: 0.85rem;
	}
	.add {
		display: flex;
		flex-wrap: wrap;
		align-items: end;
		gap: 0.6rem;
	}
	.add button {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.grow {
		flex: 1 1 22rem;
	}
	.toolbar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1.25rem;
		margin-bottom: 1rem;
	}
	.check {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.95rem;
		color: var(--text);
	}
	.search {
		margin-left: auto;
	}
	.banner {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.companies {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.companies li {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto auto;
		gap: 0.5rem 1.5rem;
		align-items: center;
		margin-bottom: 0.6rem;
	}
	.companies li.ignored {
		opacity: 0.6;
	}
	@media (max-width: 800px) {
		.companies li {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.name {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.3rem 0.75rem;
		font-size: 1.05rem;
	}
	.name a {
		text-decoration: none;
	}
	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.9rem;
		margin-top: 0.35rem;
	}
	.meta span,
	.meta a,
	.lasterror {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}
	.meta a {
		color: var(--accent);
		text-decoration: none;
	}
	.badge.ats.found {
		background: var(--accent);
		color: var(--accent-text);
	}
	.lasterror {
		margin: 0.35rem 0 0;
	}
	.jobs {
		white-space: nowrap;
	}
	.actions {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.segmented.small button {
		padding: 0.25rem 0.7rem;
		font-size: 0.85rem;
	}
</style>
