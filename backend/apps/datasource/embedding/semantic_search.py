"""
语义向量搜索模块
基于Embedding模型实现语义级别的表和字段检索
支持与自我学习引擎的集成
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import threading
import pickle
import os
import time
from datetime import datetime

from apps.ai_model.embedding import EmbeddingModelCache
from common.core.config import settings
from common.utils.utils import SQLBotLogUtil


@dataclass
class TableVector:
    """表向量信息"""
    table_name: str
    table_comment: str
    module_name: str
    embedding: np.ndarray
    field_embeddings: List[Dict[str, Any]] = field(default_factory=list)
    enum_embeddings: Dict[str, np.ndarray] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """搜索结果"""
    table_name: str
    table_comment: str
    module_name: str
    relevance_score: float
    match_type: str
    matched_fields: List[str] = field(default_factory=list)
    matched_enums: List[str] = field(default_factory=list)


class SemanticSearchEngine:
    """
    语义向量搜索引擎
    为数据库表和字段构建向量索引，支持语义级别的相似度搜索
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.embedding_model = None
        self.table_vectors: Dict[str, TableVector] = {}
        self.index_built = False
        self.last_build_time = None
        self._embedding_lock = threading.Lock()

        self._load_index()

    def _get_embedding_model(self):
        """获取Embedding模型（懒加载）"""
        if self.embedding_model is None:
            with self._embedding_lock:
                if self.embedding_model is None:
                    try:
                        self.embedding_model = EmbeddingModelCache.get_model()
                        SQLBotLogUtil.info("Embedding模型加载成功")
                    except Exception as e:
                        SQLBotLogUtil.warning(f"Embedding模型加载失败: {e}")
                        return None
        return self.embedding_model

    def _encode_text(self, text: str) -> Optional[np.ndarray]:
        """将文本编码为向量"""
        model = self._get_embedding_model()
        if model is None:
            return None
        try:
            embedding = model.embed_query(text)
            return np.array(embedding)
        except Exception as e:
            SQLBotLogUtil.warning(f"文本编码失败: {e}")
            return None

    def _encode_texts(self, texts: List[str]) -> Optional[np.ndarray]:
        """批量编码文本"""
        model = self._get_embedding_model()
        if model is None:
            return None
        try:
            embeddings = model.embed_documents(texts)
            return np.array(embeddings)
        except Exception as e:
            SQLBotLogUtil.warning(f"批量文本编码失败: {e}")
            return None

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def build_index(self, modules: List[Any], force: bool = False) -> bool:
        """
        构建向量索引

        Args:
            modules: 解析后的模块列表
            force: 是否强制重建索引

        Returns:
            是否构建成功
        """
        if self.index_built and not force:
            SQLBotLogUtil.info("索引已存在，跳过构建")
            return True

        model = self._get_embedding_model()
        if model is None:
            SQLBotLogUtil.warning("无法构建索引：Embedding模型不可用")
            return False

        SQLBotLogUtil.info("开始构建语义向量索引...")

        try:
            self.table_vectors = {}

            for module in modules:
                module_name = module.module_name

                for table in module.tables:
                    table_name = table.table_name
                    table_comment = table.table_comment

                    table_text = self._build_table_text(table)

                    embedding = self._encode_text(table_text)
                    if embedding is None:
                        continue

                    field_embeddings = []
                    enum_embeddings = {}

                    for field in table.fields:
                        if field.name in ['id', 'created_at', 'updated_at', 'tenant_id']:
                            continue
                        field_text = f"{field.name} {field.comment} {field.field_type}"
                        field_embedding = self._encode_text(field_text)
                        if field_embedding is not None:
                            field_embeddings.append({
                                'name': field.name,
                                'comment': field.comment,
                                'embedding': field_embedding
                            })

                    for enum_name, enum_values in table.enums.items():
                        enum_text = enum_name
                        for val in enum_values:
                            enum_text += f" {val.get('value', '')} {val.get('description', '')}"
                        enum_embedding = self._encode_text(enum_text)
                        if enum_embedding is not None:
                            enum_embeddings[enum_name] = enum_embedding

                    keywords = self._extract_keywords(f"{table_comment} {table_name}")
                    for field in table.fields:
                        if field.comment:
                            keywords.extend(self._extract_keywords(field.comment))

                    table_vector = TableVector(
                        table_name=table_name,
                        table_comment=table_comment,
                        module_name=module_name,
                        embedding=embedding,
                        field_embeddings=field_embeddings,
                        enum_embeddings=enum_embeddings,
                        keywords=list(set(keywords))
                    )

                    self.table_vectors[table_name] = table_vector

            self.index_built = True
            self.last_build_time = datetime.now()

            self._save_index()

            SQLBotLogUtil.info(
                f"语义向量索引构建完成: {len(self.table_vectors)} 个表, "
                f"{sum(len(t.field_embeddings) for t in self.table_vectors.values())} 个字段"
            )

            return True

        except Exception as e:
            SQLBotLogUtil.error(f"构建索引失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _build_table_text(self, table: Any) -> str:
        """构建表的描述文本"""
        parts = [table.table_comment, table.table_name]

        for field in table.fields:
            if field.name in ['id', 'created_at', 'updated_at', 'tenant_id']:
                continue
            parts.append(f"{field.name} {field.comment}")

        for enum_name, enum_values in table.enums.items():
            parts.append(enum_name)
            for val in enum_values:
                parts.append(f"{val.get('value', '')} {val.get('description', '')}")

        return " ".join(parts)

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        import re
        text = re.sub(r'[，。！？、：；""''【】（）\(\)\[\]]', ' ', text)
        words = text.split()

        stopwords = {'的', '是', '在', '有', '和', '与', '或', '及', '等', '标识', '编号', '记录', '管理'}

        keywords = []
        for word in words:
            word = word.strip()
            if word and len(word) >= 2 and word not in stopwords:
                keywords.append(word)

        return keywords

    def search(
        self,
        question: str,
        top_k: int = 5,
        threshold: float = 0.3
    ) -> List[SearchResult]:
        """
        语义搜索

        Args:
            question: 用户问题
            top_k: 返回前K个结果
            threshold: 相似度阈值

        Returns:
            搜索结果列表
        """
        if not self.index_built:
            SQLBotLogUtil.warning("索引未构建，无法搜索")
            return []

        model = self._get_embedding_model()
        if model is None:
            return []

        try:
            question_embedding = self._encode_text(question)
            if question_embedding is None:
                return []

            results = []

            for table_name, table_vec in self.table_vectors.items():
                score = self._cosine_similarity(question_embedding, table_vec.embedding)

                matched_fields = []
                matched_enums = []

                for field_info in table_vec.field_embeddings:
                    field_score = self._cosine_similarity(
                        question_embedding,
                        field_info['embedding']
                    )
                    if field_score > threshold:
                        matched_fields.append(field_info['name'])

                for enum_name, enum_embedding in table_vec.enum_embeddings.items():
                    enum_score = self._cosine_similarity(question_embedding, enum_embedding)
                    if enum_score > threshold:
                        matched_enums.append(enum_name)

                if score > threshold or matched_fields or matched_enums:
                    match_type = "semantic"
                    if matched_fields:
                        match_type = "field"
                    if matched_enums:
                        match_type = "enum"

                    final_score = score
                    if matched_fields:
                        final_score = max(final_score, max(
                            self._cosine_similarity(question_embedding, f['embedding'])
                            for f in table_vec.field_embeddings
                            if f['name'] in matched_fields
                        ))
                    if matched_enums:
                        final_score = max(final_score, max(
                            self._cosine_similarity(question_embedding, e)
                            for k, e in table_vec.enum_embeddings.items()
                            if k in matched_enums
                        ))

                    results.append(SearchResult(
                        table_name=table_vec.table_name,
                        table_comment=table_vec.table_comment,
                        module_name=table_vec.module_name,
                        relevance_score=final_score,
                        match_type=match_type,
                        matched_fields=matched_fields,
                        matched_enums=matched_enums
                    ))

            results.sort(key=lambda x: x.relevance_score, reverse=True)
            return results[:top_k]

        except Exception as e:
            SQLBotLogUtil.error(f"搜索失败: {e}")
            return []

    def search_with_fusion(
        self,
        question: str,
        keyword_results: List[Dict[str, Any]],
        top_k: int = 5,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[SearchResult]:
        """
        融合搜索：结合语义搜索和关键词搜索结果

        Args:
            question: 用户问题
            keyword_results: 关键词搜索结果
            top_k: 返回前K个结果
            semantic_weight: 语义搜索权重
            keyword_weight: 关键词搜索权重

        Returns:
            融合后的搜索结果
        """
        semantic_results = self.search(question, top_k=top_k * 2)

        score_map: Dict[str, SearchResult] = {}

        for result in semantic_results:
            fused_score = result.relevance_score * semantic_weight
            score_map[result.table_name] = SearchResult(
                table_name=result.table_name,
                table_comment=result.table_comment,
                module_name=result.module_name,
                relevance_score=fused_score,
                match_type=result.match_type,
                matched_fields=result.matched_fields,
                matched_enums=result.matched_enums
            )

        for kr in keyword_results:
            table_name = kr.get('table_name', '')
            kw_score = kr.get('score', 0)

            if table_name in score_map:
                existing = score_map[table_name]
                existing.relevance_score = existing.relevance_score + kw_score * keyword_weight
                if 'field' in kr.get('match_type', ''):
                    existing.match_type = 'hybrid'
                if kr.get('matched_fields'):
                    existing.matched_fields = list(set(
                        existing.matched_fields + kr.get('matched_fields', [])
                    ))
            else:
                score_map[table_name] = SearchResult(
                    table_name=table_name,
                    table_comment=kr.get('table_comment', ''),
                    module_name=kr.get('module_name', ''),
                    relevance_score=kw_score * keyword_weight,
                    match_type=kr.get('match_type', 'keyword'),
                    matched_fields=kr.get('matched_fields', []),
                    matched_enums=kr.get('matched_enums', [])
                )

        results = list(score_map.values())
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results[:top_k]

    def _get_index_path(self) -> str:
        """获取索引文件路径"""
        import os
        # 优先使用环境变量（用于 Docker 持久化）
        if os.environ.get('VECTOR_INDEX_PATH'):
            index_dir = os.environ.get('VECTOR_INDEX_PATH')
        else:
            # 使用相对于项目根目录的路径
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            index_dir = os.path.join(current_dir, 'data', 'vector_index')
        
        # 如果是容器内路径，检查是否是挂载点
        if index_dir.startswith('/opt/sqlbot/data/'):
            mount_path = f'/Users/cjlee/Desktop/Project/SQLbot{index_dir.replace("/opt/sqlbot", "")}'
            if os.path.exists(mount_path) and os.path.ismount(mount_path):
                index_dir = mount_path
        
        os.makedirs(index_dir, exist_ok=True)
        return os.path.join(index_dir, "db_semantic_index.pkl")

    def _save_index(self):
        """保存索引到文件"""
        try:
            index_path = self._get_index_path()
            data = {
                'table_vectors': {},
                'last_build_time': self.last_build_time
            }

            for table_name, table_vec in self.table_vectors.items():
                data['table_vectors'][table_name] = {
                    'table_name': table_vec.table_name,
                    'table_comment': table_vec.table_comment,
                    'module_name': table_vec.module_name,
                    'embedding': table_vec.embedding.tolist() if table_vec.embedding is not None else None,
                    'field_embeddings': [
                        {
                            'name': f['name'],
                            'comment': f['comment'],
                            'embedding': f['embedding'].tolist() if f['embedding'] is not None else None
                        }
                        for f in table_vec.field_embeddings
                    ],
                    'enum_embeddings': {
                        k: v.tolist() if v is not None else None
                        for k, v in table_vec.enum_embeddings.items()
                    },
                    'keywords': table_vec.keywords
                }

            with open(index_path, 'wb') as f:
                pickle.dump(data, f)

            SQLBotLogUtil.info(f"索引已保存到: {index_path}")

        except Exception as e:
            SQLBotLogUtil.warning(f"保存索引失败: {e}")

    def _load_index(self):
        """从文件加载索引"""
        try:
            index_path = self._get_index_path()
            if not os.path.exists(index_path):
                return False

            with open(index_path, 'rb') as f:
                data = pickle.load(f)

            for table_name, table_data in data['table_vectors'].items():
                field_embeddings = []
                for f in table_data.get('field_embeddings', []):
                    if f['embedding'] is not None:
                        field_embeddings.append({
                            'name': f['name'],
                            'comment': f['comment'],
                            'embedding': np.array(f['embedding'])
                        })

                enum_embeddings = {
                    k: np.array(v) if v is not None else None
                    for k, v in table_data.get('enum_embeddings', {}).items()
                }

                self.table_vectors[table_name] = TableVector(
                    table_name=table_data['table_name'],
                    table_comment=table_data['table_comment'],
                    module_name=table_data['module_name'],
                    embedding=np.array(table_data['embedding']) if table_data['embedding'] is not None else None,
                    field_embeddings=field_embeddings,
                    enum_embeddings=enum_embeddings,
                    keywords=table_data.get('keywords', [])
                )

            self.index_built = len(self.table_vectors) > 0
            self.last_build_time = data.get('last_build_time')

            if self.index_built:
                SQLBotLogUtil.info(
                    f"索引已加载: {len(self.table_vectors)} 个表"
                )

            return self.index_built

        except Exception as e:
            SQLBotLogUtil.warning(f"加载索引失败: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        return {
            'index_built': self.index_built,
            'table_count': len(self.table_vectors),
            'total_fields': sum(len(t.field_embeddings) for t in self.table_vectors.values()),
            'total_enums': sum(len(t.enum_embeddings) for t in self.table_vectors.values()),
            'last_build_time': self.last_build_time.isoformat() if self.last_build_time else None
        }


semantic_search_engine = SemanticSearchEngine()


def get_semantic_search_engine() -> SemanticSearchEngine:
    """获取语义搜索引擎实例"""
    return semantic_search_engine


def build_semantic_index(modules: List[Any], force: bool = False) -> bool:
    """构建语义索引的便捷函数"""
    engine = get_semantic_search_engine()
    return engine.build_index(modules, force=force)


def semantic_search(question: str, top_k: int = 5) -> List[SearchResult]:
    """语义搜索的便捷函数"""
    engine = get_semantic_search_engine()
    return engine.search(question, top_k=top_k)


def hybrid_search(
    question: str,
    keyword_results: List[Dict[str, Any]],
    top_k: int = 5
) -> List[SearchResult]:
    """混合搜索的便捷函数"""
    engine = get_semantic_search_engine()
    return engine.search_with_fusion(question, keyword_results, top_k=top_k)
