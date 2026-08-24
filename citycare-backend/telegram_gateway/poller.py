"""Standalone long-polling process for local development."""

import asyncio
import signal
import sys
from typing import Optional

from app.core.config import get_settings
from app.core.database import close_mongo_connection, connect_to_mongo, ensure_indexes
from telegram_gateway.adapter import TelegramAdapter
from telegram_gateway.router import TelegramRouter
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramPoller:
    """Long polling runner for development environments."""

    def __init__(self):
        self.settings = get_settings()
        self.adapter = TelegramAdapter()
        self.router = TelegramRouter(adapter=self.adapter)
        self.running = False
        self.offset: Optional[int] = None

    async def start(self) -> None:
        if not self.settings.telegram_bot_token:
            logger.error("Cannot start polling: TELEGRAM_BOT_TOKEN is not configured.")
            sys.exit(1)

        logger.info("Initializing database connection for Telegram poller...")
        await connect_to_mongo()
        await ensure_indexes()

        # Delete any active webhook to allow polling
        logger.info("Removing any active webhook before starting polling...")
        await self.adapter.delete_webhook()

        self.running = True
        logger.info("Telegram Patient Assistant poller started successfully. Listening for updates...")

        while self.running:
            try:
                updates_resp = await self.adapter.get_updates(offset=self.offset, timeout=20)
                if not updates_resp.get("ok"):
                    logger.warning("Poller getUpdates returned error: %s", updates_resp.get("description"))
                    await asyncio.sleep(2)
                    continue

                updates = updates_resp.get("result", [])
                for update in updates:
                    update_id = update.get("update_id")
                    if update_id:
                        self.offset = update_id + 1
                    await self.router.process_update(update)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Unexpected error in Telegram polling loop: %s", exc, exc_info=True)
                await asyncio.sleep(3)

        logger.info("Poller loop ended.")
        await close_mongo_connection()

    def stop(self) -> None:
        logger.info("Stopping Telegram poller...")
        self.running = False


async def main():
    poller = TelegramPoller()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, poller.stop)
        except NotImplementedError:
            # Signal handlers not implemented on Windows event loop
            pass

    try:
        await poller.start()
    except (KeyboardInterrupt, SystemExit):
        poller.stop()


if __name__ == "__main__":
    asyncio.run(main())
