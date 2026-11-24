"""Stable platform-kernel entry points.

The first modularisation phase keeps all legacy implementations in place and
exposes them through small compatibility facades.  Business modules may move
to these imports incrementally without changing database ownership, routes or
workflow behaviour.
"""

__all__ = ["audit", "file_vault", "identity", "numbering", "workflow"]
