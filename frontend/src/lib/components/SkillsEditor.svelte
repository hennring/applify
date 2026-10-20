<script lang="ts">
	import type { Schemas } from '#lib/api/client.ts';
	import { skillLevelLabels, weightLabels } from '#lib/labels.ts';

	type Skill = Schemas['Skill-Output'];
	let { skills = $bindable() }: { skills: Skill[] } = $props();

	let draft = $state('');
	let filter = $state<'all' | NonNullable<Skill['weight']>>('all');

	const counts = $derived({
		all: skills.length,
		must: skills.filter((s) => s.weight === 'must').length,
		nice: skills.filter((s) => s.weight === 'nice').length,
		avoid: skills.filter((s) => s.weight === 'avoid').length
	});

	function add() {
		const name = draft.trim();
		if (name && !skills.some((s) => s.name.toLowerCase() === name.toLowerCase())) {
			skills.push({
				name,
				weight: 'must',
				source: 'user',
				canonical: false,
				category: null,
				level: null
			});
		}
		draft = '';
	}

	function remove(skill: Skill) {
		skills.splice(skills.indexOf(skill), 1);
	}
</script>

<div class="row toolbar">
	<div class="row" role="radiogroup" aria-label="Filter">
		{#each ['all', 'must', 'nice', 'avoid'] as const as key (key)}
			<button
				type="button"
				class:active={filter === key}
				aria-pressed={filter === key}
				onclick={() => (filter = key)}
			>
				{key === 'all' ? 'Alle' : weightLabels[key]} ({counts[key]})
			</button>
		{/each}
	</div>
	<form
		class="row"
		onsubmit={(e) => {
			e.preventDefault();
			add();
		}}
	>
		<input bind:value={draft} placeholder="Skill hinzufügen" aria-label="Neuer Skill" />
		<button type="submit">+</button>
	</form>
</div>

<table>
	<thead>
		<tr><th>Skill</th><th>Gewichtung</th><th>Level</th><th></th></tr>
	</thead>
	<tbody>
		{#each skills.filter((s) => filter === 'all' || s.weight === filter) as skill (skill.name)}
			<tr>
				<td>
					{skill.name}
					{#if skill.source === 'cv'}<span class="badge" title="aus dem Lebenslauf">CV</span>{/if}
					{#if !skill.canonical}<span class="badge" title="nicht in der Skill-Liste">frei</span
						>{/if}
				</td>
				<td>
					<select bind:value={skill.weight} aria-label="Gewichtung {skill.name}">
						{#each Object.entries(weightLabels) as [value, text] (value)}
							<option {value}>{text}</option>
						{/each}
					</select>
				</td>
				<td>
					<select bind:value={skill.level} aria-label="Level {skill.name}">
						<option value={null}>–</option>
						{#each Object.entries(skillLevelLabels) as [value, text] (value)}
							<option {value}>{text}</option>
						{/each}
					</select>
				</td>
				<td>
					<button
						type="button"
						class="icon"
						aria-label="{skill.name} entfernen"
						onclick={() => remove(skill)}>×</button
					>
				</td>
			</tr>
		{:else}
			<tr><td colspan="4" class="muted">Keine Skills.</td></tr>
		{/each}
	</tbody>
</table>

<style>
	.toolbar {
		justify-content: space-between;
		margin-bottom: 0.5rem;
	}
	button.active {
		border-color: var(--accent);
		color: var(--accent);
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th {
		text-align: left;
		font-weight: 500;
		color: var(--muted);
		font-size: 0.85rem;
	}
	th,
	td {
		padding: 0.3rem 0.4rem;
		border-bottom: 1px solid var(--border);
	}
	td:last-child {
		width: 1%;
	}
</style>
