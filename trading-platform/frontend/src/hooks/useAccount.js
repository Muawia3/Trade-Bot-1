import { useTradingContext } from '../context/TradingContext';

export const useAccount = () => {
  const {
    account,
    tradingMode,
    switchMode,
    connections,
    riskMetrics,
    loading,
    error,
    refresh
  } = useTradingContext();

  return {
    account,
    tradingMode,
    switchMode,
    connections,
    riskMetrics,
    loading,
    error,
    refresh
  };
};

export default useAccount;
