#!/usr/bin/env python3
"""
分批执行自我学习测试
每次执行200次查询，可重复运行累积学习效果
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

import random
import time
from datetime import datetime
from typing import Dict, List

from apps.datasource.embedding.db_description_parser import DatabaseDescriptionParser
from apps.datasource.embedding.semantic_search import get_semantic_search_engine
from apps.datasource.embedding.self_learning import (
    get_self_learning_engine,
    record_user_feedback
)


def run_batch(batch_num: int, queries_per_batch: int = 200):
    """执行一批查询测试"""
    parser = DatabaseDescriptionParser('/opt/sqlbot/app/数据库描述.md')
    modules = parser.parse()
    semantic_engine = get_semantic_search_engine()
    learning_engine = get_self_learning_engine()

    if not semantic_engine.index_built:
        semantic_engine.build_index(modules, force=True)

    noun_keywords = {
        "资产": ["assets"], "盘点": ["inventory_records"], "维修": ["maintenance_workorders"],
        "验收": ["acceptance_applications"], "不良事件": ["adverse_reaction_records"],
        "质控": ["quality_control_records"], "计量": ["metrology_records"],
        "调配": ["transfer_records"], "报废": ["scrapped_records"],
        "日志": ["operation_logs"], "用户": ["users"], "告警": ["alert_records"]
    }

    actions = ["查询", "查看", "获取", "统计", "列出"]
    modifiers = ["", "列表", "信息", "情况", "状态", "统计", "记录"]

    print(f"\n{'='*60}")
    print(f"批次 {batch_num}: 执行 {queries_per_batch} 次查询")
    print(f"{'='*60}")

    success = 0
    failed = 0
    start_time = time.time()

    for i in range(queries_per_batch):
        noun, tables = random.choice(list(noun_keywords.items()))
        question = f"{random.choice(actions)}{noun}"

        results = semantic_engine.search(question, top_k=3)
        matched = [r.table_name for r in results[:3]]

        is_success = len(set(matched) & set(tables)) > 0

        if is_success:
            success += 1
            feedback = 'positive'
        else:
            failed += 1
            feedback = 'negative'

        record_user_feedback(
            question=question,
            generated_sql=f"SELECT * FROM {tables[0]} LIMIT 1000",
            feedback=feedback,
            matched_tables=matched
        )

        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{queries_per_batch} ({((i+1)/queries_per_batch)*100:.0f}%)")

    elapsed = time.time() - start_time
    total = success + failed

    stats = learning_engine.get_learning_stats()

    print(f"\n批次 {batch_num} 结果:")
    print(f"  成功: {success} ({success/total*100:.1f}%)")
    print(f"  失败: {failed} ({failed/total*100:.1f}%)")
    print(f"  耗时: {elapsed:.1f}秒")
    print(f"\n累计学习统计:")
    print(f"  模式数: {stats['learned_patterns']}")
    print(f"  关键词: {stats['keyword_weights']}")
    print(f"  记忆: {stats['memory_items']}")

    return {'success': success, 'failed': failed, 'elapsed': elapsed}


if __name__ == '__main__':
    if len(sys.argv) > 1:
        batch = int(sys.argv[1])
    else:
        batch = 1

    result = run_batch(batch, 200)

    print(f"\n{'='*60}")
    print("✅ 批次测试完成!")
    print(f"{'='*60}")
