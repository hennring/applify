<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, type Schemas } from '#lib/api/client.ts';
	import ChipInput from '#lib/components/ChipInput.svelte';
	import CvChangesPanel from '#lib/components/CvChangesPanel.svelte';
	import SkillsEditor from '#lib/components/SkillsEditor.svelte';
	import { languageLevelLabels, remoteLabels, stationKindLabels } from '#lib/labels.ts';
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

	async function save() {
		saving = true;
		message = null;
		const { error } = await api.PUT('/api/profile', { body: profile });
		saving = false;
		if (error) {
			message = { kind: 'error', text: errorMessage(error) };
			return;
		}
		message = { kind: 'ok', text: 'Gespeichert.' };
		await invalidateAll();
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

	// While a CV is being read, check every few seconds for the result.
	$effect(() => {
		if (!data.extracting) return;
		const timer = setInterval(() => invalidateAll(), 3000);
		return () => clearInterval(timer);
	});

	// Empty number inputs yield undefined; the API expects null.
	const toOptionalNumber = (v: number | null | undefined) => (typeof v === 'number' ? v : null);
</script>

<h1>Profil</h1>

{#if data.extracting}
	<p class="card">
		Lebenslauf wird gerade ausgelesen … Die Vorschläge erscheinen hier automatisch.
	</p>
{:else if data.changes && data.changes.changes.length}
	<CvChangesPanel
		changes={data.changes}
		disabledReason={dirty ? 'Erst die Änderungen unten speichern.' : null}
		onapply={applyChanges}
	/>
{:else if !data.changes}
	<p class="card muted">
		Tipp: <a href={resolve('/documents')}>Lebenslauf hochladen</a>, dann wird das Profil automatisch
		vorbefüllt.
	</p>
{/if}

<form
	onsubmit={(e) => {
		e.preventDefault();
		save();
	}}
>
	<section class="card">
		<h2>Kontakt</h2>
		<div class="grid">
			<label>Name <input bind:value={profile.contact.name} autocomplete="name" /></label>
			<label>E-Mail <input type="email" bind:value={profile.contact.email} /></label>
			<label>Telefon <input bind:value={profile.contact.phone} /></label>
			<label>Adresse <input bind:value={profile.contact.address} /></label>
		</div>
	</section>

	<section class="card">
		<h2>Wunschrollen</h2>
		<ChipInput
			bind:items={profile.roles}
			label="Wunschrollen"
			placeholder="z. B. Fullstack Developer"
		/>
	</section>

	<section class="card">
		<h2>Skills</h2>
		<SkillsEditor bind:skills={profile.skills} />
	</section>

	<section class="card">
		<h2>Orte & Remote</h2>
		{#each profile.locations as location, i (i)}
			<div class="row line">
				<input bind:value={location.name} placeholder="Ort" aria-label="Ort" />
				<label class="inline"
					>Umkreis
					<input type="number" min="0" max="500" bind:value={location.radius_km} class="narrow" /> km</label
				>
				<button
					type="button"
					class="icon"
					aria-label="Ort entfernen"
					onclick={() => profile.locations.splice(i, 1)}>×</button
				>
			</div>
		{/each}
		<div class="row line">
			<button type="button" onclick={() => profile.locations.push({ name: '', radius_km: 30 })}
				>+ Ort</button
			>
			<label class="inline"
				>Remote
				<select bind:value={profile.remote_pref}>
					{#each Object.entries(remoteLabels) as [value, text] (value)}
						<option {value}>{text}</option>
					{/each}
				</select>
			</label>
		</div>
	</section>

	<section class="card">
		<h2>Gehalt, Erfahrung & Sprachen</h2>
		<div class="grid">
			<label
				>Mindestgehalt (brutto/Jahr, €)
				<input
					type="number"
					min="0"
					step="1000"
					bind:value={() => profile.salary_min, (v) => (profile.salary_min = toOptionalNumber(v))}
				/>
			</label>
			<label
				>Berufserfahrung (Jahre)
				<input
					type="number"
					min="0"
					step="0.1"
					bind:value={
						() => profile.seniority_years, (v) => (profile.seniority_years = toOptionalNumber(v))
					}
				/>
			</label>
		</div>
		<h3>Sprachen</h3>
		{#each profile.languages as language, i (i)}
			<div class="row line">
				<input bind:value={language.language} placeholder="Sprache" aria-label="Sprache" />
				<select bind:value={language.level} aria-label="Niveau">
					{#each Object.entries(languageLevelLabels) as [value, text] (value)}
						<option {value}>{text}</option>
					{/each}
				</select>
				<button
					type="button"
					class="icon"
					aria-label="Sprache entfernen"
					onclick={() => profile.languages.splice(i, 1)}>×</button
				>
			</div>
		{/each}
		<button type="button" onclick={() => profile.languages.push({ language: '', level: 'B2' })}
			>+ Sprache</button
		>
	</section>

	<section class="card">
		<h2>Ausschlüsse & Firmen</h2>
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
		<h2>Anschreiben</h2>
		<div class="stack">
			<label
				>Ton
				<input bind:value={profile.tone} placeholder="z. B. freundlich, direkt, ohne Floskeln" />
			</label>
			<label
				>Feste Stichpunkte (kommen in jedes Anschreiben)
				<ChipInput bind:items={profile.cover_letter_bullets} label="Stichpunkte" />
			</label>
		</div>
	</section>

	<section class="card">
		<h2>Werdegang</h2>
		{#each profile.experience as station, i (i)}
			<div class="row line">
				<input bind:value={station.role} placeholder="Rolle" aria-label="Rolle" />
				<input bind:value={station.employer} placeholder="Arbeitgeber" aria-label="Arbeitgeber" />
				<select bind:value={station.kind} aria-label="Art">
					{#each Object.entries(stationKindLabels) as [value, text] (value)}
						<option {value}>{text}</option>
					{/each}
				</select>
				<input type="month" bind:value={station.start} aria-label="Von" />
				{#if station.current}
					<span class="muted">bis heute</span>
				{:else}
					<input type="month" bind:value={station.end} aria-label="Bis" />
				{/if}
				<label class="inline"
					><input type="checkbox" bind:checked={station.current} /> aktuell</label
				>
				<button
					type="button"
					class="icon"
					aria-label="Station entfernen"
					onclick={() => profile.experience.splice(i, 1)}>×</button
				>
			</div>
		{/each}
		<button
			type="button"
			onclick={() =>
				profile.experience.unshift({
					employer: '',
					role: '',
					kind: 'employment',
					start: null,
					end: null,
					current: false
				})}>+ Station</button
		>

		<h3>Ausbildung</h3>
		{#each profile.education as entry, i (i)}
			<div class="row line">
				<input bind:value={entry.degree} placeholder="Abschluss" aria-label="Abschluss" />
				<input bind:value={entry.institution} placeholder="Einrichtung" aria-label="Einrichtung" />
				<input type="month" bind:value={entry.start} aria-label="Von" />
				<input type="month" bind:value={entry.end} aria-label="Bis" />
				<button
					type="button"
					class="icon"
					aria-label="Eintrag entfernen"
					onclick={() => profile.education.splice(i, 1)}>×</button
				>
			</div>
		{/each}
		<button
			type="button"
			onclick={() =>
				profile.education.unshift({ institution: '', degree: '', start: null, end: null })}
			>+ Ausbildung</button
		>
	</section>

	<div class="savebar">
		<button type="submit" class="primary" disabled={saving || !dirty}>
			{saving ? 'Speichert …' : 'Speichern'}
		</button>
		{#if dirty}<span class="warn">Ungespeicherte Änderungen</span>{/if}
		{#if message}<span class={message.kind}>{message.text}</span>{/if}
	</div>
</form>

<style>
	h3 {
		font-size: 0.85rem;
		color: var(--muted);
		font-weight: 500;
		margin: 1rem 0 0.4rem;
	}
	.line {
		margin-bottom: 0.4rem;
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
	.savebar {
		position: sticky;
		bottom: 0;
		display: flex;
		gap: 1rem;
		align-items: center;
		padding: 0.75rem 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	input[type='month'] {
		width: 9.5rem;
	}
</style>
