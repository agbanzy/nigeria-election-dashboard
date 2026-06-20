"""Flask app factory for the pan-Nigeria election dashboard."""

from __future__ import annotations

import logging
import os

from flask import Flask
from flask_cors import CORS

from app.config import Config


def create_app(config: Config | None = None) -> Flask:
    cfg = config or Config.from_env()
    app = Flask(__name__)
    app.config.from_object(cfg)

    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    CORS(app, resources={r"/api/*": {"origins": cfg.cors_origins}})

    # Initialize DB engine lazily so importing the app for tests doesn't connect.
    from app.db import init_engine

    init_engine(cfg.database_url)

    # Register blueprints.
    from app.api import (
        admin as admin_api,
        analysis as analysis_api,
        auth as auth_api,
        calendar as calendar_api,
        candidates,
        elections,
        health,
        live,
        methodology,
        overview,
        results,
        scrape,
        states,
        sync as sync_api,
    )

    app.register_blueprint(admin_api.bp)
    app.register_blueprint(auth_api.bp)
    app.register_blueprint(health.bp)
    app.register_blueprint(overview.bp)
    app.register_blueprint(calendar_api.bp)
    app.register_blueprint(states.bp)
    app.register_blueprint(elections.bp)
    app.register_blueprint(candidates.bp)
    app.register_blueprint(results.bp)
    app.register_blueprint(analysis_api.bp)
    app.register_blueprint(scrape.bp)
    app.register_blueprint(methodology.bp)
    app.register_blueprint(live.bp)
    app.register_blueprint(sync_api.bp)

    return app
