#!/usr/bin/env python3
"""
完整词汇测试（包含索引构建）
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.db_description_parser import DatabaseDescriptionParser
from apps.datasource.embedding.semantic_search import SemanticSearchEngine, get_semantic_search_engine
from apps.datasource.embedding.db_context_injector import DatabaseContextInjector

print('='*80)
print('语义向量搜索词汇完整测试')
print('='*80)

# 1. 解析数据库描述文件并构建索引
print('\n[1/2] 解析数据库描述文件并构建语义向量索引...')

parser = DatabaseDescriptionParser('/opt/sqlbot/app/数据库描述.md')
modules = parser.parse()
print(f'   解析完成: {len(modules)} 个模块')

engine = get_semantic_search_engine()
success = engine.build_index(modules, force=True)

if success:
    stats = engine.get_stats()
    print(f'   ✅ 索引构建成功')
    print(f'      - 表数量: {stats["table_count"]}')
    print(f'      - 字段数量: {stats["total_fields"]}')
    print(f'      - 枚举数量: {stats["total_enums"]}')
else:
    print(f'   ❌ 索引构建失败')
    sys.exit(1)

# 2. 运行测试
print('\n[2/2] 运行词汇测试...')

injector = DatabaseContextInjector()

# 2.1 关键词搜索测试
print('\n' + '='*80)
print('2.1 关键词搜索测试')
print('='*80)

keyword_tests = [
    ("资产", "资产主表"),
    ("盘点", "盘点记录表"),
    ("维修", "维护工单表"),
    ("验收", "验收申请表"),
    ("质控", "质控记录表"),
    ("计量", "计量记录表"),
    ("不良事件", "不良事件记录表"),
]

print('\n{:<15} {:<20} {:<10}'.format('查询词', '匹配表', '相似度'))
print('-' * 50)

for query, expected in keyword_tests:
    results = engine.search(query, top_k=3)
    if results:
        result = results[0]
        print('{:<15} {:<20} {:.4f}'.format(
            query, 
            result.table_name[:20], 
            result.relevance_score
        ))
    else:
        print('{:<15} {:<20} --'.format(query, '无匹配'))

# 2.2 语义搜索测试
print('\n' + '='*80)
print('2.2 语义搜索测试（口语化表达）')
print('='*80)

semantic_tests = [
    ("设备坏了", "设备故障"),
    ("东西在哪里", "资产位置"),
    ("什么时候买的", "采购日期"),
    ("谁负责的", "责任人"),
    ("修一下设备", "维修工单"),
    ("查一下有多少", "资产统计"),
]

print('\n{:<20} {:<20} {:<10} {:<15}'.format('口语表达', '期望匹配', '相似度', '匹配表'))
print('-' * 70)

for spoken, expected in semantic_tests:
    results = engine.search(spoken, top_k=3)
    if results:
        result = results[0]
        print('{:<20} {:<20} {:.4f} {:<15}'.format(
            spoken, 
            expected[:20], 
            result.relevance_score,
            result.table_name[:15]
        ))
    else:
        print('{:<20} {:<20} -- {:<15}'.format(spoken, expected[:20], '无匹配'))

# 2.3 混合搜索对比
print('\n' + '='*80)
print('2.3 混合搜索对比（关键词 vs 混合）')
print('='*80)

comparison_tests = [
    ("设备有问题", "设备故障"),
    ("盘点下资产", "盘点记录"),
    ("修一下设备", "维修工单"),
    ("资产出问题了", "资产问题"),
]

print('\n{:<20} {:<20} {:>10} {:>10} {:>10}'.format(
    '测试问题', '期望关键词', 'KW长度', '混合长度', '提升'
))
print('-' * 75)

for hybrid, keyword in comparison_tests:
    kw_context = injector.generate_relevant_context(hybrid, use_hybrid=False)
    hybrid_context = injector.generate_relevant_context(hybrid, use_hybrid=True)
    
    kw_len = len(kw_context)
    hybrid_len = len(hybrid_context)
    improvement = ((hybrid_len - kw_len) / kw_len * 100) if kw_len > 0 else 0
    
    print('{:<20} {:<20} {:>10} {:>10} {:>9.1f}%'.format(
        hybrid[:20], 
        keyword[:20], 
        kw_len,
        hybrid_len,
        improvement
    ))

# 2.4 枚举值测试
print('\n' + '='*80)
print('2.4 枚举值测试')
print('='*80)

enum_tests = [
    ("资产状态", ["在用", "闲置", "维修", "报废"]),
    ("盘点类型", ["全面盘点", "抽查盘点", "专项盘点"]),
    ("盘点状态", ["进行中", "已完成", "已取消"]),
    ("调配状态", ["待审批", "已批准", "已完成"]),
    ("优先级", ["紧急", "高", "中", "低"]),
]

print('\n{:<15} {:<35} {}'.format('枚举类型', '期望值', '匹配'))
print('-' * 70)

for enum_name, expected_values in enum_tests:
    context = injector.generate_relevant_context(enum_name, use_hybrid=True)
    
    matched = []
    for val in expected_values:
        if val in context:
            matched.append(val)
    
    status = '✅' if len(matched) > 0 else '❌'
    print('{:<15} {:<35} {} ({}/{})'.format(
        enum_name[:15],
        ', '.join(expected_values[:2]) + ('...' if len(expected_values) > 2 else ''),
        status,
        len(matched),
        len(expected_values)
    ))

# 2.5 完整上下文示例
print('\n' + '='*80)
print('2.5 完整上下文示例')
print('='*80)

example_questions = [
    "查询盘点记录",
    "资产状态统计",
    "维修工单",
]

for question in example_questions:
    print(f'\n问题: "{question}"')
    context = injector.generate_relevant_context(question, use_hybrid=True)
    
    print('-' * 60)
    lines = [l for l in context.strip().split('\n') if l.strip()]
    for line in lines[:8]:
        print(line[:75])
    if len(lines) > 8:
        print(f'... 还有 {len(lines) - 8} 行')

print('\n' + '='*80)
print('✅ 测试完成!')
print('='*80)
