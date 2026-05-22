from typing import Literal

from pydantic import BaseModel


SearchType = Literal["content", "user"]


class SearchMeta(BaseModel):
    type: SearchType
    query: str
