from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import requests
from test_platform.models import TestCase, TestResult, TestSuite, TestSuiteCase, TestSuiteResult
from django.utils import timezone
from django.db import connection
import pytz


@csrf_exempt
@require_http_methods(["GET"])
def get_suite_result_response(request, result_id):
    """
    获取测试套件结果的响应数据
    """
    try:
        # 获取测试套件结果记录
        try:
            suite_result = TestSuiteResult.objects.get(result_id=result_id)
        except TestSuiteResult.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '测试结果不存在',
                'data': None
            }, status=404, charset='utf-8')
        
        # 解析结果数据
        try:
            result_data = json.loads(suite_result.result_data) if suite_result.result_data else {}
        except json.JSONDecodeError:
            result_data = {}
        
        # 从结果数据中提取请求和响应信息
        # 首先尝试获取最新的结果数据格式
        request_data = result_data.get('request', {})
        response_data = result_data.get('response', {})
        
        # 如果新格式不存在，尝试从详细结果中获取第一个用例的数据
        if not request_data and not response_data:
            case_results = result_data.get('case_results', [])
            if case_results and len(case_results) > 0:
                # 获取第一个用例的结果
                first_case = case_results[0]
                request_data = first_case.get('request', {})
                response_data = first_case.get('response', {})
        
        # 标准化请求数据
        request_info = {
            'case_id': request_data.get('case_id', ''),
            'api_path': request_data.get('api_path', request_data.get('url', '')),
            'method': request_data.get('method', ''),
            'headers': request_data.get('headers', {}),
            'params': request_data.get('params', {}),
            'body': request_data.get('body', {}),
            'body_type': request_data.get('body_type', 'json'),
            'assertions': request_data.get('assertions', ''),
            'tests': request_data.get('tests', []),
            'extractors': request_data.get('extractors', [])
        }
        
        # 标准化响应数据
        response_info = {
            'status_code': response_data.get('status_code', 0),
            'headers': response_data.get('headers', {}),
            'body': response_data.get('body', {}),
            'response_time': response_data.get('response_time', 0),
            'raw_text': response_data.get('raw_text', '')
        }
        
        # 构建响应
        result = {
            'code': 200,
            'message': 'success',
            'data': {
                'request': request_info,
                'response': response_info,
                'execution_time': suite_result.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': suite_result.status,
                'duration': suite_result.duration,
                'suite_id': suite_result.suite.suite_id,
                'suite_name': suite_result.suite.name
            }
        }
        
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False})
    
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'获取测试结果响应失败: {str(e)}',
            'data': None
        }, status=500, charset='utf-8', json_dumps_params={'ensure_ascii': False})


@csrf_exempt
@require_http_methods(["GET"])
def get_suite_detail(request, suite_id):
    """
    获取测试套件详情的接口
    """
    try:
        # 获取测试套件
        try:
            test_suite = TestSuite.objects.get(suite_id=suite_id)
        except TestSuite.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '测试套件不存在',
                'data': None
            }, status=404, charset='utf-8')

        # 获取套件关联的测试用例
        suite_cases = test_suite.suite_cases.all().order_by('order')
        
        # 准备用例数据
        case_list = []
        for suite_case in suite_cases:
            # 尝试获取原始测试用例
            try:
                case = TestCase.objects.get(test_case_id=suite_case.original_case_id)
                
                # 解析 JSON 字段
                try:
                    headers = json.loads(case.case_request_headers) if case.case_request_headers else {}
                except json.JSONDecodeError:
                    headers = {}
                
                try:
                    body = json.loads(case.case_requests_body) if case.case_requests_body else {}
                except json.JSONDecodeError:
                    body = case.case_requests_body
                
                try:
                    assert_contents = json.loads(case.case_assert_contents) if case.case_assert_contents else {}
                except json.JSONDecodeError:
                    assert_contents = case.case_assert_contents
                
                # 添加用例信息到列表
                case_list.append({
                    'case_id': case.test_case_id,
                    'title': case.case_name,
                    'method': case.case_request_method,
                    'api_path': case.case_path,
                    'priority': case.case_priority,
                    'description': case.case_description,
                    'status': case.case_status,
                    'last_executed_at': case.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if case.last_executed_at else None,
                    'last_execution_result': case.last_execution_result,
                    'headers': headers,
                    'body': body,
                    'case_assert_contents': assert_contents
                })
            except TestCase.DoesNotExist:
                # 如果原始用例不存在，使用关联表中的数据
                case_data = json.loads(suite_case.case_data) if suite_case.case_data else {}
                
                case_list.append({
                    'case_id': suite_case.original_case_id,
                    'title': case_data.get('name', '未知用例'),
                    'method': case_data.get('method', 'GET'),
                    'api_path': case_data.get('api_path', ''),
                    'priority': case_data.get('priority', 0),
                    'description': case_data.get('description', ''),
                    'status': case_data.get('status', 0),
                    'is_missing': True  # 标记原始用例不存在
                })
        
        # 准备环境信息
        env_info = None
        if test_suite.environment:
            env_info = {
                'env_id': test_suite.environment.environment_id,
                'name': test_suite.environment.env_name,
                'host': test_suite.environment.host,
                'port': test_suite.environment.port,
                'base_url': test_suite.environment.base_url
            }
        
        # 构建响应数据
        result = {
            'code': 200,
            'message': 'success',
            'data': {
                'suite_id': test_suite.suite_id,
                'name': test_suite.name,
                'description': test_suite.description or '',
                'env_id': test_suite.environment.environment_id if test_suite.environment else None,
                'environment': env_info,
                'project_id': test_suite.project.project_id,
                'project_name': test_suite.project.name,
                'create_time': test_suite.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'update_time': test_suite.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                'creator': test_suite.creator.username if test_suite.creator else None,
                'last_executed_at': test_suite.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if test_suite.last_executed_at else None,
                'last_execution_status': test_suite.last_execution_status,
                'cases': case_list
            }
        }
        
        return JsonResponse(result, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'获取测试套件详情失败: {str(e)}',
            'data': None
        }, status=500, charset='utf-8', json_dumps_params={'ensure_ascii': False})


@csrf_exempt
@require_http_methods(["PUT", "POST"])
def update_suite_case(request, case_id):
    """
    更新测试套件中的测试用例
    """
    try:
        # 获取测试用例
        try:
            test_case = TestCase.objects.get(test_case_id=case_id)
        except TestCase.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '测试用例不存在',
                'data': None
            }, status=404, charset='utf-8')
        
        # 获取请求数据
        try:
            body_data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({
                'code': 400,
                'message': '请求数据格式错误',
                'data': None
            }, status=400, charset='utf-8')
        
        # 提取请求字段
        case_title = body_data.get('title', '')
        case_method = body_data.get('method', '')
        case_api_path = body_data.get('api_path', '')
        case_headers = body_data.get('headers', {})
        case_params = body_data.get('params', {})
        case_expected = body_data.get('expected', '')
        case_body = body_data.get('body', {})
        case_priority = body_data.get('priority', '')
        
        # 可选字段：测试套件ID
        suite_id = body_data.get('suite_id')
        
        # 更新测试用例基本信息（原始用例）
        test_case.case_name = case_title
        test_case.case_request_method = case_method
        test_case.case_path = case_api_path
        
        # 处理字段格式
        # Headers 处理 - 确保以 JSON 对象格式存储
        if isinstance(case_headers, dict) or isinstance(case_headers, list):
            # 存储为 JSON 字符串 - 直接转换
            test_case.case_request_headers = json.dumps(case_headers)
        elif isinstance(case_headers, str):
            # 如果已经是字符串，检查是否是有效的 JSON
            try:
                # 尝试解析并重新序列化，确保格式统一
                headers_obj = json.loads(case_headers)
                test_case.case_request_headers = json.dumps(headers_obj)
            except json.JSONDecodeError:
                # 不是有效的 JSON，存储为空 JSON 对象
                test_case.case_request_headers = '{}'
        else:
            test_case.case_request_headers = '{}'
        
        # Params 处理
        if isinstance(case_params, dict) or isinstance(case_params, list):
            test_case.case_params = json.dumps(case_params)
        elif isinstance(case_params, str):
            try:
                params_obj = json.loads(case_params)
                test_case.case_params = json.dumps(params_obj)
            except json.JSONDecodeError:
                test_case.case_params = '{}'
        else:
            test_case.case_params = '{}'
        
        # Body 处理
        if isinstance(case_body, dict) or isinstance(case_body, list):
            test_case.case_requests_body = json.dumps(case_body)
        elif isinstance(case_body, str):
            # 字符串类型的 body 可能是已经格式化的 JSON 或普通文本
            try:
                body_obj = json.loads(case_body)
                test_case.case_requests_body = json.dumps(body_obj)
            except json.JSONDecodeError:
                # 不是有效的 JSON，保留原始字符串
                test_case.case_requests_body = case_body
        else:
            test_case.case_requests_body = '{}'
        
        # 预期结果处理
        test_case.case_expect_result = case_expected
        
        # 优先级处理
        priority_map = {'低': 0, '中': 1, '高': 2}
        test_case.case_priority = priority_map.get(case_priority, 0)
        
        # 保存更新后的测试用例
        test_case.save()
        
        # 如果提供了套件ID，则更新测试套件中的用例数据
        if suite_id:
            try:
                # 查找测试套件中的用例关联记录
                suite_case = TestSuiteCase.objects.get(suite_id=suite_id, original_case_id=case_id)
                
                # 构建用例数据 - 将 JSON 对象存储在套件用例数据中
                case_data = {
                    'title': case_title,
                    'name': case_title,
                    'method': case_method,
                    'api_path': case_api_path,
                    'headers': case_headers,  # 直接存储对象，不要转字符串
                    'params': case_params,
                    'expected': case_expected,
                    'body': case_body,
                    'priority': case_priority,
                    # 保留原有数据中的其他字段
                    'original_case_id': case_id
                }
                
                # 更新套件用例数据
                suite_case.case_data = json.dumps(case_data)
                suite_case.save()
                
                # 准备返回数据
                response_data = {
                    'case_id': case_id,
                    'suite_id': suite_id,
                    'title': case_title,
                    'headers': case_headers,  # 返回原始对象
                    'params': case_params,
                    'body': case_body
                }
                
                return JsonResponse({
                    'code': 200,
                    'message': '测试套件用例更新成功',
                    'data': response_data
                }, charset='utf-8', json_dumps_params={'ensure_ascii': False})
            except TestSuiteCase.DoesNotExist:
                # 如果找不到关联记录，只更新原始用例
                return JsonResponse({
                    'code': 200,
                    'message': '测试用例更新成功，但未找到关联的测试套件用例',
                    'data': {
                        'case_id': case_id,
                        'title': case_title,
                        'headers': case_headers,  # 返回原始对象
                        'params': case_params,
                        'body': case_body
                    }
                }, charset='utf-8', json_dumps_params={'ensure_ascii': False})
        else:
            # 如果没有提供套件ID，则只更新原始用例
            return JsonResponse({
                'code': 200,
                'message': '测试用例更新成功',
                'data': {
                    'case_id': case_id,
                    'title': case_title,
                    'headers': case_headers,  # 返回原始对象
                    'params': case_params,
                    'body': case_body
                }
            }, charset='utf-8', json_dumps_params={'ensure_ascii': False})
    
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'更新测试用例失败: {str(e)}',
            'data': {
                'error': str(e)
            }
        }, status=500, charset='utf-8', json_dumps_params={'ensure_ascii': False})


def set_timezone():
    """设置数据库会话时区为北京时间"""
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+08:00'")

@csrf_exempt
@require_http_methods(["POST"])
def execute_test(request, case_id):
    """
    执行测试用例的接口
    """
    # 确保数据库会话使用正确的时区
    set_timezone()
    
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
            start_time = timezone.localtime(timezone.now())  # 使用本地时间(北京时间)
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body if method in ['POST', 'PUT', 'PATCH'] else None,
                params=body if method == 'GET' else None
            )
            response.encoding = 'utf-8'
            end_time = timezone.localtime(timezone.now())  # 使用本地时间(北京时间)
            duration = (end_time - start_time).total_seconds()

            # 首先根据HTTP状态码判断响应状态
            is_http_success = 200 <= response.status_code < 300
            
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
            
            # 处理测试断言
            assertion_results = []
            has_assertions = False
            assertions_passed = True
            assertion_error = None
            
            # 检查是否有测试断言 - 直接从测试用例中获取
            try:
                # 判断case_tests字段是否有值
                has_assertions = bool(test_case.case_tests and test_case.case_tests.strip())
                
                # 如果有断言表达式，则执行断言判断
                if has_assertions:
                    print(f"发现测试断言表达式: {test_case.case_tests}")
                    
                    # 解析断言表达式
                    test_assertions = []
                    try:
                        # 尝试解析JSON格式断言
                        test_assertions = json.loads(test_case.case_tests)
                        if not isinstance(test_assertions, list):
                            test_assertions = [test_assertions]
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，尝试解析简单表达式
                        simple_assertion = test_case.case_tests.strip()
                        
                        # 处理简单断言表达式
                        if simple_assertion.startswith("=="):
                            # 状态码等于断言
                            expected_value = simple_assertion[2:].strip()
                            test_assertions = [{
                                "type": "status_code",
                                "expect": expected_value,
                                "actual": "status_code"
                            }]
                        elif simple_assertion.startswith("contains"):
                            # 包含断言
                            expected_value = simple_assertion[8:].strip()
                            test_assertions = [{
                                "type": "contains",
                                "expect": expected_value,
                                "actual": ""
                            }]
                        elif "$." in simple_assertion:
                            # JSONPath断言
                            parts = simple_assertion.split("==")
                            if len(parts) == 2:
                                jsonpath = parts[0].strip()
                                expected = parts[1].strip()
                                test_assertions = [{
                                    "type": "jsonpath",
                                    "expect": expected,
                                    "actual": jsonpath
                                }]
                    
                    # 导入jsonpath模块用于解析JSON数据
                    import jsonpath_ng.ext as jsonpath
                    import re
                    
                    # 逐个执行断言
                    for assertion in test_assertions:
                        assertion_type = assertion.get('type', '')
                        expect = assertion.get('expect', '')
                        actual = assertion.get('actual', '')
                        
                        # 不同类型的断言处理
                        if assertion_type == 'jsonpath':
                            # 使用jsonpath提取实际值
                            try:
                                json_expr = jsonpath.parse(actual)
                                matches = [match.value for match in json_expr.find(response_body)]
                                actual_value = matches[0] if matches else None
                                
                                # 比较预期值和实际值
                                if actual_value is not None:
                                    # 尝试将字符串转换为相应类型进行比较
                                    try:
                                        if isinstance(actual_value, (int, float)):
                                            expect_value = float(expect)
                                        elif isinstance(actual_value, bool):
                                            expect_value = expect.lower() == 'true'
                                        else:
                                            expect_value = expect
                                                
                                        assertion_pass = actual_value == expect_value
                                    except:
                                        # 如果转换失败，直接比较字符串
                                        assertion_pass = str(actual_value) == expect
                                else:
                                    assertion_pass = False
                                    
                                assertion_results.append({
                                    'type': assertion_type,
                                    'expect': expect,
                                    'actual': actual,
                                    'actual_value': actual_value,
                                    'success': assertion_pass,
                                    'message': '断言通过' if assertion_pass else f'断言失败: 期望值 {expect}, 实际值 {actual_value}'
                                })
                                
                                if not assertion_pass:
                                    assertions_passed = False
                                    assertion_error = f'JsonPath断言失败: {actual} 的值 {actual_value} 不等于期望值 {expect}'
                            except Exception as e:
                                assertions_passed = False
                                error_msg = f'JsonPath断言执行异常: {str(e)}'
                                assertion_results.append({
                                    'type': assertion_type,
                                    'expect': expect,
                                    'actual': actual,
                                    'success': False,
                                    'message': error_msg
                                })
                                assertion_error = error_msg
                        
                        elif assertion_type == 'status_code':
                            # 校验HTTP状态码
                            actual_status = response.status_code
                            expected_status = int(expect)
                            assertion_pass = actual_status == expected_status
                            
                            assertion_results.append({
                                'type': assertion_type,
                                'expect': expected_status,
                                'actual': actual_status,
                                'success': assertion_pass,
                                'message': '断言通过' if assertion_pass else f'断言失败: 期望状态码 {expected_status}, 实际状态码 {actual_status}'
                            })
                            
                            if not assertion_pass:
                                assertions_passed = False
                                assertion_error = f'状态码断言失败: 期望 {expected_status}, 实际 {actual_status}'
                        
                        elif assertion_type == 'contains':
                            # 检查响应文本是否包含指定内容
                            response_text = response.text
                            assertion_pass = expect in response_text
                            
                            assertion_results.append({
                                'type': assertion_type,
                                'expect': expect,
                                'actual': '响应文本',
                                'success': assertion_pass,
                                'message': '断言通过' if assertion_pass else f'断言失败: 响应文本不包含 {expect}'
                            })
                            
                            if not assertion_pass:
                                assertions_passed = False
                                assertion_error = f'包含断言失败: 响应文本不包含 {expect}'
                        
                        elif assertion_type == 'regex':
                            # 正则表达式匹配
                            response_text = response.text
                            try:
                                pattern = re.compile(expect)
                                assertion_pass = bool(pattern.search(response_text))
                                
                                assertion_results.append({
                                    'type': assertion_type,
                                    'expect': expect,
                                    'actual': '响应文本',
                                    'success': assertion_pass,
                                    'message': '断言通过' if assertion_pass else f'断言失败: 响应文本不匹配正则表达式 {expect}'
                                })
                                
                                if not assertion_pass:
                                    assertions_passed = False
                                    assertion_error = f'正则断言失败: 响应文本不匹配 {expect}'
                            except re.error as e:
                                assertions_passed = False
                                error_msg = f'正则表达式错误: {str(e)}'
                                assertion_results.append({
                                    'type': assertion_type,
                                    'expect': expect,
                                    'actual': '响应文本',
                                    'success': False,
                                    'message': error_msg
                                })
                                assertion_error = error_msg
                        
                        # 修复：如果有断言定义但没有执行任何断言（结果为空），则使用HTTP状态码判断
                        if has_assertions and not assertion_results:
                            assertions_passed = is_http_success
                            if not is_http_success:
                                assertion_error = f'HTTP状态码: {response.status_code} 不在成功范围内'
                            
                            # 添加一个默认的HTTP状态码断言结果
                            assertion_results.append({
                                'type': 'status_code',
                                'expect': '200-299',
                                'actual': response.status_code,
                                'success': is_http_success,
                                'message': '断言通过' if is_http_success else f'断言失败: HTTP状态码 {response.status_code} 不在成功范围内'
                            })
                            
            except Exception as e:
                print(f"断言处理发生异常: {str(e)}")
                # 断言处理异常，不影响原有逻辑，仍然根据HTTP状态码判断
                has_assertions = False
            
            # 根据是否有断言和断言结果判断最终状态
            if has_assertions:
                # 使用断言结果判断
                status = 'PASS' if assertions_passed else 'FAIL'
                is_success = assertions_passed
            else:
                # 没有断言，使用HTTP状态码判断
                status = 'PASS' if is_http_success else 'FAIL'
                is_success = is_http_success

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
                },
                'assertions': {
                    'has_assertions': has_assertions,
                    'all_passed': assertions_passed,
                    'results': assertion_results,
                    'error': assertion_error
                }
            }

            test_result = TestResult.objects.create(
                case=test_case,
                execution_time=start_time,
                status=status,
                duration=duration,
                result_data=json.dumps(result_data, ensure_ascii=False),
                error_message=None if is_success else (
                    assertion_error if has_assertions and not assertions_passed 
                    else f'HTTP状态码: {response.status_code}'
                )
            )

            # 更新测试用例的执行时间和状态
            try:
                # 保存断言结果到测试用例
                assertion_results_json = json.dumps({
                    'has_assertions': has_assertions,
                    'all_passed': assertions_passed,
                    'results': assertion_results,
                    'error': assertion_error
                }, ensure_ascii=False)
                
                # 使用 raw SQL 来更新，避免 Django ORM 的时区转换
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE test_platform_testcase 
                        SET last_executed_at = %s,
                            last_execution_result = %s,
                            last_assertion_results = %s,
                            update_time = %s
                        WHERE test_case_id = %s
                    """, [start_time, status.lower(), assertion_results_json, timezone.localtime(timezone.now()), test_case.test_case_id])
                
                print(f"已更新测试用例状态: {test_case.test_case_id}, 状态: {status.lower()}, 时间: {start_time}")
            except Exception as e:
                print(f"更新测试用例状态失败: {str(e)}")

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
                    },
                    'assertions': {
                        'has_assertions': has_assertions,
                        'all_passed': assertions_passed,
                        'results': assertion_results
                    }
                }
            }, charset='utf-8', json_dumps_params={'ensure_ascii': False})

        except requests.RequestException as e:
            # 记录请求失败的结果
            current_time = timezone.localtime(timezone.now())
            test_result = TestResult.objects.create(
                case=test_case,
                execution_time=current_time,
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

            # 更新测试用例的执行时间和状态为错误
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE test_platform_testcase 
                        SET last_executed_at = %s,
                            last_execution_result = 'error',
                            last_assertion_results = %s,
                            update_time = %s
                        WHERE test_case_id = %s
                    """, [
                        current_time, 
                        json.dumps({
                            'has_assertions': False, 
                            'all_passed': False,
                            'results': [],
                            'error': str(e)
                        }, ensure_ascii=False),
                        current_time, 
                        test_case.test_case_id
                    ])
                
                print(f"已更新测试用例状态: {test_case.test_case_id}, 状态: error, 时间: {current_time}")
            except Exception as e:
                print(f"更新测试用例状态失败: {str(e)}")

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
# Remove the HTTP method restriction to support all request types
def execute_test_direct(request):
    try:
        # 设置会话时区
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+08:00'")
            
        # 获取北京时区
        beijing_tz = pytz.timezone('Asia/Shanghai')
        current_time = timezone.localtime(timezone.now())  # 使用 localtime 获取本地时间
        
        # 打印请求信息，帮助调试
        print(f"收到请求: 方法={request.method}, 路径={request.path}")
            
        # 解析请求数据
        try:
            # 尝试解析请求体，同时处理空请求体的情况
            if hasattr(request, 'body') and request.body:
                test_data = json.loads(request.body)
            else:
                # 如果请求体为空，则使用请求对象中的data属性
                test_data = request.data if hasattr(request, 'data') else {}
        except json.JSONDecodeError:
            # 如果JSON解析失败，尝试从request.data获取数据
            test_data = getattr(request, 'data', {})
            if not isinstance(test_data, dict):
                test_data = {}
        
        # 从请求对象中直接获取HTTP方法，而不是从测试数据中获取
        # 这样才能正确支持各种HTTP方法
        method = request.method
                
        # 记录请求数据，便于调试    
        print(f"接收到的测试数据: {test_data}")
        
        # 获取测试用例信息
        case_id = test_data.get('case_id')
        api_path = test_data.get('api_path') or request.path
        
        print(f"执行请求: 方法={method}, 路径={api_path}")
        
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
        # 首先从请求对象中获取头信息
        if hasattr(request, 'headers'):
            headers = dict(request.headers)
            
        # 然后从测试数据中获取头信息
        headers_list = test_data.get('headers', [])
        if isinstance(headers_list, list):
            for header in headers_list:
                if isinstance(header, dict) and header.get('key'):
                    headers[header['key']] = header['value']
        elif isinstance(headers_list, dict):
            headers.update(headers_list)

        # 处理 params
        params = {}
        # 首先从请求对象中获取GET参数
        if hasattr(request, 'GET'):
            params = dict(request.GET)
            
        # 然后从测试数据中获取参数
        params_list = test_data.get('params', [])
        if isinstance(params_list, list):
            for param in params_list:
                if isinstance(param, dict) and param.get('key'):
                    params[param['key']] = param['value']
        elif isinstance(params_list, dict):
            params.update(params_list)

        # 处理 body
        body = {}
        
        # 根据请求方法处理请求体
        if method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            # 首先从请求对象中获取请求体
            if hasattr(request, 'body') and request.body:
                try:
                    body = json.loads(request.body)
                except json.JSONDecodeError:
                    body = {}
                    
            # 然后从测试数据中获取请求体
            test_body = test_data.get('body', {})
            if isinstance(test_body, str):
                try:
                    test_body = json.loads(test_body) if test_body else {}
                except json.JSONDecodeError:
                    test_body = {}
                    
            # 如果测试数据中提供了请求体，优先使用它
            if test_body:
                body = test_body
                
        body_type = test_data.get('body_type', 'json')

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
        if method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            if body_type == 'form-data':
                request_kwargs['data'] = body
            else:
                request_kwargs['json'] = body
        
        # 记录开始时间
        start_time = timezone.localtime(timezone.now())  # 使用本地时间(北京时间)
        
        # 发送请求
        response = requests.request(method, **request_kwargs)
        
        # 计算执行时间
        end_time = timezone.localtime(timezone.now())  # 使用本地时间(北京时间)
        duration = (end_time - start_time).total_seconds()
        
        # 首先根据HTTP状态码判断响应状态
        is_http_success = 200 <= response.status_code < 300
        
        # 尝试解析响应为JSON
        try:
            response_data = response.json()
            response_body = response_data
        except json.JSONDecodeError:
            response_data = response.text
            response_body = {'content': response.text}
        
        # 处理测试断言
        assertion_results = []
        has_assertions = False
        assertions_passed = True
        assertion_error = None
        
        # 检查是否有测试断言 - 直接从测试用例中获取
        try:
            # 判断case_tests字段是否有值
            has_assertions = bool(test_case.case_tests and test_case.case_tests.strip())
            
            # 如果有断言表达式，则执行断言判断
            if has_assertions:
                print(f"发现测试断言表达式: {test_case.case_tests}")
                
                # 解析断言表达式
                test_assertions = []
                try:
                    # 尝试解析JSON格式断言
                    test_assertions = json.loads(test_case.case_tests)
                    if not isinstance(test_assertions, list):
                        test_assertions = [test_assertions]
                except json.JSONDecodeError:
                    # 如果不是JSON格式，尝试解析简单表达式
                    simple_assertion = test_case.case_tests.strip()
                    
                    # 处理简单断言表达式
                    if simple_assertion.startswith("=="):
                        # 状态码等于断言
                        expected_value = simple_assertion[2:].strip()
                        test_assertions = [{
                            "type": "status_code",
                            "expect": expected_value,
                            "actual": "status_code"
                        }]
                    elif simple_assertion.startswith("contains"):
                        # 包含断言
                        expected_value = simple_assertion[8:].strip()
                        test_assertions = [{
                            "type": "contains",
                            "expect": expected_value,
                            "actual": ""
                        }]
                    elif "$." in simple_assertion:
                        # JSONPath断言
                        parts = simple_assertion.split("==")
                        if len(parts) == 2:
                            jsonpath = parts[0].strip()
                            expected = parts[1].strip()
                            test_assertions = [{
                                "type": "jsonpath",
                                "expect": expected,
                                "actual": jsonpath
                            }]
                
                # 导入jsonpath模块用于解析JSON数据
                import jsonpath_ng.ext as jsonpath
                import re
                
                # 逐个执行断言
                for assertion in test_assertions:
                    assertion_type = assertion.get('type', '')
                    expect = assertion.get('expect', '')
                    actual = assertion.get('actual', '')
                    
                    # 不同类型的断言处理
                    if assertion_type == 'jsonpath':
                        # 使用jsonpath提取实际值
                        try:
                            json_expr = jsonpath.parse(actual)
                            matches = [match.value for match in json_expr.find(response_body)]
                            actual_value = matches[0] if matches else None
                            
                            # 比较预期值和实际值
                            if actual_value is not None:
                                # 尝试将字符串转换为相应类型进行比较
                                try:
                                    if isinstance(actual_value, (int, float)):
                                        expect_value = float(expect)
                                    elif isinstance(actual_value, bool):
                                        expect_value = expect.lower() == 'true'
                                    else:
                                        expect_value = expect
                                        
                                    assertion_pass = actual_value == expect_value
                                except:
                                    # 如果转换失败，直接比较字符串
                                    assertion_pass = str(actual_value) == expect
                            else:
                                assertion_pass = False
                                
                            assertion_results.append({
                                'type': assertion_type,
                                'expect': expect,
                                'actual': actual,
                                'actual_value': actual_value,
                                'success': assertion_pass,
                                'message': '断言通过' if assertion_pass else f'断言失败: 期望值 {expect}, 实际值 {actual_value}'
                            })
                            
                            if not assertion_pass:
                                assertions_passed = False
                                assertion_error = f'JsonPath断言失败: {actual} 的值 {actual_value} 不等于期望值 {expect}'
                        except Exception as e:
                            assertions_passed = False
                            error_msg = f'JsonPath断言执行异常: {str(e)}'
                            assertion_results.append({
                                'type': assertion_type,
                                'expect': expect,
                                'actual': actual,
                                'success': False,
                                'message': error_msg
                            })
                            assertion_error = error_msg
                    
                    elif assertion_type == 'status_code':
                        # 校验HTTP状态码
                        actual_status = response.status_code
                        expected_status = int(expect)
                        assertion_pass = actual_status == expected_status
                        
                        assertion_results.append({
                            'type': assertion_type,
                            'expect': expected_status,
                            'actual': actual_status,
                            'success': assertion_pass,
                            'message': '断言通过' if assertion_pass else f'断言失败: 期望状态码 {expected_status}, 实际状态码 {actual_status}'
                        })
                        
                        if not assertion_pass:
                            assertions_passed = False
                            assertion_error = f'状态码断言失败: 期望 {expected_status}, 实际 {actual_status}'
                    
                    elif assertion_type == 'contains':
                        # 检查响应文本是否包含指定内容
                        response_text = response.text
                        assertion_pass = expect in response_text
                        
                        assertion_results.append({
                            'type': assertion_type,
                            'expect': expect,
                            'actual': '响应文本',
                            'success': assertion_pass,
                            'message': '断言通过' if assertion_pass else f'断言失败: 响应文本不包含 {expect}'
                        })
                        
                        if not assertion_pass:
                            assertions_passed = False
                            assertion_error = f'包含断言失败: 响应文本不包含 {expect}'
                    
                    elif assertion_type == 'regex':
                        # 正则表达式匹配
                        response_text = response.text
                        try:
                            pattern = re.compile(expect)
                            assertion_pass = bool(pattern.search(response_text))
                            
                            assertion_results.append({
                                'type': assertion_type,
                                'expect': expect,
                                'actual': '响应文本',
                                'success': assertion_pass,
                                'message': '断言通过' if assertion_pass else f'断言失败: 响应文本不匹配正则表达式 {expect}'
                            })
                            
                            if not assertion_pass:
                                assertions_passed = False
                                assertion_error = f'正则断言失败: 响应文本不匹配 {expect}'
                        except re.error as e:
                            assertions_passed = False
                            error_msg = f'正则表达式错误: {str(e)}'
                            assertion_results.append({
                                'type': assertion_type,
                                'expect': expect,
                                'actual': '响应文本',
                                'success': False,
                                'message': error_msg
                            })
                            assertion_error = error_msg
                    
                    # 修复：如果有断言定义但没有执行任何断言（结果为空），则使用HTTP状态码判断
                    if has_assertions and not assertion_results:
                        assertions_passed = is_http_success
                        if not is_http_success:
                            assertion_error = f'HTTP状态码: {response.status_code} 不在成功范围内'
                        
                        # 添加一个默认的HTTP状态码断言结果
                        assertion_results.append({
                            'type': 'status_code',
                            'expect': '200-299',
                            'actual': response.status_code,
                            'success': is_http_success,
                            'message': '断言通过' if is_http_success else f'断言失败: HTTP状态码 {response.status_code} 不在成功范围内'
                        })
                        
        except Exception as e:
            print(f"断言处理发生异常: {str(e)}")
            # 断言处理异常，不影响原有逻辑，仍然根据HTTP状态码判断
            has_assertions = False
        
        # 根据是否有断言和断言结果判断最终状态
        if has_assertions:
            # 使用断言结果判断
            status = 'PASS' if assertions_passed else 'FAIL'
            is_success = assertions_passed
        else:
            # 没有断言，使用HTTP状态码判断
            status = 'PASS' if is_http_success else 'FAIL'
            is_success = is_http_success
            
        # 添加响应状态码和原始响应内容，确保错误信息可以传递
        response_info = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': response_data,
            'response_time': duration,
            'raw_text': response.text  # 保存原始响应文本
        }

        # 更新测试用例的执行时间和状态
        try:
            print(f"当前时间: {current_time}")
            # 使用 raw SQL 来更新，避免 Django ORM 的时区转换
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE test_platform_testcase 
                    SET last_executed_at = %s,
                        last_execution_result = %s,
                        last_assertion_results = %s,
                        update_time = %s
                    WHERE test_case_id = %s
                """, [current_time, status.lower(), json.dumps({
                    'has_assertions': has_assertions,
                    'all_passed': assertions_passed,
                    'results': assertion_results,
                    'error': assertion_error
                }, ensure_ascii=False), current_time, case_id])
            
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
            'response': response_info,
            'assertions': {
                'has_assertions': has_assertions,
                'all_passed': assertions_passed,
                'results': assertion_results,
                'error': assertion_error
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
                None if is_success else (
                    assertion_error if has_assertions and not assertions_passed 
                    else f'HTTP状态码: {response.status_code}'
                ),
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
                'response': response_info,
                'response_headers': dict(response.headers),  # 单独保存响应头
                'headers': headers,  # 这里只包含请求的头信息
                'request': {
                    'method': method,
                    'url': api_path,
                    'headers': headers,
                    'params': params,
                    'body': body,
                    'body_type': body_type
                },
                'assertions': {
                    'has_assertions': has_assertions,
                    'all_passed': assertions_passed,
                    'results': assertion_results
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
                            last_assertion_results = %s,
                            update_time = %s
                        WHERE test_case_id = %s
                    """, [
                        current_time, 
                        json.dumps({
                            'has_assertions': False, 
                            'all_passed': False,
                            'results': [],
                            'error': str(e)
                        }, ensure_ascii=False),
                        current_time, 
                        test_case.test_case_id
                    ])
                
                print(f"已更新测试用例状态: {test_case.test_case_id}, 状态: error, 时间: {current_time}")
            except Exception as e:
                print(f"更新测试用例状态失败: {str(e)}")

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
