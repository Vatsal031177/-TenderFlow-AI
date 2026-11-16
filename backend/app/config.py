from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://tendos:tendos@localhost:5432/tendos"
    elasticsearch_url: str = "http://localhost:9200"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "tenderflow-ai"
    min_margin_percent: float = 18.0
    confidence_review_threshold: float = 0.75

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
