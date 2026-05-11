from __future__ import annotations

from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from supabase import Client, create_client


class SupabaseSettings(BaseSettings):
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def public_config(self) -> dict[str, str]:
        return {
            "supabase_url": self.supabase_url,
            "supabase_anon_key": self.supabase_anon_key,
        }

    def server_key(self) -> str:
        return self.supabase_service_role_key


def get_supabase_settings() -> SupabaseSettings:
    return SupabaseSettings()


def create_server_supabase_client(settings: SupabaseSettings | None = None) -> Client:
    resolved = settings or get_supabase_settings()
    key = resolved.server_key()
    if not resolved.supabase_url or not key:
        raise ValueError("SUPABASE_URL and a server Supabase key are required")
    return create_client(resolved.supabase_url, key)


def create_public_supabase_client(settings: SupabaseSettings | None = None) -> Client:
    resolved = settings or get_supabase_settings()
    if not resolved.supabase_url or not resolved.supabase_anon_key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY are required")
    return create_client(resolved.supabase_url, resolved.supabase_anon_key)


def get_public_supabase_config(settings: SupabaseSettings | None = None) -> dict[str, Any]:
    resolved = settings or get_supabase_settings()
    return resolved.public_config()
