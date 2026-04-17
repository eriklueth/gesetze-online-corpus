from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AffectedLaw:
    bjnr: str
    jurabk: str | None
    title: str
    stand_datum: str | None
    source_xml_sha256_before: str | None
    source_xml_sha256_after: str
    changed_paths: list[str] = field(default_factory=list)


@dataclass
class DetectedEventGroup:
    effective_date: str
    laws: list[AffectedLaw] = field(default_factory=list)
    source_type: str = "gii-stand-datum"

    @property
    def event_id(self) -> str:
        if len(self.laws) == 1:
            return f"{self.effective_date}-stand-{self.laws[0].bjnr}"
        return f"{self.effective_date}-stand-{len(self.laws)}laws"
