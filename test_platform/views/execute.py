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
            # 获取用例数据，优先使用套件中的case_data
            try:
                case_data = json.loads(suite_case.case_data) if suite_case.case_data else {}
            except json.JSONDecodeError:
                case_data = {}
                
            if case_data:
                # 如果套件中有数据，直接使用
                case_list.append({
                    'case_id': suite_case.original_case_id,
                    'title': case_data.get('title', f'用例{suite_case.original_case_id}'),
                    'method': case_data.get('method', 'GET'),
                    'api_path': case_data.get('api_path', ''),
                    'priority': case_data.get('priority', 0),
                    'description': case_data.get('description', ''),
                    'status': case_data.get('status', 0),
                    'headers': case_data.get('headers', {}),
                    'body': case_data.get('body', {}),
                    'params': case_data.get('params', {}),
                    'expected': case_data.get('expected', ''),
                    'extractors': case_data.get('extractors', [])
                })
            else:
                # 如果套件中没有数据，尝试从原始测试用例获取
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
                        params = json.loads(case.case_params) if case.case_params else {}
                    except json.JSONDecodeError:
                        params = {}
                    
                    try:
                        assert_contents = json.loads(case.case_assert_contents) if case.case_assert_contents else {}
                    except json.JSONDecodeError:
                        assert_contents = case.case_assert_contents
                    
                    # 解析提取器字段
                    try:
                        extractors = json.loads(case.case_extractors) if case.case_extractors else []
                    except json.JSONDecodeError:
                        extractors = []
                    
                    # 添加用例信息到列表
                    case_data = {
                        'title': case.case_name,
                        'method': case.case_request_method,
                        'api_path': case.case_path,
                        'headers': headers,
                        'params': params,
                        'body': body,
                        'expected': case.case_expect_result,
                        'priority': case.case_priority,
                        'description': case.case_description,
                        'status': case.case_status,
                        'extractors': extractors
                    }
                    
                    # 将数据保存到测试套件中，便于下次使用
                    suite_case.case_data = json.dumps(case_data)
                    suite_case.save()
                    
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
                        'params': params,
                        'expected': case.case_expect_result,
                        'case_assert_contents': assert_contents,
                        'extractors': extractors
                    })
                except TestCase.DoesNotExist:
                    # 如果原始用例不存在，使用最小数据集
                    case_list.append({
                        'case_id': suite_case.original_case_id,
                        'title': f'未知用例 {suite_case.original_case_id}',
                        'method': 'GET',
                        'api_path': '',
                        'priority': 0,
                        'description': '',
                        'status': 0,
                        'headers': {},
                        'body': {},
                        'params': {},
                        'expected': '',
                        'extractors': [],
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
    
    该接口只会更新测试套件中的用例数据(TestSuiteCase.case_data)，
    不会修改原始测试用例表中的数据
    """
    try:
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
        case_extractors = body_data.get('extractors', [])
        
        # 获取套件ID - 这是必须的
        suite_id = body_data.get('suite_id')
        if not suite_id:
            return JsonResponse({
                'code': 400,
                'message': '缺少必要参数suite_id',
                'data': None
            }, status=400, charset='utf-8')
            
        try:
            # 查找测试套件中的用例关联记录
            suite_case = TestSuiteCase.objects.get(suite_id=suite_id, original_case_id=case_id)
            
            # 尝试获取当前case_data数据以保留其他字段
            try:
                existing_data = json.loads(suite_case.case_data) if suite_case.case_data else {}
            except json.JSONDecodeError:
                existing_data = {}
            
            # 构建用例数据 - 将 JSON 对象存储在套件用例数据中
            case_data = {
                'title': case_title,
                'name': case_title,
                'method': case_method,
                'api_path': case_api_path,
                'headers': case_headers,
                'params': case_params,
                'expected': case_expected,
                'body': case_body,
                'priority': case_priority,
                'extractors': case_extractors,
                'original_case_id': case_id
            }
            
            # 保留原有数据中可能存在的其他字段
            for key in existing_data:
                if key not in case_data:
                    case_data[key] = existing_data[key]
            
            # 更新套件用例数据
            suite_case.case_data = json.dumps(case_data)
            suite_case.save()
            
            # 准备返回数据
            response_data = {
                'case_id': case_id,
                'suite_id': suite_id,
                'title': case_title,
                'headers': case_headers,
                'params': case_params,
                'body': case_body,
                'extractors': case_extractors
            }
            
            return JsonResponse({
                'code': 200,
                'message': '测试套件用例更新成功',
                'data': response_data
            }, charset='utf-8', json_dumps_params={'ensure_ascii': False})
        except TestSuiteCase.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '未找到测试套件中的关联用例',
                'data': None
            }, status=404, charset='utf-8')
    
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'更新测试套件用例失败: {str(e)}',
            'data': {
                'error': str(e)
            }
        }, status=500, charset='utf-8', json_dumps_params={'ensure_ascii': False})


def set_timezone():
    """设置数据库会话时区为北京时间"""
    with connection.cursor() as cursor:
        cursor.execute("SET time_zone = '+08:00'")

def replace_variables(data, context):
    """
    递归替换数据中的${变量名}为上下文中的实际值
    
    参数:
        data: 要处理的数据(可以是字典、列表、字符串)
        context: 变量上下文字典
        
    返回:
        替换变量后的数据
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            result[key] = replace_variables(value, context)
        return result
    elif isinstance(data, list):
        return [replace_variables(item, context) for item in data]
    elif isinstance(data, str):
        # 替换字符串中的${变量名}
        import re
        variable_pattern = r'\${([^}]+)}'
        matches = re.findall(variable_pattern, data)
        
        replaced_data = data
        for var_name in matches:
            if var_name in context:
                # 替换为实际值
                replaced_data = replaced_data.replace(f'${{{var_name}}}', str(context[var_name]))
        return replaced_data
    else:
        return data

def handle_variable_extraction(response_data, extractors):
    """
    从响应中提取变量
    
    参数:
        response_data: 响应数据，可以是响应体或完整的响应信息对象
        extractors: 提取器配置列表
        
    返回:
        提取的变量字典 {变量名: 变量值}
    """
    extracted_vars = {}
    
    if not extractors or not isinstance(extractors, list):
        return extracted_vars
        
    # 确定响应体
    if isinstance(response_data, dict) and 'body' in response_data:
        # 如果传入的是完整的响应信息对象
        response_body = response_data.get('body', {})
    else:
        # 如果直接传入的是响应体
        response_body = response_data
        
    for extractor in extractors:
        if not isinstance(extractor, dict):
            continue
            
        # 检查提取器是否启用
        if not extractor.get('enabled', True):
            continue
            
        name = extractor.get('name')
        expression = extractor.get('expression')
        extractor_type = extractor.get('type', 'jsonpath')
        default_value = extractor.get('defaultValue', '')
        
        if name and expression:
            # 根据提取器类型提取变量
            if extractor_type == 'jsonpath':
                import jsonpath_ng.ext as jsonpath
                try:
                    if isinstance(response_body, dict) or isinstance(response_body, list):
                        json_expr = jsonpath.parse(expression)
                        matches = [match.value for match in json_expr.find(response_body)]
                        if matches:
                            # 存储提取的变量
                            extracted_vars[name] = matches[0]
                            print(f"成功提取变量 {name} = {matches[0]}")
                        else:
                            # 使用默认值
                            extracted_vars[name] = default_value
                            print(f"未找到匹配值，使用默认值 {name} = {default_value}")
                    else:
                        # 如果响应体不是JSON格式，使用默认值
                        extracted_vars[name] = default_value
                        print(f"响应体不是JSON格式，使用默认值 {name} = {default_value}")
                except Exception as e:
                    print(f"提取变量失败: {str(e)}")
                    extracted_vars[name] = default_value
            
            # 可以添加其他类型的提取器支持，如正则表达式等
    
    return extracted_vars

def get_suite_case_data(suite_case):
    """
    从测试套件用例中获取执行所需的所有数据，优先使用套件中的case_data
    
    参数:
        suite_case: TestSuiteCase对象
        
    返回:
        包含完整测试用例数据的字典
    """
    # 尝试解析case_data
    try:
        case_data = json.loads(suite_case.case_data) if suite_case.case_data else {}
    except json.JSONDecodeError:
        case_data = {}
    
    # 设置必要的默认值
    if not case_data:
        # 如果没有套件数据，尝试从原始用例中获取数据
        try:
            original_case = TestCase.objects.get(test_case_id=suite_case.original_case_id)
            
            # 解析 JSON 字段
            try:
                headers = json.loads(original_case.case_request_headers) if original_case.case_request_headers else {}
            except json.JSONDecodeError:
                headers = {}
            
            try:
                body = json.loads(original_case.case_requests_body) if original_case.case_requests_body else {}
            except json.JSONDecodeError:
                body = original_case.case_requests_body
                
            try:
                params = json.loads(original_case.case_params) if original_case.case_params else {}
            except json.JSONDecodeError:
                params = {}
                
            try:
                extractors = json.loads(original_case.case_extractors) if original_case.case_extractors else []
            except json.JSONDecodeError:
                extractors = []
            
            # 构建基础数据
            case_data = {
                'title': original_case.case_name,
                'name': original_case.case_name,
                'method': original_case.case_request_method,
                'api_path': original_case.case_path,
                'headers': headers,
                'params': params,
                'body': body,
                'expected': original_case.case_expect_result,
                'priority': original_case.case_priority,
                'extractors': extractors,
                'original_case_id': suite_case.original_case_id
            }
        except TestCase.DoesNotExist:
            # 如果原始用例也不存在，则提供最小默认值
            case_data = {
                'title': f'未知用例 {suite_case.original_case_id}',
                'method': 'GET',
                'api_path': '',
                'headers': {},
                'params': {},
                'body': {},
                'expected': '',
                'priority': 0,
                'extractors': [],
                'original_case_id': suite_case.original_case_id
            }
    
    return case_data

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
        
        # 获取测试环境和变量上下文
        env_id = test_data.get('env_id')
        context = test_data.get('context', {})  # 从请求中获取变量上下文
        
        # 如果没有传入上下文，则初始化一个空的
        if not isinstance(context, dict):
            context = {}
            
        print(f"执行请求: 方法={method}, 路径={api_path}, 环境ID={env_id}")
        print(f"当前变量上下文: {context}")
        
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
            
        # 获取提取器信息
        extractors = test_data.get('extractors', [])

        # 变量替换 - 对请求数据中的${变量名}进行替换
        api_path = replace_variables(api_path, context)
        headers = replace_variables(headers, context)
        params = replace_variables(params, context)
        body = replace_variables(body, context)

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
        
        # 从响应中提取变量
        extracted_vars = handle_variable_extraction(response_body, extractors)
        
        # 更新上下文变量，用于下一个请求
        context.update(extracted_vars)
        
        # 添加提取的变量到结果中
        extracted_data = {
            'variables': extracted_vars,
            'context': context  # 返回完整上下文，包括之前的变量
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
            
        # 添加响应状态码和原始响应内容，确保错误信息可以传递
        response_info = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'body': response_body,
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
            },
            'extractors': {
                'extracted_variables': extracted_vars,
                'context': context
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
                },
                'extractors': {
                    'extracted_variables': extracted_vars,
                    'context': context
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
