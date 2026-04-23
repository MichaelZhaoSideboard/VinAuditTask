from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    min_make_listings: int = 50   # filters junk makes (e.g. "23' GOOSENECK TRAILER")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
