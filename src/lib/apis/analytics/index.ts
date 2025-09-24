import { WEBUI_API_BASE_URL } from '$lib/constants';

export const getAnalyticsSummary = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/summary`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getAnalyticsDailyTrend = async (token: string, days: number = 7) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/daily-trend?days=${days}`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getAnalyticsUserBreakdown = async (token: string, limit: number = 10) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/user-breakdown?limit=${limit}`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getAnalyticsHealth = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/health`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const exportAnalyticsData = async (token: string, format: string = 'csv', type: string = 'summary') => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/export/${format}?type=${type}`, {
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
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// Password verification removed - now using existing OpenWebUI authentication
// Analytics access is controlled by admin role in the UI

export const getAnalyticsConversations = async (token: string, limit: number = 20, offset: number = 0) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/conversations?limit=${limit}&offset=${offset}`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const triggerAnalyticsProcessing = async (token: string, date?: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/analytics/trigger-processing`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: date ? JSON.stringify({ date }) : '{}'
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail || err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};