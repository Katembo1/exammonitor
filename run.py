"""Application entry point for running the Exam Monitor server."""

import os
import logging

from app import create_app, socketio

app = create_app()


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "false").lower() == "true"

    port_env = os.getenv("PORT", "5000")
    try:
        port = int(port_env)
    except ValueError:
        logger.warning("Invalid PORT '%s', falling back to 5000", port_env)
        port = 5000

    logger.info("Starting Exam Monitor server on %s:%s (debug=%s)", host, port, debug)
    socketio.run(app, host=host, port=port, debug=debug)
