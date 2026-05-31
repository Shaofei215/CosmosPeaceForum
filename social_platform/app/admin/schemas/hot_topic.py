from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HotTopicCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    search_query: str = Field(min_length=1, max_length=200)
    summary: Optional[str] = Field(default=None, max_length=2000)
    source: str = Field(default="manual", max_length=20)
    status: str = Field(default="active", max_length=20)
    rank: int = Field(default=1, ge=1)


class HotTopicUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    search_query: Optional[str] = Field(default=None, min_length=1, max_length=200)
    summary: Optional[str] = Field(default=None, max_length=2000)
    source: Optional[str] = Field(default=None, max_length=20)
    status: Optional[str] = Field(default=None, max_length=20)
    rank: Optional[int] = Field(default=None, ge=1)


class HotTopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    search_query: str
    summary: Optional[str]
    source: str
    status: str
    rank: int
    generation_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class HotTopicSettingsResponse(BaseModel):
    id: int
    agent_enabled: bool
    agent_interval_minutes: int
    publish_policy: str
    llm_base_url: Optional[str]
    llm_model_name: Optional[str]
    llm_api_key: Optional[str]
    web_search_enabled: bool
    tavily_api_key: Optional[str]
    history_limit: int
    updated_at: datetime


class HotTopicSettingsUpdateRequest(BaseModel):
    agent_enabled: Optional[bool] = None
    agent_interval_minutes: Optional[int] = Field(default=None, ge=5, le=10080)
    publish_policy: Optional[str] = Field(default=None, max_length=20)
    llm_base_url: Optional[str] = Field(default=None, max_length=500)
    llm_model_name: Optional[str] = Field(default=None, max_length=120)
    llm_api_key: Optional[str] = Field(default=None, max_length=500)
    web_search_enabled: Optional[bool] = None
    tavily_api_key: Optional[str] = Field(default=None, max_length=500)
    history_limit: Optional[int] = Field(default=None, ge=1, le=10)


class HotTopicGenerationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    publish_policy: str
    input_snapshot: Optional[str]
    output_json: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]


class HotTopicGenerationRunResponse(BaseModel):
    generation: HotTopicGenerationResponse
    topics: list[HotTopicResponse]
