"""Event detection and backdated commit pipeline.

Phase C v1 uses ``stand_datum`` from each law's ``meta.json`` as
effective_date approximation. Phase C v2 will add recht.bund.de events
for per-paragraph accuracy.
"""

from .commit import commit_event_groups
from .detect import detect_event_groups
from .schema import AffectedLaw, DetectedEventGroup
from .writer import write_event

__all__ = [
    "AffectedLaw",
    "DetectedEventGroup",
    "commit_event_groups",
    "detect_event_groups",
    "write_event",
]
