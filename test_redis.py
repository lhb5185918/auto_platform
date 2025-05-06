import redis
import sys

def test_redis_connection(host, port, db=0):
    try:
        # 创建Redis连接
        r = redis.Redis(host=host, port=port, db=db)
        
        # 尝试ping服务器
        response = r.ping()
        print(f"Redis连接成功！服务器响应: {response}")
        
        # 尝试简单的set/get操作
        r.set('test_key', 'hello')
        value = r.get('test_key')
        print(f"测试读写操作成功，值为: {value.decode('utf-8')}")
        
        return True
    except redis.exceptions.ConnectionError as e:
        print(f"Redis连接失败: {str(e)}")
        return False
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    # Redis服务器信息
    host = "47.94.195.221"
    port = 6379
    
    print(f"测试Redis连接: {host}:{port}")
    success = test_redis_connection(host, port)
    
    if not success:
        print("\n尝试使用本地Redis...")
        success = test_redis_connection("localhost", 6379)
    
    sys.exit(0 if success else 1) 