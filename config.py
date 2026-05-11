from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    canvas_api_token: str
    canvas_base_url: str = "https://canvas.instructure.com"
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
