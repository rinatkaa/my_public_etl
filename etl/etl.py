import os
import tempfile
import psycopg2
from psycopg2.extras import DictCursor
from elasticsearch import Elasticsearch, helpers
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
import time
from uuid import UUID
import json
from collections import defaultdict
from config import PostgresConfig, ElasticConfig, AppConfig
from models import FilmWork, Person

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ETLProcess:
    def __init__(self):
        self.pg_config = PostgresConfig()
        self.es_config = ElasticConfig()
        self.app_config = AppConfig()
        self.pg_conn = None
        self.es_client = None
        self.batch_size = self.app_config.BATCH_SIZE

        # Названия индексов
        self.fw_index = self.es_config.INDEX
        self.genre_index = self.es_config.INDEX_GENRES #"genres"
        self.person_index = self.es_config.INDEX_PERSONS # "persons"

        # Состояние для каждой сущности, last_modified и last_id для каждой сущности
        self.state = {
            "film_work": {"last_modified": datetime.min, "last_id": None},
            "genre": {"last_modified": datetime.min, "last_id": None},
            "person": {"last_modified": datetime.min, "last_id": None}
        }

    def connect_postgres(self, max_attempts: Optional[int] = None, backoff_factor: Optional[float] = None):
        """Подключение к PostgreSQL с повторными попытками и backoff"""
        if max_attempts is None: 
            max_attempts = self.pg_config.MAX_CONNECT_ATTEMPTS
        if backoff_factor is None:
            backoff_factor = self.pg_config.CONNECT_BACKOFF_FACTOR

        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                self.pg_conn = psycopg2.connect(
                    host=self.pg_config.HOST, 
                    port=self.pg_config.PORT,
                    database=self.pg_config.DATABASE, 
                    user=self.pg_config.USER,
                    password=self.pg_config.PASSWORD, 
                    cursor_factory=DictCursor
                )
                logger.info("Connected to PostgreSQL")
                return
            except Exception as e:
                if attempt >= max_attempts:
                    logger.error(f"Failed to connect to PostgreSQL after {attempt} attempts: {e}")
                    raise
                sleep_time = backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    f"PostgreSQL connection failed (attempt {attempt}/{max_attempts}), "
                    f"retrying in {sleep_time:.1f}s: {e}"
                    )
                time.sleep(sleep_time)

    def connect_elasticsearch(
            self, 
            max_attempts: Optional[int] = None, 
            backoff_factor: Optional[float] = None
            ):
                """Подключение к Elasticsearch с повторными попытками и backoff"""
                if max_attempts is None: 
                    max_attempts = self.es_config.MAX_CONNECT_ATTEMPTS
                if backoff_factor is None: 
                    backoff_factor = self.es_config.CONNECT_BACKOFF_FACTOR

                attempt = 0
                while attempt < max_attempts:
                    attempt += 1
                    try:
                        self.es_client = Elasticsearch(
                            [self.es_config.url],
                            request_timeout=30
                        )
                        if self.es_client.ping():
                            logger.info("Connected to Elasticsearch")
                            return
                    except Exception as e:
                        if attempt >= max_attempts:
                            logger.error(
                                f"Failed to connect to Elasticsearch after {attempt} attempts: {e}"
                            )
                            raise
                sleep_time = backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    f"Elasticsearch connection failed (attempt {attempt}/{max_attempts}), "
                    f"retrying in {sleep_time:.1f}s: {e}"
                )
                time.sleep(sleep_time)

    def load_last_modified_state(self):
        """Загрузка состояния последней модификации из файла"""
        try:
            with open("etl_state.json", "r") as f:
                saved_state = json.load(f)
            for entity in ["film_work", "genre", "person"]:
                if entity in saved_state:
                    lm = saved_state[entity].get("last_modified")
                    lid = saved_state[entity].get("last_id")
                    self.state[entity]["last_modified"] = datetime.fromisoformat(lm) if lm else datetime.min
                    self.state[entity]["last_id"] = UUID(lid) if lid else None
            logger.info("Loaded state for all entities.")
        except FileNotFoundError:
            logger.info("No state file found, starting from beginning")
        except Exception as e:
            logger.error(f"Error loading state, starting from beginning: {e}")

    def save_state(self):
        """Атомарное сохранение состояния ETL"""
        target_path = "etl_state.json"
        state_to_save = {
            entity: {
                "last_modified": s["last_modified"].isoformat() if s["last_modified"] != datetime.min else None,
                "last_id": str(s["last_id"]) if s["last_id"] else None
            } for entity, s in self.state.items()
        }
        state_to_save["timestamp for info"] = datetime.now().isoformat()
        # Временный файл обязательно создаём в той же директории, 
        # иначе os.replace не будет атомарным на некоторых ФС.
        work_dir = os.path.dirname(os.path.abspath(target_path))
        fd, tmp_path = tempfile.mkstemp(dir=work_dir, suffix=".tmp", prefix="etl_state_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state_to_save, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target_path)
            logger.info("State saved atomically.")
        except Exception as e:
            if os.path.exists(tmp_path): os.unlink(tmp_path)
            logger.error(f"Failed to save state: {e}")
            raise

    def create_index_with_mapping(self):
        """Создание индексов с заданным маппингом"""
        # Берём настройки анализатора: стемминг, стоп-слов и пр. унес в конфиг config.py 
        analysis_cfg = self.es_config.ES_ANALYSIS_SETTINGS
        # Film Work маппинг - оставляем как было
        fw_mapping = {
            **analysis_cfg, 
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "id": {
                        "type": "keyword"
                    },
                    "imdb_rating": {
                        "type": "float"
                    },
                    "genres": {
                        "type": "keyword"
                    },
                    "title": {
                        "type": "text", 
                        "analyzer": "ru_en", 
                        "fields": {
                            "raw": {
                                "type": "keyword"
                            }
                        }
                    },
                    "description": {
                        "type": "text", 
                        "analyzer": "ru_en"
                    },
                    "directors_names": {
                        "type": "text", 
                        "analyzer": "ru_en"
                    },
                    "actors_names": {
                        "type": "text",
                        "analyzer": "ru_en"
                    },
                    "writers_names": {
                        "type": "text", 
                        "analyzer": "ru_en"
                    },
                    "directors": {
                        "type": "nested", 
                        "dynamic": "strict", 
                        "properties": {
                            "id": {
                                "type": "keyword"
                            }, 
                            "name": {
                                "type": "text", 
                                "analyzer": "ru_en"
                            }
                        }
                    },
                    "actors": {
                        "type": "nested", 
                        "dynamic": "strict", 
                        "properties": {
                            "id": {
                                "type": "keyword"
                            }, 
                            "name": {
                                "type": "text", 
                                "analyzer": "ru_en"
                            }
                        }
                    },
                    "writers": {
                        "type": "nested", 
                        "dynamic": "strict", 
                        "properties": {
                            "id": {
                                "type": "keyword"
                            }, 
                            "name": {
                                "type": "text", 
                                "analyzer": "ru_en"
                            }
                        }
                    }
                }
            }
        }
        # Проверяем существование $fw_index индекса и создаём, если его нет
        if not self.es_client.indices.exists(index=self.fw_index):
            self.es_client.indices.create(index=self.fw_index, body=fw_mapping)
            logger.info(f"Index {self.fw_index} created")

        # Genres маппинг - добавляем поля id - keyword, name с текстовым типом и анализатором для поиска по названию жанра
        g_mapping = {
            **analysis_cfg,
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "id": {
                        "type": "keyword"
                    },
                    "name": {
                        "type": "text", 
                        "analyzer": "ru_en", 
                        "fields": {
                            "raw": {
                                "type": "keyword"
                            }
                        }
                    }
                }
            }
        }
        # Проверяем существование $genre_index индекса и создаём, если его нет
        if not self.es_client.indices.exists(index=self.genre_index):
            self.es_client.indices.create(index=self.genre_index, body=g_mapping)
            logger.info(f"Index {self.genre_index} created")

        # Persons мапппинг - добавляем поля id - keyword, full_name с текстовым типом и анализатором для поиска по имени
        p_mapping = {
            **analysis_cfg,
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "id": {
                        "type": "keyword"
                    },
                    "full_name": {
                        "type": "text", 
                        "analyzer": "ru_en", 
                        "fields": {
                            "raw": {
                                "type": "keyword"
                            }
                        }
                    }
                }
            }
        }
        # Проверяем существование $person_index индекса и создаём, если его нет
        if not self.es_client.indices.exists(index=self.person_index):
            self.es_client.indices.create(index=self.person_index, body=p_mapping)
            logger.info(f"Index {self.person_index} created")

    def get_updated_records(self, entity: str, batch_size: int) -> Tuple[List[UUID], datetime, UUID]:
        """Получение ID сущностей {film_work, }, измененных после определенного времени"""
        last_modified = self.state[entity]["last_modified"]
        #если значение None или отсутствует, используй значение последнего id, иначе 00000000-0000-0000-0000-000000000000
        last_id = self.state[entity]["last_id"] or UUID('00000000-0000-0000-0000-000000000000')
        #Прежняя выборка, забирает id фильмов, если есть изменения в фильмах, жанрах или персонах, связанных с фильмами. Но она не работает корректно для жанров и персон, т.к. там нет связей. Поэтому для жанров и персон делаем простые выборки по их полям modified и id.
        if entity == "film_work":
            query = """
                SELECT fw.id, fw.modified,
                    GREATEST(fw.modified, COALESCE(MAX(g.modified), fw.modified), COALESCE(MAX(p.modified), fw.modified)) AS effective_modified
                FROM content.film_work fw
                LEFT JOIN content.genre_film_work gfw ON gfw.film_work_id = fw.id
                LEFT JOIN content.genre g ON g.id = gfw.genre_id
                LEFT JOIN content.person_film_work pfw ON pfw.film_work_id = fw.id
                LEFT JOIN content.person p ON p.id = pfw.person_id
                GROUP BY fw.id, fw.modified
                HAVING GREATEST(fw.modified, COALESCE(MAX(g.modified), fw.modified), COALESCE(MAX(p.modified), fw.modified)) > %s
                   OR (GREATEST(fw.modified, COALESCE(MAX(g.modified), fw.modified), COALESCE(MAX(p.modified), fw.modified)) = %s AND fw.id > %s)
                ORDER BY effective_modified, fw.id
                LIMIT %s
            """
            params = (last_modified, last_modified, str(last_id), batch_size)
        # Для жанров и персон делаем простые выборки по их полям modified и id, т.к. там нет связей с другими сущностями, которые могли бы влиять на выборку.
        elif entity == "genre":
            query = """
                SELECT id, name, modified FROM content.genre
                WHERE modified > %s OR (modified = %s AND id > %s)
                ORDER BY modified, id LIMIT %s
            """
            params = (last_modified, last_modified, str(last_id), batch_size)
        # Для жанров и персон делаем простые выборки по их полям modified и id, т.к. там нет связей с другими сущностями, которые могли бы влиять на выборку.
        elif entity == "person":
            query = """
                SELECT id, full_name, modified FROM content.person
                WHERE modified > %s OR (modified = %s AND id > %s)
                ORDER BY modified, id LIMIT %s
            """
            params = (last_modified, last_modified, str(last_id), batch_size)

        with self.pg_conn.cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()

        if not results:
            return [], last_modified, last_id

        ids = [row['id'] for row in results]
        new_modified = results[-1].get('effective_modified') or results[-1]['modified']
        new_id = results[-1]['id']
        return ids, new_modified, new_id

    def fetch_and_prepare_data(self, entity: str, ids: List[UUID]) -> List[Dict]:
        """Получение данных из Postgres по ID и подготовка их для индексации в Elasticsearch, чтоб потом забулкать в ES. Для фильмов дополнительно подтягиваем связанные жанры и персоны, а для жанров и персон просто их данные, т.к. там нет связей с другими сущностями, которые могли бы влиять на выборку."""
        if not ids: return []
        actions = []

        with self.pg_conn.cursor() as cursor:
            if entity == "film_work":
                # Фильмы
                cursor.execute("SELECT id, title, description, rating as imdb_rating FROM content.film_work WHERE id = ANY(%s::uuid[])", (ids,))
                fw_map = {row['id']: row for row in cursor.fetchall()}
                # Жанры
                cursor.execute("SELECT gfw.film_work_id, g.name FROM content.genre_film_work gfw JOIN content.genre g ON g.id = gfw.genre_id WHERE gfw.film_work_id = ANY(%s::uuid[])", (ids,))
                g_map = defaultdict(list)
                for r in cursor.fetchall(): g_map[r['film_work_id']].append(r['name'])
                # Персоны
                cursor.execute("SELECT pfw.film_work_id, p.id, p.full_name as name, pfw.role FROM content.person_film_work pfw JOIN content.person p ON p.id = pfw.person_id WHERE pfw.film_work_id = ANY(%s::uuid[])", (ids,))
                p_map = defaultdict(list)
                for r in cursor.fetchall(): p_map[r['film_work_id']].append(Person(id=r['id'], name=r['name'], role=r['role']))

                for fid in ids:
                    if fid not in fw_map: continue
                    base = fw_map[fid]
                    fw = FilmWork(
                        id=fid, title=base['title'], description=base['description'],
                        imdb_rating=float(base['imdb_rating']) if base['imdb_rating'] else None,
                        genres=g_map.get(fid, [])
                    )
                    fw.process_persons(p_map.get(fid, []))
                    actions.append({"_index": self.fw_index, "_id": str(fw.id), "_source": fw.to_elastic_dict()})

            elif entity == "genre":
                cursor.execute("SELECT id, name FROM content.genre WHERE id = ANY(%s::uuid[])", (ids,))
                for r in cursor.fetchall():
                    actions.append({"_index": self.genre_index, "_id": str(r['id']), "_source": {"id": str(r['id']), "name": r['name']}})

            elif entity == "person":
                cursor.execute("SELECT id, full_name FROM content.person WHERE id = ANY(%s::uuid[])", (ids,))
                for r in cursor.fetchall():
                    actions.append({"_index": self.person_index, "_id": str(r['id']), "_source": {"id": str(r['id']), "full_name": r['full_name']}})

        return actions

    def bulk_index(self, actions: List[Dict]):
        """Финальная Индексация данных в Elasticsearch с помощью bulk API"""
        if not actions: return
        try:
            success, errors = helpers.bulk(self.es_client, actions, raise_on_error=False, chunk_size=500)
            failed = len(errors) if errors else 0
            logger.info(f"Bulk indexing: {success} ok, {failed} failed")
            if errors: logger.warning(f"Bulk errors: {errors[:3]}...")
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            raise

    def sync_entity(self, entity: str):
        """Синхронизация одной сущности: получение обновлений, подготовка данных и индексация в ES, с обновлением состояния после каждой партии данных"""
        logger.info(f"Starting sync for {entity}...")
        while True:
            ids, new_modified, new_id = self.get_updated_records(entity, self.batch_size)
            if not ids:
                logger.info(f"No more updates for {entity}.")
                break

            actions = self.fetch_and_prepare_data(entity, ids)
            if actions:
                self.bulk_index(actions)
                logger.info(f"Indexed {len(actions)} records for {entity}.")

            self.state[entity]["last_modified"] = new_modified
            self.state[entity]["last_id"] = new_id
            self.save_state()

            if len(ids) < self.batch_size:
                break
        logger.info(f"Finished sync for {entity}.")

    def run_etl(self):
        self.load_last_modified_state()
        self.connect_postgres()
        self.connect_elasticsearch()
        self.create_index_with_mapping()

        # Синхронизируем все сущности последовательно
        for entity in ["film_work", "genre", "person"]:
            try:
                self.sync_entity(entity)
            except Exception as e:
                logger.error(f"ETL failed for {entity}: {e}. Skipping to next entity.")
                continue

        logger.info("ETL process completed for all entities..")
        self.close_connections()

    def close_connections(self):
        if self.pg_conn: self.pg_conn.close()
        if self.es_client: self.es_client.close()
        logger.info("Connections closed.")

def main():
    etl = ETLProcess()
    etl.run_etl()

if __name__ == "__main__":
    main()