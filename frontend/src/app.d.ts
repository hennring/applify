// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		interface PageState {
			/** Job open in the detail panel of the daily list (shallow routing). */
			jobId?: number | null;
		}
		// interface Platform {}
	}
}

export {};
