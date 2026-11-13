import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { TradingProvider } from './context/TradingContext';
import { WebSocketProvider } from './context/WebSocketContext';
import MainLayout from './layouts/MainLayout';

// Pages
import DashboardPage from './pages/DashboardPage';
import MarketPage from './pages/MarketPage';
import TradingPage from './pages/TradingPage';
import StrategiesPage from './pages/StrategiesPage';
import PortfolioPage from './pages/PortfolioPage';
import AnalyticsPage from './pages/AnalyticsPage';
import BacktestPage from './pages/BacktestPage';
import RiskPage from './pages/RiskPage';
import SettingsPage from './pages/SettingsPage';

export const App = () => {
  return (
    <ThemeProvider>
      <WebSocketProvider>
        <TradingProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<MainLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="market" element={<MarketPage />} />
                <Route path="trading" element={<TradingPage />} />
                <Route path="strategies" element={<StrategiesPage />} />
                <Route path="portfolio" element={<PortfolioPage />} />
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="backtest" element={<BacktestPage />} />
                <Route path="risk" element={<RiskPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </TradingProvider>
      </WebSocketProvider>
    </ThemeProvider>
  );
};

export default App;
