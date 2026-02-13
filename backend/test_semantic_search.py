#!/usr/bin/env python3
"""
测试语义向量搜索功能
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.db_description_parser import DatabaseDescriptionParser
from apps.datasource.embedding.semantic_search import (
    SemanticSearchEngine,
    get_semantic_search_engine,
    build_semantic_index
)
from apps.datasource.embedding.db_context_injector import DatabaseContextInjector

print('='*70)
print('测试语义向量搜索功能')
print('='*70)

# 1. 解析数据库描述文件
print('\n1. 解析数据库描述文件...')
parser = DatabaseDescriptionParser('/opt/sqlbot/app/数据库描述.md')
modules = parser.parse()
print(f'   解析完成: {len(modules)} 个模块')

# 2. 构建语义向量索引
print('\n2. 构建语义向量索引...')
engine = get_semantic_search_engine()
success = engine.build_index(modules, force=True)
if success:
    stats = engine.get_stats()
    print(f'   ✅ 索引构建成功')
    print(f'   - 表数量: {stats["table_count"]}')
    print(f'   - 字段数量: {stats["total_fields"]}')
    print(f'   - 枚举数量: {stats["total_enums"]}')
else:
    print(f'   ❌ 索引构建失败')
    sys.exit(1)

# 3. 测试语义搜索
print('\n3. 测试语义搜索...')
print('-'*70)

test_questions = [
    "查询盘点记录",
    "资产状态统计",
    "维修工单",
    "验收申请情况",
    "设备故障",
    "计量检测结果",
    "质控管理",
    "不良事件报告"
]

for question in test_questions:
    print(f'\n问题: "{question}"')
    results = engine.search(question, top_k=3)
    
    for i, result in enumerate(results[:2], 1):
        print(f'   [{i}] {result.table_name} ({result.table_comment})')
        print(f'       相似度: {result.relevance_score:.4f}')
        print(f'       匹配类型: {result.match_type}')
        if result.matched_fields:
            print(f'       匹配字段: {", ".join(result.matched_fields[:3])}')
        if result.matched_enums:
            print(f'       匹配枚举: {", ".join(result.matched_enums[:3])}')

# 4. 测试混合搜索
print('\n' + '='*70)
print('4. 测试混合搜索（关键词 + 语义）')
print('-'*70)

injector = DatabaseContextInjector()

for question in test_questions[:5]:
    print(f'\n问题: "{question}"')
    context = injector.generate_relevant_context(question, use_hybrid=True)
    print(f'   上下文长度: {len(context)} 字符')
    if context:
        print(f'   上下文预览:\n{context[:300]}...')

# 5. 对比测试
print('\n' + '='*70)
print('5. 对比测试：关键词搜索 vs 混合搜索')
print('-'*70)

comparison_question = "设备坏了"
print(f'\n问题: "{comparison_question}"')

print('\n关键词搜索结果:')
kw_context = injector.generate_relevant_context(comparison_question, use_hybrid=False)
print(f'   长度: {len(kw_context)} 字符')

print('\n混合搜索结果:')
hybrid_context = injector.generate_relevant_context(comparison_question, use_hybrid=True)
print(f'   长度: {len(hybrid_context)} 字符')

if kw_context != hybrid_context:
    print('\n✅ 混合搜索与关键词搜索结果不同，语义增强生效！')
else:
    print('\n⚠️ 两种搜索结果相同，可能需要调整阈值')

print('\n' + '='*70)
print('测试完成!')
print('='*70)
