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
    environment_cover = models.ForeignKey(TestEnvironmentCover, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='test_suites', verbose_name='执行环境套')
    environment = models.ForeignKey(TestEnvironment, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='test_suites_env', verbose_name='执行环境')
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


class TestExecutionLog(models.Model):
    """测试执行日志模型，记录详细的执行过程"""
    log_id = models.AutoField(primary_key=True, verbose_name='日志ID')
    # 可以关联到测试用例、测试套件或单独执行
    case = models.ForeignKey(TestCase, on_delete=models.SET_NULL, null=True, blank=True, 
                             related_name='execution_logs', verbose_name='测试用例')
    suite = models.ForeignKey(TestSuite, on_delete=models.SET_NULL, null=True, blank=True, 
                              related_name='execution_logs', verbose_name='测试套件')
    # 只保留与测试套件结果的关联
    suite_result = models.ForeignKey(TestSuiteResult, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='execution_logs', verbose_name='套件执行结果')
    # 执行基本信息
    execution_time = models.DateTimeField(auto_now_add=True, verbose_name='执行时间')
    status = models.CharField(max_length=20, verbose_name='执行状态', 
                             choices=[('pass', '通过'), ('fail', '失败'), 
                                     ('error', '错误'), ('skip', '跳过')])
    duration = models.FloatField(verbose_name='执行时长(秒)', default=0)
    executor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                related_name='execution_logs', verbose_name='执行人')
    
    # 请求详情
    request_url = models.TextField(verbose_name='请求URL', null=True, blank=True)
    request_method = models.CharField(max_length=20, verbose_name='请求方法', null=True, blank=True)
    request_headers = models.TextField(verbose_name='请求头', null=True, blank=True)
    request_body = models.TextField(verbose_name='请求体', null=True, blank=True)
    
    # 响应详情
    response_status_code = models.IntegerField(verbose_name='响应状态码', null=True, blank=True)
    response_headers = models.TextField(verbose_name='响应头', null=True, blank=True)
    response_body = models.TextField(verbose_name='响应体', null=True, blank=True)
    
    # 日志详情
    log_detail = models.TextField(verbose_name='详细日志', null=True, blank=True)
    error_message = models.TextField(verbose_name='错误信息', null=True, blank=True)
    
    # 提取的变量
    extracted_variables = models.TextField(verbose_name='提取的变量', null=True, blank=True)
    
    # 断言结果
    assertion_results = models.TextField(verbose_name='断言结果', null=True, blank=True)
    
    # 环境信息
    environment = models.ForeignKey(TestEnvironment, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='execution_logs', verbose_name='执行环境')
    environment_cover = models.ForeignKey(TestEnvironmentCover, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='execution_logs', verbose_name='环境套')
    
    class Meta:
        verbose_name = '执行日志'
        verbose_name_plural = '执行日志'
        ordering = ['-execution_time']  # 按执行时间倒序排列
    
    def __str__(self):
        case_name = self.case.case_name if self.case else (self.suite.name if self.suite else '未知用例')
        return f"{case_name} - {self.execution_time} - {self.status}"


class TestPlan(models.Model):
    """测试计划模型"""
    plan_id = models.AutoField(primary_key=True, verbose_name='计划ID')
    name = models.CharField(max_length=255, verbose_name='计划名称')
    description = models.TextField(verbose_name='计划描述', null=True, blank=True)
    
    # 计划调度设置
    SCHEDULE_TYPES = [
        ('once', '一次性'),
        ('daily', '每天'),
        ('weekly', '每周'),
        ('cron', '定时任务')
    ]
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES, default='once', verbose_name='调度类型')
    execute_time = models.DateTimeField(null=True, blank=True, verbose_name='执行时间')
    cron_expression = models.CharField(max_length=100, null=True, blank=True, verbose_name='Cron表达式')
    
    # 重试设置
    retry_times = models.IntegerField(default=0, verbose_name='重试次数')
    
    # 通知设置
    NOTIFY_TYPES = [
        ('email', '邮件'),
        ('dingtalk', '钉钉'),
        ('wechat', '微信'),
        ('sms', '短信')
    ]
    notify_types = models.CharField(max_length=255, null=True, blank=True, verbose_name='通知类型')
    
    # 执行状态
    status = models.CharField(max_length=20, default='pending', verbose_name='执行状态',
                             choices=[
                                 ('pending', '待执行'),
                                 ('running', '执行中'),
                                 ('completed', '已完成'),
                                 ('failed', '失败'),
                                 ('cancelled', '已取消')
                             ])
    
    # 关联关系
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='test_plans', verbose_name='所属项目')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='test_plans', verbose_name='创建者')
    
    # 时间戳
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    last_executed_at = models.DateTimeField(null=True, blank=True, verbose_name='最后执行时间')
    
    class Meta:
        verbose_name = '测试计划'
        verbose_name_plural = '测试计划'
        ordering = ['-create_time']
        
    def __str__(self):
        return self.name


class TestPlanSuite(models.Model):
    """测试计划-测试套件关联模型"""
    id = models.AutoField(primary_key=True)
    plan = models.ForeignKey(TestPlan, on_delete=models.CASCADE, related_name='plan_suites', verbose_name='测试计划')
    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='plan_suites', verbose_name='测试套件')
    order = models.IntegerField(default=0, verbose_name='执行顺序')
    
    # 关联环境
    environment = models.ForeignKey(TestEnvironment, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='plan_suites', verbose_name='执行环境')
    environment_cover = models.ForeignKey(TestEnvironmentCover, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='plan_suites', verbose_name='环境套')
    
    # 时间戳
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        ordering = ['order']
        unique_together = ['plan', 'suite']
        
    def __str__(self):
        return f"{self.plan.name} - {self.suite.name}"


class TestPlanResult(models.Model):
    """测试计划执行结果模型"""
    result_id = models.AutoField(primary_key=True, verbose_name='结果ID')
    plan = models.ForeignKey(TestPlan, on_delete=models.CASCADE, related_name='execution_results', verbose_name='测试计划')
    execution_time = models.DateTimeField(verbose_name='执行时间')
    status = models.CharField(max_length=20, verbose_name='执行状态',
                             choices=[
                                 ('pass', '通过'),
                                 ('fail', '失败'),
                                 ('error', '错误'),
                                 ('partial', '部分通过'),
                                 ('cancelled', '已取消')
                             ])
    
    # 执行结果统计
    duration = models.FloatField(verbose_name='执行时长', help_text='单位：秒', default=0)
    total_suites = models.IntegerField(verbose_name='套件总数', default=0)
    passed_suites = models.IntegerField(verbose_name='通过套件数', default=0)
    failed_suites = models.IntegerField(verbose_name='失败套件数', default=0)
    error_suites = models.IntegerField(verbose_name='错误套件数', default=0)
    
    # 测试用例统计
    total_cases = models.IntegerField(verbose_name='用例总数', default=0)
    passed_cases = models.IntegerField(verbose_name='通过用例数', default=0)
    failed_cases = models.IntegerField(verbose_name='失败用例数', default=0)
    error_cases = models.IntegerField(verbose_name='错误用例数', default=0)
    skipped_cases = models.IntegerField(verbose_name='跳过用例数', default=0)
    
    # 通过率
    pass_rate = models.FloatField(verbose_name='通过率', default=0)
    
    # 结果数据
    result_data = models.TextField(verbose_name='结果数据', help_text='JSON格式的详细结果数据')
    error_message = models.TextField(verbose_name='错误信息', null=True, blank=True)
    
    # 关联用户
    executor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='plan_results', verbose_name='执行者')
    
    # 时间戳
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '测试计划结果'
        verbose_name_plural = '测试计划结果'
        ordering = ['-execution_time']
        
    def __str__(self):
        return f"{self.plan.name} - {self.execution_time}"


class RAGKnowledgeBase(models.Model):
    """RAG知识库模型"""
    rag_id = models.AutoField(primary_key=True, verbose_name='知识库ID')
    name = models.CharField(max_length=100, verbose_name='知识库名称')
    space_id = models.CharField(max_length=100, verbose_name='空间ID')
    
    # 知识库类型选项
    FORMAT_TYPES = [
        (0, '文本'),
        (2, '图片'),
    ]
    format_type = models.IntegerField(choices=FORMAT_TYPES, default=0, verbose_name='知识库类型')
    
    # 知识库描述和图标
    description = models.TextField(null=True, blank=True, verbose_name='知识库描述')
    file_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='图标文件ID')
    
    # API配置信息
    api_key = models.CharField(max_length=500, verbose_name='API密钥', help_text='用于访问第三方RAG服务的密钥')
    api_base = models.CharField(max_length=200, default='https://api.coze.cn', verbose_name='API基础URL')
    
    # 状态信息
    STATUS_CHOICES = [
        ('creating', '创建中'),
        ('active', '正常'),
        ('error', '错误'),
        ('deleted', '已删除'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='creating', verbose_name='状态')
    error_message = models.TextField(null=True, blank=True, verbose_name='错误信息')
    
    # 外部系统返回的知识库ID
    external_dataset_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='外部知识库ID')
    
    # 关联关系
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='rag_knowledge_bases', verbose_name='所属项目')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rag_knowledge_bases', verbose_name='创建者')
    
    # 时间戳
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'RAG知识库'
        verbose_name_plural = 'RAG知识库'
        ordering = ['-create_time']
    
    def __str__(self):
        return self.name


class RAGFile(models.Model):
    """RAG知识库文件模型"""
    file_id = models.AutoField(primary_key=True, verbose_name='文件ID')
    
    # 文件信息
    file_name = models.CharField(max_length=255, verbose_name='文件名称')
    file_size = models.IntegerField(default=0, verbose_name='文件大小(字节)')
    file_type = models.CharField(max_length=50, verbose_name='文件类型')
    file_url = models.TextField(verbose_name='文件URL')
    
    # 外部系统返回的文件ID
    external_file_id = models.CharField(max_length=100, null=True, blank=True, verbose_name='外部文件ID')
    
    # 处理状态
    STATUS_CHOICES = [
        ('uploading', '上传中'),
        ('processing', '处理中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('deleted', '已删除'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading', verbose_name='状态')
    error_message = models.TextField(null=True, blank=True, verbose_name='错误信息')
    
    # 关联关系
    knowledge_base = models.ForeignKey(RAGKnowledgeBase, on_delete=models.CASCADE, related_name='files', verbose_name='所属知识库')
    uploader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rag_files', verbose_name='上传者')
    
    # 时间戳
    upload_time = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = 'RAG文件'
        verbose_name_plural = 'RAG文件'
        ordering = ['-upload_time']
    
    def __str__(self):
        return self.file_name


class RAGQuery(models.Model):
    """RAG查询记录模型"""
    query_id = models.AutoField(primary_key=True, verbose_name='查询ID')
    
    # 查询信息
    query_text = models.TextField(verbose_name='查询文本')
    response_text = models.TextField(verbose_name='响应文本')
    
    # 查询参数
    temperature = models.FloatField(default=0.7, verbose_name='温度参数')
    max_tokens = models.IntegerField(default=2048, verbose_name='最大令牌数')
    
    # 查询统计
    token_count = models.IntegerField(default=0, verbose_name='令牌数量')
    response_time = models.FloatField(default=0, verbose_name='响应时间(秒)')
    
    # 引用的文件
    referenced_files = models.TextField(null=True, blank=True, verbose_name='引用的文件')
    
    # 关联关系
    knowledge_base = models.ForeignKey(RAGKnowledgeBase, on_delete=models.CASCADE, related_name='queries', verbose_name='知识库')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='rag_queries', verbose_name='查询用户')
    
    # 时间戳
    query_time = models.DateTimeField(auto_now_add=True, verbose_name='查询时间')
    
    class Meta:
        verbose_name = 'RAG查询'
        verbose_name_plural = 'RAG查询'
        ordering = ['-query_time']
    
    def __str__(self):
        return f"{self.query_text[:50]}..."


class APIKey(models.Model):
    """API密钥管理模型"""
    api_key_id = models.AutoField(primary_key=True, verbose_name='密钥ID')
    key_name = models.CharField(max_length=100, verbose_name='密钥名称')
    
    # API密钥信息
    api_key = models.CharField(max_length=500, verbose_name='API密钥')
    api_base = models.CharField(max_length=200, default='https://api.coze.cn', verbose_name='API基础URL')
    
    # 服务类型
    SERVICE_TYPES = [
        ('coze', 'Coze'),
        ('openai', 'OpenAI'),
        ('zhipu', '智谱AI'),
        ('deepseek', 'DeepSeek'),
        ('other', '其他')
    ]
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES, default='coze', verbose_name='服务类型')
    
    # 密钥状态
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    
    # 使用限制
    rate_limit = models.IntegerField(default=0, verbose_name='速率限制(每分钟)', help_text='0表示无限制')
    token_limit = models.IntegerField(default=0, verbose_name='令牌限制(每月)', help_text='0表示无限制')
    
    # 用量统计
    usage_count = models.IntegerField(default=0, verbose_name='使用次数')
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='最后使用时间')
    
    # 配置信息（JSON格式）
    config = models.TextField(null=True, blank=True, verbose_name='配置信息', help_text='JSON格式的额外配置参数')
    
    # 关联用户
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys', verbose_name='所属用户')
    
    # 时间戳
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    # 项目关联（可选）
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='api_keys', verbose_name='关联项目')
    
    class Meta:
        verbose_name = 'API密钥'
        verbose_name_plural = 'API密钥'
        ordering = ['-create_time']
        unique_together = ['user', 'key_name']  # 同一用户下密钥名称不能重复
    
    def __str__(self):
        return f"{self.key_name} ({self.service_type})"
    
    def save(self, *args, **kwargs):
        # 如果设置为默认密钥，将同一用户下同一服务类型的其他密钥设为非默认
        if self.is_default:
            APIKey.objects.filter(user=self.user, service_type=self.service_type).update(is_default=False)
        super().save(*args, **kwargs)


class AnalysisResult(models.Model):
    """AI分析结果模型，保存文件分析结果"""
    analysis_id = models.AutoField(primary_key=True, verbose_name='分析ID')
    file_name = models.CharField(max_length=255, verbose_name='文件名')
    file_type = models.CharField(max_length=50, verbose_name='文件类型')
    deepseek_response = models.TextField(verbose_name='DeepSeek响应', null=True, blank=True)
    sheets_data = models.TextField(verbose_name='解析的表格数据', null=True, blank=True)
    test_cases_data = models.TextField(verbose_name='测试用例数据', null=True, blank=True)
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='analysis_results',
                                verbose_name='创建者')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, 
                                related_name='analysis_results', verbose_name='项目')
    
    def __str__(self):
        return f"{self.file_name} - {self.create_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    class Meta:
        ordering = ['-create_time']
        verbose_name = 'AI分析结果'
        verbose_name_plural = 'AI分析结果'


class TestMindMap(models.Model):
    """测试脑图模型"""
    mindmap_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, verbose_name='脑图名称')
    data = models.TextField(verbose_name='脑图数据')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='mindmaps', verbose_name='所属项目')
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='创建人')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '测试脑图'
        verbose_name_plural = '测试脑图'
        db_table = 'test_platform_testmindmap'
        ordering = ['-update_time']

    def __str__(self):
        return self.name
