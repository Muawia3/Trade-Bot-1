/**
 * Format price according to symbol standard decimals
 */
export const formatPrice = (price, symbol = 'XAUUSD') => {
  if (price === null || price === undefined || isNaN(price)) return '0.00';
  const num = Number(price);
  if (symbol.toUpperCase().includes('XAU') || symbol.toUpperCase().includes('GOLD')) {
    return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (symbol.toUpperCase().includes('JPY')) {
    return num.toLocaleString('en-US', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
  }
  // Standard Forex (EURUSD, GBPUSD, etc.)
  return num.toLocaleString('en-US', { minimumFractionDigits: 5, maximumFractionDigits: 5 });
};

/**
 * Format currency amount with symbol ($)
 */
export const formatCurrency = (amount, currency = 'USD') => {
  if (amount === null || amount === undefined || isNaN(amount)) return '$0.00';
  const num = Number(amount);
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(num);
};

/**
 * Format percentage with positive/negative prefix
 */
export const formatPercent = (percent, includeSign = true) => {
  if (percent === null || percent === undefined || isNaN(percent)) return '0.00%';
  const num = Number(percent);
  const formatted = Math.abs(num).toFixed(2) + '%';
  if (!includeSign) return formatted;
  if (num > 0) return `+${formatted}`;
  if (num < 0) return `-${formatted}`;
  return formatted;
};

/**
 * Format dates
 */
export const formatDate = (dateString, includeTime = true) => {
  if (!dateString) return '-';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return String(dateString);

  if (includeTime) {
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  }
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
};

/**
 * Format Lot Size
 */
export const formatLot = (lots) => {
  if (lots === null || lots === undefined || isNaN(lots)) return '0.01';
  return Number(lots).toFixed(2);
};

/**
 * Return appropriate Tailwind color class for PnL / numeric direction
 */
export const getPnlColor = (value) => {
  const num = Number(value);
  if (num > 0) return 'text-emerald-400';
  if (num < 0) return 'text-rose-400';
  return 'text-slate-400';
};

export const getPnlBg = (value) => {
  const num = Number(value);
  if (num > 0) return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30';
  if (num < 0) return 'bg-rose-500/10 text-rose-400 border border-rose-500/30';
  return 'bg-slate-700/20 text-slate-400 border border-slate-700/40';
};
