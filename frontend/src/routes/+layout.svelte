<script lang="ts">
	import '../app.css';
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
		{ href: '/market', label: 'Markt' },
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
	.shell {
		display: grid;
		grid-template-columns: 13rem 1fr;
		min-height: 100vh;
	}
	nav {
		position: sticky;
		top: 0;
		align-self: start;
		height: 100vh;
		box-sizing: border-box;
		overflow-y: auto;
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
	/* Centered in the space beside the nav. */
	main {
		justify-self: center;
		width: 100%;
		box-sizing: border-box;
		padding: 1.5rem 2rem;
		max-width: 110rem;
		min-width: 0;
	}
	@media (max-width: 700px) {
		.shell {
			grid-template-columns: 1fr;
		}
		nav {
			position: static;
			height: auto;
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
