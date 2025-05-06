from django.http import JsonResponse
from django.core.paginator import Paginator
from test_platform.models import Project, TestCase, TestSuiteResult
from django.contrib.auth.models import User
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response
import json
from django.db.models import Q, Count, Case, When, F, FloatField, ExpressionWrapper, Sum


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
        
        # 查询结果列表
        project_list = []
        
        # 遍历构建项目信息
        for project in projects:
            # 获取测试用例数量
            test_cases_count = TestCase.objects.filter(project=project).count()
            
            # 获取测试套件执行次数
            suite_results = TestSuiteResult.objects.filter(suite__project=project)
            execution_count = suite_results.count()
            
            # 计算成功率
            if execution_count > 0:
                # 计算通过的结果数
                pass_count = suite_results.filter(status='pass').count()
                # 计算成功率百分比
                success_rate = round((pass_count / execution_count) * 100, 1)
            else:
                success_rate = 0.0
            
            # 获取项目创建者信息
            creator_info = {
                "id": project.user.id if project.user else None,
                "username": project.user.username if project.user else "未知",
            }
            
            # 构建项目信息
            project_data = {
                "id": project.project_id,
                "name": project.name,
                "description": project.description,
                "test_cases_count": test_cases_count,
                "execution_count": execution_count,
                "success_rate": success_rate,
                "create_time": project.created_at.strftime('%Y-%m-%d %H:%M:%S') if project.created_at else None,
                "update_time": project.updated_at.strftime('%Y-%m-%d %H:%M:%S') if project.updated_at else None,
                "creator": creator_info,
                'status': project.is_active
            }
            
            project_list.append(project_data)
        
        # 使用分页器
        paginator = Paginator(project_list, page_size)
        page_obj = paginator.get_page(page)
        
        # 构建响应数据
        response_data = {
            "code": 200,
            "message": "success",
            "data": {
                "total": len(project_list),
                "projects": list(page_obj)
            }
        }
        
        return JsonResponse(response_data)
    else:
        # POST请求处理逻辑，主要用于搜索
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
            
            # 查询符合条件的项目
            projects = Project.objects.filter(query).order_by('created_at')
            
            # 查询结果列表
            project_list = []
            
            # 遍历构建项目信息
            for project in projects:
                # 获取测试用例数量
                test_cases_count = TestCase.objects.filter(project=project).count()
                
                # 获取测试套件执行次数
                suite_results = TestSuiteResult.objects.filter(suite__project=project)
                execution_count = suite_results.count()
                
                # 计算成功率
                if execution_count > 0:
                    # 计算通过的结果数
                    pass_count = suite_results.filter(status='pass').count()
                    # 计算成功率百分比
                    success_rate = round((pass_count / execution_count) * 100, 1)
                else:
                    success_rate = 0.0
                
                # 获取项目创建者信息
                creator_info = {
                    "id": project.user.id if project.user else None,
                    "username": project.user.username if project.user else "未知",
                }
                
                # 构建项目信息
                project_data = {
                    "id": project.project_id,
                    "name": project.name,
                    "description": project.description,
                    "test_cases_count": test_cases_count,
                    "execution_count": execution_count,
                    "success_rate": success_rate,
                    "create_time": project.created_at.strftime('%Y-%m-%d %H:%M:%S') if project.created_at else None,
                    "update_time": project.updated_at.strftime('%Y-%m-%d %H:%M:%S') if project.updated_at else None,
                    "creator": creator_info,
                    'status': project.is_active
                }
                
                project_list.append(project_data)

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
