import subprocess
import os
import shutil
import time

if shutil.which("redis-server"):
    try:
        subprocess.run(
            ["redis-server", "--daemonize", "yes", "--loglevel", "warning"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        time.sleep(0.5)
    except Exception:
        pass

from backend.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def create_app():
    from pathlib import Path
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    @asynccontextmanager
    async def lifespan(application):
        from backend.data.db import init_db
        try:
            init_db()
            logger.info("Database migrations applied")
        except Exception as exc:
            logger.warning("Database migration failed (non-fatal): %s", exc)

        from backend.ingest.scheduler import IngestScheduler
        scheduler = IngestScheduler()
        try:
            scheduler.schedule_all()
            logger.info("Ingest scheduler started")
        except Exception as exc:
            logger.warning("Scheduler start failed (non-fatal): %s", exc)

        yield

        try:
            scheduler.stop()
        except Exception:
            pass

    app = FastAPI(title="Tariff Risk Desk", version="0.1.0", lifespan=lifespan)

    frontend_dir = Path(__file__).parent / "frontend"
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir)), name="frontend")

    from backend.api.index_routes import router as index_router
    from backend.api.markets_routes import router as markets_router
    from backend.api.divergence_routes import router as divergence_router
    from backend.api.rules_routes import router as rules_router
    from backend.api.execution_routes import router as execution_router
    from backend.api.risk_routes import router as risk_router
    from backend.api.events_routes import router as events_router
    from backend.api.health_routes import router as health_router
    from backend.api.ws_routes import router as ws_router
    from backend.api.stablecoin_routes import router as stablecoin_router
    from backend.api.predict_routes import router as predict_router
    from backend.api.montecarlo_routes import router as montecarlo_router
    from backend.api.yield_routes import router as yield_router
    from backend.api.microstructure_routes import router as microstructure_router
    from backend.api.agents_routes import router as agents_router
    from backend.api.metrics_routes import router as metrics_router
    from backend.api.solana_routes import router as solana_router
    from backend.api.funding_arb_routes import router as funding_arb_router
    from backend.api.basis_routes import router as basis_router
    from backend.api.stable_flow_routes import router as stable_flow_router
    from backend.api.portfolio_routes import router as portfolio_router
    from backend.api.liquidation_routes import router as liquidation_router

    app.include_router(index_router)
    app.include_router(markets_router)
    app.include_router(divergence_router)
    app.include_router(rules_router)
    app.include_router(execution_router)
    app.include_router(risk_router)
    app.include_router(events_router)
    app.include_router(health_router)
    app.include_router(ws_router)
    app.include_router(stablecoin_router)
    app.include_router(predict_router)
    app.include_router(montecarlo_router)
    app.include_router(yield_router)
    app.include_router(microstructure_router)
    app.include_router(agents_router)
    app.include_router(metrics_router)
    app.include_router(solana_router)
    app.include_router(funding_arb_router)
    app.include_router(basis_router)
    app.include_router(stable_flow_router)
    app.include_router(portfolio_router)
    app.include_router(liquidation_router)

    @app.get("/")
    def root():
        return FileResponse(str(frontend_dir / "index.html"), headers={"Cache-Control": "no-cache"})

    logger.info("Tariff Risk Desk API initialized with all routes")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
