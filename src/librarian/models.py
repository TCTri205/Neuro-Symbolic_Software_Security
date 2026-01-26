from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SecurityLabel(str, Enum):
    SOURCE = "source"
    SINK = "sink"
    SANITIZER = "sanitizer"
    NONE = "none"


class ParameterSpec(BaseModel):
    name: str
    index: int = -1  # -1 means unknown or irrelevant
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class FunctionSpec(BaseModel):
    name: str  # Fully qualified name (e.g., "os.system")
    label: SecurityLabel = SecurityLabel.NONE
    parameters: List[ParameterSpec] = Field(default_factory=list)
    returns_tainted: bool = False
    description: Optional[str] = None
    cwe_id: Optional[str] = None  # e.g., "CWE-78"


class LibraryVersion(BaseModel):
    version: str  # e.g., "1.0.0"
    functions: List[FunctionSpec] = Field(default_factory=list)
    release_date: Optional[str] = None
    deprecated: bool = False


class Library(BaseModel):
    name: str  # e.g., "requests"
    ecosystem: str  # e.g., "pypi", "npm"
    versions: List[LibraryVersion] = Field(default_factory=list)
    description: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None
