"""
自我学习引擎
从用户反馈和查询历史中学习，不断增强语义理解能力

功能：
1. 反馈收集：记录用户对SQL结果的评价（👍/👎）
2. 模式学习：从成功的查询中学习语义模式
3. 权重调整：根据反馈自动调整关键词权重
4. 记忆库：存储成功案例，支持相似查询推荐
5. 自适应优化：持续改进搜索效果
"""

import json
import time
import hashlib
import pickle
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import threading
import numpy as np

from common.utils.utils import SQLBotLogUtil
from apps.ai_model.embedding import EmbeddingModelCache


@dataclass
class QueryFeedback:
    """查询反馈记录"""
    query_id: str
    question: str
    generated_sql: str
    feedback: str  # "positive", "negative"
    feedback_time: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    matched_tables: List[str] = field(default_factory=list)
    matched_fields: List[str] = field(default_factory=list)
    matched_enums: List[str] = field(default_factory=list)
    relevance_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class LearnedPattern:
    """学习到的语义模式"""
    pattern_id: str
    question_pattern: str
    matched_table: str
    matched_field: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    confidence: float = 0.0
    keywords: List[str] = field(default_factory=list)
    embeddings: Optional[List[float]] = None
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class KeywordWeight:
    """关键词权重"""
    keyword: str
    weight: float
    success_count: int = 0
    failure_count: int = 0
    table_associations: Dict[str, int] = field(default_factory=dict)


@dataclass
class MemoryItem:
    """记忆库条目"""
    question: str
    sql: str
    table: str
    keywords: List[str]
    embedding: List[float]
    success_count: int = 1
    last_used: datetime = field(default_factory=datetime.now)
    related_questions: List[str] = field(default_factory=list)


class SelfLearningEngine:
    """
    自我学习引擎
    从用户反馈中持续学习和优化
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

        self.feedback_history: List[QueryFeedback] = []
        self.learned_patterns: Dict[str, LearnedPattern] = {}
        self.keyword_weights: Dict[str, KeywordWeight] = {}
        self.memory_bank: Dict[str, MemoryItem] = {}
        self.query_stats: Dict[str, int] = defaultdict(int)
        self.table_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        self.embedding_model = None
        self._embedding_lock = threading.Lock()

        self._load_data()

    def _get_embedding_model(self):
        """获取Embedding模型"""
        if self.embedding_model is None:
            with self._embedding_lock:
                if self.embedding_model is None:
                    try:
                        self.embedding_model = EmbeddingModelCache.get_model()
                    except Exception as e:
                        SQLBotLogUtil.warning(f"无法加载Embedding模型: {e}")
                        return None
        return self.embedding_model

    def _get_data_path(self) -> str:
        """获取数据存储路径"""
        import os
        # 使用相对于项目根目录的路径
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        data_dir = os.path.join(current_dir, 'data', 'self_learning')
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _get_file_path(self, name: str) -> str:
        """获取数据文件路径"""
        return os.path.join(self._get_data_path(), f"{name}.pkl")

    def _load_data(self):
        """加载历史数据"""
        try:
            files = ['feedback', 'patterns', 'keywords', 'memory']
            for name in files:
                filepath = self._get_file_path(name)
                if os.path.exists(filepath):
                    with open(filepath, 'rb') as f:
                        data = pickle.load(f)
                    if name == 'feedback':
                        self.feedback_history = data
                    elif name == 'patterns':
                        self.learned_patterns = data
                    elif name == 'keywords':
                        self.keyword_weights = data
                    elif name == 'memory':
                        self.memory_bank = data

            SQLBotLogUtil.info(f"自我学习数据加载完成: "
                             f"反馈{len(self.feedback_history)}, "
                             f"模式{len(self.learned_patterns)}, "
                             f"关键词{len(self.keyword_weights)}, "
                             f"记忆{len(self.memory_bank)}")
        except Exception as e:
            SQLBotLogUtil.warning(f"加载自我学习数据失败: {e}")

    def _save_data(self):
        """保存数据"""
        try:
            for name, data in [
                ('feedback', self.feedback_history),
                ('patterns', self.learned_patterns),
                ('keywords', self.keyword_weights),
                ('memory', self.memory_bank)
            ]:
                filepath = self._get_file_path(name)
                with open(filepath, 'wb') as f:
                    pickle.dump(data, f)
        except Exception as e:
            SQLBotLogUtil.warning(f"保存自我学习数据失败: {e}")

    def record_feedback(
        self,
        question: str,
        generated_sql: str,
        feedback: str,
        matched_tables: List[str],
        matched_fields: List[str] = None,
        matched_enums: List[str] = None,
        relevance_scores: Dict[str, float] = None,
        user_id: str = None,
        session_id: str = None
    ) -> str:
        """
        记录用户反馈

        Args:
            question: 用户问题
            generated_sql: 生成的SQL
            feedback: 反馈类型 ("positive" 或 "negative")
            matched_tables: 匹配到的表
            matched_fields: 匹配到的字段
            matched_enums: 匹配到的枚举
            relevance_scores: 各表的相似度分数
            user_id: 用户ID
            session_id: 会话ID

        Returns:
            query_id: 反馈记录ID
        """
        query_id = hashlib.md5(f"{question}{time.time()}".encode()).hexdigest()[:12]

        feedback_record = QueryFeedback(
            query_id=query_id,
            question=question,
            generated_sql=generated_sql,
            feedback=feedback,
            feedback_time=datetime.now(),
            user_id=user_id,
            session_id=session_id,
            matched_tables=matched_tables or [],
            matched_fields=matched_fields or [],
            matched_enums=matched_enums or [],
            relevance_scores=relevance_scores or {}
        )

        self.feedback_history.append(feedback_record)

        self._learn_from_feedback(feedback_record)

        self._save_data()

        SQLBotLogUtil.info(f"反馈已记录: {query_id} - {feedback}")

        return query_id

    def _learn_from_feedback(self, feedback: QueryFeedback):
        """从反馈中学习"""
        if feedback.feedback == "negative":
            self._learn_from_failure(feedback)
        else:
            self._learn_from_success(feedback)

    def _learn_from_success(self, feedback: QueryFeedback):
        """从成功案例中学习"""
        keywords = self._extract_keywords(feedback.question)

        for table in feedback.matched_tables:
            self.table_stats[table]['success'] += 1

            for keyword in keywords:
                if keyword not in self.keyword_weights:
                    self.keyword_weights[keyword] = KeywordWeight(
                        keyword=keyword,
                        weight=1.0
                    )

                kw = self.keyword_weights[keyword]
                kw.success_count += 1
                kw.weight = min(2.0, 1.0 + (kw.success_count - kw.failure_count) * 0.1)

                if table not in kw.table_associations:
                    kw.table_associations[table] = 0
                kw.table_associations[table] += 1

        pattern_key = self._create_pattern_key(feedback.matched_tables, feedback.matched_fields)
        if pattern_key not in self.learned_patterns:
            embedding = self._get_question_embedding(feedback.question)
            self.learned_patterns[pattern_key] = LearnedPattern(
                pattern_id=pattern_key,
                question_pattern=feedback.question[:100],
                matched_table=feedback.matched_tables[0] if feedback.matched_tables else "",
                success_count=1,
                keywords=keywords,
                embeddings=embedding.tolist() if embedding is not None else None
            )
        else:
            pattern = self.learned_patterns[pattern_key]
            pattern.success_count += 1
            pattern.confidence = pattern.success_count / (pattern.success_count + pattern.failure_count + 1)
            pattern.last_updated = datetime.now()

        self._add_to_memory(feedback)

    def _learn_from_failure(self, feedback: QueryFeedback):
        """从失败案例中学习"""
        keywords = self._extract_keywords(feedback.question)

        for table in feedback.matched_tables:
            self.table_stats[table]['failure'] += 1

            for keyword in keywords:
                if keyword not in self.keyword_weights:
                    self.keyword_weights[keyword] = KeywordWeight(
                        keyword=keyword,
                        weight=1.0
                    )

                kw = self.keyword_weights[keyword]
                kw.failure_count += 1
                kw.weight = max(0.1, 1.0 - (kw.failure_count - kw.success_count) * 0.1)

        pattern_key = self._create_pattern_key(feedback.matched_tables, feedback.matched_fields)
        if pattern_key in self.learned_patterns:
            pattern = self.learned_patterns[pattern_key]
            pattern.failure_count += 1
            pattern.confidence = pattern.success_count / (pattern.success_count + pattern.failure_count + 1)
            pattern.last_updated = datetime.now()

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        import re
        text = re.sub(r'[，。！？、：；""''【】（）\(\)\[\]]', ' ', text)
        words = text.split()

        stopwords = {'的', '是', '在', '有', '和', '查询', '统计', '获取', '请', '帮我'}

        keywords = []
        for word in words:
            word = word.strip()
            if word and len(word) >= 2 and word not in stopwords:
                keywords.append(word)

        return keywords

    def _create_pattern_key(self, tables: List[str], fields: List[str]) -> str:
        """创建模式键"""
        key_parts = sorted(set(tables + (fields or [])))
        return '|'.join(key_parts[:3])

    def _get_question_embedding(self, question: str) -> Optional[np.ndarray]:
        """获取问题的向量表示"""
        model = self._get_embedding_model()
        if model is None:
            return None
        try:
            embedding = model.embed_query(question)
            if isinstance(embedding, list):
                return np.array(embedding)
            return embedding
        except Exception:
            return None

    def _add_to_memory(self, feedback: QueryFeedback):
        """添加到记忆库"""
        keywords = self._extract_keywords(feedback.question)
        embedding = self._get_question_embedding(feedback.question)

        if not embedding is None:
            memory_id = hashlib.md5(feedback.question.encode()).hexdigest()[:16]

            self.memory_bank[memory_id] = MemoryItem(
                question=feedback.question,
                sql=feedback.generated_sql,
                table=feedback.matched_tables[0] if feedback.matched_tables else "",
                keywords=keywords,
                embedding=embedding.tolist(),
                success_count=1,
                last_used=datetime.now()
            )

            if len(self.memory_bank) > 1000:
                self._prune_memory()

    def _prune_memory(self):
        """清理低质量的记忆"""
        sorted_items = sorted(
            self.memory_bank.items(),
            key=lambda x: (x[1].success_count, x[1].last_used),
            reverse=True
        )
        self.memory_bank = dict(sorted_items[:1000])

    def get_enhanced_weights(self, keywords: List[str]) -> Dict[str, float]:
        """
        获取增强后的关键词权重

        Args:
            keywords: 原始关键词列表

        Returns:
            增强后的权重字典
        """
        enhanced = {}
        for keyword in keywords:
            if keyword in self.keyword_weights:
                kw = self.keyword_weights[keyword]
                enhanced[keyword] = kw.weight
            else:
                enhanced[keyword] = 1.0
        return enhanced

    def get_similar_questions(self, question: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        """
        获取相似的问题

        Args:
            question: 当前问题
            top_k: 返回数量

        Returns:
            (问题, SQL, 相似度) 列表
        """
        embedding = self._get_question_embedding(question)
        if embedding is None:
            return []

        results = []
        for memory_id, item in self.memory_bank.items():
            if item.embedding:
                item_embedding = np.array(item.embedding)
                similarity = np.dot(embedding, item_embedding) / (
                    np.linalg.norm(embedding) * np.linalg.norm(item_embedding) + 1e-8
                )
                results.append((item.question, item.sql, float(similarity)))

        results.sort(key=lambda x: x[2], reverse=True)
        return results[:top_k]

    def get_recommended_keywords(self, question: str) -> List[str]:
        """
        根据历史推荐关键词

        Args:
            question: 用户问题

        Returns:
            推荐关键词列表
        """
        keywords = self._extract_keywords(question)
        recommended = []

        for keyword in keywords:
            if keyword in self.keyword_weights:
                kw = self.keyword_weights[keyword]
                if kw.weight > 1.2:
                    recommended.append(f"{keyword}*")

        return recommended

    def get_table_suggestions(self, question: str) -> List[Tuple[str, float]]:
        """
        根据历史推荐可能相关的表

        Args:
            question: 用户问题

        Returns:
            (表名, 置信度) 列表
        """
        keywords = self._extract_keywords(question)
        table_scores: Dict[str, float] = defaultdict(float)

        for keyword in keywords:
            if keyword in self.keyword_weights:
                kw = self.keyword_weights[keyword]
                for table, count in kw.table_associations.items():
                    table_scores[table] += kw.weight * count

        results = sorted(table_scores.items(), key=lambda x: x[1], reverse=True)
        return results[:5]

    def get_learning_stats(self) -> Dict[str, Any]:
        """获取学习统计信息"""
        total_feedback = len(self.feedback_history)
        positive = sum(1 for f in self.feedback_history if f.feedback == "positive")
        negative = total_feedback - positive

        top_keywords = sorted(
            self.keyword_weights.items(),
            key=lambda x: x[1].weight,
            reverse=True
        )[:10]

        top_patterns = sorted(
            self.learned_patterns.items(),
            key=lambda x: x[1].success_count,
            reverse=True
        )[:5]

        return {
            "total_feedback": total_feedback,
            "positive_feedback": positive,
            "negative_feedback": negative,
            "success_rate": positive / total_feedback if total_feedback > 0 else 0,
            "learned_patterns": len(self.learned_patterns),
            "keyword_weights": len(self.keyword_weights),
            "memory_items": len(self.memory_bank),
            "top_keywords": [
                {"keyword": k, "weight": v.weight, "success": v.success_count}
                for k, v in top_keywords
            ],
            "top_patterns": [
                {
                    "pattern": pattern.question_pattern[:50],
                    "success": pattern.success_count,
                    "confidence": pattern.confidence
                }
                for _, pattern in top_patterns
            ]
        }

    def analyze_query_patterns(self, days: int = 7) -> Dict[str, Any]:
        """分析查询模式"""
        cutoff = datetime.now() - timedelta(days=days)

        recent_feedback = [
            f for f in self.feedback_history
            if f.feedback_time > cutoff
        ]

        if not recent_feedback:
            return {"message": "没有足够的反馈数据"}

        table_performance = {}
        for feedback in recent_feedback:
            for table in feedback.matched_tables:
                if table not in table_performance:
                    table_performance[table] = {"success": 0, "failure": 0}
                if feedback.feedback == "positive":
                    table_performance[table]["success"] += 1
                else:
                    table_performance[table]["failure"] += 1

        common_mistakes = []
        for feedback in recent_feedback:
            if feedback.feedback == "negative":
                keywords = self._extract_keywords(feedback.question)
                common_mistakes.append({
                    "question": feedback.question,
                    "matched_tables": feedback.matched_tables,
                    "keywords": keywords
                })

        return {
            "period_days": days,
            "total_queries": len(recent_feedback),
            "success_rate": sum(1 for f in recent_feedback if f.feedback == "positive") / len(recent_feedback),
            "table_performance": table_performance,
            "common_mistakes": common_mistakes[:5]
        }

    def reset_learning_data(self):
        """重置所有学习数据"""
        self.feedback_history = []
        self.learned_patterns = {}
        self.keyword_weights = {}
        self.memory_bank = {}
        self.table_stats = defaultdict(lambda: defaultdict(int))

        for name in ['feedback', 'patterns', 'keywords', 'memory']:
            filepath = self._get_file_path(name)
            if os.path.exists(filepath):
                os.remove(filepath)

        SQLBotLogUtil.info("自我学习数据已重置")


self_learning_engine = SelfLearningEngine()


def get_self_learning_engine() -> SelfLearningEngine:
    """获取自我学习引擎实例"""
    return self_learning_engine


def record_user_feedback(
    question: str,
    generated_sql: str,
    feedback: str,
    matched_tables: List[str],
    matched_fields: List[str] = None,
    matched_enums: List[str] = None,
    user_id: str = None
) -> str:
    """
    记录用户反馈的便捷函数

    Args:
        question: 用户问题
        generated_sql: 生成的SQL
        feedback: 反馈 ("positive" 或 "negative")
        matched_tables: 匹配到的表
        matched_fields: 匹配到的字段
        matched_enums: 匹配到的枚举
        user_id: 用户ID

    Returns:
        query_id: 反馈记录ID
    """
    engine = get_self_learning_engine()
    return engine.record_feedback(
        question=question,
        generated_sql=generated_sql,
        feedback=feedback,
        matched_tables=matched_tables,
        matched_fields=matched_fields,
        matched_enums=matched_enums,
        user_id=user_id
    )


def get_similar_questions(question: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
    """获取相似问题的便捷函数"""
    engine = get_self_learning_engine()
    return engine.get_similar_questions(question, top_k)


def get_enhanced_weights(keywords: List[str]) -> Dict[str, float]:
    """获取增强权重的便捷函数"""
    engine = get_self_learning_engine()
    return engine.get_enhanced_weights(keywords)


def get_learning_stats() -> Dict[str, Any]:
    """获取学习统计的便捷函数"""
    engine = get_self_learning_engine()
    return engine.get_learning_stats()
