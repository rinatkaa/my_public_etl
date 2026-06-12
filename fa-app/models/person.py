"""Модели персон: актёры, сценаристы и режиссёры.

Все три роли описываются одной структурой (идентификатор + имя),
а роль определяется тем, в каком списке фильма находится персона
(actors/writers/directors). Поэтому для вложенного представления
внутри фильма достаточно одной модели PersonNested (см. использование в film.py)
"""
from typing import List
from uuid import UUID

from pydantic import Field

from models.base import BaseConfigModel


class PersonNested(BaseConfigModel):
    """Персона во вложенном виде внутри документа фильма.
e
    Соответствует объектам в полях actors/writers/directors индекса
    movies: {"id": ..., "name": ...}.
    """

    id: UUID
    name: str


class PersonFilm(BaseConfigModel):
    """Фильм в карточке персоны с перечнем её ролей в этом фильме"""

    id: UUID
    roles: List[str] = Field(default_factory=list)


class Person(BaseConfigModel):
    """Персона как самостоятельная сущность.

    Используется на странице персоны: полное имя и список фильмов
    с ролями (actor/writer/director) в каждом из них.
    """

    id: UUID
    full_name: str
    films: List[PersonFilm] = Field(default_factory=list)
