<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import ChipInput from '#lib/components/ChipInput.svelte';
	import ChipList from '#lib/components/ChipList.svelte';
	import CvChangesPanel from '#lib/components/CvChangesPanel.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import SectionHead from '#lib/components/SectionHead.svelte';
	import SkillsEditor from '#lib/components/SkillsEditor.svelte';
	import { languageLevelLabels, remoteLabels, stationKindLabels } from '#lib/labels.ts';
	import { fade } from 'svelte/transition';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	// Deeply reactive, editable copy of the saved profile; recreated when the page data reloads.
	const profile = $derived.by(() => {
		const editable = $state<Schemas['ProfileData-Output']>(structuredClone(data.profile));
		return editable;
	});
	const saved = $derived(JSON.stringify(data.profile));

	const dirty = $derived(JSON.stringify(profile) !== saved);
	let saving = $state(false);
	let message = $state<{ kind: 'ok' | 'error'; text: string } | null>(null);
	let editingRoles = $state(false);

	async function save() {
		saving = true;
		message = null;
		const { error } = await api.PUT('/api/profile', { body: profile });
		saving = false;
		if (error) {
			message = { kind: 'error', text: errorMessage(error) };
			return;
		}
		// Reload first: until the page data is fresh, the form would still count as dirty.
		await invalidateAll();
		message = { kind: 'ok', text: 'Gespeichert.' };
	}

	async function applyChanges(ids: string[]) {
		if (!data.changes) return;
		const { error } = await api.POST('/api/profile/cv-changes/apply', {
			body: { document_id: data.changes.document_id, change_ids: ids }
		});
		message = error
			? { kind: 'error', text: errorMessage(error) }
			: { kind: 'ok', text: `${ids.length} Vorschläge übernommen.` };
		await invalidateAll();
	}

	// While a CV is being read, check every few seconds for the result. The backend fills
	// the profile itself, so the form is locked meanwhile (a reload would drop edits).
	$effect(() => {
		if (!data.extracting) return;
		const timer = setInterval(() => invalidateAll(), 3000);
		return () => clearInterval(timer);
	});

	// Success messages fade after a few seconds, or as soon as there are new edits.
	$effect(() => {
		if (message?.kind !== 'ok') return;
		if (dirty) {
			message = null;
			return;
		}
		const timer = setTimeout(() => (message = null), 4000);
		return () => clearTimeout(timer);
	});

	let wasExtracting = false;
	$effect(() => {
		if (wasExtracting && !data.extracting) {
			message = { kind: 'ok', text: 'Lebenslauf ausgelesen, neue Angaben wurden eingetragen.' };
		}
		wasExtracting = data.extracting;
	});

	function addRole(role: string) {
		if (!profile.roles.some((r) => r.toLowerCase() === role.toLowerCase())) {
			profile.roles.push(role);
		}
	}

	// Empty number inputs yield undefined; the API expects null.
	const toOptionalNumber = (v: number | null | undefined) => (typeof v === 'number' ? v : null);
</script>

<div class="pagehead">
	<h1><Icon name="user" size={28} /> Profil</h1>
	{#if dirty || saving}
		<button
			type="submit"
			form="profile-form"
			class="primary save"
			disabled={saving || data.extracting}
			transition:fade={{ duration: 150 }}
		>
			<Icon name={saving ? 'loader' : 'save'} size={18} class={saving ? 'spin' : ''} />
			{saving ? 'Speichert …' : 'Speichern'}
		</button>
		<span class="warn status" transition:fade={{ duration: 150 }}
			><Icon name="circle-alert" size={16} /> Ungespeicherte Änderungen</span
		>
	{/if}
	{#if message}<span class="{message.kind} status"
			><Icon name={message.kind === 'ok' ? 'circle-check' : 'circle-alert'} size={16} />
			{message.text}</span
		>{/if}
	<a class="upload" href={resolve('/documents')}><Icon name="upload" size={16} /> Lebenslauf</a>
</div>

{#if data.extracting}
	<p class="card banner">
		<Icon name="loader" class="spin" />
		Lebenslauf wird gerade ausgelesen … Die Angaben werden danach automatisch eingetragen.
	</p>
{:else if data.changes && data.changes.changes.length}
	<CvChangesPanel
		changes={data.changes}
		disabledReason={dirty ? 'Erst die Änderungen speichern.' : null}
		onapply={applyChanges}
	/>
{:else if !data.changes}
	<p class="card banner muted">
		<Icon name="file-text" />
		<span
			>Tipp: <a href={resolve('/documents')}>Lebenslauf hochladen</a>, dann wird das Profil
			automatisch ausgefüllt.</span
		>
	</p>
{/if}

<form
	id="profile-form"
	onsubmit={(e) => {
		e.preventDefault();
		save();
	}}
>
	<fieldset class="layout" disabled={data.extracting}>
		<div class="col">
			<section class="card">
				<h2><Icon name="user" size={22} /> Kontakt</h2>
				<div class="grid">
					<label
						><span class="lbl"><Icon name="user" size={15} /> Name</span>
						<input bind:value={profile.contact.name} autocomplete="name" /></label
					>
					<label
						><span class="lbl"><Icon name="mail" size={15} /> E-Mail</span>
						<input type="email" bind:value={profile.contact.email} autocomplete="email" /></label
					>
					<label
						><span class="lbl"><Icon name="phone" size={15} /> Telefon</span>
						<input bind:value={profile.contact.phone} autocomplete="tel" /></label
					>
					<label
						><span class="lbl"><Icon name="house" size={15} /> Adresse</span>
						<input bind:value={profile.contact.address} /></label
					>
				</div>
			</section>

			<section class="card">
				<SectionHead
					icon="target"
					title="Wunschrollen"
					bind:editing={editingRoles}
					onadd={addRole}
					addPlaceholder="z. B. Fullstack Developer"
				/>
				<ChipList
					items={profile.roles}
					key={(r) => r.toLowerCase()}
					text={(r) => r}
					editing={editingRoles}
					onremove={(r) => profile.roles.splice(profile.roles.indexOf(r), 1)}
				/>
			</section>

			<section class="card">
				<SkillsEditor bind:skills={profile.skills} />
			</section>

			<section class="card">
				<h2><Icon name="briefcase" size={22} /> Werdegang</h2>
				{#each profile.experience as station, i (i)}
					<div class="entry">
						<div class="fields">
							<input
								bind:value={station.role}
								placeholder="Rolle"
								aria-label="Rolle"
								class="wide"
							/>
							<input
								bind:value={station.employer}
								placeholder="Arbeitgeber"
								aria-label="Arbeitgeber"
								class="wide"
							/>
							<select bind:value={station.kind} aria-label="Art">
								{#each Object.entries(stationKindLabels) as [value, text] (value)}
									<option {value}>{text}</option>
								{/each}
							</select>
						</div>
						<div class="fields">
							<Icon name="calendar" size={16} class="muted" />
							<input type="month" bind:value={station.start} aria-label="Von" />
							<span class="muted">–</span>
							{#if station.current}
								<span class="muted">heute</span>
							{:else}
								<input type="month" bind:value={station.end} aria-label="Bis" />
							{/if}
							<label class="inline"
								><input type="checkbox" bind:checked={station.current} /> aktuell</label
							>
						</div>
						<button
							type="button"
							class="icon remove"
							aria-label="Station entfernen"
							title="Entfernen"
							onclick={() => profile.experience.splice(i, 1)}
							><Icon name="trash" size={16} /></button
						>
					</div>
				{/each}
				<button
					type="button"
					class="add"
					onclick={() =>
						profile.experience.unshift({
							employer: '',
							role: '',
							kind: 'employment',
							start: null,
							end: null,
							current: false
						})}><Icon name="plus" size={16} /> Station</button
				>
			</section>

			<section class="card">
				<h2><Icon name="graduation-cap" size={22} /> Ausbildung</h2>
				{#each profile.education as entry, i (i)}
					<div class="entry">
						<div class="fields">
							<input
								bind:value={entry.degree}
								placeholder="Abschluss"
								aria-label="Abschluss"
								class="wide"
							/>
							<input
								bind:value={entry.institution}
								placeholder="Einrichtung"
								aria-label="Einrichtung"
								class="wide"
							/>
						</div>
						<div class="fields">
							<Icon name="calendar" size={16} class="muted" />
							<input type="month" bind:value={entry.start} aria-label="Von" />
							<span class="muted">–</span>
							<input type="month" bind:value={entry.end} aria-label="Bis" />
						</div>
						<button
							type="button"
							class="icon remove"
							aria-label="Eintrag entfernen"
							title="Entfernen"
							onclick={() => profile.education.splice(i, 1)}><Icon name="trash" size={16} /></button
						>
					</div>
				{/each}
				<button
					type="button"
					class="add"
					onclick={() =>
						profile.education.unshift({ institution: '', degree: '', start: null, end: null })}
					><Icon name="plus" size={16} /> Ausbildung</button
				>
			</section>
		</div>

		<div class="col">
			<section class="card">
				<h2><Icon name="map-pin" size={22} /> Orte & Remote</h2>
				{#each profile.locations as location, i (i)}
					<div class="row line">
						<input bind:value={location.name} placeholder="Ort" aria-label="Ort" class="grow" />
						<input
							type="number"
							min="0"
							max="500"
							bind:value={location.radius_km}
							class="narrow"
							aria-label="Umkreis in km"
						/>
						<span class="muted">km</span>
						<button
							type="button"
							class="icon"
							aria-label="Ort entfernen"
							onclick={() => profile.locations.splice(i, 1)}><Icon name="x" size={16} /></button
						>
					</div>
				{/each}
				<button
					type="button"
					class="add"
					onclick={() => profile.locations.push({ name: '', radius_km: 30 })}
					><Icon name="plus" size={16} /> Ort</button
				>
				<label class="spaced"
					><span class="lbl"><Icon name="house" size={15} /> Remote</span>
					<select bind:value={profile.remote_pref}>
						{#each Object.entries(remoteLabels) as [value, text] (value)}
							<option {value}>{text}</option>
						{/each}
					</select>
				</label>
			</section>

			<section class="card">
				<h2><Icon name="wallet" size={22} /> Gehalt & Erfahrung</h2>
				<div class="stack">
					<label
						><span class="lbl">Mindestgehalt (brutto/Jahr, €)</span>
						<input
							type="number"
							min="0"
							step="1000"
							bind:value={
								() => profile.salary_min, (v) => (profile.salary_min = toOptionalNumber(v))
							}
						/>
					</label>
					<label
						><span class="lbl">Berufserfahrung (Jahre)</span>
						<input
							type="number"
							min="0"
							step="0.1"
							bind:value={
								() => profile.seniority_years,
								(v) => (profile.seniority_years = toOptionalNumber(v))
							}
						/>
					</label>
				</div>
			</section>

			<section class="card">
				<h2><Icon name="languages" size={22} /> Sprachen</h2>
				{#each profile.languages as language, i (i)}
					<div class="row line">
						<input
							bind:value={language.language}
							placeholder="Sprache"
							aria-label="Sprache"
							class="grow"
						/>
						<select bind:value={language.level} aria-label="Niveau">
							{#each Object.entries(languageLevelLabels) as [value, text] (value)}
								<option {value}>{text}</option>
							{/each}
						</select>
						<button
							type="button"
							class="icon"
							aria-label="Sprache entfernen"
							onclick={() => profile.languages.splice(i, 1)}><Icon name="x" size={16} /></button
						>
					</div>
				{/each}
				<button
					type="button"
					class="add"
					onclick={() => profile.languages.push({ language: '', level: 'B2' })}
					><Icon name="plus" size={16} /> Sprache</button
				>
			</section>

			<section class="card">
				<h2><Icon name="ban" size={22} /> Ausschlüsse & Firmen</h2>
				<div class="stack">
					<label
						>Ausschlusswörter
						<ChipInput
							bind:items={profile.exclude_keywords}
							label="Ausschlusswörter"
							placeholder="z. B. Zeitarbeit"
						/>
					</label>
					<label
						>Ausgeschlossene Firmen
						<ChipInput bind:items={profile.exclude_companies} label="Ausgeschlossene Firmen" />
					</label>
					<label
						>Bevorzugte Firmen
						<ChipInput bind:items={profile.preferred_companies} label="Bevorzugte Firmen" />
					</label>
				</div>
			</section>

			<section class="card">
				<h2><Icon name="pen-line" size={22} /> Anschreiben</h2>
				<div class="stack">
					<label
						>Ton
						<input
							bind:value={profile.tone}
							placeholder="z. B. freundlich, direkt, ohne Floskeln"
						/>
					</label>
					<label
						>Feste Stichpunkte (kommen in jedes Anschreiben)
						<ChipInput bind:items={profile.cover_letter_bullets} label="Stichpunkte" />
					</label>
				</div>
			</section>
		</div>
	</fieldset>
</form>

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
	h1 {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin: 0 0.5rem 0 0;
		/* Same height as the save button, so the header does not jump when it appears. */
		min-height: 2.7rem;
	}
	.save {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.55rem 1.3rem;
		font-size: 1.05rem;
		font-weight: 600;
		border-radius: 999px;
	}
	.status {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.upload {
		margin-left: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		color: var(--accent);
		text-decoration: none;
	}
	.banner {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 3fr) minmax(20rem, 2fr);
		gap: 1rem;
		align-items: start;
		border: none;
		margin: 0;
		padding: 0;
		min-width: 0;
	}
	.layout:disabled {
		opacity: 0.6;
	}
	/* Cancel main's top padding (see +layout.svelte) so nothing scrolls above the header. */
	@media (max-width: 700px) {
		.pagehead {
			margin-top: -1rem;
			padding-top: 0.75rem;
		}
	}
	@media (max-width: 1100px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.col {
		min-width: 0;
	}
	.col > .card:last-child {
		margin-bottom: 0;
	}
	.card h2 {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		font-size: 1.35rem;
		margin-bottom: 1rem;
	}
	.lbl {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.entry {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.5rem 0.75rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--border);
	}
	.entry:first-of-type {
		padding-top: 0;
	}
	.entry .fields {
		grid-column: 1;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.entry .remove {
		grid-column: 2;
		grid-row: 1 / span 2;
		align-self: center;
	}
	.remove:hover {
		color: var(--error);
	}
	.wide {
		flex: 1 1 14rem;
	}
	.grow {
		flex: 1;
	}
	.line {
		margin-bottom: 0.5rem;
	}
	.inline {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.narrow {
		width: 5rem;
	}
	.stack {
		display: grid;
		gap: 0.75rem;
	}
	.spaced {
		margin-top: 1rem;
	}
	button.add {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		margin-top: 0.75rem;
	}
	input[type='month'] {
		width: 9.5rem;
	}
</style>
