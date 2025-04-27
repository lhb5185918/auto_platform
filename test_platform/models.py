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
    case_params = models.TextField(verbose_name='请求参数', db_comment='HTTP请求参数')
    case_precondition = models.TextField(verbose_name='前置条件', db_comment='执行测试用例前的条件')
    case_request_headers = models.TextField(verbose_name='请求头', db_comment='HTTP请求头信息')
    case_requests_body = models.TextField(verbose_name='请求体', db_comment='HTTP请求体内容')
    case_expect_result = models.TextField(verbose_name='期望结果', db_comment='测试用例的预期结果')
    case_assert_type = models.CharField(max_length=50, verbose_name='断言类型', null=True, blank=True,
                                        db_comment='断言的类型')
    case_assert_contents = models.TextField(verbose_name='断言内容', db_comment='断言的具体内容')
    case_extractors = models.TextField(verbose_name='提取器', null=True, blank=True, db_comment='测试结果提取器配置')
    case_tests = models.TextField(verbose_name='测试断言', null=True, blank=True, db_comment='测试断言配置')
    last_assertion_results = models.TextField(verbose_name='最后断言结果', null=True, blank=True, db_comment='最后一次执行的断言结果')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间', db_comment='测试用例的创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间', db_comment='测试用例的最后更新时间')
    last_executed_at = models.DateTimeField(null=True, blank=True, verbose_name='最后执行时间')
    last_execution_result = models.CharField(max_length=20, default='not_run', verbose_name='最后执行结果')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='test_cases',
                                verbose_name='创建者', db_comment='创建该测试用例的用户')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_cases', verbose_name='项目',
                                db_comment='关联的项目')

    def __str__(self):
        return self.case_name


class TestEnvironment(models.Model):
    environment_id = models.AutoField(primary_key=True, verbose_name='环境ID')
    host = models.CharField(max_length=255, verbose_name='主机地址')
    port = models.IntegerField(verbose_name='端口号')
    base_url = models.CharField(max_length=255, verbose_name='基础URL')
    protocol = models.CharField(max_length=50, verbose_name='协议')
    token = models.CharField(max_length=255, verbose_name='令牌值')
    db_host = models.CharField(max_length=255, verbose_name='主机地址')
    db_port = models.IntegerField(verbose_name='端口号')
    db_name = models.CharField(max_length=255, verbose_name='数据库名称')
    db_user = models.CharField(max_length=50, verbose_name='用户名')
    db_password = models.CharField(max_length=50, verbose_name='密码')
    time_out = models.IntegerField(verbose_name='超时时间')
    description = models.TextField(verbose_name='环境描述')
    content_type = models.CharField(max_length=50, verbose_name='内容类型')
    charset = models.CharField(max_length=50, verbose_name='字符集')
    env_name = models.CharField(max_length=50, verbose_name='环境名称')
    version = models.CharField(max_length=50, verbose_name='版本号')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='environments', verbose_name='项目',
                                db_comment='关联的项目')
    environment_cover = models.ForeignKey('TestEnvironmentCover', on_delete=models.CASCADE, null=True, blank=True,
                                          related_name='environments', verbose_name='环境套')

    def __str__(self):
        return self.env_name



class TestEnvironmentCover(models.Model):
    environment_cover_id = models.AutoField(primary_key=True, verbose_name='环境套id')
    environment_name = models.CharField(max_length=255, verbose_name='环境名称')
    environment_description = models.TextField(verbose_name='环境描述')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='environment_covers',
                                verbose_name='项目')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    creat_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='environment_covers',
                                   verbose_name='创建者')


class TestResult(models.Model):
    test_result_id = models.AutoField(primary_key=True, verbose_name='结果ID')
    case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name='results', verbose_name='测试用例')
    execution_time = models.DateTimeField(verbose_name='执行时间')
    status = models.CharField(max_length=20, verbose_name='执行状态', choices=[
        ('PASS', '通过'),
        ('FAIL', '失败'),
        ('ERROR', '错误'),
        ('SKIP', '跳过')
    ])
    result_data = models.TextField(verbose_name='结果数据')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    error_message = models.TextField(verbose_name='错误信息', null=True, blank=True)
    duration = models.FloatField(verbose_name='执行时长', help_text='单位：秒', default=0)
    environment = models.ForeignKey(TestEnvironment, on_delete=models.SET_NULL, null=True,
                                    related_name='test_results', verbose_name='执行环境')

    def __str__(self):
        return f"{self.case.case_name} - {self.execution_time}"


class TestSuite(models.Model):
    """测试套件模型"""
    suite_id = models.AutoField(primary_key=True, verbose_name='套件ID')
    name = models.CharField(max_length=255, verbose_name='套件名称')
    description = models.TextField(verbose_name='套件描述', null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_suites', verbose_name='所属项目')
    environment = models.ForeignKey(TestEnvironment, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='test_suites', verbose_name='执行环境')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='test_suites',
                                verbose_name='创建者')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    last_executed_at = models.DateTimeField(null=True, blank=True, verbose_name='最后执行时间')
    last_execution_status = models.CharField(max_length=20, default='not_run', verbose_name='最后执行状态')

    def __str__(self):
        return self.name


class TestSuiteCase(models.Model):
    """测试套件-测试用例关联模型"""
    id = models.AutoField(primary_key=True)
    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='suite_cases', verbose_name='测试套件')
    # 用于存储原始测试用例的ID
    original_case_id = models.IntegerField(verbose_name='原始用例ID')
    # 测试用例的克隆/自定义数据
    case_data = models.TextField(verbose_name='用例数据', help_text='JSON格式的测试用例数据')
    order = models.IntegerField(default=0, verbose_name='执行顺序')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        ordering = ['order']
        unique_together = ['suite', 'original_case_id']

    def __str__(self):
        return f"{self.suite.name} - 用例ID:{self.original_case_id} (顺序:{self.order})"


class TestSuiteResult(models.Model):
    """测试套件执行结果模型"""
    result_id = models.AutoField(primary_key=True, verbose_name='结果ID')
    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='execution_results', verbose_name='测试套件')
    execution_time = models.DateTimeField(verbose_name='执行时间')
    status = models.CharField(max_length=20, verbose_name='执行状态', choices=[
        ('pass', '通过'),
        ('fail', '失败'),
        ('error', '错误'),
        ('skip', '跳过'),
        ('partial', '部分通过')
    ])
    duration = models.FloatField(verbose_name='执行时长', help_text='单位：秒', default=0)
    total_cases = models.IntegerField(verbose_name='用例总数', default=0)
    passed_cases = models.IntegerField(verbose_name='通过用例数', default=0)
    failed_cases = models.IntegerField(verbose_name='失败用例数', default=0)
    error_cases = models.IntegerField(verbose_name='错误用例数', default=0)
    skipped_cases = models.IntegerField(verbose_name='跳过用例数', default=0)
    pass_rate = models.FloatField(verbose_name='通过率', default=0)
    result_data = models.TextField(verbose_name='结果数据', help_text='JSON格式的详细结果数据')
    environment = models.ForeignKey(TestEnvironment, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='suite_results', verbose_name='执行环境')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='suite_results',
                               verbose_name='执行者')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    def __str__(self):
        return f"{self.suite.name} - {self.execution_time}"
