from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import Q
import json
from datetime import datetime, timedelta

from test_platform.models import TestExecutionLog, TestCase, TestSuite


class ExecutionLogView(APIView):
    """测试执行日志视图"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, result_id=None):
        """查询执行日志
        
        支持两种模式:
        1. 查询单个日志详情: /api/log/{log_id}
        2. 查询日志列表: /api/log?case_id=x&suite_id=y&status=z&start_time=xx&end_time=xx&page=1&page_size=10
        """
        # 查询单个日志详情
        if result_id is not None:
            try:
                log = TestExecutionLog.objects.get(suite_result_id=result_id)
                
                # 构建日志详情
                log_data = {
                    'log_id': log.log_id,
                    'case_name': log.case.case_name if log.case else None,
                    'suite_name': log.suite.name if log.suite else None,
                    'suite_result_id': log.suite_result.result_id if log.suite_result else None,
                    'execution_time': log.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': log.status,
                    'duration': log.duration,
                    'executor': log.executor.username if log.executor else None,
                    'request': {
                        'url': log.request_url,
                        'method': log.request_method,
                        'headers': json.loads(log.request_headers) if log.request_headers else {},
                        'body': json.loads(log.request_body) if log.request_body else {}
                    },
                    'response': {
                        'status_code': log.response_status_code,
                        'headers': json.loads(log.response_headers) if log.response_headers else {},
                        'body': json.loads(log.response_body) if log.response_body else {}
                    },
                    'log_detail': log.log_detail,
                    'error_message': log.error_message,
                    'extracted_variables': json.loads(log.extracted_variables) if log.extracted_variables else {},
                    'assertion_results': json.loads(log.assertion_results) if log.assertion_results else {},
                    'environment': {
                        'id': log.environment.environment_id if log.environment else None,
                        'name': log.environment.env_name if log.environment else None
                    },
                    'environment_cover': {
                        'id': log.environment_cover.environment_cover_id if log.environment_cover else None,
                        'name': log.environment_cover.environment_name if log.environment_cover else None
                    }
                }
                
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': log_data
                })
                
            except TestExecutionLog.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '日志不存在',
                    'data': None
                }, status=404)
                
        # 查询日志列表
        else:
            # 获取查询参数
            case_id = request.GET.get('case_id')
            suite_id = request.GET.get('suite_id')
            suite_result_id = request.GET.get('suite_result_id')  # 保留套件结果ID参数
            status = request.GET.get('status')
            start_time = request.GET.get('start_time')
            end_time = request.GET.get('end_time')
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            
            # 构建查询条件
            query = Q()
            
            if case_id:
                query &= Q(case_id=case_id)
            
            if suite_id:
                query &= Q(suite_id=suite_id)
            
            # 套件结果ID查询条件
            if suite_result_id:
                query &= Q(suite_result_id=suite_result_id)
            
            if status:
                query &= Q(status=status)
            
            if start_time and end_time:
                try:
                    start_datetime = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                    end_datetime = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                    query &= Q(execution_time__range=(start_datetime, end_datetime))
                except ValueError:
                    pass
            
            # 执行查询
            logs = TestExecutionLog.objects.filter(query).order_by('-execution_time')
            
            # 计算分页
            total = logs.count()
            start = (page - 1) * page_size
            end = start + page_size
            logs_page = logs[start:end]
            
            # 构建响应数据
            log_list = []
            for log in logs_page:
                log_list.append({
                    'log_id': log.log_id,
                    'case_name': log.case.case_name if log.case else None,
                    'suite_name': log.suite.name if log.suite else None,
                    'suite_result_id': log.suite_result.result_id if log.suite_result else None,
                    'execution_time': log.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': log.status,
                    'duration': log.duration,
                    'request_url': log.request_url,
                    'request_method': log.request_method,
                    'response_status_code': log.response_status_code,
                    'error_message': log.error_message
                })
            
            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'logs': log_list
                }
            })
    
    def post(self, request):
        """
        手动创建日志记录（通常由系统自动调用，但也提供手动调用接口）
        """
        try:
            # 获取请求数据
            case_id = request.data.get('case_id')
            suite_id = request.data.get('suite_id')
            status = request.data.get('status', 'error')  # 默认为错误状态
            duration = float(request.data.get('duration', 0))
            request_data = request.data.get('request', {})
            response_data = request.data.get('response', {})
            log_detail = request.data.get('log_detail', '')
            error_message = request.data.get('error_message', '')
            extracted_variables = request.data.get('extracted_variables', {})
            assertion_results = request.data.get('assertion_results', {})
            
            # 获取关联对象
            case = None
            suite = None
            
            if case_id:
                try:
                    case = TestCase.objects.get(test_case_id=case_id)
                except TestCase.DoesNotExist:
                    pass
            
            if suite_id:
                try:
                    suite = TestSuite.objects.get(suite_id=suite_id)
                except TestSuite.DoesNotExist:
                    pass
            
            # 创建日志
            log = TestExecutionLog.objects.create(
                case=case,
                suite=suite,
                status=status,
                duration=duration,
                executor=request.user,
                request_url=request_data.get('url', ''),
                request_method=request_data.get('method', ''),
                request_headers=json.dumps(request_data.get('headers', {})),
                request_body=json.dumps(request_data.get('body', {})),
                response_status_code=response_data.get('status_code'),
                response_headers=json.dumps(response_data.get('headers', {})),
                response_body=json.dumps(response_data.get('body', {})),
                log_detail=log_detail,
                error_message=error_message,
                extracted_variables=json.dumps(extracted_variables),
                assertion_results=json.dumps(assertion_results)
            )
            
            return JsonResponse({
                'code': 200,
                'message': '日志记录成功',
                'data': {
                    'log_id': log.log_id
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'日志记录失败: {str(e)}',
                'data': None
            }, status=500)
            
    def delete(self, request, log_id):
        """删除日志"""
        try:
            log = TestExecutionLog.objects.get(log_id=log_id)
            log.delete()
            
            return JsonResponse({
                'code': 200,
                'message': '日志删除成功',
                'data': None
            })
            
        except TestExecutionLog.DoesNotExist:
            return JsonResponse({
                'code': 404,
                'message': '日志不存在',
                'data': None
            }, status=404) 