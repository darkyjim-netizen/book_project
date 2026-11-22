#!/bin/bash
# 컨테이너가 켜질 때 DB와 백엔드를 순서대로 실행한다.
service postgresql start
# DB가 연결을 받을 때까지 기다린다 (최대 30초)
for i in $(seq 1 30); do
  su - postgres -c "psql -c 'select 1'" >/dev/null 2>&1 && break
  sleep 1
done
cd /root/backend
. .venv/bin/activate
exec uvicorn main:app --host 0.0.0.0 --port 8000
