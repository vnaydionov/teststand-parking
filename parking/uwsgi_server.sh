#!/bin/sh
uwsgi-core --plugin python27 --http-socket :8111 --wsgi-file wsgi_app.py --master --processes 4 --threads 2 --stats 127.0.0.1:9191
