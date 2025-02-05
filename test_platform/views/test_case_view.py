from django.http import JsonResponse
from django.core.paginator import Paginator
from test_platform.models import Project, TestCase, TestEnvironment, TestEnvironmentCover
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
                    body = json.loads(test_case.case_requests_body) if test_case.case_requests_body else {}
                except json.JSONDecodeError:
                    body = {}

                # 处理 expected_result
                try:
                    expected_result = json.loads(test_case.case_expect_result) if test_case.case_expect_result else {}
                except json.JSONDecodeError:
                    expected_result = {}

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
            case_body = request.data.get('body')
            case_headers = self._process_headers(request.data.get('headers'))
            case_method = request.data.get('method')
            case_assertions = request.data.get('assertions')
            case_params = request.data.get('params')
            priority_map = {'低': 0, '中': 1, '高': 2}
            case_priority = priority_map.get(request.data.get('priority'), 0)
            project_id = request.data.get('project_id')
            expected_result = request.data.get('expected_result')

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
            test_case = TestCase.objects.get(test_case_id=case_id)
            
            case_name = request.data.get('title')
            case_path = request.data.get('api_path')
            case_body = request.data.get('body')
            case_headers = self._process_headers(request.data.get('headers'))
            case_method = request.data.get('method')
            case_assertions = request.data.get('assertions')
            case_params = request.data.get('params')
            priority_map = {'低': 0, '中': 1, '高': 2}
            case_priority = priority_map.get(request.data.get('priority'), 0)
            expected_result = request.data.get('expected_result')

            test_case.case_name = case_name
            test_case.case_path = case_path
            test_case.case_requests_body = case_body
            test_case.case_request_headers = case_headers  # 使用处理后的headers
            test_case.case_request_method = case_method
            test_case.case_assert_contents = case_assertions
            test_case.case_priority = case_priority
            test_case.case_expect_result = expected_result
            
            test_case.save()

            return JsonResponse({
                'code': 200,
                'message': '测试用例更新成功',
                'data': {
                    'id': test_case.test_case_id,
                    'name': test_case.case_name
                }
            })

        except TestCase.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '测试用例不存在',
                'data': None
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'更新测试用例失败：{str(e)}',
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

    def get(self, request, project_id):
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
