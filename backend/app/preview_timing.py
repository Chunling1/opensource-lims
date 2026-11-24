"""Structured stage timings: no business identifiers, body, file paths or errors."""
from contextlib import contextmanager
import logging
import time
import uuid


class Trace:
    def __init__(self, kind):
        self.kind = kind
        self.identifier = uuid.uuid4().hex
        self.started = time.monotonic()

    @contextmanager
    def stage(self, name):
        start = time.monotonic()
        outcome = 'ok'
        try:
            yield
        except BaseException:
            outcome = 'failed'
            raise
        finally:
            logging.getLogger(__name__).info(
                'preview_stage trace=%s kind=%s stage=%s outcome=%s elapsed_ms=%.1f total_ms=%.1f',
                self.identifier, self.kind, name, outcome,
                (time.monotonic() - start) * 1000, (time.monotonic() - self.started) * 1000)
