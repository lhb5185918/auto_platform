#!/bin/bash
set -e

# 确保日志目录存在
mkdir -p /app/logs
chmod -R 777 /app/logs

# 检查DNS是否能解析数据库主机名
echo "验证数据库主机名DNS解析..."
if [[ "${DATABASE_HOST}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "数据库主机是IP地址，跳过DNS检查"
else
  echo "尝试解析数据库主机名: ${DATABASE_HOST}"
  if ! nslookup ${DATABASE_HOST} > /dev/null 2>&1; then
    echo "警告: 无法解析数据库主机名，尝试使用/etc/hosts中的映射"
    # 打印当前hosts配置
    echo "当前hosts配置:"
    cat /etc/hosts
  else
    echo "数据库主机名解析成功"
  fi
fi

# 等待数据库服务可用
echo "等待数据库服务..."
for i in {1..60}; do  # 增加重试次数到60次
  if nc -z -w 5 ${DATABASE_HOST} ${DATABASE_PORT}; then  # 设置连接超时为5秒
    echo "数据库服务已就绪"
    break
  fi
  
  if [ $i -eq 60 ]; then
    echo "数据库连接超时，退出启动"
    exit 1
  fi
  
  echo "等待数据库连接... (尝试 $i/60)"
  sleep 3  # 增加等待时间到3秒
done

# 等待Redis服务可用
echo "等待Redis服务..."
for i in {1..30}; do
  if nc -z -w 3 ${REDIS_HOST} ${REDIS_PORT}; then  # 设置连接超时为3秒
    echo "Redis服务已就绪"
    break
  fi
  
  if [ $i -eq 30 ]; then
    echo "Redis连接超时，退出启动"
    exit 1
  fi
  
  echo "等待Redis连接... (尝试 $i/30)"
  sleep 1
done

# 收集静态文件
echo "收集静态文件..."
python manage.py collectstatic --noinput

# 跳过数据库迁移
echo "跳过数据库迁移..."
# 如果需要验证数据库连接可以取消注释下面的代码
# python -c "
# import django
# from django.db import connections
# django.setup()
# try:
#     connections['default'].cursor()
#     print('数据库连接正常')
# except Exception as e:
#     print(f'数据库连接失败: {e}')
# "

# 启动Gunicorn服务器
echo "启动Web服务器..."
exec gunicorn --workers=4 \
              --bind 0.0.0.0:8000 \
              --timeout 300 \
              --access-logfile /app/logs/access.log \
              --error-logfile /app/logs/error.log \
              djangoProject4.wsgi:application 