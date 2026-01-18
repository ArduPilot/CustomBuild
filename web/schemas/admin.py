from typing import List

from pydantic import BaseModel, Field


# --- Refresh Remotes Response ---
class RefreshRemotesResponse(BaseModel):
    """Response schema for remote refresh operation."""
    remotes: List[str] = Field(
        ...,
        description="List of remotes discovered in remotes.json file"
    )
