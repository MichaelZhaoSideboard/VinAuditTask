from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    min_make_listings: int = 50  # filter out junk makes/models below this count

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
