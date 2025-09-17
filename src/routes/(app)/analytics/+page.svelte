<script lang="ts">
	import { onMount } from 'svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import LockClosed from '$lib/components/icons/LockClosed.svelte';
	import { toast } from 'svelte-sonner';

	// Dummy data for the dashboard
	let analyticsData = {
		totalConversations: 1247,
		totalTimeSaved: 2856, // minutes
		avgTimeSavedPerConversation: 12.8, // minutes
		confidenceLevel: 85, // percentage
		dailyTrend: [
			{ date: '2025-01-10', conversations: 45, timeSaved: 87 },
			{ date: '2025-01-11', conversations: 52, timeSaved: 94 },
			{ date: '2025-01-12', conversations: 38, timeSaved: 76 },
			{ date: '2025-01-13', conversations: 61, timeSaved: 118 },
			{ date: '2025-01-14', conversations: 49, timeSaved: 89 },
			{ date: '2025-01-15', conversations: 55, timeSaved: 102 },
			{ date: '2025-01-16', conversations: 43, timeSaved: 81 }
		],
		userBreakdown: [
			{ userId: 'user_001', conversations: 156, timeSaved: 312 },
			{ userId: 'user_002', conversations: 142, timeSaved: 287 },
			{ userId: 'user_003', conversations: 98, timeSaved: 189 },
			{ userId: 'user_004', conversations: 134, timeSaved: 268 },
			{ userId: 'user_005', conversations: 89, timeSaved: 178 }
		]
	};

	let isAuthenticated = false;
	let password = '';
	let showPasswordModal = true;

	const authenticate = () => {
		// For demo purposes, any password works
		if (password.length > 0) {
			isAuthenticated = true;
			showPasswordModal = false;
			toast.success('Access granted');
		} else {
			toast.error('Password required');
		}
	};

	const exportCSV = () => {
		const csvData = [
			['Date', 'Conversations', 'Time Saved (min)'],
			...analyticsData.dailyTrend.map(day => [
				day.date,
				day.conversations.toString(),
				day.timeSaved.toString()
			])
		];

		const csvContent = csvData.map(row => row.join(',')).join('\n');
		const blob = new Blob([csvContent], { type: 'text/csv' });
		const url = window.URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = `analytics-export-${new Date().toISOString().split('T')[0]}.csv`;
		link.click();
		window.URL.revokeObjectURL(url);

		toast.success('CSV exported successfully');
	};

	const formatMinutes = (minutes: number): string => {
		const hours = Math.floor(minutes / 60);
		const mins = minutes % 60;
		return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
	};

	onMount(() => {
		// Check if user is already authenticated (could be from localStorage)
		const authStatus = localStorage.getItem('analytics_auth');
		if (authStatus === 'true') {
			isAuthenticated = true;
			showPasswordModal = false;
		}
	});
</script>

<svelte:head>
	<title>Analytics Dashboard - AI Time Savings</title>
</svelte:head>

<!-- Password Protection Modal -->
{#if showPasswordModal}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
		<div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-96 max-w-md mx-4">
			<div class="flex items-center mb-4">
				<LockClosed className="w-6 h-6 mr-2 text-blue-600" />
				<h2 class="text-xl font-semibold text-gray-900 dark:text-white">Protected Analytics</h2>
			</div>
			<p class="text-gray-600 dark:text-gray-300 mb-4">
				This dashboard contains sensitive analytics data. Please enter the access password.
			</p>
			<form on:submit|preventDefault={authenticate}>
				<input
					bind:value={password}
					type="password"
					placeholder="Enter password"
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md mb-4 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
					autofocus
				/>
				<button
					type="submit"
					class="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors"
				>
					Access Dashboard
				</button>
			</form>
		</div>
	</div>
{/if}

{#if isAuthenticated}
	<div class="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900">
		<div class="container mx-auto px-4 py-6 max-w-7xl">
			<!-- Header -->
			<div class="mb-8">
				<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
					<div class="flex items-center">
						<ChartBar className="w-8 h-8 mr-3 text-blue-600 flex-shrink-0" />
						<div>
							<h1 class="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white">AI Time Savings Analytics</h1>
							<p class="text-sm sm:text-base text-gray-600 dark:text-gray-300 mt-1">
								Daily analysis of AI-assisted conversation efficiency
							</p>
						</div>
					</div>
					<button
						on:click={exportCSV}
						class="flex items-center justify-center px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors whitespace-nowrap"
					>
						<ArrowDownTray className="w-4 h-4 mr-2" />
						Export CSV
					</button>
				</div>
			</div>

			<!-- Key Metrics Cards -->
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-8">
				<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
					<div class="flex items-center">
						<div class="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
							<ChartBar className="w-6 h-6 text-blue-600" />
						</div>
						<div class="ml-4">
							<p class="text-sm font-medium text-gray-600 dark:text-gray-300">Total Conversations</p>
							<p class="text-2xl font-semibold text-gray-900 dark:text-white">{analyticsData.totalConversations.toLocaleString()}</p>
						</div>
					</div>
				</div>

				<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
					<div class="flex items-center">
						<div class="p-2 bg-green-100 dark:bg-green-900 rounded-lg">
							<svg class="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
						</div>
						<div class="ml-4">
							<p class="text-sm font-medium text-gray-600 dark:text-gray-300">Total Time Saved</p>
							<p class="text-2xl font-semibold text-gray-900 dark:text-white">{formatMinutes(analyticsData.totalTimeSaved)}</p>
						</div>
					</div>
				</div>

				<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
					<div class="flex items-center">
						<div class="p-2 bg-purple-100 dark:bg-purple-900 rounded-lg">
							<svg class="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
							</svg>
						</div>
						<div class="ml-4">
							<p class="text-sm font-medium text-gray-600 dark:text-gray-300">Avg. per Conversation</p>
							<p class="text-2xl font-semibold text-gray-900 dark:text-white">{formatMinutes(analyticsData.avgTimeSavedPerConversation)}</p>
						</div>
					</div>
				</div>

				<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
					<div class="flex items-center">
						<div class="p-2 bg-orange-100 dark:bg-orange-900 rounded-lg">
							<svg class="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
						</div>
						<div class="ml-4">
							<p class="text-sm font-medium text-gray-600 dark:text-gray-300">Confidence Level</p>
							<p class="text-2xl font-semibold text-gray-900 dark:text-white">{analyticsData.confidenceLevel}%</p>
						</div>
					</div>
				</div>
			</div>

			<!-- Charts Section -->
			<div class="grid grid-cols-1 xl:grid-cols-2 gap-6 lg:gap-8 mb-8">
				<!-- Daily Trend Chart -->
				<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
					<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Daily Time Savings Trend</h3>
					<div class="h-48 sm:h-64 flex items-end justify-between space-x-1 sm:space-x-2 overflow-x-auto">
						{#each analyticsData.dailyTrend as day, index}
							<div class="flex flex-col items-center flex-shrink-0">
								<div
									class="bg-blue-500 rounded-t transition-all duration-300 hover:bg-blue-600"
									style="height: {(day.timeSaved / Math.max(...analyticsData.dailyTrend.map(d => d.timeSaved))) * 160}px; width: 24px; min-width: 24px;"
									title="{day.date}: {day.timeSaved} minutes saved"
								></div>
								<div class="text-xs text-gray-600 dark:text-gray-300 mt-2 transform -rotate-45 origin-center">
									{day.date.split('-')[2]}
								</div>
							</div>
						{/each}
					</div>
					<div class="mt-4 text-sm text-gray-600 dark:text-gray-300">
						Last 7 days • Total: {analyticsData.dailyTrend.reduce((sum, day) => sum + day.timeSaved, 0)} minutes saved
					</div>
				</div>

				<!-- User Breakdown -->
				<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
					<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Top Users by Time Saved</h3>
					<div class="space-y-4">
						{#each analyticsData.userBreakdown as user, index}
							<div class="flex items-center justify-between">
								<div class="flex items-center min-w-0 flex-1">
									<div class="w-8 h-8 bg-gray-300 dark:bg-gray-600 rounded-full flex items-center justify-center text-sm font-medium text-gray-700 dark:text-gray-300 flex-shrink-0">
										#{index + 1}
									</div>
									<div class="ml-3 min-w-0 flex-1">
										<p class="text-sm font-medium text-gray-900 dark:text-white truncate">{user.userId}</p>
										<p class="text-xs text-gray-600 dark:text-gray-300">{user.conversations} conversations</p>
									</div>
								</div>
								<div class="text-right ml-4 flex-shrink-0">
									<p class="text-sm font-semibold text-gray-900 dark:text-white">{formatMinutes(user.timeSaved)}</p>
									<div class="w-16 sm:w-24 bg-gray-200 dark:bg-gray-700 rounded-full h-2 mt-1">
										<div
											class="bg-green-500 h-2 rounded-full transition-all duration-300"
											style="width: {(user.timeSaved / Math.max(...analyticsData.userBreakdown.map(u => u.timeSaved))) * 100}%"
										></div>
									</div>
								</div>
							</div>
						{/each}
					</div>
				</div>
			</div>

			<!-- System Info -->
			<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
				<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">System Information</h3>
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
					<div>
						<p class="text-gray-600 dark:text-gray-300">Timezone</p>
						<p class="font-medium text-gray-900 dark:text-white">Europe/Budapest</p>
					</div>
					<div>
						<p class="text-gray-600 dark:text-gray-300">Last Analysis</p>
						<p class="font-medium text-gray-900 dark:text-white">Today 00:00</p>
					</div>
					<div>
						<p class="text-gray-600 dark:text-gray-300">Idle Threshold</p>
						<p class="font-medium text-gray-900 dark:text-white">10 minutes</p>
					</div>
				</div>
			</div>

			<!-- Footer -->
			<div class="mt-6 sm:mt-8 text-center text-xs sm:text-sm text-gray-600 dark:text-gray-400 px-2">
				<p>Analytics processed daily at 00:00 Europe/Budapest • Data includes manual time estimates with confidence intervals</p>
			</div>
		</div>
	</div>
{/if}