from django.http import JsonResponse
from django.core.paginator import Paginator
from test_platform.models import Project, TestCase
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


class TestCaseView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, project_id):
        try:
            page = request.GET.get('page')
            page_size = request.GET.get('pageSize')
            page = int(page) if page is not None else 1
            page_size = int(page_size) if page_size is not None else 10

            test_cases = TestCase.objects.filter(project_id=project_id).order_by('-creat_time')
            paginator = Paginator(test_cases, page_size)
            current_page = paginator.page(page)
            test_cases_data = []

            # 优先级映射
            priority_map = {0: '低', 1: '中', 2: '高'}
            # 状态映射
            status_map = {
                'passed': '通过',
                'failed': '失败',
                'blocked': '阻塞',
                'not_run': '未执行'
            }

            for case in current_page.object_list:
                # 尝试将headers和body转换为字典
                try:
                    headers = json.loads(case.case_request_headers) if case.case_request_headers else {}
                except:
                    headers = case.case_request_headers
                
                try:
                    body = json.loads(case.case_requests_body) if case.case_requests_body else {}
                except:
                    body = case.case_requests_body

                try:
                    expected_result = json.loads(case.case_expect_result) if case.case_expect_result else {}
                except:
                    expected_result = case.case_expect_result

                test_cases_data.append({
                    'case_id': case.test_case_id,
                    'title': case.case_name,
                    'api_path': case.case_path,
                    'method': case.case_request_method,
                    'priority': priority_map.get(case.case_priority, '低'),
                    'status': status_map.get(case.last_execution_result, '未执行'),
                    'headers': case.case_request_headers,
                    'params': case.case_params,  # 如果需要params，需要在模型中添加相应字段
                    'body': case.case_requests_body,
                    'expected_result': expected_result,
                    'assertions': case.case_assert_contents,
                    'creator': {
                        'id': case.creator.id if case.creator else None,
                        'username': case.creator.username if case.creator else None
                    },
                    'create_time': case.creat_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': case.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_execution_time': case.last_executed_at.strftime(
                        '%Y-%m-%d %H:%M:%S') if case.last_executed_at else None
                })

            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': paginator.count,
                    'testCases': test_cases_data
                }
            })

        except Exception as e:
            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': 0,
                    'testCases': []
                }
            })

    def post(self, request):
        try:
            case_name = request.data.get('title')
            case_path = request.data.get('api_path')
            case_body = request.data.get('body')
            case_headers = request.data.get('headers')
            case_method = request.data.get('method')
            case_assertions = request.data.get('assertions')
            case_params = request.data.get('params')
            priority_map = {'低': 0, '中': 1, '高': 2}
            case_priority = priority_map.get(request.data.get('priority'), 0)  # 将中文优先级转换为数字
            project_id = request.data.get('project_id')
            expected_result = request.data.get('expected_result')

            project = Project.objects.get(project_id=project_id)

            test_case = TestCase.objects.create(
                case_name=case_name,
                case_path=case_path,
                case_description='',  # 默认空描述
                case_requests_body=case_body,
                case_request_headers=case_headers,
                case_request_method=case_method,
                case_assert_type='contains',  # 默认断言类型
                case_assert_contents=case_assertions,
                case_priority=case_priority,
                case_status=0,  # 默认未执行
                case_precondition='',  # 默认空前置条件
                case_expect_result=expected_result,
                project=project,
                creator=request.user,
                last_execution_result='not_run'  # 默认未执行
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
