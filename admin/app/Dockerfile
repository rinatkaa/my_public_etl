FROM python:3.10

WORKDIR /opt/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UWSGI_PROCESSES=1
ENV UWSGI_THREADS=16
ENV UWSGI_HARAKIRI=240
ENV DJANGO_SETTINGS_MODULE='example.settings'
ENV DJANGO_SUPERUSER_USERNAME='super'
ENV DJANGO_SUPERUSER_PASSWORD='puper'
ENV DJANGO_SUPERUSER_EMAIL='super@puper.it'

COPY run_uwsgi.sh run_uwsgi.sh
COPY requirements.txt requirements.txt
COPY uwsgi/uwsgi.ini uwsgi.ini

RUN  mkdir -p /var/www/static/ \
     && mkdir -p /var/www/media/ \
     && mkdir -p /opt/app/static/ \
     && mkdir -p /opt/app/media/ \
     && pip install --upgrade pip \
     && pip install -r requirements.txt

COPY . .

COPY postconf.sh /postconf.sh
RUN chmod +x /postconf.sh
#RUN python manage.py collectstatic --no-input
RUN python manage.py makemigrations --no-input
#RUN python manage.py migrate --no-input
#RUN python manage.py createsuperuser --no-input

EXPOSE 8000

ENTRYPOINT ["/postconf.sh"]
