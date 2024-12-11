from django.urls import path
from test_platform.views import login_views, project_view

urlpatterns = [
    path('api/login/', login_views.LoginView.as_view(), name='login'),
    path('api/register/', login_views.RegisterView.as_view(), name='register'),
    path('api/project/', project_view.get_project_list, name='get_project_list'),
    path('api/project/create/', project_view.creat_project, name='creat_project')
]
