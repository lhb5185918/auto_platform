from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from rest_framework.permissions import AllowAny


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    
    def post(self, request):
        try:
            print("==== Login Debug Info ====")
            print("Request Method:", request.method)
            print("Request Headers:", request.headers)
            print("Request Data:", request.data)
            print("========================")
            
            username = request.data.get('username')
            password = request.data.get('password')
            
            # 添加调试信息
            print("Login attempt for username:", username)
            
            if not username or not password:
                return Response({
                    "code": 400,
                    "message": "用户名和密码不能为空",
                    "data": None
                })

            user = authenticate(username=username, password=password)
            
            if user is not None:
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                
                # 添加调试信息
                print("Login successful for user:", username)
                print("Generated token:", access_token)
                
                return Response({
                    "code": 200,
                    "message": "登录成功",
                    "data": {
                        "token": access_token,
                        "refresh": str(refresh),
                        "user": {
                            "id": user.id,
                            "username": user.username,
                            "avatar": user.profile.avatar if hasattr(user, 'profile') else "",
                            "email": user.email
                        },
                        "redirect_url": "/"
                    }
                })
            else:
                return Response({
                    "code": 401,
                    "message": "用户名或密码错误",
                    "data": None
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            print("Login error:", str(e))
            return Response({
                "code": 500,
                "message": f"登录失败：{str(e)}",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    
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
