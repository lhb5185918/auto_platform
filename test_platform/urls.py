from django.urls import path
from test_platform.views.login_views import LoginView, RegisterView
from test_platform.views.project_view import ProjectView, get_project_list, ProjectEditView, ProjectDeleteView
from test_platform.views.test_case_view import TestCaseView, TestEnvironmentView, TestCaseImportView, \
    TestEnvironmentCoverView
from test_platform.views import execute

urlpatterns = [
    # 登录相关路由
    path('api/login/', LoginView.as_view(), name='login'),
    path('api/register/', RegisterView.as_view(), name='register'),

    # 项目相关路由
    path('api/project/', get_project_list, name='project_list'),
    path('api/project/create/', ProjectView.as_view(), name='create_project'),
    path('api/project/edit/', ProjectEditView.as_view(), name='edit_project'),
    path('api/project/delete/', ProjectDeleteView.as_view(), name='delete_project'),

    # 测试用例相关路由
    path('api/testcase/list/<int:project_id>', TestCaseView.as_view(), name='testcase_list'),
    path('api/testcase/create/', TestCaseView.as_view(), name='testcase_create'),
    path('api/testcase/update/<int:case_id>/', TestCaseView.as_view(), name='testcase_update'),
    path('api/env/create', TestEnvironmentView.as_view(), name='env_create'),
    path('api/env/list/<int:project_id>', TestEnvironmentView.as_view(), name='env_list'),

    path('api/env/variable/<int:env_id>', TestEnvironmentView.as_view(), name='env_edit'),
    path('api/testcase/import/', TestCaseImportView.as_view(), name='testcase_import'),
    path('api/env-suite/create', TestEnvironmentCoverView.as_view(), name='environment_cover_create'),
    path('api/env-suite/list/<int:project_id>', TestEnvironmentCoverView.as_view(), name='environment_cover_list'),

    path('api/execute_test/', execute.execute_test, name='execute_test'),

    # 测试用例执行相关路由
    path('api/testcase/execute/<int:case_id>', execute.execute_test, name='execute_test'),
    path('api/testcase/execute_direct/', execute.execute_test_direct, name='execute_test_direct'),

]


