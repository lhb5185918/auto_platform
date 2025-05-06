from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
import json
from django.utils import timezone
from test_platform.models import TestPlan, TestPlanSuite, TestSuite, Project, TestPlanResult
import datetime
from test_platform.tasks import execute_test_plan


class TestPlanView(APIView):
    """测试计划视图"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def post(self, request):
        """创建测试计划"""
        try:
            # 解析请求数据
            data = request.data
            
            # 获取必要参数
            name = data.get('name')
            description = data.get('description', '')
            schedule_type = data.get('scheduleType', 'once')
            execute_time_str = data.get('executeTime')
            cron_expression = data.get('cronExpression', '')
            test_suites = data.get('testSuites', [])
            retry_times = data.get('retryTimes', 0)
            notify_types = data.get('notifyTypes', [])
            project_id = data.get('projectId')
            
            # 验证必要参数
            if not name:
                return JsonResponse({
                    'code': 400,
                    'message': '测试计划名称不能为空',
                    'data': None
                }, status=400)
                
            if not test_suites:
                return JsonResponse({
                    'code': 400,
                    'message': '测试套件不能为空',
                    'data': None
                }, status=400)
                
            if not project_id:
                return JsonResponse({
                    'code': 400,
                    'message': '项目ID不能为空',
                    'data': None
                }, status=400)
                
            # 验证项目是否存在
            try:
                project = Project.objects.get(project_id=project_id)
            except Project.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '项目不存在',
                    'data': None
                }, status=404)
                
            # 解析执行时间
            execute_time = None
            if execute_time_str:
                try:
                    execute_time = datetime.datetime.strptime(execute_time_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    return JsonResponse({
                        'code': 400,
                        'message': '执行时间格式错误，正确格式为：YYYY-MM-DD HH:MM:SS',
                        'data': None
                    }, status=400)
            
            # 验证定时任务表达式
            if schedule_type == 'cron' and not cron_expression:
                return JsonResponse({
                    'code': 400,
                    'message': '定时任务类型需要提供Cron表达式',
                    'data': None
                }, status=400)
                
            # 创建测试计划
            test_plan = TestPlan.objects.create(
                name=name,
                description=description,
                schedule_type=schedule_type,
                execute_time=execute_time,
                cron_expression=cron_expression,
                retry_times=retry_times,
                notify_types=','.join(notify_types) if notify_types else '',
                project=project,
                creator=request.user,
                status='pending'
            )
            
            # 创建测试计划与测试套件的关联
            for index, suite_id in enumerate(test_suites):
                try:
                    suite = TestSuite.objects.get(suite_id=suite_id)
                    # 创建关联
                    TestPlanSuite.objects.create(
                        plan=test_plan,
                        suite=suite,
                        order=index,
                        environment=suite.environment,
                        environment_cover=suite.environment_cover
                    )
                except TestSuite.DoesNotExist:
                    # 如果套件不存在，记录一个错误，但不影响整体创建
                    print(f"测试套件ID {suite_id} 不存在")
            
            # 返回成功响应
            return JsonResponse({
                'code': 200,
                'message': '测试计划创建成功',
                'data': {
                    'plan_id': test_plan.plan_id,
                    'name': test_plan.name,
                    'schedule_type': test_plan.schedule_type,
                    'execute_time': test_plan.execute_time.strftime('%Y-%m-%d %H:%M:%S') if test_plan.execute_time else None,
                    'status': test_plan.status,
                    'create_time': test_plan.create_time.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
            
        except Exception as e:
            # 处理异常情况
            return JsonResponse({
                'code': 500,
                'message': f'创建测试计划失败: {str(e)}',
                'data': None
            }, status=500)
    
    def get(self, request, plan_id=None, project_id=None):
        """获取测试计划列表或详情"""
        try:
            if plan_id:
                # 获取单个测试计划详情
                try:
                    plan = TestPlan.objects.get(plan_id=plan_id)
                except TestPlan.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '测试计划不存在',
                        'data': None
                    }, status=404)

                # 获取关联的测试套件
                plan_suites = plan.plan_suites.all().order_by('order')
                suite_list = []
                
                for plan_suite in plan_suites:
                    suite_data = {
                        'suite_id': plan_suite.suite.suite_id,
                        'name': plan_suite.suite.name,
                        'order': plan_suite.order,
                        'environment_id': plan_suite.environment.environment_id if plan_suite.environment else None,
                        'environment_name': plan_suite.environment.env_name if plan_suite.environment else None,
                        'environment_cover_id': plan_suite.environment_cover.environment_cover_id if plan_suite.environment_cover else None,
                        'environment_cover_name': plan_suite.environment_cover.environment_name if plan_suite.environment_cover else None,
                    }
                    suite_list.append(suite_data)
                
                # 获取最近的执行结果
                latest_results = plan.execution_results.all().order_by('-execution_time')[:5]
                result_list = []
                
                for result in latest_results:
                    result_data = {
                        'result_id': result.result_id,
                        'execution_time': result.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'status': result.status,
                        'duration': result.duration,
                        'pass_rate': result.pass_rate,
                        'total_cases': result.total_cases,
                        'passed_cases': result.passed_cases,
                        'failed_cases': result.failed_cases,
                        'error_cases': result.error_cases
                    }
                    result_list.append(result_data)
                
                # 构建响应数据
                plan_data = {
                    'plan_id': plan.plan_id,
                    'name': plan.name,
                    'description': plan.description,
                    'schedule_type': plan.schedule_type,
                    'execute_time': plan.execute_time.strftime('%Y-%m-%d %H:%M:%S') if plan.execute_time else None,
                    'cron_expression': plan.cron_expression,
                    'retry_times': plan.retry_times,
                    'notify_types': plan.notify_types.split(',') if plan.notify_types else [],
                    'status': plan.status,
                    'project_id': plan.project.project_id,
                    'project_name': plan.project.name,
                    'creator': plan.creator.username if plan.creator else None,
                    'create_time': plan.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'update_time': plan.update_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'last_executed_at': plan.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if plan.last_executed_at else None,
                    'suites': suite_list,
                    'latest_results': result_list
                }
                
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': plan_data
                })
                
            elif project_id:
                # 获取项目的测试计划列表
                plans = TestPlan.objects.filter(project_id=project_id).order_by('-create_time')
                plan_list = []
                
                for plan in plans:
                    # 获取最新的执行结果
                    latest_result = plan.execution_results.all().order_by('-execution_time').first()
                    
                    # 套件数量
                    suite_count = plan.plan_suites.count()
                    
                    plan_data = {
                        'plan_id': plan.plan_id,
                        'name': plan.name,
                        'schedule_type': plan.schedule_type,
                        'execute_time': plan.execute_time.strftime('%Y-%m-%d %H:%M:%S') if plan.execute_time else None,
                        'status': plan.status,
                        'creator': plan.creator.username if plan.creator else None,
                        'create_time': plan.create_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'last_executed_at': plan.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if plan.last_executed_at else None,
                        'suite_count': suite_count,
                        'latest_result': {
                            'result_id': latest_result.result_id,
                            'status': latest_result.status,
                            'pass_rate': latest_result.pass_rate,
                            'execution_time': latest_result.execution_time.strftime('%Y-%m-%d %H:%M:%S')
                        } if latest_result else None
                    }
                    plan_list.append(plan_data)
                
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': plan_list
                })
            
            else:
                # 获取所有测试计划
                plans = TestPlan.objects.all().order_by('-create_time')
                plan_list = []
                
                for plan in plans:
                    plan_data = {
                        'plan_id': plan.plan_id,
                        'name': plan.name,
                        'description': plan.description,
                        'project_id': plan.project.project_id,
                        'project_name': plan.project.name,
                        'schedule_type': plan.schedule_type,
                        'execute_time': plan.execute_time.strftime('%Y-%m-%d %H:%M:%S') if plan.execute_time else None,
                        'cron_expression': plan.cron_expression,
                        'status': plan.status,
                        'last_run_time': plan.last_executed_at.strftime('%Y-%m-%d %H:%M:%S') if plan.last_executed_at else None,
                        'creator': plan.creator.username if plan.creator else None,
                        'create_time': plan.create_time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    plan_list.append(plan_data)
                
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': plan_list
                })
                
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取测试计划失败: {str(e)}',
                'data': None
            }, status=500)
    
    def put(self, request, plan_id):
        """更新测试计划"""
        try:
            # 获取测试计划
            try:
                plan = TestPlan.objects.get(plan_id=plan_id)
            except TestPlan.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试计划不存在',
                    'data': None
                }, status=404)
            
            # 解析请求数据
            data = request.data
            
            # 更新基本信息
            if 'name' in data:
                plan.name = data['name']
                
            if 'description' in data:
                plan.description = data['description']
                
            if 'scheduleType' in data:
                plan.schedule_type = data['scheduleType']
                
            if 'executeTime' in data:
                execute_time_str = data['executeTime']
                if execute_time_str:
                    try:
                        plan.execute_time = datetime.datetime.strptime(execute_time_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        return JsonResponse({
                            'code': 400,
                            'message': '执行时间格式错误，正确格式为：YYYY-MM-DD HH:MM:SS',
                            'data': None
                        }, status=400)
                else:
                    plan.execute_time = None
                    
            if 'cronExpression' in data:
                plan.cron_expression = data['cronExpression']
                
            if 'retryTimes' in data:
                plan.retry_times = data['retryTimes']
                
            if 'notifyTypes' in data:
                notify_types = data['notifyTypes']
                plan.notify_types = ','.join(notify_types) if notify_types else ''
                
            if 'status' in data:
                plan.status = data['status']
                
            # 保存更新
            plan.save()
            
            # 处理测试套件更新
            if 'testSuites' in data:
                test_suites = data['testSuites']
                
                # 删除旧的关联
                TestPlanSuite.objects.filter(plan=plan).delete()
                
                # 创建新的关联
                for index, suite_id in enumerate(test_suites):
                    try:
                        suite = TestSuite.objects.get(suite_id=suite_id)
                        TestPlanSuite.objects.create(
                            plan=plan,
                            suite=suite,
                            order=index,
                            environment=suite.environment,
                            environment_cover=suite.environment_cover
                        )
                    except TestSuite.DoesNotExist:
                        print(f"测试套件ID {suite_id} 不存在")
            
            return JsonResponse({
                'code': 200,
                'message': '测试计划更新成功',
                'data': {
                    'plan_id': plan.plan_id,
                    'name': plan.name,
                    'schedule_type': plan.schedule_type,
                    'execute_time': plan.execute_time.strftime('%Y-%m-%d %H:%M:%S') if plan.execute_time else None,
                    'status': plan.status,
                    'update_time': plan.update_time.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'更新测试计划失败: {str(e)}',
                'data': None
            }, status=500)
    
    def delete(self, request, plan_id):
        """删除测试计划"""
        try:
            # 获取测试计划
            try:
                plan = TestPlan.objects.get(plan_id=plan_id)
            except TestPlan.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试计划不存在',
                    'data': None
                }, status=404)
            
            # 删除测试计划
            plan.delete()
            
            return JsonResponse({
                'code': 200,
                'message': '测试计划删除成功',
                'data': None
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'删除测试计划失败: {str(e)}',
                'data': None
            }, status=500)
    
    def execute_plan(self, request, plan_id):
        """手动执行测试计划"""
        try:
            # 获取测试计划
            try:
                plan = TestPlan.objects.get(plan_id=plan_id)
            except TestPlan.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试计划不存在',
                    'data': None
                }, status=404)
            
            # 检查计划状态
            if plan.status == 'running':
                return JsonResponse({
                    'code': 400,
                    'message': '测试计划正在执行中',
                    'data': None
                }, status=400)
            
            # 异步执行测试计划
            task = execute_test_plan.delay(plan.plan_id)
            
            # 更新计划状态
            plan.status = 'running'
            plan.save()
            
            return JsonResponse({
                'code': 200,
                'message': '测试计划开始执行',
                'data': {
                    'plan_id': plan.plan_id,
                    'task_id': task.id,
                    'status': 'running'
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'执行测试计划失败: {str(e)}',
                'data': None
            }, status=500)
    
    def get_plan_executions(self, request, plan_id):
        """获取测试计划的执行历史记录"""
        try:
            # 验证计划是否存在
            try:
                plan = TestPlan.objects.get(plan_id=plan_id)
            except TestPlan.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试计划不存在',
                    'data': None
                }, status=404)
            
            # 获取分页参数
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('pageSize', 10))
            
            # 计算分页索引
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            
            # 获取测试计划的执行结果，按执行时间倒序排列
            executions = TestPlanResult.objects.filter(
                plan=plan
            ).order_by('-execution_time')
            
            # 计算总记录数
            total_count = executions.count()
            
            # 分页
            executions_page = executions[start_index:end_index]
            
            # 构建响应数据
            execution_list = []
            for execution in executions_page:
                # 解析结果数据，获取摘要信息和完整的result_data
                execution_summary = {}
                full_result_data = {}
                
                try:
                    if execution.result_data:
                        full_result_data = json.loads(execution.result_data)
                        if isinstance(full_result_data, dict) and 'execution_summary' in full_result_data:
                            execution_summary = full_result_data.get('execution_summary', {})
                except Exception as e:
                    print(f"解析结果数据失败: {str(e)}")
                
                execution_data = {
                    'result_id': execution.result_id,
                    'execution_time': execution.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': execution.status,
                    'duration': execution.duration,
                    'total_suites': execution.total_suites,
                    'passed_suites': execution.passed_suites,
                    'failed_suites': execution.failed_suites,
                    'error_suites': execution.error_suites,
                    'total_cases': execution.total_cases,
                    'passed_cases': execution.passed_cases,
                    'failed_cases': execution.failed_cases,
                    'error_cases': execution.error_cases,
                    'skipped_cases': execution.skipped_cases,
                    'pass_rate': execution.pass_rate,
                    'executor': execution.executor.username if execution.executor else None,
                    'summary': execution_summary,
                    'result_data': full_result_data  # 添加完整的result_data
                }
                execution_list.append(execution_data)
            
            return JsonResponse({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': total_count,
                    'page': page,
                    'page_size': page_size,
                    'executions': execution_list
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'获取执行历史失败: {str(e)}',
                'data': None
            }, status=500) 