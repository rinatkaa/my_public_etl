# Внутренние модели описываем тут, они используются для бизнес-логики в service.
# Используем pydantic для упрощения работы при перегонке данных из json в объекты.
"""Доменная модель фильма.

Зеркалит документ из индекса ElasticSearch movies: имена и типы полей
совпадают с тем, что складывает ETL. Для использования
в бизнес-логике сервиса
"""
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from models.base import BaseConfigModel
from models.person import PersonNested


class Film(BaseConfigModel):
    id: UUID
    title: str
    description: Optional[str] = None
    imdb_rating: Optional[float] = None

    # Жанры в индексе хранятся как список названий (keyword), без id
    genres: List[str] = Field(default_factory=list)

    # Персоны во вложенном виде: {id, name}, разнесены по ролям
    directors: List[PersonNested] = Field(default_factory=list)
    actors: List[PersonNested] = Field(default_factory=list)
    writers: List[PersonNested] = Field(default_factory=list)

    # Денормализованные строки имён, пригодится для поиска по фильму
    directors_names: str = ""
    actors_names: str = ""
    writers_names: str = ""
