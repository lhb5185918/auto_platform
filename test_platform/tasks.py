from celery import shared_task
from test_platform.models import TestPlan, TestPlanSuite, TestPlanResult, TestSuiteResult, TestExecutionLog
from django.utils import timezone
from django.db.models import Q
import json
import datetime
from croniter import croniter
import logging
from django.urls import reverse
from django.test import RequestFactory
from test_platform.views.report_view import TestReportView

# 配置日志
logger = logging.getLogger(__name__)

@shared_task
def execute_test_plan(plan_id):
    """执行指定的测试计划"""
    try:
        # 导入需要的模型和视图（放在函数内部避免循环导入）
        from test_platform.models import TestPlan, TestPlanSuite, TestPlanResult, TestSuiteResult, TestExecutionLog
        
        plan = TestPlan.objects.get(plan_id=plan_id)
        logger.info(f"开始执行测试计划: {plan.name} (ID: {plan.plan_id})")
        
        # 更新测试计划状态为执行中
        plan.status = 'running'
        plan.save()
        
        # 获取测试计划中的所有测试套件
        plan_suites = TestPlanSuite.objects.filter(plan=plan).order_by('order')
        total_suites = plan_suites.count()
        
        # 检查是否有测试套件需要执行
        logger.info(f"找到 {total_suites} 个测试套件需要执行")
        if total_suites == 0:
            logger.warning(f"测试计划 {plan.name} (ID: {plan.plan_id}) 没有关联任何测试套件!")
            
            # 即使没有测试套件，也创建一个结果记录
            start_time = timezone.now()
            end_time = start_time
            duration = 0
            status = 'pass'  # 没有测试套件，默认为通过
            
            # 生成结果数据
            result_info = {
                'execution_summary': {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'duration': duration,
                    'status': status,
                    'total_suites': 0,
                    'passed_suites': 0,
                    'failed_suites': 0,
                    'error_suites': 0,
                    'total_cases': 0,
                    'passed_cases': 0,
                    'failed_cases': 0,
                    'error_cases': 0,
                    'skipped_cases': 0,
                    'pass_rate': 0,
                    'message': '测试计划没有关联任何测试套件'
                },
                'suite_results': []
            }
            
            # 创建测试计划结果记录
            plan_result = TestPlanResult.objects.create(
                plan=plan,
                execution_time=start_time,
                status=status,
                duration=duration,
                total_suites=0,
                passed_suites=0,
                failed_suites=0,
                error_suites=0,
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                error_cases=0,
                skipped_cases=0,
                pass_rate=0,
                result_data=json.dumps(result_info),
                executor=plan.creator
            )
            
            # 更新测试计划状态
            plan.status = 'completed' if schedule_type_requires_reset(plan.schedule_type) else 'pending'
            plan.last_executed_at = end_time
            plan.save()
            
            logger.info(f"测试计划执行完成(无测试套件): {plan.name} (ID: {plan.plan_id})")
            
            return {
                'success': True,
                'plan_id': plan.plan_id,
                'result_id': plan_result.result_id,
                'status': status,
                'message': '测试计划没有包含任何测试套件'
            }
        
        start_time = timezone.now()
        
        # 初始化结果统计
        passed_suites = 0
        failed_suites = 0
        error_suites = 0
        total_cases = 0
        passed_cases = 0
        failed_cases = 0
        error_cases = 0
        skipped_cases = 0
        
        # 用于存储详细执行结果
        execution_results = []
        
        # 依次执行测试套件
        for plan_suite in plan_suites:
            try:
                logger.info(f"开始执行测试套件: {plan_suite.suite.name} (ID: {plan_suite.suite.suite_id})")
                
                # 调用测试套件执行方法
                from test_platform.views.test_case_view import TestSuiteView
                suite_view = TestSuiteView()
                
                # 创建模拟请求
                class MockRequest:
                    def __init__(self, user):
                        self.user = user
                        self.data = {}
                
                mock_request = MockRequest(plan.creator)
                suite_id = plan_suite.suite.suite_id
                
                # 确定环境
                env_id = None
                if plan_suite.environment:
                    env_id = plan_suite.environment.environment_id
                    logger.info(f"使用环境 ID: {env_id} 执行测试套件")
                
                # 执行测试套件
                logger.info(f"调用 execute_suite 方法执行测试套件 {suite_id}")
                suite_result = suite_view.execute_suite(mock_request, suite_id, environment_id=env_id)
                
                # 解析套件执行结果
                suite_result_data = json.loads(suite_result.content)
                result_id = suite_result_data.get('data', {}).get('result_id')
                suite_status = suite_result_data.get('data', {}).get('status', '').lower()
                
                logger.info(f"测试套件执行完成: ID={suite_id}, 结果ID={result_id}, 状态={suite_status}")
                
                # 获取测试套件结果详情
                try:
                    # 获取详细测试结果
                    suite_result_obj = TestSuiteResult.objects.get(result_id=result_id)
                    logger.info(f"成功获取测试套件结果: ID={result_id}, 状态={suite_result_obj.status}")
                    
                    # 更新统计数据
                    if suite_result_obj.status == 'pass':
                        passed_suites += 1
                    elif suite_result_obj.status == 'fail':
                        failed_suites += 1
                    else:
                        error_suites += 1
                    
                    total_cases += suite_result_obj.total_cases
                    passed_cases += suite_result_obj.passed_cases
                    failed_cases += suite_result_obj.failed_cases
                    error_cases += suite_result_obj.error_cases
                    skipped_cases += suite_result_obj.skipped_cases
                    
                    # 从测试报告接口获取详细结果
                    try:
                        # 导入需要的模块（放在函数内避免循环导入）
                        from django.urls import reverse
                        from django.test import RequestFactory
                        from test_platform.views.report_view import TestReportView
                        
                        # 创建请求获取测试报告详情
                        factory = RequestFactory()
                        report_request = factory.get('/')
                        report_request.user = plan.creator
                        
                        # 获取详细报告
                        report_view = TestReportView()
                        detailed_report = report_view.get(report_request, result_id=result_id)
                        detailed_data = json.loads(detailed_report.content).get('data', {})
                        
                        # 获取测试套件执行的日志记录
                        execution_logs = TestExecutionLog.objects.filter(
                            suite_result_id=result_id
                        ).order_by('-execution_time')
                        
                        # 记录找到的日志数量
                        logger.info(f"找到 {execution_logs.count()} 条测试套件执行日志")
                        
                        # 处理日志记录
                        log_entries = []
                        for log in execution_logs:
                            log_entry = {
                                'log_id': log.log_id,
                                'execution_time': log.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'status': log.status,
                                'duration': log.duration,
                                'request_url': log.request_url,
                                'request_method': log.request_method,
                                'log_detail': log.log_detail,
                                'error_message': log.error_message or '',
                            }
                            
                            # 添加请求和响应的详细信息，如果可解析为JSON则解析
                            try:
                                if log.request_headers:
                                    log_entry['request_headers'] = json.loads(log.request_headers)
                                if log.request_body:
                                    log_entry['request_body'] = json.loads(log.request_body)
                                if log.response_headers:
                                    log_entry['response_headers'] = json.loads(log.response_headers)
                                if log.response_body:
                                    log_entry['response_body'] = json.loads(log.response_body)
                            except json.JSONDecodeError:
                                # 如果解析失败，保留原始文本
                                if log.request_headers and 'request_headers' not in log_entry:
                                    log_entry['request_headers'] = log.request_headers
                                if log.request_body and 'request_body' not in log_entry:
                                    log_entry['request_body'] = log.request_body
                                if log.response_headers and 'response_headers' not in log_entry:
                                    log_entry['response_headers'] = log.response_headers
                                if log.response_body and 'response_body' not in log_entry:
                                    log_entry['response_body'] = log.response_body
                            
                            log_entries.append(log_entry)
                        
                        # 添加到执行结果，包含完整的测试用例结果和日志记录
                        suite_detail = {
                            'suite_id': suite_id,
                            'suite_name': plan_suite.suite.name,
                            'result_id': result_id,
                            'status': suite_result_obj.status,
                            'total_cases': suite_result_obj.total_cases,
                            'passed_cases': suite_result_obj.passed_cases,
                            'failed_cases': suite_result_obj.failed_cases,
                            'error_cases': suite_result_obj.error_cases,
                            'duration': suite_result_obj.duration,
                            'pass_rate': suite_result_obj.pass_rate,
                            'execution_time': suite_result_obj.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'environment': plan_suite.environment.env_name if plan_suite.environment else None,
                            'caseResults': detailed_data.get('caseResults', []),
                            'execution_logs': log_entries  # 添加执行日志记录
                        }
                        
                        # 检查suite_result_obj.result_data内容并记录
                        try:
                            if suite_result_obj.result_data:
                                result_data_obj = json.loads(suite_result_obj.result_data)
                                logger.info(f"测试套件结果数据包含以下键: {list(result_data_obj.keys())}")
                                # 增强suite_detail，添加原始result_data内容
                                suite_detail['result_data'] = result_data_obj
                        except Exception as e:
                            logger.warning(f"解析suite_result_obj.result_data失败: {str(e)}")
                        
                    except Exception as report_error:
                        logger.warning(f"获取详细测试报告失败: {str(report_error)}")
                        
                        # 尝试从结果数据中解析测试用例详情
                        case_results = []
                        try:
                            if suite_result_obj.result_data:
                                result_data_obj = json.loads(suite_result_obj.result_data)
                                if isinstance(result_data_obj, list):
                                    case_results = result_data_obj
                                elif isinstance(result_data_obj, dict) and 'case_results' in result_data_obj:
                                    case_results = result_data_obj.get('case_results', [])
                                elif isinstance(result_data_obj, dict) and 'results' in result_data_obj:
                                    case_results = result_data_obj.get('results', [])
                        except Exception as detail_error:
                            logger.warning(f"解析测试用例结果详情失败: {str(detail_error)}")
                        
                        # 获取测试套件执行的日志记录
                        execution_logs = TestExecutionLog.objects.filter(
                            suite_result_id=result_id
                        ).order_by('-execution_time')
                        
                        # 处理日志记录
                        log_entries = []
                        for log in execution_logs:
                            log_entry = {
                                'log_id': log.log_id,
                                'execution_time': log.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'status': log.status,
                                'duration': log.duration,
                                'request_url': log.request_url,
                                'request_method': log.request_method,
                                'log_detail': log.log_detail,
                                'error_message': log.error_message or '',
                            }
                            log_entries.append(log_entry)
                        
                        # 添加基本执行结果信息和日志记录
                        suite_detail = {
                            'suite_id': suite_id,
                            'suite_name': plan_suite.suite.name,
                            'result_id': result_id,
                            'status': suite_result_obj.status,
                            'total_cases': suite_result_obj.total_cases,
                            'passed_cases': suite_result_obj.passed_cases,
                            'failed_cases': suite_result_obj.failed_cases,
                            'error_cases': suite_result_obj.error_cases,
                            'duration': suite_result_obj.duration,
                            'pass_rate': suite_result_obj.pass_rate,
                            'execution_time': suite_result_obj.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'environment': plan_suite.environment.env_name if plan_suite.environment else None,
                            'caseResults': case_results,
                            'execution_logs': log_entries  # 添加执行日志记录
                        }
                    
                    # 将结果添加到执行结果列表
                    execution_results.append(suite_detail)
                    logger.info(f"添加测试套件 {suite_id} 结果到执行结果列表，当前列表长度: {len(execution_results)}")
                    
                except Exception as e:
                    logger.warning(f"获取套件结果详情失败: {str(e)}")
                    # 如果找不到结果记录，根据返回状态统计
                    if suite_status == 'pass':
                        passed_suites += 1
                    elif suite_status == 'fail':
                        failed_suites += 1
                    else:
                        error_suites += 1
                    
                    # 尝试获取执行日志，即使没有找到TestSuiteResult记录
                    execution_logs = TestExecutionLog.objects.filter(
                        suite_id=suite_id
                    ).order_by('-execution_time')[:5]  # 获取最近的5条记录
                    
                    log_entries = []
                    for log in execution_logs:
                        log_entry = {
                            'log_id': log.log_id,
                            'execution_time': log.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                            'status': log.status,
                            'duration': log.duration,
                            'request_url': log.request_url,
                            'request_method': log.request_method,
                            'log_detail': log.log_detail,
                            'error_message': log.error_message or '',
                        }
                        log_entries.append(log_entry)
                    
                    # 添加到执行结果 (简化版本，但包含日志)
                    suite_detail = {
                        'suite_id': suite_id,
                        'suite_name': plan_suite.suite.name,
                        'result_id': result_id,
                        'status': suite_status,
                        'duration': suite_result_data.get('data', {}).get('duration', 0),
                        'note': '无法获取详细结果信息',
                        'execution_logs': log_entries  # 添加执行日志记录
                    }
                    
                    # 将结果添加到执行结果列表
                    execution_results.append(suite_detail)
                    logger.info(f"添加测试套件 {suite_id} 简化结果到执行结果列表，当前列表长度: {len(execution_results)}")
                
            except Exception as e:
                logger.error(f"执行套件失败: {plan_suite.suite.name} (ID: {plan_suite.suite.suite_id}), 错误: {str(e)}")
                # 套件执行异常
                error_suites += 1
                
                # 尝试获取执行日志，即使执行失败
                execution_logs = TestExecutionLog.objects.filter(
                    suite_id=plan_suite.suite.suite_id
                ).order_by('-execution_time')[:1]  # 可能会有错误日志记录
                
                log_entries = []
                for log in execution_logs:
                    log_entry = {
                        'log_id': log.log_id,
                        'execution_time': log.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'status': log.status,
                        'duration': log.duration,
                        'request_url': log.request_url,
                        'request_method': log.request_method,
                        'log_detail': log.log_detail,
                        'error_message': log.error_message or '',
                    }
                    log_entries.append(log_entry)
                
                suite_detail = {
                    'suite_id': plan_suite.suite.suite_id,
                    'suite_name': plan_suite.suite.name,
                    'status': 'error',
                    'error_message': str(e),
                    'execution_logs': log_entries  # 添加执行日志记录
                }
                
                # 将结果添加到执行结果列表
                execution_results.append(suite_detail)
                logger.info(f"添加测试套件 {plan_suite.suite.suite_id} 错误结果到执行结果列表，当前列表长度: {len(execution_results)}")
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        # 计算通过率
        pass_rate = 0
        if total_cases > 0:
            pass_rate = (passed_cases / total_cases) * 100
        
        # 判断整体状态
        if failed_suites > 0 or error_suites > 0:
            status = 'partial' if passed_suites > 0 else 'fail'
        else:
            status = 'pass'
            
        # 生成结果数据
        result_info = {
            'execution_summary': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration': duration,
                'status': status,
                'total_suites': total_suites,
                'passed_suites': passed_suites,
                'failed_suites': failed_suites,
                'error_suites': error_suites,
                'total_cases': total_cases,
                'passed_cases': passed_cases,
                'failed_cases': failed_cases,
                'error_cases': error_cases,
                'skipped_cases': skipped_cases,
                'pass_rate': pass_rate
            },
            'suite_results': execution_results
        }
        
        # 日志记录结果信息
        logger.info(f"测试计划执行结果摘要: {result_info['execution_summary']}")
        logger.info(f"测试套件结果数量: {len(execution_results)}")
        
        # 检查执行结果是否为空
        if len(execution_results) == 0:
            logger.warning("警告: 没有测试套件执行结果数据!")
        else:
            logger.info(f"第一个测试套件结果: {json.dumps({k: v for k, v in execution_results[0].items() if k != 'execution_logs'})}")
        
        # 创建测试计划结果记录
        plan_result = TestPlanResult.objects.create(
            plan=plan,
            execution_time=start_time,
            status=status,
            duration=duration,
            total_suites=total_suites,
            passed_suites=passed_suites,
            failed_suites=failed_suites,
            error_suites=error_suites,
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            error_cases=error_cases,
            skipped_cases=skipped_cases,
            pass_rate=pass_rate,
            result_data=json.dumps(result_info),
            executor=plan.creator
        )
        
        # 验证结果数据是否正确保存
        try:
            saved_result = TestPlanResult.objects.get(result_id=plan_result.result_id)
            saved_data = json.loads(saved_result.result_data)
            saved_suite_results = saved_data.get('suite_results', [])
            logger.info(f"验证保存的结果数据: 测试套件结果数量 = {len(saved_suite_results)}")
        except Exception as e:
            logger.error(f"验证结果数据失败: {str(e)}")
        
        # 更新测试计划状态
        plan.status = 'completed' if schedule_type_requires_reset(plan.schedule_type) else 'pending'
        plan.last_executed_at = end_time
        plan.save()
        
        logger.info(f"测试计划执行完成: {plan.name} (ID: {plan.plan_id}), 状态: {status}")
        
        # 处理通知
        if plan.notify_types:
            send_plan_execution_notification.delay(plan.plan_id, plan_result.result_id)
        
        return {
            'success': True,
            'plan_id': plan.plan_id,
            'result_id': plan_result.result_id,
            'status': status
        }
    except Exception as e:
        logger.error(f"执行测试计划出错: {str(e)}")
        # 尝试将计划状态恢复为待执行
        try:
            from test_platform.models import TestPlan
            plan = TestPlan.objects.get(plan_id=plan_id)
            plan.status = 'pending'
            plan.save()
        except Exception:
            pass
        
        return {
            'success': False,
            'error': str(e),
            'plan_id': plan_id
        }

def schedule_type_requires_reset(schedule_type):
    """判断计划类型是否需要重置状态"""
    # 非一次性计划执行后仍保持pending状态
    return schedule_type == 'once'

@shared_task
def send_plan_execution_notification(plan_id, result_id):
    """发送测试计划执行结果通知"""
    try:
        # 在函数内部导入模型，避免循环导入
        from test_platform.models import TestPlan, TestPlanResult
        
        plan = TestPlan.objects.get(plan_id=plan_id)
        result = TestPlanResult.objects.get(result_id=result_id)
        
        notify_types = plan.notify_types.split(',') if plan.notify_types else []
        
        logger.info(f"开始发送测试计划通知: {plan.name} (ID: {plan.plan_id}), 通知类型: {notify_types}")
        
        # 实现各种通知方式
        for notify_type in notify_types:
            if notify_type == 'email':
                # 实现发送邮件
                pass
            elif notify_type == 'dingtalk':
                # 实现钉钉通知
                pass
            elif notify_type == 'wechat':
                # 实现微信通知
                pass
            elif notify_type == 'sms':
                # 实现短信通知
                pass
                
        return {
            'success': True,
            'plan_id': plan_id,
            'result_id': result_id,
            'notify_types': notify_types
        }
            
    except Exception as e:
        logger.error(f"发送通知失败: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'plan_id': plan_id,
            'result_id': result_id
        }

@shared_task(name='test_platform.tasks.check_scheduled_test_plans')
def check_scheduled_test_plans():
    """检查并执行计划中的测试计划"""
    try:
        # 导入TestPlan模型（这里导入是为了避免循环导入问题）
        from test_platform.models import TestPlan
        
        now = timezone.now()
        logger.info(f"开始检查定时测试计划: {now}")
        
        # 查找一次性执行计划（状态为pending且执行时间已到）
        once_plans = TestPlan.objects.filter(
            status='pending',
            schedule_type='once',
            execute_time__lte=now
        )
        
        for plan in once_plans:
            logger.info(f"执行一次性测试计划: {plan.name} (ID: {plan.plan_id})")
            execute_test_plan.delay(plan.plan_id)
            
        # 处理每日执行的计划
        daily_plans = TestPlan.objects.filter(
            status='pending',
            schedule_type='daily'
        )
        
        for plan in daily_plans:
            if plan.execute_time:
                # 检查当天的执行时间是否已到
                plan_time = plan.execute_time.time()
                now_time = now.time()
                if now_time >= plan_time and (now - now.replace(hour=plan_time.hour, minute=plan_time.minute, second=0)).total_seconds() < 120:
                    logger.info(f"执行每日测试计划: {plan.name} (ID: {plan.plan_id})")
                    execute_test_plan.delay(plan.plan_id)
        
        # 处理每周执行的计划
        weekly_plans = TestPlan.objects.filter(
            status='pending',
            schedule_type='weekly'
        )
        
        for plan in weekly_plans:
            if plan.execute_time:
                # 检查当天是否是计划的执行星期几
                plan_weekday = plan.execute_time.weekday()
                now_weekday = now.weekday()
                
                if now_weekday == plan_weekday:
                    # 再检查时间是否已到
                    plan_time = plan.execute_time.time()
                    now_time = now.time()
                    if now_time >= plan_time and (now - now.replace(hour=plan_time.hour, minute=plan_time.minute, second=0)).total_seconds() < 120:
                        logger.info(f"执行每周测试计划: {plan.name} (ID: {plan.plan_id})")
                        execute_test_plan.delay(plan.plan_id)
        
        # 处理Cron表达式的执行计划
        cron_plans = TestPlan.objects.filter(
            status='pending',
            schedule_type='cron',
        ).exclude(cron_expression='')
        
        for plan in cron_plans:
            try:
                # 检查cron表达式是否有效
                cron = croniter(plan.cron_expression, now)
                # 获取下一次执行时间
                next_run = cron.get_prev(datetime)
                
                # 如果最近一次执行时间在当前时间的前2分钟内，则执行任务
                time_diff = (now - timezone.make_aware(next_run)).total_seconds()
                if 0 <= time_diff < 120:
                    logger.info(f"执行CRON计划任务: {plan.name} (ID: {plan.plan_id})")
                    execute_test_plan.delay(plan.plan_id)
            except Exception as e:
                logger.error(f"解析CRON表达式出错: {plan.name} (ID: {plan.plan_id}), 错误: {str(e)}")
                
        return f"检查完成: 发现 {once_plans.count()} 个一次性计划"
            
    except Exception as e:
        logger.error(f"检查测试计划时出错: {str(e)}")
        return f"检查失败: {str(e)}"

@shared_task
def retry_failed_plans():
    """重试失败的测试计划"""
    failed_plans = TestPlan.objects.filter(status='failed')
    
    for plan in failed_plans:
        # 检查重试次数
        results = TestPlanResult.objects.filter(plan=plan)
        retry_count = results.count()
        
        if retry_count < plan.retry_times:
            execute_test_plan.delay(plan.plan_id)
            
@shared_task
def reset_stalled_plans():
    """重置卡在执行中状态的测试计划"""
    # 查找执行时间超过1小时的测试计划
    one_hour_ago = timezone.now() - datetime.timedelta(hours=1)
    
    stalled_plans = TestPlan.objects.filter(
        status='running',
        update_time__lt=one_hour_ago
    )
    
    for plan in stalled_plans:
        plan.status = 'failed'
        plan.save()
        
        # 记录错误
        TestPlanResult.objects.create(
            plan=plan,
            execution_time=one_hour_ago,
            status='error',
            error_message='测试计划执行超时',
            executor=plan.creator
        ) 