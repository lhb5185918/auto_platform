from django.urls import path
from test_platform.views.login_views import LoginView, RegisterView, UserInfoView
from test_platform.views.project_view import ProjectView, get_project_list, ProjectEditView, ProjectDeleteView
from test_platform.views.test_case_view import TestCaseView, TestEnvironmentView, TestCaseImportView, \
    TestEnvironmentCoverView, TestSuiteView, EnvironmentSwitchView
from test_platform.views import execute
from test_platform.views.report_view import TestReportView
from test_platform.views.statistics_view import TestTrendView
from test_platform.views.log_view import ExecutionLogView
from test_platform.views.test_plan_view import TestPlanView
from test_platform.views.rag_view import (
    RAGBaseView, list_external_datasets, create_api_key_config, 
    list_workspaces, upload_knowledge_document,
    get_upload_progress, list_knowledge_documents, upload_file
)
from test_platform.views.agent_view import file_parse, save_deepseek_config, get_deepseek_config, create_test_case, export_test_cases
from django.http import JsonResponse

urlpatterns = [
    # 登录相关路由
    path('api/login/', LoginView.as_view(), name='login'),
    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/user/info/', UserInfoView.as_view(), name='user_info'),

    # 项目相关路由
    path('api/project/', get_project_list, name='project_list'),
    path('api/project/create/', ProjectView.as_view(), name='create_project'),
    path('api/project/edit/', ProjectEditView.as_view(), name='edit_project'),
    path('api/project/delete/', ProjectDeleteView.as_view(), name='delete_project'),

    # 测试用例相关路由
    path('api/testcase/list/<int:project_id>', TestCaseView.as_view(), name='testcase_list'),
    path('api/testcase/create/', TestCaseView.as_view(), name='testcase_create'),
    path('api/testcase/update/<int:case_id>/', TestCaseView.as_view(), name='testcase_update'),
    path('api/testcase/status/<int:case_id>', TestCaseView.as_view(), name='testcase_status_update'),
    path('api/env/create', TestEnvironmentView.as_view(), name='env_create'),
    path('api/env/list/<int:project_id>', TestEnvironmentView.as_view(), name='env_list'),

    path('api/env/variable/<int:env_id>', TestEnvironmentView.as_view(), name='env_edit'),
    path('api/testcase/import/', TestCaseImportView.as_view(), name='testcase_import'),
    path('api/env-suite/create', TestEnvironmentCoverView.as_view(), name='environment_cover_create'),
    path('api/env-suite/list/<int:project_id>', TestEnvironmentCoverView.as_view(), name='environment_cover_list'),
    path('api/env-suite/delete/<int:env_cover_id>', TestEnvironmentCoverView.as_view(), name='environment_cover_delete'),
    
    # 环境套切换路由
    path('api/environment/current/', EnvironmentSwitchView.as_view(), name='environment_switch'),

    path('api/execute_test/', execute.execute_test, name='execute_test'),

    # 测试用例执行相关路由
    path('api/testcase/execute/<int:case_id>', execute.execute_test, name='execute_test'),
    path('api/testcase/execute_direct/', execute.execute_test_direct, name='execute_test_direct'),
    
    # 测试用例更新相关路由
    path('api/testcase/update/<int:case_id>', execute.update_suite_case, name='update_suite_case'),

    # 测试套件相关路由
    path('api/suite/create', TestSuiteView.as_view(), name='suite_create'),
    path('api/suite/list/<int:project_id>', TestSuiteView.as_view(), name='suite_list'),
    path('api/suite/<int:suite_id>', TestSuiteView.as_view(), name='suite_detail'),
    path('api/suite/update/<int:suite_id>', TestSuiteView.as_view(), name='suite_update'),
    path('api/suite/delete/<int:suite_id>', TestSuiteView.as_view(), name='suite_delete'),
    path('api/suite', TestSuiteView.as_view(), name='suite_list_all'),
    path('api/suite/execute/<int:suite_id>', TestSuiteView.as_view(), name='suite_execute'),
    path('api/suite/detail/<int:suite_id>', execute.get_suite_detail, name='suite_detail_view'),
    
    # 测试报告相关路由
    path('api/report/latest/<int:suite_id>', TestReportView.as_view(), name='report_latest'),
    path('api/report/list/<int:project_id>', TestReportView.as_view(), name='report_list'),
    path('api/report/detail/<int:result_id>', TestReportView.as_view(), name='report_detail'),
    path('api/report/delete/<int:result_id>', TestReportView.as_view(), name='report_delete'),
    path('api/report/response/<int:result_id>', execute.get_suite_result_response, name='suite_result_response'),
    
    # 统计相关路由
    path('api/statistics/trend', TestTrendView.as_view(), name='statistics_trend'),
    
    # 执行日志相关路由
    path('api/log', ExecutionLogView.as_view(), name='execution_log_list'),
    path('api/log/<int:result_id>', ExecutionLogView.as_view(), name='execution_log_detail'),
    
    # 测试计划相关路由
    path('api/test-plan/', TestPlanView.as_view(), name='test_plan_create'),
    path('api/test-plan/list/<int:project_id>', TestPlanView.as_view(), name='test_plan_list'),
    path('api/test-plan/<int:plan_id>', TestPlanView.as_view(), name='test_plan_detail'),
    path('api/test-plan/update/<int:plan_id>', TestPlanView.as_view(), name='test_plan_update'),
    path('api/test-plan/delete/<int:plan_id>', TestPlanView.as_view(), name='test_plan_delete'),
    path('api/test-plan/execute/<int:plan_id>', lambda request, plan_id: TestPlanView().execute_plan(request, plan_id), name='test_plan_execute'),
    path('api/test-plan/<int:plan_id>/executions', lambda request, plan_id: TestPlanView().get_plan_executions(request, plan_id), name='test_plan_executions'),

    # RAG知识库相关路由
    path('api/rag/', RAGBaseView.as_view(), name='rag_create'),
    path('api/rag/list/<int:project_id>', lambda request, project_id: RAGBaseView().get(request, project_id=project_id), name='rag_list'),
    path('api/rag/<int:rag_id>', RAGBaseView.as_view(), name='rag_detail'),
    path('api/rag/update_key/<int:rag_id>', lambda request, rag_id: RAGBaseView().patch(request, rag_id) if request.method == 'PATCH' else RAGBaseView().get(request, rag_id), name='rag_update_key'),
    path('api/rag/external-datasets', list_external_datasets, name='list_external_datasets'),
    path('api/rag/config', create_api_key_config, name='create_api_key_config'),
    path('api/rag/workspaces', list_workspaces, name='list_workspaces'),
    path('api/rag/upload', upload_knowledge_document, name='upload_knowledge_document'),
    path('api/rag/progress', get_upload_progress, name='get_upload_progress'),
    path('api/rag/documents', list_knowledge_documents, name='list_knowledge_documents'),
    path('api/rag/file/upload', upload_file, name='upload_file'),
    
    # 文件解析相关路由
    path('api/agent/file/parse', file_parse, name='file_parse'),
    
    # 测试用例创建路由
    path('api/agent/create-test-case', create_test_case, name='create_test_case'),
    
    # 测试用例导出路由
    path('api/agent/export-test-case', export_test_cases, name='export_test_cases'),
    
    # DeepSeek API配置相关路由
    path('api/config/deepseek', save_deepseek_config, name='deepseek_config'),
]


