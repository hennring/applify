<script lang="ts">
	import { healthRows } from '#lib/health.ts';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<h1>Tagesliste</h1>
<p class="muted">Gerankte Stellen, Suchlauf und Fortschritt kommen in M2/M3.</p>

<section class="card">
	<h2>Systemstatus</h2>
	{#if data.health}
		<ul class="status">
			{#each healthRows(data.health) as row (row.label)}
				<li>
					<span class={row.ok ? 'ok' : 'error'}>{row.ok ? '●' : '○'}</span>
					{row.label}
					{#if row.detail}<span class="muted">– {row.detail}</span>{/if}
				</li>
			{/each}
		</ul>
	{:else}
		<p class="error">Backend nicht erreichbar.</p>
	{/if}
</section>

<style>
	.status {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.4rem;
	}
</style>
