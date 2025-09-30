/**
 * Unit tests for Analytics API service
 *
 * This module tests the frontend API service layer including:
 * - API endpoint calls
 * - Error handling
 * - Response parsing
 * - Authentication token handling
 */
import { describe, it, expect, beforeEach, vi, type Mock } from 'vitest';

import {
	getAnalyticsSummary,
	getAnalyticsDailyTrend,
	getAnalyticsUserBreakdown,
	getAnalyticsHealth,
	getAnalyticsChats,
	exportAnalyticsData
} from './index';

// Mock fetch globally
global.fetch = vi.fn() as Mock;

// Mock WEBUI_API_BASE_URL
vi.mock('$lib/constants', () => ({
	WEBUI_API_BASE_URL: 'http://localhost:8080/api/v1'
}));

describe('Analytics API Service', () => {
	const mockToken = 'test_jwt_token';
	const mockFetch = global.fetch as Mock;

	beforeEach(() => {
		mockFetch.mockClear();
	});

	describe('getAnalyticsSummary', () => {
		it('should successfully fetch analytics summary', async () => {
			const mockSummaryData = {
				totalChats: 100,
				totalTimeSaved: 3000,
				avgTimeSavedPerChat: 30.0,
				confidenceLevel: 85.0
			};

			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockSummaryData
			});

			const result = await getAnalyticsSummary(mockToken);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/summary',
				{
					method: 'GET',
					headers: {
						'Content-Type': 'application/json',
						Authorization: `Bearer ${mockToken}`
					}
				}
			);

			expect(result).toEqual(mockSummaryData);
		});

		it('should handle API errors gracefully', async () => {
			const mockError = { detail: 'Unauthorized' };

			mockFetch.mockResolvedValueOnce({
				ok: false,
				json: async () => mockError
			});

			await expect(getAnalyticsSummary(mockToken)).rejects.toEqual(mockError);
		});

		it('should handle network errors', async () => {
			mockFetch.mockRejectedValueOnce(new Error('Network error'));

			const result = await getAnalyticsSummary(mockToken);

			expect(result).toBeNull();
		});

		it('should handle malformed JSON responses', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: false,
				json: async () => {
					throw new Error('Invalid JSON');
				}
			});

			const result = await getAnalyticsSummary(mockToken);

			expect(result).toBeNull();
		});
	});

	describe('getAnalyticsDailyTrend', () => {
		it('should successfully fetch daily trend data', async () => {
			const mockTrendData = {
				data: [
					{
						date: '2025-01-20',
						chats: 15,
						timeSaved: 450,
						avgConfidence: 80.0
					},
					{
						date: '2025-01-19',
						chats: 12,
						timeSaved: 360,
						avgConfidence: 82.0
					}
				]
			};

			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockTrendData
			});

			const result = await getAnalyticsDailyTrend(mockToken, 7);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/daily-trend?days=7',
				{
					method: 'GET',
					headers: {
						'Content-Type': 'application/json',
						Authorization: `Bearer ${mockToken}`
					}
				}
			);

			expect(result).toEqual(mockTrendData);
		});

		it('should use default days parameter', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ data: [] })
			});

			await getAnalyticsDailyTrend(mockToken);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/daily-trend?days=7',
				expect.any(Object)
			);
		});
	});

	describe('getAnalyticsUserBreakdown', () => {
		it('should successfully fetch user breakdown data', async () => {
			const mockUserData = {
				users: [
					{
						userName: 'User One (user1@example.com)',
						chats: 25,
						timeSaved: 750,
						avgConfidence: 85.0
					}
				]
			};

			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockUserData
			});

			const result = await getAnalyticsUserBreakdown(mockToken, 10);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/user-breakdown?limit=10',
				{
					method: 'GET',
					headers: {
						'Content-Type': 'application/json',
						Authorization: `Bearer ${mockToken}`
					}
				}
			);

			expect(result).toEqual(mockUserData);
		});

		it('should use default limit parameter', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ users: [] })
			});

			await getAnalyticsUserBreakdown(mockToken);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/user-breakdown?limit=10',
				expect.any(Object)
			);
		});
	});

	describe('getAnalyticsHealth', () => {
		it('should successfully fetch health status', async () => {
			const mockHealthData = {
				status: 'healthy',
				lastProcessingRun: '2025-01-20T10:00:00',
				nextScheduledRun: '2025-01-21T00:00:00',
				systemInfo: {
					timezone: 'UTC',
					idleThresholdMinutes: 10,
					processingVersion: '1.0'
				}
			};

			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockHealthData
			});

			const result = await getAnalyticsHealth(mockToken);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/health',
				{
					method: 'GET',
					headers: {
						'Content-Type': 'application/json',
						Authorization: `Bearer ${mockToken}`
					}
				}
			);

			expect(result).toEqual(mockHealthData);
		});
	});

	describe('getAnalyticsChats', () => {
		it('should successfully fetch chats data', async () => {
			const mockChatData = {
				chats: [
					{
						id: 'conv1',
						userName: 'User One (user1@example.com)',
						createdAt: '2025-01-20T10:00:00',
						timeSaved: 45,
						confidence: 85,
						summary: 'Test chat summary'
					}
				]
			};

			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => mockChatData
			});

			const result = await getAnalyticsChats(mockToken, 20, 0);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/chats?limit=20&offset=0',
				{
					method: 'GET',
					headers: {
						'Content-Type': 'application/json',
						Authorization: `Bearer ${mockToken}`
					}
				}
			);

			expect(result).toEqual(mockChatData);
		});

		it('should use default parameters', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => ({ chats: [] })
			});

			await getAnalyticsChats(mockToken);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/chats?limit=20&offset=0',
				expect.any(Object)
			);
		});
	});

	describe('exportAnalyticsData', () => {
		it('should successfully export CSV data', async () => {
			const mockCsvData = 'Metric,Value\nTotal Chats,50\n';
			const mockBlob = new Blob([mockCsvData], { type: 'text/csv' });

			mockFetch.mockResolvedValueOnce({
				ok: true,
				blob: async () => mockBlob
			});

			const result = await exportAnalyticsData(mockToken, 'csv', 'summary');

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/export/csv?type=summary',
				{
					method: 'GET',
					headers: {
						Authorization: `Bearer ${mockToken}`
					}
				}
			);

			expect(result).toEqual(mockBlob);
		});

		it('should use default parameters', async () => {
			const mockBlob = new Blob([''], { type: 'text/csv' });

			mockFetch.mockResolvedValueOnce({
				ok: true,
				blob: async () => mockBlob
			});

			await exportAnalyticsData(mockToken);

			expect(mockFetch).toHaveBeenCalledWith(
				'http://localhost:8080/api/v1/analytics/export/csv?type=summary',
				expect.any(Object)
			);
		});

		it('should handle export errors', async () => {
			const mockError = { detail: 'Export failed' };

			mockFetch.mockResolvedValueOnce({
				ok: false,
				json: async () => mockError
			});

			await expect(exportAnalyticsData(mockToken, 'csv', 'summary')).rejects.toEqual(mockError);
		});

		it('should handle blob conversion errors', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: false,
				blob: async () => {
					throw new Error('Blob conversion failed');
				}
			});

			const result = await exportAnalyticsData(mockToken, 'csv', 'summary');

			expect(result).toBeNull();
		});
	});

	describe('Error Handling', () => {
		it('should handle 404 errors appropriately', async () => {
			const mockError = { detail: 'Not Found', status: 404 };

			mockFetch.mockResolvedValueOnce({
				ok: false,
				status: 404,
				json: async () => mockError
			});

			try {
				await getAnalyticsSummary(mockToken);
			} catch (error) {
				expect(error).toEqual(mockError);
			}
		});

		it('should handle 403 unauthorized errors', async () => {
			const mockError = { detail: 'Forbidden' };

			mockFetch.mockResolvedValueOnce({
				ok: false,
				status: 403,
				json: async () => mockError
			});

			await expect(getAnalyticsSummary(mockToken)).rejects.toEqual(mockError);
		});

		it('should handle server errors (500)', async () => {
			const mockError = { detail: 'Internal Server Error' };

			mockFetch.mockResolvedValueOnce({
				ok: false,
				status: 500,
				json: async () => mockError
			});

			await expect(getAnalyticsSummary(mockToken)).rejects.toEqual(mockError);
		});
	});

	describe('Authentication', () => {
		it('should include Bearer token in all requests', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => ({})
			});

			await getAnalyticsSummary(mockToken);

			expect(mockFetch).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({
					headers: expect.objectContaining({
						Authorization: `Bearer ${mockToken}`
					})
				})
			);
		});

		it('should handle missing token gracefully', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: async () => ({})
			});

			await getAnalyticsSummary('');

			expect(mockFetch).toHaveBeenCalledWith(
				expect.any(String),
				expect.objectContaining({
					headers: expect.objectContaining({
						Authorization: 'Bearer '
					})
				})
			);
		});
	});

	describe('Performance', () => {
		it('should handle concurrent requests properly', async () => {
			// Mock multiple successful responses
			mockFetch
				.mockResolvedValueOnce({
					ok: true,
					json: async () => ({ totalChats: 100 })
				})
				.mockResolvedValueOnce({
					ok: true,
					json: async () => ({ data: [] })
				})
				.mockResolvedValueOnce({
					ok: true,
					json: async () => ({ users: [] })
				});

			const promises = [
				getAnalyticsSummary(mockToken),
				getAnalyticsDailyTrend(mockToken),
				getAnalyticsUserBreakdown(mockToken)
			];

			const results = await Promise.all(promises);

			expect(results).toHaveLength(3);
			expect(mockFetch).toHaveBeenCalledTimes(3);
		});
	});
});