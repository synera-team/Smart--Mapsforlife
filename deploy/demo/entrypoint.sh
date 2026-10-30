#!/bin/sh
# Demo container start: build the demo DB once (fresh schema + repo sample data + labelled [DEMO] seed),
# keep a pristine copy for resets, then serve. Data lives on the /data volume and survives restarts and redeploys.
set -e
cd /app
python server/manage.py init                      # schema + sample data + M4L migrations (idempotent)
if [ ! -f /data/demo-template.db ]; then
  (cd server && python seed_m4l_demo.py)          # refuses production paths; does nothing if already seeded
  python server/m4l_demo.py snapshot
fi
if [ -f /data/RESET_DEMO ]; then                  # touch /data/RESET_DEMO and restart to wipe visitor data
  python server/m4l_demo.py reset && rm -f /data/RESET_DEMO
fi
cd server
exec gunicorn -w "${WORKERS:-2}" --threads 4 -b "0.0.0.0:${PORT:-8080}" --timeout 120 --access-logfile - wsgi:app
