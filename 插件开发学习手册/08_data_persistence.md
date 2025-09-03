# 数据持久化快速参考

## 基本文件操作
```python
import os
import json
from pathlib import Path

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 在data目录下创建插件专用目录
        self.data_dir = Path("data/plugins/my_plugin_data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 数据文件路径
        self.user_data_file = self.data_dir / "users.json"
        self.config_file = self.data_dir / "plugin_config.json"
        
        # 加载数据
        self.user_data = self.load_json_file(self.user_data_file, {})
        self.plugin_config = self.load_json_file(self.config_file, {})

    def load_json_file(self, file_path: Path, default_value=None):
        """加载JSON文件"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"加载文件失败 {file_path}: {e}")
        
        return default_value if default_value is not None else {}

    def save_json_file(self, file_path: Path, data):
        """保存JSON文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存文件失败 {file_path}: {e}")
            raise

    def save_user_data(self):
        """保存用户数据"""
        self.save_json_file(self.user_data_file, self.user_data)

    def save_plugin_config(self):
        """保存插件配置"""
        self.save_json_file(self.config_file, self.plugin_config)
```

## 用户数据管理
```python
@filter.command("save_data")
async def save_user_data(self, event: AstrMessageEvent, key: str, value: str):
    """保存用户数据"""
    try:
        user_id = event.get_sender_id()
        
        # 确保用户数据存在
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        
        # 保存数据
        self.user_data[user_id][key] = value
        self.save_user_data()
        
        yield event.plain_result(f"数据已保存: {key} = {value}")
        
    except Exception as e:
        logger.error(f"保存用户数据失败: {e}")
        yield event.plain_result("保存失败")

@filter.command("get_data")
async def get_user_data(self, event: AstrMessageEvent, key: str):
    """获取用户数据"""
    try:
        user_id = event.get_sender_id()
        value = self.user_data.get(user_id, {}).get(key, "未找到")
        yield event.plain_result(f"{key}: {value}")
        
    except Exception as e:
        logger.error(f"获取用户数据失败: {e}")
        yield event.plain_result("获取失败")

@filter.command("list_data")
async def list_user_data(self, event: AstrMessageEvent):
    """列出用户所有数据"""
    try:
        user_id = event.get_sender_id()
        data = self.user_data.get(user_id, {})
        
        if not data:
            yield event.plain_result("您还没有保存任何数据")
            return
        
        result = "您的数据:\n"
        for key, value in data.items():
            result += f"{key}: {value}\n"
        
        yield event.plain_result(result)
        
    except Exception as e:
        logger.error(f"列出用户数据失败: {e}")
        yield event.plain_result("获取失败")
```

## 群组数据管理
```python
@filter.command("save_group_data")
async def save_group_data(self, event: AstrMessageEvent, key: str, value: str):
    """保存群组数据"""
    try:
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("此指令仅在群聊中使用")
            return
        
        # 群组数据文件
        group_data_file = self.data_dir / f"group_{group_id}.json"
        group_data = self.load_json_file(group_data_file, {})
        
        group_data[key] = value
        self.save_json_file(group_data_file, group_data)
        
        yield event.plain_result(f"群组数据已保存: {key} = {value}")
        
    except Exception as e:
        logger.error(f"保存群组数据失败: {e}")
        yield event.plain_result("保存失败")
```

## CSV文件操作
```python
import csv

def save_to_csv(self, filename: str, data: list):
    """保存数据到CSV文件"""
    try:
        csv_path = self.data_dir / filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        
        logger.info(f"CSV文件已保存: {csv_path}")
        
    except Exception as e:
        logger.error(f"保存CSV文件失败: {e}")
        raise

def load_from_csv(self, filename: str):
    """从CSV文件加载数据"""
    try:
        csv_path = self.data_dir / filename
        
        if not csv_path.exists():
            return []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
            
    except Exception as e:
        logger.error(f"加载CSV文件失败: {e}")
        return []

@filter.command("export_users")
async def export_users_csv(self, event: AstrMessageEvent):
    """导出用户数据为CSV"""
    try:
        # 转换用户数据为CSV格式
        csv_data = []
        for user_id, data in self.user_data.items():
            row = {"user_id": user_id}
            row.update(data)
            csv_data.append(row)
        
        self.save_to_csv("users_export.csv", csv_data)
        yield event.plain_result("用户数据已导出到CSV文件")
        
    except Exception as e:
        logger.error(f"导出CSV失败: {e}")
        yield event.plain_result("导出失败")
```

## 数据库操作 (SQLite)
```python
import sqlite3
import aiosqlite

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def init_database(self):
        """初始化数据库"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    score INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    key TEXT,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            await db.commit()

    async def add_user(self, user_id: str, username: str):
        """添加用户"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)',
                (user_id, username)
            )
            await db.commit()

    async def get_user_score(self, user_id: str):
        """获取用户积分"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT score FROM users WHERE user_id = ?', 
                (user_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def update_user_score(self, user_id: str, score: int):
        """更新用户积分"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE users SET score = ? WHERE user_id = ?',
                (score, user_id)
            )
            await db.commit()

# 在插件中使用
def __init__(self, context: Context):
    super().__init__(context)
    self.data_dir = Path("data/plugins/my_plugin_data")
    self.data_dir.mkdir(parents=True, exist_ok=True)
    
    self.db = DatabaseManager(str(self.data_dir / "plugin.db"))
    asyncio.create_task(self.db.init_database())

@filter.command("add_score")
async def add_score(self, event: AstrMessageEvent, points: int):
    """增加积分"""
    try:
        user_id = event.get_sender_id()
        username = event.get_sender_name()
        
        # 确保用户存在
        await self.db.add_user(user_id, username)
        
        # 获取当前积分
        current_score = await self.db.get_user_score(user_id)
        new_score = current_score + points
        
        # 更新积分
        await self.db.update_user_score(user_id, new_score)
        
        yield event.plain_result(f"积分已更新: {current_score} → {new_score}")
        
    except Exception as e:
        logger.error(f"更新积分失败: {e}")
        yield event.plain_result("更新失败")
```

## 文件缓存管理
```python
import time
import hashlib

class FileCache:
    def __init__(self, cache_dir: Path, max_age: int = 3600):
        self.cache_dir = cache_dir
        self.max_age = max_age  # 缓存有效期（秒）
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, url: str) -> str:
        """生成缓存键"""
        return hashlib.md5(url.encode()).hexdigest()

    def get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.cache"

    def is_cache_valid(self, cache_path: Path) -> bool:
        """检查缓存是否有效"""
        if not cache_path.exists():
            return False
        
        file_age = time.time() - cache_path.stat().st_mtime
        return file_age < self.max_age

    async def get_cached_data(self, url: str):
        """获取缓存数据"""
        cache_key = self.get_cache_key(url)
        cache_path = self.get_cache_path(cache_key)
        
        if self.is_cache_valid(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"读取缓存失败: {e}")
        
        return None

    async def save_cache_data(self, url: str, data):
        """保存数据到缓存"""
        try:
            cache_key = self.get_cache_key(url)
            cache_path = self.get_cache_path(cache_key)
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")

    def clear_expired_cache(self):
        """清理过期缓存"""
        try:
            current_time = time.time()
            for cache_file in self.cache_dir.glob("*.cache"):
                file_age = current_time - cache_file.stat().st_mtime
                if file_age > self.max_age:
                    cache_file.unlink()
                    
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")

# 使用缓存
def __init__(self, context: Context):
    super().__init__(context)
    self.cache = FileCache(Path("data/plugins/my_plugin_cache"), max_age=1800)

@filter.command("cached_request")
async def cached_request(self, event: AstrMessageEvent, url: str):
    """带缓存的请求"""
    try:
        # 尝试从缓存获取
        cached_data = await self.cache.get_cached_data(url)
        if cached_data:
            yield event.plain_result(f"缓存数据: {cached_data}")
            return
        
        # 发起实际请求
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
        
        # 保存到缓存
        await self.cache.save_cache_data(url, data)
        yield event.plain_result(f"新数据: {data}")
        
    except Exception as e:
        yield event.plain_result(f"请求失败: {str(e)}")
```

## 数据备份与恢复
```python
import shutil
from datetime import datetime

def backup_data(self):
    """备份数据"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path("data/backups/my_plugin")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_path = backup_dir / f"backup_{timestamp}.zip"
        
        # 创建ZIP备份
        shutil.make_archive(
            str(backup_path.with_suffix('')),
            'zip',
            str(self.data_dir)
        )
        
        logger.info(f"数据已备份到: {backup_path}")
        return backup_path
        
    except Exception as e:
        logger.error(f"备份失败: {e}")
        raise

@filter.command("backup")
@filter.permission_type(filter.PermissionType.ADMIN)
async def create_backup(self, event: AstrMessageEvent):
    """创建数据备份"""
    try:
        backup_path = self.backup_data()
        yield event.plain_result(f"备份完成: {backup_path.name}")
    except Exception as e:
        yield event.plain_result(f"备份失败: {str(e)}")

def restore_data(self, backup_path: Path):
    """恢复数据"""
    try:
        if not backup_path.exists():
            raise FileNotFoundError("备份文件不存在")
        
        # 备份当前数据
        current_backup = self.backup_data()
        logger.info(f"当前数据已备份到: {current_backup}")
        
        # 恢复数据
        shutil.unpack_archive(str(backup_path), str(self.data_dir.parent))
        
        # 重新加载数据
        self.user_data = self.load_json_file(self.user_data_file, {})
        
        logger.info("数据恢复完成")
        
    except Exception as e:
        logger.error(f"恢复失败: {e}")
        raise
```

## 数据安全注意事项
```python
# 1. 敏感数据加密
import base64
from cryptography.fernet import Fernet

def encrypt_sensitive_data(self, data: str, key: bytes) -> str:
    """加密敏感数据"""
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return base64.b64encode(encrypted).decode()

def decrypt_sensitive_data(self, encrypted_data: str, key: bytes) -> str:
    """解密敏感数据"""
    f = Fernet(key)
    decoded = base64.b64decode(encrypted_data.encode())
    return f.decrypt(decoded).decode()

# 2. 数据验证
def validate_user_data(self, data: dict) -> bool:
    """验证用户数据格式"""
    required_fields = ['user_id', 'username']
    return all(field in data for field in required_fields)

# 3. 文件锁定（避免并发写入）
import fcntl

def safe_write_file(self, file_path: Path, data):
    """安全写入文件"""
    temp_path = file_path.with_suffix('.tmp')
    
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 文件锁
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 原子性替换
        temp_path.replace(file_path)
        
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e
```
