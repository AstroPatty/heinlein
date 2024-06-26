from pydantic import ByteSize, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HeinleinConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HEINLEIN_", validate_assignment=True)
    CACHE_ENABLED: bool = Field(False)
    CACHE_SIZE: ByteSize = Field(4e9, ge=1e9)
