"""Pagination utilities."""
from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=1000, description="Max rows to return")
    offset: int = Field(default=0, ge=0, description="Number of rows to skip")


def build_pagination_response(
    items: list, total: int, offset: int, limit: int
) -> dict:
    return {
        "items": items,
        "total": total,
        "count": len(items),
        "offset": offset,
        "limit": limit,
        "has_more": total > offset + len(items),
        "next_offset": offset + len(items) if total > offset + len(items) else None,
    }
