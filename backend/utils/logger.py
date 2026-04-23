"""
Structured logging setup
"""
import logging
import sys


def setup_logger(level: str = "INFO"):
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers = [handler]

    # Quiet noisy libs
    for lib in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(lib).setLevel(logging.WARNING)
