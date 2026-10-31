<script lang="ts">
	import { api, type Schemas } from '#lib/api/client.ts';
	import Icon from '#lib/components/Icon.svelte';

	let {
		value,
		excluded,
		onchange
	}: { value: string | null; excluded: boolean; onchange: (city: string | null) => void } =
		$props();

	const TYPING_DELAY_MS = 150;

	// What is typed; follows the filter whenever that changes.
	let draft = $derived(value ?? '');
	let options = $state<Schemas['CityOption'][]>([]);
	let open = $state(false);
	let active = $state(-1);
	let timer: ReturnType<typeof setTimeout> | undefined;
	// Only the answer to the latest request counts; a slower, older one is dropped.
	let latest = 0;

	async function suggest() {
		clearTimeout(timer);
		const request = ++latest;
		const { data } = await api.GET('/api/matches/cities', {
			params: { query: { q: draft.trim(), excluded } }
		});
		if (request !== latest) return;
		options = data ?? [];
		active = -1;
		open = true;
	}

	function close() {
		clearTimeout(timer);
		latest += 1;
		open = false;
		active = -1;
	}

	function choose(city: string | null) {
		close();
		draft = city ?? '';
		if (city !== value) onchange(city);
	}

	function oninput() {
		active = -1;
		clearTimeout(timer);
		timer = setTimeout(suggest, TYPING_DELAY_MS);
	}

	function onfocus(event: FocusEvent) {
		(event.currentTarget as HTMLInputElement).select();
		suggest();
	}

	// Leaving the field never filters by half a name.
	function onblur() {
		if (!draft.trim()) choose(null);
		else {
			close();
			draft = value ?? '';
		}
	}

	async function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			close();
		} else if (event.key === 'Enter') {
			event.preventDefault();
			if (!draft.trim()) return choose(null);
			// Enter right after typing must not pick from the list of the previous letter.
			if (active < 0) await suggest();
			const option = options[Math.max(active, 0)];
			if (option) choose(option.name);
		} else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && options.length) {
			event.preventDefault();
			const step = event.key === 'ArrowDown' ? 1 : -1;
			open = true;
			active = (active + step + options.length + (active < 0 && step < 0 ? 1 : 0)) % options.length;
		}
	}
</script>

<div class="city">
	<Icon name="map-pin" size={15} />
	<input
		type="text"
		role="combobox"
		placeholder="Stadt"
		aria-label="Stadt"
		aria-autocomplete="list"
		aria-expanded={open}
		aria-controls="city-options"
		aria-activedescendant={active >= 0 ? `city-option-${active}` : undefined}
		autocomplete="off"
		bind:value={draft}
		{oninput}
		{onfocus}
		{onblur}
		{onkeydown}
	/>
	{#if value}
		<button
			type="button"
			class="clear"
			aria-label="Stadtfilter löschen"
			onclick={() => choose(null)}><Icon name="x" size={14} /></button
		>
	{/if}
	<div id="city-options" class="options" role="listbox" aria-label="Städte" hidden={!open}>
		{#each options as option, i (option.name)}
			<!-- Keeps the focus in the input, so the blur does not come before the click. -->
			<button
				type="button"
				id="city-option-{i}"
				role="option"
				tabindex="-1"
				aria-selected={i === active}
				class:active={i === active}
				onmousedown={(e) => e.preventDefault()}
				onclick={() => choose(option.name)}
			>
				{option.name} <span class="muted">{option.jobs}</span>
			</button>
		{:else}
			<p class="muted">Keine Stadt mit Stellen gefunden</p>
		{/each}
	</div>
</div>

<style>
	.city {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		color: var(--muted);
	}
	input {
		width: 11rem;
		color: var(--text);
	}
	.clear {
		position: absolute;
		right: 0.3rem;
		display: inline-flex;
		border: none;
		background: none;
		padding: 0.15rem;
		cursor: pointer;
	}
	.options {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		z-index: 10;
		margin-top: 0.2rem;
		max-height: 18rem;
		overflow-y: auto;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--bg);
	}
	.options[hidden] {
		display: none;
	}
	.options button {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		width: 100%;
		border: none;
		border-radius: 0;
		background: none;
		color: var(--text);
		padding: 0.35rem 0.6rem;
		text-align: left;
		cursor: pointer;
	}
	.options button:hover,
	.options button.active {
		background: var(--chip);
	}
	.options p {
		margin: 0;
		padding: 0.35rem 0.6rem;
		font-size: 0.9rem;
	}
</style>
