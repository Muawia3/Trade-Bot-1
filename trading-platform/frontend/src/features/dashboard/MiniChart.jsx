import React, { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import PriceDisplay from '../../components/common/PriceDisplay';

export const MiniChart = ({ symbol = 'XAUUSD', data = [], height = 180, price, change }) => {
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const isGold = symbol.toUpperCase().includes('XAU');
    const isUp = (change || 0) >= 0;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#64748b'
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: 'rgba(30, 41, 59, 0.4)', style: 2 }
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
      timeScale: {
        visible: false,
        borderVisible: false
      },
      rightPriceScale: {
        visible: true,
        borderVisible: false,
        scaleMargins: { top: 0.1, bottom: 0.1 }
      },
      crosshair: {
        vertLine: { visible: false },
        horzLine: { visible: false }
      },
      handleScroll: false,
      handleScale: false
    });

    chartInstanceRef.current = chart;

    const areaSeries = chart.addAreaSeries({
      topColor: isUp ? 'rgba(16, 185, 129, 0.28)' : 'rgba(239, 68, 68, 0.28)',
      bottomColor: 'rgba(15, 23, 42, 0.0)',
      lineColor: isUp ? '#10b981' : '#ef4444',
      lineWidth: 2,
      priceFormat: {
        type: 'price',
        precision: isGold ? 2 : 5,
        minMove: isGold ? 0.01 : 0.00001
      }
    });

    // Generate mock or formatted line data if empty
    let chartData = [];
    if (data && data.length > 0) {
      chartData = data.map((d) => ({
        time: typeof d.time === 'number' ? d.time : Math.floor(new Date(d.time).getTime() / 1000),
        value: d.close || d.value || 0
      }));
    } else {
      let base = isGold ? 2645 : 1.084;
      const now = Math.floor(Date.now() / 1000);
      for (let i = 40; i >= 0; i--) {
        base += (Math.random() - 0.48) * (isGold ? 1.5 : 0.0005);
        chartData.push({
          time: now - i * 300,
          value: +base.toFixed(isGold ? 2 : 5)
        });
      }
    }

    areaSeries.setData(chartData);
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
  }, [symbol, data, height, change]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-slate-100">{symbol}</span>
          <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
            M15
          </span>
        </div>
        <PriceDisplay
          price={price || (symbol === 'XAUUSD' ? 2650.60 : 1.08456)}
          symbol={symbol}
          size="sm"
          showChange
          change={change || 0.42}
        />
      </div>
      <div ref={chartContainerRef} className="w-full flex-1" />
    </div>
  );
};

export default MiniChart;
