import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth.router import router as auth_router
from market.aggregator import MarketAggregator
from market.connectors.binance import BinanceConnector
from market.connectors.okx import OKXConnector
from pubsub.broker import PubSubBroker
from trading.engine import PaperTradingEngine
from trading.router import router as trading_router
from ws.router import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    broker = PubSubBroker()
    aggregator = MarketAggregator(broker)
    trading_engine = PaperTradingEngine(broker)

    binance = BinanceConnector(aggregator)
    okx = OKXConnector(aggregator)

    tasks = [
        asyncio.create_task(binance.connect(), name="binance-connector"),
        asyncio.create_task(okx.connect(), name="okx-connector"),
        asyncio.create_task(
            trading_engine.run_matcher(aggregator), name="order-matcher"
        ),
    ]

    app.state.broker = broker
    app.state.aggregator = aggregator
    app.state.trading_engine = trading_engine

    logger.info("Server started — connecting to exchanges")
    yield

    logger.info("Shutting down — cancelling background tasks")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Shutdown complete")


app = FastAPI(
    title="Market Data Router & Paper Trading API",
    description=(
        "Aggregates real-time market data from Binance and OKX "
        "and exposes unified streams and a paper trading engine."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(trading_router)
app.include_router(ws_router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(Path("static") / "index.html")
