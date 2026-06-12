"""Базовые классы для моделей.

Доменные модели описывают данные так, как они лежат в хранилище
(ElasticSearch) и используются в бизнес-логике сервисов
"""
from pydantic import BaseModel, ConfigDict


class BaseConfigModel(BaseModel):
    """Базовая модель проекта с общей конфигурацией
    """

    model_config = ConfigDict(populate_by_name=True)
