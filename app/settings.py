from pydantic import BaseSettings, Field, validator
from typing import Optional

class Settings(BaseSettings):
    SUPABASE_DB_URL: Optional[str] = Field(
        default=None,
        description="postgresql://.../postgres?sslmode=require",
        env="SUPABASE_DB_URL",
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    USERS_PATH: str = Field(default="data/users.json")
    INTERVIEWERS_PATH: str = Field(default="data/interviewers.json")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("SUPABASE_DB_URL")
    def _validate_db_url(cls, v):
        if not v:
            raise ValueError(
                "Set SUPABASE_DB_URL to your Supabase Postgres connection string (with ?sslmode=require)."
            )
        if "sslmode" not in v:
            raise ValueError("SUPABASE_DB_URL must include ?sslmode=require")
        return v

settings = Settings()
