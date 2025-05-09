import json
import logging
import time
from django.http import StreamingHttpResponse, JsonResponse
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
from test_platform.models import APIKey

logger = logging.getLogger(__name__)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def chat_stream(request):
    """
    智能助手流式对话接口
    
    请求参数:
    - messages: 消息历史记录，格式为[{"role": "user", "content": "问题"}, ...]
    - api_key_id: (可选) 指定使用的API密钥ID
    - stream: (可选) 是否使用流式响应，默认为True
    
    流式响应格式: 
    每个响应块为JSON格式，格式为:
    {"content": "部分响应内容", "done": false}
    最后一个块的done为true
    
    非流式响应格式:
    {"code": 200, "message": "success", "data": {"content": "完整响应内容"}}
    """
    try:
        # 解析请求数据
        data = request.data
        messages = data.get('messages', [])
        api_key_id = data.get('api_key_id')
        use_stream = data.get('stream', True)
        
        # 参数验证
        if not messages:
            return JsonResponse({
                'code': 400,
                'message': '消息不能为空',
                'data': None
            }, status=400)
        
        # 获取API密钥配置
        api_key_obj = get_api_key(request.user, api_key_id)
        if not api_key_obj:
            return JsonResponse({
                'code': 400,
                'message': '未找到有效的API密钥配置',
                'data': None
            }, status=400)
        
        # 获取配置参数
        config = get_config_from_api_key(api_key_obj)
        model = config.get('model', 'deepseek-chat')
        temperature = config.get('temperature', 0.7)
        
        # 创建OpenAI客户端
        client = OpenAI(
            api_key=api_key_obj.api_key,
            base_url=api_key_obj.api_base
        )
        
        # 检查是否使用流式响应
        if use_stream:
            # 返回流式响应
            return StreamingHttpResponse(
                stream_response(client, messages, model, temperature),
                content_type='text/event-stream'
            )
        else:
            # 调用模型获取完整响应
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=False
            )
            content = response.choices[0].message.content
            
            # 更新API密钥使用统计
            update_api_key_usage(api_key_obj)
            
            # 返回完整响应
            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'content': content
                }
            })
            
    except Exception as e:
        logger.error(f"智能助手对话失败: {str(e)}", exc_info=True)
        
        # 如果是流式响应，返回错误消息
        if request.data.get('stream', True):
            def error_stream():
                yield json.dumps({
                    'content': f"出错了: {str(e)}",
                    'done': True
                })
            return StreamingHttpResponse(error_stream(), content_type='text/event-stream')
        
        # 非流式响应
        return JsonResponse({
            'code': 500,
            'message': f'智能助手对话失败: {str(e)}',
            'data': None
        }, status=500)

def stream_response(client, messages, model, temperature):
    """
    从大模型获取流式响应，并转换为适当的格式发送给客户端
    
    :param client: OpenAI客户端
    :param messages: 消息历史
    :param model: 模型名称
    :param temperature: 温度参数
    :return: 生成器，产生流式响应
    """
    try:
        # 调用模型API获取流式响应
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True
        )
        
        # 累积的响应文本
        accumulated_content = ""
        
        # 处理每个响应块
        for chunk in response:
            # 提取当前块的内容
            content = chunk.choices[0].delta.content or ""
            accumulated_content += content
            
            # 转换为JSON格式并发送
            yield json.dumps({
                'content': content,
                'done': False
            })
            
            # 添加小延迟，避免浏览器过载
            time.sleep(0.01)
        
        # 发送最后一个块，标记完成
        yield json.dumps({
            'content': '',
            'done': True
        })
        
    except Exception as e:
        logger.error(f"流式响应生成失败: {str(e)}", exc_info=True)
        yield json.dumps({
            'content': f"\n生成响应时出错: {str(e)}",
            'done': True
        })

def get_api_key(user, api_key_id=None):
    """
    获取用户的API密钥配置
    
    :param user: 当前用户
    :param api_key_id: 可选，指定使用的API密钥ID
    :return: APIKey对象或None
    """
    # 如果提供了api_key_id，直接使用该API密钥
    if api_key_id:
        try:
            return APIKey.objects.get(api_key_id=api_key_id, user=user, is_active=True)
        except APIKey.DoesNotExist:
            logger.warning(f"指定的API密钥不存在: {api_key_id}")
            return None
    
    # 尝试获取默认的API密钥 (优先尝试deepseek，然后是其他任何类型)
    api_key_obj = APIKey.objects.filter(
        user=user,
        service_type='deepseek',
        is_active=True,
        is_default=True
    ).first()
    
    # 如果没有找到deepseek默认API密钥，尝试任何默认API密钥
    if not api_key_obj:
        api_key_obj = APIKey.objects.filter(
            user=user,
            is_active=True,
            is_default=True
        ).first()
    
    # 如果仍然没有找到，获取最近创建的活跃API密钥
    if not api_key_obj:
        api_key_obj = APIKey.objects.filter(
            user=user,
            is_active=True
        ).order_by('-create_time').first()
    
    return api_key_obj

def get_config_from_api_key(api_key_obj):
    """
    从API密钥对象中获取配置信息
    
    :param api_key_obj: APIKey对象
    :return: 配置字典
    """
    config = {}
    if hasattr(api_key_obj, 'config') and api_key_obj.config:
        try:
            config = json.loads(api_key_obj.config)
        except json.JSONDecodeError:
            logger.warning(f"API密钥配置JSON解析失败: {api_key_obj.config}")
    
    # 如果是OpenAI类型，设置默认模型为gpt-3.5-turbo
    if api_key_obj.service_type == 'openai' and 'model' not in config:
        config['model'] = 'gpt-3.5-turbo'
    
    # 如果是DeepSeek类型，设置默认模型为deepseek-chat
    elif api_key_obj.service_type == 'deepseek' and 'model' not in config:
        config['model'] = 'deepseek-chat'
    
    # 其他类型设置默认模型
    elif 'model' not in config:
        config['model'] = 'default-model'
    
    return config

def update_api_key_usage(api_key_obj):
    """
    更新API密钥的使用统计
    
    :param api_key_obj: APIKey对象
    """
    try:
        from django.db.models import F
        from django.utils import timezone
        
        APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
            usage_count=F('usage_count') + 1,
            last_used_at=timezone.now()
        )
    except Exception as e:
        logger.error(f"更新API密钥使用统计失败: {str(e)}")
        # 不影响主流程，忽略错误 