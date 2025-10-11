"""Level loading and validation helpers for the levels API."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

LEVELS_DIR_ENV = "FOLDIT_LEVELS_DIR"
DEFAULT_LEVELS_DIR = Path(__file__).resolve().parents[1] / "data" / "levels"
ALLOWED_SS = {"H", "E", "C"}
DIFFICULTIES = {"easy", "medium", "hard"}


class LevelDataError(Exception):
    """Base exception for level loading errors."""


@dataclass(slots=True)
class LevelNotFoundError(LevelDataError):
    """Raised when a requested level is missing from disk."""

    level_id: str


@dataclass(slots=True)
class LevelValidationError(LevelDataError):
    """Raised when a level fails schema validation."""

    details: List[dict]


class ContactModel(BaseModel):
    """Representation of a residue contact entry."""

    model_config = ConfigDict(extra="forbid")

    i: int
    j: int
    type: str | None = None

    @model_validator(mode="after")
    def validate_indices(self) -> "ContactModel":
        if self.i < 0 or self.j < 0:
            raise ValueError("contact indices must be non-negative")
        if self.i == self.j:
            raise ValueError("contact indices must be distinct")
        return self


class LevelSummaryModel(BaseModel):
    """Summary information exposed on the level catalog."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    difficulty: str
    length: int
    preview_img_url: str | None = None
    tags: List[str] | None = None
    short_desc: str | None = None

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        if value not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {sorted(DIFFICULTIES)}")
        return value

    @field_validator("length")
    @classmethod
    def validate_length(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("length must be positive")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(
        cls, value: Iterable[str] | None
    ) -> List[str] | None:  # pragma: no cover - trivial normalisation
        if value is None:
            return None
        tags = [tag for tag in value if tag]
        return tags or None


class LevelModel(BaseModel):
    """Full level definition used by the play experience."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    difficulty: str
    length: int
    sequence: str
    start_coords_url: str
    target_ss: str
    target_contacts: List[ContactModel] | None = None
    tips: List[str] | None = None
    preview_img_url: str | None = None
    version: int | None = None

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        if value not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {sorted(DIFFICULTIES)}")
        return value

    @model_validator(mode="after")
    def validate_consistency(self) -> "LevelModel":
        sequence_length = len(self.sequence)
        if sequence_length == 0:
            raise ValueError("sequence must contain at least one residue")
        if self.length != sequence_length:
            raise ValueError("length field must match sequence length")
        if len(self.target_ss) != sequence_length:
            raise ValueError("target secondary structure must match sequence length")
        invalid_ss = sorted(set(self.target_ss) - ALLOWED_SS)
        if invalid_ss:
            raise ValueError(f"invalid secondary structure codes: {invalid_ss}")
        if self.target_contacts:
            for contact in self.target_contacts:
                if contact.i >= sequence_length or contact.j >= sequence_length:
                    raise ValueError("contact indices must fall within the sequence length")
        return self


def _compute_etag(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _load_json(path: Path) -> Tuple[object, bytes]:
    raw = _load_bytes(path)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise LevelValidationError([{"msg": f"invalid json: {exc}"}]) from exc


def get_levels_dir() -> Path:
    override = os.getenv(LEVELS_DIR_ENV)
    return Path(override) if override else DEFAULT_LEVELS_DIR


def load_level_summaries() -> Tuple[List[LevelSummaryModel], str]:
    """Load the level index file and validate each entry."""

    path = get_levels_dir() / "levels_index.json"
    if not path.exists():
        raise LevelDataError("levels index missing")
    data, raw = _load_json(path)
    if not isinstance(data, list):
        raise LevelDataError("levels index must be an array")

    summaries: List[LevelSummaryModel] = []
    try:
        for entry in data:
            summaries.append(LevelSummaryModel.model_validate(entry))
    except ValidationError as exc:  # pragma: no cover - validated via API tests
        raise LevelValidationError(exc.errors()) from exc

    return summaries, _compute_etag(raw)


def load_level(level_id: str) -> Tuple[LevelModel, str]:
    """Load the full level definition."""

    path = get_levels_dir() / f"{level_id}.json"
    if not path.exists():
        raise LevelNotFoundError(level_id)

    data, raw = _load_json(path)
    try:
        level = LevelModel.model_validate(data)
    except ValidationError as exc:
        raise LevelValidationError(exc.errors()) from exc

    return level, _compute_etag(raw)


__all__ = [
    "ContactModel",
    "LevelDataError",
    "LevelModel",
    "LevelNotFoundError",
    "LevelSummaryModel",
    "LevelValidationError",
    "get_levels_dir",
    "load_level",
    "load_level_summaries",
]
