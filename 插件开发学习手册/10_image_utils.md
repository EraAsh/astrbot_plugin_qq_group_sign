# 图像处理和实用工具快速参考

## 文字转图片
```python
@filter.command("text2img")
async def text_to_image(self, event: AstrMessageEvent, text: str):
    """将文字转换为图片"""
    try:
        # 使用AstrBot内置方法
        image_url = await self.text_to_image(text)
        yield event.image_result(image_url)
        
        # 如果需要文件路径而不是URL
        # image_path = await self.text_to_image(text, return_url=False)
        
    except Exception as e:
        logger.error(f"文字转图片失败: {e}")
        yield event.plain_result(f"转换失败: {str(e)}")
```

## 自定义HTML渲染
```python
@filter.command("html_render")
async def html_render_demo(self, event: AstrMessageEvent):
    """自定义HTML模板渲染"""
    
    # HTML模板
    template = '''
    <div style="
        font-family: 'Microsoft YaHei', Arial, sans-serif;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        max-width: 400px;
    ">
        <h2 style="text-align: center; margin: 0 0 20px 0; font-size: 24px;">
            {{ title }}
        </h2>
        
        <div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 10px; margin-bottom: 15px;">
            <h3 style="margin: 0 0 10px 0; font-size: 16px;">📋 待办事项</h3>
            <ul style="list-style: none; padding: 0; margin: 0;">
            {% for item in todos %}
                <li style="
                    background: rgba(255,255,255,0.1);
                    margin: 8px 0;
                    padding: 10px;
                    border-radius: 8px;
                    border-left: 4px solid #FFD700;
                ">
                    {{ item }}
                </li>
            {% endfor %}
            </ul>
        </div>
        
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            opacity: 0.8;
        ">
            <span>🕒 {{ timestamp }}</span>
            <span>👤 {{ user }}</span>
        </div>
    </div>
    '''
    
    # 数据
    import datetime
    data = {
        "title": "我的计划",
        "todos": [
            "完成AstrBot插件开发",
            "学习新的编程技术",
            "整理项目文档",
            "优化代码性能"
        ],
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "user": event.get_sender_name()
    }
    
    try:
        image_url = await self.html_render(template, data)
        yield event.image_result(image_url)
    except Exception as e:
        logger.error(f"HTML渲染失败: {e}")
        yield event.plain_result(f"渲染失败: {str(e)}")
```

## 图片处理工具
```python
from PIL import Image, ImageDraw, ImageFont
import io
import base64

def create_simple_image(self, text: str, width: int = 400, height: int = 200) -> str:
    """创建简单的图片"""
    try:
        # 创建图片
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)
        
        # 尝试使用系统字体
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        # 计算文字位置
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # 绘制文字
        draw.text((x, y), text, font=font, fill='black')
        
        # 保存到data目录
        import os
        os.makedirs("data/temp", exist_ok=True)
        
        import time
        filename = f"temp_img_{int(time.time())}.png"
        file_path = os.path.join("data/temp", filename)
        
        img.save(file_path)
        return file_path
        
    except Exception as e:
        logger.error(f"创建图片失败: {e}")
        raise

@filter.command("simple_img")
async def create_img(self, event: AstrMessageEvent, text: str):
    """创建简单图片"""
    try:
        image_path = self.create_simple_image(text)
        yield event.image_result(image_path)
    except Exception as e:
        yield event.plain_result(f"创建图片失败: {str(e)}")
```

## 进度条生成器
```python
def generate_progress_bar(self, progress: float, width: int = 300) -> str:
    """生成进度条HTML"""
    progress = max(0, min(100, progress))  # 限制在0-100之间
    
    template = f'''
    <div style="
        font-family: Arial, sans-serif;
        padding: 20px;
        background: #f0f0f0;
        border-radius: 10px;
        width: {width}px;
    ">
        <div style="margin-bottom: 10px; font-size: 16px; font-weight: bold;">
            进度: {progress:.1f}%
        </div>
        
        <div style="
            background: #ddd;
            border-radius: 10px;
            overflow: hidden;
            height: 20px;
        ">
            <div style="
                background: linear-gradient(90deg, #4CAF50, #45a049);
                height: 100%;
                width: {progress}%;
                transition: width 0.3s ease;
                border-radius: 10px;
            "></div>
        </div>
        
        <div style="
            margin-top: 10px;
            font-size: 12px;
            color: #666;
            text-align: center;
        ">
            {'■' * int(progress // 5)}{'□' * int((100 - progress) // 5)}
        </div>
    </div>
    '''
    
    return template

@filter.command("progress")
async def show_progress(self, event: AstrMessageEvent, value: float):
    """显示进度条"""
    try:
        html = self.generate_progress_bar(value)
        image_url = await self.html_render(html, {})
        yield event.image_result(image_url)
    except Exception as e:
        yield event.plain_result(f"生成进度条失败: {str(e)}")
```

## 二维码生成
```python
# 需要安装: pip install qrcode[pil]
import qrcode
from io import BytesIO

def generate_qr_code(self, text: str) -> str:
    """生成二维码"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 保存文件
        import os
        import time
        os.makedirs("data/temp", exist_ok=True)
        
        filename = f"qr_{int(time.time())}.png"
        file_path = os.path.join("data/temp", filename)
        
        img.save(file_path)
        return file_path
        
    except Exception as e:
        logger.error(f"生成二维码失败: {e}")
        raise

@filter.command("qrcode")
async def create_qr(self, event: AstrMessageEvent, text: str):
    """生成二维码"""
    try:
        qr_path = self.generate_qr_code(text)
        yield event.image_result(qr_path)
    except Exception as e:
        yield event.plain_result(f"生成二维码失败: {str(e)}")
```

## 数据可视化
```python
# 需要安装: pip install matplotlib
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 无GUI模式

def create_chart(self, data: dict, chart_type: str = "bar") -> str:
    """创建图表"""
    try:
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']  # 中文字体
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if chart_type == "bar":
            ax.bar(data.keys(), data.values())
            ax.set_title("柱状图")
        elif chart_type == "line":
            ax.plot(list(data.keys()), list(data.values()), marker='o')
            ax.set_title("折线图")
        elif chart_type == "pie":
            ax.pie(data.values(), labels=data.keys(), autopct='%1.1f%%')
            ax.set_title("饼图")
        
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # 保存图片
        import os
        import time
        os.makedirs("data/temp", exist_ok=True)
        
        filename = f"chart_{int(time.time())}.png"
        file_path = os.path.join("data/temp", filename)
        
        plt.savefig(file_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return file_path
        
    except Exception as e:
        logger.error(f"创建图表失败: {e}")
        raise

@filter.command("chart")
async def create_chart_cmd(self, event: AstrMessageEvent, chart_type: str = "bar"):
    """创建示例图表"""
    try:
        # 示例数据
        data = {
            "周一": 23,
            "周二": 45,
            "周三": 56,
            "周四": 78,
            "周五": 32,
            "周六": 67,
            "周日": 89
        }
        
        chart_path = self.create_chart(data, chart_type)
        yield event.image_result(chart_path)
        
    except Exception as e:
        yield event.plain_result(f"创建图表失败: {str(e)}")
```

## 文件类型检测
```python
import mimetypes
import magic  # 需要安装: pip install python-magic-bin (Windows)

def detect_file_type(self, file_path: str) -> str:
    """检测文件类型"""
    try:
        # 方法1: 使用mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type:
            return mime_type
        
        # 方法2: 使用python-magic (更准确)
        if magic:
            return magic.from_file(file_path, mime=True)
        
        return "unknown"
        
    except Exception as e:
        logger.error(f"检测文件类型失败: {e}")
        return "unknown"

def is_image_file(self, file_path: str) -> bool:
    """检查是否为图片文件"""
    mime_type = self.detect_file_type(file_path)
    return mime_type.startswith('image/') if mime_type else False
```

## 文件大小转换
```python
def format_file_size(self, size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

@filter.command("fileinfo")
async def file_info(self, event: AstrMessageEvent, file_path: str):
    """获取文件信息"""
    try:
        import os
        from pathlib import Path
        
        if not os.path.exists(file_path):
            yield event.plain_result("文件不存在")
            return
        
        file_stat = os.stat(file_path)
        file_size = self.format_file_size(file_stat.st_size)
        file_type = self.detect_file_type(file_path)
        
        import datetime
        modified_time = datetime.datetime.fromtimestamp(file_stat.st_mtime)
        
        info = f"""文件信息:
📁 名称: {Path(file_path).name}
📏 大小: {file_size}
🎯 类型: {file_type}
📅 修改时间: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}"""
        
        yield event.plain_result(info)
        
    except Exception as e:
        yield event.plain_result(f"获取文件信息失败: {str(e)}")
```

## 临时文件管理
```python
import tempfile
import atexit
import threading

class TempFileManager:
    def __init__(self):
        self.temp_files = set()
        self.lock = threading.Lock()
        atexit.register(self.cleanup_all)
    
    def create_temp_file(self, suffix: str = "", prefix: str = "astrbot_") -> str:
        """创建临时文件"""
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            prefix=prefix,
            dir="data/temp"
        )
        temp_path = temp_file.name
        temp_file.close()
        
        with self.lock:
            self.temp_files.add(temp_path)
        
        return temp_path
    
    def cleanup_file(self, file_path: str):
        """清理单个文件"""
        try:
            import os
            if os.path.exists(file_path):
                os.unlink(file_path)
            
            with self.lock:
                self.temp_files.discard(file_path)
                
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")
    
    def cleanup_all(self):
        """清理所有临时文件"""
        with self.lock:
            for file_path in list(self.temp_files):
                self.cleanup_file(file_path)

# 在插件中使用
def __init__(self, context: Context):
    super().__init__(context)
    self.temp_manager = TempFileManager()

async def terminate(self):
    """插件停止时清理临时文件"""
    self.temp_manager.cleanup_all()
```

## 图片缩放和处理
```python
from PIL import Image

def resize_image(self, input_path: str, max_width: int = 800, max_height: int = 600) -> str:
    """调整图片大小"""
    try:
        with Image.open(input_path) as img:
            # 计算新尺寸
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # 创建输出文件
            output_path = self.temp_manager.create_temp_file(suffix=".jpg")
            
            # 转换为RGB (处理RGBA)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            img.save(output_path, "JPEG", quality=85, optimize=True)
            
        return output_path
        
    except Exception as e:
        logger.error(f"调整图片大小失败: {e}")
        raise

@filter.command("resize")
async def resize_image_cmd(self, event: AstrMessageEvent, width: int = 800, height: int = 600):
    """调整图片大小 (需要回复包含图片的消息)"""
    try:
        # 检查消息中是否有图片
        image_url = None
        for msg_seg in event.message_obj.message:
            if hasattr(msg_seg, 'type') and msg_seg.type == 'image':
                image_url = msg_seg.data.get('url')
                break
        
        if not image_url:
            yield event.plain_result("请发送包含图片的消息")
            return
        
        # 下载图片
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    temp_input = self.temp_manager.create_temp_file(suffix=".jpg")
                    
                    with open(temp_input, 'wb') as f:
                        f.write(await response.read())
                    
                    # 调整大小
                    resized_path = self.resize_image(temp_input, width, height)
                    
                    yield event.image_result(resized_path)
                    
                    # 清理临时文件
                    self.temp_manager.cleanup_file(temp_input)
                    self.temp_manager.cleanup_file(resized_path)
                else:
                    yield event.plain_result("下载图片失败")
        
    except Exception as e:
        yield event.plain_result(f"处理图片失败: {str(e)}")
```
