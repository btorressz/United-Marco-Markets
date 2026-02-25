import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.core.event_bus import EventBus
from backend.core.state_store import StateStore
from backend.ingest.wits_ingest import WITSIngestor
from backend.ingest.gdelt_ingest import GDELTIngestor
from backend.ingest.kraken_ingest import KrakenIngestor
from backend.ingest.coingecko_ingest import CoinGeckoIngestor
from backend.ingest.pyth_ingest import PythIngestor
from backend.ingest.drift_ingest import DriftIngestor

logger = logging.getLogger(__name__)


class IngestScheduler:

    def __init__(self, event_bus: EventBus | None = None, state_store: StateStore | None = None):
        self.event_bus = event_bus or EventBus()
        self.state_store = state_store or StateStore()
        self.scheduler = AsyncIOScheduler()

        self.wits = WITSIngestor(event_bus=self.event_bus, state_store=self.state_store)
        self.gdelt = GDELTIngestor(event_bus=self.event_bus, state_store=self.state_store)
        self.kraken = KrakenIngestor(state_store=self.state_store)
        self.coingecko = CoinGeckoIngestor(state_store=self.state_store)
        self.pyth = PythIngestor(state_store=self.state_store)
        self.drift = DriftIngestor(state_store=self.state_store)

    def schedule_all(self) -> None:
        self.scheduler.add_job(
            self._run_wits, "interval", hours=6, id="wits_ingest",
            name="WITS Tariff Ingest", replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_gdelt, "interval", minutes=5, id="gdelt_ingest",
            name="GDELT News Ingest", replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_kraken, "interval", seconds=30, id="kraken_ingest",
            name="Kraken Price Ingest", replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_coingecko, "interval", seconds=60, id="coingecko_ingest",
            name="CoinGecko Price Ingest", replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_pyth, "interval", seconds=30, id="pyth_ingest",
            name="Pyth Price Ingest", replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_drift, "interval", seconds=60, id="drift_ingest",
            name="Drift Market Ingest", replace_existing=True,
        )

        self.scheduler.start()
        logger.info("IngestScheduler started with %d jobs", len(self.scheduler.get_jobs()))

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("IngestScheduler stopped")

    async def _run_wits(self) -> None:
        try:
            await self.wits.fetch_all()
            logger.debug("WITS ingest completed")
        except Exception:
            logger.error("WITS ingest job failed", exc_info=True)

    async def _run_gdelt(self) -> None:
        try:
            await self.gdelt.fetch_articles()
            logger.debug("GDELT ingest completed")
        except Exception:
            logger.error("GDELT ingest job failed", exc_info=True)

    async def _run_kraken(self) -> None:
        try:
            await self.kraken.fetch_ticker()
            logger.debug("Kraken ingest completed")
        except Exception:
            logger.error("Kraken ingest job failed", exc_info=True)

    async def _run_coingecko(self) -> None:
        try:
            await self.coingecko.fetch_price()
            logger.debug("CoinGecko ingest completed")
        except Exception:
            logger.error("CoinGecko ingest job failed", exc_info=True)

    async def _run_pyth(self) -> None:
        try:
            await self.pyth.fetch_price()
            logger.debug("Pyth ingest completed")
        except Exception:
            logger.error("Pyth ingest job failed", exc_info=True)

    async def _run_drift(self) -> None:
        try:
            await self.drift.fetch_market_data()
            await self.drift.fetch_funding()
            logger.debug("Drift ingest completed")
        except Exception:
            logger.error("Drift ingest job failed", exc_info=True)
