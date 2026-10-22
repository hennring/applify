<script lang="ts">
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';
	import type { PageProps } from './$types';

	type Source = Schemas['SourceOut'];

	let { data }: PageProps = $props();

	// Page data, replaced by every answer of the API.
	let settings = $derived(data.settings);
	let error = $state<string | null>(null);
	let busy = $state<string | null>(null);
	// Editable values, recreated whenever the settings change: per source and field
	// (secrets start empty, meaning "unchanged"), and the contact address.
	const drafts = $derived.by(() => {
		const editable = $state<Record<string, Record<string, string>>>(
			Object.fromEntries((settings?.sources ?? []).map((s) => [s.key, { ...s.fields }]))
		);
		return editable;
	});
	const general = $derived.by(() => {
		const editable = $state({ contact: settings?.contact ?? '' });
		return editable;
	});

	const fieldLabels: Record<string, string> = {
		app_id: 'App-ID',
		app_key: 'App-Key',
		token: 'Persönlicher Zugriffstoken'
	};
	const jobSources = $derived(settings?.sources.filter((s) => s.kind === 'jobs') ?? []);
	const discovery = $derived(settings?.sources.filter((s) => s.kind === 'discovery') ?? []);

	function fieldNames(source: Source): string[] {
		return [...Object.keys(source.fields), ...Object.keys(source.secrets)];
	}

	function dirty(source: Source): boolean {
		const draft = drafts[source.key] ?? {};
		return fieldNames(source).some((name) =>
			name in source.secrets ? !!draft[name] : (draft[name] ?? '') !== source.fields[name]
		);
	}

	async function update(source: Source, body: Schemas['SourcePatch']) {
		busy = source.key;
		error = null;
		const response = await api.PUT('/api/settings/sources/{key}', {
			params: { path: { key: source.key } },
			body
		});
		busy = null;
		if (response.error || !response.data) {
			error = errorMessage(response.error);
			return;
		}
		settings = response.data;
	}

	function saveFields(source: Source) {
		const draft = drafts[source.key] ?? {};
		// Empty secrets mean "keep"; only send what was typed.
		const config = Object.fromEntries(
			fieldNames(source)
				.filter((name) => !(name in source.secrets) || draft[name])
				.map((name) => [name, draft[name] ?? ''])
		);
		return update(source, { config });
	}

	function removeSecret(source: Source, name: string) {
		return update(source, { config: { [name]: '' } });
	}

	async function saveContact() {
		busy = 'general';
		error = null;
		const response = await api.PUT('/api/settings/general', { body: { contact: general.contact } });
		busy = null;
		if (response.error || !response.data) error = errorMessage(response.error);
		else settings = response.data;
	}
</script>

<div class="pagehead">
	<h1><Icon name="wrench" size={28} /> Einstellungen</h1>
</div>

{#if error}<p class="card error" role="alert">{error}</p>{/if}

{#if !settings}
	<p class="card error">Einstellungen konnten nicht geladen werden.</p>
{:else}
	<div class="layout">
		<div class="col">
			<section class="card">
				<h2><Icon name="search" size={18} /> Stellenquellen</h2>
				<p class="muted small">
					Jede Quelle lässt sich einzeln abschalten. Zahlen: Stellen im Bestand und Ergebnis des
					letzten Suchlaufs.
				</p>
				<ul class="sources">
					{#each jobSources as source (source.key)}
						{@render sourceRow(source)}
					{/each}
				</ul>
			</section>
		</div>
		<div class="col">
			<section class="card">
				<h2><Icon name="building" size={18} /> Firmen-Discovery</h2>
				<p class="muted small">
					Findet Firmen mit Sitz in den Profil-Orten für die Watchlist. Läuft höchstens einmal pro
					Woche und Ort; nur Firmen mit erkannter Karriereseite erscheinen unter Firmen.
				</p>
				<ul class="sources">
					{#each discovery as source (source.key)}
						{@render sourceRow(source)}
					{/each}
				</ul>
			</section>

			<section class="card">
				<h2><Icon name="mail" size={18} /> Kontaktadresse für Abrufe</h2>
				<p class="muted small">
					Wird im User-Agent jeder Anfrage mitgeschickt, damit Betreiber sich melden können
					(höfliches Abrufen). Wikidata verlangt sie. Sonst werden keine persönlichen Daten
					übertragen.
				</p>
				<form
					class="row"
					onsubmit={(e) => {
						e.preventDefault();
						saveContact();
					}}
				>
					<input
						type="text"
						bind:value={general.contact}
						placeholder="E-Mail-Adresse oder URL"
						aria-label="Kontaktadresse"
						class="grow"
					/>
					<button
						type="submit"
						class="primary"
						disabled={busy === 'general' || general.contact === settings.contact}
					>
						<Icon name="save" size={16} /> Speichern
					</button>
				</form>
				{#if settings.contact_from_env}
					<p class="muted small">Aktuell aus der Umgebungsvariable APPLIFY_HTTP_CONTACT.</p>
				{/if}
			</section>
		</div>
	</div>
{/if}

{#snippet sourceRow(source: Source)}
	<li class:off={!source.enabled}>
		<div class="srchead">
			<label class="switch">
				<input
					type="checkbox"
					checked={source.enabled}
					disabled={busy === source.key}
					onchange={(e) => update(source, { enabled: e.currentTarget.checked })}
				/>
				<strong>{source.label}</strong>
			</label>
			<span class="count muted small">
				{source.count}
				{source.kind === 'jobs' ? 'Stellen' : 'Firmen'}
			</span>
		</div>
		<p class="muted small desc">{source.description}</p>
		{#if source.last_run}
			<p class="small lastrun">
				Letzter Lauf: {source.last_run.found} gefunden · <strong>{source.last_run.new} neu</strong>
				{#if source.last_run.filtered}· {source.last_run.filtered} vorgefiltert{/if}
				{#if source.last_run.errors}<span class="error">· {source.last_run.errors} Fehler</span
					>{/if}
			</p>
		{/if}
		{#if source.enabled && source.missing.length}
			<p class="small warn">
				<Icon name="circle-alert" size={14} /> Wird übersprungen, bis
				{source.missing.map((m) => fieldLabels[m] ?? m).join(' und ')} eingetragen
				{source.missing.length > 1 ? 'sind' : 'ist'}.
			</p>
		{/if}
		{#if fieldNames(source).length}
			<form
				class="fields"
				onsubmit={(e) => {
					e.preventDefault();
					saveFields(source);
				}}
			>
				{#each Object.keys(source.fields) as name (name)}
					<label>
						{fieldLabels[name] ?? name}
						<input type="text" bind:value={drafts[source.key][name]} autocomplete="off" />
					</label>
				{/each}
				{#each Object.keys(source.secrets) as name (name)}
					<label>
						<span class="row"
							>{fieldLabels[name] ?? name}
							{#if source.secrets[name]}
								<span class="badge ok">gesetzt</span>
								<button
									type="button"
									class="icon"
									aria-label="{fieldLabels[name] ?? name} entfernen"
									onclick={() => removeSecret(source, name)}><Icon name="trash" size={14} /></button
								>
							{/if}</span
						>
						<input
							type="password"
							bind:value={drafts[source.key][name]}
							placeholder={source.secrets[name] ? 'unverändert' : ''}
							autocomplete="off"
						/>
					</label>
				{/each}
				<div>
					<button type="submit" class="primary" disabled={busy === source.key || !dirty(source)}>
						<Icon name="save" size={16} /> Speichern
					</button>
				</div>
			</form>
		{/if}
	</li>
{/snippet}

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
	.card h2 {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 1.1rem;
	}
	.small {
		font-size: 0.85rem;
	}
	.sources {
		list-style: none;
		margin: 0.5rem 0 0;
		padding: 0;
	}
	.sources li {
		padding: 0.85rem 0;
		border-top: 1px solid var(--border);
	}
	.sources li.off .desc,
	.sources li.off strong {
		opacity: 0.6;
	}
	.srchead {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}
	.switch {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		font-size: 1rem;
		color: var(--text);
		cursor: pointer;
	}
	.switch input {
		width: 1.1rem;
		height: 1.1rem;
		accent-color: var(--accent);
	}
	.desc,
	.lastrun,
	.warn {
		margin: 0.3rem 0 0 1.65rem;
	}
	.warn {
		display: flex;
		align-items: center;
		gap: 0.3rem;
	}
	.fields {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
		align-items: end;
		gap: 0.6rem;
		margin: 0.6rem 0 0 1.65rem;
	}
	.fields button,
	form.row button {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.grow {
		flex: 1;
	}
	.badge.ok {
		color: var(--ok);
	}
</style>
