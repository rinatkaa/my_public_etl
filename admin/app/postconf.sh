#!/bin/sh
# postconf.sh

# Run configuration tasks
echo "Running setup..."
python manage.py migrate --no-input
#python manage.py makemigrations --no-input
python manage.py createsuperuser --no-input
python manage.py collectstatic --no-input


# Execute the main container command
#exec "$@"
exec uwsgi --strict --ini uwsgi.ini
#exec "$@"
#tail -f /dev/null