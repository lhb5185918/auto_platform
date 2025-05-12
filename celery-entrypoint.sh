#!/bin/bash

# 等待Redis主库可用
echo "等待Redis服务..."
while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
  sleep 1
done
echo "Redis服务已就绪"

# 等待10秒确保所有服务都已启动
sleep 10

echo "启动Celery worker..."
cd /app
celery -A djangoProject4 worker --loglevel=info 