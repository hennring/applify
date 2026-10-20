<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, uploadDocument, type Schemas } from '#lib/api/client.ts';
	import { formatBytes, formatDateTime } from '#lib/labels.ts';
	import type { PageProps } from './$types';

	type DocumentType = Schemas['DocumentOut']['type'];

	let { data }: PageProps = $props();

	const sections: { type: DocumentType; title: string; hint: string; accept: string }[] = [
		{
			type: 'cv',
			title: 'Lebenslauf',
			hint: 'Text-PDF. Wird nach dem Hochladen automatisch ausgelesen und füllt das Profil vor. Für das Bewerbungspaket wird der neueste verwendet.',
			accept: '.pdf,application/pdf'
		},
		{
			type: 'certificate',
			title: 'Zeugnisse',
			hint: 'PDFs, werden dem Bewerbungspaket beigelegt.',
			accept: '.pdf,application/pdf'
		},
		{
			type: 'sample_letter',
			title: 'Beispielanschreiben',
			hint: 'Optional, PDF oder TXT. Dient als Stilvorlage für generierte Anschreiben.',
			accept: '.pdf,.txt,application/pdf,text/plain'
		}
	];

	let busy = $state<DocumentType | null>(null);
	let error = $state<string | null>(null);

	const running = $derived(data.documents.some((d) => d.extraction_status === 'running'));

	$effect(() => {
		if (!running) return;
		const timer = setInterval(() => invalidateAll(), 3000);
		return () => clearInterval(timer);
	});

	async function upload(type: DocumentType, input: HTMLInputElement) {
		const files = [...(input.files ?? [])];
		if (!files.length) return;
		busy = type;
		error = null;
		for (const file of files) {
			const result = await uploadDocument(type, file);
			if (result.error) {
				error = `${file.name}: ${result.error}`;
				break;
			}
		}
		input.value = '';
		busy = null;
		await invalidateAll();
	}

	async function remove(doc: Schemas['DocumentOut']) {
		if (!confirm(`„${doc.filename}“ löschen?`)) return;
		const response = await api.DELETE('/api/documents/{document_id}', {
			params: { path: { document_id: doc.id } }
		});
		if (response.error) error = errorMessage(response.error);
		await invalidateAll();
	}

	async function extract(doc: Schemas['DocumentOut']) {
		const response = await api.POST('/api/documents/{document_id}/extract', {
			params: { path: { document_id: doc.id } }
		});
		if (response.error) error = errorMessage(response.error);
		await invalidateAll();
	}
</script>

<h1>Dokumente</h1>

{#if error}<p class="card error" role="alert">{error}</p>{/if}

{#each sections as section (section.type)}
	{@const docs = data.documents.filter((d) => d.type === section.type)}
	<section class="card">
		<div class="row head">
			<h2>{section.title}</h2>
			<label class="upload">
				<input
					type="file"
					accept={section.accept}
					multiple={section.type === 'certificate'}
					disabled={busy !== null}
					onchange={(e) => upload(section.type, e.currentTarget)}
				/>
				<span>{busy === section.type ? 'Lädt hoch …' : 'Hochladen'}</span>
			</label>
		</div>
		<p class="muted small">{section.hint}</p>

		{#if docs.length}
			<ul>
				{#each docs as doc, i (doc.id)}
					<li>
						<div class="row">
							<!-- API file download, not an app route -->
							<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -->
							<a href="/api/documents/{doc.id}/file" target="_blank" rel="noopener"
								>{doc.filename}</a
							>
							{#if section.type === 'cv' && i === 0 && docs.length > 1}
								<span class="badge">aktuell</span>
							{/if}
							<span class="muted small"
								>{formatBytes(doc.size_bytes)} · {formatDateTime(doc.uploaded_at)}</span
							>
							<button
								type="button"
								class="icon"
								aria-label="{doc.filename} löschen"
								onclick={() => remove(doc)}>×</button
							>
						</div>
						{#if !doc.has_text}
							<p class="warn small">
								Kein Text gefunden – vermutlich ein gescanntes PDF. Bitte ein Text-PDF hochladen.
							</p>
						{:else if section.type === 'cv'}
							<p class="small status">
								{#if doc.extraction_status === 'running'}
									<span class="spinner" aria-hidden="true"></span> Wird ausgelesen … (dauert bis zu einer
									Minute)
								{:else if doc.extraction_status === 'done'}
									<span class="ok">✓ Ausgelesen</span>
									{#if doc.extracted_at}<span class="muted">{formatDateTime(doc.extracted_at)}</span
										>{/if}
									– <a href={resolve('/profile')}>Vorschläge im Profil ansehen</a>
									<button type="button" onclick={() => extract(doc)}>Erneut auslesen</button>
								{:else if doc.extraction_status === 'failed'}
									<span class="error">Auslesen fehlgeschlagen: {doc.extraction_error}</span>
									<button type="button" onclick={() => extract(doc)}>Erneut versuchen</button>
								{:else}
									<button type="button" onclick={() => extract(doc)}>Auslesen</button>
								{/if}
							</p>
						{/if}
					</li>
				{/each}
			</ul>
		{:else}
			<p class="muted">Noch nichts hochgeladen.</p>
		{/if}
	</section>
{/each}

<style>
	.head {
		justify-content: space-between;
	}
	.head h2 {
		margin: 0;
	}
	.small {
		font-size: 0.85rem;
		margin: 0.25rem 0;
	}
	ul {
		list-style: none;
		padding: 0;
		margin: 0.5rem 0 0;
		display: grid;
		gap: 0.6rem;
	}
	li {
		border-top: 1px solid var(--border);
		padding-top: 0.6rem;
	}
	.status {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		flex-wrap: wrap;
	}
	.upload input {
		position: absolute;
		opacity: 0;
		width: 1px;
		height: 1px;
	}
	.upload span {
		display: inline-block;
		background: var(--accent);
		color: var(--accent-text);
		border-radius: 6px;
		padding: 0.35rem 0.8rem;
		cursor: pointer;
	}
	.upload:focus-within span {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.spinner {
		width: 0.8rem;
		height: 0.8rem;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
