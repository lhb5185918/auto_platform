from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from test_platform.models import TestSuite, TestSuiteCase, TestResult, TestSuiteResult, Project
import json
from django.db.models import Max, Subquery, OuterRef
from django.db import connection


class TestReportView(APIView):
    """测试报告视图"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, suite_id=None, project_id=None, result_id=None):
        """
        获取测试报告
        - 如果提供了suite_id，则获取该测试套件的最新执行结果报告
        - 如果提供了project_id，则获取该项目下所有测试套件的最新执行报告列表
        - 如果提供了result_id，则获取指定ID的测试报告详情
        """
        # 获取指定ID的测试报告详情
        if result_id is not None:
            try:
                # 获取指定ID的测试报告
                try:
                    result = TestSuiteResult.objects.get(result_id=result_id)
                except TestSuiteResult.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '测试报告不存在',
                        'data': None
                    })
                
                # 获取关联的测试套件
                try:
                    test_suite = TestSuite.objects.get(suite_id=result.suite_id)
                except TestSuite.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '关联的测试套件不存在',
                        'data': None
                    })
                
                try:
                    # 解析结果数据
                    result_data = json.loads(result.result_data)
                    
                    # 状态转换为中文
                    status_map = {
                        'pass': '通过',
                        'fail': '失败',
                        'error': '错误',
                        'skip': '跳过',
                        'partial': '部分通过'
                    }
                    
                    result_status = status_map.get(result.status, result.status)
                    
                    # 转换用例结果格式
                    case_results = []
                    for case in result_data.get('results', []):
                        # 状态转换为中文
                        case_status = '通过' if case.get('status') == 'PASS' else '失败'
                        
                        # 添加格式化后的用例结果
                        case_results.append({
                            'id': str(case.get('case_id', '')),
                            'title': case.get('title', ''),
                            'api': case.get('api_path', ''),
                            'method': case.get('method', ''),
                            'duration': int(float(case.get('duration', 0)) * 1000),  # 转换为毫秒
                            'status': case_status,
                            'message': case.get('error', '执行成功') if case_status == '失败' else '验证成功',
                            'requestData': str(case.get('request', {})),
                            'responseData': str(case.get('response', {}))
                        })
                    
                    # 构建符合前端需求的响应数据
                    report_data = {
                        'id': str(result.result_id),
                        'suiteId': str(test_suite.suite_id),
                        'suiteName': test_suite.name,
                        'executionTime': result.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': result.duration,
                        'environment': result.environment.env_name if result.environment else '未指定环境',
                        'totalCases': result.total_cases,
                        'passedCases': result.passed_cases,
                        'failedCases': result.failed_cases + result.error_cases,  # 合并失败和错误
                        'passRate': result.pass_rate,
                        'result': result_status,
                        'caseResults': case_results,
                        'projectId': test_suite.project_id,  # 添加项目ID
                        'projectName': test_suite.project.name,  # 添加项目名称
                        'creator': result.creator.username if result.creator else '未知用户'  # 添加执行者
                    }
                    
                    return JsonResponse({
                        'code': 200,
                        'message': 'success',
                        'data': report_data
                    })
                    
                except json.JSONDecodeError:
                    # 如果结果数据解析失败，则使用数据库中的统计数据生成基本报告
                    report_data = {
                        'id': str(result.result_id),
                        'suiteId': str(test_suite.suite_id),
                        'suiteName': test_suite.name,
                        'executionTime': result.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': result.duration,
                        'environment': result.environment.env_name if result.environment else '未指定环境',
                        'totalCases': result.total_cases,
                        'passedCases': result.passed_cases,
                        'failedCases': result.failed_cases + result.error_cases,
                        'passRate': result.pass_rate,
                        'result': status_map.get(result.status, result.status),
                        'caseResults': [],
                        'projectId': test_suite.project_id,
                        'projectName': test_suite.project.name,
                        'creator': result.creator.username if result.creator else '未知用户',
                        'error': '结果数据解析失败'
                    }
                    
                    return JsonResponse({
                        'code': 200,
                        'message': '结果数据部分加载',
                        'data': report_data
                    })
                
            except Exception as e:
                return JsonResponse({
                    'code': 500,
                    'message': f'获取测试报告详情失败: {str(e)}',
                    'data': None
                })
        
        # 获取项目的测试报告列表
        elif project_id is not None:
            try:
                # 验证项目是否存在
                try:
                    project = Project.objects.get(project_id=project_id)
                except Project.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '项目不存在',
                        'data': None
                    })
                
                # 获取分页参数
                page = int(request.GET.get('page', 1))
                page_size = int(request.GET.get('pageSize', 10))
                
                # 使用原生SQL查询项目下所有的测试报告，并按执行时间降序排序
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT tr.* 
                        FROM test_platform_testsuiteresult tr
                        INNER JOIN test_platform_testsuite ts ON tr.suite_id = ts.suite_id
                        WHERE ts.project_id = %s
                        ORDER BY tr.execution_time DESC
                    """, [project_id])
                    
                    # 获取列名
                    columns = [col[0] for col in cursor.description]
                    
                    # 获取所有结果
                    all_results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                # 计算总数
                total = len(all_results)
                
                # 分页
                start = (page - 1) * page_size
                end = start + page_size
                paginated_results = all_results[start:end]
                
                # 状态转换为中文
                status_map = {
                    'pass': '通过',
                    'fail': '失败',
                    'error': '错误',
                    'skip': '跳过',
                    'partial': '部分通过'
                }
                
                # 构建返回数据
                reports = []
                for result in paginated_results:
                    # 获取相关的测试套件
                    try:
                        test_suite = TestSuite.objects.get(suite_id=result['suite_id'])
                        environment_name = '未设置'
                        if test_suite.environment:
                            environment_name = test_suite.environment.env_name
                    except TestSuite.DoesNotExist:
                        continue
                    
                    # 格式化执行时间
                    execution_time = result['execution_time']
                    if execution_time:
                        if isinstance(execution_time, str):
                            execution_time = execution_time
                        else:
                            execution_time = execution_time.strftime('%Y-%m-%d %H:%M:%S')
                    
                    report = {
                        'id': str(result['result_id']),
                        'suiteId': str(result['suite_id']),
                        'suiteName': test_suite.name,
                        'executionTime': execution_time,
                        'duration': float(result['duration']) if result['duration'] is not None else 0,
                        'environment': environment_name,
                        'totalCases': result['total_cases'],
                        'passedCases': result['passed_cases'],
                        'failedCases': result['failed_cases'] + result['error_cases'],
                        'passRate': result['pass_rate'],
                        'result': status_map.get(result['status'], result['status'])
                    }
                    reports.append(report)
                
                return JsonResponse({
                    'code': 200,
                    'message': 'success',
                    'data': {
                        'total': total,
                        'reports': reports
                    }
                })
                
            except Exception as e:
                return JsonResponse({
                    'code': 500,
                    'message': f'获取测试报告列表失败: {str(e)}',
                    'data': None
                })
        
        # 获取单个测试套件的最新执行结果报告
        elif suite_id is not None:
            try:
                # 获取测试套件
                try:
                    test_suite = TestSuite.objects.get(suite_id=suite_id)
                except TestSuite.DoesNotExist:
                    return JsonResponse({
                        'code': 404,
                        'message': '测试套件不存在',
                        'data': None
                    })
                
                # 获取该测试套件的最新执行结果
                latest_result = TestSuiteResult.objects.filter(
                    suite=test_suite
                ).order_by('-execution_time').first()
                
                # 如果没有找到执行结果，返回404
                if not latest_result:
                    return JsonResponse({
                        'code': 404,
                        'message': '该测试套件尚未执行过测试',
                        'data': None
                    })
                
                try:
                    # 解析结果数据
                    result_data = json.loads(latest_result.result_data)
                    
                    # 状态转换为中文
                    status_map = {
                        'pass': '通过',
                        'fail': '失败',
                        'error': '错误',
                        'skip': '跳过',
                        'partial': '部分通过'
                    }
                    
                    result_status = status_map.get(latest_result.status, latest_result.status)
                    
                    # 转换用例结果格式
                    case_results = []
                    for case in result_data.get('results', []):
                        # 状态转换为中文
                        case_status = '通过' if case.get('status') == 'PASS' else '失败'
                        
                        # 添加格式化后的用例结果
                        case_results.append({
                            'id': str(case.get('case_id', '')),
                            'title': case.get('title', ''),
                            'api': case.get('api_path', ''),
                            'method': case.get('method', ''),
                            'duration': int(float(case.get('duration', 0)) * 1000),  # 转换为毫秒
                            'status': case_status,
                            'message': case.get('error', '执行成功') if case_status == '失败' else '验证成功',
                            'requestData': str(case.get('request', {})),
                            'responseData': str(case.get('response', {}))
                        })
                    
                    # 构建符合前端需求的响应数据
                    report_data = {
                        'id': str(latest_result.result_id),
                        'suiteId': str(test_suite.suite_id),
                        'suiteName': test_suite.name,
                        'executionTime': latest_result.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': latest_result.duration,
                        'environment': latest_result.environment.env_name if latest_result.environment else '未指定环境',
                        'totalCases': latest_result.total_cases,
                        'passedCases': latest_result.passed_cases,
                        'failedCases': latest_result.failed_cases + latest_result.error_cases,  # 合并失败和错误
                        'passRate': latest_result.pass_rate,
                        'result': result_status,
                        'caseResults': case_results
                    }
                    
                    return JsonResponse({
                        'code': 200,
                        'message': 'success',
                        'data': report_data
                    })
                    
                except json.JSONDecodeError:
                    # 如果结果数据解析失败，则使用数据库中的统计数据生成基本报告
                    report_data = {
                        'id': str(latest_result.result_id),
                        'suiteId': str(test_suite.suite_id),
                        'suiteName': test_suite.name,
                        'executionTime': latest_result.execution_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': latest_result.duration,
                        'environment': latest_result.environment.env_name if latest_result.environment else '未指定环境',
                        'totalCases': latest_result.total_cases,
                        'passedCases': latest_result.passed_cases,
                        'failedCases': latest_result.failed_cases + latest_result.error_cases,
                        'passRate': latest_result.pass_rate,
                        'result': status_map.get(latest_result.status, latest_result.status),
                        'caseResults': [],
                        'error': '结果数据解析失败'
                    }
                    
                    return JsonResponse({
                        'code': 200,
                        'message': '结果数据部分加载',
                        'data': report_data
                    })
                
            except Exception as e:
                return JsonResponse({
                    'code': 500,
                    'message': f'获取测试报告失败: {str(e)}',
                    'data': None
                })
        
        # 如果没有提供suite_id和project_id，返回错误
        else:
            return JsonResponse({
                'code': 400,
                'message': '缺少必要的参数',
                'data': None
            })

    def delete(self, request, result_id=None):
        """删除指定ID的测试报告"""
        if not result_id:
            return JsonResponse({
                'code': 400,
                'message': '缺少报告ID',
                'data': None
            })
            
        try:
            # 查找报告
            try:
                report = TestSuiteResult.objects.get(result_id=result_id)
            except TestSuiteResult.DoesNotExist:
                return JsonResponse({
                    'code': 404,
                    'message': '测试报告不存在',
                    'data': None
                })
                
            # 获取相关信息用于返回
            suite_id = report.suite_id
            execution_time = report.execution_time.strftime('%Y-%m-%d %H:%M:%S')
                
            # 删除报告
            report.delete()
                
            return JsonResponse({
                'code': 200,
                'message': '测试报告删除成功',
                'data': {
                    'id': result_id,
                    'suiteId': suite_id,
                    'executionTime': execution_time
                }
            })
                
        except Exception as e:
            return JsonResponse({
                'code': 500,
                'message': f'删除测试报告失败: {str(e)}',
                'data': None
            }) 