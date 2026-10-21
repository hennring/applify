<script lang="ts">
	import { resolve } from '$app/paths';
	import Icon from '#lib/components/Icon.svelte';
	import JobDetail from '#lib/components/JobDetail.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<a class="back" href={resolve('/')}><Icon name="chevron-up" size={16} class="left" /> Tagesliste</a>
<JobDetail jobId={data.jobId} />

<style>
	.back {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		margin-bottom: 0.75rem;
		color: var(--muted);
		text-decoration: none;
		font-size: 0.9rem;
	}
	.back:hover {
		color: var(--accent);
	}
	.back :global(.left) {
		transform: rotate(-90deg);
	}
</style>
