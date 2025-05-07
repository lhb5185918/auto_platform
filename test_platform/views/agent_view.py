import os
import json
import uuid
import pandas as pd
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import logging
import docx
import PyPDF2
import io

logger = logging.getLogger(__name__)

# 定义允许的文件类型
ALLOWED_EXTENSIONS = {
    'docx': ['docx'],
    'excel': ['xlsx', 'xls', 'csv'],
    'pdf': ['pdf']
}

# 创建临时文件存储目录
TEMP_DIR = os.path.join(settings.MEDIA_ROOT, 'temp_files')
os.makedirs(TEMP_DIR, exist_ok=True)


class FileParseView(APIView):
    """
    文件解析视图
    处理不同类型文件的上传和解析功能
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        """
        处理文件上传及解析
        :param request: 包含文件和解析参数的请求
        :return: 解析结果或错误信息
        """
        try:
            # 检查是否有文件上传
            if 'file' not in request.FILES:
                return JsonResponse({
                    'code': 400,
                    'message': '未找到上传的文件',
                    'data': None
                }, status=400)

            uploaded_file = request.FILES['file']
            
            # 获取文件扩展名并检查是否支持
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            # 根据文件类型调用相应的解析方法
            if file_extension in ALLOWED_EXTENSIONS['docx']:
                result = self.parse_docx(uploaded_file)
            elif file_extension in ALLOWED_EXTENSIONS['excel']:
                result = self.parse_excel(uploaded_file, file_extension)
            elif file_extension in ALLOWED_EXTENSIONS['pdf']:
                result = self.parse_pdf(uploaded_file)
            else:
                return JsonResponse({
                    'code': 400,
                    'message': f'不支持的文件类型: {file_extension}',
                    'data': None
                }, status=400)
            
            return JsonResponse({
                'code': 200,
                'message': '文件解析成功',
                'data': result
            })
            
        except Exception as e:
            logger.error(f"文件解析失败: {str(e)}", exc_info=True)
            return JsonResponse({
                'code': 500,
                'message': f'文件解析失败: {str(e)}',
                'data': None
            }, status=500)
    
    def save_temp_file(self, file):
        """
        保存临时文件
        :param file: 上传的文件对象
        :return: 临时文件的路径
        """
        # 生成唯一的文件名
        filename = f"{uuid.uuid4()}_{file.name}"
        filepath = os.path.join(TEMP_DIR, filename)
        
        # 保存文件
        with open(filepath, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
                
        return filepath
    
    def parse_docx(self, file):
        """
        解析Word文档
        :param file: 上传的docx文件
        :return: 解析结果，包含文档内容和结构信息
        """
        # 使用python-docx库解析文档
        doc = docx.Document(file)
        
        # 提取文档内容
        content = {
            'paragraphs': [],
            'tables': []
        }
        
        # 提取段落
        for para in doc.paragraphs:
            if para.text.strip():
                content['paragraphs'].append({
                    'text': para.text,
                    'style': para.style.name if para.style else 'Normal'
                })
        
        # 提取表格
        for i, table in enumerate(doc.tables):
            table_data = []
            for row in table.rows:
                row_data = []
                for cell in row.cells:
                    row_data.append(cell.text)
                table_data.append(row_data)
            content['tables'].append({
                'id': i + 1,
                'data': table_data
            })
        
        # 返回解析结果
        return {
            'file_type': 'docx',
            'file_name': file.name,
            'content': content
        }
    
    def parse_excel(self, file, file_extension):
        """
        解析Excel文件
        :param file: 上传的Excel文件
        :param file_extension: 文件扩展名
        :return: 解析结果，包含工作表和数据
        """
        # 保存临时文件
        temp_file_path = self.save_temp_file(file)
        
        try:
            # 根据文件类型选择读取方式
            if file_extension == 'csv':
                # 读取CSV文件
                df = pd.read_csv(temp_file_path)
                sheets = [{
                    'name': 'Sheet1',
                    'data': df.fillna('').to_dict(orient='records')
                }]
            else:
                # 读取Excel文件
                excel_file = pd.ExcelFile(temp_file_path)
                sheets = []
                
                # 遍历所有工作表
                for sheet_name in excel_file.sheet_names:
                    df = excel_file.parse(sheet_name)
                    sheets.append({
                        'name': sheet_name,
                        'data': df.fillna('').to_dict(orient='records')
                    })
            
            # 返回解析结果
            return {
                'file_type': file_extension,
                'file_name': file.name,
                'sheets': sheets
            }
            
        finally:
            # 删除临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    def parse_pdf(self, file):
        """
        解析PDF文件
        :param file: 上传的PDF文件
        :return: 解析结果，包含文档页面和内容
        """
        # 从上传的文件创建二进制流
        file_stream = io.BytesIO(file.read())
        
        # 使用PyPDF2解析PDF
        pdf_reader = PyPDF2.PdfReader(file_stream)
        num_pages = len(pdf_reader.pages)
        
        # 提取文档内容
        content = {
            'num_pages': num_pages,
            'pages': []
        }
        
        # 提取每页内容
        for i in range(num_pages):
            page = pdf_reader.pages[i]
            page_text = page.extract_text()
            content['pages'].append({
                'page_num': i + 1,
                'text': page_text
            })
        
        # 返回解析结果
        return {
            'file_type': 'pdf',
            'file_name': file.name,
            'content': content
        }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([JWTAuthentication])
def file_parse(request):
    """
    文件解析API视图函数
    :param request: HTTP请求对象
    :return: JsonResponse包含解析结果
    """
    # 实例化视图类并调用post方法
    view = FileParseView()
    return view.post(request)
