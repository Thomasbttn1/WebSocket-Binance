# Market Data Router & Paper Trading API

A FastAPI server that aggregates real-time cryptocurrency market data from **Binance** and **OKX** and exposes unified WebSocket streams alongside a paper trading engine.

---

## Features

- **Live order book** (top-of-book) from both exchanges for 5 pairs
- **Best touch** — best bid/ask across exchanges with source attribution
- **Trade stream** — real-time trade feed per symbol and exchange
- **Live klines** — 1s, 10s, 1m, 5m candlesticks built from raw trades (no REST APIs used)
- **EWMA** — per-subscription exponential weighted moving average with configurable half-life
- **JWT authentication** — register, login, secure endpoints
- **Paper trading** — deposit, limit orders, balance management, automatic order matching

---

## Setup

### Requirements

Python 3.12+ recommended.

```bash
pip install -r requirements.txt
```

### Running the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The server connects to Binance and OKX WebSocket feeds on startup.

### Swagger UI

Open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

---

## Configuration

Edit `config.py` to change:

| Setting | Default | Description |
|---|---|---|
| `TRADING_PAIRS` | 5 pairs | Symbols to subscribe to |
| `KLINE_INTERVALS` | `[1, 10, 60, 300]` | Candle intervals in seconds |
| `JWT_SECRET` | env `JWT_SECRET` | Secret key for token signing |
| `QUEUE_MAX_SIZE` | `200` | Per-subscriber message buffer |
| `RECONNECT_MAX_WAIT` | `60` | Max reconnect backoff (seconds) |

---

## REST API Reference

### Public

| Method | Path | Description |
|---|---|---|
| `POST` | `/register` | Create account |
| `POST` | `/login` | Get JWT token |
| `GET` | `/info` | List assets and trading pairs |

### Authenticated (Bearer token required)

| Method | Path | Description |
|---|---|---|
| `POST` | `/deposit` | Deposit funds |
| `GET` | `/balance` | Get total and available balances |
| `POST` | `/orders` | Place a limit order |
| `GET` | `/orders/{token_id}` | Get order status |
| `DELETE` | `/orders/{token_id}` | Cancel an open order |

#### Register
```json
POST /register
{ "username": "alice", "password": "secret" }
```

#### Login
```json
POST /login
{ "username": "alice", "password": "secret" }
→ { "access_token": "<jwt>", "token_type": "bearer" }
```

#### Deposit
```json
POST /deposit
Authorization: Bearer <token>
{ "asset": "USDT", "amount": 10000 }
```

#### Place order
```json
POST /orders
Authorization: Bearer <token>
{
  "token_id": "my-unique-order-id",
  "symbol": "BTCUSDT",
  "side": "buy",
  "price": 50000.0,
  "quantity": 0.1
}
```

Order execution: a buy order fills when `best_ask <= limit_price`; a sell order fills when `best_bid >= limit_price`.

---

## WebSocket API

Connect to `ws://localhost:8000/ws?token=<jwt>`

### Subscribe to best touch
```json
{
  "action": "subscribe",
  "stream": "best_touch",
  "symbol": "BTCUSDT",
  "exchange": "all"
}
```

### Subscribe to trades
```json
{
  "action": "subscribe",
  "stream": "trades",
  "symbol": "ETHUSDT",
  "exchange": "binance"
}
```

### Subscribe to klines
```json
{
  "action": "subscribe",
  "stream": "klines",
  "symbol": "SOLUSDT",
  "interval": "1m",
  "exchange": "okx"
}
```
Valid intervals: `1s`, `10s`, `1m`, `5m`

### Subscribe to EWMA
```json
{
  "action": "subscribe",
  "stream": "ewma",
  "symbol": "BTCUSDT",
  "half_life": 30,
  "exchange": "all"
}
```
`half_life` is in seconds. The EWMA is computed from live trade prices starting from subscription time.

### Exchange filter
- `all` — merged data from both exchanges
- `binance` — Binance only
- `okx` — OKX only

### Response format
```json
{
  "topic": "BTCUSDT.best_touch",
  "data": {
    "symbol": "BTCUSDT",
    "best_bid": 96500.0,
    "best_bid_qty": 0.5,
    "best_bid_exchange": "binance",
    "best_ask": 96502.0,
    "best_ask_qty": 0.3,
    "best_ask_exchange": "okx",
    "timestamp": 1710000000.123
  }
}
```

---

## Client Example

```bash
pip install httpx websockets
python client_example.py
```

Demonstrates: registration, login, deposits, order placement, cancellation, balance, and all WebSocket stream types.

---

## Project Structure

```
├── main.py                  # FastAPI app + lifespan (connector startup)
├── config.py                # Constants and trading pair configuration
├── dependencies.py          # FastAPI dependency injectors
├── requirements.txt
├── client_example.py        # Demo client
│
├── auth/
│   ├── models.py            # User Pydantic models
│   ├── store.py             # In-memory user store
│   ├── service.py           # Password hashing, JWT
│   └── router.py            # /register, /login endpoints
│
├── market/
│   ├── models.py            # Trade, OrderBook, Kline, EWMA models
│   ├── aggregator.py        # Central state hub
│   ├── order_book.py        # OrderBook with merge logic
│   ├── kline_builder.py     # OHLCV candle builder
│   ├── ewma.py              # EWMA calculator
│   └── connectors/
│       ├── base.py          # Reconnect loop base class
│       ├── binance.py       # Binance WS connector
│       └── okx.py           # OKX WS connector
│
├── pubsub/
│   └── broker.py            # Topic-based asyncio fan-out broker
│
├── trading/
│   ├── models.py            # Order, Balance models
│   ├── engine.py            # Paper trading engine + order matcher
│   └── router.py            # /deposit, /orders, /balance endpoints
│
└── ws/
    └── router.py            # /ws WebSocket endpoint
```

---

## Authors

- **Thomas Betton** — thomas.betton@edu.devinci.fr
- ** Lou Girault ** — lou.girault@edu.devinci.fr