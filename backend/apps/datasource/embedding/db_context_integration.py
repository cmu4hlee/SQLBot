"""
数据库描述上下文集成模块
将数据库描述的解析结果集成到自然语言查询的提示词中
"""

import re
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
import threading
import os

_db_context_injector = None
_db_context_lock = threading.Lock()


def _get_injector():
    """获取或创建数据库上下文注入器（单例模式）"""
    global _db_context_injector
    if _db_context_injector is None:
        with _db_context_lock:
            if _db_context_injector is None:
                from apps.datasource.embedding.db_context_injector import DatabaseContextInjector
                _db_context_injector = DatabaseContextInjector()
    return _db_context_injector


def get_db_context_for_prompt(question: str) -> str:
    """
    根据用户问题获取相关的数据库描述上下文
    用于注入到大模型的系统提示词中
    
    Args:
        question: 用户自然语言问题
        
    Returns:
        格式化的数据库上下文字符串，用于添加到提示词中
    """
    try:
        injector = _get_injector()
        context = injector.generate_relevant_context(question)
        return context
    except Exception as e:
        print(f"Failed to get db context: {e}")
        return ""


def get_full_db_context() -> str:
    """获取完整的数据库上下文"""
    try:
        injector = _get_injector()
        return injector.generate_full_context()
    except Exception as e:
        print(f"Failed to get full db context: {e}")
        return ""


def reload_db_context():
    """重新加载数据库上下文（当数据库描述文件更新时调用）"""
    global _db_context_injector
    _db_context_injector = None
    _get_injector()


def get_enum_hint_for_field(table_name: str, field_name: str) -> str:
    """
    获取字段的枚举值提示
    
    Args:
        table_name: 表名
        field_name: 字段名
        
    Returns:
        枚举值提示字符串
    """
    try:
        injector = _get_injector()
        enum_values = injector.get_table_enum_values(table_name)
        
        if field_name in enum_values:
            values = enum_values[field_name]
            if values:
                values_str = ", ".join(values)
                return f"\n注意: {table_name}.{field_name} 的可能取值包括: {values_str}"
    except Exception as e:
        print(f"Failed to get enum hint: {e}")
    return ""


def get_field_description(table_name: str, field_name: str) -> str:
    """
    获取字段的业务含义描述
    
    Args:
        table_name: 表名
        field_name: 字段名
        
    Returns:
        字段含义描述字符串
    """
    try:
        injector = _get_injector()
        table_info = injector.get_table_info(table_name)
        
        if table_info:
            for field in table_info.fields:
                if field.name.lower() == field_name.lower():
                    if field.comment:
                        return f"\n参考: {table_name}.{field_name} 表示{field.comment}"
    except Exception as e:
        print(f"Failed to get field description: {e}")
    return ""


def get_table_info(table_name: str) -> Optional[Dict[str, Any]]:
    """获取表的详细信息"""
    try:
        injector = _get_injector()
        table = injector.get_table_info(table_name)
        if table:
            return {
                "table_name": table.table_name,
                "table_comment": table.table_comment,
                "fields": [
                    {"name": f.name, "type": f.field_type, "comment": f.comment}
                    for f in table.fields
                ],
                "enums": table.enums,
                "foreign_keys": table.foreign_keys
            }
    except Exception as e:
        print(f"Failed to get table info: {e}")
    return None


def get_business_glossary() -> Dict[str, str]:
    """获取业务术语词典"""
    try:
        injector = _get_injector()
        return injector.get_business_glossary()
    except Exception as e:
        print(f"Failed to get business glossary: {e}")
        return {}


def enhance_schema_with_context(schema: str, question: str) -> str:
    """
    增强schema，添加数据库描述上下文
    
    Args:
        schema: 原始schema字符串
        question: 用户问题
        
    Returns:
        增强后的schema字符串
    """
    db_context = get_db_context_for_prompt(question)
    
    if db_context:
        enhanced = f"{schema}\n\n## 业务语义参考 (来自数据库描述):\n{db_context}"
        return enhanced
    
    return schema


class DBContextMiddleware:
    """
    数据库上下文中间件
    用于在SQL生成过程中注入数据库描述上下文
    """
    
    def __init__(self):
        self.enabled = True
    
    def before_generate_sql(self, question: str, schema: str) -> str:
        """
        SQL生成前的处理
        可以用于增强schema
        
        Args:
            question: 用户问题
            schema: 数据库schema
            
        Returns:
            增强后的schema
        """
        if not self.enabled:
            return schema
        
        return enhance_schema_with_context(schema, question)
    
    def after_generate_sql(self, question: str, generated_sql: str) -> str:
        """
        SQL生成后的处理
        可以用于添加枚举值提示等
        
        Args:
            question: 用户问题
            generated_sql: 生成的SQL
            
        Returns:
            处理后的SQL
        """
        if not self.enabled:
            return generated_sql
        
        # 这里可以添加SQL后处理逻辑，比如验证枚举值等
        return generated_sql


db_context_middleware = DBContextMiddleware()


def is_db_context_available() -> bool:
    """检查数据库描述上下文是否可用"""
    try:
        injector = _get_injector()
        modules = injector.get_modules()
        return len(modules) > 0
    except Exception:
        return False


def get_db_context_stats() -> Dict[str, Any]:
    """获取数据库上下文状态统计"""
    try:
        injector = _get_injector()
        modules = injector.get_modules()
        
        total_tables = sum(len(m.tables) for m in modules)
        total_fields = sum(
            len([f for f in m.tables[i].fields 
                 if f.name not in ['id', 'created_at', 'updated_at']])
            for m in modules for i in range(len(m.tables))
        )
        total_enums = sum(
            sum(len(t.enums) for t in m.tables)
            for m in modules
        )
        
        return {
            "available": True,
            "modules_count": len(modules),
            "tables_count": total_tables,
            "fields_count": total_fields,
            "enums_count": total_enums,
            "last_update": injector._last_parse_time.isoformat() if injector._last_parse_time else None
        }
    except Exception as e:
        return {
            "available": False,
            "error": str(e)
        }
