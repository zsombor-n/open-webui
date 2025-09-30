<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import ArrowDownTray from '$lib/components/icons/ArrowDownTray.svelte';
	import LockClosed from '$lib/components/icons/LockClosed.svelte';
	import { toast } from 'svelte-sonner';
	import { user, config, showSidebar } from '$lib/stores';
	import AnalyticsNavbar from '$lib/components/analytics/Navbar.svelte';
	import {
		getAnalyticsSummary,
		getAnalyticsTrends,
		getAnalyticsUserBreakdown,
		getAnalyticsHealth,
		getAnalyticsChats,
		exportAnalyticsData,
		triggerAnalyticsProcessing
	} from '$lib/apis/analytics';
	import { type DateRangeValue, calculateLast7Days, calculateDateRange } from '$lib/utils/dateRanges';

	const i18n = getContext('i18n');

	// Analytics data state
	let analyticsData = {
		summary: null,
		dailyTrend: [],
		userBreakdown: [],
		health: null,
		recentChats: [],
		loading: true,
		error: null
	};

	// Manual processing state
	let isProcessing = false;
	let processingMessage = '';

	// Date range state
	let selectedDateRange: DateRangeValue = 'this_week';

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

			// Load all analytics data using range type (backend calculates dates with Pendulum)
			// Note: Daily trend always shows last 7 days regardless of selected range
			const last7Days = calculateLast7Days();

			// Convert quarter-based ranges to actual dates (backend doesn't support "quarter" range type)
			const isQuarterRange = selectedDateRange.includes('quarter');
			const dateRange = isQuarterRange ? calculateDateRange(selectedDateRange) : null;

			// Use either calculated dates (for quarters) or range type (for week/month/year)
			const startDate = isQuarterRange ? dateRange.startDate : undefined;
			const endDate = isQuarterRange ? dateRange.endDate : undefined;
			const rangeType = isQuarterRange ? undefined : selectedDateRange;

			// Build promises array conditionally based on feature flags
			const promises: Record<string, Promise<any>> = {
				summary: getAnalyticsSummary($user.token, startDate, endDate, rangeType),
				dailyTrend: getAnalyticsTrends($user.token, last7Days.startDate, last7Days.endDate),
				health: getAnalyticsHealth($user.token)
			};

			// Only fetch user breakdown if feature flag is enabled
			if ($config?.features?.enable_user_breakdown ?? false) {
				promises.userBreakdown = getAnalyticsUserBreakdown($user.token, 10, startDate, endDate, rangeType);
			}

			// Only fetch chats if feature flag is enabled
			if ($config?.features?.enable_top_chats ?? false) {
				promises.chats = getAnalyticsChats($user.token, 10, 0, false, startDate, endDate, rangeType);
			}

			const results = await Promise.allSettled(Object.values(promises));
			const keys = Object.keys(promises);

			// Handle successful responses
			results.forEach((result, index) => {
				const key = keys[index];
				if (result.status === 'fulfilled' && result.value) {
					switch (key) {
						case 'summary':
							analyticsData.summary = result.value;
							break;
						case 'dailyTrend':
							analyticsData.dailyTrend = result.value || [];
							break;
						case 'userBreakdown':
							analyticsData.userBreakdown = result.value || [];
							break;
						case 'health':
							analyticsData.health = result.value;
							break;
						case 'chats':
							analyticsData.recentChats = result.value || [];
							break;
					}
				}
			});

			// Check if any requests failed with 404 (API not implemented)
			const hasNotFound = results.some(
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
			// Convert quarter-based ranges to actual dates (backend doesn't support "quarter" range type)
			const isQuarterRange = selectedDateRange.includes('quarter');
			const dateRange = isQuarterRange ? calculateDateRange(selectedDateRange) : null;

			// Use either calculated dates (for quarters) or range type (for week/month/year)
			const startDate = isQuarterRange ? dateRange.startDate : undefined;
			const endDate = isQuarterRange ? dateRange.endDate : undefined;
			const rangeType = isQuarterRange ? undefined : selectedDateRange;

			const blob = await exportAnalyticsData($user.token, 'csv', type, startDate, endDate, rangeType);
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

	const handleDateRangeChange = (event: CustomEvent) => {
		selectedDateRange = event.detail.value;
		// Reload data with new date range
		loadAnalytics();
	};

	const formatMinutes = (minutes: number): string => {
		const hours = Math.floor(minutes / 60);
		const mins = minutes % 60;
		return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
	};

	const formatMinutesWithTotal = (minutes: number): string => {
		const hours = Math.floor(minutes / 60);
		const mins = minutes % 60;
		const hoursMinutes = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
		return `${hoursMinutes} (${minutes.toLocaleString()} minutes)`;
	};

	// Ensure we always have exactly 7 consecutive days of data in ascending order
	const ensureSevenDays = (dailyData) => {
		// Generate the last 7 completed days (excluding today) going backwards
		const result = [];
		const today = new Date();

		for (let i = 7; i >= 1; i--) {
			const date = new Date(today);
			date.setDate(today.getDate() - i);
			const dateString = date.toISOString().split('T')[0];

			// Look for existing data for this date
			const existingData = dailyData ? dailyData.find(d => d.date === dateString) : null;

			result.push({
				date: dateString,
				timeSaved: existingData ? existingData.timeSaved : 0,
				chats: existingData ? existingData.chats : 0,
				avgConfidence: existingData ? existingData.avgConfidence : 0
			});
		}

		return result;
	};

	// Reactive data for chart
	$: sortedDailyTrend = analyticsData.dailyTrend ?
		ensureSevenDays(analyticsData.dailyTrend) : [];
	$: maxTimeSaved = Math.max(...sortedDailyTrend.map(d => d.timeSaved), 1); // Minimum 1 to avoid division by zero

	// Calculate bar height with better visual differentiation
	const calculateBarHeight = (timeSaved, maxTime) => {
		if (timeSaved === 0) return 24; // Special low height for zero values

		// Use logarithmic scaling for better visual differentiation
		const minHeight = 40;
		const maxHeight = 200;

		// Simple proportional scaling with minimum height for non-zero values
		const proportion = timeSaved / maxTime;
		const height = minHeight + (proportion * (maxHeight - minHeight));

		return Math.round(height);
	};

	const formatDateTime = (isoString: string | null | undefined): string => {
		if (!isoString) return 'Never';
		try {
			const date = new Date(isoString);
			// Format as "Sep 25, 2025 at 3:17 PM"
			return date.toLocaleDateString('en-US', {
				month: 'short',
				day: 'numeric',
				year: 'numeric'
			}) + ' at ' + date.toLocaleTimeString('en-US', {
				hour: 'numeric',
				minute: '2-digit',
				hour12: true
			});
		} catch (error) {
			return 'Invalid date';
		}
	};


	onMount(() => {
		// Initial load
		if (hasAccess) {
			loadAnalytics();
		} else {
			analyticsData.loading = false;
		}
	});
</script>

<svelte:head>
	<title>Analytics Dashboard - AI Time Savings</title>
</svelte:head>

<!-- Main Layout Container -->
<div class="flex-1 flex flex-col h-full overflow-hidden {$showSidebar ? 'md:max-w-[calc(100%-260px)]' : ''}">
	<!-- Analytics Navbar -->
	{#if hasAccess}
		<AnalyticsNavbar
			{triggerProcessing}
			{exportData}
			{isProcessing}
			bind:selectedDateRange
			on:dateRangeChange={handleDateRangeChange}
		/>
	{/if}

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
								<p class="text-sm font-medium text-gray-600 dark:text-gray-300">Total Chats</p>
								<p class="text-2xl font-semibold text-gray-900 dark:text-white">
									{analyticsData.summary?.totalChats?.toLocaleString() || '0'}
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
								<p class="text-sm font-medium text-gray-600 dark:text-gray-300">Avg. per Chat</p>
								<p class="text-2xl font-semibold text-gray-900 dark:text-white">
									{analyticsData.summary?.avgTimeSavedPerChat ? formatMinutes(analyticsData.summary.avgTimeSavedPerChat) : '0m'}
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
					<!-- Cogniforce EfX Card -->
					<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
						<!-- Top Row: 75% height - Main EfX Score -->
						<div class="flex flex-col h-full">
							<div class="flex-[3] flex items-center justify-center border-b border-gray-200 dark:border-gray-700 pb-4 mb-4">
								<div class="text-center">
									<div class="flex items-center justify-center gap-2 mb-3">
										<svg class="w-10 h-10 text-cyan-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
										</svg>
										<p class="text-xl font-medium text-gray-600 dark:text-gray-300">Cogniforce EfX™</p>
									</div>
									<p class="text-8xl font-bold text-gray-900 dark:text-white leading-none">
										{analyticsData.summary?.efxScore || '0'}
									</p>
									<p class="text-base text-gray-500 dark:text-gray-400 mt-2">Efficiency Index</p>
								</div>
							</div>

							<!-- Bottom Row: 25% height - 4 Components -->
							<div class="flex-[1] grid grid-cols-4 gap-3">
								<!-- Velocity -->
								<div class="text-center">
									<p class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Velocity <span class="text-green-600 dark:text-green-400">↑</span></p>
									<p class="text-3xl font-bold text-blue-600 dark:text-blue-400">
										{analyticsData.summary?.efxSpeed || '0'}
									</p>
								</div>

								<!-- Quality -->
								<div class="text-center">
									<p class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Quality <span class="text-green-600 dark:text-green-400">✓</span></p>
									<p class="text-3xl font-bold text-green-600 dark:text-green-400">
										{analyticsData.summary?.efxQuality || '0'}
									</p>
								</div>

								<!-- Safety -->
								<div class="text-center">
									<p class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Safety <span class="text-green-600 dark:text-green-400">✓</span></p>
									<p class="text-3xl font-bold text-orange-600 dark:text-orange-400">
										{analyticsData.summary?.efxSafety || '0'}
									</p>
								</div>

								<!-- Cost Efficiency -->
								<div class="text-center">
									<p class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Cost Efficiency <span class="text-green-600 dark:text-green-400">↑</span></p>
									<p class="text-3xl font-bold text-purple-600 dark:text-purple-400">
										{analyticsData.summary?.efxCost || '0'}
									</p>
								</div>
							</div>
						</div>
					</div>

					<!-- Daily Trend Chart -->
					<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
						<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Daily Time Savings Trend</h3>
						<div class="h-40 sm:h-52 flex items-end gap-3 sm:gap-4">
							{#each sortedDailyTrend as day, index}
								<div class="flex flex-col items-center flex-1 px-0.5">
									<div
										class="{day.timeSaved > 0 ? 'bg-blue-500 hover:bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'} rounded-t transition-all duration-300 w-full relative flex items-center justify-center"
										style="height: {calculateBarHeight(day.timeSaved, maxTimeSaved)}px;"
										title="{day.date}: {formatMinutes(day.timeSaved)} saved ({day.chats} chats)"
									>
										{#if day.timeSaved > 0}
											<div class="text-white text-xs font-medium text-center leading-tight px-1">
												{formatMinutes(day.timeSaved)}
											</div>
										{:else}
											<div class="text-gray-500 dark:text-gray-400 text-xs font-medium">
												0m
											</div>
										{/if}
									</div>
									<div class="text-xs text-gray-600 dark:text-gray-300 mt-2 text-center">
										{new Date(day.date).toLocaleDateString('en', { weekday: 'short' })}
									</div>
									<div class="text-xs text-gray-500 dark:text-gray-400">
										{day.date.split('-')[2]}
									</div>
								</div>
							{/each}
						</div>
						<div class="mt-4 text-sm text-gray-600 dark:text-gray-300">
							Last 7 days • Total: {formatMinutesWithTotal(sortedDailyTrend.reduce((sum, day) => sum + day.timeSaved, 0))}
						</div>
					</div>

					<!-- User Breakdown -->
					{#if ($config?.features?.enable_user_breakdown ?? false) && $user?.role === 'admin'}
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
												<p class="text-xs text-gray-600 dark:text-gray-300">{user.chats} chats</p>
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
					{/if}

					<!-- Recent Chats -->
					{#if ($config?.features?.enable_top_chats ?? false) && $user?.role === 'admin'}
					<div class="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
						<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Recent Chats</h3>
						{#if analyticsData.recentChats && analyticsData.recentChats.length > 0}
							<div class="space-y-3">
								{#each analyticsData.recentChats.slice(0, 5) as chat}
									<div class="flex justify-between items-center py-2 border-b border-gray-100 dark:border-gray-700">
										<div class="flex-1">
											<p class="text-sm font-medium text-gray-900 dark:text-white">
												{chat.topic || 'General Discussion'}
											</p>
											<p class="text-xs text-gray-600 dark:text-gray-300">
												{new Date(chat.createdAt).toLocaleDateString()}
											</p>
											<p class="text-xs text-gray-600 dark:text-gray-300">
												{chat.userName}
											</p>
										</div>
										<div class="text-right">
											<p class="text-sm font-semibold text-green-600 dark:text-green-400">
												{formatMinutes(chat.timeSaved)}
											</p>
											<p class="text-xs text-gray-600 dark:text-gray-300">
												{chat.confidence}% confidence
											</p>
										</div>
									</div>
								{/each}
							</div>
						{:else}
							<div class="text-center py-6 text-gray-500 dark:text-gray-400">
								<p>No recent chats</p>
								<p class="text-sm mt-1">Chats API not implemented</p>
							</div>
						{/if}
					</div>
					{/if}
				</div>
			{/if}

			<!-- System Info -->
			{#if !analyticsData.loading && !analyticsData.error}
				<div class="bg-white dark:bg-gray-800 rounded-lg p-4 sm:p-6 shadow-sm">
					<h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">System Information & Processing Status</h3>
					<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
						<div>
							<p class="text-gray-600 dark:text-gray-300">Processing Status</p>
							<p class="font-medium text-gray-900 dark:text-white">
								{#if analyticsData.health}
									<span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium
										{analyticsData.health.status === 'success' || analyticsData.health.status === 'healthy' ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
										 analyticsData.health.status === 'running' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
										 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'}">
										{analyticsData.health.status}
									</span>
								{:else}
									<span class="text-gray-500">Unknown</span>
								{/if}
							</p>
						</div>
						<div>
							<p class="text-gray-600 dark:text-gray-300">Last Processing Run</p>
							<p class="font-medium text-gray-900 dark:text-white">
								{formatDateTime(analyticsData.health?.lastProcessingRun)}
							</p>
						</div>
						<div>
							<p class="text-gray-600 dark:text-gray-300">Timezone</p>
							<p class="font-medium text-gray-900 dark:text-white">
								{analyticsData.health?.systemInfo?.timezone || 'UTC'}
							</p>
						</div>
						<div>
							<p class="text-gray-600 dark:text-gray-300">Idle Threshold</p>
							<p class="font-medium text-gray-900 dark:text-white">
								{analyticsData.health?.systemInfo?.idleThresholdMinutes || '10'} minutes
							</p>
						</div>
						{#if analyticsData.health?.nextScheduledRun}
							<div>
								<p class="text-gray-600 dark:text-gray-300">Next Scheduled Run</p>
								<p class="font-medium text-gray-900 dark:text-white">
									{formatDateTime(analyticsData.health.nextScheduledRun)}
								</p>
							</div>
						{/if}
						{#if analyticsData.summary?.totalChats}
							<div>
								<p class="text-gray-600 dark:text-gray-300">Data Coverage</p>
								<p class="font-medium text-gray-900 dark:text-white">
									{analyticsData.summary.totalChats} chats
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
</div>