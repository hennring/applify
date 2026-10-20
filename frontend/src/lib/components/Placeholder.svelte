<script lang="ts">
	import type { Snippet } from 'svelte';

	let { title, milestone, children }: { title: string; milestone: string; children: Snippet } =
		$props();
</script>

<h1>{title}</h1>
<p>{@render children()}</p>
<p class="muted">Kommt in {milestone}.</p>
