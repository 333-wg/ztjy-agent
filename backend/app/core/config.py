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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
