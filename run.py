"""Application entry point for running the Exam Monitor server.

Logging configuration is provided by the :mod:`app` package.
"""

import os
import logging

from app import create_app, socketio


if __name__ == "__main__":
    app = create_app()
    logger = logging.getLogger(__name__)

    host = os.getenv("HOST", "127.0.0.1")
    debug = os.getenv("DEBUG", "false").lower() == "true"

    port_env = os.getenv("PORT", "5000")
    try:
        port = int(port_env)
    except ValueError:
        logger.warning("Invalid PORT '%s', falling back to 5000", port_env)
        port = 5000

    if host == "0.0.0.0":
        logger.warning("Binding to all interfaces (0.0.0.0); set HOST=127.0.0.1 for local-only.")

    logger.info("Starting Exam Monitor server on %s:%s (debug=%s)", host, port, debug)
    socketio.run(app, host=host, port=port, debug=debug)
