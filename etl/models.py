from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from uuid import UUID

class Person(BaseModel):
    id: UUID
    name: str
    role: str

class Genre(BaseModel):
    id: UUID
    name: str

class FilmWork(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    imdb_rating: Optional[float] = None

    # Безопасные изменяемые поля: каждый экземпляр получит свой уникальный список/дикт
    genres: List[str] = Field(default_factory=list)
    directors: List[Dict] = Field(default_factory=list)
    actors: List[Dict] = Field(default_factory=list)
    writers: List[Dict] = Field(default_factory=list)
    # Строки иммутабельны
    directors_names: str = ""
    actors_names: str = ""
    writers_names: str = ""

    def to_elastic_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "imdb_rating": self.imdb_rating,
            "genres": self.genres,
            "title": self.title,
            "description": self.description,
            "directors_names": self.directors_names,
            "actors_names": self.actors_names,
            "writers_names": self.writers_names,
            "directors": self.directors,
            "actors": self.actors,
            "writers": self.writers
        }

    def process_persons(self, persons: List[Person]):
        directors = []
        actors = []
        writers = []

        directors_names_list = []
        actors_names_list = []
        writers_names_list = []

        for person in persons:
            person_dict = {"id": str(person.id), "name": person.name}

            if person.role == "director":
                directors.append(person_dict)
                directors_names_list.append(person.name)
            elif person.role == "actor":
                actors.append(person_dict)
                actors_names_list.append(person.name)
            elif person.role == "writer":
                writers.append(person_dict)
                writers_names_list.append(person.name)

        self.directors = directors
        self.actors = actors
        self.writers = writers
        self.directors_names = " ".join(directors_names_list)
        self.actors_names = " ".join(actors_names_list)
        self.writers_names = " ".join(writers_names_list)