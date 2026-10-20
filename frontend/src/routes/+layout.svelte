<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import favicon from '#lib/assets/favicon.svg';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const nav = [
		{ href: '/', label: 'Tagesliste' },
		{ href: '/applications', label: 'Bewerbungen' },
		{ href: '/companies', label: 'Firmen' },
		{ href: '/coverage', label: 'Abdeckung' },
		{ href: '/profile', label: 'Profil' },
		{ href: '/documents', label: 'Dokumente' },
		{ href: '/settings', label: 'Einstellungen' }
	] as const;

	function isActive(href: string): boolean {
		const path = page.url.pathname;
		return href === '/' ? path === '/' || path.startsWith('/jobs') : path.startsWith(href);
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Applify</title>
</svelte:head>

<div class="shell">
	<nav>
		<a class="brand" href={resolve('/')}>Applify</a>
		{#each nav as item (item.href)}
			<a href={resolve(item.href)} aria-current={isActive(item.href) ? 'page' : undefined}
				>{item.label}</a
			>
		{/each}
	</nav>
	<main>
		{@render children()}
	</main>
</div>

<style>
	:global(:root) {
		--bg: #f7f7f5;
		--surface: #ffffff;
		--text: #1d1d1b;
		--muted: #6b6b66;
		--border: #e2e2dd;
		--accent: #2f5bd3;
		--ok: #1f8a4c;
		--error: #c0392b;
		color-scheme: light dark;
		font-family: system-ui, sans-serif;
	}
	@media (prefers-color-scheme: dark) {
		:global(:root) {
			--bg: #171716;
			--surface: #21211f;
			--text: #ececea;
			--muted: #9a9a94;
			--border: #34342f;
			--accent: #7d9dff;
			--ok: #4cc27f;
			--error: #ef6b5c;
		}
	}
	:global(body) {
		margin: 0;
		background: var(--bg);
		color: var(--text);
	}
	:global(.muted) {
		color: var(--muted);
	}
	:global(.ok) {
		color: var(--ok);
	}
	:global(.error) {
		color: var(--error);
	}
	:global(.card) {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 1rem 1.25rem;
	}
	:global(.card h2) {
		margin-top: 0;
		font-size: 1rem;
	}

	.shell {
		display: grid;
		grid-template-columns: 13rem 1fr;
		min-height: 100vh;
	}
	nav {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 1.25rem 0.75rem;
		border-right: 1px solid var(--border);
		background: var(--surface);
	}
	nav a {
		color: var(--text);
		text-decoration: none;
		padding: 0.45rem 0.75rem;
		border-radius: 6px;
	}
	nav a[aria-current='page'] {
		background: var(--bg);
		color: var(--accent);
		font-weight: 600;
	}
	.brand {
		font-weight: 700;
		font-size: 1.15rem;
		margin-bottom: 1rem;
	}
	main {
		padding: 1.5rem 2rem;
		max-width: 70rem;
	}
	@media (max-width: 700px) {
		.shell {
			grid-template-columns: 1fr;
		}
		nav {
			flex-direction: row;
			flex-wrap: wrap;
			border-right: none;
			border-bottom: 1px solid var(--border);
		}
		.brand {
			margin-bottom: 0;
		}
		main {
			padding: 1rem;
		}
	}
</style>
