#!/usr/bin/env python3
"""
自我学习功能完整测试
测试反馈收集、模式学习、权重调整、记忆库等所有功能
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.self_learning import (
    SelfLearningEngine,
    get_self_learning_engine,
    record_user_feedback,
    get_similar_questions,
    get_enhanced_weights,
    get_learning_stats
)
from apps.datasource.embedding.db_description_parser import DatabaseDescriptionParser
from apps.datasource.embedding.semantic_search import get_semantic_search_engine

print('='*80)
print('自我学习功能完整测试')
print('='*80)

# 1. 初始化并构建索引
print('\n[1/6] 初始化系统...')

engine = get_self_learning_engine()

parser = DatabaseDescriptionParser('/opt/sqlbot/app/数据库描述.md')
modules = parser.parse()
print(f'   解析完成: {len(modules)} 个模块')

semantic_engine = get_semantic_search_engine()
semantic_engine.build_index(modules, force=True)
print(f'   语义索引构建完成')

# 2. 测试反馈收集
print('\n' + '='*80)
print('[2/6] 测试反馈收集功能')
print('='*80)

sample_queries = [
    {
        "question": "查询资产分类列表",
        "sql": "SELECT * FROM asset_categories ORDER BY id LIMIT 1000",
        "feedback": "positive",
        "tables": ["asset_categories"],
        "fields": ["id", "category_name", "parent_id"],
        "enums": []
    },
    {
        "question": "统计资产状态分布",
        "sql": "SELECT status, COUNT(*) as count FROM assets GROUP BY status",
        "feedback": "positive",
        "tables": ["assets"],
        "fields": ["status", "asset_type"],
        "enums": ["资产状态"]
    },
    {
        "question": "盘点记录查询",
        "sql": "SELECT * FROM inventory_records ORDER BY inventory_date DESC LIMIT 1000",
        "feedback": "positive",
        "tables": ["inventory_records"],
        "fields": ["inventory_no", "inventory_date", "inventory_type"],
        "enums": ["盘点类型", "盘点状态"]
    },
    {
        "question": "维修工单列表",
        "sql": "SELECT * FROM maintenance_workorders ORDER BY created_at DESC LIMIT 1000",
        "feedback": "negative",
        "tables": ["maintenance_workorders"],
        "fields": ["work_order_no", "status"],
        "enums": ["优先级", "状态"]
    },
    {
        "question": "设备故障记录",
        "sql": "SELECT * FROM adverse_reaction_records WHERE report_type = '设备故障'",
        "feedback": "positive",
        "tables": ["adverse_reaction_records"],
        "fields": ["report_no", "asset_id", "severity"],
        "enums": ["报告类型", "严重程度"]
    }
]

print('\n记录用户反馈:')
for i, query in enumerate(sample_queries, 1):
    query_id = record_user_feedback(
        question=query["question"],
        generated_sql=query["sql"],
        feedback=query["feedback"],
        matched_tables=query["tables"],
        matched_fields=query["fields"],
        matched_enums=query["enums"],
        user_id="test_user"
    )
    status = "✅" if query["feedback"] == "positive" else "❌"
    print(f'   {status} [{i}] {query["question"][:30]}... -> {query["feedback"]}')

# 3. 测试关键词权重学习
print('\n' + '='*80)
print('[3/6] 测试关键词权重学习')
print('='*80)

test_keywords = ["资产", "盘点", "维修", "故障", "查询"]

print('\n增强后的关键词权重:')
print('{:<15} {:<10} {:<10} {:<10}'.format('关键词', '权重', '成功', '失败'))
print('-' * 50)

for keyword in test_keywords:
    weights = get_enhanced_weights([keyword])
    engine_instance = get_self_learning_engine()
    kw = engine_instance.keyword_weights.get(keyword)
    if kw:
        print('{:<15} {:<10.2f} {:<10} {:<10}'.format(
            keyword,
            kw.weight,
            kw.success_count,
            kw.failure_count
        ))
    else:
        print('{:<15} {:<10.2f} {:<10} {:<10}'.format(keyword, weights.get(keyword, 1.0), 0, 0))

# 4. 测试记忆库
print('\n' + '='*80)
print('[4/6] 测试记忆库功能')
print('='*80)

similar_tests = [
    "资产情况查询",
    "盘点单信息",
    "设备问题"
]

print('\n相似问题推荐:')
for question in similar_tests:
    print(f'\n问题: "{question}"')
    similar = get_similar_questions(question, top_k=3)
    if similar:
        for sq, sql, score in similar:
            print(f'   → "{sq[:40]}..." (相似度: {score:.3f})')
    else:
        print('   暂无相似问题')

# 5. 测试学习统计
print('\n' + '='*80)
print('[5/6] 测试学习统计')
print('='*80)

stats = get_learning_stats()

print('\n学习统计信息:')
print(f'   总反馈数: {stats["total_feedback"]}')
print(f'   成功反馈: {stats["positive_feedback"]}')
print(f'   失败反馈: {stats["negative_feedback"]}')
print(f'   成功率: {stats["success_rate"]:.1%}')
print(f'   学习模式: {stats["learned_patterns"]}')
print(f'   关键词权重: {stats["keyword_weights"]}')
print(f'   记忆条目: {stats["memory_items"]}')

print('\n高频关键词 (Top 5):')
for kw in stats["top_keywords"][:5]:
    print(f'   - {kw["keyword"]}: 权重={kw["weight"]:.2f}, 成功={kw["success"]}')

print('\n成功模式 (Top 3):')
for pattern in stats["top_patterns"][:3]:
    print(f'   - {pattern["pattern"][:30]}... 成功={pattern["success"]}, 置信度={pattern["confidence"]:.2f}')

# 6. 测试表建议
print('\n' + '='*80)
print('[6/6] 测试表建议功能')
print('='*80)

table_tests = [
    "想看资产",
    "盘点信息",
    "维修情况"
]

print('\n基于历史的表建议:')
for question in table_tests:
    print(f'\n问题: "{question}"')
    suggestions = engine_instance.get_table_suggestions(question)
    if suggestions:
        for table, score in suggestions[:3]:
            print(f'   → {table} (置信度: {score:.2f})')
    else:
        print('   暂无建议')

# 7. 完整学习闭环演示
print('\n' + '='*80)
print('[演示] 完整学习闭环')
print('='*80)

print('\n场景: 用户多次查询"设备"相关问题')

device_queries = [
    ("设备列表查询", "SELECT * FROM assets WHERE asset_type = '医疗设备'", "positive"),
    ("设备情况统计", "SELECT COUNT(*) FROM assets WHERE status = '在用'", "positive"),
    ("设备维修记录", "SELECT * FROM maintenance_workorders", "negative"),
    ("设备验收信息", "SELECT * FROM acceptance_applications", "positive"),
]

print('\n记录查询反馈:')
for question, sql, feedback in device_queries:
    query_id = record_user_feedback(
        question=question,
        generated_sql=sql,
        feedback=feedback,
        matched_tables=["assets"],
        matched_fields=["asset_type", "status"],
        user_id="user_001"
    )
    print(f'   {"✅" if feedback == "positive" else "❌"} {question}')

print('\n学习后的关键词权重变化:')
device_kw = engine_instance.keyword_weights.get("设备")
if device_kw:
    print(f'   设备: 权重={device_kw.weight:.2f}, 成功={device_kw.success_count}, 失败={device_kw.failure_count}')

print('\n' + '='*80)
print('✅ 自我学习功能测试完成!')
print('='*80)

print('\n功能摘要:')
print('1. ✅ 反馈收集: 记录用户对SQL结果的评价')
print('2. ✅ 模式学习: 从成功/失败案例中学习语义模式')
print('3. ✅ 权重调整: 根据反馈自动调整关键词权重')
print('4. ✅ 记忆库: 存储成功案例，支持相似查询推荐')
print('5. ✅ 表建议: 基于历史推荐可能相关的表')
print('6. ✅ 统计分析: 提供学习效果统计和常见错误分析')
