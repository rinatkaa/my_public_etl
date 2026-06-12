from uuid import UUID

from models.base import BaseConfigModel


class Genre(BaseConfigModel):
    """Жанры.

    Нюанс - сейчас жанры в etl хранятся без uuid, но он нужен будет для API.
    """

    id: UUID
    name: str
