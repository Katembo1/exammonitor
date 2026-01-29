"""Application entry point for running the Exam Monitor server."""

import os

from app import create_app, socketio

app = create_app()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    socketio.run(app, host=host, port=port, debug=debug)
