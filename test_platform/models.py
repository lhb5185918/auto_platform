from django.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    project_id = models.AutoField(primary_key=True, verbose_name='项目ID')
    name = models.CharField(max_length=255, verbose_name='项目名称')
    description = models.TextField(verbose_name='项目描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    is_active = models.IntegerField(default=0, verbose_name='状态是否活跃')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='projects', verbose_name='用户')

    def __str__(self):
        return self.name


class TestCase(models.Model):
    test_case_id = models.AutoField(primary_key=True, verbose_name='用例ID', db_comment='测试用例的唯一标识')
    case_name = models.CharField(max_length=255, verbose_name='用例名称', db_comment='测试用例的名称')
    case_description = models.TextField(verbose_name='用例描述', db_comment='对测试用例的详细描述')
    case_path = models.CharField(max_length=255, verbose_name='用例路径', db_comment='测试用例的文件路径')
    case_request_method = models.CharField(max_length=255, verbose_name='请求方法', db_comment='HTTP请求方法')
    case_priority = models.IntegerField(default=0, verbose_name='用例优先级', choices=[
        (0, '低'),
        (1, '中'),
        (2, '高'),
    ], db_comment='测试用例的优先级')
    case_status = models.IntegerField(default=0, verbose_name='用例执行状态', choices=[
        (0, '未执行'),
        (1, '已执行'),
    ], db_comment='测试用例的执行状态')
    case_precondition = models.TextField(verbose_name='前置条件', db_comment='执行测试用例前的条件')
    case_request_headers = models.TextField(verbose_name='请求头', db_comment='HTTP请求头信息')
    case_requests_body = models.TextField(verbose_name='请求体', db_comment='HTTP请求体内容')
    case_expect_result = models.TextField(verbose_name='期望结果', db_comment='测试用例的预期结果')
    case_assert_type = models.CharField(max_length=50, verbose_name='断言类型', null=True, blank=True,
                                        db_comment='断言的类型')
    case_assert_contents = models.TextField(verbose_name='断言内容', db_comment='断言的具体内容')
    creat_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间', db_comment='测试用例的创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间', db_comment='测试用例的最后更新时间')
    last_executed_at = models.DateTimeField(verbose_name='最近执行时间', null=True, blank=True,
                                            db_comment='最后一次执行测试用例的时间')
    last_execution_result = models.CharField(max_length=20, verbose_name='最近执行结果', choices=[
        ('passed', '通过'),
        ('failed', '失败'),
        ('blocked', '阻塞'),
        ('not_run', '未执行')
    ], default='not_run', db_comment='最近一次执行的结果')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='test_cases',
                                verbose_name='创建者', db_comment='创建该测试用例的用户')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_cases', verbose_name='项目',
                                db_comment='关联的项目')


def __str__(self):
    return self.case_name
