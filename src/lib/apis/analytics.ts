import { WEBUI_API_BASE_URL } from '$lib/constants';

type AnalyticsSummary = {
	totalChats: number;
	totalTimeSaved: number;
	avgTimeSavedPerChat: number;
	confidenceLevel: number;
};

type DailyTrendItem = {
	date: string;
	chats: number;
	timeSaved: number;
	avgConfidence: number;
};

type UserBreakdownItem = {
	userId: string;
	userName: string;
	chats: number;
	timeSaved: number;
	avgConfidence: number;
};

type SystemInfo = {
	timezone: string;
	processingEnabled: boolean;
	idleThresholdMinutes: number;
	modelName: string;
};

type HealthStatus = {
	status: string;
	lastProcessingRun: string | null;
	nextScheduledRun: string;
	systemInfo: SystemInfo;
};

type ChatItem = {
	id: string;
	userId: string;
	userName: string;
	createdAt: string;
	timeSaved: number;
	confidence: number;
	summary: string;
	topic: string;
	messageCount: number;
};

type ProcessingTriggerResponse = {
	status: string;
	targetDate: string;
	message: string;
	processingLogId?: string;
	chatsProcessed: number;
	chatsFailed: number;
	durationSeconds: number;
	totalCostUsd: number;
	modelUsed: string;
};

export const getAnalyticsSummary = async (
	token: string = '',
	startDate?: string,
	endDate?: string,
	rangeType?: string
): Promise<AnalyticsSummary> => {
	let error = null;

	const params = new URLSearchParams();
	if (rangeType) {
		params.append('range_type', rangeType);
	} else {
		if (startDate) params.append('start_date', startDate);
		if (endDate) params.append('end_date', endDate);
	}

	const url = `${WEBUI_API_BASE_URL}/analytics/summary${params.toString() ? '?' + params.toString() : ''}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getAnalyticsTrends = async (
	token: string = '',
	startDate?: string,
	endDate?: string,
	rangeType?: string
): Promise<DailyTrendItem[]> => {
	let error = null;

	const params = new URLSearchParams();
	if (rangeType) {
		params.append('range_type', rangeType);
	} else {
		if (startDate) params.append('start_date', startDate);
		if (endDate) params.append('end_date', endDate);
	}

	const url = `${WEBUI_API_BASE_URL}/analytics/trends${params.toString() ? '?' + params.toString() : ''}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res.data || [];
};

export const getAnalyticsUserBreakdown = async (
	token: string = '',
	limit: number = 10,
	startDate?: string,
	endDate?: string,
	rangeType?: string
): Promise<UserBreakdownItem[]> => {
	let error = null;

	const params = new URLSearchParams();
	params.append('limit', limit.toString());
	if (rangeType) {
		params.append('range_type', rangeType);
	} else {
		if (startDate) params.append('start_date', startDate);
		if (endDate) params.append('end_date', endDate);
	}

	const url = `${WEBUI_API_BASE_URL}/analytics/user-breakdown?${params.toString()}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res.users || [];
};

export const getAnalyticsHealth = async (token: string = ''): Promise<HealthStatus> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/health`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getAnalyticsChats = async (
	token: string = '',
	limit: number = 20,
	offset: number = 0,
	fullSummary: boolean = false,
	startDate?: string,
	endDate?: string,
	rangeType?: string
): Promise<ChatItem[]> => {
	let error = null;

	const params = new URLSearchParams();
	params.append('limit', limit.toString());
	params.append('offset', offset.toString());
	params.append('full_summary', fullSummary.toString());
	if (rangeType) {
		params.append('range_type', rangeType);
	} else {
		if (startDate) params.append('start_date', startDate);
		if (endDate) params.append('end_date', endDate);
	}

	const url = `${WEBUI_API_BASE_URL}/analytics/chats?${params.toString()}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res.chats || [];
};

export const exportAnalyticsData = async (
	token: string = '',
	format: string = 'csv',
	type: string = 'summary',
	startDate?: string,
	endDate?: string,
	rangeType?: string
): Promise<Blob | null> => {
	let error = null;

	const params = new URLSearchParams();
	params.append('type', type);
	if (rangeType) {
		params.append('range_type', rangeType);
	} else {
		if (startDate) params.append('start_date', startDate);
		if (endDate) params.append('end_date', endDate);
	}

	const url = `${WEBUI_API_BASE_URL}/analytics/export/${format}?${params.toString()}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.blob();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const triggerAnalyticsProcessing = async (
	token: string = '',
	date?: string
): Promise<ProcessingTriggerResponse> => {
	let error = null;

	const url = date
		? `${WEBUI_API_BASE_URL}/analytics/trigger-processing?date=${date}`
		: `${WEBUI_API_BASE_URL}/analytics/trigger-processing`;

	const res = await fetch(url, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail ?? 'Server connection failed';
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};