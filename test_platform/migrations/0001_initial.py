# Generated by Django 4.2.17 on 2024-12-22 08:13

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Project',
            fields=[
                ('project_id', models.AutoField(primary_key=True, serialize=False, verbose_name='项目ID')),
                ('name', models.CharField(max_length=255, verbose_name='项目名称')),
                ('description', models.TextField(verbose_name='项目描述')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('is_active', models.IntegerField(default=0, verbose_name='状态是否活跃')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='projects', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
        ),
        migrations.CreateModel(
            name='TestCase',
            fields=[
                ('test_case_id', models.AutoField(db_comment='测试用例的唯一标识', primary_key=True, serialize=False, verbose_name='用例ID')),
                ('case_name', models.CharField(db_comment='测试用例的名称', max_length=255, verbose_name='用例名称')),
                ('case_description', models.TextField(db_comment='对测试用例的详细描述', verbose_name='用例描述')),
                ('case_path', models.CharField(db_comment='测试用例的文件路径', max_length=255, verbose_name='用例路径')),
                ('case_request_method', models.CharField(db_comment='HTTP请求方法', max_length=255, verbose_name='请求方法')),
                ('case_priority', models.IntegerField(choices=[(0, '低'), (1, '中'), (2, '高')], db_comment='测试用例的优先级', default=0, verbose_name='用例优先级')),
                ('case_status', models.IntegerField(choices=[(0, '未执行'), (1, '已执行')], db_comment='测试用例的执行状态', default=0, verbose_name='用例执行状态')),
                ('case_params', models.TextField(db_comment='HTTP请求参数', verbose_name='请求参数')),
                ('case_precondition', models.TextField(db_comment='执行测试用例前的条件', verbose_name='前置条件')),
                ('case_request_headers', models.TextField(db_comment='HTTP请求头信息', verbose_name='请求头')),
                ('case_requests_body', models.TextField(db_comment='HTTP请求体内容', verbose_name='请求体')),
                ('case_expect_result', models.TextField(db_comment='测试用例的预期结果', verbose_name='期望结果')),
                ('case_assert_type', models.CharField(blank=True, db_comment='断言的类型', max_length=50, null=True, verbose_name='断言类型')),
                ('case_assert_contents', models.TextField(db_comment='断言的具体内容', verbose_name='断言内容')),
                ('create_time', models.DateTimeField(auto_now_add=True, db_comment='测试用例的创建时间', verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, db_comment='测试用例的最后更新时间', verbose_name='更新时间')),
                ('last_executed_at', models.DateTimeField(blank=True, db_comment='最后一次执行测试用例的时间', null=True, verbose_name='最近执行时间')),
                ('last_execution_result', models.CharField(choices=[('passed', '通过'), ('failed', '失败'), ('blocked', '阻塞'), ('not_run', '未执行')], db_comment='最近一次执行的结果', default='not_run', max_length=20, verbose_name='最近执行结果')),
                ('creator', models.ForeignKey(db_comment='创建该测试用例的用户', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='test_cases', to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
                ('project', models.ForeignKey(db_comment='关联的项目', on_delete=django.db.models.deletion.CASCADE, related_name='test_cases', to='test_platform.project', verbose_name='项目')),
            ],
        ),
        migrations.CreateModel(
            name='TestEnvironment',
            fields=[
                ('environment_id', models.AutoField(primary_key=True, serialize=False, verbose_name='环境ID')),
                ('host', models.CharField(max_length=255, verbose_name='主机地址')),
                ('port', models.IntegerField(verbose_name='端口号')),
                ('base_url', models.CharField(max_length=255, verbose_name='基础URL')),
                ('protocol', models.CharField(max_length=50, verbose_name='协议')),
                ('token', models.CharField(max_length=255, verbose_name='令牌值')),
                ('db_host', models.CharField(max_length=255, verbose_name='主机地址')),
                ('db_port', models.IntegerField(verbose_name='端口号')),
                ('db_name', models.CharField(max_length=255, verbose_name='数据库名称')),
                ('db_user', models.CharField(max_length=50, verbose_name='用户名')),
                ('db_password', models.CharField(max_length=50, verbose_name='密码')),
                ('time_out', models.IntegerField(verbose_name='超时时间')),
                ('description', models.TextField(verbose_name='环境描述')),
                ('content_type', models.CharField(max_length=50, verbose_name='内容类型')),
                ('charset', models.CharField(max_length=50, verbose_name='字符集')),
                ('env_name', models.CharField(max_length=50, verbose_name='环境名称')),
                ('version', models.CharField(max_length=50, verbose_name='版本号')),
            ],
        ),
        migrations.CreateModel(
            name='TestResult',
            fields=[
                ('test_result_id', models.AutoField(default=1, primary_key=True, serialize=False, verbose_name='结果ID')),
                ('execution_time', models.DateTimeField(verbose_name='执行时间')),
                ('status', models.CharField(choices=[('PASS', '通过'), ('FAIL', '失败'), ('ERROR', '错误'), ('SKIP', '跳过')], max_length=20, verbose_name='执行状态')),
                ('result_data', models.TextField(verbose_name='结果数据')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='错误信息')),
                ('duration', models.FloatField(default=0, help_text='单位：秒', verbose_name='执行时长')),
                ('case', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='results', to='test_platform.testcase', verbose_name='测试用例')),
                ('environment', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='test_results', to='test_platform.testenvironment', verbose_name='执行环境')),
            ],
        ),
        migrations.CreateModel(
            name='TestEnvironmentCover',
            fields=[
                ('environment_cover_id', models.AutoField(primary_key=True, serialize=False, verbose_name='环境套id')),
                ('environment_name', models.CharField(max_length=255, verbose_name='环境名称')),
                ('environment_description', models.TextField(verbose_name='环境描述')),
                ('create_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('update_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('creat_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='environment_covers', to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='environment_covers', to='test_platform.project', verbose_name='项目')),
            ],
        ),
        migrations.AddField(
            model_name='testenvironment',
            name='environment_cover',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='environments', to='test_platform.testenvironmentcover', verbose_name='环境套'),
        ),
        migrations.AddField(
            model_name='testenvironment',
            name='project',
            field=models.ForeignKey(db_comment='关联的项目', on_delete=django.db.models.deletion.CASCADE, related_name='environments', to='test_platform.project', verbose_name='项目'),
        ),
    ]
