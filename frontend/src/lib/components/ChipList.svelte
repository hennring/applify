<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	let {
		items,
		key,
		text,
		editing = false,
		selectedKey = null,
		limit = 15,
		empty = 'Noch keine Einträge.',
		onremove,
		onselect,
		extra
	}: {
		items: T[];
		key: (item: T) => string;
		text: (item: T) => string;
		editing?: boolean;
		selectedKey?: string | null;
		/** Chips shown before "Mehr anzeigen". */
		limit?: number;
		empty?: string;
		onremove?: (item: T) => void;
		onselect?: (item: T) => void;
		/** Additional content inside a chip, e.g. a source marker. */
		extra?: Snippet<[T]>;
	} = $props();

	let expanded = $state(false);
	const visible = $derived(expanded || editing ? items : items.slice(0, limit));
</script>

{#if items.length}
	<ul class="chips">
		{#each visible as item (key(item))}
			<li class="chip" class:selected={key(item) === selectedKey}>
				{#if onselect}
					<button
						type="button"
						class="label"
						title={text(item)}
						aria-pressed={key(item) === selectedKey}
						onclick={() => onselect(item)}
					>
						<span class="text">{text(item)}</span>
						{@render extra?.(item)}
					</button>
				{:else}
					<span class="label" title={text(item)}>
						<span class="text">{text(item)}</span>
						{@render extra?.(item)}
					</span>
				{/if}
				{#if editing && onremove}
					<button
						type="button"
						class="remove"
						aria-label="{text(item)} entfernen"
						onclick={() => onremove(item)}><Icon name="x" size={14} /></button
					>
				{/if}
			</li>
		{/each}
	</ul>
	{#if items.length > limit && !editing}
		<button type="button" class="more" onclick={() => (expanded = !expanded)}>
			{expanded ? 'Weniger anzeigen' : `Mehr anzeigen (${items.length - limit})`}
			<Icon name={expanded ? 'chevron-up' : 'chevron-down'} size={16} />
		</button>
	{/if}
{:else}
	<p class="muted empty">{empty}</p>
{/if}

<style>
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		max-width: 100%;
		border: 1px solid var(--chip-border);
		border-radius: 999px;
		transition: border-color 0.15s;
	}
	.chip:hover,
	.chip.selected {
		border-color: var(--accent);
	}
	.chip.selected {
		background: var(--chip);
	}
	.label {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
		padding: 0.3rem 0.85rem;
		border: none;
		background: none;
		border-radius: 999px;
	}
	.text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 22rem;
	}
	.remove {
		display: inline-flex;
		border: none;
		background: none;
		padding: 0.3rem 0.6rem 0.3rem 0;
		margin-left: -0.4rem;
		color: var(--muted);
	}
	.remove:hover {
		color: var(--error);
	}
	.more {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin: 0.75rem auto 0;
		border: none;
		background: none;
		font-weight: 600;
	}
	.more:hover {
		color: var(--accent);
	}
	.empty {
		margin: 0;
	}
</style>
