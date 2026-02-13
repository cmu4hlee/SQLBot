#!/usr/bin/env python3
"""
测试自然语言查询流程中的数据库上下文集成
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.db_context_integration import (
    get_db_context_for_prompt,
    is_db_context_available,
    get_db_context_stats
)
from apps.chat.models.chat_model import AiModelQuestion

print('='*70)
print('自然语言查询流程测试')
print('='*70)

# 1. 检查数据库上下文是否可用
print('\n1. 检查数据库上下文状态')
available = is_db_context_available()
print(f'   可用: {available}')

if available:
    stats = get_db_context_stats()
    print(f'   模块数: {stats.get("modules_count", 0)}')
    print(f'   表数: {stats.get("tables_count", 0)}')
    print(f'   枚举数: {stats.get("enums_count", 0)}')

# 2. 测试不同类型的查询
print('\n2. 测试不同类型的自然语言查询')
print('-'*70)

test_cases = [
    {
        'question': '查询所有资产分类',
        'description': '测试资产分类表匹配',
        'expected_tables': ['asset_categories']
    },
    {
        'question': '统计资产状态分布',
        'description': '测试资产状态枚举提取',
        'expected_tables': ['assets'],
        'expected_enums': ['资产状态']
    },
    {
        'question': '查询盘点记录',
        'description': '测试盘点相关表匹配和枚举',
        'expected_tables': ['inventory_records', 'inventory_details'],
        'expected_enums': ['盘点类型', '盘点状态', '差异类型']
    },
    {
        'question': '维护工单列表',
        'description': '测试维护工单表匹配',
        'expected_tables': ['maintenance_workorders'],
        'expected_enums': ['优先级', '状态']
    },
    {
        'question': '查询验收申请',
        'description': '测试验收申请表匹配',
        'expected_tables': ['acceptance_applications'],
        'expected_enums': ['申请状态', '文件类型', '签字类型']
    },
    {
        'question': '不良事件记录',
        'description': '测试不良事件表匹配',
        'expected_tables': ['adverse_reaction_records'],
        'expected_enums': ['报告类型', '严重程度', '事件后果', '事件等级', '处理状态']
    },
    {
        'question': '计量检测结果',
        'description': '测试计量管理表匹配',
        'expected_tables': ['metrology_records'],
        'expected_enums': ['计量类型', '计量结果', '状态']
    },
    {
        'question': '质控管理情况',
        'description': '测试质控管理表匹配',
        'expected_tables': ['quality_control_records'],
        'expected_enums': ['质控类型', '质控结果', '状态']
    }
]

results = []
for i, test_case in enumerate(test_cases, 1):
    question = test_case['question']
    context = get_db_context_for_prompt(question)
    
    result = {
        'question': question,
        'description': test_case['description'],
        'context_length': len(context),
        'has_context': len(context) > 0,
        'matched_tables': [],
        'matched_enums': []
    }
    
    if context:
        # 检查是否匹配到预期的表
        for table in test_case.get('expected_tables', []):
            if table in context:
                result['matched_tables'].append(table)
        
        # 检查是否匹配到预期的枚举
        for enum in test_case.get('expected_enums', []):
            if enum in context:
                result['matched_enums'].append(enum)
    
    results.append(result)
    
    print(f'\n   [{i}] {question}')
    print(f'       描述: {test_case["description"]}')
    print(f'       上下文长度: {len(context)} 字符')
    print(f'       匹配到表: {", ".join(result["matched_tables"]) if result["matched_tables"] else "无"}')
    print(f'       匹配到枚举: {", ".join(result["matched_enums"]) if result["matched_enums"] else "无"}')

# 3. 统计结果
print('\n' + '='*70)
print('3. 测试结果统计')
print('='*70)

total = len(results)
with_context = sum(1 for r in results if r['has_context'])
with_tables = sum(1 for r in results if r['matched_tables'])
with_enums = sum(1 for r in results if r['matched_enums'])

print(f'\n   总测试数: {total}')
print(f'   有上下文: {with_context} ({with_context/total*100:.1f}%)')
print(f'   匹配到表: {with_tables} ({with_tables/total*100:.1f}%)')
print(f'   匹配到枚举: {with_enums} ({with_enums/total*100:.1f}%)')

# 4. 展示一个完整的上下文示例
print('\n' + '='*70)
print('4. 完整上下文示例（盘点记录）')
print('='*70)

example_question = '查询盘点记录'
example_context = get_db_context_for_prompt(example_question)
if example_context:
    print(example_context)

# 5. 测试 AiModelQuestion 类的 db_context 字段
print('\n' + '='*70)
print('5. 测试 AiModelQuestion 集成')
print('='*70)

question_obj = AiModelQuestion(question='测试问题')
question_obj.db_context = get_db_context_for_prompt('盘点')
print(f'   问题: 测试问题')
print(f'   db_context 长度: {len(question_obj.db_context)} 字符')
print(f'   db_context 已设置: {"是" if question_obj.db_context else "否"}')

print('\n' + '='*70)
print('测试完成!')
print('='*70)
