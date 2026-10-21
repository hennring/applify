<script lang="ts">
	import Icon, { type IconName } from './Icon.svelte';

	let {
		icon,
		title,
		editing = $bindable(false),
		addPlaceholder = 'Hinzufügen …',
		onadd
	}: {
		icon: IconName;
		title: string;
		editing?: boolean;
		addPlaceholder?: string;
		/** Enables the "+" button; called with the trimmed input. */
		onadd?: (value: string) => void;
	} = $props();

	let adding = $state(false);
	let draft = $state('');

	function submit() {
		const value = draft.trim();
		if (value) onadd?.(value);
		draft = '';
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ',') {
			// Enter must not submit the surrounding profile form.
			event.preventDefault();
			submit();
		} else if (event.key === 'Escape') {
			adding = false;
		}
	}
</script>

<div class="head">
	<h2><Icon name={icon} size={22} /> {title}</h2>
	{#if onadd}
		<button
			type="button"
			class="round"
			class:on={adding}
			aria-label="{title}: hinzufügen"
			title="Hinzufügen"
			onclick={() => (adding = !adding)}><Icon name={adding ? 'x' : 'plus'} /></button
		>
	{/if}
	<button
		type="button"
		class="round"
		class:on={editing}
		aria-label="{title}: {editing ? 'Bearbeiten beenden' : 'bearbeiten'}"
		title={editing ? 'Fertig' : 'Bearbeiten'}
		aria-pressed={editing}
		onclick={() => (editing = !editing)}><Icon name={editing ? 'check' : 'pencil'} /></button
	>
</div>

{#if adding}
	<div class="add">
		<!-- svelte-ignore a11y_autofocus -->
		<input
			bind:value={draft}
			{onkeydown}
			placeholder={addPlaceholder}
			aria-label="{title}: neuer Eintrag"
			autofocus
		/>
		<button type="button" class="primary" onclick={submit} disabled={!draft.trim()}>
			<Icon name="plus" size={16} /> Hinzufügen
		</button>
	</div>
{/if}

<style>
	.head {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin-bottom: 1rem;
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		margin: 0 0.4rem 0 0;
		font-size: 1.35rem;
	}
	.add {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}
	.add input {
		flex: 1;
		max-width: 28rem;
	}
	.add button {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
</style>
