from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    canvas_base_url: str = "https://canvas.instructure.com"
    canvas_api_token: str = ""
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
