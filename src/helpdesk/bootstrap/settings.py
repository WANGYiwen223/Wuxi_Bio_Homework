"""Local settings; API credentials never appear in repr, errors, or traces."""

from pathlib import Path
import os
from urllib.parse import urlparse

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    base_url: str
    api_key: SecretStr
    model_name: str
    timeout: float = Field(default=60, gt=0, le=120)
    max_model_calls: int = Field(default=8, ge=1, le=20)
    max_tool_calls: int = Field(default=16, ge=1, le=40)
    max_context_chars: int = Field(default=48000, ge=8000, le=200000)
    run_dir: Path

    @classmethod
    def load(cls, root: Path):
        values = {**dotenv_values(root / ".env", encoding="utf-8-sig"), **os.environ}
        required = ["HELPDESK_MODEL_BASE_URL", "HELPDESK_MODEL_API_KEY", "HELPDESK_MODEL_NAME"]
        if any(not values.get(key) for key in required):
            raise ValueError("Missing required HELPDESK_MODEL_* configuration; see .env.example")
        url = urlparse(values[required[0]])
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Model endpoint must be an HTTP(S) base URL without embedded credentials")
        return cls(base_url=values[required[0]], api_key=SecretStr(values[required[1]]), model_name=values[required[2]], timeout=values.get("HELPDESK_MODEL_TIMEOUT", 60), max_model_calls=values.get("HELPDESK_MAX_MODEL_CALLS", 8), max_tool_calls=values.get("HELPDESK_MAX_TOOL_CALLS", 16), max_context_chars=values.get("HELPDESK_MAX_CONTEXT_CHARS", 48000), run_dir=root / values.get("HELPDESK_RUN_DIR", "var/runs/baseline"))
