#!/usr/bin/env python3
"""
直接测试关键词提取和匹配逻辑
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.db_context_injector import DatabaseContextInjector

# 创建新的注入器实例
injector = DatabaseContextInjector()

print('='*70)
print('直接测试关键词提取和匹配逻辑')
print('='*70)

# 测试问题
test_question = '查询盘点记录'

print(f'\n1. 测试问题: "{test_question}"')

# 提取关键词
keywords = injector._extract_keywords(test_question)
print(f'   提取的关键词: {keywords}')

# 获取模块
modules = injector.get_modules()
print(f'   模块数: {len(modules)}')

# 计算每个模块的相关性
print('\n2. 模块相关性计算:')
for module in modules:
    score = injector._calculate_relevance(module, keywords)
    print(f'   模块 "{module.module_name}": 分数={score}')

# 找到相关性最高的模块
print('\n3. 按相关性排序的模块:')
module_scores = []
for module in modules:
    score = injector._calculate_relevance(module, keywords)
    module_scores.append((score, module))

module_scores.sort(key=lambda x: x[0], reverse=True)

for score, module in module_scores[:5]:
    print(f'   分数={score}: {module.module_name}')

# 测试第一个模块中的表
print('\n4. 第一个模块中表的相关性:')
first_module = module_scores[0][1]
for table in first_module.tables:
    table_score = injector._calculate_table_relevance(table, keywords)
    print(f'   分数={table_score}: {table.table_name} ({table.table_comment})')

print('\n' + '='*70)
print('测试完成!')
print('='*70)
