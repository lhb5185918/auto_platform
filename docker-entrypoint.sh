#!/bin/bash

# 等待数据库服务可用
echo "等待数据库服务..."
sleep 10

# 收集静态文件
echo "收集静态文件..."
python manage.py collectstatic --noinput

# 执行数据库迁移
echo "执行数据库迁移..."
python manage.py makemigrations
python manage.py migrate

# 启动Gunicorn服务器
echo "启动Web服务器..."
gunicorn --bind 0.0.0.0:8000 djangoProject4.wsgi:application 