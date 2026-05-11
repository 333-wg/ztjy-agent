from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Advertisement Agent System"
    app_env: str = "development"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    admin_backend_url: str = ""
    browser_profile_path: str = ""
    browser_profile_alias: str = ""
    playwright_login_success_selector: str = ""
    langgraph_checkpointer: str = "memory"
    langgraph_postgres_url: str = ""
    langgraph_postgres_setup: bool = False
    llm_parser_mode: str = "deterministic"
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
