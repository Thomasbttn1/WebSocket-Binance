"""
Client example demonstrating all features of the Market Data Router API.

Run the server first:
    uvicorn main:app --host 0.0.0.0 --port 8000

Then run this script:
    python client_example.py
"""

import asyncio
import json
import uuid

import websockets
import httpx

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────

def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# ──────────────────────────────────────────────
# REST demo
# ──────────────────────────────────────────────

async def rest_demo(client: httpx.AsyncClient) -> str:
    username = f"trader_{uuid.uuid4().hex[:6]}"
    password = "password123"

    print_section("1. Registration")
    r = await client.post("/register", json={"username": username, "password": password})
    print(f"  POST /register → {r.status_code}: {r.json()}")
    assert r.status_code == 201, r.text

    print_section("2. Login")
    r = await client.post("/login", json={"username": username, "password": password})
    print(f"  POST /login → {r.status_code}")
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print_section("3. /info — available assets and pairs")
    r = await client.get("/info")
    print(f"  GET /info → {r.json()}")

    print_section("4. Deposit funds")
    r = await client.post(
        "/deposit", json={"asset": "USDT", "amount": 10000}, headers=headers
    )
    print(f"  POST /deposit → {r.status_code}: {r.json()}")

    print_section("5. Get balance")
    r = await client.get("/balance", headers=headers)
    print(f"  GET /balance → {r.json()}")

    print_section("6. Place a limit buy order")
    token_id = f"order_{uuid.uuid4().hex[:8]}"
    r = await client.post(
        "/orders",
        json={
            "token_id": token_id,
            "symbol": "BTCUSDT",
            "side": "buy",
            "price": 50000.0,
            "quantity": 0.01,
        },
        headers=headers,
    )
    print(f"  POST /orders → {r.status_code}: {r.json()}")
    assert r.status_code == 201, r.text

    print_section("7. Get order status")
    r = await client.get(f"/orders/{token_id}", headers=headers)
    print(f"  GET /orders/{token_id} → {r.json()}")

    print_section("8. Balance after order reservation")
    r = await client.get("/balance", headers=headers)
    data = r.json()
    print(f"  Available USDT: {data['available']['USDT']:.2f}  (500 reserved)")
    print(f"  Total USDT:     {data['total']['USDT']:.2f}")

    print_section("9. Cancel the order")
    r = await client.delete(f"/orders/{token_id}", headers=headers)
    print(f"  DELETE /orders/{token_id} → {r.status_code}: {r.json()}")

    print_section("10. Balance after cancellation (reserved released)")
    r = await client.get("/balance", headers=headers)
    data = r.json()
    print(f"  Available USDT: {data['available']['USDT']:.2f}  (should be 10000)")

    print_section("11. Malformed order — should be rejected")
    r = await client.post(
        "/orders",
        json={
            "token_id": "bad_order",
            "symbol": "FAKEPAIR",
            "side": "buy",
            "price": -100,
            "quantity": 0.01,
        },
        headers=headers,
    )
    print(f"  POST /orders (bad symbol) → {r.status_code}: {r.json()['detail']}")

    return token


# ──────────────────────────────────────────────
# WebSocket demo
# ──────────────────────────────────────────────

async def ws_demo(token: str) -> None:
    print_section("12. WebSocket subscriptions")
    url = f"{WS_URL}?token={token}"

    try:
        async with websockets.connect(url) as ws:
            # Subscribe to all stream types
            subscriptions = [
                {
                    "action": "subscribe",
                    "stream": "best_touch",
                    "symbol": "BTCUSDT",
                    "exchange": "all",
                },
                {
                    "action": "subscribe",
                    "stream": "trades",
                    "symbol": "ETHUSDT",
                    "exchange": "binance",
                },
                {
                    "action": "subscribe",
                    "stream": "klines",
                    "symbol": "SOLUSDT",
                    "interval": "1m",
                    "exchange": "all",
                },
                {
                    "action": "subscribe",
                    "stream": "ewma",
                    "symbol": "BTCUSDT",
                    "half_life": 30,
                    "exchange": "all",
                },
            ]

            for sub in subscriptions:
                await ws.send(json.dumps(sub))
                print(f"  Subscribed: {sub['stream']} {sub.get('symbol')} [{sub.get('exchange')}]")

            print("\n  Receiving 15 messages (Ctrl+C to stop early)...")
            count = 0
            try:
                async with asyncio.timeout(30):
                    async for raw in ws:
                        msg = json.loads(raw)
                        topic = msg.get("topic", "")
                        data = msg.get("data", {})

                        if "best_touch" in topic:
                            print(
                                f"  [{topic}] bid={data.get('best_bid')} "
                                f"({data.get('best_bid_exchange')}) | "
                                f"ask={data.get('best_ask')} ({data.get('best_ask_exchange')})"
                            )
                        elif "trades" in topic:
                            print(
                                f"  [{topic}] price={data.get('price')} qty={data.get('quantity')}"
                            )
                        elif "klines" in topic:
                            print(
                                f"  [{topic}] O={data.get('open')} H={data.get('high')} "
                                f"L={data.get('low')} C={data.get('close')} "
                                f"closed={data.get('is_closed')}"
                            )
                        elif "ewma" in topic:
                            print(
                                f"  [{topic}] ewma={data.get('value'):.2f} "
                                f"(half_life={data.get('half_life')}s)"
                            )

                        count += 1
                        if count >= 15:
                            break
            except TimeoutError:
                print("  (timeout — no data received within 30s, is the server running?)")
    except Exception as exc:
        print(f"  WebSocket error: {exc}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

async def main():
    print("Market Data Router — Client Demo")
    print("Make sure the server is running: uvicorn main:app --port 8000")

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        token = await rest_demo(client)

    await ws_demo(token)

    print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(main())
