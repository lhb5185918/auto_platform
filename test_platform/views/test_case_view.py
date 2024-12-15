from django.http import JsonResponse
from django.core.paginator import Paginator
from test_platform.models import Project, TestCase, TestEnvironment
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

            test_cases = TestCase.objects.filter(project_id=project_id).order_by('-create_time')
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
                    'create_time': case.create_time.strftime('%Y-%m-%d %H:%M:%S'),
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


class TestEnvironmentView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        try:
            variables = request.data.get("variables")
            project_id = request.data.get("project_id")
            name = request.data.get("name")

            project = Project.objects.get(project_id=project_id)

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
                        'description': description
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
                "code": 400,
                "message": "项目不存在"
            }, status=400)
        except Exception as e:
            return Response({
                "code": 400,
                "message": f"环境变量创建失败：{str(e)}"
            }, status=400)

    def get(self, request, project_id):
        try:
            # 获取指定项目的所有环境变量
            environments = TestEnvironment.objects.filter(
                project_id=project_id
            ).order_by('environment_id')

            # 按环境名称分组整理数据
            env_data = {}
            for env in environments:
                if env.env_name not in env_data:
                    env_data[env.env_name] = {
                        'id': env.environment_id,
                        'name': env.env_name,
                        'project_id': env.project_id,
                        'create_time': env.project.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'update_time': env.project.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
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
                    ('version', '版本号')
                ]

                for field, desc in fields:
                    value = getattr(env, field)
                    if value:  # 只添加非空值
                        env_data[env.env_name]['variables'].append({
                            'id': env.environment_id,
                            'key': field,
                            'value': str(value),
                            'description': desc
                        })

            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': list(env_data.values())
            })

        except Project.DoesNotExist:
            return JsonResponse({
                'code': 400,
                'message': '项目不存在'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'code': 400,
                'message': f'获取环境变量失败：{str(e)}'
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
