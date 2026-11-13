/**
 * Simple utility to combine CSS class names
 */
export const cn = (...classes) => {
  return classes.filter(Boolean).join(' ');
};

/**
 * Calculate pips difference
 */
export const calculatePips = (entryPrice, currentPrice, symbol = 'XAUUSD') => {
  if (!entryPrice || !currentPrice) return 0;
  const diff = currentPrice - entryPrice;
  if (symbol.toUpperCase().includes('XAU')) {
    // For Gold, 0.10 is 1 pip or 0.01 is 1 point
    return +(diff / 0.1).toFixed(1);
  }
  if (symbol.toUpperCase().includes('JPY')) {
    return +(diff / 0.01).toFixed(1);
  }
  return +(diff / 0.0001).toFixed(1);
};

/**
 * Truncate long hashes/ids
 */
export const truncateId = (id, len = 8) => {
  if (!id) return '';
  if (id.length <= len) return id;
  return `${id.substring(0, len)}...`;
};

/**
 * Debounce helper
 */
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

/**
 * Safe JSON parser with fallback
 */
export const safeJsonParse = (str, fallback = {}) => {
  try {
    return JSON.parse(str);
  } catch (e) {
    return fallback;
  }
};
