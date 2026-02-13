"""
数据库描述上下文注入模块
将数据库描述文件的解析结果注入到大模型的系统提示词中，增强模型对业务语义的理解
支持关键词搜索和语义向量搜索的混合检索
"""

import os
import re
import threading
from typing import Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime
import json

from apps.datasource.embedding.db_description_parser import DatabaseDescriptionParser, ModuleInfo, TableInfo
from apps.datasource.embedding.semantic_search import (
    SemanticSearchEngine,
    SearchResult as SemanticSearchResult,
    get_semantic_search_engine,
    build_semantic_index
)


class DatabaseContextInjector:
    """数据库描述上下文注入器"""

    _instance = None
    _parsed_modules: List[ModuleInfo] = None
    _last_parse_time: datetime = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._load_if_needed()

    def _load_if_needed(self):
        """如果需要的话加载解析结果"""
        if self._parsed_modules is None:
            self.reload()

    def reload(self):
        """重新加载并解析数据库描述文件"""
        description_file = None
        for path in ["/Users/cjlee/Desktop/Project/SQLbot/backend", "."]:
            if os.path.exists(f"{path}/数据库描述.md"):
                description_file = f"{path}/数据库描述.md"
                break

        if description_file and os.path.exists(description_file):
            try:
                parser = DatabaseDescriptionParser(description_file)
                self._parsed_modules = parser.parse()
                self._last_parse_time = datetime.now()
            except Exception as e:
                print(f"Failed to load database description: {e}")
                self._parsed_modules = []
        else:
            self._parsed_modules = []

    def get_modules(self) -> List[ModuleInfo]:
        """获取解析后的模块列表"""
        self._load_if_needed()
        return self._parsed_modules or []

    def generate_relevant_context(self, question: str) -> str:
        """
        根据用户问题生成相关的数据库上下文
        用于注入到大模型的系统提示词中
        """
        modules = self.get_modules()
        if not modules:
            return ""

        keywords = self._extract_keywords(question)
        relevant_parts = []

        for module in modules:
            relevance_score = self._calculate_relevance(module, keywords)
            if relevance_score > 0:
                relevant_parts.append((relevance_score, module))

        relevant_parts.sort(key=lambda x: x[0], reverse=True)

        if not relevant_parts:
            return ""

        context_lines = ["\n\n## 业务语义参考 (基于数据库描述):\n"]

        for score, module in relevant_parts[:3]:
            if score > 0:
                context_lines.append(f"### {module.module_name}\n")
                context_lines.append(f"{module.module_description}\n")

                table_scores = []
                for table in module.tables:
                    table_relevance = self._calculate_table_relevance(table, keywords)
                    if table_relevance > 0:
                        table_scores.append((table_relevance, table))

                table_scores.sort(key=lambda x: x[0], reverse=True)

                for _, table in table_scores[:3]:
                    context_lines.append(f"\n**{table.table_name}** ({table.table_comment}):\n")

                    if table.enums:
                        enum_list = []
                        for enum_name, values in table.enums.items():
                            val_names = ', '.join([v.get('value', '') for v in values[:3]])
                            enum_list.append(f"{enum_name}: {val_names}")
                        if enum_list:
                            context_lines.append(f"  状态类型: {'; '.join(enum_list)}\n")

                    key_fields = []
                    for field in table.fields[:5]:
                        if field.comment and field.name not in ['id', 'created_at', 'updated_at']:
                            key_fields.append(f"{field.name}({field.comment})")
                    if key_fields:
                        context_lines.append(f"  关键字段: {', '.join(key_fields)}\n")

        return ''.join(context_lines)

    def generate_full_context(self) -> str:
        """生成完整的数据库上下文"""
        modules = self.get_modules()
        if not modules:
            return ""

        context_lines = ["## 数据库架构上下文\n"]

        for module in modules:
            context_lines.append(f"\n### {module.module_name}\n")
            context_lines.append(f"{module.module_description}\n")

            for table in module.tables:
                context_lines.append(f"\n**{table.table_name}** - {table.table_comment}\n")

                if table.enums:
                    enum_info = []
                    for enum_name, values in table.enums.items():
                        val_list = ', '.join([v.get('value', '') for v in values[:5]])
                        enum_info.append(f"{enum_name}: {val_list}")
                    context_lines.append(f"  枚举: {'; '.join(enum_info)}\n")

                if table.foreign_keys:
                    fk_info = [f"{fk.get('field')}->{fk.get('ref_table')}" for fk in table.foreign_keys]
                    context_lines.append(f"  关联: {'; '.join(fk_info)}\n")

        return ''.join(context_lines)

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词（支持中英文混合，使用n-gram分词）"""
        import re

        text_clean = re.sub(r'[，。！？、：；""''【】（）\(\)\[\]]', ' ', text).strip()
        if not text_clean:
            return []

        stopwords = {'的', '是', '在', '有', '和', '与', '或', '及', '等', '查询', '统计', '获取', '查找',
                     '请问', '我想', '请', '帮我', '多少', '哪些', '什么', '如何', '怎样', '显示', '所有', '列表',
                     '一个', '这个', '那个', '哪些', '各种', '不同'}

        keywords = set()

        text_no_punct = re.sub(r'[^\w\s]', '', text_clean)

        is_chinese = any('\u4e00' <= c <= '\u9fff' for c in text_no_punct)

        if is_chinese:
            for i in range(len(text_no_punct) - 1):
                if '\u4e00' <= text_no_punct[i] <= '\u9fff':
                    ngram = text_no_punct[i:i+2]
                    if ngram not in stopwords and len(ngram) == 2:
                        keywords.add(ngram)

            words = text_clean.split()
            for word in words:
                word = word.strip()
                if word and len(word) >= 2 and word not in stopwords:
                    keywords.add(word)
        else:
            words = text_no_punct.split()
            for word in words:
                word = word.strip()
                if word and word not in stopwords and len(word) >= 2:
                    keywords.add(word)

        return list(keywords)

    def _calculate_relevance(self, module: ModuleInfo, keywords: List[str]) -> int:
        """计算模块与问题的相关性分数"""
        score = 0

        module_name_lower = module.module_name.lower()
        module_desc_lower = module.module_description.lower()

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in module_name_lower:
                score += 3
            if kw_lower in module_desc_lower:
                score += 1

        for table in module.tables:
            table_score = self._calculate_table_relevance(table, keywords)
            score += table_score

        return score

    def _calculate_table_relevance(self, table: TableInfo, keywords: List[str]) -> int:
        """计算表与问题的相关性分数"""
        score = 0

        table_name_lower = table.table_name.lower()
        table_comment_lower = table.table_comment.lower()

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in table_name_lower:
                score += 2
            if kw_lower in table_comment_lower:
                score += 1

            for field in table.fields:
                field_name_lower = field.name.lower()
                field_comment_lower = field.comment.lower() if field.comment else ""

                if kw_lower in field_name_lower:
                    score += 0.5
                if kw_lower in field_comment_lower:
                    score += 0.3

        for enum_name in table.enums.keys():
            if any(kw.lower() in enum_name.lower() for kw in keywords):
                score += 1

        return score

    def get_table_enum_values(self, table_name: str) -> Dict[str, List[str]]:
        """获取指定表的枚举值"""
        modules = self.get_modules()

        for module in modules:
            for table in module.tables:
                if table.table_name.lower() == table_name.lower():
                    result = {}
                    for enum_name, values in table.enums.items():
                        result[enum_name] = [v.get('value', '') for v in values]
                    return result

        return {}

    def get_table_info(self, table_name: str) -> Optional[TableInfo]:
        """获取指定表的详细信息"""
        modules = self.get_modules()

        for module in modules:
            for table in module.tables:
                if table.table_name.lower() == table_name.lower():
                    return table

        return None

    def get_business_glossary(self) -> Dict[str, str]:
        """获取业务术语词典"""
        glossary = {}

        modules = self.get_modules()

        for module in modules:
            for table in module.tables:
                for field in table.fields:
                    if field.comment and field.name not in ['id', 'created_at', 'updated_at']:
                        glossary[field.comment] = f"{table.table_name}.{field.name}"

                for enum_name, values in table.enums.items():
                    for val in values:
                        val_name = val.get('value', '')
                        val_desc = val.get('description', '')
                        if val_desc:
                            glossary[f"{val_name}"] = f"{table.table_name}.{enum_name}: {val_name}"

        return glossary


injector = DatabaseContextInjector()


def get_db_context_for_prompt(question: str, use_hybrid: bool = True) -> str:
    """
    获取用于注入到提示词的数据库上下文
    使用混合搜索（关键词 + 语义）提高匹配准确性
    """
    return injector.generate_relevant_context(question, use_hybrid=use_hybrid)


def get_full_db_context() -> str:
    """获取完整的数据库上下文"""
    return injector.generate_full_context()


def reload_db_context():
    """重新加载数据库上下文"""
    injector.reload()


class DatabaseContextTemplate:
    """数据库上下文模板生成器"""

    @staticmethod
    def generate_sql_enhancement(schema: str, question: str) -> str:
        """
        生成SQL生成的增强上下文
        将数据库描述信息与schema结合
        """
        db_context = get_db_context_for_prompt(question)

        enhancement = f"""
{schema}

{db_context}
"""
        return enhancement

    @staticmethod
    def generate_enum_hint(table_name: str, field_name: str) -> str:
        """
        生成枚举值提示
        用于帮助模型理解字段的可能取值
        """
        enum_values = injector.get_table_enum_values(table_name)

        if field_name in enum_values:
            values = enum_values[field_name]
            if values:
                hint = f"\n注意: {table_name}.{field_name} 的可能取值包括: {', '.join(values)}"
                return hint

        return ""

    @staticmethod
    def generate_field_hint(table_name: str, field_name: str) -> str:
        """
        生成字段含义提示
        用于帮助模型理解字段的业务含义
        """
        table_info = injector.get_table_info(table_name)

        if table_info:
            for field in table_info.fields:
                if field.name.lower() == field_name.lower():
                    if field.comment:
                        return f"\n参考: {table_name}.{field_name} 表示{field.comment}"

        return ""

    @staticmethod
    def generate_join_hint(table1: str, table2: str) -> str:
        """
        生成关联查询提示
        用于帮助模型理解表之间的关联关系
        """
        modules = injector.get_modules()

        for module in modules:
            for table in module.tables:
                if table.table_name.lower() == table1.lower():
                    for fk in table.foreign_keys:
                        if fk.get('ref_table', '').lower() == table2.lower():
                            return f"\n参考: {table1} 通过字段 {fk.get('field')} 关联到 {table2}.{fk.get('ref_field')}"

        return ""


def enhance_sql_prompt_schema(schema: str, question: str) -> str:
    """
    增强SQL生成的schema上下文

    Args:
        schema: 原始schema字符串
        question: 用户问题

    Returns:
        增强后的schema字符串
    """
    return DatabaseContextTemplate.generate_sql_enhancement(schema, question)


def get_enum_hint_for_field(table_name: str, field_name: str) -> str:
    """
    获取字段的枚举值提示

    Args:
        table_name: 表名
        field_name: 字段名

    Returns:
        枚举值提示字符串
    """
    return DatabaseContextTemplate.generate_enum_hint(table_name, field_name)


def get_field_description(table_name: str, field_name: str) -> str:
    """
    获取字段的业务含义描述

    Args:
        table_name: 表名
        field_name: 字段名

    Returns:
        字段含义描述字符串
    """
    return DatabaseContextTemplate.generate_field_hint(table_name, field_name)


def get_join_hint(table1: str, table2: str) -> str:
    """
    获取表关联提示

    Args:
        table1: 表1名
        table2: 表2名

    Returns:
        关联提示字符串
    """
    return DatabaseContextTemplate.generate_join_hint(table1, table2)
