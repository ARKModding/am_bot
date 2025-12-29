import os

from am_bot import ARKBot
from am_bot.logging_config import setup_logging


setup_logging()


if __name__ == "__main__":
    client = ARKBot(command_prefix="nevergoingtobeacommandthroughhere")
    client.run(os.getenv("BOT_TOKEN"))
