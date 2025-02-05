from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import requests
from test_platform.models import TestCase, TestResult
from django.utils import timezone
from django.db import connection
import pytz


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
    try:
        # 设置会话时区
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+08:00'")
            
        # 获取北京时区
        beijing_tz = pytz.timezone('Asia/Shanghai')
        current_time = timezone.localtime(timezone.now())  # 使用 localtime 获取本地时间
            
        # 解析请求数据
        test_data = json.loads(request.body)
        
        # 获取测试用例信息
        case_id = test_data.get('case_id')
        api_path = test_data.get('api_path')
        method = test_data.get('method', 'GET').upper()
        
        # 获取测试用例对象
        try:
            test_case = TestCase.objects.get(test_case_id=case_id)
        except TestCase.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '测试用例不存在',
                'data': {'error': f'找不到ID为{case_id}的测试用例'}
            })
        
        # 处理 headers
        headers = {}
        headers_list = test_data.get('headers', [])
        if isinstance(headers_list, list):
            for header in headers_list:
                if isinstance(header, dict) and header.get('key'):
                    headers[header['key']] = header['value']
        elif isinstance(headers_list, dict):
            headers = headers_list

        # 处理 params
        params = {}
        params_list = test_data.get('params', [])
        if isinstance(params_list, list):
            for param in params_list:
                if isinstance(param, dict) and param.get('key'):
                    params[param['key']] = param['value']
        elif isinstance(params_list, dict):
            params = params_list

        # 处理 body
        body = test_data.get('body', {})
        body_type = test_data.get('body_type', 'none')
        
        if isinstance(body, str):
            try:
                body = json.loads(body) if body else {}
            except json.JSONDecodeError:
                body = {}

        # 处理 form-data
        if body_type == 'form-data':
            form_data = {}
            for item in test_data.get('form_data', []):
                if isinstance(item, dict) and item.get('key'):
                    form_data[item['key']] = item['value']
            body = form_data

        # 准备请求参数
        request_kwargs = {
            'url': api_path,
            'headers': headers,
            'params': params,
        }

        # 根据不同的HTTP方法和body_type添加相应的参数
        if method in ['POST', 'PUT', 'PATCH']:
            if body_type == 'form-data':
                request_kwargs['data'] = body
            else:
                request_kwargs['json'] = body
        
        # 记录开始时间
        start_time = timezone.now()
        
        # 发送请求
        response = requests.request(method, **request_kwargs)
        
        # 计算执行时间
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        # 判断响应状态
        is_success = 200 <= response.status_code < 300
        status = 'PASS' if is_success else 'FAIL'
        
        # 尝试解析响应为JSON
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = response.text

        # 更新测试用例的执行时间和状态
        try:
            print(f"当前时间: {current_time}")
            # 使用 raw SQL 来更新，避免 Django ORM 的时区转换
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE test_platform_testcase 
                    SET last_executed_at = %s,
                        last_execution_result = %s,
                        update_time = %s
                    WHERE test_case_id = %s
                """, [current_time, status.lower(), current_time, case_id])
            
            updated_case = TestCase.objects.get(test_case_id=case_id)
            print(f"更新后状态: {updated_case.last_executed_at}, {updated_case.last_execution_result}")
        except Exception as e:
            print(f"更新测试用例状态失败: {str(e)}")

        # 记录测试结果
        result_data = {
            'request': {
                'url': api_path,
                'method': method,
                'headers': headers,
                'params': params,
                'body': body,
                'body_type': body_type
            },
            'response': {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'body': response_data,
                'response_time': duration
            }
        }

        # 创建测试结果记录，同样使用 raw SQL
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO test_platform_testresult 
                (case_id, execution_time, status, duration, result_data, error_message, create_time, update_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                test_case.test_case_id,
                current_time,
                status,  # 使用正确的状态
                duration,  # 添加持续时间
                json.dumps(result_data, ensure_ascii=False),  # 使用正确的结果数据
                None if is_success else f'HTTP状态码: {response.status_code}',
                current_time,  # create_time
                current_time   # update_time
            ])
            
            # 获取最后插入的 ID
            test_result_id = cursor.lastrowid

        # 构建响应结果
        result = {
            'success': True,
            'message': '测试执行成功',
            'data': {
                'result_id': test_result_id,
                'status': status,
                'duration': duration,
                'execution_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'status_code': response.status_code,
                'response': response_data,
                'headers': dict(response.headers),
                'request': {
                    'method': method,
                    'url': api_path,
                    'headers': headers,
                    'params': params,
                    'body': body,
                    'body_type': body_type
                }
            }
        }

        return JsonResponse(result, json_dumps_params={'ensure_ascii': False})

    except requests.RequestException as e:
        if 'test_case' in locals():
            try:
                current_time = timezone.localtime(timezone.now())
                # 使用 raw SQL 更新错误状态
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE test_platform_testcase 
                        SET last_executed_at = %s,
                            last_execution_result = 'error',
                            update_time = %s
                        WHERE test_case_id = %s
                    """, [current_time, current_time, case_id])
                    
                    cursor.execute("""
                        INSERT INTO test_platform_testresult 
                        (case_id, execution_time, status, result_data, error_message, create_time, update_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, [
                        test_case.test_case_id,
                        current_time,
                        'ERROR',
                        json.dumps({
                            'error': str(e),
                            'request': {
                                'url': api_path,
                                'method': method,
                                'headers': headers,
                                'params': params,
                                'body': body
                            }
                        }, ensure_ascii=False),
                        str(e),
                        current_time,  # create_time
                        current_time   # update_time
                    ])
            except Exception as update_error:
                print(f"更新测试用例状态失败: {str(update_error)}")

        return JsonResponse({
            'success': False,
            'message': f'请求发送失败: {str(e)}',
            'data': {
                'error': str(e)
            }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'执行测试时发生错误: {str(e)}',
            'data': {
                'error': str(e)
            }
        })

def set_timezone():
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+08:00'")
