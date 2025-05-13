#!/bin/bash
set -e

# 检查DNS是否能解析Redis主机名
echo "验证Redis主机名DNS解析..."
if [[ "${REDIS_HOST}" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Redis主机是IP地址，跳过DNS检查"
else
  echo "尝试解析Redis主机名: ${REDIS_HOST}"
  if ! nslookup ${REDIS_HOST} > /dev/null 2>&1; then
    echo "警告: 无法解析Redis主机名，尝试使用/etc/hosts中的映射"
    echo "当前hosts配置:"
    cat /etc/hosts
  else
    echo "Redis主机名解析成功"
  fi
fi

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

# 等待Web服务启动
echo "等待Web服务启动..."
sleep 5

echo "启动Celery worker..."
cd /app
exec celery -A djangoProject4 worker --loglevel=info 