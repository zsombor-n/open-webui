<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	onMount(() => {
		// Get the current URL search parameters
		const params = new URLSearchParams(window.location.search);

		const videoId = params.get('v');
		if (videoId !== null) {
			// Redirect to root with 'youtube' parameter

			goto(`/?youtube=${encodeURIComponent(videoId)}`);
		} else {
			// Redirect to root if 'v' parameter doesn't exist
			goto('/');
		}
	});
</script>
