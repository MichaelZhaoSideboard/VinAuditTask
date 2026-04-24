from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    min_make_listings: int = 50   # filters junk makes (e.g. "23' GOOSENECK TRAILER")
    min_model_listings: int = 5   # filters junk models (e.g. VIN codes, "Other")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
