from django.http import JsonResponse
from django.core.paginator import Paginator
from test_platform.models import Project
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


@csrf_exempt  # 禁用CSRF保护，允许跨域请求
def get_project_list(request):
    """
    获取项目列表的视图函数
    支持GET和POST两种请求方式，实现分页查询
    """
    if request.method == 'GET':
        # 获取分页参数，默认第1页，每页10条
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))

        # 查询所有项目并按创建时间排序
        projects = Project.objects.all().order_by('created_at')

        # 使用Django分页器进行分页处理
        paginator = Paginator(projects, page_size)
        page_obj = paginator.get_page(page)

        # 初始化响应数据结构
        data = {
            "total": paginator.count,  # 总记录数
            "projects": [],  # 项目列表
            "page": page,  # 当前页码
            "page_size": page_size,  # 每页大小
            "total_pages": paginator.num_pages  # 总页数
        }

        # 遍历当前页的项目，构建详细信息
        for project in page_obj:
            # 获取项目成员数量
            members_count = project.user.projects.count()

            # TODO: 以下是示例数据，需要根据实际模型关联获取
            test_cases_count = 100  # 测试用例数量
            execution_count = 50  # 执行次数
            success_rate = 95.5  # 成功率
            last_execution_time = datetime.now().isoformat()  # 最后执行时间

            # 构建创建者信息
            creator = {
                "id": project.user.id,
                "username": project.user.username,
                "avatar": "avatar_url"  # TODO: 需要关联用户头像
            }

            # 构建单个项目的详细信息
            project_info = {
                "id": project.project_id,
                "name": project.name,
                "description": project.description,
                "status": "active",  # TODO: 需要关联项目状态
                "create_time": project.created_at.isoformat(),
                "update_time": project.updated_at.isoformat(),
                "creator": creator,
                "members_count": members_count,
                "test_cases_count": test_cases_count,
                "execution_count": execution_count,
                "success_rate": success_rate,
                "last_execution_time": last_execution_time
            }

            data["projects"].append(project_info)

        # 构建最终响应数据
        response_data = {
            "code": 200,
            "message": "获取项目列表成功",
            "total": paginator.count,
            "data": data
        }

        return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})
    else:
        # POST请求处理逻辑，与GET类似，但从请求体获取参数
        request_body = json.loads(request.body)
        if 'page' in request_body:
            page = int(request_body['page'])
            page_size = int(request_body['page_size'])
            # 查询和分页逻辑与GET请求相同
            projects = Project.objects.all().order_by('created_at')
            paginator = Paginator(projects, page_size)
            page_obj = paginator.get_page(page)

            # 构建响应数据结构
            data = {
                "total": paginator.count,
                "projects": [],
                "page": page,
                "page_size": page_size,
                "total_pages": paginator.num_pages
            }

            # 遍历构建项目信息，逻辑与GET请求相同
            for project in page_obj:
                members_count = project.user.projects.count()

                # TODO: 示例数据，需要实际关联
                test_cases_count = 100
                execution_count = 50
                success_rate = 95.5
                last_execution_time = datetime.now().isoformat()

                creator = {
                    "id": project.user.id,
                    "username": project.user.username,
                    "avatar": "avatar_url"
                }

                project_info = {
                    "id": project.project_id,
                    "name": project.name,
                    "description": project.description,
                    "status": project.is_active,
                    "create_time": project.created_at.isoformat(),
                    "update_time": project.updated_at.isoformat(),
                    "creator": creator,
                    "members_count": members_count,
                    "test_cases_count": test_cases_count,
                    "execution_count": execution_count,
                    "success_rate": success_rate,
                    "last_execution_time": last_execution_time
                }

                data["projects"].append(project_info)

            response_data = {
                "code": 200,
                "message": "获取项目列表成功",
                "total": paginator.count,
                "data": data
            }
            return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})
        else:
            try:
                request_body = json.loads(request.body)
                name = request_body.get('name', '')
                project_status = request_body.get('status', None)
                start_time = request_body.get('start_date', '')
                end_time = request_body.get('end_date', '')
                query = Q()
                if name and name.strip():
                    query &= Q(name=name)
                if project_status is not None and project_status != '':
                    query &= Q(is_active=project_status)
                if start_time and end_time:
                    start_datetime = datetime.strptime(start_time, '%Y-%m-%d')
                    end_datetime = datetime.strptime(end_time, '%Y-%m-%d')
                    query &= Q(created_at__range=(start_datetime, end_datetime))
                projects = Project.objects.filter(query).order_by('created_at')
                project_list = []
                for project in projects:
                    project_list.append({
                        'id': project.project_id,
                        'name': project.name,
                        'description': project.description,
                        'status': project.is_active,
                        'create_time': project.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'creator': {
                            'id': project.user.id,
                            'username': project.user.username
                        } if project.user else None,
                        'test_cases_count': project.test_cases.count() if hasattr(project, 'test_cases') else 0,
                        'last_execution_time': project.created_at.strftime(
                            '%Y-%m-%d %H:%M:%S') if project.created_at else None
                    })

                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'total': len(project_list),
                        'projects': project_list
                    }
                })
            except Exception as e:
                return JsonResponse({
                    'code': 200,
                    'message': f'查询失败：{str(e)}'
                })


class ProjectView(APIView):
    """
    项目创建视图类
    使用JWT认证和权限控制
    """
    authentication_classes = [JWTAuthentication]  # 使用JWT认证
    permission_classes = [IsAuthenticated]  # 要求用户必须登录

    def post(self, request):
        """
        创建新项目的方法
        :param request: HTTP请求对象
        :return: Response对象，包含创建结果
        """
        try:
            # 从请求数据中获取项目信息
            project_name = request.data.get('name')
            project_description = request.data.get('description')
            project_status = request.data.get('status')

            # 检查项目名称是否已存在
            if Project.objects.filter(name=project_name).exists():
                return Response({
                    "code": 400,
                    "message": "项目已存在"
                })

            # 创建新项目
            Project.objects.create(
                name=project_name,
                description=project_description,
                is_active=project_status,
                user=request.user  # 使用当前登录用户作为创建者
            )

            # 返回成功响应
            return Response({
                "code": 200,
                "message": "创建项目成功"
            })

        except Exception as e:
            # 记录错误并返回错误响应
            print("Error:", str(e))
            return Response({
                "code": 500,
                "message": f"创建项目失败：{str(e)}"
            })


class ProjectEditView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_name = request.data.get('name')
        project_description = request.data.get('description')
        project_status = request.data.get('status')
        project_id = request.data.get('id')
        project = Project.objects.filter(project_id=project_id)
        if project:
            Project.objects.filter(project_id=project_id).update(name=project_name, description=project_description,
                                                                 is_active=project_status)
            return JsonResponse({"code": 200, "message": "编辑项目成功"})
        return JsonResponse({"code": 400, "message": "项目不存在"})


class ProjectDeleteView(APIView):
    def post(self, request):
        project_id = request.data.get('id')
        if Project.objects.filter(project_id=project_id).exists():
            Project.objects.filter(project_id=project_id).delete()
            return JsonResponse({"code": 200, "message": "删除项目成功"})
        return JsonResponse({"code": 400, "message": "项目不存在"})
