import logging

from .bot import ARKBot


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__version__ = "0.0.1"
