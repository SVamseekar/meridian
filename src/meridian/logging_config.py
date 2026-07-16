import logging


def configure_logging() -> None:
    """Plain stdlib logging; RequestLoggingMiddleware emits its own
    JSON-formatted message string per record, so no JSON formatter
    is required at the handler level (see deployment.md §4)."""
    logging.basicConfig(level=logging.INFO)
