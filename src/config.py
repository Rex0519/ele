from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://admin:password@localhost:5432/electric"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    mcp_port: int = 8001

    # Feishu webhook
    feishu_webhook_url: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
