<script lang="ts">
	let {
		items = $bindable(),
		placeholder = 'Hinzufügen …',
		label
	}: { items: string[]; placeholder?: string; label: string } = $props();

	let draft = $state('');

	function add() {
		const value = draft.trim();
		if (value && !items.some((i) => i.toLowerCase() === value.toLowerCase())) {
			items.push(value);
		}
		draft = '';
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ',') {
			event.preventDefault();
			add();
		} else if (event.key === 'Backspace' && !draft && items.length) {
			items.pop();
		}
	}
</script>

<div class="chips" role="group" aria-label={label}>
	{#each items as item, i (item)}
		<span class="chip">
			{item}
			<button
				type="button"
				class="icon"
				aria-label="{item} entfernen"
				onclick={() => items.splice(i, 1)}>×</button
			>
		</span>
	{/each}
	<input bind:value={draft} {onkeydown} onblur={add} {placeholder} aria-label={label} />
</div>

<style>
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 0.3rem;
		background: var(--bg);
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.1rem;
		background: var(--chip);
		border-radius: 999px;
		padding: 0.1rem 0.15rem 0.1rem 0.6rem;
	}
	.chip button {
		border: none;
		background: none;
		padding: 0 0.35rem;
	}
	input {
		flex: 1;
		min-width: 10rem;
		border: none;
		background: transparent;
		padding: 0.2rem 0.3rem;
	}
	input:focus {
		outline: none;
	}
</style>
