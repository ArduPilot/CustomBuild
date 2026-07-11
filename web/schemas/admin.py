from typing import List

from pydantic import BaseModel, Field


class RefreshVersionsResponse(BaseModel):
    """Response schema for version metadata refresh operation."""
    remotes: List[str] = Field(
        ...,
        description="Git remotes synced after refreshing all version providers",
    )
