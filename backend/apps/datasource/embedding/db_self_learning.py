"""
数据库描述自我学习模块
根据数据库描述文件生成语义化的术语和训练数据，增强大模型的上下文理解能力
"""

import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict

from apps.terminology.models.terminology_model import TerminologyInfo
from apps.data_training.models.data_training_model import DataTrainingInfo
from apps.ai_model.embedding import EmbeddingModelCache
from common.core.config import settings
from common.utils.utils import SQLBotLogUtil


@dataclass
class GeneratedTerm:
    """生成的术语"""
    word: str
    other_words: List[str]
    description: str
    table_name: str
    field_name: Optional[str]
    enum_type: Optional[str]


@dataclass
class GeneratedTraining:
    """生成的训练数据"""
    question: str
    sql: str
    description: str
    table_name: str


class DatabaseSelfLearning:
    """数据库自我学习引擎"""

    def __init__(self, description_file_path: str, ds_id: Optional[int] = None):
        self.description_file_path = Path(description_file_path)
        self.ds_id = ds_id
        self.embedding_model = None

    def _get_embedding_model(self):
        """获取embedding模型"""
        if self.embedding_model is None:
            self.embedding_model = EmbeddingModelCache.get_model()
        return self.embedding_model

    def generate_terminology_from_fields(self, table_name: str, table_comment: str,
                                        fields: List[Dict], enums: Dict[str, List[Dict]]
                                        ) -> List[GeneratedTerm]:
        """根据字段生成术语"""
        terms = []

        # 生成表级术语
        term = GeneratedTerm(
            word=table_comment if table_comment else table_name,
            other_words=[table_name],
            description=f"对应数据表 {table_name}",
            table_name=table_name,
            field_name=None,
            enum_type=None
        )
        terms.append(term)

        # 生成字段级术语
        for field in fields:
            field_name = field.get('name', '')
            field_type = field.get('field_type', '')
            field_comment = field.get('comment', '')
            field_group = field.get('field_group', '')

            # 跳过ID、审计字段等
            if field_name in ['id', 'created_at', 'updated_at', 'created_by', 'updated_by', 'tenant_id']:
                continue

            # 生成同义词
            other_words = [field_name]
            if '_' in field_name:
                camel_case = ''.join([w.capitalize() for w in field_name.split('_')])
                other_words.append(camel_case)
                other_words.append(field_name.replace('_', ''))

            # 常见中文术语映射
            term_mapping = {
                'name': ['名称', '名称字段'],
                'code': ['编码', '编号', '代码'],
                'status': ['状态', '状态值'],
                'type': ['类型', '类别'],
                'date': ['日期', '时间'],
                'amount': ['金额', '数量', '总额'],
                'price': ['价格', '单价'],
                'department': ['部门', '科室'],
                'person': ['人', '人员', '负责人'],
                'location': ['位置', '地点'],
                'remark': ['备注', '说明'],
            }

            if field_name in term_mapping:
                other_words.extend(term_mapping[field_name])

            # 生成描述
            if field_comment:
                description = f"对应 {table_name}.{field_name}"
                if field_group:
                    description += f"，属于'{field_group}'分组"
                description += f"，类型为{field_type}"
            else:
                description = f"对应 {table_name}.{field_name}，类型为{field_type}"

            term = GeneratedTerm(
                word=field_comment if field_comment else field_name,
                other_words=list(set(other_words)),
                description=description,
                table_name=table_name,
                field_name=field_name,
                enum_type=None
            )
            terms.append(term)

        # 生成枚举术语
        for enum_type, values in enums.items():
            for enum_val in values:
                value = enum_val.get('value', '')
                value_desc = enum_val.get('description', '')

                if value and value not in ['NULL', '-', '']:
                    other_words = [value]
                    if ' ' in value:
                        other_words.extend(value.split())

                    term = GeneratedTerm(
                        word=f"{table_comment}:{value}" if table_comment else value,
                        other_words=other_words,
                        description=f"{table_name}.{enum_type}枚举值：{value} - {value_desc}" if value_desc else f"{table_name}.{enum_type}枚举值：{value}",
                        table_name=table_name,
                        field_name=None,
                        enum_type=enum_type
                    )
                    terms.append(term)

        return terms

    def generate_training_from_modules(self, modules: List[Dict]) -> List[GeneratedTraining]:
        """根据模块生成训练数据"""
        trainings = []

        for module in modules:
            module_name = module.get('module_name', '')
            module_desc = module.get('module_description', '')
            tables = module.get('tables', [])

            for table in tables:
                table_name = table.get('table_name', '')
                table_comment = table.get('table_comment', '')
                fields = table.get('fields', [])
                enums = table.get('enums', {})

                # 生成基础查询
                trainings.extend(self._generate_basic_queries(table, table_comment))

                # 生成统计查询
                trainings.extend(self._generate_aggregate_queries(table, table_comment))

                # 生成条件查询
                trainings.extend(self._generate_conditional_queries(table, table_comment, enums))

                # 生成关联查询
                trainings.extend(self._generate_join_queries(tables, table, table_comment))

        return trainings

    def _generate_basic_queries(self, table: Dict, table_comment: str) -> List[GeneratedTraining]:
        """生成基础查询"""
        queries = []
        table_name = table.get('table_name', '')
        fields = table.get('fields', [])

        # 获取常用字段
        name_field = None
        status_field = None
        date_field = None
        amount_field = None

        for field in fields:
            fname = field.get('name', '')
            if fname in ['name', 'asset_name', 'title']:
                name_field = fname
            elif fname == 'status':
                status_field = fname
            elif 'date' in fname.lower() or 'time' in fname.lower():
                if not date_field:
                    date_field = fname
            elif 'amount' in fname.lower() or 'price' in fname.lower() or 'cost' in fname.lower():
                if not amount_field:
                    amount_field = fname

        # 生成查询所有记录
        if name_field:
            question = f"查询所有{table_comment}列表"
            sql = f"SELECT * FROM {table_name} ORDER BY {name_field} LIMIT 1000;"
            queries.append(GeneratedTraining(question, sql, f"查询{table_comment}基础信息", table_name))
        else:
            question = f"查询所有{table_comment}"
            sql = f"SELECT * FROM {table_name} ORDER BY id LIMIT 1000;"
            queries.append(GeneratedTraining(question, sql, f"查询{table_comment}基础信息", table_name))

        # 生成带状态的查询
        if status_field:
            for status_val in ['进行中', '已完成', '待处理', '已通过']:
                question = f"查询状态为'{status_val}'的{table_comment}"
                sql = f"SELECT * FROM {table_name} WHERE {status_field} = '{status_val}' ORDER BY id LIMIT 1000;"
                queries.append(GeneratedTraining(question, sql, f"查询状态为{status_val}的{table_comment}", table_name))

        return queries

    def _generate_aggregate_queries(self, table: Dict, table_comment: str) -> List[GeneratedTraining]:
        """生成统计查询"""
        queries = []
        table_name = table.get('table_name', '')
        fields = table.get('fields', [])

        # 查找可以分组统计的字段
        group_fields = []
        for field in fields:
            fname = field.get('name', '')
            ftype = field.get('field_type', '')
            if fname in ['status', 'type', 'category', 'department']:
                group_fields.append(fname)

        amount_field = None
        for field in fields:
            fname = field.get('name', '')
            if 'amount' in fname.lower() or 'price' in fname.lower():
                amount_field = fname
                break

        for group_field in group_fields:
            question = f"按{group_field}统计{table_comment}数量"
            sql = f"SELECT {group_field}, COUNT(*) AS count FROM {table_name} GROUP BY {group_field} ORDER BY count DESC LIMIT 1000;"
            queries.append(GeneratedTraining(question, sql, f"按{group_field}分组统计{table_comment}", table_name))

            if amount_field:
                question = f"按{group_field}统计{table_comment}的{amount_field}总额"
                sql = f"SELECT {group_field}, COUNT(*) AS count, SUM({amount_field}) AS total_{amount_field} FROM {table_name} GROUP BY {group_field} ORDER BY total_{amount_field} DESC LIMIT 1000;"
                queries.append(GeneratedTraining(question, sql, f"按{group_field}分组统计金额", table_name))

        # 统计总数
        question = f"统计{table_comment}总数"
        sql = f"SELECT COUNT(*) AS total FROM {table_name};"
        queries.append(GeneratedTraining(question, sql, f"统计{table_comment}总数", table_name))

        return queries

    def _generate_conditional_queries(self, table: Dict, table_comment: str, enums: Dict) -> List[GeneratedTraining]:
        """生成条件查询"""
        queries = []
        table_name = table.get('table_name', '')
        fields = table.get('fields', [])

        # 生成按日期范围查询
        date_field = None
        for field in fields:
            fname = field.get('name', '')
            if 'date' in fname.lower() or 'time' in fname.lower():
                if 'created' not in fname and 'updated' not in fname:
                    date_field = fname
                    break

        if date_field:
            question = f"查询最近30天的{table_comment}"
            sql = f"SELECT * FROM {table_name} WHERE {date_field} >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) ORDER BY {date_field} DESC LIMIT 1000;"
            queries.append(GeneratedTraining(question, sql, f"查询最近30天的{table_comment}", table_name))

        # 生成按枚举值查询
        for enum_type, values in enums.items():
            for val in values[:3]:  # 限制数量
                value = val.get('value', '')
                if value and value not in ['NULL', '-', '']:
                    question = f"查询{enum_type}为'{value}'的{table_comment}"
                    sql = f"SELECT * FROM {table_name} WHERE {enum_type} = '{value}' ORDER BY id LIMIT 1000;"
                    queries.append(GeneratedTraining(question, sql, f"查询特定{enum_type}的{table_comment}", table_name))

        return queries

    def _generate_join_queries(self, all_tables: List[Dict], current_table: Dict,
                               table_comment: str) -> List[GeneratedTraining]:
        """生成关联查询"""
        queries = []
        table_name = current_table.get('table_name', '')
        foreign_keys = current_table.get('foreign_keys', [])

        for fk in foreign_keys:
            ref_table = fk.get('ref_table', '')
            ref_field = fk.get('ref_field', '')

            # 查找被引用表的信息
            ref_table_info = None
            for t in all_tables:
                if t.get('table_name') == ref_table:
                    ref_table_info = t
                    break

            if ref_table_info:
                ref_comment = ref_table_info.get('table_comment', '')

                # 生成关联查询
                question = f"查询关联{ref_comment}的{table_comment}"
                sql = f"""
SELECT t.*, r.* FROM {table_name} t
JOIN {ref_table} r ON t.{fk.get('field')} = r.{ref_field}
ORDER BY t.id LIMIT 1000;
                """.strip()
                queries.append(GeneratedTraining(question, sql, f"{table_comment}关联{ref_comment}查询", table_name))

        return queries

    def generate_context_summary(self, modules: List[Dict]) -> str:
        """生成数据库上下文摘要，用于提供给大模型"""
        summary_parts = ["# 资产管理系统(ZCGL)数据库上下文信息"]

        for module in modules:
            module_name = module.get('module_name', '')
            module_desc = module.get('module_description', '')
            tables = module.get('tables', [])

            summary_parts.append(f"\n## {module_name}")
            summary_parts.append(f"功能: {module_desc}")
            summary_parts.append("\n### 核心表结构:")

            for table in tables:
                table_name = table.get('table_name', '')
                table_comment = table.get('table_comment', '')
                fields = table.get('fields', [])
                enums = table.get('enums', {})

                summary_parts.append(f"\n#### {table_name} ({table_comment})")

                # 关键字段
                key_fields = [f for f in fields if f.get('comment') and f.get('comment') != '']
                if key_fields:
                    field_descs = []
                    for f in key_fields[:5]:
                        fname = f.get('name', '')
                        ftype = f.get('field_type', '')
                        fcomment = f.get('comment', '')
                        field_descs.append(f"{fname}({ftype}): {fcomment}")
                    summary_parts.append(f"主要字段: {'; '.join(field_descs)}")

                # 枚举字段
                if enums:
                    enum_descs = []
                    for enum_name, values in enums.items():
                        val_list = ', '.join([v.get('value', '') for v in values[:3]])
                        enum_descs.append(f"{enum_name}: {val_list}")
                    summary_parts.append(f"状态类型: {'; '.join(enum_descs)}")

                # 外键关系
                fks = table.get('foreign_keys', [])
                if fks:
                    fk_descs = [f"{fk.get('field')}->{fk.get('ref_table')}.{fk.get('ref_field')}" for fk in fks]
                    summary_parts.append(f"关联关系: {'; '.join(fk_descs)}")

        # 添加业务规则说明
        summary_parts.append("\n## 重要业务规则")
        summary_parts.append("- 所有业务表都包含租户隔离字段(tenant_id)")
        summary_parts.append("- 资产主表使用asset_code作为主要标识")
        summary_parts.append("- 资产状态包括: 在用、闲置、维修、报废、调配中")
        summary_parts.append("- 支持多级分类的树形结构设计")

        return '\n'.join(summary_parts)

    def create_terminology_info(self, term: GeneratedTerm, oid: int) -> TerminologyInfo:
        """将生成的术语转换为数据库模型"""
        return TerminologyInfo(
            word=term.word,
            other_words=term.other_words,
            description=term.description,
            specific_ds=self.ds_id is not None,
            datasource_ids=[self.ds_id] if self.ds_id else [],
            enabled=True
        )

    def create_training_info(self, training: GeneratedTraining, oid: int) -> DataTrainingInfo:
        """将生成的训练数据转换为数据库模型"""
        return DataTrainingInfo(
            question=training.question,
            description=training.sql,
            datasource=self.ds_id,
            enabled=True
        )

    async def learn_and_store(self, session, oid: int):
        """执行完整的学习流程并存储到数据库"""
        from apps.terminology.curd.terminology import create_terminology
        from apps.data_training.curd.data_training import create_training
        from .db_description_parser import DatabaseDescriptionParser

        SQLBotLogUtil.info("开始数据库自我学习...")

        parser = DatabaseDescriptionParser(str(self.description_file_path))
        modules = parser.parse()

        all_terms = []
        all_trainings = []

        # 生成术语
        for module in modules:
            for table in module.tables:
                terms = self.generate_terminology_from_fields(
                    table.table_name,
                    table.table_comment,
                    [{'name': f.name, 'field_type': f.field_type, 'comment': f.comment,
                      'field_group': f.field_group} for f in table.fields],
                    table.enums
                )
                all_terms.extend(terms)

        # 生成训练数据
        modules_dict = [{
            'module_name': m.module_name,
            'module_description': m.module_description,
            'tables': [{
                'table_name': t.table_name,
                'table_comment': t.table_comment,
                'fields': [{'name': f.name, 'field_type': f.field_type, 'comment': f.comment,
                            'field_group': f.field_group} for f in t.fields],
                'enums': t.enums,
                'foreign_keys': t.foreign_keys
            } for t in m.tables]
        } for m in modules]

        trainings = self.generate_training_from_modules(modules_dict)
        all_trainings.extend(trainings)

        # 存储术语
        term_count = 0
        for term in all_terms[:100]:  # 限制数量
            try:
                term_info = self.create_terminology_info(term, oid)
                create_terminology(session, term_info, oid, lambda k, **kw: k, skip_embedding=False)
                term_count += 1
            except Exception as e:
                SQLBotLogUtil.warning(f"跳过术语 {term.word}: {e}")

        # 存储训练数据
        train_count = 0
        for training in all_trainings[:50]:  # 限制数量
            try:
                train_info = self.create_training_info(training, oid)
                create_training(session, train_info, oid, lambda k, **kw: k, skip_embedding=False)
                train_count += 1
            except Exception as e:
                SQLBotLogUtil.warning(f"跳过训练数据: {e}")

        SQLBotLogUtil.info(f"数据库自我学习完成: 生成了 {term_count} 个术语和 {train_count} 条训练数据")

        return {
            'terms_count': term_count,
            'trainings_count': train_count
        }

    def get_prompt_context(self, question: str, modules: List[Dict]) -> str:
        """根据问题生成相关的上下文信息"""
        relevant_parts = ["# 相关数据库上下文"]

        # 简单的关键词匹配
        keywords = self._extract_keywords(question)

        for module in modules:
            relevance_score = 0
            module_name = module.get('module_name', '')
            module_desc = module.get('module_description', '')
            tables = module.get('tables', [])

            # 检查模块名和描述
            for kw in keywords:
                if kw.lower() in module_name.lower() or kw.lower() in module_desc.lower():
                    relevance_score += 2

            for table in tables:
                table_name = table.get('table_name', '')
                table_comment = table.get('table_comment', '')
                fields = table.get('fields', [])
                enums = table.get('enums', {})

                # 检查表名和注释
                for kw in keywords:
                    if kw.lower() in table_name.lower() or kw.lower() in table_comment.lower():
                        relevance_score += 1

                # 检查字段
                for field in fields:
                    fname = field.get('name', '')
                    fcomment = field.get('comment', '')
                    for kw in keywords:
                        if kw.lower() in fname.lower() or kw.lower() in fcomment.lower():
                            relevance_score += 0.5

                # 检查枚举
                for enum_name, values in enums.items():
                    for kw in keywords:
                        if kw.lower() in enum_name.lower():
                            relevance_score += 1
                        for val in values:
                            vvalue = val.get('value', '')
                            vdesc = val.get('description', '')
                            if kw.lower() in vvalue.lower() or kw.lower() in vdesc.lower():
                                relevance_score += 0.5

            if relevance_score > 0:
                relevant_parts.append(f"\n## {module_name} (相关性: {relevance_score})")
                for table in tables:
                    tname = table.get('table_name', '')
                    tcomment = table.get('table_comment', '')
                    relevant_parts.append(f"\n### {tname} ({tcomment})")

                    # 添加关键字段信息
                    key_fields = [f for f in table.get('fields', []) if f.get('comment')]
                    if key_fields[:3]:
                        field_info = ', '.join([f"{f.get('name')}: {f.get('comment')}" for f in key_fields[:3]])
                        relevant_parts.append(f"关键字段: {field_info}")

                    # 添加枚举信息
                    if table.get('enums'):
                        enum_info = ', '.join([f"{k}" for k in table.get('enums').keys()])
                        relevant_parts.append(f"状态类型: {enum_info}")

        return '\n'.join(relevant_parts) if len(relevant_parts) > 1 else ""

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 移除标点符号，分词
        text = re.sub(r'[，。！？、：；""''【】（）\(\)\[\]]', ' ', text)
        words = text.split()

        # 移除停用词
        stopwords = ['的', '是', '在', '有', '和', '与', '或', '及', '等', '查询', '统计', '获取', '查找', '请问', '我想', '请']
        keywords = [w for w in words if len(w) >= 2 and w not in stopwords]

        return keywords


async def generate_db_context_for_llm(question: str, modules: List[Dict]) -> str:
    """为LLM生成数据库上下文"""
    learner = DatabaseSelfLearning("")
    return learner.get_prompt_context(question, modules)
