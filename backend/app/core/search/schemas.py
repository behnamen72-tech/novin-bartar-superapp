from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SearchEntityType(StrEnum):
    ORGANIZATION = "organization"
    PERSON = "person"
    DOCUMENT = "document"
    CUSTOMER = "customer"
    SUPPLIER = "supplier"


class SearchResultItem(BaseModel):
    entity_type: SearchEntityType
    id: UUID
    title: str
    subtitle: str | None = None
    organization_id: UUID | None = None
    organization_name: str | None = None
    action_path: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    counts: dict[str, int] = Field(default_factory=dict)
