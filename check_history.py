import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

if not mt5.initialize():
    print("Failed to init MT5:", mt5.last_error())
    exit()

account = mt5.account_info()
print(f"Account: {account.login} | Server: {account.server} | Balance: ${account.balance:.2f} | Equity: ${account.equity:.2f}")

from_date = datetime.now() - timedelta(days=20)
to_date = datetime.now() + timedelta(days=2)

deals = mt5.history_deals_get(from_date, to_date)
if deals is None or len(deals) == 0:
    print("No deals found in history.")
else:
    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df["time"] = pd.to_datetime(df["time"], unit="s")
    cols = ["ticket", "order", "time", "symbol", "type", "entry", "volume", "price", "profit", "comment"]
    avail_cols = [c for c in cols if c in df.columns]
    print("\n=== RECENT DEALS (OUT / CLOSES) ===")
    closed = df[df["entry"] == 1].copy()
    if len(closed) > 0:
        print(closed[avail_cols].to_string())
        total_profit = closed["profit"].sum()
        wins = closed[closed["profit"] > 0]
        losses = closed[closed["profit"] < 0]
        zeros = closed[closed["profit"] == 0]
        print("\n=== PERFORMANCE STATS ===")
        print(f"Total Closed Trades: {len(closed)}")
        print(f"Total Net P/L: ${total_profit:.2f}")
        if len(wins) > 0:
            print(f"Wins: {len(wins)} ({len(wins)/len(closed)*100:.1f}%) | Total Win: ${wins['profit'].sum():.2f} | Avg Win: ${wins['profit'].mean():.2f} | Max Win: ${wins['profit'].max():.2f}")
        if len(losses) > 0:
            print(f"Losses: {len(losses)} ({len(losses)/len(closed)*100:.1f}%) | Total Loss: ${losses['profit'].sum():.2f} | Avg Loss: ${losses['profit'].mean():.2f} | Max Loss: ${losses['profit'].min():.2f}")
        print(f"Breakeven/Zero trades: {len(zeros)}")
    else:
        print("No closed deals yet.")

print("\n=== CURRENT OPEN POSITIONS ===")
positions = mt5.positions_get()
if positions:
    pdf = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
    cols = ["ticket", "time", "symbol", "type", "volume", "price_open", "sl", "tp", "profit", "comment"]
    avail = [c for c in cols if c in pdf.columns]
    print(pdf[avail].to_string())
else:
    print("No open positions.")

mt5.shutdown()
