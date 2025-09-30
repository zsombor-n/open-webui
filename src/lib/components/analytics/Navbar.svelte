<script lang="ts">
	import { getContext, createEventDispatcher } from 'svelte';
	import { user, showArchivedChats } from '$lib/stores';
	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import DateRangeSelector from './DateRangeSelector.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let triggerProcessing: () => Promise<void>;
	export let exportData: (type: string) => Promise<void>;
	export let isProcessing: boolean = false;
	export let selectedDateRange = 'this_week';

	const handleDateRangeChange = (event: CustomEvent) => {
		selectedDateRange = event.detail.value;
		// Forward the event to the parent component
		dispatch('dateRangeChange', { value: selectedDateRange });
	};
</script>

<nav class="sticky top-0 z-30 w-full py-2 flex flex-col items-center drag-region bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm shadow-lg">
	<div class="flex items-center w-full pl-1.5 pr-1">
		<div
			class=" bg-linear-to-b via-50% from-white via-white to-transparent dark:from-gray-900 dark:via-gray-900 dark:to-transparent pointer-events-none absolute inset-0 -bottom-7 z-[-1]"
		></div>

		<div class=" flex max-w-full w-full mx-auto px-1.5 md:px-2 bg-transparent">
			<div class="flex items-center w-full max-w-full">
				<!-- Left side: Analytics branding and subtitle -->
				<div class="flex-1 flex items-center min-w-0">
					<div class="flex items-center min-w-0">
						<ChartBar className="w-6 h-6 mr-3 text-blue-600 flex-shrink-0" />
						<div class="min-w-0">
							<h1 class="text-lg font-semibold text-gray-900 dark:text-white">AI Analytics</h1>
							<p class="text-xs text-gray-600 dark:text-gray-300 truncate">
								Daily analysis of AI-assisted chat efficiency
							</p>
						</div>
					</div>
				</div>

				<!-- Center: Action buttons -->
				<div class="flex flex-wrap gap-1 mx-4">
					<button
						on:click={triggerProcessing}
						disabled={isProcessing}
						class="flex items-center px-2 py-1.5 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-500 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-xs"
					>
						{#if isProcessing}
							<svg class="animate-spin w-3 h-3 mr-1" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
							</svg>
							Processing...
						{:else}
							🔄 Run Analytics
						{/if}
					</button>
					<button
						on:click={() => exportData('summary')}
						class="flex items-center px-2 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors text-xs"
					>
						<ArrowDownTray className="w-3 h-3 mr-1" />
						Summary
					</button>
					<button
						on:click={() => exportData('daily')}
						class="flex items-center px-2 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors text-xs"
					>
						<ArrowDownTray className="w-3 h-3 mr-1" />
						Daily
					</button>
					<button
						on:click={() => exportData('detailed')}
						class="flex items-center px-2 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors text-xs"
					>
						<ArrowDownTray className="w-3 h-3 mr-1" />
						Detailed
					</button>
				</div>

				<!-- Date Range Selector -->
				<div class="flex items-center mx-2">
					<DateRangeSelector
						bind:value={selectedDateRange}
						on:change={handleDateRangeChange}
					/>
				</div>

				<!-- Right side: User profile -->
				<div class="self-center flex flex-none items-center text-gray-600 dark:text-gray-400">
					{#if $user !== undefined && $user !== null}
						<UserMenu
							className="max-w-[240px]"
							role={$user?.role}
							help={true}
							on:show={(e) => {
								if (e.detail === 'archived-chat') {
									showArchivedChats.set(true);
								}
							}}
						>
							<div
								class="select-none flex rounded-xl p-1.5 w-full hover:bg-gray-50 dark:hover:bg-gray-850 transition"
							>
								<div class=" self-center">
									<span class="sr-only">{$i18n.t('User menu')}</span>
									<img
										src={$user?.profile_image_url}
										class="size-6 object-cover rounded-full"
										alt=""
										draggable="false"
									/>
								</div>
							</div>
						</UserMenu>
					{/if}
				</div>
			</div>
		</div>
	</div>
</nav>