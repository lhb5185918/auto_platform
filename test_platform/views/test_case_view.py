from django.http import JsonResponse
from django.core.paginator import Paginator
from test_platform.models import Project, TestCase, TestEnvironment, TestEnvironmentCover, TestSuite, TestSuiteCase, TestSuiteResult, TestExecutionLog, TestResult
from django.contrib.auth.models import User
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response
import json
from django.db.models import Q
from rest_framework.parsers import MultiPartParser
import pandas as pd
from django.db import transaction
from test_platform.serializers import TestCaseSerializer
from rest_framework import serializers
from django.utils import timezone
import time
from test_platform.views import execute as execute_module
from urllib.parse import urlparse, parse_qs


class TestCaseView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _process_headers(self, headers):
        """处理请求头数据的通用方法"""
        if not headers:  # 如果headers为None或空
            return '{}'
            
        if isinstance(headers, str):
            try:
                # 如果是字符串，尝试解析为JSON
                headers = json.loads(headers)
            except json.JSONDecodeError:
                # 如果解析失败，使用空字典
                return '{}'
        elif isinstance(headers, dict):
            # 如果是字典且为空，返回空JSON字符串
            if not headers:
                return '{}'
            # 如果是非空字典，转换为JSON字符串
            return json.dumps(headers)
        
        # 其他情况返回空JSON字符串
        return '{}'

    def _process_body(self, body):
        """处理请求体数据的通用方法"""
        if not body:  # 如果body为None或空
            return '{}'
            
        if isinstance(body, str):
            try:
                # 如果是字符串，尝试解析为JSON以验证格式
                json.loads(body)
                # 如果是有效的JSON字符串，直接返回
                return body
            except json.JSONDecodeError:
                # 如果解析失败但仍需保存，转换为JSON字符串
                try:
                    # 尝试将字符串解析为Python对象然后转为JSON
                    import ast
                    try:
                        # 尝试作为Python表达式解析
                        body_obj = ast.literal_eval(body)
                        return json.dumps(body_obj)
                    except:
                        # 如果不是有效的Python表达式，直接将字符串转为JSON
                        return json.dumps(body)
                except:
                    return json.dumps({})
        elif isinstance(body, dict):
            # 如果是字典，转换为JSON字符串
            return json.dumps(body)
        
        # 其他类型，尝试转换为JSON字符串
        try:
            return json.dumps(body)
        except:
            return '{}'

    def _process_extractors(self, extractors):
        """处理提取器数据的通用方法"""
        print(f"_process_extractors收到的原始数据: {extractors}, 类型: {type(extractors)}")
        
        if not extractors:  # 如果extractors为None或空
            print("提取器数据为空，返回空JSON数组")
            return '[]'
            
        if isinstance(extractors, str):
            try:
                # 如果是字符串，尝试解析为JSON以验证格式
                parsed = json.loads(extractors)
                print(f"成功解析提取器字符串为: {parsed}")
                # 如果是有效的JSON字符串，直接返回
                return extractors
            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {str(e)}")
                # 如果解析失败，尝试其他方式解析
                try:
                    import ast
                    # 尝试作为Python表达式解析
                    extractors_obj = ast.literal_eval(extractors)
                    print(f"通过ast解析成功: {extractors_obj}")
                    return json.dumps(extractors_obj)
                except Exception as e:
                    print(f"ast解析也失败: {str(e)}")
                    return '[]'
        elif isinstance(extractors, list):
            # 如果是列表，转换为JSON字符串
            print(f"提取器是列表，转换为JSON")
            return json.dumps(extractors)
        elif isinstance(extractors, dict):
            # 如果是字典（单个提取器），封装为列表后转换为JSON字符串
            print(f"提取器是字典，封装为列表后转换为JSON")
            return json.dumps([extractors])
        
        # 其他情况返回空JSON数组
        print(f"提取器是其他类型: {type(extractors)}，返回空数组")
        return '[]'

    def _process_tests(self, tests):
        """处理测试断言数据的通用方法"""
        if not tests:  # 如果tests为None或空
            return '{}'
            
        if isinstance(tests, str):
            try:
                # 如果是字符串，尝试解析为JSON以验证格式
                json.loads(tests)
                # 如果是有效的JSON字符串，直接返回
                return tests
            except json.JSONDecodeError:
                # 如果解析失败，尝试其他方式解析
                try:
                    import ast
                    # 尝试作为Python表达式解析
                    tests_obj = ast.literal_eval(tests)
                    return json.dumps(tests_obj)
                except:
                    return '{}'
        elif isinstance(tests, list) or isinstance(tests, dict):
            # 如果是列表或字典，转换为JSON字符串
            return json.dumps(tests)
        
        # 其他情况返回空JSON对象
        return '{}'

    def get(self, request, project_id):
        try:
            # 获取查询参数
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('pageSize', 10))
            keyword = request.GET.get('keyword', '')
            status = request.GET.get('status', '')
            priority = request.GET.get('priority', '')

            # 构建基础查询
            queryset = TestCase.objects.filter(project_id=project_id)

            # 关键字搜索（标题）
            if keyword:
                queryset = queryset.filter(case_name__icontains=keyword)

            # 状态过滤
            if status:
                if status == '未执行':
                    queryset = queryset.filter(
                        Q(last_execution_result='not_run') |
                        Q(last_execution_result__isnull=True)
                    )
                elif status == '通过':
                    queryset = queryset.filter(last_execution_result='pass')
                elif status == '失败':
                    queryset = queryset.filter(last_execution_result='fail')
                elif status == '错误':
                    queryset = queryset.filter(last_execution_result='error')

            # 优先级过滤
            if priority:
                priority_map = {
                    '高': 2,
                    '中': 1,
                    '低': 0
                }
                if priority in priority_map:
                    queryset = queryset.filter(case_priority=priority_map[priority])

            # 按创建时间倒序排序
            queryset = queryset.order_by('-create_time')

            # 计算总数
            total = queryset.count()

            # 分页
            start = (page - 1) * page_size
            end = start + page_size
            test_cases = queryset[start:end]

            # 按原有格式构建返回数据
            test_cases_data = []
            for test_case in test_cases:
                # 处理 headers
                try:
                    headers = json.loads(test_case.case_request_headers) if test_case.case_request_headers else {}
                except json.JSONDecodeError:
                    headers = {}

                # 处理 body
                try:
                    # 先尝试解析为JSON对象
                    if test_case.case_requests_body:
                        # 打印原始body数据，帮助调试
                        print(f"原始body数据: {test_case.case_requests_body}")
                        
                        if isinstance(test_case.case_requests_body, str):
                            # 检查是否是Python字典字符串表示（而非JSON）
                            if test_case.case_requests_body.strip().startswith('{') and "'" in test_case.case_requests_body:
                                try:
                                    # 尝试将Python字典字符串转为Python对象
                                    import ast
                                    body_dict = ast.literal_eval(test_case.case_requests_body)
                                    # 然后再转为标准JSON
                                    body = body_dict
                                except:
                                    try:
                                        # 尝试直接解析为JSON
                                        body = json.loads(test_case.case_requests_body)
                                    except json.JSONDecodeError:
                                        # 如果不是有效的JSON字符串，保留原始值
                                        body = test_case.case_requests_body
                            else:
                                try:
                                    # 尝试直接解析为JSON
                                    body = json.loads(test_case.case_requests_body)
                                except json.JSONDecodeError:
                                    # 如果不是有效的JSON字符串，保留原始值
                                    body = test_case.case_requests_body
                        else:
                            # 非字符串类型，尝试直接使用
                            body = test_case.case_requests_body
                    else:
                        body = {}
                    
                    # 打印处理后的body数据
                    print(f"处理后的body数据: {body}")
                except Exception as e:
                    print(f"处理body时出错: {str(e)}")
                    body = test_case.case_requests_body or {}

                # 处理 expected_result
                try:
                    expected_result = json.loads(test_case.case_expect_result) if test_case.case_expect_result else {}
                except json.JSONDecodeError:
                    expected_result = {}
                    
                # 处理 extractors
                try:
                    extractors = json.loads(test_case.case_extractors) if test_case.case_extractors else []
                except json.JSONDecodeError:
                    extractors = []
                    
                # 处理 tests
                try:
                    tests = json.loads(test_case.case_tests) if test_case.case_tests else []
                except json.JSONDecodeError:
                    tests = []

                test_cases_data.append({
                    'case_id': test_case.test_case_id,
                    'title': test_case.case_name,
                    'api_path': test_case.case_path,
                    'method': test_case.case_request_method,
                    'priority': test_case.get_case_priority_display(),
                    'status': '未执行' if test_case.last_execution_result in ['not_run', None] else test_case.last_execution_result,
                    'headers': headers,
                    'params': test_case.case_params or '',
                    'body': body,
                    'expected_result': expected_result,
                    'assertions': test_case.case_assert_contents or '',
                    'extractors': extractors,
                    'tests': tests,
                    'creator': {
                        'id': test_case.creator.id if test_case.creator else None,
                        'username': test_case.creator.username if test_case.creator else None
                    },
                    'create_time': test_case.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': test_case.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_execution_time': test_case.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if test_case.last_executed_at else None
                })

            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': total,
                    'testCases': test_cases_data
                }
            })

        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': str(e),
                'data': None
            })

    def post(self, request):
        try:
            case_name = request.data.get('title')
            case_path = request.data.get('api_path')
            case_body = self._process_body(request.data.get('body'))
            case_headers = self._process_headers(request.data.get('headers'))
            case_method = request.data.get('method')
            case_assertions = request.data.get('assertions', '')
            case_params = request.data.get('params', '')
            priority_map = {'低': 0, '中': 1, '高': 2}
            case_priority = priority_map.get(request.data.get('priority'), 0)
            project_id = request.data.get('project_id')
            expected_result = request.data.get('expected_result', '{}')
            case_extractors = self._process_extractors(request.data.get('extractors'))
            case_tests = self._process_tests(request.data.get('tests'))

            # 将params转换为JSON格式
            processed_params = self._process_body(case_params)

            # 打印调试信息
            print(f"请求的body: {request.data.get('body')}")
            print(f"处理后的body: {case_body}")
            print(f"请求的params: {case_params}")
            print(f"处理后的params: {processed_params}")
            print(f"请求的extractors: {request.data.get('extractors')}")
            print(f"处理后的extractors: {case_extractors}")
            print(f"请求的tests: {request.data.get('tests')}")
            print(f"处理后的tests: {case_tests}")

            project = Project.objects.get(project_id=project_id)

            test_case = TestCase.objects.create(
                case_name=case_name,
                case_path=case_path,
                case_description='',
                case_requests_body=case_body,
                case_request_headers=case_headers,  # 使用处理后的headers
                case_request_method=case_method,
                case_assert_type='contains',
                case_assert_contents=case_assertions,
                case_priority=case_priority,
                case_status=0,
                case_precondition='',
                case_expect_result=expected_result,
                case_extractors=case_extractors,  # 添加提取器
                case_tests=case_tests,  # 添加测试断言
                case_params=processed_params,  # 添加处理后的params
                project=project,
                creator=request.user,
                last_execution_result='not_run'
            )

            return JsonResponse({
                'code': 200,
                'message': '测试用例创建成功',
                'data': {
                    'id': test_case.test_case_id,
                    'name': test_case.case_name
                }
            })

        except Project.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '项目不存在',
                'data': None
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'创建测试用例失败：{str(e)}',
                'data': None
            })

    def put(self, request, case_id):
        try:
            # 检查请求路径是否包含status，如果是，则只更新状态
            # 注意：这是针对/api/testcase/status/{case_id}路径的特殊处理
            if request.path.endswith(f'/status/{case_id}'):
                try:
                    test_case = TestCase.objects.get(test_case_id=case_id)
                except TestCase.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '测试用例不存在',
                        'data': None
                    }, status=404)
                
                # 获取状态信息
                status = request.data.get('status', '')
                
                # 状态映射
                status_map = {
                    '通过': 'pass',
                    '失败': 'fail',
                    '错误': 'error',
                    '跳过': 'skip',
                    '未执行': 'not_run'
                }
                
                # 更新状态
                if status in status_map:
                    # 只更新状态和最后执行时间，不修改其他字段
                    current_time = timezone.now()
                    
                    # 使用update方法只更新指定字段，避免其他字段被清空
                    TestCase.objects.filter(test_case_id=case_id).update(
                        last_execution_result=status_map[status],
                        last_executed_at=current_time,
                        update_time=current_time
                    )
                    
                    # 打印日志
                    print(f"PUT更新后状态: {current_time}, {status_map[status]}")
                    
                    return JsonResponse({
                        'code': 200,
                        'message': '测试用例状态更新成功',
                        'data': {
                            'case_id': case_id,
                            'status': status_map[status],
                            'update_time': current_time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                    })
                else:
                    return JsonResponse({
                        'code': 400,
                        'message': f'无效的状态值: {status}',
                        'data': None
                    }, status=400)
            
            # 正常的PUT请求处理（更新整个测试用例）
            test_case = TestCase.objects.get(test_case_id=case_id)
            
            case_name = request.data.get('title')
            case_path = request.data.get('api_path')
            case_body = self._process_body(request.data.get('body'))
            case_headers = self._process_headers(request.data.get('headers'))
            case_method = request.data.get('method')
            case_assertions = request.data.get('assertions', '')  # 提供空字符串作为默认值
            case_params = request.data.get('params', '')  # 提供空字符串作为默认值
            priority_map = {'低': 0, '中': 1, '高': 2}
            case_priority = priority_map.get(request.data.get('priority'), 0)
            expected_result = request.data.get('expected_result', '{}')  # 提供空JSON作为默认值
            
            # 处理params参数
            processed_params = self._process_body(case_params)
            
            # 明确获取并处理extractors字段
            raw_extractors = request.data.get('extractors', [])
            print(f"原始请求中的extractors: {raw_extractors}")
            print(f"extractors类型: {type(raw_extractors)}")
            
            # 确保extractors是合适的格式
            if isinstance(raw_extractors, list):
                case_extractors = json.dumps(raw_extractors)
            else:
                case_extractors = self._process_extractors(raw_extractors)
            
            print(f"处理后的extractors: {case_extractors}")
            
            case_tests = self._process_tests(request.data.get('tests'))
            
            # 打印调试信息
            print(f"请求的body: {request.data.get('body')}")
            print(f"处理后的body: {case_body}")
            print(f"请求的params: {case_params}")
            print(f"处理后的params: {processed_params}")
            print(f"用例标题: {case_name}")

            # 准备更新字段，只包含非空字段
            update_fields = {}
            
            # 只有在提供了非空值时才更新相应字段
            if case_name not in [None, '']:
                update_fields['case_name'] = case_name
            if case_path not in [None, '']:
                update_fields['case_path'] = case_path
            if case_body not in [None, '']:
                update_fields['case_requests_body'] = case_body
            if case_headers not in [None, '']:
                update_fields['case_request_headers'] = case_headers
            if case_method not in [None, '']:
                update_fields['case_request_method'] = case_method
            
            # 其他字段可以为空，但我们也只在有值时更新
            if case_assertions is not None:
                update_fields['case_assert_contents'] = case_assertions
            if processed_params is not None:
                update_fields['case_params'] = processed_params
            
            update_fields['case_priority'] = case_priority
            update_fields['case_expect_result'] = expected_result
            update_fields['case_extractors'] = case_extractors
            update_fields['case_tests'] = case_tests
            update_fields['update_time'] = timezone.now()
            
            # 确保update_fields不为空
            if update_fields:
                # 使用filter和update方法更新数据
                TestCase.objects.filter(test_case_id=case_id).update(**update_fields)
            else:
                print("没有可更新的字段")

            # 重新获取更新后的对象
            updated_case = TestCase.objects.get(test_case_id=case_id)
            print(f"保存后的extractors: {updated_case.case_extractors}")
            
            # 尝试解析存储的extractors，确认是否可以正确读取
            try:
                saved_extractors = json.loads(updated_case.case_extractors) if updated_case.case_extractors else []
                print(f"解析后的extractors: {saved_extractors}")
            except json.JSONDecodeError as e:
                print(f"解析保存后的extractors失败: {str(e)}")
                saved_extractors = []

            return JsonResponse({
                'code': 200,
                'message': '测试用例更新成功',
                'data': {
                    'id': test_case.test_case_id,
                    'name': test_case.case_name,
                    'extractors': saved_extractors  # 在响应中返回提取器数据，便于验证
                }
            })

        except TestCase.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '测试用例不存在',
                'data': None
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"更新测试用例时出错: {str(e)}")
            return JsonResponse({
                'code': 500,
                'message': f'更新测试用例失败：{str(e)}',
                'data': None
            })

    def patch(self, request, case_id):
        """更新测试用例执行状态"""
        try:
            try:
                test_case = TestCase.objects.get(test_case_id=case_id)
            except TestCase.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试用例不存在',
                    'data': None
                }, status=404)
            
            # 获取状态信息
            status = request.data.get('status', '')
            
            # 状态映射
            status_map = {
                '通过': 'pass',
                '失败': 'fail',
                '错误': 'error',
                '跳过': 'skip',
                '未执行': 'not_run'
            }
            
            # 更新状态
            if status in status_map:
                # 只更新状态和最后执行时间，不修改其他字段
                current_time = timezone.now()
                
                # 使用update方法只更新指定字段，避免其他字段被清空
                TestCase.objects.filter(test_case_id=case_id).update(
                    last_execution_result=status_map[status],
                    last_executed_at=current_time,
                    update_time=current_time
                )
                
                # 打印日志
                print(f"更新后状态: {current_time}, {status_map[status]}")
                
                return JsonResponse({
                    'code': 200,
                    'message': '测试用例状态更新成功',
                    'data': {
                        'case_id': case_id,
                        'status': status_map[status],
                        'update_time': current_time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                })
            else:
                return JsonResponse({
                    'code': 400,
                    'message': f'无效的状态值: {status}',
                    'data': None
                }, status=400)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'code': 500,
                'message': f'更新测试用例状态失败：{str(e)}',
                'data': None
            }, status=500)

    def delete(self, request, case_id):
        """
        删除测试用例
        """
        try:
            # 查找测试用例
            try:
                test_case = TestCase.objects.get(test_case_id=case_id)
            except TestCase.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试用例不存在',
                    'data': None
                }, status=404)
            
            # 检查是否存在关联的测试套件用例
            suite_cases = TestSuiteCase.objects.filter(original_case_id=case_id)
            if suite_cases.exists():
                # 获取所有关联的套件名称
                suite_names = []
                for suite_case in suite_cases:
                    try:
                        suite_name = suite_case.suite.name
                        suite_names.append(suite_name)
                    except:
                        pass
                
                if suite_names:
                    return JsonResponse({
                        'code': 400,
                        'message': f'测试用例已被以下测试套件引用，无法删除: {", ".join(suite_names)}',
                        'data': None
                    }, status=400)
            
            # 检查是否存在测试结果
            results = TestResult.objects.filter(case=test_case)
            
            # 先删除关联的测试结果记录
            if results.exists():
                results.delete()
                
            # 删除关联的执行日志
            logs = TestExecutionLog.objects.filter(case=test_case)
            if logs.exists():
                logs.delete()
            
            # 执行删除操作
            project_id = test_case.project.project_id
            case_name = test_case.case_name
            test_case.delete()
            
            return JsonResponse({
                'code': 200,
                'message': f'测试用例"{case_name}"已成功删除',
                'data': {
                    'project_id': project_id,
                    'case_id': case_id
                }
            })
            
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            return JsonResponse({
                'code': 500,
                'message': f'删除测试用例时发生错误: {str(e)}',
                'data': {
                    'error': str(e),
                    'traceback': traceback_str
                }
            }, status=500)
    
    def get(self, request, case_id=None, project_id=None):
        """
        获取测试用例详情或列表
        - 如果有case_id，则返回单个测试用例详情
        - 如果有project_id，则返回项目下的测试用例列表
        """
        # 处理单个测试用例查询
        if case_id is not None:
            try:
                test_case = TestCase.objects.get(test_case_id=case_id)
                
                # 处理headers
                try:
                    headers = json.loads(test_case.case_request_headers) if test_case.case_request_headers else {}
                except json.JSONDecodeError:
                    headers = {}

                # 处理body
                try:
                    if test_case.case_requests_body:
                        if isinstance(test_case.case_requests_body, str):
                            try:
                                body = json.loads(test_case.case_requests_body)
                            except json.JSONDecodeError:
                                body = test_case.case_requests_body
                        else:
                            body = test_case.case_requests_body
                    else:
                        body = {}
                except Exception as e:
                    body = test_case.case_requests_body or {}

                # 处理expected_result
                try:
                    expected_result = json.loads(test_case.case_expect_result) if test_case.case_expect_result else {}
                except json.JSONDecodeError:
                    expected_result = {}
                    
                # 处理extractors
                try:
                    extractors = json.loads(test_case.case_extractors) if test_case.case_extractors else []
                except json.JSONDecodeError:
                    extractors = []
                    
                # 处理tests
                try:
                    tests = json.loads(test_case.case_tests) if test_case.case_tests else []
                except json.JSONDecodeError:
                    tests = []

                # 处理params
                try:
                    params = json.loads(test_case.case_params) if test_case.case_params else {}
                except json.JSONDecodeError:
                    params = test_case.case_params or {}

                # 构建响应数据
                case_data = {
                    'case_id': test_case.test_case_id,
                    'title': test_case.case_name,
                    'api_path': test_case.case_path,
                    'method': test_case.case_request_method,
                    'priority': test_case.get_case_priority_display(),
                    'status': '未执行' if test_case.last_execution_result in ['not_run', None] else test_case.last_execution_result,
                    'headers': headers,
                    'params': params,
                    'body': body,
                    'expected_result': expected_result,
                    'assertions': test_case.case_assert_contents or '',
                    'extractors': extractors,
                    'tests': tests,
                    'project_id': test_case.project.project_id,
                    'creator': {
                        'id': test_case.creator.id if test_case.creator else None,
                        'username': test_case.creator.username if test_case.creator else None
                    },
                    'create_time': test_case.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': test_case.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_execution_time': test_case.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if test_case.last_executed_at else None
                }

                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': case_data
                })
                
            except TestCase.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试用例不存在',
                    'data': None
                }, status=404)
            except Exception as e:
                return JsonResponse({
                    'code': 500,
                    'message': str(e),
                    'data': None
                }, status=500)
                
        # 处理测试用例列表查询（与原有的get方法逻辑保持一致）
        elif project_id is not None:
            try:
                # 获取查询参数
                page = int(request.GET.get('page', 1))
                page_size = int(request.GET.get('pageSize', 10))
                keyword = request.GET.get('keyword', '')
                status = request.GET.get('status', '')
                priority = request.GET.get('priority', '')

                # 构建基础查询
                queryset = TestCase.objects.filter(project_id=project_id)

                # 关键字搜索（标题）
                if keyword:
                    queryset = queryset.filter(case_name__icontains=keyword)

                # 状态过滤
                if status:
                    if status == '未执行':
                        queryset = queryset.filter(
                            Q(last_execution_result='not_run') |
                            Q(last_execution_result__isnull=True)
                        )
                    elif status == '通过':
                        queryset = queryset.filter(last_execution_result='pass')
                    elif status == '失败':
                        queryset = queryset.filter(last_execution_result='fail')
                    elif status == '错误':
                        queryset = queryset.filter(last_execution_result='error')

                # 优先级过滤
                if priority:
                    priority_map = {
                        '高': 2,
                        '中': 1,
                        '低': 0
                    }
                    if priority in priority_map:
                        queryset = queryset.filter(case_priority=priority_map[priority])

                # 按创建时间倒序排序
                queryset = queryset.order_by('-create_time')

                # 计算总数
                total = queryset.count()

                # 分页
                start = (page - 1) * page_size
                end = start + page_size
                test_cases = queryset[start:end]

                # 按原有格式构建返回数据
                test_cases_data = []
                for test_case in test_cases:
                    # 处理 headers
                    try:
                        headers = json.loads(test_case.case_request_headers) if test_case.case_request_headers else {}
                    except json.JSONDecodeError:
                        headers = {}

                    # 处理 body
                    try:
                        # 先尝试解析为JSON对象
                        if test_case.case_requests_body:
                            if isinstance(test_case.case_requests_body, str):
                                try:
                                    # 尝试将Python字典字符串转为Python对象
                                    if test_case.case_requests_body.strip().startswith('{') and "'" in test_case.case_requests_body:
                                        import ast
                                        body_dict = ast.literal_eval(test_case.case_requests_body)
                                        body = body_dict
                                    else:
                                        # 尝试直接解析为JSON
                                        body = json.loads(test_case.case_requests_body)
                                except:
                                    # 如果不是有效的JSON字符串，保留原始值
                                    body = test_case.case_requests_body
                            else:
                                # 非字符串类型，尝试直接使用
                                body = test_case.case_requests_body
                        else:
                            body = {}
                    except Exception as e:
                        body = test_case.case_requests_body or {}

                    # 处理 expected_result
                    try:
                        expected_result = json.loads(test_case.case_expect_result) if test_case.case_expect_result else {}
                    except json.JSONDecodeError:
                        expected_result = {}
                        
                    # 处理 extractors
                    try:
                        extractors = json.loads(test_case.case_extractors) if test_case.case_extractors else []
                    except json.JSONDecodeError:
                        extractors = []
                        
                    # 处理 tests
                    try:
                        tests = json.loads(test_case.case_tests) if test_case.case_tests else []
                    except json.JSONDecodeError:
                        tests = []

                    test_cases_data.append({
                        'case_id': test_case.test_case_id,
                        'title': test_case.case_name,
                        'api_path': test_case.case_path,
                        'method': test_case.case_request_method,
                        'priority': test_case.get_case_priority_display(),
                        'status': '未执行' if test_case.last_execution_result in ['not_run', None] else test_case.last_execution_result,
                        'headers': headers,
                        'params': test_case.case_params or '',
                        'body': body,
                        'expected_result': expected_result,
                        'assertions': test_case.case_assert_contents or '',
                        'extractors': extractors,
                        'tests': tests,
                        'creator': {
                            'id': test_case.creator.id if test_case.creator else None,
                            'username': test_case.creator.username if test_case.creator else None
                        },
                        'create_time': test_case.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'update_time': test_case.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'last_execution_time': test_case.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if test_case.last_executed_at else None
                    })

                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'total': total,
                        'testCases': test_cases_data
                    }
                })

            except Exception as e:
                return JsonResponse({
                    'code': 500,
                    'message': str(e),
                    'data': None
                }, status=500)
        else:
            return JsonResponse({
                'code': 400,
                'message': '缺少必要的参数',
                'data': None
            }, status=400)


class TestEnvironmentView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            variables = request.data.get("variables")
            project_id = request.data.get("project_id")
            name = request.data.get("name")
            env_suite_id = request.data.get("envSuiteId")  # 获取环境套ID
            
            project = Project.objects.get(project_id=project_id)
            # 获取对应的环境套
            env_cover = TestEnvironmentCover.objects.get(environment_cover_id=env_suite_id)

            for variable in variables:
                if variable is not None:
                    # 根据变量类型设置相应的字段
                    key = variable.get('key')
                    value = variable.get('value')
                    description = variable.get('description', '')

                    # 创建环境变量，根据key类型设置相应字段
                    env_data = {
                        'project': project,
                        'env_name': name,
                        'description': description,
                        'environment_cover': env_cover  # 添加环境套关联
                    }

                    # 根据key设置对应的字段值
                    if key == 'host':
                        env_data['host'] = value
                    elif key == 'port':
                        env_data['port'] = int(value)
                    elif key == 'base_url':
                        env_data['base_url'] = value
                    elif key == 'protocol':
                        env_data['protocol'] = value
                    elif key == 'token':
                        env_data['token'] = value
                    elif key == 'db_host':
                        env_data['db_host'] = value
                    elif key == 'db_port':
                        env_data['db_port'] = int(value)
                    elif key == 'db_name':
                        env_data['db_name'] = value
                    elif key == 'db_user':
                        env_data['db_user'] = value
                    elif key == 'db_password':
                        env_data['db_password'] = value
                    elif key == 'time_out':
                        env_data['time_out'] = int(value)
                    elif key == 'content_type':
                        env_data['content_type'] = value
                    elif key == 'charset':
                        env_data['charset'] = value
                    elif key == 'version':
                        env_data['version'] = value

                    # 设置默认值
                    env_data.setdefault('host', '')
                    env_data.setdefault('port', 0)
                    env_data.setdefault('base_url', '')
                    env_data.setdefault('protocol', '')
                    env_data.setdefault('token', '')
                    env_data.setdefault('db_host', '')
                    env_data.setdefault('db_port', 0)
                    env_data.setdefault('db_name', '')
                    env_data.setdefault('db_user', '')
                    env_data.setdefault('db_password', '')
                    env_data.setdefault('time_out', 0)
                    env_data.setdefault('content_type', '')
                    env_data.setdefault('charset', '')
                    env_data.setdefault('version', '')

                    test_environment = TestEnvironment.objects.create(**env_data)

            return Response({
                "code": 200,
                "message": "环境变量创建成功"
            })

        except Project.DoesNotExist:
            return Response({
                "code": 404,
                "message": "项目不存在"
            }, status=404)
        except TestEnvironmentCover.DoesNotExist:
            return Response({
                "code": 404,
                "message": "环境套不存在"
            }, status=404)
        except Exception as e:
            return Response({
                "code": 400,
                "message": f"环境变量创建失败：{str(e)}"
            }, status=400)

    def get(self, request, env_id=None, project_id=None):
        # 如果传入了env_id参数（处理 /api/env/variable/<int:env_id> 路径）
        if env_id is not None:
            try:
                # 获取特定环境变量
                environment = TestEnvironment.objects.get(environment_id=env_id)
                
                # 提取相关字段
                env_data = {
                    'id': environment.environment_id,
                    'name': environment.env_name,
                    'description': environment.description,
                    'env_suite_id': environment.environment_cover.environment_cover_id if environment.environment_cover else None,
                    'variables': []
                }
                
                # 添加所有非空字段作为变量
                fields = [
                    ('host', '主机地址'),
                    ('port', '端口号'),
                    ('base_url', '基础URL'),
                    ('protocol', '协议'),
                    ('token', '令牌值'),
                    ('db_host', '数据库主机'),
                    ('db_port', '数据库端口'),
                    ('db_name', '数据库名称'),
                    ('db_user', '数据库用户'),
                    ('db_password', '数据库密码'),
                    ('time_out', '超时时间'),
                    ('content_type', '内容类型'),
                    ('charset', '字符集'),
                    ('version', '版本号'),
                ]

                for field, desc in fields:
                    value = getattr(environment, field)
                    if value:  # 只添加非空值
                        env_data['variables'].append({
                            'id': environment.environment_id,
                            'key': field,
                            'value': str(value),
                            'description': environment.description or desc
                        })

                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': env_data
                })

            except TestEnvironment.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '环境变量不存在',
                    'data': None
                }, status=404)
            except Exception as e:
                return JsonResponse({
                    'code': 400,
                    'message': f'获取环境变量失败：{str(e)}',
                    'data': None
                }, status=400)
        
        # 如果传入了project_id参数（处理 /api/env/list/<int:project_id> 路径）
        elif project_id is not None:
            try:
                # 获取指定项目的所有环境变量，按环境套分组
                environments = TestEnvironment.objects.filter(
                    project_id=project_id
                ).order_by('environment_id')

                # 按环境套分组整理数据
                env_data = {}
                for env in environments:
                    env_suite_id = env.environment_cover.environment_cover_id if env.environment_cover else None
                    env_name = env.env_name
                    
                    # 如果这个环境套还没有记录，创建一个新的记录
                    if env_name not in env_data:
                        env_data[env_name] = {
                            'id': env.environment_id,
                            'name': env.env_name,
                            'description': env.description,
                            'env_suite_id': env_suite_id,
                            'variables': []
                        }

                    # 将所有非空字段添加为变量
                    fields = [
                        ('host', '主机地址'),
                        ('port', '端口号'),
                        ('base_url', '基础URL'),
                        ('protocol', '协议'),
                        ('token', '令牌值'),
                        ('db_host', '数据库主机'),
                        ('db_port', '数据库端口'),
                        ('db_name', '数据库名称'),
                        ('db_user', '数据库用户'),
                        ('db_password', '数据库密码'),
                        ('time_out', '超时时间'),
                        ('content_type', '内容类型'),
                        ('charset', '字符集'),
                        ('version', '版本号'),
                    ]

                    for field, desc in fields:
                        value = getattr(env, field)
                        if value:  # 只添加非空值
                            env_data[env_name]['variables'].append({
                                'id': env.environment_id,
                                'key': field,
                                'value': str(value),
                                'description': env.description or desc
                            })

                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': list(env_data.values())
                })

            except Project.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '项目不存在',
                    'data': []
                }, status=404)
            except Exception as e:
                return JsonResponse({
                    'code': 400,
                    'message': f'获取环境变量失败：{str(e)}',
                    'data': []
                }, status=400)
        else:
            return JsonResponse({
                'code': 400,
                'message': '缺少必要的参数',
                'data': None
            }, status=400)

    def put(self, request, env_id):
        try:
            key = request.data.get('key')
            value = request.data.get('value')
            description = request.data.get('description')

            # 检查环境变量是否存在
            environment = TestEnvironment.objects.get(
                environment_id=env_id
            )

            # 根据key更新对应的字段
            if key == 'host':
                environment.host = value
            elif key == 'port':
                environment.port = int(value) if value else 0
            elif key == 'base_url':
                environment.base_url = value
            elif key == 'protocol':
                environment.protocol = value
            elif key == 'token':
                environment.token = value
            elif key == 'db_host':
                environment.db_host = value
            elif key == 'db_port':
                environment.db_port = int(value) if value else 0
            elif key == 'db_name':
                environment.db_name = value
            elif key == 'db_user':
                environment.db_user = value
            elif key == 'db_password':
                environment.db_password = value
            elif key == 'time_out':
                environment.time_out = int(value) if value else 0
            elif key == 'content_type':
                environment.content_type = value
            elif key == 'charset':
                environment.charset = value
            elif key == 'version':
                environment.version = value

            # 保存更新
            environment.save()

            return JsonResponse({
                'code': 200,
                'message': '环境变量更新成功',
                'data': {
                    'id': environment.environment_id,
                    'key': key,
                    'value': value,
                    'description': description
                }
            })

        except TestEnvironment.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '环境变量不存在'
            }, status=404)
        except ValueError as e:
            return JsonResponse({
                'code': 400,
                'message': f'数值类型转换失败：{str(e)}'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'code': 400,
                'message': f'更新环境变量失败：{str(e)}'
            }, status=400)

    def delete(self, request, env_id):
        try:
            # 直接使用 URL 中的 env_id
            environment = TestEnvironment.objects.get(
                environment_id=env_id
            )

            # 删除环境变量
            environment.delete()

            return JsonResponse({
                'code': 200,
                'message': '环境变量删除成功'
            })

        except TestEnvironment.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '环境变量不存在'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'code': 400,
                'message': f'删除环境变量失败：{str(e)}'
            }, status=400)


class TestCaseImportView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = (MultiPartParser,)

    def post(self, request):
        try:
            file = request.FILES.get('file')
            project_id = request.data.get('project_id')

            # 添加更详细的调试信息
            print("原始project_id:", project_id)
            print("project_id类型:", type(project_id))
            print("请求数据:", request.data)

            if not file or not project_id:
                return JsonResponse({
                    'code': 400,
                    'message': '缺少项目id或未上传文件'
                }, status=400)

            try:
                project_id = int(project_id)
                print("转换后的project_id:", project_id)
            except (TypeError, ValueError):
                return JsonResponse({
                    'code': 400,
                    'message': '无效的项目ID'
                }, status=400)

            if not (file.name.endswith('.xlsx') or file.name.endswith('.xls')):
                return JsonResponse({
                    'code': 400,
                    'message': '文件格式错误，请上传xlsx或xls文件'
                }, status=400)

            # 读取Excel文件并打印列名，帮助调试
            df = pd.read_excel(file)
            print("Excel列名:", df.columns.tolist())

            # 定义Excel列名和代码中使用的字段的映射关系
            column_mapping = {
                'post请求': '用例标题',
                'api/post': 'api路径',
                'post': '请求方法',
                'Unnamed: 3': '请求参数',
                '{12}': '请求体',
                '高': '优先级',
                '{12}.1': '断言',
                '成功': '预期结果'
            }

            # 重命名列
            df = df.rename(columns=column_mapping)

            # 检查必需的列
            required_columns = ['用例标题', 'api路径', '请求方法']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return JsonResponse({
                    'code': 400,
                    'message': f'缺少列：{", ".join(missing_columns)}'
                }, status=400)

            with transaction.atomic():
                imported_count = 0
                test_cases = []

                for _, row in df.iterrows():
                    test_case_data = {
                        'project_id': int(project_id),
                        'case_name': row['用例标题'],
                        'case_path': row['api路径'],
                        'case_request_method': row['请求方法'].upper(),
                        'case_priority': self.normalize_priority(row.get('优先级', '中')),
                        'case_status': '0',
                        'case_request_headers': self.ensure_json_format(row.get('请求头', '')),
                        'case_params': self.ensure_json_format(row.get('请求参数', '')),
                        'case_requests_body': self.ensure_json_format(row.get('请求体', '')),
                        'case_assert_contents': row.get('断言', '$.code=200'),
                        'case_description': row.get('描述', '从Excel导入的测试用例'),
                        'case_expect_result': row.get('预期结果', '')
                    }

                    print("准备序列化的数据:", test_case_data)
                    serializer = TestCaseSerializer(data=test_case_data)

                    try:
                        if serializer.is_valid(raise_exception=True):
                            print("序列化后的数据:", serializer.validated_data)
                            test_case = serializer.save()
                            test_cases.append(test_case)
                            imported_count += 1
                    except serializers.ValidationError as e:
                        print("序列化错误:", e.detail)
                        return JsonResponse({
                            'code': 400,
                            'message': f'第{imported_count + 1}行数据验证失败：{e.detail}'
                        }, status=400)

                return JsonResponse({
                    'code': 200,
                    'message': '用例导入成功',
                    'data': {
                        'imported_count': imported_count
                    }
                })

        except Exception as e:
            print("导入错误:", str(e))
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'code': 500,
                'message': f'导入用例失败：{str(e)}'
            }, status=500)

    def normalize_priority(self, priority):
        """标准化优先级值"""
        # 打印接收到的优先级值，帮助调试
        print("接收到的优先级值:", priority)

        priority_map = {
            '高': '2',
            '中': '1',
            '低': '0',
            # 添加数字字符串的映射
            '0': '0',
            '1': '1',
            '2': '2'
        }

        # 如果已经是数字字符串，直接返回
        if priority in ['0', '1', '2']:
            return priority

        # 获取映射值，默认返回'1'（中优先级）
        result = priority_map.get(str(priority).strip(), '1')
        print("转换后的优先级值:", result)
        return result

    def ensure_json_format(self, value):
        """确保值是有效的JSON格式"""
        if not value:
            return '{}'
        try:
            # 如果已经是字典，转换为JSON字符串
            if isinstance(value, dict):
                import json
                return json.dumps(value)
            # 如果是字符串，验证是否为有效的JSON
            if isinstance(value, str):
                import json
                json.loads(value)
                return value
            return '{}'
        except (json.JSONDecodeError, TypeError):
            return '{}'


class TestEnvironmentCoverView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            project_id = request.data.get('projectId')
            name = request.data.get('name')
            description = request.data.get('description')
            project = Project.objects.get(project_id=project_id)
            environment_cover = TestEnvironmentCover.objects.create(
                project=project,
                environment_name=name,
                environment_description=description
            )
            return JsonResponse({
                'code': 200,
                'message': '环境套创建成功',
            })
        except Project.DoesNotExist:
            return JsonResponse({
                'code': 400,
                'message': '项目不存在'
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'环境套创建失败：{str(e)}'
            })

    def get(self, request, project_id):
        try:
            project = Project.objects.get(project_id=project_id)
            environment_covers = TestEnvironmentCover.objects.filter(project=project)

            # 准备返回数据
            cover_data = []
            for cover in environment_covers:
                cover_data.append({
                    'id': cover.environment_cover_id,
                    'name': cover.environment_name,
                    'description': cover.environment_description,
                    'project_id': cover.project.project_id,
                    'create_time': cover.create_time.strftime('%Y-%m-%d %H:%M:%S') if cover.create_time else None,
                    'update_time': cover.update_time.strftime('%Y-%m-%d %H:%M:%S') if cover.update_time else None
                })

            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': len(cover_data),
                    'items': cover_data
                }
            })

        except Project.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '项目不存在',
                'data': None
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取环境套列表失败：{str(e)}',
                'data': None
            })
            
    def delete(self, request, env_cover_id):
        """删除测试环境套"""
        try:
            # 查找环境套
            try:
                environment_cover = TestEnvironmentCover.objects.get(environment_cover_id=env_cover_id)
            except TestEnvironmentCover.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '环境套不存在',
                    'data': None
                }, status=404)
            
            # 先检查是否有环境变量关联到这个环境套
            related_environments = TestEnvironment.objects.filter(environment_cover=environment_cover)
            related_count = related_environments.count()
            
            # 如果有关联的环境变量，提供警告并级联删除
            if related_count > 0:
                # 删除所有关联的环境变量
                related_environments.delete()
            
            # 删除环境套
            environment_cover.delete()
            
            return JsonResponse({
                'code': 200,
                'message': f'环境套删除成功，同时删除了{related_count}个关联环境变量',
                'data': None
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'删除环境套失败：{str(e)}',
                'data': None
            }, status=500)


class TestSuiteView(APIView):
    """测试套件视图"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def execute_suite(self, request, suite_id, environment_id=None):
        """
        执行测试套件的方法，供其他模块调用
        这是对post方法的封装，使其可以被直接调用
        """
        # 创建一个包含suite_id的请求数据
        if hasattr(request, 'data'):
            request.data['suite_id'] = suite_id
        else:
            # 如果request是自定义对象，可能没有data属性
            request.data = {'suite_id': suite_id}
            
        # 如果提供了环境ID，添加到请求数据中
        if environment_id:
            request.data['environment_id'] = environment_id
            
        # 调用post方法执行测试套件
        return self.post(request, suite_id=suite_id)
    
    def post(self, request, suite_id=None):
        """创建测试套件或执行测试套件"""
        # 执行测试套件
        if suite_id is not None:
            try:
                # 获取测试套件
                try:
                    test_suite = TestSuite.objects.get(suite_id=suite_id)
                except TestSuite.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '测试套件不存在',
                        'data': None
                    }, status=404)
                
                # 获取测试环境
                environment = None
                # 优先使用环境套关联的环境
                if test_suite.environment_cover:
                    # 从环境套中获取第一个环境实例
                    environment = TestEnvironment.objects.filter(environment_cover=test_suite.environment_cover).first()
                    if not environment:
                        return JsonResponse({
                            'code': 400,
                            'message': f'环境套"{test_suite.environment_cover.environment_name}"下没有可用的环境配置，请先为该环境套添加环境',
                            'data': None
                        }, status=400)
                # 如果没有环境套，回退到使用直接关联的环境
                elif test_suite.environment:
                    environment = test_suite.environment
                else:
                    return JsonResponse({
                        'code': 400,
                        'message': '测试套件未配置执行环境套或环境',
                        'data': None
                    }, status=400)
                
                # 获取套件中的所有测试用例，按顺序排序
                suite_cases = test_suite.suite_cases.all().order_by('order')
                if not suite_cases:
                    return JsonResponse({
                        'code': 400,
                        'message': '测试套件中没有测试用例',
                        'data': None
                    }, status=400)
                
                # 执行结果统计
                total_cases = len(suite_cases)
                passed_cases = 0
                failed_cases = 0
                error_cases = 0
                skipped_cases = 0
                total_duration = 0
                execution_results = []
                
                # 初始化变量上下文
                context = {}
                
                # 记录开始时间
                suite_start_time = timezone.now()
                
                # 依次执行每个测试用例
                for index, suite_case in enumerate(suite_cases):
                    try:
                        # 解析测试用例数据
                        case_data = json.loads(suite_case.case_data)
                        original_case_id = suite_case.original_case_id
                        
                        # 替换变量
                        if context:
                            # 导入变量替换函数
                            from test_platform.views.execute import replace_variables
                            
                            # 替换URL中的变量
                            api_path = replace_variables(case_data.get('api_path', ''), context)
                            # 替换请求头中的变量
                            headers = replace_variables(case_data.get('headers', {}), context)
                            # 替换请求参数中的变量
                            params = replace_variables(case_data.get('params', {}), context)
                            # 替换请求体中的变量
                            body = replace_variables(case_data.get('body', {}), context)
                            
                            # 更新case_data
                            case_data['api_path'] = api_path
                            case_data['headers'] = headers
                            case_data['params'] = params
                            case_data['body'] = body
                        
                        # 构建执行请求数据
                        execute_data = {
                            'case_id': original_case_id,
                            'api_path': case_data.get('api_path', ''),
                            'method': case_data.get('method', ''),
                            'headers': case_data.get('headers', {}),
                            'params': case_data.get('params', ''),
                            'body': case_data.get('body', {}),
                            'body_type': case_data.get('body_type', 'raw'),
                            'assertions': case_data.get('assertions', ''),
                            'tests': case_data.get('tests', []),
                            'extractors': case_data.get('extractors', []),
                            'context': context  # 传递当前变量上下文
                        }
                        
                        print(f"执行测试用例 {index + 1}/{total_cases}: ID={original_case_id}, 名称={case_data.get('title', '')}")
                        print(f"请求方法: {execute_data['method']}")
                        print(f"当前变量上下文: {context}")
                        
                        # 模拟请求对象
                        class MockRequest:
                            def __init__(self, data):
                                self.data = data
                                # 添加自动化标记，表示这是自动化接口执行
                                self.data['is_automation'] = True
                                
                                # 根据HTTP方法区别处理请求体
                                method = data.get('method', '').upper()
                                if method == 'GET':
                                    # GET请求通常不需要请求体
                                    self.body = b''  # 空请求体
                                else:
                                    # POST/PUT等请求需要请求体
                                    self.body = json.dumps(data).encode('utf-8')
                                    
                                # 不设置默认值，完全使用测试用例中定义的方法
                                self.method = method
                                self.path = data.get('api_path', '')
                                
                                # 处理URL中的查询参数
                                parsed_url = urlparse(self.path)
                                self.path = parsed_url.path  # 只保留路径部分，移除查询参数
                                
                                # 添加额外的请求属性
                                self.user = request.user  # 传递当前用户信息
                                
                                # 添加META字典，包含自动化标记
                                self.META = {
                                    'HTTP_X_AUTOMATION': 'true'  # 标记为自动化接口执行
                                }
                                
                                # 处理GET请求参数
                                self.GET = {}
                                # 首先从URL中提取查询参数
                                if parsed_url.query:
                                    query_dict = parse_qs(parsed_url.query)
                                    self.GET = {k: v[0] for k, v in query_dict.items()}
                                
                                # 然后再处理测试用例中的params字段
                                if method == 'GET' and data.get('params'):
                                    params = data.get('params')
                                    if isinstance(params, dict):
                                        # 合并参数，优先使用params中的值
                                        self.GET.update(params)
                                    elif isinstance(params, str):
                                        try:
                                            # 尝试解析为字典
                                            if params.startswith('{'):
                                                param_dict = json.loads(params)
                                                self.GET.update(param_dict)
                                            else:
                                                # 解析URL查询字符串
                                                param_dict = parse_qs(params)
                                                self.GET.update({k: v[0] for k, v in param_dict.items()})
                                        except:
                                            pass  # 如果解析失败，保留URL中的参数
                                
                                # 添加POST和DELETE请求的空处理
                                self.POST = {}
                                self.DELETE = {}
                                self.PUT = {}
                                
                                # 处理请求头，确保只使用测试用例中的头信息
                                # 明确只从测试用例数据中获取headers，不要添加额外的头信息
                                case_headers = data.get('headers', {})
                                self.headers = case_headers.copy() if isinstance(case_headers, dict) else {}
                                
                                # 打印调试信息
                                print(f"请求头信息: {self.headers}")
                                print(f"处理后的路径: {self.path}")
                                print(f"处理后的GET参数: {self.GET}")
                                
                                self._body = self.body  # Django内部使用_body
                                
                                # 确保params字段可以被execute_test_direct函数访问到
                                # 这是关键的修改：确保params字段在直接执行时可用
                                if self.method == 'GET':
                                    self.data['params'] = self.GET
                        
                        # 创建模拟请求
                        mock_request = MockRequest(execute_data)
                        print(f"模拟请求的HTTP方法: {mock_request.method}")
                        print(f"模拟请求的路径: {mock_request.path}")
                        print(f"模拟请求的GET参数: {mock_request.GET}")
                        print(mock_request.headers)
                        
                        # 记录用例开始时间
                        case_start_time = time.time()
                        
                        # 执行测试用例
                        try:
                            # 使用direct执行方法，因为它接受更灵活的参数
                            response = execute_module.execute_test_direct(mock_request)
                            # 尝试解析响应内容
                            try:
                                response_data = json.loads(response.content)
                                
                                # 处理提取的变量和上下文更新，不管是否有extractors都执行
                                # 获取提取的变量，更新上下文
                                extractors_data = response_data.get('data', {}).get('extractors', {})
                                new_vars = extractors_data.get('extracted_variables', {})
                                if new_vars:
                                    print(f"提取到变量: {new_vars}")
                                    context.update(new_vars)
                                
                                # 更新整个上下文
                                new_context = extractors_data.get('context', {})
                                if new_context:
                                    context = new_context
                                    print(f"更新后的上下文: {context}")
                                
                                # 注释掉为每个测试用例创建执行日志的代码
                                # 在execute_test_direct方法中，会创建一条总的日志
                                # 在测试套件执行完成后，会创建一条套件执行结果记录，足够记录执行历史
                            except Exception as parse_error:
                                print(f"解析响应内容失败: {str(parse_error)}")
                            except json.JSONDecodeError:
                                # 如果无法解析为JSON，则使用原始文本
                                response_text = response.content.decode('utf-8', errors='ignore')
                                response_data = {
                                    'success': False,
                                    'message': '响应无法解析为JSON',
                                    'data': {
                                        'status': 'ERROR',
                                        'error': f'响应内容不是有效的JSON: {response_text[:200]}...',
                                        'status_code': getattr(response, 'status_code', 500)
                                    }
                                }
                        except Exception as e:
                            # 处理请求执行过程中的异常
                            print(f"执行API请求时出错: {str(e)}")
                            response_data = {
                                'success': False,
                                'message': f'执行API请求时出错: {str(e)}',
                                'data': {
                                    'status': 'ERROR',
                                    'error': str(e)
                                }
                            }
                        
                        # 计算用例执行时间
                        case_duration = time.time() - case_start_time
                        total_duration += case_duration
                        
                        # 解析执行结果
                        success = response_data.get('success', False)
                        result_data = response_data.get('data', {})
                        status = result_data.get('status', 'ERROR')
                        
                        # 获取API响应信息
                        api_response = result_data.get('response', {})
                        api_status_code = api_response.get('status_code', 0) if isinstance(api_response, dict) else 0
                        
                        # 提取错误信息
                        error_message = None
                        
                        # 如果API返回了错误状态码(4xx或5xx)，优先使用API的错误信息
                        if api_status_code >= 400:
                            # 尝试从API响应中获取错误信息
                            try:
                                if isinstance(api_response, dict) and api_response.get('body'):
                                    # 优先使用body中的内容
                                    error_body = api_response.get('body')
                                    if isinstance(error_body, dict):
                                        # 如果body是字典，尝试获取detail字段
                                        error_message = json.dumps(error_body)
                                    elif isinstance(error_body, str):
                                        error_message = error_body
                                elif isinstance(api_response, dict) and api_response.get('raw_text'):
                                    # 如果有原始文本，使用原始文本
                                    error_message = api_response.get('raw_text')
                            except Exception as e:
                                print(f"解析API错误信息失败: {str(e)}")
                                
                        # 如果没有从API获取到错误信息，则使用result_data中的error字段
                        if not error_message:
                            error_message = result_data.get('error', None)
                        
                        # 统计结果
                        if status == 'PASS':
                            passed_cases += 1
                        elif status == 'FAIL':
                            failed_cases += 1
                        elif status == 'SKIP':
                            skipped_cases += 1
                        else:
                            error_cases += 1
                        
                        # 保存执行结果
                        execution_results.append({
                            'index': index + 1,
                            'case_id': original_case_id,
                            'title': case_data.get('title', ''),
                            'status': status,
                            'duration': round(case_duration, 2),
                            'api_path': case_data.get('api_path', ''),
                            'method': case_data.get('method', 'GET'),
                            'request': execute_data,
                            'response': result_data.get('response', {}),
                            'response_headers': result_data.get('response_headers', {}),  # 单独保存响应头
                            'error': error_message,
                            'extractors': result_data.get('extractors', {})  # 添加提取器信息
                        })
                        
                    except json.JSONDecodeError as e:
                        print(f"执行测试用例 {original_case_id} 时JSON解析错误: {str(e)}")
                        error_cases += 1
                        execution_results.append({
                            'index': index + 1,
                            'case_id': original_case_id,
                            'title': case_data.get('title', '') if 'case_data' in locals() else f'用例 {original_case_id}',
                            'status': 'ERROR',
                            'duration': 0,
                            'api_path': case_data.get('api_path', '') if 'case_data' in locals() else '',
                            'method': case_data.get('method', 'GET') if 'case_data' in locals() else '',
                            'error': f"JSON解析错误: {str(e)}"
                        })
                    except Exception as e:
                        print(f"执行测试用例 {original_case_id} 时出错: {str(e)}")
                        error_cases += 1
                        execution_results.append({
                            'index': index + 1,
                            'case_id': original_case_id,
                            'title': case_data.get('title', '') if 'case_data' in locals() else f'用例 {original_case_id}',
                            'status': 'ERROR',
                            'duration': 0,
                            'api_path': case_data.get('api_path', '') if 'case_data' in locals() else '',
                            'method': case_data.get('method', 'GET') if 'case_data' in locals() else '',
                            'error': str(e)
                        })
                
                # 计算总耗时
                suite_end_time = timezone.now()
                total_duration_seconds = (suite_end_time - suite_start_time).total_seconds()
                
                # 确定整体执行状态
                if failed_cases > 0 or error_cases > 0:
                    suite_status = 'fail'
                elif skipped_cases == total_cases:
                    suite_status = 'skip'
                elif passed_cases == total_cases:
                    suite_status = 'pass'
                else:
                    suite_status = 'partial'
                
                # 更新测试套件状态
                test_suite.last_executed_at = suite_start_time
                test_suite.last_execution_status = suite_status
                test_suite.save()
                
                # 计算通过率
                pass_rate = round(passed_cases / total_cases * 100, 2) if total_cases > 0 else 0
                
                # 准备结果数据
                result_data = {
                    'execution_time': suite_start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': round(total_duration_seconds, 2),
                    'total_cases': total_cases,
                    'passed_cases': passed_cases,
                    'failed_cases': failed_cases,
                    'error_cases': error_cases,
                    'skipped_cases': skipped_cases,
                    'pass_rate': pass_rate,
                    'results': execution_results
                }
                
                # 创建测试套件执行结果记录
                suite_result = TestSuiteResult.objects.create(
                    suite=test_suite,
                    execution_time=suite_start_time,
                    status=suite_status,
                    duration=total_duration_seconds,
                    total_cases=total_cases,
                    passed_cases=passed_cases,
                    failed_cases=failed_cases,
                    error_cases=error_cases,
                    skipped_cases=skipped_cases,
                    pass_rate=pass_rate,
                    result_data=json.dumps(result_data, ensure_ascii=False),
                    environment=environment,
                    creator=request.user
                )
                
                # 创建一条总的执行日志记录
                try:
                    # 构建请求和响应的汇总信息
                    summary_request = {
                        'total_cases': total_cases,
                        'execution_info': f"测试套件 '{test_suite.name}' 共执行了 {total_cases} 个测试用例"
                    }
                    
                    summary_response = {
                        'passed': passed_cases,
                        'failed': failed_cases,
                        'error': error_cases,
                        'skipped': skipped_cases,
                        'pass_rate': f"{pass_rate}%"
                    }
                    
                    # 创建执行日志
                    log = TestExecutionLog.objects.create(
                        suite=test_suite,
                        suite_result=suite_result,
                        status=suite_status,
                        duration=total_duration_seconds,
                        executor=None,  # 避免AnonymousUser的问题
                        request_url=f"测试套件执行: {test_suite.name}",
                        request_method="SUITE",
                        request_headers=json.dumps(summary_request),
                        request_body=json.dumps({'suite_id': suite_id}),
                        response_status_code=200,
                        response_headers=json.dumps(summary_response),
                        response_body=json.dumps(execution_results),
                        log_detail=f"测试套件 {test_suite.name} 执行完成，共 {total_cases} 个用例，通过 {passed_cases} 个，失败 {failed_cases} 个，错误 {error_cases} 个，跳过 {skipped_cases} 个",
                        error_message="" if suite_status in ['pass', 'partial'] else f"测试套件执行失败，通过率: {pass_rate}%",
                        environment=environment
                    )
                    print(f"已创建测试套件执行总日志: ID={log.log_id}")
                except Exception as log_error:
                    print(f"创建测试套件执行总日志失败: {str(log_error)}")
                    import traceback
                    traceback.print_exc()
                
                # 查询所有尚未关联到suite_result的执行日志并更新
                TestExecutionLog.objects.filter(
                    suite=test_suite,
                    suite_result__isnull=True,
                    execution_time__gte=suite_start_time
                ).update(suite_result=suite_result)
                
                # 返回执行结果
                return JsonResponse({
                    'code': 200,
                    'message': '测试套件执行完成',
                    'data': {
                        'suite_id': test_suite.suite_id,
                        'name': test_suite.name,
                        'status': suite_status,
                        'execution_time': suite_start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': round(total_duration_seconds, 2),
                        'total_cases': total_cases,
                        'passed_cases': passed_cases,
                        'failed_cases': failed_cases,
                        'error_cases': error_cases,
                        'skipped_cases': skipped_cases,
                        'pass_rate': pass_rate,
                        'results': execution_results
                    }
                })
                
            except Exception as e:
                return JsonResponse({
                    'code': 500,
                    'message': f'执行测试套件失败: {str(e)}',
                    'data': None
                }, status=500)
        
        # 创建测试套件
        else:
            try:
                with transaction.atomic():
                    # 获取请求数据
                    name = request.data.get('name')
                    description = request.data.get('description', '')
                    env_id = request.data.get('envId')
                    project_id = request.data.get('project_id')
                    selected_cases = request.data.get('selectedCases', [])
                    
                    if not name or not project_id:
                        return JsonResponse({
                            'code': 400,
                            'message': '套件名称和项目ID不能为空',
                            'data': None
                        }, status=400)
                        
                    # 获取项目和环境(如果有)
                    try:
                        project = Project.objects.get(project_id=project_id)
                    except Project.DoesNotExist:
                        return JsonResponse({
                            'code': 404,
                            'message': '项目不存在',
                            'data': None
                        }, status=404)
                    
                    environment_cover = None
                    if env_id:
                        try:
                            # 现在是直接查找环境套
                            environment_cover = TestEnvironmentCover.objects.get(environment_cover_id=env_id)
                        except TestEnvironmentCover.DoesNotExist:
                            return JsonResponse({
                                'code': 404,
                                'message': '环境套不存在',
                                'data': None
                            }, status=404)
                    
                    # 创建测试套件
                    test_suite = TestSuite.objects.create(
                        name=name,
                        description=description,
                        project=project,
                        environment_cover=environment_cover,  # 使用环境套而不是环境
                        creator=request.user
                    )
                    
                    # 添加测试用例到套件
                    for index, case_data in enumerate(selected_cases):
                        # 获取原始用例ID
                        original_id = case_data.get('original_id')
                        if not original_id and 'case_id' in case_data:
                            # 尝试从case_id中提取
                            case_id = case_data.get('case_id')
                            if '_' in case_id:
                                original_id = case_id.split('_')[0]
                            else:
                                original_id = case_id
                        
                        if not original_id:
                            continue  # 如果无法确定原始ID，则跳过
                        
                        # 检查原始用例是否存在
                        try:
                            original_case = TestCase.objects.get(test_case_id=original_id)
                        except TestCase.DoesNotExist:
                            # 如果原始用例不存在，记录警告但继续
                            print(f"警告: 原始用例 ID {original_id} 不存在，但仍将其添加到套件")
                        
                        # 保存用例数据
                        TestSuiteCase.objects.create(
                            suite=test_suite,
                            original_case_id=int(original_id),
                            case_data=json.dumps(case_data, ensure_ascii=False),
                            order=index
                        )
                    
                    return JsonResponse({
                        'code': 200,
                        'message': '测试套件创建成功',
                        'data': {
                            'suite_id': test_suite.suite_id,
                            'name': test_suite.name,
                            'case_count': len(selected_cases)
                        }
                    })
                    
            except Exception as e:
                return JsonResponse({
                    'code': 500,
                    'message': f'创建测试套件失败: {str(e)}',
                    'data': None
                }, status=500)
    
    def get(self, request, project_id=None, suite_id=None):
        """获取测试套件列表或单个测试套件详情"""
        try:
            # 获取单个测试套件详情
            if suite_id is not None:
                try:
                    test_suite = TestSuite.objects.get(suite_id=suite_id)
                except TestSuite.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '测试套件不存在',
                        'data': None
                    }, status=404)
                
                # 获取套件中的测试用例
                suite_cases = test_suite.suite_cases.all().order_by('order')
                cases_data = []
                
                for suite_case in suite_cases:
                    try:
                        # 解析存储的case_data
                        case_data = json.loads(suite_case.case_data)
                        
                        # 如果没有extractors字段，尝试从原始用例中获取
                        if 'extractors' not in case_data:
                            try:
                                original_case = TestCase.objects.get(test_case_id=suite_case.original_case_id)
                                if original_case.case_extractors:
                                    try:
                                        extractors = json.loads(original_case.case_extractors)
                                        case_data['extractors'] = extractors
                                    except json.JSONDecodeError:
                                        case_data['extractors'] = []
                                else:
                                    case_data['extractors'] = []
                            except TestCase.DoesNotExist:
                                case_data['extractors'] = []
                        
                        cases_data.append(case_data)
                    except json.JSONDecodeError:
                        # 如果用例数据无法解析，则跳过
                        continue
                
                # 构建响应数据
                suite_data = {
                    'suite_id': test_suite.suite_id,
                    'name': test_suite.name,
                    'description': test_suite.description,
                    'project_id': test_suite.project.project_id,
                    'project_name': test_suite.project.name,  # 添加项目名称
                    'env_id': test_suite.environment_cover.environment_cover_id if test_suite.environment_cover else None,
                    'environment': {  # 保留environment字段名，但内容为environment_cover信息
                        'env_id': test_suite.environment_cover.environment_cover_id if test_suite.environment_cover else None,
                        'name': test_suite.environment_cover.environment_name if test_suite.environment_cover else '',
                        'description': test_suite.environment_cover.environment_description if test_suite.environment_cover else ''
                    } if test_suite.environment_cover else None,
                    'creator': test_suite.creator.username if test_suite.creator else None,
                    'create_time': test_suite.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': test_suite.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_executed_at': test_suite.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if test_suite.last_executed_at else None,
                    'last_execution_status': test_suite.last_execution_status,
                    'cases': cases_data,
                    'environment_cover_id': test_suite.environment_cover_id
                }
                
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': suite_data
                })
            
            # 获取项目的测试套件列表
            elif project_id is not None:
                try:
                    project = Project.objects.get(project_id=project_id)
                except Project.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '项目不存在',
                        'data': None
                    }, status=404)
                
                # 获取分页参数
                page = int(request.GET.get('page', 1))
                page_size = int(request.GET.get('pageSize', 10))
                
                # 获取项目的测试套件
                test_suites = TestSuite.objects.filter(project=project).order_by('-create_time')
                
                # 计算总数
                total = test_suites.count()
                
                # 分页
                start = (page - 1) * page_size
                end = start + page_size
                paginated_suites = test_suites[start:end]
                
                # 构建响应数据
                suites_data = []
                for suite in paginated_suites:
                    case_count = suite.suite_cases.count()
                    suites_data.append({
                        'suite_id': suite.suite_id,
                        'name': suite.name,
                        'description': suite.description,
                        'project_id': suite.project.project_id,
                        'env_id': suite.environment.environment_id if suite.environment else None,
                        'env_name': suite.environment.env_name if suite.environment else '',
                        'case_count': case_count,
                        'creator': {
                            'id': suite.creator.id if suite.creator else None,
                            'username': suite.creator.username if suite.creator else None
                        },
                        'create_time': suite.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'update_time': suite.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'last_executed_at': suite.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if suite.last_executed_at else None,
                        'last_execution_status': suite.last_execution_status,
                        'environment_cover_id': suite.environment_cover_id

                    })
                
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'total': total,
                        'suites': suites_data
                    }
                })
            
            # 获取所有测试套件列表
            else:
                # 获取分页参数和可能的项目ID参数
                page = int(request.GET.get('page', 1))
                page_size = int(request.GET.get('pageSize', 10))
                query_project_id = request.GET.get('project_id')
                
                # 根据项目ID筛选
                if query_project_id:
                    try:
                        project = Project.objects.get(project_id=query_project_id)
                        test_suites = TestSuite.objects.filter(project=project).order_by('-create_time')
                    except Project.DoesNotExist:
                        return JsonResponse({
                            'code': 404,
                            'message': '项目不存在',
                            'data': None
                        }, status=404)
                else:
                    # 获取所有测试套件
                    test_suites = TestSuite.objects.all().order_by('-create_time')
                
                # 计算总数
                total = test_suites.count()
                
                # 分页
                start = (page - 1) * page_size
                end = start + page_size
                paginated_suites = test_suites[start:end]
                
                # 构建响应数据
                items = []
                for suite in paginated_suites:
                    case_count = suite.suite_cases.count()
                    items.append({
                        'id': suite.suite_id,
                        'name': suite.name,
                        'description': suite.description or '',
                        'case_count': case_count,
                        'last_execution_time': suite.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if suite.last_executed_at else None,
                        'project_id': suite.project.project_id,
                        'project_name': suite.project.name,  # 添加项目名称
                        'status': 'active',  # 固定值，可以根据需要修改
                        'created_at': suite.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'updated_at': suite.update_time.strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                message = "获取测试套件列表成功"
                if query_project_id:
                    project_name = project.name
                    message = f"获取项目 '{project_name}' 的测试套件列表成功"
                
                return JsonResponse({
                    'code': 200,
                    'message': message,
                    'data': {
                        'total': total,
                        'items': items
                    }
                })
                
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取测试套件失败: {str(e)}',
                'data': None
            }, status=500)
    
    def put(self, request, suite_id):
        """更新测试套件"""
        try:
            with transaction.atomic():
                try:
                    test_suite = TestSuite.objects.get(suite_id=suite_id)
                except TestSuite.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '测试套件不存在',
                        'data': None
                    }, status=404)
                
                # 获取请求数据
                name = request.data.get('name')
                description = request.data.get('description')
                env_id = request.data.get('envId')
                selected_cases = request.data.get('selectedCases', [])
                
                # 更新套件基本信息
                if name:
                    test_suite.name = name
                if description is not None:
                    test_suite.description = description
                
                # 更新环境套
                if env_id:
                    try:
                        environment_cover = TestEnvironmentCover.objects.get(environment_cover_id=env_id)
                        test_suite.environment_cover = environment_cover
                    except TestEnvironmentCover.DoesNotExist:
                        pass  # 如果环境套不存在，则保持原有环境套
                
                test_suite.save()
                
                # 如果提供了测试用例，则更新套件中的用例
                if selected_cases:
                    # 删除现有的测试用例
                    test_suite.suite_cases.all().delete()
                    
                    # 添加新的测试用例
                    for index, case_data in enumerate(selected_cases):
                        # 获取原始用例ID
                        original_id = case_data.get('original_id')
                        if not original_id and 'case_id' in case_data:
                            # 尝试从case_id中提取
                            case_id = case_data.get('case_id')
                            if '_' in case_id:
                                original_id = case_id.split('_')[0]
                            else:
                                original_id = case_id
                        
                        if not original_id:
                            continue  # 如果无法确定原始ID，则跳过
                        
                        # 保存用例数据
                        TestSuiteCase.objects.create(
                            suite=test_suite,
                            original_case_id=int(original_id),
                            case_data=json.dumps(case_data, ensure_ascii=False),
                            order=index
                        )
                
                return JsonResponse({
                    'code': 200,
                    'message': '测试套件更新成功',
                    'data': {
                        'suite_id': test_suite.suite_id,
                        'name': test_suite.name,
                        'case_count': len(selected_cases) if selected_cases else test_suite.suite_cases.count()
                    }
                })
                
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'更新测试套件失败: {str(e)}',
                'data': None
            }, status=500)
    
    def delete(self, request, suite_id):
        """删除测试套件"""
        try:
            try:
                test_suite = TestSuite.objects.get(suite_id=suite_id)
            except TestSuite.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试套件不存在',
                    'data': None
                }, status=404)
            
            # 删除测试套件
            test_suite.delete()
            
            return JsonResponse({
                'code': 200,
                'message': '测试套件删除成功',
                'data': None
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'删除测试套件失败: {str(e)}',
                'data': None
            }, status=500)


class EnvironmentSwitchView(APIView):
    """环境套切换视图"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request):
        try:
            # 从会话中获取当前环境套ID
            current_env_id = request.session.get('current_environment_cover_id')
            
            if current_env_id:
                # 检查环境套是否存在
                try:
                    environment_cover = TestEnvironmentCover.objects.get(environment_cover_id=current_env_id)
                    return JsonResponse({
                        'code': 200,
                        'message': 'success',
                        'data': {
                            'env_id': str(current_env_id),
                            'env_name': environment_cover.environment_name,
                            'description': environment_cover.environment_description
                        }
                    })
                except TestEnvironmentCover.DoesNotExist:
                    # 如果环境套不存在，清除会话中的ID
                    if 'current_environment_cover_id' in request.session:
                        del request.session['current_environment_cover_id']
            
            # 如果没有设置环境套或环境套不存在，返回空数据
            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'env_id': None
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取当前环境套失败：{str(e)}',
                'data': None
            })
    
    def put(self, request):
        try:
            env_id = request.data.get('env_id')
            
            # 验证环境套ID是否存在
            try:
                environment_cover = TestEnvironmentCover.objects.get(environment_cover_id=env_id)
            except TestEnvironmentCover.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '环境套不存在',
                    'data': None
                })
                
            # 在这里可以添加会话状态或用户设置来记住当前选择的环境套
            # 例如，可以使用Django会话存储当前环境套ID
            request.session['current_environment_cover_id'] = env_id
            
            # 返回成功响应
            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'env_id': str(env_id)
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'切换环境套失败：{str(e)}',
                'data': None
            })
