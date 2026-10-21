<script lang="ts">
	let { score, size = 'md' }: { score: number; size?: 'md' | 'lg' } = $props();

	const tone = $derived(score >= 75 ? 'high' : score >= 50 ? 'mid' : 'low');
</script>

<span class="score {tone} {size}" title="Score {score} von 100">{score}</span>

<style>
	.score {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 50%;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		border: 2px solid currentColor;
	}
	.lg {
		width: 4rem;
		height: 4rem;
		font-size: 1.5rem;
	}
	.high {
		color: var(--ok);
	}
	.mid {
		color: var(--accent);
	}
	.low {
		color: var(--muted);
	}
</style>
