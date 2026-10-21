<script lang="ts">
	import type { Schemas } from '#lib/api/client.ts';
	import { changeFieldLabels, changeLabel, changeValue, formatDateTime } from '#lib/labels.ts';
	import Icon from './Icon.svelte';

	let {
		changes,
		disabledReason,
		onapply
	}: {
		changes: Schemas['CvChanges'];
		disabledReason: string | null;
		onapply: (ids: string[]) => Promise<void>;
	} = $props();

	let selected = $state<string[]>([]);
	let busy = $state(false);

	// Group by field, keeping the backend's order.
	const groups = $derived(
		Object.entries(Object.groupBy(changes.changes, (c) => c.field)) as [
			Schemas['ChangeItem']['field'],
			Schemas['ChangeItem'][]
		][]
	);

	async function apply(ids: string[]) {
		busy = true;
		try {
			await onapply(ids);
			selected = [];
		} finally {
			busy = false;
		}
	}
</script>

<section class="card suggestions">
	<h2><Icon name="file-text" /> Abweichungen zum Lebenslauf</h2>
	<p class="muted">
		{changes.filename}{changes.extracted_at
			? `, ausgelesen ${formatDateTime(changes.extracted_at)}`
			: ''}. Neue Angaben wurden direkt eingetragen; diese hier weichen von deinem Profil ab und
		werden nur mit deiner Auswahl übernommen.
	</p>

	{#each groups as [field, items] (field)}
		<h3>{changeFieldLabels[field]}</h3>
		<ul>
			{#each items as change (change.id)}
				<li>
					<label class="option">
						<input type="checkbox" value={change.id} bind:group={selected} />
						<span>
							{#if change.field === 'contact' || change.field === 'languages' || change.field === 'seniority_years'}
								<strong>{changeLabel(change)}:</strong>
							{/if}
							{#if change.current}
								<del class="muted">{changeValue(change, change.current)}</del> →
							{/if}
							{changeValue(change, change.suggested)}
						</span>
					</label>
				</li>
			{/each}
		</ul>
	{/each}

	{#if changes.dropped_skills.length}
		<p class="muted small">
			Verworfen, weil im Lebenslauf nicht gefunden: {changes.dropped_skills.join(', ')}
		</p>
	{/if}

	<div class="row">
		<button
			type="button"
			class="primary"
			disabled={busy || !selected.length || !!disabledReason}
			onclick={() => apply(selected)}
		>
			{selected.length} übernehmen
		</button>
		<button
			type="button"
			disabled={busy || !!disabledReason}
			onclick={() => apply(changes.changes.map((c) => c.id))}
		>
			Alle übernehmen
		</button>
		<button
			type="button"
			disabled={busy}
			onclick={() => (selected = selected.length ? [] : changes.changes.map((c) => c.id))}
		>
			{selected.length ? 'Auswahl aufheben' : 'Alle auswählen'}
		</button>
		{#if disabledReason}<span class="warn">{disabledReason}</span>{/if}
	</div>
</section>

<style>
	.suggestions {
		border-color: var(--accent);
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	h3 {
		font-size: 0.85rem;
		margin: 0.75rem 0 0.25rem;
		color: var(--muted);
		font-weight: 500;
	}
	ul {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.15rem;
	}
	.option {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
		color: var(--text);
		font-size: 0.95rem;
	}
	.small {
		font-size: 0.85rem;
	}
	.row {
		margin-top: 1rem;
	}
</style>
