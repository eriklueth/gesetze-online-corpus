"""Additional upstream sources beyond the per-fetcher root.

Currently this package only contains the NeuRIS client scaffold which
is consumed by the bund fetcher's event-detection when the
`GESETZE_NEURIS_ENABLED` env flag is set. Separating NeuRIS from the
bund fetcher folder keeps the facade of "one fetcher == one portal"
clean and allows the same client to be used later for promulgation
metadata on Landesrecht (NeuRIS scope grows over time).
"""

__all__ = ["neuris"]
