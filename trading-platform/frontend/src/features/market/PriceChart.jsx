import React, { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';

export const PriceChart = ({
  symbol = 'XAUUSD',
  candles = [],
  timeframe = 'M15',
  height = 520,
  showIndicators = true
}) => {
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const isGold = symbol.toUpperCase().includes('XAU');

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#090d16' },
        textColor: '#94a3b8',
        fontSize: 12
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
        horzLines: { color: 'rgba(30, 41, 59, 0.5)' }
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
      timeScale: {
        borderColor: 'rgba(51, 65, 85, 0.6)',
        timeVisible: true,
        secondsVisible: false
      },
      rightPriceScale: {
        borderColor: 'rgba(51, 65, 85, 0.6)',
        scaleMargins: { top: 0.1, bottom: 0.2 }
      },
      crosshair: {
        vertLine: {
          color: '#38bdf8',
          width: 1,
          style: 3,
          labelBackgroundColor: '#0284c7'
        },
        horzLine: {
          color: '#38bdf8',
          width: 1,
          style: 3,
          labelBackgroundColor: '#0284c7'
        }
      }
    });

    chartInstanceRef.current = chart;

    // Candlestick Series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderUpColor: '#10b981',
      borderDownColor: '#ef4444',
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444',
      priceFormat: {
        type: 'price',
        precision: isGold ? 2 : 5,
        minMove: isGold ? 0.01 : 0.00001
      }
    });

    // Volume Series
    const volumeSeries = chart.addHistogramSeries({
      color: '#38bdf8',
      priceFormat: { type: 'volume' },
      priceScaleId: '', // overlay
      scaleMargins: { top: 0.82, bottom: 0 }
    });

    // EMA 20 Overlay Line
    let emaSeries = null;
    if (showIndicators) {
      emaSeries = chart.addLineSeries({
        color: '#f59e0b',
        lineWidth: 2,
        title: 'EMA 20',
        priceScaleId: 'right'
      });
    }

    if (candles && candles.length > 0) {
      const sortedCandles = [...candles].sort((a, b) => a.time - b.time);
      candleSeries.setData(sortedCandles);

      const volumeData = sortedCandles.map((c) => ({
        time: c.time,
        value: c.volume || Math.floor(Math.random() * 800 + 100),
        color: c.close >= c.open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'
      }));
      volumeSeries.setData(volumeData);

      // Simple EMA calculation
      if (emaSeries && sortedCandles.length > 20) {
        const k = 2 / (20 + 1);
        let ema = sortedCandles[0].close;
        const emaData = sortedCandles.map((c) => {
          ema = c.close * k + ema * (1 - k);
          return { time: c.time, value: +ema.toFixed(isGold ? 2 : 5) };
        });
        emaSeries.setData(emaData);
      }
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartContainerRef.current && chartInstanceRef.current) {
        chartInstanceRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [symbol, candles, timeframe, height, showIndicators]);

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-slate-800 bg-[#090d16]">
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
};

export default PriceChart;
