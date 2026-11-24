from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Event(BaseModel):
    event_id: str = Field(min_length=8, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    item_id: str = Field(min_length=1, max_length=64)
    kind: Literal["view", "click", "purchase"] = "view"
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
