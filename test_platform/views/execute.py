from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import requests
from test_platform.models import TestCase, TestResult
from django.utils import timezone

@csrf_exempt
@require_http_methods(["POST"])
def execute_test(request, case_id):
    """
    执行测试用例的接口
    """
    try:
        # 获取测试用例
        try:
            test_case = TestCase.objects.get(test_case_id=case_id)
        except TestCase.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '测试用例不存在'
            }, status=404, charset='utf-8')
            
        # 执行接口请求
        try:
            # 准备请求数据
            url = test_case.case_path
            method = test_case.case_request_method
            
            # 安全解析 headers
            try:
                headers = json.loads(test_case.case_request_headers) if test_case.case_request_headers else {}
            except json.JSONDecodeError:
                headers = {}
            
            # 安全解析 body
            try:
                body = json.loads(test_case.case_requests_body) if test_case.case_requests_body else None
            except json.JSONDecodeError:
                body = test_case.case_requests_body
            
            # 发送请求
            start_time = timezone.now()
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body if method in ['POST', 'PUT', 'PATCH'] else None,
                params=body if method == 'GET' else None
            )
            response.encoding = 'utf-8'
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            # 判断响应状态
            is_success = 200 <= response.status_code < 300
            status = 'PASS' if is_success else 'FAIL'
            
            # 获取响应内容
            content_type = response.headers.get('Content-Type', '')
            
            # 处理响应体
            try:
                if 'application/json' in content_type:
                    response_body = response.json()
                elif 'text/html' in content_type:
                    # 对 HTML 内容进行格式化
                    response_body = {
                        'type': 'html',
                        'content': response.text.strip(),
                        'formatted': True
                    }
                elif 'text/plain' in content_type:
                    response_body = {
                        'type': 'text',
                        'content': response.text.strip()
                    }
                else:
                    response_body = {
                        'type': content_type,
                        'content': response.text.strip()
                    }
            except Exception as e:
                response_body = {
                    'type': 'error',
                    'content': str(e),
                    'raw_content': response.text
                }
            
            # 记录测试结果
            result_data = {
                'request': {
                    'url': url,
                    'method': method,
                    'headers': headers,
                    'body': body
                },
                'response': {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'content_type': content_type,
                    'body': response_body,
                    'response_time': duration
                }
            }
            
            test_result = TestResult.objects.create(
                case=test_case,
                execution_time=start_time,
                status=status,
                duration=duration,
                result_data=json.dumps(result_data, ensure_ascii=False),
                error_message=None if is_success else f'HTTP状态码: {response.status_code}'
            )
            
            return JsonResponse({
                'success': True,
                'message': '测试用例执行成功',
                'data': {
                    'result_id': test_result.test_result_id,
                    'status': status,
                    'duration': duration,
                    'execution_time': test_result.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'request': {
                        'url': url,
                        'method': method,
                        'headers': headers,
                        'body': body
                    },
                    'response': {
                        'status_code': response.status_code,
                        'content_type': content_type,
                        'response_time': duration,
                        'headers': dict(response.headers),
                        'body': response_body
                    }
                }
            }, charset='utf-8', json_dumps_params={'ensure_ascii': False})
            
        except requests.RequestException as e:
            # 记录请求失败的结果
            test_result = TestResult.objects.create(
                case=test_case,
                execution_time=timezone.now(),
                status='ERROR',
                result_data=json.dumps({
                    'error': str(e),
                    'request': {
                        'url': url,
                        'method': method,
                        'headers': headers,
                        'body': body
                    }
                }, ensure_ascii=False),
                error_message=str(e)
            )
            
            return JsonResponse({
                'success': False,
                'message': f'请求执行失败: {str(e)}',
                'data': {
                    'result_id': test_result.test_result_id,
                    'status': 'ERROR',
                    'error': str(e),
                    'request': {
                        'url': url,
                        'method': method,
                        'headers': headers,
                        'body': body
                    }
                }
            }, status=500, charset='utf-8', json_dumps_params={'ensure_ascii': False})
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'执行测试用例时发生错误: {str(e)}',
            'data': {
                'error': str(e),
                'case_id': case_id
            }
        }, status=500, charset='utf-8', json_dumps_params={'ensure_ascii': False})

@csrf_exempt
@require_http_methods(["POST"])
def execute_test_direct(request):
    """
    直接执行测试的接口，使用传入的参数
    请求体格式：
    {
        "api_path": "接口路径",
        "method": "请求方法",
        "headers": [{"key": "key1", "value": "value1", "enabled": true}],
        "params": [{"key": "key1", "value": "value1", "enabled": true}],
        "body": "请求体",
        "body_type": "none/form-data/raw",
        "raw_content_type": "application/json",
        "form_data": [{"key": "key1", "value": "value1", "enabled": true}]
    }
    """
    try:
        # 解析请求数据
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': '无效的请求数据格式'
            }, status=400, charset='utf-8')

        # 准备请求数据
        url = data.get('api_path')
        method = data.get('method', 'GET')
        
        # 处理 headers
        headers = {}
        for header in data.get('headers', []):
            if header.get('enabled', True) and header.get('key'):
                headers[header['key']] = header['value']
                
        # 处理查询参数
        params = {}
        for param in data.get('params', []):
            if param.get('enabled', True) and param.get('key'):
                params[param['key']] = param['value']
        
        # 处理请求体
        body = None
        body_type = data.get('body_type', 'none')
        if body_type == 'raw':
            try:
                body = json.loads(data.get('body', '{}'))
            except json.JSONDecodeError:
                body = data.get('body')
        elif body_type == 'form-data':
            body = {}
            for form_item in data.get('form_data', []):
                if form_item.get('enabled', True) and form_item.get('key'):
                    body[form_item['key']] = form_item['value']
        
        # 发送请求
        try:
            start_time = timezone.now()
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=body if method in ['POST', 'PUT', 'PATCH'] and body_type == 'raw' else None,
                data=body if method in ['POST', 'PUT', 'PATCH'] and body_type == 'form-data' else None
            )
            response.encoding = 'utf-8'
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()
            
            # 判断响应状态
            is_success = 200 <= response.status_code < 300
            status = 'PASS' if is_success else 'FAIL'
            
            # 处理响应体
            content_type = response.headers.get('Content-Type', '')
            try:
                if 'application/json' in content_type:
                    response_body = response.json()
                elif 'text/html' in content_type:
                    response_body = {
                        'type': 'html',
                        'content': response.text.strip(),
                        'formatted': True
                    }
                elif 'text/plain' in content_type:
                    response_body = {
                        'type': 'text',
                        'content': response.text.strip()
                    }
                else:
                    response_body = {
                        'type': content_type,
                        'content': response.text.strip()
                    }
            except Exception as e:
                response_body = {
                    'type': 'error',
                    'content': str(e),
                    'raw_content': response.text
                }
            
            return JsonResponse({
                'success': True,
                'message': '测试执行成功',
                'data': {
                    'status': status,
                    'duration': duration,
                    'execution_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'request': {
                        'url': url,
                        'method': method,
                        'headers': headers,
                        'params': params,
                        'body': body,
                        'body_type': body_type
                    },
                    'response': {
                        'status_code': response.status_code,
                        'content_type': content_type,
                        'response_time': duration,
                        'headers': dict(response.headers),
                        'body': response_body
                    }
                }
            }, charset='utf-8', json_dumps_params={'ensure_ascii': False})
            
        except requests.RequestException as e:
            return JsonResponse({
                'success': False,
                'message': f'请求执行失败: {str(e)}',
                'data': {
                    'status': 'ERROR',
                    'error': str(e),
                    'request': {
                        'url': url,
                        'method': method,
                        'headers': headers,
                        'params': params,
                        'body': body,
                        'body_type': body_type
                    }
                }
            }, status=500, charset='utf-8', json_dumps_params={'ensure_ascii': False})
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'执行测试时发生错误: {str(e)}',
            'data': {
                'error': str(e)
            }
        }, status=500, charset='utf-8', json_dumps_params={'ensure_ascii': False})
