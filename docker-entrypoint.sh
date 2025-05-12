#!/bin/bash

# 等待数据库服务可用
echo "等待数据库服务..."
while ! nc -z ${DATABASE_HOST:-db} ${DATABASE_PORT:-3306}; do
  sleep 1
done
echo "数据库服务已就绪"

# 等待Redis服务可用
echo "等待Redis服务..."
while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
  sleep 1
done
echo "Redis服务已就绪"

# 收集静态文件
echo "收集静态文件..."
python manage.py collectstatic --noinput

# 执行数据库迁移
echo "执行数据库迁移..."
python manage.py makemigrations
python manage.py migrate

# 启动Gunicorn服务器
echo "启动Web服务器..."
gunicorn --workers=4 --bind 0.0.0.0:8000 djangoProject4.wsgi:application --timeout 300 --access-logfile /app/logs/access.log --error-logfile /app/logs/error.log 