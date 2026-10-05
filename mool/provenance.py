"""Tagged values: every security-critical value carries where it came from."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Trust(str, Enum):
    USER = "user"            # the human's own words
    CONTACTS = "contacts"    # the user's own saved data
    REGISTRY = "registry"    # a verified merchant registry
    UNTRUSTED = "untrusted"  # anything read from the outside world


TRUSTED = frozenset({Trust.USER, Trust.CONTACTS, Trust.REGISTRY})


@dataclass(frozen=True)
class Origin:
    trust: Trust
    source: str  # e.g. "contacts:Ramesh Kirana", "doc:invoice.pdf", "mcp:merchant_lookup"


@dataclass(frozen=True)
class Tagged:
    value: object
    origins: frozenset

    @property
    def trusted(self) -> bool:
        return bool(self.origins) and all(o.trust in TRUSTED for o in self.origins)

    @property
    def sources(self) -> list[str]:
        return sorted(o.source for o in self.origins)

    def derive(self, value) -> "Tagged":
        """A value computed from this one inherits all of its origins."""
        return Tagged(value, self.origins)

    def to_dict(self) -> dict:
        return {"value": self.value,
                "origins": sorted([{"trust": o.trust.value, "source": o.source} for o in self.origins],
                                  key=lambda d: (d["trust"], d["source"]))}


def tag(value, trust: Trust, source: str) -> Tagged:
    return Tagged(value, frozenset({Origin(trust, source)}))
