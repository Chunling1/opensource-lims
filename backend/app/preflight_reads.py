"""Ephemeral read reuse inside one synchronous, read-only preflight.

Never a process/request-wide authorization cache. Every invocation starts fresh,
including nested invocations; exceptions reset the context in finally. No ORM
session or transaction ownership is changed. Other callers execute normally.
"""
from contextvars import ContextVar
from functools import wraps

_reads = ContextVar('compliance_preflight_reads', default=None)


def reuse_preflight_reads(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        token = _reads.set({})
        try:
            return function(*args, **kwargs)
        finally:
            _reads.reset(token)
    return wrapped


def read_once(key, loader):
    reads = _reads.get()
    if reads is None:
        return loader()
    if key not in reads:
        reads[key] = loader()
    return reads[key]


def reuse_existing_preflight_reads(function):
    """Read-only inner calculation: retain an enclosing invocation or isolate one."""
    isolated = reuse_preflight_reads(function)
    @wraps(function)
    def wrapped(*args, **kwargs):
        if _reads.get() is not None:
            return function(*args, **kwargs)
        return isolated(*args, **kwargs)
    return wrapped
