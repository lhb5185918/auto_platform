from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from test_platform.models import TestMindMap, Project, User
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

class MindMapView(APIView):
    """测试脑图视图"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self, request):
        """创建或更新测试脑图"""
        try:
            # 解析请求数据
            data = request.data
            name = data.get('name')
            mindmap_data = data.get('data')
            project_id = data.get('project_id')
            
            # 验证必要字段
            if not all([name, mindmap_data, project_id]):
                return JsonResponse({
                    'code': 400,
                    'message': '缺少必要参数',
                    'data': None
                }, status=400)
                
            # 获取项目
            try:
                project = Project.objects.get(project_id=project_id)
            except Project.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '项目不存在',
                    'data': None
                }, status=404)
                
            # 创建或更新脑图
            mindmap, created = TestMindMap.objects.update_or_create(
                name=name,
                project=project,
                defaults={
                    'data': mindmap_data,
                    'creator': request.user,
                }
            )
            
            # 返回结果
            return JsonResponse({
                'code': 200,
                'message': '保存成功',
                'data': {
                    'mindmap_id': mindmap.mindmap_id,
                    'name': mindmap.name,
                    'project_id': project.project_id,
                    'create_time': mindmap.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': mindmap.update_time.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'保存失败: {str(e)}',
                'data': None
            }, status=500)
    
    def get(self, request, mindmap_id=None):
        """获取测试脑图列表或详情"""
        try:
            # 获取单个脑图详情
            if mindmap_id:
                try:
                    mindmap = TestMindMap.objects.get(mindmap_id=mindmap_id)
                    return JsonResponse({
                        'code': 200,
                        'message': '获取成功',
                        'data': {
                            'mindmap_id': mindmap.mindmap_id,
                            'name': mindmap.name,
                            'data': mindmap.data,
                            'project_id': mindmap.project.project_id,
                            'creator': mindmap.creator.username if mindmap.creator else None,
                            'create_time': mindmap.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'update_time': mindmap.update_time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                    })
                except TestMindMap.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '脑图不存在',
                        'data': None
                    }, status=404)
            
            # 获取项目脑图列表
            project_id = request.GET.get('project_id')
            if project_id:
                mindmaps = TestMindMap.objects.filter(project_id=project_id)
            else:
                mindmaps = TestMindMap.objects.all()
                
            mindmap_list = [{
                'mindmap_id': mindmap.mindmap_id,
                'name': mindmap.name,
                'project_id': mindmap.project.project_id,
                'creator': mindmap.creator.username if mindmap.creator else None,
                'create_time': mindmap.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                'update_time': mindmap.update_time.strftime('%Y-%m-%d %H:%M:%S')
            } for mindmap in mindmaps]
            
            return JsonResponse({
                'code': 200,
                'message': '获取成功',
                'data': mindmap_list
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取失败: {str(e)}',
                'data': None
            }, status=500)
    
    def delete(self, request, mindmap_id):
        """删除测试脑图"""
        try:
            try:
                mindmap = TestMindMap.objects.get(mindmap_id=mindmap_id)
            except TestMindMap.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '脑图不存在',
                    'data': None
                }, status=404)
                
            mindmap.delete()
            
            return JsonResponse({
                'code': 200,
                'message': '删除成功',
                'data': None
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'删除失败: {str(e)}',
                'data': None
            }, status=500) 