"""Read provider configuration without ever exposing credentials in repr/logs."""

import os

from pydantic import BaseModel, Field, SecretStr


class AISettings(BaseModel):
    api_key: SecretStr
    model: str = Field(min_length=1, max_length=100)
    timeout: float = Field(default=30, gt=0, le=30, allow_inf_nan=False)
    request_timeout: float = Field(default=25, gt=0, le=30, allow_inf_nan=False)
    cache_enabled: bool = True

    @classmethod
    def from_env(cls) -> "AISettings":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "").strip(),
            timeout=os.getenv("AI_TIMEOUT_SECONDS", "30"),
            request_timeout=os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "25"),
            cache_enabled=os.getenv("AI_CACHE_ENABLED", "true"),
        )
