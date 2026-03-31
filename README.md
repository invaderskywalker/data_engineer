


venv/bin/gunicorn --timeout 120 -w 1 -k eventlet  -b 0.0.0.0:8889 src.api.app.App:app

venv/bin/gunicorn -w 1 --log-level debug -b 127.0.0.1:7001 src.api.app.App:app

