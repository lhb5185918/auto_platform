from django.http import JsonResponse
from rest_framework.views import APIView
from django.db.models import Count, Q, F
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from datetime import datetime, timedelta
import calendar
import locale
from test_platform.models import TestSuiteResult


class TestTrendView(APIView):
    """测试执行趋势统计视图"""
    
    def get(self, request):
        trend_type = request.GET.get('type', 'week')  # 默认为周趋势
        
        if trend_type == 'week':
            # 获取最近7天的数据
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=6)
            
            # 按天聚合统计数据
            results = (TestSuiteResult.objects
                      .filter(execution_time__date__gte=start_date, execution_time__date__lte=end_date)
                      .annotate(date=TruncDay('execution_time'))
                      .values('date')
                      .annotate(
                          total_count=Count('result_id'),
                          success_count=Count('result_id', filter=Q(status='pass')),
                          fail_count=Count('result_id', filter=Q(status__in=['fail', 'error', 'partial']))
                      )
                      .order_by('date'))
            
            # 准备数据
            dates = []
            total_counts = []
            success_counts = []
            fail_counts = []
            
            # 创建包含所有日期的字典
            date_range = {}
            current_date = start_date
            
            # 星期几的中文表示
            weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            
            while current_date <= end_date:
                # 获取日期对应的星期几（0-6，0是周一）
                weekday_idx = current_date.weekday()
                date_str = weekdays[weekday_idx]
                
                date_range[current_date.strftime('%Y-%m-%d')] = {
                    'date_str': date_str,
                    'total_count': 0,
                    'success_count': 0,
                    'fail_count': 0
                }
                current_date += timedelta(days=1)
            
            # 填充查询结果
            for result in results:
                date_key = result['date'].strftime('%Y-%m-%d')
                if date_key in date_range:
                    date_range[date_key]['total_count'] = result['total_count']
                    date_range[date_key]['success_count'] = result['success_count']
                    date_range[date_key]['fail_count'] = result['fail_count']
            
            # 按日期顺序填充结果数组
            for date_key in sorted(date_range.keys()):
                data = date_range[date_key]
                dates.append(data['date_str'])
                total_counts.append(data['total_count'])
                success_counts.append(data['success_count'])
                fail_counts.append(data['fail_count'])
            
        elif trend_type == 'month':
            # 获取当前月的数据
            today = datetime.now()
            first_day = today.replace(day=1)
            last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
            
            # 按天聚合统计数据
            results = (TestSuiteResult.objects
                      .filter(execution_time__date__gte=first_day, execution_time__date__lte=last_day)
                      .annotate(date=TruncDay('execution_time'))
                      .values('date')
                      .annotate(
                          total_count=Count('result_id'),
                          success_count=Count('result_id', filter=Q(status='pass')),
                          fail_count=Count('result_id', filter=Q(status__in=['fail', 'error', 'partial']))
                      )
                      .order_by('date'))
            
            # 准备数据
            dates = []
            total_counts = []
            success_counts = []
            fail_counts = []
            
            # 创建包含当月所有日期的字典
            date_range = {}
            current_date = first_day
            while current_date <= last_day:
                # 获取日期对应的日(DD格式)
                date_str = f"{current_date.day}日"
                
                date_range[current_date.strftime('%Y-%m-%d')] = {
                    'date_str': date_str,
                    'total_count': 0,
                    'success_count': 0,
                    'fail_count': 0
                }
                current_date += timedelta(days=1)
            
            # 填充查询结果
            for result in results:
                date_key = result['date'].strftime('%Y-%m-%d')
                if date_key in date_range:
                    date_range[date_key]['total_count'] = result['total_count']
                    date_range[date_key]['success_count'] = result['success_count']
                    date_range[date_key]['fail_count'] = result['fail_count']
            
            # 按日期顺序填充结果数组
            for date_key in sorted(date_range.keys()):
                data = date_range[date_key]
                dates.append(data['date_str'])
                total_counts.append(data['total_count'])
                success_counts.append(data['success_count'])
                fail_counts.append(data['fail_count'])
        
        # 返回统一格式的响应
        return JsonResponse({
            'code': 200,
            'message': 'success',
            'data': {
                'dates': dates,
                'total_counts': total_counts,
                'success_counts': success_counts,
                'fail_counts': fail_counts
            }
        }) 