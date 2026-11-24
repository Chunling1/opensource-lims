"""Dedicated incremental AI index worker process."""

import os
import signal
import time

from app import create_app
from app.extensions import db
from app.functions.ai_index import incremental
from app.models import AiIndexState

running = True


def stop(_signum, _frame):
    global running
    running = False


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    app = create_app()
    if not app.config.get("AI_ENABLED"):
        app.logger.info("AI worker is disabled by AI_ENABLED=0")
        return
    interval = max(5, int(os.environ.get("AI_INDEX_INTERVAL_SECONDS", "30")))
    with app.app_context():
        while running:
            try:
                incremental(app.config.get("AI_INDEX_BATCH_SIZE", 500))
            except Exception as exc:
                db.session.rollback()
                state = db.session.get(AiIndexState, "business") or AiIndexState(key="business")
                state.last_error = str(exc)[:2000]
                db.session.add(state)
                db.session.commit()
                app.logger.exception("AI index update failed")
            deadline = time.monotonic() + interval
            while running and time.monotonic() < deadline:
                time.sleep(min(1, deadline - time.monotonic()))


if __name__ == "__main__":
    main()
