#!/usr/bin/env python3
"""Kombinierter Cron-Worker: Persons + Deals Delta-Sync alle 15 Minuten."""

import asyncio
import logging
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

INTERVAL_SECONDS = int(os.getenv("CRON_INTERVAL", "900"))  # 15 Min


def run_sync():
    """Führt beide Cron-Syncs nacheinander aus."""
    from cron_persons import main as sync_persons
    from cron_deals import main as sync_deals

    log.info("=== Persons Sync ===")
    try:
        asyncio.run(sync_persons())
    except Exception as exc:
        log.error("Persons Sync fehlgeschlagen: %s", exc, exc_info=True)

    log.info("=== Deals Sync ===")
    try:
        asyncio.run(sync_deals())
    except Exception as exc:
        log.error("Deals Sync fehlgeschlagen: %s", exc, exc_info=True)


if __name__ == "__main__":
    log.info("Cron-Worker gestartet. Intervall: %ds", INTERVAL_SECONDS)
    while True:
        try:
            run_sync()
        except Exception as exc:
            log.error("Sync-Zyklus fehlgeschlagen: %s", exc, exc_info=True)
        log.info("Nächster Sync in %ds", INTERVAL_SECONDS)
        time.sleep(INTERVAL_SECONDS)
