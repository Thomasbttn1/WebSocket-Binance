import os

# Trading pairs (in exchange-normalized format)
TRADING_PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

# Kline intervals in seconds
KLINE_INTERVALS = [1, 10, 60, 300]

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey_change_in_production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24 hours

# PubSub queue max size per subscriber (drop oldest if full)
QUEUE_MAX_SIZE = 200

# Binance WebSocket URL
BINANCE_WS_URL = "wss://stream.binance.com:9443/stream"

# OKX WebSocket URL
OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"

# Reconnect settings
RECONNECT_MAX_WAIT = 60  # seconds

# Assets derived from trading pairs
def get_assets() -> list[str]:
    assets = set()
    for pair in TRADING_PAIRS:
        # All pairs end in USDT in this config
        if pair.endswith("USDT"):
            assets.add(pair[:-4])
            assets.add("USDT")
        elif pair.endswith("BTC"):
            assets.add(pair[:-3])
            assets.add("BTC")
    return sorted(assets)

ASSETS = get_assets()
