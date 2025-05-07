import requests
import json
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from test_platform.models import RAGKnowledgeBase, Project, APIKey
from django.db.models import F
from django.utils import timezone
from django.db import models
import logging

logger = logging.getLogger(__name__)


class APIKeyView(APIView):
    """API密钥管理视图"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self, request):
        """创建API密钥"""
        try:
            # 获取请求参数
            key_name = request.data.get('key_name')
            api_key = request.data.get('api_key')
            api_base = request.data.get('api_base', 'https://api.coze.cn')
            service_type = request.data.get('service_type', 'coze')
            is_default = request.data.get('is_default', False)
            project_id = request.data.get('project_id')
            
            # 参数验证
            if not key_name:
                return JsonResponse({
                    'code': 400,
                    'message': '密钥名称不能为空',
                    'data': None
                }, status=400)
                
            if not api_key:
                return JsonResponse({
                    'code': 400,
                    'message': 'API密钥不能为空',
                    'data': None
                }, status=400)
            
            # 检查项目（如果提供）
            project = None
            if project_id:
                try:
                    project = Project.objects.get(project_id=project_id)
                except Project.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '项目不存在',
                        'data': None
                    }, status=404)
            
            # 检查同一用户下是否有同名密钥
            if APIKey.objects.filter(user=request.user, key_name=key_name).exists():
                return JsonResponse({
                    'code': 400,
                    'message': '同名密钥已存在',
                    'data': None
                }, status=400)
            
            # 创建API密钥
            api_key_obj = APIKey.objects.create(
                key_name=key_name,
                api_key=api_key,
                api_base=api_base,
                service_type=service_type,
                is_default=is_default,
                user=request.user,
                project=project
            )
            
            return JsonResponse({
                'code': 200,
                'message': 'API密钥创建成功',
                'data': {
                    'api_key_id': api_key_obj.api_key_id,
                    'key_name': api_key_obj.key_name,
                    'service_type': api_key_obj.service_type,
                    'is_default': api_key_obj.is_default,
                    'api_base': api_key_obj.api_base,
                    'create_time': api_key_obj.create_time.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'创建API密钥失败: {str(e)}',
                'data': None
            }, status=500)
    
    def get(self, request, api_key_id=None):
        """获取API密钥列表或详情"""
        try:
            if api_key_id:
                # 获取单个API密钥详情
                try:
                    api_key = APIKey.objects.get(api_key_id=api_key_id, user=request.user)
                except APIKey.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': 'API密钥不存在',
                        'data': None
                    }, status=404)
                
                # 返回API密钥详情（不包含API密钥值）
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'api_key_id': api_key.api_key_id,
                        'key_name': api_key.key_name,
                        'api_base': api_key.api_base,
                        'service_type': api_key.service_type,
                        'is_active': api_key.is_active,
                        'is_default': api_key.is_default,
                        'usage_count': api_key.usage_count,
                        'last_used_at': api_key.last_used_at.strftime('%Y-%m-%d %H:%M:%S') if api_key.last_used_at else None,
                        'project_id': api_key.project.project_id if api_key.project else None,
                        'project_name': api_key.project.name if api_key.project else None,
                        'create_time': api_key.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'update_time': api_key.update_time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                })
            else:
                # 获取API密钥列表
                service_type = request.GET.get('service_type')
                project_id = request.GET.get('project_id')
                
                # 构建查询条件
                query = {'user': request.user}
                
                if service_type:
                    query['service_type'] = service_type
                    
                if project_id:
                    query['project_id'] = project_id
                    
                # 查询API密钥
                api_keys = APIKey.objects.filter(**query).order_by('-is_default', '-create_time')
                
                # 构建响应数据
                api_key_list = []
                for key in api_keys:
                    api_key_list.append({
                        'api_key_id': key.api_key_id,
                        'key_name': key.key_name,
                        'service_type': key.service_type,
                        'is_active': key.is_active,
                        'is_default': key.is_default,
                        'api_base': key.api_base,
                        'usage_count': key.usage_count,
                        'project_id': key.project.project_id if key.project else None,
                        'project_name': key.project.name if key.project else None,
                        'create_time': key.create_time.strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': api_key_list
                })
                
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取API密钥失败: {str(e)}',
                'data': None
            }, status=500)
    
    def patch(self, request, api_key_id):
        """更新API密钥"""
        try:
            # 获取API密钥对象
            try:
                api_key = APIKey.objects.get(api_key_id=api_key_id, user=request.user)
            except APIKey.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': 'API密钥不存在',
                    'data': None
                }, status=404)
            
            # 更新API密钥信息
            if 'key_name' in request.data:
                # 检查新名称是否与其他密钥冲突
                new_name = request.data['key_name']
                if new_name != api_key.key_name and APIKey.objects.filter(user=request.user, key_name=new_name).exists():
                    return JsonResponse({
                        'code': 400,
                        'message': '同名密钥已存在',
                        'data': None
                    }, status=400)
                api_key.key_name = new_name
            
            if 'api_key' in request.data:
                api_key.api_key = request.data['api_key']
                
            if 'api_base' in request.data:
                api_key.api_base = request.data['api_base']
                
            if 'service_type' in request.data:
                api_key.service_type = request.data['service_type']
                
            if 'is_active' in request.data:
                api_key.is_active = request.data['is_active']
                
            if 'is_default' in request.data:
                api_key.is_default = request.data['is_default']
                
            if 'project_id' in request.data:
                project_id = request.data['project_id']
                if project_id:
                    try:
                        project = Project.objects.get(project_id=project_id)
                        api_key.project = project
                    except Project.DoesNotExist:
                        return JsonResponse({
                            'code': 404,
                            'message': '项目不存在',
                            'data': None
                        }, status=404)
                else:
                    api_key.project = None
            
            # 保存更新
            api_key.save()
            
            return JsonResponse({
                'code': 200,
                'message': 'API密钥更新成功',
                'data': {
                    'api_key_id': api_key.api_key_id,
                    'key_name': api_key.key_name,
                    'service_type': api_key.service_type,
                    'is_active': api_key.is_active,
                    'is_default': api_key.is_default,
                    'update_time': api_key.update_time.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'更新API密钥失败: {str(e)}',
                'data': None
            }, status=500)
    
    def delete(self, request, api_key_id):
        """删除API密钥"""
        try:
            # 获取API密钥对象
            try:
                api_key = APIKey.objects.get(api_key_id=api_key_id, user=request.user)
            except APIKey.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': 'API密钥不存在',
                    'data': None
                }, status=404)
            
            # 删除API密钥
            key_name = api_key.key_name
            api_key.delete()
            
            return JsonResponse({
                'code': 200,
                'message': f'API密钥 {key_name} 已删除',
                'data': None
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'删除API密钥失败: {str(e)}',
                'data': None
            }, status=500)


class RAGBaseView(APIView):
    """RAG知识库管理视图"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self, request):
        """创建RAG知识库"""
        try:
            # 获取请求参数
            api_key_id = request.data.get('api_key_id')  # 改为使用api_key_id
            name = request.data.get('name')
            # 支持title字段作为name的替代
            if not name and request.data.get('title'):
                name = request.data.get('title')
            space_id = request.data.get('space_id')
            format_type = request.data.get('format_type')
            description = request.data.get('description', '')  # 可选参数设置默认值
            file_id = request.data.get('file_id', None)  # 可选参数
            project_id = request.data.get('project_id')

            # 参数验证
            if not name:
                return JsonResponse({
                    'code': 400,
                    'message': '知识库名称不能为空',
                    'data': None
                }, status=400)

            if not space_id:
                return JsonResponse({
                    'code': 400,
                    'message': '空间ID不能为空',
                    'data': None
                }, status=400)

            if format_type is None:
                return JsonResponse({
                    'code': 400,
                    'message': '知识库类型不能为空',
                    'data': None
                }, status=400)

            if not project_id:
                return JsonResponse({
                    'code': 400,
                    'message': '项目ID不能为空',
                    'data': None
                }, status=400)

            # 获取关联的项目
            try:
                project = Project.objects.get(project_id=project_id)
            except Project.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '项目不存在',
                    'data': None
                }, status=404)

            # 获取API密钥信息
            api_key_obj = None

            # 如果提供了api_key_id，直接使用该API密钥
            if api_key_id:
                try:
                    api_key_obj = APIKey.objects.get(api_key_id=api_key_id, user=request.user)
                except APIKey.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '指定的API密钥不存在',
                        'data': None
                    }, status=404)
            else:
                # 否则，查找该用户的默认API密钥
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True,
                    is_default=True
                ).first()

                # 如果没有默认API密钥，则获取最近创建的活跃API密钥
                if not api_key_obj:
                    api_key_obj = APIKey.objects.filter(
                        user=request.user,
                        service_type='coze',
                        is_active=True
                    ).order_by('-create_time').first()

            # 检查是否找到了API密钥
            if not api_key_obj:
                return JsonResponse({
                    'code': 400,
                    'message': '未找到可用的API密钥，请先创建API密钥',
                    'data': None
                }, status=400)

            # 先创建知识库记录
            rag_knowledge = RAGKnowledgeBase.objects.create(
                name=name,
                space_id=space_id,
                format_type=format_type,
                description=description,
                file_id=file_id,
                api_key=api_key_obj.api_key,
                api_base=api_key_obj.api_base,
                status='creating',
                project=project,
                creator=request.user
            )

            # 调用创建知识库API
            try:
                result = self.create_rag_base(
                    rag_knowledge=rag_knowledge,
                    name=name,
                    space_id=space_id,
                    format_type=format_type,
                    description=description,
                    file_id=file_id
                )

                # 更新知识库状态
                if 'data' in result and 'dataset_id' in result['data']:
                    rag_knowledge.external_dataset_id = result['data']['dataset_id']
                    rag_knowledge.status = 'active'
                else:
                    rag_knowledge.status = 'error'
                    rag_knowledge.error_message = json.dumps(result)

                rag_knowledge.save()

                # 更新API密钥使用统计
                APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
                    usage_count=F('usage_count') + 1,
                    last_used_at=timezone.now()
                )

                # 根据API响应返回结果
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'rag_id': rag_knowledge.rag_id,
                        'external_dataset_id': rag_knowledge.external_dataset_id,
                        'name': rag_knowledge.name,
                        'status': rag_knowledge.status,
                        'api_key_id': api_key_obj.api_key_id,
                        'api_key_name': api_key_obj.key_name,
                        'api_response': result
                    }
                })
            except Exception as api_error:
                # 更新知识库状态为错误
                rag_knowledge.status = 'error'
                rag_knowledge.error_message = str(api_error)
                rag_knowledge.save()

                raise api_error

        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'创建知识库失败: {str(e)}',
                'data': None
            }, status=500)

    def get(self, request, rag_id=None, project_id=None):
        """获取RAG知识库列表或详情"""
        try:
            if rag_id:
                # 获取单个知识库详情
                try:
                    rag_knowledge = RAGKnowledgeBase.objects.get(rag_id=rag_id)
                except RAGKnowledgeBase.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '知识库不存在',
                        'data': None
                    }, status=404)

                # 返回知识库详情（不包含API密钥）
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'rag_id': rag_knowledge.rag_id,
                        'name': rag_knowledge.name,
                        'space_id': rag_knowledge.space_id,
                        'format_type': rag_knowledge.format_type,
                        'description': rag_knowledge.description,
                        'file_id': rag_knowledge.file_id,
                        'api_base': rag_knowledge.api_base,
                        'status': rag_knowledge.status,
                        'external_dataset_id': rag_knowledge.external_dataset_id,
                        'project_id': rag_knowledge.project.project_id,
                        'project_name': rag_knowledge.project.name,
                        'creator': rag_knowledge.creator.username if rag_knowledge.creator else None,
                        'create_time': rag_knowledge.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'update_time': rag_knowledge.update_time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                })
            else:
                # 获取知识库列表
                # 如果URL传入了project_id作为路径参数，优先使用该值
                if not project_id:
                    # 如果没有从URL路径获取到project_id，尝试从查询参数获取
                    project_id = request.GET.get('project_id')

                # 获取分页参数
                page = int(request.GET.get('page', 1))
                page_size = int(request.GET.get('pageSize', 10))
                keyword = request.GET.get('keyword', '')

                # 构建查询条件
                query_filter = {}
                if project_id:
                    query_filter['project_id'] = project_id

                # 如果有关键词，添加名称模糊搜索条件
                if keyword:
                    query_filter['name__icontains'] = keyword

                # 获取知识库列表
                rag_list = RAGKnowledgeBase.objects.filter(**query_filter).order_by('-create_time')

                # 计算总数
                total = rag_list.count()

                # 手动分页
                start = (page - 1) * page_size
                end = start + page_size
                rag_list = rag_list[start:end]

                # 构建响应数据（不包含API密钥）
                rag_data = []
                for rag in rag_list:
                    rag_data.append({
                        'rag_id': rag.rag_id,
                        'name': rag.name,
                        'space_id': rag.space_id,
                        'format_type': rag.format_type,
                        'status': rag.status,
                        'external_dataset_id': rag.external_dataset_id,
                        'project_id': rag.project.project_id,
                        'project_name': rag.project.name,
                        'creator': rag.creator.username if rag.creator else None,
                        'create_time': rag.create_time.strftime('%Y-%m-%d %H:%M:%S')
                    })

                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'list': rag_data,
                        'total': total,
                        'page': page,
                        'pageSize': page_size
                    }
                })

        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取知识库失败: {str(e)}',
                'data': None
            }, status=500)

    def create_rag_base(self, rag_knowledge, name, space_id, format_type, description='', file_id=None):
        """
        创建RAG知识库核心方法

        参数:
        rag_knowledge (RAGKnowledgeBase): 知识库对象
        name (str): 知识库名称
        space_id (str): 空间ID
        format_type (int): 知识库类型，0为文本，2为图片
        description (str, optional): 知识库描述
        file_id (str, optional): 知识库图标文件ID

        返回:
        dict: API响应结果
        """
        # 从知识库对象中获取API配置
        api_key = rag_knowledge.api_key
        api_base = rag_knowledge.api_base

        # 构建API调用URL
        url = f"{api_base}/v1/datasets"

        # 构建请求数据
        data = {
            "name": name,
            "space_id": space_id,
            "format_type": format_type
        }

        # 添加可选参数
        if description:
            data["description"] = description

        if file_id:
            data["file_id"] = file_id

        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            # 发送API请求
            response = requests.post(url, headers=headers, data=json.dumps(data))
            response.raise_for_status()  # 抛出HTTP错误以便捕获
            return response.json()
        except requests.exceptions.RequestException as e:
            # 处理请求异常
            error_msg = str(e)
            try:
                # 尝试解析错误响应
                if hasattr(e, 'response') and e.response is not None:
                    error_data = e.response.json()
                    error_msg = error_data.get('msg', str(e))
            except (json.JSONDecodeError, ValueError, AttributeError) as parse_error:
                # 捕获JSON解析错误和其他可能的错误
                error_msg = f"{error_msg} (解析响应失败: {str(parse_error)})"
            
            raise Exception(f"API调用失败: {error_msg}")
            
    def patch(self, request, rag_id):
        """更新RAG知识库与API密钥关联"""
        try:
            # 获取参数
            api_key_id = request.data.get('api_key_id')
            
            # 验证参数
            if not api_key_id:
                return JsonResponse({
                    'code': 400,
                    'message': 'API密钥ID不能为空',
                    'data': None
                }, status=400)
                
            # 获取知识库对象
            try:
                rag_knowledge = RAGKnowledgeBase.objects.get(rag_id=rag_id)
            except RAGKnowledgeBase.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '知识库不存在',
                    'data': None
                }, status=404)
            
            # 获取API密钥对象
            try:
                api_key_obj = APIKey.objects.get(api_key_id=api_key_id, user=request.user)
            except APIKey.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': 'API密钥不存在',
                    'data': None
                }, status=404)
            
            # 更新知识库的API密钥信息
            rag_knowledge.api_key = api_key_obj.api_key
            rag_knowledge.api_base = api_key_obj.api_base
            rag_knowledge.save()
            
            return JsonResponse({
                'code': 200,
                'message': '知识库API密钥更新成功',
                'data': {
                    'rag_id': rag_knowledge.rag_id,
                    'name': rag_knowledge.name,
                    'api_key_id': api_key_obj.api_key_id,
                    'api_key_name': api_key_obj.key_name
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'更新知识库API密钥失败: {str(e)}',
                'data': None
            }, status=500)

    def list_external_datasets(self, request):
        """
        查询外部系统中的知识库列表
        
        接口参数:
        space_id (str): 必选，知识库所在的空间ID
        name (str): 可选，知识库名称，支持模糊搜索
        format_type (int): 可选，知识库类型，0为文本，1为表格，2为图片
        page_num (int): 可选，页码，默认为1
        page_size (int): 可选，每页条数，默认为10
        api_key_id (str): 可选，指定使用的API密钥ID，不提供则使用默认密钥
        
        返回:
        dict: 知识库列表信息
        """
        try:
            # 获取请求参数
            space_id = request.GET.get('space_id')
            name = request.GET.get('name')
            format_type = request.GET.get('format_type')
            page_num = request.GET.get('page_num', '1')
            page_size = request.GET.get('page_size', '10')
            api_key_id = request.GET.get('api_key_id')
            
            # 参数验证
            if not space_id:
                return JsonResponse({
                    'code': 400,
                    'message': '空间ID不能为空',
                    'data': None
                }, status=400)
            
            # 获取API密钥信息
            api_key_obj = None
            
            # 如果提供了api_key_id，直接使用该API密钥
            if api_key_id:
                try:
                    api_key_obj = APIKey.objects.get(api_key_id=api_key_id, user=request.user, is_active=True)
                except APIKey.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '指定的API密钥不存在或已禁用',
                        'data': None
                    }, status=404)
            else:
                # 否则，查找该用户的默认API密钥
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True,
                    is_default=True
                ).first()
                
                # 如果没有默认API密钥，则获取最近创建的活跃API密钥
                if not api_key_obj:
                    api_key_obj = APIKey.objects.filter(
                        user=request.user,
                        service_type='coze',
                        is_active=True
                    ).order_by('-create_time').first()
            
            # 检查是否找到了API密钥
            if not api_key_obj:
                return JsonResponse({
                    'code': 400,
                    'message': '未找到可用的API密钥，请先创建API密钥',
                    'data': None
                }, status=400)
            
            # 构建API请求参数
            url = f"{api_key_obj.api_base}/v1/datasets"
            params = {
                'space_id': space_id,
                'page_num': page_num,
                'page_size': page_size
            }
            
            # 添加可选参数
            if name:
                params['name'] = name
                
            if format_type:
                params['format_type'] = format_type
            
            # 构建请求头
            headers = {
                "Authorization": f"Bearer {api_key_obj.api_key}",
                "Content-Type": "application/json"
            }
            
            # 发送API请求
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # 抛出HTTP错误以便捕获
            result = response.json()
            
            # 更新API密钥使用统计
            APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
                usage_count=F('usage_count') + 1,
                last_used_at=timezone.now()
            )
            
            # 返回结果
            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'api_key_id': api_key_obj.api_key_id,
                    'api_key_name': api_key_obj.key_name,
                    'space_id': space_id,
                    'total_count': result.get('data', {}).get('total_count', 0),
                    'datasets': result.get('data', {}).get('dataset_list', [])
                }
            })
            
        except requests.exceptions.RequestException as e:
            # 处理请求异常
            error_msg = str(e)
            try:
                # 尝试解析错误响应
                if hasattr(e, 'response') and e.response is not None:
                    error_data = e.response.json()
                    error_msg = error_data.get('msg', str(e))
            except (json.JSONDecodeError, ValueError, AttributeError) as parse_error:
                # 捕获JSON解析错误和其他可能的错误
                error_msg = f"{error_msg} (解析响应失败: {str(parse_error)})"
            
            return JsonResponse({
                'code': 500,
                'message': f"API调用失败: {error_msg}",
                'data': None
            }, status=500)
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取外部知识库列表失败: {str(e)}',
                'data': None
            }, status=500)

    def delete(self, request, rag_id):
        """删除RAG知识库"""
        try:
            # 获取知识库对象
            try:
                rag_knowledge = RAGKnowledgeBase.objects.get(rag_id=rag_id)
            except RAGKnowledgeBase.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '知识库不存在',
                    'data': None
                }, status=404)
            
            # 检查权限
            if not request.user.is_staff and rag_knowledge.creator != request.user:
                return JsonResponse({
                    'code': 403,
                    'message': '没有权限删除此知识库',
                    'data': None
                }, status=403)
            
            # 获取API密钥信息
            api_key_obj = None
            
            # 查找该用户的默认API密钥
            api_key_obj = APIKey.objects.filter(
                user=request.user,
                service_type='coze',
                is_active=True,
                is_default=True
            ).first()
            
            # 如果没有默认API密钥，则获取最近创建的活跃API密钥
            if not api_key_obj:
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True
                ).order_by('-create_time').first()
            
            # 检查是否找到了API密钥
            if not api_key_obj:
                return JsonResponse({
                    'code': 400,
                    'message': '未找到可用的API密钥，请先创建API密钥',
                    'data': None
                }, status=400)
            
            # 构建API请求参数
            url = f"{api_key_obj.api_base}/v1/datasets/{rag_knowledge.external_dataset_id}"
            
            # 构建请求头
            headers = {
                "Authorization": f"Bearer {api_key_obj.api_key}",
                "Content-Type": "application/json"
            }
            
            # 发送API请求删除外部知识库
            response = requests.delete(url, headers=headers)
            response.raise_for_status()  # 抛出HTTP错误以便捕获
            result = response.json()
            
            # 更新API密钥使用统计
            APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
                usage_count=F('usage_count') + 1,
                last_used_at=timezone.now()
            )
            
            # 删除本地知识库记录
            rag_knowledge.delete()
            
            return JsonResponse({
                'code': 200,
                'message': '知识库删除成功',
                'data': {
                    'rag_id': rag_id,
                    'external_dataset_id': rag_knowledge.external_dataset_id,
                    'name': rag_knowledge.name,
                    'api_response': result
                }
            })
            
        except requests.exceptions.RequestException as e:
            # 处理请求异常
            error_msg = str(e)
            try:
                # 尝试解析错误响应
                if hasattr(e, 'response') and e.response is not None:
                    error_data = e.response.json()
                    error_msg = error_data.get('msg', str(e))
            except (json.JSONDecodeError, ValueError, AttributeError) as parse_error:
                # 捕获JSON解析错误和其他可能的错误
                error_msg = f"{error_msg} (解析响应失败: {str(parse_error)})"
            
            return JsonResponse({
                'code': 500,
                'message': f"API调用失败: {error_msg}",
                'data': None
            }, status=500)
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'删除知识库失败: {str(e)}',
                'data': None
            }, status=500)


# 添加获取外部知识库列表的API路由
@api_view(['GET'])
def list_external_datasets(request):
    """获取外部知识库列表的API端点"""
    view = RAGBaseView()
    return view.list_external_datasets(request)


# 添加查询空间列表的API接口
@api_view(['GET'])
def list_workspaces(request):
    """
    查询Coze平台中的空间列表
    
    GET参数:
    api_key_id (str): 可选，指定使用的API密钥ID，不提供则使用默认密钥
    """
    try:
        # 检查用户认证
        if not request.user.is_authenticated:
            return JsonResponse({
                'code': 401,
                'message': '未授权，请先登录',
                'data': None
            }, status=401)
        
        # 获取API密钥ID参数
        api_key_id = request.GET.get('api_key_id')
        
        # 获取API密钥信息
        api_key_obj = None
        
        # 如果提供了api_key_id，直接使用该API密钥
        if api_key_id:
            try:
                api_key_obj = APIKey.objects.get(api_key_id=api_key_id, user=request.user, is_active=True)
            except APIKey.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '指定的API密钥不存在或已禁用',
                    'data': None
                }, status=404)
        else:
            # 否则，查找该用户的默认API密钥
            api_key_obj = APIKey.objects.filter(
                user=request.user,
                service_type='coze',
                is_active=True,
                is_default=True
            ).first()
            
            # 如果没有默认API密钥，则获取最近创建的活跃API密钥
            if not api_key_obj:
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True
                ).order_by('-create_time').first()
        
        # 检查是否找到了API密钥
        if not api_key_obj:
            return JsonResponse({
                'code': 400,
                'message': '未找到可用的API密钥，请先创建API密钥',
                'data': None
            }, status=400)
        
        # 构建API请求
        url = f"{api_key_obj.api_base}/v1/workspaces"
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key_obj.api_key}",
            "Content-Type": "application/json"
        }
        
        # 发送API请求
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # 抛出HTTP错误以便捕获
        result = response.json()
        
        # 更新API密钥使用统计
        APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
            usage_count=F('usage_count') + 1,
            last_used_at=timezone.now()
        )
        
        # 返回结果
        return JsonResponse(result)
        
    except requests.exceptions.RequestException as e:
        # 处理请求异常
        error_msg = str(e)
        try:
            # 尝试解析错误响应
            if hasattr(e, 'response') and e.response is not None:
                error_data = e.response.json()
                error_msg = error_data.get('msg', str(e))
        except:
            pass
        
        return JsonResponse({
            'code': 500,
            'message': f"API调用失败: {error_msg}",
            'data': None
        }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'获取空间列表失败: {str(e)}',
            'data': None
        }, status=500)


# 添加简化的API密钥配置接口
@api_view(['POST', 'GET'])
def create_api_key_config(request):
    """
    简化的API密钥配置接口
    
    POST请求参数示例:
    {
        "apiKey": "pat_iqYHxPuKfn84xmSd7jTD83UIhiyrHiObwCki3IZ63PrOZzkyVcGSyrCBWfKmgeLm"
    }
    
    GET请求：获取当前用户的默认API密钥
    """
    # 检查用户认证
    if not request.user.is_authenticated:
        return JsonResponse({
            'code': 401,
            'message': '未授权，请先登录',
            'data': None
        }, status=401)
    
    # GET请求处理：查询API密钥
    if request.method == 'GET':
        try:
            # 查找该用户的默认API密钥
            api_key_obj = APIKey.objects.filter(
                user=request.user,
                service_type='coze',
                is_active=True,
                is_default=True
            ).first()
            
            # 如果没有默认API密钥，则获取最近创建的活跃API密钥
            if not api_key_obj:
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True
                ).order_by('-create_time').first()
            
            # 检查是否找到了API密钥
            if not api_key_obj:
                return JsonResponse({
                    'code': 404,
                    'message': '未找到可用的API密钥',
                    'data': None
                }, status=404)
            
            # 返回API密钥
            return JsonResponse({
                'code': 200,
                'message': '获取成功',
                'data': {
                    'apiKey': api_key_obj.api_key
                }
            })
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取API密钥失败: {str(e)}',
                'data': None
            }, status=500)
    
    # POST请求处理：创建API密钥
    try:
        # 获取请求参数
        api_key = request.data.get('apiKey')
        
        # 参数验证
        if not api_key:
            return JsonResponse({
                'code': 400,
                'message': 'API密钥不能为空',
                'data': None
            }, status=400)
        
        # 生成密钥名称（使用密钥的前8位字符，方便识别）
        key_prefix = api_key[:8] if len(api_key) > 8 else api_key
        key_name = f"Coze-{key_prefix}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        # 检查是否已存在相同apiKey的记录
        if APIKey.objects.filter(api_key=api_key, user=request.user).exists():
            return JsonResponse({
                'code': 400,
                'message': '该API密钥已存在',
                'data': None
            }, status=400)
        
        # 创建API密钥
        api_key_obj = APIKey.objects.create(
            key_name=key_name,
            api_key=api_key,
            api_base='https://api.coze.cn',
            service_type='coze',
            is_default=True,  # 设为默认密钥
            user=request.user
        )
        
        # 返回结果
        return JsonResponse({
            'code': 200,
            'message': 'API密钥配置成功',
            'data': {
                'api_key_id': api_key_obj.api_key_id,
                'key_name': api_key_obj.key_name,
                'service_type': api_key_obj.service_type,
                'is_default': api_key_obj.is_default,
                'api_base': api_key_obj.api_base,
                'create_time': api_key_obj.create_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'API密钥配置失败: {str(e)}',
            'data': None
        }, status=500)


# 添加知识库文件上传接口
@api_view(['POST'])
def upload_knowledge_document(request):
    """
    向指定知识库中上传文件
    
    请求参数：
    - dataset_id: 知识库ID
    - document_bases: 文件元数据数组，最多10个文件
    - chunk_strategy: 分段规则
    - format_type: 知识库类型（0:文本, 2:图片）
    
    支持的上传方式：
    1. 文本知识库：
       - 通过Base64上传本地文件
       - 上传在线网页
    2. 图片知识库：
       - 通过file_id上传图片
    """
    try:
        # 检查用户认证
        if not request.user.is_authenticated:
            return JsonResponse({
                'code': 401,
                'message': '未授权，请先登录',
                'data': None
            }, status=401)
        
        # 获取请求参数
        dataset_id = request.data.get('dataset_id')
        document_bases = request.data.get('document_bases', [])
        chunk_strategy = request.data.get('chunk_strategy', {})
        format_type = request.data.get('format_type')
        api_key_id = request.data.get('api_key_id')
        
        # 参数验证
        if not dataset_id:
            return JsonResponse({
                'code': 400,
                'message': '知识库ID不能为空',
                'data': None
            }, status=400)
            
        if not document_bases or not isinstance(document_bases, list):
            return JsonResponse({
                'code': 400,
                'message': '文件元数据不能为空且必须是数组',
                'data': None
            }, status=400)
            
        if len(document_bases) > 10:
            return JsonResponse({
                'code': 400,
                'message': '每次最多上传10个文件',
                'data': None
            }, status=400)
            
        if not chunk_strategy:
            return JsonResponse({
                'code': 400,
                'message': '分段规则不能为空',
                'data': None
            }, status=400)
            
        if format_type is None:
            return JsonResponse({
                'code': 400,
                'message': '知识库类型不能为空',
                'data': None
            }, status=400)
            
        # 获取API密钥信息
        api_key_obj = None
        
        # 如果提供了api_key_id，直接使用该API密钥
        if api_key_id:
            try:
                api_key_obj = APIKey.objects.get(api_key_id=api_key_id, user=request.user, is_active=True)
            except APIKey.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '指定的API密钥不存在或已禁用',
                    'data': None
                }, status=404)
        else:
            # 否则，查找该用户的默认API密钥
            api_key_obj = APIKey.objects.filter(
                user=request.user,
                service_type='coze',
                is_active=True,
                is_default=True
            ).first()
            
            # 如果没有默认API密钥，则获取最近创建的活跃API密钥
            if not api_key_obj:
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True
                ).order_by('-create_time').first()
        
        # 检查是否找到了API密钥
        if not api_key_obj:
            return JsonResponse({
                'code': 400,
                'message': '未找到可用的API密钥，请先创建API密钥',
                'data': None
            }, status=400)
        
        # 构建API请求参数
        url = f"{api_key_obj.api_base}/open_api/knowledge/document/create"
        
        # 构建请求体
        payload = {
            "dataset_id": dataset_id,
            "document_bases": document_bases,
            "chunk_strategy": chunk_strategy,
            "format_type": format_type
        }
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key_obj.api_key}",
            "Content-Type": "application/json",
            "Agw-Js-Conv": "str"  # 防止丢失数字类型参数的精度
        }
        
        # 发送API请求
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # 抛出HTTP错误以便捕获
        result = response.json()
        
        # 更新API密钥使用统计
        APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
            usage_count=F('usage_count') + 1,
            last_used_at=timezone.now()
        )
        
        # 返回结果
        return JsonResponse({
            'code': 200,
            'message': 'success',
            'data': result
        })
        
    except requests.exceptions.RequestException as e:
        # 处理请求异常
        error_msg = str(e)
        try:
            # 尝试解析错误响应
            if hasattr(e, 'response') and e.response is not None:
                error_data = e.response.json()
                error_msg = error_data.get('msg', str(e))
        except (json.JSONDecodeError, ValueError, AttributeError) as parse_error:
            # 捕获JSON解析错误和其他可能的错误
            error_msg = f"{error_msg} (解析响应失败: {str(parse_error)})"
        
        return JsonResponse({
            'code': 500,
            'message': f"API调用失败: {error_msg}",
            'data': None
        }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'上传文件失败: {str(e)}',
            'data': None
        }, status=500)


# 添加知识库文件上传进度查询接口
@api_view(['POST'])
def get_upload_progress(request):
    """
    查询知识库文件上传进度
    
    请求参数：
    - space_id: 空间id
    - dataset_id: 知识库ID
    - document_ids: 需要获取上传进度的文件ID数组，多个文件必须位于同一个知识库中
    - api_key_id: 可选，指定使用的API密钥ID，不提供则使用默认密钥
    
    返回数据:
    - 文件上传进度详情，包括处理状态、进度百分比、预计剩余时间等
    """
    try:
        # 检查用户认证
        if not request.user.is_authenticated:
            return JsonResponse({
                'code': 401,
                'message': '未授权，请先登录',
                'data': None
            }, status=401)
        
        # 获取请求参数
        dataset_id = request.data.get('dataset_id')
        document_ids = request.data.get('document_ids', [])
        api_key_id = request.data.get('api_key_id')
        
        # 参数验证
        if not dataset_id:
            return JsonResponse({
                'code': 400,
                'message': '知识库ID不能为空',
                'data': None
            }, status=400)
            
        if not document_ids or not isinstance(document_ids, list):
            return JsonResponse({
                'code': 400,
                'message': '文件ID不能为空且必须是数组',
                'data': None
            }, status=400)
            
        # 获取API密钥信息
        api_key_obj = None
        
        # 如果提供了api_key_id，直接使用该API密钥
        if api_key_id:
            try:
                api_key_obj = APIKey.objects.get(api_key_id=api_key_id, user=request.user, is_active=True)
            except APIKey.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '指定的API密钥不存在或已禁用',
                    'data': None
                }, status=404)
        else:
            # 否则，查找该用户的默认API密钥
            api_key_obj = APIKey.objects.filter(
                user=request.user,
                service_type='coze',
                is_active=True,
                is_default=True
            ).first()
            
            # 如果没有默认API密钥，则获取最近创建的活跃API密钥
            if not api_key_obj:
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True
                ).order_by('-create_time').first()
        
        # 检查是否找到了API密钥
        if not api_key_obj:
            return JsonResponse({
                'code': 400,
                'message': '未找到可用的API密钥，请先创建API密钥',
                'data': None
            }, status=400)
        
        # 构建API请求参数
        url = f"{api_key_obj.api_base}/v1/datasets/{dataset_id}/process"
        
        # 构建请求体
        payload = {
            "document_ids": document_ids
        }
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key_obj.api_key}",
            "Content-Type": "application/json"
        }
        
        # 发送API请求
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # 抛出HTTP错误以便捕获
        result = response.json()
        
        # 更新API密钥使用统计
        APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
            usage_count=F('usage_count') + 1,
            last_used_at=timezone.now()
        )
        
        # 返回结果
        return JsonResponse({
            'code': 200,
            'message': 'success',
            'data': result.get('data', {})
        })
        
    except requests.exceptions.RequestException as e:
        # 处理请求异常
        error_msg = str(e)
        try:
            # 尝试解析错误响应
            if hasattr(e, 'response') and e.response is not None:
                error_data = e.response.json()
                error_msg = error_data.get('msg', str(e))
        except (json.JSONDecodeError, ValueError, AttributeError) as parse_error:
            # 捕获JSON解析错误和其他可能的错误
            error_msg = f"{error_msg} (解析响应失败: {str(parse_error)})"
        
        return JsonResponse({
            'code': 500,
            'message': f"API调用失败: {error_msg}",
            'data': None
        }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'获取上传进度失败: {str(e)}',
            'data': None
        }, status=500)


# 添加知识库文件列表查询接口
@api_view(['POST'])
def list_knowledge_documents(request):
    """
    查询指定知识库的文件列表
    
    请求参数：
    - dataset_id: 知识库ID
    - page: 页码，默认为1
    - size: 每页记录数，默认为10
    - api_key_id: 可选，指定使用的API密钥ID，不提供则使用默认密钥
    
    返回数据:
    - 知识库文件列表，包含文件详细信息
    """
    try:
        # 检查用户认证
        if not request.user.is_authenticated:
            return JsonResponse({
                'code': 401,
                'message': '未授权，请先登录',
                'data': None
            }, status=401)
        
        # 获取请求参数
        dataset_id = request.data.get('dataset_id')
        page = request.data.get('page', 1)
        size = request.data.get('size', 10)
        api_key_id = request.data.get('api_key_id')
        
        # 参数验证
        if not dataset_id:
            return JsonResponse({
                'code': 400,
                'message': '知识库ID不能为空',
                'data': None
            }, status=400)
            
        # 获取API密钥信息
        api_key_obj = None
        
        # 如果提供了api_key_id，直接使用该API密钥
        if api_key_id:
            try:
                api_key_obj = APIKey.objects.get(api_key_id=api_key_id, user=request.user, is_active=True)
            except APIKey.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '指定的API密钥不存在或已禁用',
                    'data': None
                }, status=404)
        else:
            # 否则，查找该用户的默认API密钥
            api_key_obj = APIKey.objects.filter(
                user=request.user,
                service_type='coze',
                is_active=True,
                is_default=True
            ).first()
            
            # 如果没有默认API密钥，则获取最近创建的活跃API密钥
            if not api_key_obj:
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True
                ).order_by('-create_time').first()
        
        # 检查是否找到了API密钥
        if not api_key_obj:
            return JsonResponse({
                'code': 400,
                'message': '未找到可用的API密钥，请先创建API密钥',
                'data': None
            }, status=400)
        
        # 构建API请求参数
        url = f"{api_key_obj.api_base}/open_api/knowledge/document/list"
        
        # 构建请求体
        payload = {
            "dataset_id": dataset_id,
            "page": int(page),
            "size": int(size)
        }
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key_obj.api_key}",
            "Content-Type": "application/json",
            "Agw-Js-Conv": "str"  # 防止丢失数字类型参数的精度
        }
        
        # 发送API请求
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # 抛出HTTP错误以便捕获
        result = response.json()
        
        # 更新API密钥使用统计
        APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
            usage_count=F('usage_count') + 1,
            last_used_at=timezone.now()
        )
        
        # 构建返回结果
        return_data = {
            'document_list': result.get('document_infos', []),
            'total': result.get('total', 0),
            'page': page,
            'size': size
        }
        
        # 返回结果
        return JsonResponse({
            'code': 200,
            'message': 'success',
            'data': return_data
        })
        
    except requests.exceptions.RequestException as e:
        # 处理请求异常
        error_msg = str(e)
        try:
            # 尝试解析错误响应
            if hasattr(e, 'response') and e.response is not None:
                error_data = e.response.json()
                error_msg = error_data.get('msg', str(e))
        except (json.JSONDecodeError, ValueError, AttributeError) as parse_error:
            # 捕获JSON解析错误和其他可能的错误
            error_msg = f"{error_msg} (解析响应失败: {str(parse_error)})"
        
        return JsonResponse({
            'code': 500,
            'message': f"API调用失败: {error_msg}",
            'data': None
        }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'获取文件列表失败: {str(e)}',
            'data': None
        }, status=500)


# 添加文件上传接口
@api_view(['POST'])
def upload_file(request):
    """
    上传文件到Coze平台
    
    请求参数：
    - file: 要上传的文件（multipart/form-data）
    - api_key_id: 可选，指定使用的API密钥ID，不提供则使用默认密钥
    
    返回数据:
    - file_id: 文件ID
    - file_name: 文件名
    - file_size: 文件大小
    - file_type: 文件类型
    """
    try:
        # 检查用户认证
        if not request.user.is_authenticated:
            return JsonResponse({
                'code': 401,
                'message': '未授权，请先登录',
                'data': None
            }, status=401)
        
        # 获取上传的文件
        if 'file' not in request.FILES:
            return JsonResponse({
                'code': 400,
                'message': '未找到上传的文件',
                'data': None
            }, status=400)
            
        uploaded_file = request.FILES['file']
        
        # 检查文件大小（最大512MB）
        if uploaded_file.size > 512 * 1024 * 1024:
            return JsonResponse({
                'code': 400,
                'message': '文件大小超过限制（最大512MB）',
                'data': None
            }, status=400)
            
        # 获取文件扩展名
        file_extension = uploaded_file.name.split('.')[-1].upper()
        
        # 检查文件类型
        allowed_extensions = {
            # 文档
            'DOC', 'DOCX', 'XLS', 'XLSX', 'PPT', 'PPTX', 'PDF', 'NUMBERS', 'CSV',
            # 文本文件
            'JS', 'CPP', 'PY', 'JAVA', 'C', 'TXT', 'CSS', 'JAVASCRIPT', 'HTML', 'JSON', 'MD',
            # 图片
            'JPG', 'JPG2', 'PNG', 'GIF', 'WEBP', 'HEIC', 'HEIF', 'BMP', 'PCD', 'TIFF',
            # 音频
            'WAV', 'OGG_OPUS',
            # 视频
            'MP4', 'AVI', 'MOV', '3GP', '3GPP', 'FLV', 'WEBM', 'WMV', 'RMVB', 'M4V', 'MKV',
            # 压缩文件
            'RAR', 'ZIP', '7Z', 'GZ', 'GZIP', 'BZ2'
        }
        
        if file_extension not in allowed_extensions:
            return JsonResponse({
                'code': 400,
                'message': f'不支持的文件类型: {file_extension}',
                'data': None
            }, status=400)
        
        # 获取API密钥信息
        api_key_id = request.data.get('api_key_id')
        api_key_obj = None
        
        # 如果提供了api_key_id，直接使用该API密钥
        if api_key_id:
            try:
                api_key_obj = APIKey.objects.get(api_key_id=api_key_id, user=request.user, is_active=True)
            except APIKey.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '指定的API密钥不存在或已禁用',
                    'data': None
                }, status=404)
        else:
            # 否则，查找该用户的默认API密钥
            api_key_obj = APIKey.objects.filter(
                user=request.user,
                service_type='coze',
                is_active=True,
                is_default=True
            ).first()
            
            # 如果没有默认API密钥，则获取最近创建的活跃API密钥
            if not api_key_obj:
                api_key_obj = APIKey.objects.filter(
                    user=request.user,
                    service_type='coze',
                    is_active=True
                ).order_by('-create_time').first()
        
        # 检查是否找到了API密钥
        if not api_key_obj:
            return JsonResponse({
                'code': 400,
                'message': '未找到可用的API密钥，请先创建API密钥',
                'data': None
            }, status=400)
        
        # 构建API请求参数
        url = f"{api_key_obj.api_base}/v1/files/upload"
        
        # 构建请求头
        headers = {
            "Authorization": f"Bearer {api_key_obj.api_key}"
        }
        
        # 准备文件数据
        files = {
            'file': (uploaded_file.name, uploaded_file, uploaded_file.content_type)
        }
        
        # 发送API请求
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status()  # 抛出HTTP错误以便捕获
        result = response.json()
        
        # 更新API密钥使用统计
        APIKey.objects.filter(api_key_id=api_key_obj.api_key_id).update(
            usage_count=F('usage_count') + 1,
            last_used_at=timezone.now()
        )
        
        # 返回结果
        return JsonResponse({
            'code': 200,
            'message': '文件上传成功',
            'data': {
                'file_id': result.get('data', {}).get('file_id'),
                'file_name': uploaded_file.name,
                'file_size': uploaded_file.size,
                'file_type': file_extension,
                'api_response': result
            }
        })
        
    except requests.exceptions.RequestException as e:
        # 处理请求异常
        error_msg = str(e)
        try:
            # 尝试解析错误响应
            if hasattr(e, 'response') and e.response is not None:
                error_data = e.response.json()
                error_msg = error_data.get('msg', str(e))
        except (json.JSONDecodeError, ValueError, AttributeError) as parse_error:
            # 捕获JSON解析错误和其他可能的错误
            error_msg = f"{error_msg} (解析响应失败: {str(parse_error)})"
        
        return JsonResponse({
            'code': 500,
            'message': f"API调用失败: {error_msg}",
            'data': None
        }, status=500)
        
    except Exception as e:
        return JsonResponse({
            'code': 500,
            'message': f'文件上传失败: {str(e)}',
            'data': None
        }, status=500)


