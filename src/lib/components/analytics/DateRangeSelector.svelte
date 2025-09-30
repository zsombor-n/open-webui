<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { flyAndScale } from '$lib/utils/transitions';
	import { createEventDispatcher, getContext } from 'svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let value = 'this_week';
	export let placeholder = 'Select date range';

	const dateRanges = [
		{ value: 'this_week', label: 'This Week' },
		{ value: 'last_week', label: 'Last Week' },
		{ value: 'this_month', label: 'This Month' },
		{ value: 'last_month', label: 'Last Month' },
		{ value: 'this_quarter', label: 'This Quarter' },
		{ value: 'last_quarter', label: 'Last Quarter' },
		{ value: 'this_year', label: 'This Year' },
		{ value: 'last_year', label: 'Last Year' }
	];

	let show = false;

	$: selectedRange = dateRanges.find(r => r.value === value);

	const handleSelect = (selectedValue: string) => {
		value = selectedValue;
		show = false;
		dispatch('change', { value: selectedValue });
	};
</script>

<DropdownMenu.Root
	bind:open={show}
	onOpenChange={() => {
		// Optional: Add any side effects when dropdown opens/closes
	}}
	closeFocus={false}
>
	<DropdownMenu.Trigger
		class="relative font-primary outline-hidden focus:outline-hidden"
		aria-label={placeholder}
	>
		<div
			class="flex items-center px-3 py-1.5 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg transition-colors text-xs"
		>
			<!-- Calendar icon -->
			<svg class="w-3 h-3 mr-1.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
			</svg>

			<span class="truncate">
				{selectedRange?.label || placeholder}
			</span>

			<!-- Chevron down icon -->
			<ChevronDown className="ml-1.5 size-3 flex-shrink-0" strokeWidth="2.5" />
		</div>
	</DropdownMenu.Trigger>

	<DropdownMenu.Content
		class="z-40 w-auto min-w-[140px] max-w-[calc(100vw-1rem)] justify-start rounded-xl bg-white dark:bg-gray-850 dark:text-white shadow-lg border border-gray-200 dark:border-gray-700 outline-hidden"
		transition={flyAndScale}
		side="bottom-start"
		sideOffset={4}
	>
		<div class="p-1">
			{#each dateRanges as range}
				<DropdownMenu.Item
					class="flex items-center w-full px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors cursor-pointer {value === range.value ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : ''}"
					on:click={() => handleSelect(range.value)}
				>
					{range.label}
				</DropdownMenu.Item>
			{/each}
		</div>
	</DropdownMenu.Content>
</DropdownMenu.Root>