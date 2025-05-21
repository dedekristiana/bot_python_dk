import time
import requests
from binance.client import Client
import pandas as pd
import ta
from datetime import datetime

# === KONFIGURASI ===
API_KEY = 'ISI_API_KEY_BINANCE_MU'
API_SECRET = 'ISI_API_SECRET_MU'
client = Client(API_KEY, API_SECRET)

SYMBOL = 'XRPUSDT'
INTERVAL = Client.KLINE_INTERVAL_1MINUTE
ORDER_SIZE = 50
MAX_ORDERS_PER_DAY = 3
TP_MIN = 0.005
TP_MAX = 0.01
SL = 0.005
TELEGRAM_TOKEN = 'ISI_TOKEN_BOT'
CHAT_ID = 'ISI_CHAT_ID'

orders_today = 0
last_order_date = None
active_orders = []

def send_telegram(msg):
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
        data = {'chat_id': CHAT_ID, 'text': msg}
        requests.post(url, data=data)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_data():
    klines = client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=100)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_vol', 'taker_buy_quote_vol', 'ignore'
    ])
    df['close'] = pd.to_numeric(df['close'])
    df['open'] = pd.to_numeric(df['open'])
    df['high'] = pd.to_numeric(df['high'])
    df['low'] = pd.to_numeric(df['low'])
    df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    return df

def is_bullish(candle):
    return candle['close'] > candle['open']

def is_bearish(candle):
    return candle['close'] < candle['open']

def check_signal(df):
    latest = df.iloc[-1]
    rsi = latest['rsi']
    if rsi < 30 and is_bullish(latest):
        return 'BUY', latest['close']
    elif rsi > 70 and is_bearish(latest):
        return 'SELL', latest['close']
    else:
        return None, None

def simulate_order(action, price):
    global orders_today
    tp_pct = round(TP_MIN + (TP_MAX - TP_MIN) * 0.5, 4)
    sl_pct = SL
    if action == 'BUY':
        tp = price * (1 + tp_pct)
        sl = price * (1 - sl_pct)
    else:
        tp = price * (1 - tp_pct)
        sl = price * (1 + sl_pct)

    order = {
        'action': action,
        'entry_price': price,
        'tp': tp,
        'sl': sl,
        'size': ORDER_SIZE,
        'opened_at': datetime.now()
    }
    active_orders.append(order)
    orders_today += 1

    msg = (
        f"[{order['opened_at'].strftime('%Y-%m-%d %H:%M:%S')}]\n"
        f"SIMULATED {action} XRP/USDT at {price:.4f} (Amount: ${ORDER_SIZE})\n"
        f"TP set at {tp:.4f} | SL at {sl:.4f}\n"
        f"Orders today: {orders_today}/{MAX_ORDERS_PER_DAY}"
    )
    send_telegram(msg)

def check_active_orders(current_price):
    global active_orders
    closed_orders = []

    for order in active_orders:
        action = order['action']
        tp = order['tp']
        sl = order['sl']

        if action == 'BUY':
            if current_price >= tp:
                send_telegram(f"✅ TP HIT! BUY at {order['entry_price']:.4f}, TP at {current_price:.4f}")
                closed_orders.append(order)
            elif current_price <= sl:
                send_telegram(f"⚠️ SL HIT! BUY at {order['entry_price']:.4f}, SL at {current_price:.4f}")
                closed_orders.append(order)

        elif action == 'SELL':
            if current_price <= tp:
                send_telegram(f"✅ TP HIT! SELL at {order['entry_price']:.4f}, TP at {current_price:.4f}")
                closed_orders.append(order)
            elif current_price >= sl:
                send_telegram(f"⚠️ SL HIT! SELL at {order['entry_price']:.4f}, SL at {current_price:.4f}")
                closed_orders.append(order)

    for order in closed_orders:
        active_orders.remove(order)

# === LOOP UTAMA ===
send_telegram("🚀 Bot trading dimulai...")

while True:
    now = datetime.now()
    if last_order_date != now.date():
        orders_today = 0
        last_order_date = now.date()

    try:
        df = get_data()
        current_price = df.iloc[-1]['close']

        if active_orders:
            check_active_orders(current_price)

        if orders_today < MAX_ORDERS_PER_DAY and not active_orders:
            signal, price = check_signal(df)
            if signal:
                simulate_order(signal, price)
        else:
            print("Menunggu... order penuh atau masih aktif.")

    except Exception as e:
        send_telegram(f"❌ ERROR: {str(e)}")

    time.sleep(60)
