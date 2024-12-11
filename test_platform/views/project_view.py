from django.http import JsonResponse
from django.core.paginator import Paginator
from test_platform.models import Project
from django.contrib.auth.models import User
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
import json


@csrf_exempt
def get_project_list(request):
    if request.method == 'GET':
        # 获取请求参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))

        # 查询所有项目并排序
        projects = Project.objects.all().order_by('created_at')  # 使用 'created_at' 进行排序

        # 分页
        paginator = Paginator(projects, page_size)
        page_obj = paginator.get_page(page)

        # 构建响应数据
        data = {
            "total": paginator.count,
            "projects": [],
            "page": page,
            "page_size": page_size,
            "total_pages": paginator.num_pages
        }

        for project in page_obj:
            # 获取项目成员数
            members_count = project.user.projects.count()

            # 获取测试用例数和执行次数（假设这些数据存储在其他模型中）
            test_cases_count = 100  # 示例数据
            execution_count = 50  # 示例数据
            success_rate = 95.5  # 示例数据
            last_execution_time = datetime.now().isoformat()  # 示例数据

            # 获取创建者信息
            creator = {
                "id": project.user.id,
                "username": project.user.username,
                "avatar": "avatar_url"  # 示例数据
            }

            # 构建项目信息
            project_info = {
                "id": project.project_id,
                "name": project.name,
                "description": project.description,
                "status": "active",  # 示例数据
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

        # 返回 JSON 响应
        response_data = {
            "code": 200,
            "message": "获取项目列表成功",
            "total": paginator.count,
            "data": data
        }

        return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})
    else:
        request_body = json.loads(request.body)
        page = int(request_body['page'])
        page_size = int(request_body['page_size'])

        # 查询所有项目并排序
        projects = Project.objects.all().order_by('created_at')  # 使用 'created_at' 进行排序

        # 分页
        paginator = Paginator(projects, page_size)
        page_obj = paginator.get_page(page)

        # 构建响应数据
        data = {
            "total": paginator.count,
            "projects": [],
            "page": page,
            "page_size": page_size,
            "total_pages": paginator.num_pages
        }

        for project in page_obj:
            print(project.user)
            # 获取项目成员数
            members_count = project.user.projects.count()

            # 获取测试用例数和执行次数（假设这些数据存储在其他模型中）
            test_cases_count = 100  # 示例数据
            execution_count = 50  # 示例数据
            success_rate = 95.5  # 示例数据
            last_execution_time = datetime.now().isoformat()  # 示例数据

            # 获取创建者信息
            creator = {
                "id": project.user.id,
                "username": project.user.username,
                "avatar": "avatar_url"  # 示例数据
            }

            # 构建项目信息
            project_info = {
                "id": project.project_id,
                "name": project.name,
                "description": project.description,
                "status": "active",  # 示例数据
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

        # 返回 JSON 响应
        response_data = {
            "code": 200,
            "message": "获取项目列表成功",
            "total": paginator.count,
            "data": data
        }
        return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
def creat_project(request):
    request_body = json.loads(request.body)
    project_name = request_body['name']
    project_description = request_body['description']
    project_status = request_body['status']
    project_object = Project.objects.filter(name=project_name)
    if project_object:
        response_data = {
            "code": 400,
            "message": "项目已存在"
        }
        return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})
    else:
        project_object = Project.objects.create(name=project_name, description=project_description,
                                                is_active=project_status,user_id=request.user.id)
        project_object.save()
        response_data = {
            "code": 200,
            "message": "创建项目成功"
        }
        return JsonResponse(response_data, json_dumps_params={'ensure_ascii': False})
