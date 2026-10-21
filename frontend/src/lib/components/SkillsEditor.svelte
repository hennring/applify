<script lang="ts">
	import type { Schemas } from '#lib/api/client.ts';
	import { skillLevelLabels, weightLabels } from '#lib/labels.ts';
	import ChipList from './ChipList.svelte';
	import Icon from './Icon.svelte';
	import SectionHead from './SectionHead.svelte';

	type Skill = Schemas['Skill-Output'];
	type Weight = NonNullable<Skill['weight']>;
	let { skills = $bindable() }: { skills: Skill[] } = $props();

	const groups: { weight: Weight; title: string }[] = [
		{ weight: 'must', title: 'Pflicht' },
		{ weight: 'nice', title: 'Gern' },
		{ weight: 'avoid', title: 'Will ich nicht' }
	];

	let editing = $state(false);
	let selectedKey = $state<string | null>(null);
	const skillKey = (s: Skill) => s.name.toLowerCase();
	const selected = $derived(skills.find((s) => skillKey(s) === selectedKey) ?? null);

	function add(name: string) {
		if (!skills.some((s) => skillKey(s) === name.toLowerCase())) {
			skills.push({
				name,
				weight: 'must',
				source: 'user',
				canonical: false,
				category: null,
				level: null
			});
		}
	}

	function remove(skill: Skill) {
		skills.splice(skills.indexOf(skill), 1);
	}
</script>

<SectionHead
	icon="wrench"
	title="Skills"
	bind:editing
	onadd={add}
	addPlaceholder="z. B. TypeScript"
/>

{#each groups as group (group.weight)}
	{@const items = skills.filter((s) => (s.weight ?? 'nice') === group.weight)}
	<h3>{group.title} <span class="count">{items.length}</span></h3>
	<ChipList
		{items}
		key={skillKey}
		text={(s) => s.name}
		{editing}
		{selectedKey}
		empty="Keine."
		onremove={remove}
		onselect={(s) => (selectedKey = selectedKey === skillKey(s) ? null : skillKey(s))}
	>
		{#snippet extra(skill)}
			{#if skill.level}<span class="level">{skillLevelLabels[skill.level]}</span>{/if}
			{#if skill.source === 'cv'}<span class="src" title="aus dem Lebenslauf"
					><Icon name="file-text" size={14} /></span
				>{/if}
		{/snippet}
	</ChipList>
{/each}

{#if selected}
	<div class="detail">
		<strong class="name">{selected.name}</strong>
		{#if selected.source === 'cv'}
			<span class="badge"><Icon name="file-text" size={12} /> aus Lebenslauf</span>
		{/if}
		{#if !selected.canonical}<span class="badge" title="nicht in der Skill-Liste">frei</span>{/if}

		<div class="segmented" role="radiogroup" aria-label="Gewichtung">
			{#each Object.entries(weightLabels) as [value, label] (value)}
				<button
					type="button"
					role="radio"
					aria-checked={selected.weight === value}
					class:on={selected.weight === value}
					onclick={() => (selected.weight = value as Weight)}>{label}</button
				>
			{/each}
		</div>

		<div class="segmented" role="radiogroup" aria-label="Level">
			{#each [[null, '–'], ...Object.entries(skillLevelLabels)] as [value, label] (value)}
				<button
					type="button"
					role="radio"
					aria-checked={selected.level === value}
					class:on={selected.level === value}
					onclick={() => (selected.level = value as Skill['level'])}>{label}</button
				>
			{/each}
		</div>

		<button
			type="button"
			class="icon danger"
			aria-label="{selected.name} entfernen"
			title="Entfernen"
			onclick={() => remove(selected)}><Icon name="trash" size={16} /></button
		>
		<button
			type="button"
			class="icon"
			aria-label="Auswahl schließen"
			onclick={() => (selectedKey = null)}><Icon name="x" size={16} /></button
		>
	</div>
{:else if skills.length}
	<p class="muted hint">Skill anklicken, um Gewichtung und Level zu ändern.</p>
{/if}

<style>
	h3 {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 1rem;
		margin: 1.1rem 0 0.6rem;
	}
	h3:first-of-type {
		margin-top: 0;
	}
	.count {
		font-size: 0.8rem;
		font-weight: 500;
		color: var(--muted);
	}
	.level {
		font-size: 0.75rem;
		color: var(--muted);
	}
	.src {
		display: inline-flex;
		color: var(--accent);
	}
	.detail {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		margin-top: 1.25rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--accent);
		border-radius: 8px;
		background: var(--bg);
	}
	.name {
		margin-right: 0.25rem;
	}
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
	}
	.segmented {
		display: inline-flex;
		border: 1px solid var(--border);
		border-radius: 999px;
		overflow: hidden;
	}
	.segmented button {
		border: none;
		border-radius: 0;
		padding: 0.25rem 0.75rem;
		background: none;
	}
	.segmented button + button {
		border-left: 1px solid var(--border);
	}
	.segmented button.on {
		background: var(--accent);
		color: var(--accent-text);
	}
	.danger:hover {
		color: var(--error);
	}
	.detail .icon:first-of-type {
		margin-left: auto;
	}
	.hint {
		margin: 1rem 0 0;
		font-size: 0.85rem;
	}
</style>
