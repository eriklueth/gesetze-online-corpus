"""Event scaffold.

Not wired in yet. The schema is stable (see docs/SCHEMA.md) and the
writer is usable once an event source (recht.bund.de / Buzer HTML) is
plugged in.
"""

from .writer import write_event

__all__ = ["write_event"]
