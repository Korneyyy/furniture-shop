web: python manage.py collectstatic --noinput && python manage.py ensuresuperuser && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
