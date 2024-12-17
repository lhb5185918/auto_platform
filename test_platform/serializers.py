from rest_framework import serializers
from .models import TestCase


class TestCaseSerializer(serializers.ModelSerializer):
    project_id = serializers.IntegerField(required=True)

    class Meta:
        model = TestCase
        fields = [
            'project_id',
            'case_name',
            'case_path',
            'case_request_method',
            'case_priority',
            'case_status',
            'case_request_headers',
            'case_params',
            'case_requests_body',
            'case_assert_contents',
            'case_description',
            'case_expect_result'
        ]
        extra_kwargs = {
            'project_id': {'required': True}
        }

    def to_internal_value(self, data):
        """数据转换前的处理"""
        print("转换前的数据:", data)
        ret = super().to_internal_value(data)
        print("转换后的数据:", ret)
        return ret

    def validate(self, attrs):
        """整体验证"""
        print("验证前的数据:", attrs)

        # 验证 project_id
        if 'project_id' not in attrs:
            raise serializers.ValidationError({"project_id": "This field is required."})

        # 验证标题长度
        if len(attrs.get('case_name', '')) > 100:
            raise serializers.ValidationError({"case_name": "标题长度不能超过100个字符"})

        # 验证接口路径格式
        if not attrs.get('case_path', '').startswith('/'):
            attrs['case_path'] = '/' + attrs['case_path']

        # 设置默认状态
        if 'case_status' not in attrs:
            attrs['case_status'] = '0'

        print("验证后的数据:", attrs)
        return attrs

    def validate_case_request_method(self, value):
        """验证请求方法"""
        valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        if value.upper() not in valid_methods:
            raise serializers.ValidationError(f"无效的请求方法。支持的方法: {', '.join(valid_methods)}")
        return value.upper()

    def validate_case_priority(self, value):
        """验证优先级"""
        print("序列化器接收到的优先级值:", value)

        priority_map = {
            '高': '1',
            '中': '2',
            '低': '0',
            '0': '0',
            '1': '1',
            '2': '2'
        }

        if value in ['0', '1', '2']:
            return value

        normalized_value = priority_map.get(str(value).strip())
        if normalized_value is not None:
            return normalized_value

        raise serializers.ValidationError(f"无效的优先级。支持的优先级: 0(高), 1(中), 2(低)")

    def validate_case_request_headers(self, value):
        """验证请求头格式"""
        if value and isinstance(value, str):
            try:
                import json
                json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("请求头必须是有效的JSON格式")
        return value or '{}'

    def validate_case_params(self, value):
        """验证请求参数格式"""
        if value and isinstance(value, str):
            try:
                import json
                json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("请求参数必须是有效的JSON格式")
        return value or '{}'

    def validate_case_requests_body(self, value):
        """验证请求体格式"""
        if value and isinstance(value, str):
            try:
                import json
                json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError("请求体必须是有效的JSON格式")
        return value or '{}'

    def create(self, validated_data):
        """创建实例"""
        print("创建前的数据:", validated_data)

        if 'project_id' not in validated_data:
            raise serializers.ValidationError({"project_id": "This field is required."})

        instance = super().create(validated_data)
        print("创建后的实例:", instance.__dict__)
        return instance
