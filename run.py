import logging
import os

from am_bot import ARKBot


logger = logging.getLogger()
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
logger.propagate = True


if __name__ == "__main__":
    client = ARKBot(command_prefix="nevergoingtobeacommandthroughhere")
    client.run(os.getenv("BOT_TOKEN"))
