export type DateRangeValue = 'this_week' | 'last_week' | 'this_month' | 'last_month' | 'this_quarter' | 'last_quarter' | 'this_year' | 'last_year';

export interface DateRange {
	startDate: string;
	endDate: string;
}

export function calculateDateRange(rangeValue: DateRangeValue): DateRange {
	const now = new Date();
	const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

	let startDate: Date;
	let endDate: Date;

	switch (rangeValue) {
		case 'this_week':
			// This week: Monday to today
			const dayOfWeek = today.getDay();
			const daysFromMonday = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Sunday = 0, so 6 days from Monday
			startDate = new Date(today);
			startDate.setDate(today.getDate() - daysFromMonday);
			endDate = today;
			break;

		case 'last_week':
			// Last week: Previous Monday to Sunday
			const lastWeekStart = new Date(today);
			const daysToLastMonday = today.getDay() === 0 ? 13 : today.getDay() + 6; // Get to previous Monday
			lastWeekStart.setDate(today.getDate() - daysToLastMonday);

			const lastWeekEnd = new Date(lastWeekStart);
			lastWeekEnd.setDate(lastWeekStart.getDate() + 6); // Sunday

			startDate = lastWeekStart;
			endDate = lastWeekEnd;
			break;

		case 'this_month':
			// This month: First day of current month to today
			startDate = new Date(today.getFullYear(), today.getMonth(), 1);
			endDate = today;
			break;

		case 'last_month':
			// Last month: First to last day of previous month
			const lastMonth = today.getMonth() === 0 ? 11 : today.getMonth() - 1;
			const lastMonthYear = today.getMonth() === 0 ? today.getFullYear() - 1 : today.getFullYear();

			startDate = new Date(lastMonthYear, lastMonth, 1);
			endDate = new Date(lastMonthYear, lastMonth + 1, 0); // Last day of month
			break;

		case 'this_quarter':
			// This quarter: First day of current quarter to today
			const currentQuarter = Math.floor(today.getMonth() / 3);
			startDate = new Date(today.getFullYear(), currentQuarter * 3, 1);
			endDate = today;
			break;

		case 'last_quarter':
			// Last quarter: First to last day of previous quarter
			const lastQuarter = Math.floor(today.getMonth() / 3) - 1;
			let lastQuarterYear = today.getFullYear();
			let adjustedQuarter = lastQuarter;

			if (lastQuarter < 0) {
				adjustedQuarter = 3; // Q4
				lastQuarterYear = today.getFullYear() - 1;
			}

			startDate = new Date(lastQuarterYear, adjustedQuarter * 3, 1);
			endDate = new Date(lastQuarterYear, adjustedQuarter * 3 + 3, 0); // Last day of quarter
			break;

		case 'this_year':
			// This year: January 1st to today
			startDate = new Date(today.getFullYear(), 0, 1);
			endDate = today;
			break;

		case 'last_year':
			// Last year: January 1st to December 31st of previous year
			const lastYear = today.getFullYear() - 1;
			startDate = new Date(lastYear, 0, 1);
			endDate = new Date(lastYear, 11, 31);
			break;

		default:
			// Default to this week
			const defaultDayOfWeek = today.getDay();
			const defaultDaysFromMonday = defaultDayOfWeek === 0 ? 6 : defaultDayOfWeek - 1;
			startDate = new Date(today);
			startDate.setDate(today.getDate() - defaultDaysFromMonday);
			endDate = today;
			break;
	}

	return {
		startDate: formatDate(startDate),
		endDate: formatDate(endDate)
	};
}

export function calculateLast7Days(): DateRange {
	const today = new Date();
	const endDate = new Date(today.getFullYear(), today.getMonth(), today.getDate());
	const startDate = new Date(endDate);
	startDate.setDate(endDate.getDate() - 6); // 7 days total (today + 6 previous days)

	return {
		startDate: formatDate(startDate),
		endDate: formatDate(endDate)
	};
}

function formatDate(date: Date): string {
	return date.toISOString().split('T')[0];
}