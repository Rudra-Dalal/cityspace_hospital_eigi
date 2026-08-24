"""Top-level entrypoint for running the Telegram Patient Assistant poller."""

import asyncio
from telegram_gateway.poller import main

if __name__ == "__main__":
    asyncio.run(main())
