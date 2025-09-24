<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import LockClosed from '$lib/components/icons/LockClosed.svelte';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';
	import {
		getAnalyticsSummary,
		getAnalyticsDailyTrend,
		getAnalyticsUserBreakdown,
		getAnalyticsHealth,
		getAnalyticsConversations,
		exportAnalyticsData,
		triggerAnalyticsProcessing
	} from '$lib/apis/analytics';

	const i18n = getContext('i18n');

	// Analytics data state
	let analyticsData = {
		summary: null,
		dailyTrend: [],
		userBreakdown: [],
		health: null,
		recentConversations: [],
		loading: true,
		error: null
	};

	// Manual processing state
	let isProcessing = false;
	let processingMessage = '';

	// Check user authentication and admin role
	$: isAuthenticated = $user?.token;
	$: isAdmin = $user?.role === 'admin';
	$: hasAccess = isAuthenticated && isAdmin;

	const loadAnalytics = async () => {
		if (!$user?.token) {
			analyticsData.error = 'User not authenticated';
			analyticsData.loading = false;
			return;
		}

		try {
			analyticsData.loading = true;
			analyticsData.error = null;

			// Load all analytics data
			const [summary, dailyTrend, userBreakdown, health, conversations] = await Promise.allSettled([
				getAnalyticsSummary($user.token),
				getAnalyticsDailyTrend($user.token, 7),
				getAnalyticsUserBreakdown($user.token, 10),
				getAnalyticsHealth($user.token),
				getAnalyticsConversations($user.token, 10)
			]);

			// Handle successful responses
			if (summary.status === 'fulfilled' && summary.value) {
				analyticsData.summary = summary.value;
			}
			if (dailyTrend.status === 'fulfilled' && dailyTrend.value) {
				analyticsData.dailyTrend = dailyTrend.value.data || [];
			}
			if (userBreakdown.status === 'fulfilled' && userBreakdown.value) {
				analyticsData.userBreakdown = userBreakdown.value.users || [];
			}
			if (health.status === 'fulfilled' && health.value) {
				analyticsData.health = health.value;
			}
			if (conversations.status === 'fulfilled' && conversations.value) {
				analyticsData.recentConversations = conversations.value.conversations || [];
			}

			// Check if any requests failed with 404 (API not implemented)
			const hasNotFound = [summary, dailyTrend, userBreakdown, health, conversations].some(
				result => result.status === 'rejected' && result.reason?.status === 404
			);

			if (hasNotFound) {
				toast.info('Analytics API endpoints are not yet implemented. Showing empty state.');
			}

			analyticsData.loading = false;
		} catch (err) {
			console.error('Failed to load analytics:', err);
			analyticsData.error = err.message || 'Failed to load analytics data';
			analyticsData.loading = false;
			toast.error('Failed to load analytics data');
		}
	};

	const exportData = async (type: string) => {
		if (!$user?.token) {
			toast.error('User not authenticated');
			return;
		}

		try {
			const blob = await exportAnalyticsData($user.token, 'csv', type);
			if (blob) {
				const url = window.URL.createObjectURL(blob);
				const link = document.createElement('a');
				link.href = url;
				link.download = `analytics-${type}-export-${new Date().toISOString().split('T')[0]}.csv`;
				link.click();
				window.URL.revokeObjectURL(url);
				toast.success(`${type} data exported successfully`);
			}
		} catch (err) {
			console.error('Export failed:', err);
			if (err?.status === 404) {
				toast.warning('Export functionality not yet implemented');
			} else {
				toast.error('Export failed');
			}
		}
	};

	const exportCSV = () => exportData('daily');

	const triggerProcessing = async () => {
		isProcessing = true;
		processingMessage = '';

		try {
			const result = await triggerAnalyticsProcessing($user.token);
			processingMessage = 'Processing started successfully!';

			// Refresh dashboard data after a delay
			setTimeout(() => {
				loadAnalytics();
				processingMessage = '';
			}, 3000);
		} catch (error) {
			processingMessage = 'Failed to trigger processing';
			console.error('Error triggering processing:', error);
		} finally {
			isProcessing = false;
		}
	};

	const formatMinutes = (minutes: number): string => {
		const hours = Math.floor(minutes / 60);
		const mins = minutes % 60;
		return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
	};

	// Reactive statement to load analytics when user gains access
	$: if (hasAccess && analyticsData.loading === true) {
		loadAnalytics();
	} else if (!hasAccess) {
		analyticsData.loading = false;
	}

	onMount(() => {
		// Initial load check
		if (!hasAccess) {
			analyticsData.loading = false;
		}
	});
</script>

<svelte:head>
	<title>Analytics Dashboard - AI Time Savings</title>
</svelte:head>

<!-- Access Control Messages -->
{#if !isAuthenticated}
	<div class="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
		<div class="text-center max-w-md mx-4">
			<div class="flex justify-center mb-4">
				<LockClosed className="w-16 h-16 text-gray-400" />
			</div>
			<h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">Authentication Required</h2>
			<p class="text-gray-600 dark:text-gray-300 mb-6">
				Please log in to access the analytics dashboard.
			</p>
			<a
				href="/auth"
				class="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
			>
				Go to Login
			</a>
		</div>
	</div>
{:else if !isAdmin}
	<div class="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
		<div class="text-center max-w-md mx-4">
			<div class="flex justify-center mb-4">
				<LockClosed className="w-16 h-16 text-red-400" />
			</div>
			<h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-4">Access Denied</h2>
			<p class="text-gray-600 dark:text-gray-300 mb-4">
				Analytics dashboard requires administrator privileges.
			</p>
			<div class="bg-amber-50 dark:bg-amber-900 border border-amber-200 dark:border-amber-700 rounded-lg p-4">
				<p class="text-amber-800 dark:text-amber-200 text-sm">
					<strong>Current user:</strong> {$user?.email || 'Unknown'}<br>
					<strong>Role:</strong> {$user?.role || 'Unknown'}<br>
					<strong>Required role:</strong> admin
				</p>
			</div>
		</div>
	</div>
{:else}
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
					<div class="flex flex-wrap gap-2">
						<button
							on:click={triggerProcessing}
							disabled={isProcessing}
							class="flex items-center px-3 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-500 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm"
						>
							{#if isProcessing}
								<svg class="animate-spin w-4 h-4 mr-2" viewBox="0 0 24 24">
									<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none"></circle>
									<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
								</svg>
								Processing...
							{:else}
								🔄 Run Analytics Now
							{/if}
						</button>
						<button
							on:click={() => exportData('summary')}
							class="flex items-center px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors text-sm"
						>
							<ArrowDownTray className="w-4 h-4 mr-2" />
							Export Summary
						</button>
						<button
							on:click={() => exportData('daily')}
							class="flex items-center px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors text-sm"
						>
							<ArrowDownTray className="w-4 h-4 mr-2" />
							Export Daily
						</button>
						<button
							on:click={() => exportData('detailed')}
							class="flex items-center px-3 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors text-sm"
						>
							<ArrowDownTray className="w-4 h-4 mr-2" />
							Export Detailed
						</button>
					</div>
				</div>
			</div>

			<!-- Processing Message -->
			{#if processingMessage}
				<div class="mb-4 p-3 rounded-lg {processingMessage.includes('success') ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300' : 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300'}">
					{processingMessage}
				</div>
			{/if}

			<!-- Loading State -->
			{#if analyticsData.loading}
				<div class="flex items-center justify-center py-12">
					<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
					<span class="ml-3 text-gray-600 dark:text-gray-300">Loading analytics data...</span>
				</div>
			{:else if analyticsData.error}
				<div class="bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-lg p-4 mb-8">
					<p class="text-red-800 dark:text-red-200">Error loading analytics: {analyticsData.error}</p>
				</div>
			{:else}
				<!-- Key Metrics Cards -->
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-8">
					<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
						<div class="flex items-center">
							<div class="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
								<ChartBar className="w-6 h-6 text-blue-600" />
							</div>
							<div class="ml-4">
								<p class="text-sm font-medium text-gray-600 dark:text-gray-300">Total Conversations</p>
								<p class="text-2xl font-semibold text-gray-900 dark:text-white">
									{analyticsData.summary?.totalConversations?.toLocaleString() || '0'}
								</p>
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
								<p class="text-2xl font-semibold text-gray-900 dark:text-white">
									{analyticsData.summary?.totalTimeSaved ? formatMinutes(analyticsData.summary.totalTimeSaved) : '0m'}
								</p>
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
								<p class="text-2xl font-semibold text-gray-900 dark:text-white">
									{analyticsData.summary?.avgTimeSavedPerConversation ? formatMinutes(analyticsData.summary.avgTimeSavedPerConversation) : '0m'}
								</p>
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
								<p class="text-2xl font-semibold text-gray-900 dark:text-white">
									{analyticsData.summary?.confidenceLevel || '0'}%
								</p>
							</div>
						</div>
					</div>
				</div>
			{/if}

			<!-- Charts Section -->
			{#if !analyticsData.loading && !analyticsData.error}
				<div class="grid grid-cols-1 xl:grid-cols-2 gap-6 lg:gap-8 mb-8">
					<!-- Daily Trend Chart -->
					<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
						<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Daily Time Savings Trend</h3>
						{#if analyticsData.dailyTrend && analyticsData.dailyTrend.length > 0}
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
						{:else}
							<div class="h-48 sm:h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
								<div class="text-center">
									<p>No daily trend data available</p>
									<p class="text-sm mt-1">Analytics API not yet implemented</p>
								</div>
							</div>
						{/if}
					</div>

					<!-- User Breakdown -->
					<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
						<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Top Users by Time Saved</h3>
						{#if analyticsData.userBreakdown && analyticsData.userBreakdown.length > 0}
							<div class="space-y-4">
								{#each analyticsData.userBreakdown as user, index}
									<div class="flex items-center justify-between">
										<div class="flex items-center min-w-0 flex-1">
											<div class="w-8 h-8 bg-gray-300 dark:bg-gray-600 rounded-full flex items-center justify-center text-sm font-medium text-gray-700 dark:text-gray-300 flex-shrink-0">
												#{index + 1}
											</div>
											<div class="ml-3 min-w-0 flex-1">
												<p class="text-sm font-medium text-gray-900 dark:text-white truncate">{user.userName}</p>
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
						{:else}
							<div class="flex items-center justify-center h-48 text-gray-500 dark:text-gray-400">
								<div class="text-center">
									<p>No user breakdown data available</p>
									<p class="text-sm mt-1">Analytics API not yet implemented</p>
								</div>
							</div>
						{/if}
					</div>
				</div>

				<!-- Enhanced Analytics Sections -->
				<div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6 mb-8">
					<!-- Time Analysis Breakdown -->
					<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
						<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Time Analysis</h3>
						{#if analyticsData.summary}
							<div class="space-y-3">
								<div class="flex justify-between items-center">
									<span class="text-sm text-gray-600 dark:text-gray-300">Active Time:</span>
									<span class="font-medium text-gray-900 dark:text-white">
										{analyticsData.summary.totalActiveTime ? formatMinutes(analyticsData.summary.totalActiveTime) : '0m'}
									</span>
								</div>
								<div class="flex justify-between items-center">
									<span class="text-sm text-gray-600 dark:text-gray-300">Idle Time:</span>
									<span class="font-medium text-gray-900 dark:text-white">
										{analyticsData.summary.totalIdleTime ? formatMinutes(analyticsData.summary.totalIdleTime) : '0m'}
									</span>
								</div>
								<div class="flex justify-between items-center">
									<span class="text-sm text-gray-600 dark:text-gray-300">Efficiency:</span>
									<span class="font-medium text-green-600 dark:text-green-400">
										{analyticsData.summary.efficiencyRate || 0}%
									</span>
								</div>
								<div class="mt-4">
									<div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
										<div
											class="bg-green-500 h-2 rounded-full transition-all duration-300"
											style="width: {analyticsData.summary.efficiencyRate || 0}%"
										></div>
									</div>
									<p class="text-xs text-gray-600 dark:text-gray-300 mt-1">Overall efficiency score</p>
								</div>
							</div>
						{:else}
							<div class="text-center py-6 text-gray-500 dark:text-gray-400">
								<p>No time analysis data</p>
								<p class="text-sm mt-1">API not implemented</p>
							</div>
						{/if}
					</div>

					<!-- System Health Status -->
					<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
						<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Processing Status</h3>
						{#if analyticsData.health}
							<div class="space-y-3">
								<div class="flex items-center justify-between">
									<span class="text-sm text-gray-600 dark:text-gray-300">Status:</span>
									<span class="px-2 py-1 rounded text-xs font-medium
										{analyticsData.health.status === 'success' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
										 analyticsData.health.status === 'running' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
										 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'}">
										{analyticsData.health.status}
									</span>
								</div>
								<div class="flex justify-between items-center">
									<span class="text-sm text-gray-600 dark:text-gray-300">Last Run:</span>
									<span class="font-medium text-gray-900 dark:text-white text-sm">
										{analyticsData.health.lastRun}
									</span>
								</div>
								<div class="flex justify-between items-center">
									<span class="text-sm text-gray-600 dark:text-gray-300">Processed:</span>
									<span class="font-medium text-gray-900 dark:text-white">
										{analyticsData.health.processedCount} conversations
									</span>
								</div>
								{#if analyticsData.health.processingTime}
									<div class="flex justify-between items-center">
										<span class="text-sm text-gray-600 dark:text-gray-300">Processing Time:</span>
										<span class="font-medium text-gray-900 dark:text-white">
											{analyticsData.health.processingTime}s
										</span>
									</div>
								{/if}
							</div>
						{:else}
							<div class="text-center py-6 text-gray-500 dark:text-gray-400">
								<p>System health unavailable</p>
								<p class="text-sm mt-1">Health API not implemented</p>
							</div>
						{/if}
					</div>

					<!-- Recent Conversations -->
					<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm lg:col-span-2 xl:col-span-1">
						<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recent Conversations</h3>
						{#if analyticsData.recentConversations && analyticsData.recentConversations.length > 0}
							<div class="space-y-3">
								{#each analyticsData.recentConversations.slice(0, 5) as conversation}
									<div class="flex justify-between items-center py-2 border-b border-gray-100 dark:border-gray-700">
										<div class="flex-1">
											<p class="text-sm font-medium text-gray-900 dark:text-white">
												{new Date(conversation.first_message_at).toLocaleDateString()}
											</p>
											<p class="text-xs text-gray-600 dark:text-gray-300">
												{formatMinutes(conversation.total_duration_minutes)} duration
											</p>
										</div>
										<div class="text-right">
											<p class="text-sm font-semibold text-green-600 dark:text-green-400">
												{formatMinutes(conversation.time_saved_minutes)}
											</p>
											<p class="text-xs text-gray-600 dark:text-gray-300">
												{conversation.confidence_score}% confidence
											</p>
										</div>
									</div>
								{/each}
							</div>
						{:else}
							<div class="text-center py-6 text-gray-500 dark:text-gray-400">
								<p>No recent conversations</p>
								<p class="text-sm mt-1">Conversations API not implemented</p>
							</div>
						{/if}
					</div>
				</div>
			{/if}

			<!-- System Info -->
			{#if !analyticsData.loading && !analyticsData.error}
				<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
					<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">System Information</h3>
					<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
						<div>
							<p class="text-gray-600 dark:text-gray-300">Timezone</p>
							<p class="font-medium text-gray-900 dark:text-white">
								{analyticsData.health?.timezone || 'Europe/Budapest'}
							</p>
						</div>
						<div>
							<p class="text-gray-600 dark:text-gray-300">Last Analysis</p>
							<p class="font-medium text-gray-900 dark:text-white">
								{analyticsData.health?.lastRun || 'API not available'}
							</p>
						</div>
						<div>
							<p class="text-gray-600 dark:text-gray-300">Idle Threshold</p>
							<p class="font-medium text-gray-900 dark:text-white">
								{analyticsData.health?.idleThreshold || '10'} minutes
							</p>
						</div>
						{#if analyticsData.health?.nextRun}
							<div>
								<p class="text-gray-600 dark:text-gray-300">Next Run</p>
								<p class="font-medium text-gray-900 dark:text-white">
									{analyticsData.health.nextRun}
								</p>
							</div>
						{/if}
						{#if analyticsData.summary?.totalConversations}
							<div>
								<p class="text-gray-600 dark:text-gray-300">Data Coverage</p>
								<p class="font-medium text-gray-900 dark:text-white">
									{analyticsData.summary.totalConversations} conversations
								</p>
							</div>
						{/if}
					</div>
				</div>
			{/if}

			<!-- Footer -->
			<div class="mt-6 sm:mt-8 text-center text-xs sm:text-sm text-gray-600 dark:text-gray-400 px-2">
				<p>Analytics processed daily at 00:00 Europe/Budapest • Data includes manual time estimates with confidence intervals</p>
			</div>
		</div>
	</div>
{/if}