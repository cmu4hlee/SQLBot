#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.db_context_integration import (
    get_db_context_for_prompt,
    is_db_context_available,
    get_db_context_stats
)

print('='*60)
print('测试数据库上下文集成模块')
print('='*60)

available = is_db_context_available()
print(f'1. 数据库上下文是否可用: {available}')

if available:
    stats = get_db_context_stats()
    print(f'\n2. 数据库上下文统计:')
    print(f'   模块数: {stats.get("modules_count", 0)}')
    print(f'   表数: {stats.get("tables_count", 0)}')
    print(f'   枚举数: {stats.get("enums_count", 0)}')

test_questions = [
    '查询资产状态统计',
    '查询资产信息',
    '资产分类',
    '盘点记录',
    '维护工单',
    '质控管理',
    '查询所有资产'
]

print(f'\n3. 测试不同问题:')
for question in test_questions:
    context = get_db_context_for_prompt(question)
    print(f'\n   问题: "{question}"')
    print(f'   上下文长度: {len(context)} 字符')
    if context:
        print(f'   上下文内容:\n{context[:400]}...')

print('\n' + '='*60)
print('测试完成!')
print('='*60)
