from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal, ClassVar

class PostgresConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='PG_', env_file='.env', extra='ignore')

    HOST: str = Field(default='cinema-db', description='PostgreSQL host')
    PORT: int = Field(default=5432, ge=1, le=65535)
    DATABASE: str = Field(default='postgres')
    USER: str = Field(default='postgres')
    PASSWORD: str = Field(default='')
    MAX_CONNECT_ATTEMPTS: int = Field(default=5, ge=1)
    CONNECT_BACKOFF_FACTOR: float = Field(default=1.0, ge=0.1)

class ElasticConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='ES_', env_file='.env', extra='ignore')

    HOST: str = Field(default='elasticsearch')
    PORT: int = Field(default=9200, ge=1, le=65535)
    SCHEME: Literal['http', 'https'] = Field(default='http')
    INDEX: str = Field(default='movies')
    INDEX_GENRES: str = Field(default='genres')
    INDEX_PERSONS: str = Field(default='persons')
    MAX_CONNECT_ATTEMPTS: int = Field(default=5, ge=1)
    CONNECT_BACKOFF_FACTOR: float = Field(default=1.0, ge=0.1)
    ES_ANALYSIS_SETTINGS: ClassVar[dict] = {
        "settings": {
            "refresh_interval": "1s",
            "analysis": {
                "filter": {
                    "english_stop": {"type": "stop", "stopwords": "_english_"},
                    "english_stemmer": {"type": "stemmer", "language": "english"},
                    "english_possessive_stemmer": {"type": "stemmer", "language": "possessive_english"},
                    "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                    "russian_stemmer": {"type": "stemmer", "language": "russian"}
                },
                "analyzer": {
                    "ru_en": {
                        "tokenizer": "standard",
                        "filter": [
                            "lowercase", "english_stop", "english_stemmer",
                            "english_possessive_stemmer", "russian_stop", "russian_stemmer"
                        ]
                    }
                }
            }
        }
    }

    @property
    def url(self) -> str:
        return f"{self.SCHEME}://{self.HOST}:{self.PORT}"

class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    BATCH_SIZE: int = Field(default=20, ge=1)
    STATE_FILE: str = Field(default='etl_state.json')
