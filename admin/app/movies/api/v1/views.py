from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Q
from django.http import JsonResponse
from django.views.generic.list import BaseListView
from django.views.generic.detail import BaseDetailView
from django.views import View
from movies.models import FilmWork, PersonFilmWork 

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

import uuid

class MoviesListApi(BaseListView):
    model = FilmWork
    paginate_by = 50  # кол-во строк на странице 

    def get_queryset(self):
        """Возвращает исходный набор фильмов можно добавлять filter, order_by и пр."""
        # + order для статичности пагинации
        return FilmWork.objects.all().order_by('id')

    def get_context_data(self, *, object_list=None, **kwargs):
        queryset = object_list if object_list is not None else self.get_queryset()
        page_number = self.request.GET.get('page', 1)

        # Ручная пагинация через Django Paginator
        paginator = Paginator(queryset, self.paginate_by)
        
        try:
            page = paginator.page(page_number)
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

        # Формируем список фильмов вручную
        results = []
        for movie in page.object_list:
            results.append({
                "id": str(movie.id),  # UUID → string
                "title": movie.title,
                "description": movie.description,
                "creation_date": movie.creation_date.isoformat() if movie.creation_date else None,
                "rating": movie.rating,
                "type": movie.type,
            })
        # Собираем ответ
        return {
            "count": paginator.count,
            "total_pages": paginator.num_pages,
            "prev": page.previous_page_number() if page.has_previous() else None,
            "next": page.next_page_number() if page.has_next() else None,
            "results": results,
        }
    
    def render_to_response(self, context, **response_kwargs):
        """Возвращаем JSON"""
        return JsonResponse(context, **response_kwargs)
    

"""
    
        Детальное представление 

"""

class MovieDetailApi(View):
    def get(self, request, *args, **kwargs):
        raw_id = kwargs.get('id')

        # Валидация формата UUID вручную
        try:
            film_id = uuid.UUID(raw_id)
        except (ValueError, TypeError, AttributeError):
            return JsonResponse({"error": "Invalid UUID format"}, status=400)

        # Поиск записи в БД
        film = FilmWork.objects.filter(id=film_id).prefetch_related('genres').first()
        if not film:
            return JsonResponse({"error": "Film not found"}, status=404)

        # Сборка данных по спецификации OpenAPI
        data = {
            "id": str(film.id),
            "title": film.title,
            "description": film.description,
            "creation_date": film.creation_date.isoformat() if film.creation_date else None,
            "rating": float(film.rating) if film.rating is not None else None,
            "type": film.type,
            "genres": list(film.genres.values_list('name', flat=True)),
            "actors": [],
            "directors": [],
            "writers": [],
        }

        # Распределение ролей
        links = film.persons.through.objects.filter(film_work_id=film.id).select_related('person')
        for link in links:
            name = link.person.full_name
            role = link.role  
            if role == 'actor': data["actors"].append(name)
            elif role == 'director': data["directors"].append(name)
            elif role == 'writer': data["writers"].append(name)

        # возвращаем JSON
        return JsonResponse(data)


    """
     Не работает с uuid, т.к. в дебрях django при ошибке поиска в view возвращается 404 и HTML страница об ошибке

       model = FilmWork
    pk_url_kwarg = 'id'  # Имя параметра из <uuid:id>

    def get_queryset(self):
        return FilmWork.objects.prefetch_related('genres')

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg)
        if queryset is None:
            queryset = self.get_queryset()
        
        try:
            # pk является uuid.UUID благодаря конвертеру <uuid:id>
            return queryset.get(id=pk)
        except FilmWork.DoesNotExist:
            raise Http404("Фильм не найден")

    def get_context_data(self, **kwargs):
        movie = self.object

        # Жанры
        genres = list(movie.genres.values_list('name', flat=True))

        # персоны по ролям
        person_links = movie.persones.through.objects.filter(film_work_id=movie.id).select_related('person')

        actors, directors, writers = [], [], []
        for link in person_links:
            role = link.role  
            name = link.person.full_name

            if role == 'actor':
                actors.append(name)
            elif role == 'director':
                directors.append(name)
            elif role == 'writer':
                writers.append(name)

        return {
            "id": str(movie.id),
            "title": movie.title,
            "description": movie.description,
            "creation_date": movie.creation_date.isoformat() if movie.creation_date else None,
            "rating": float(movie.rating) if movie.rating is not None else None,
            "type": movie.type,
            "genres": genres,
            "actors": actors,
            "directors": directors,
            "writers": writers,
        }

    def render_to_response(self, context, **response_kwargs):
        return JsonResponse(context, **response_kwargs)
"""