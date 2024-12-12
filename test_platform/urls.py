from django.urls import path
from test_platform.views.login_views import LoginView, RegisterView
from test_platform.views.project_view import ProjectView, get_project_list

urlpatterns = [
    # 登录相关路由
    path('api/login/', LoginView.as_view(), name='login'),
    path('api/register/', RegisterView.as_view(), name='register'),
    
    # 项目相关路由
    path('api/project/', get_project_list, name='project_list'),
    path('api/project/create/', ProjectView.as_view(), name='create_project'),
]
