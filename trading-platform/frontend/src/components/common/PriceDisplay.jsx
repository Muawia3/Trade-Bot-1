import React, { useState, useEffect, useRef } from 'react';
import { formatPrice } from '../../utils/formatters';

export const PriceDisplay = ({
  price,
  symbol = 'XAUUSD',
  size = 'md',
  showChange = false,
  change = 0,
  className = ''
}) => {
  const [flash, setFlash] = useState(null); // 'up' | 'down' | null
  const prevPriceRef = useRef(price);

  useEffect(() => {
    if (prevPriceRef.current !== undefined && price !== prevPriceRef.current) {
      if (price > prevPriceRef.current) {
        setFlash('up');
      } else if (price < prevPriceRef.current) {
        setFlash('down');
      }
      prevPriceRef.current = price;

      const timer = setTimeout(() => setFlash(null), 800);
      return () => clearTimeout(timer);
    }
  }, [price]);

  const sizeClasses = {
    sm: 'text-sm font-semibold',
    md: 'text-base font-bold',
    lg: 'text-2xl font-black tracking-tight',
    xl: 'text-3xl font-extrabold tracking-tight'
  };

  const flashClasses = {
    up: 'text-emerald-400 bg-emerald-500/10 px-1 rounded transition-colors duration-300',
    down: 'text-rose-400 bg-rose-500/10 px-1 rounded transition-colors duration-300',
    null: 'text-slate-100 transition-colors duration-500'
  };

  return (
    <div className={`inline-flex items-center gap-2 font-mono ${className}`}>
      <span className={`${sizeClasses[size] || sizeClasses.md} ${flashClasses[flash] || flashClasses.null}`}>
        {formatPrice(price, symbol)}
      </span>
      {showChange && (
        <span
          className={`text-xs px-1.5 py-0.5 rounded font-mono font-medium ${
            change >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
          }`}
        >
          {change >= 0 ? `+${change}%` : `${change}%`}
        </span>
      )}
    </div>
  );
};

export default PriceDisplay;
