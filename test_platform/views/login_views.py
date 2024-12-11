from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User


class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)
            return Response({
                "code": 200,
                "message": "登录成功",
                "data": {
                    "token": str(refresh.access_token),
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "avatar": user.profile.avatar if hasattr(user, 'profile') else "",  # 假设用户有一个profile模型
                        "email": user.email
                    },
                    "redirect_url": "/"  # 登录成功后的跳转地址
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                "code": 401,
                "message": "用户名或密码错误",
                "data": None
            }, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email')
        user_res = User.objects.filter(username=username)
        if user_res:
            return Response({
                "code": 400,
                "message": "用户名已存在",
                "data": None
            })
        User.objects.create_user(username=username, password=password, email=email)
        user = authenticate(request, username=username, password=password)
        refresh = RefreshToken.for_user(user)
        return Response({
            "code": 200,
            "message": "注册成功",
            "data": {
                "token": str(refresh.access_token),
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "avatar": None
                },
                "redirect_url": "login/"
            }
        }
        )
