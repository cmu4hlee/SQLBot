#!/usr/bin/env python3
"""
调试关键词匹配逻辑
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.db_context_injector import DatabaseContextInjector

# 创建新的注入器实例
injector = DatabaseContextInjector()
modules = injector.get_modules()

print('='*70)
print('调试关键词匹配逻辑')
print('='*70)

# 显示所有模块名和表名
print('\n1. 所有模块和表:')
for module in modules:
    print(f'   模块: {module.module_name}')
    for table in module.tables:
        print(f'      表: {table.table_name} ({table.table_comment})')

print('\n2. 关键词匹配测试:')
print('-'*70)

test_keywords = ['资产', '分类', '状态', '盘点', '工单', '验收', '不良', '事件', '计量', '质控']

for keyword in test_keywords:
    matches = []
    for module in modules:
        # 检查模块名
        if keyword.lower() in module.module_name.lower():
            matches.append(f"模块: {module.module_name}")
        
        for table in module.tables:
            # 检查表名
            if keyword.lower() in table.table_name.lower():
                matches.append(f"表名: {table.table_name}")
            # 检查表注释
            if keyword.lower() in table.table_comment.lower():
                matches.append(f"表注释: {table.table_comment} ({table.table_name})")
            # 检查字段
            for field in table.fields:
                if keyword.lower() in field.name.lower() or keyword.lower() in (field.comment or '').lower():
                    matches.append(f"字段: {table.table_name}.{field.name} ({field.comment})")
    
    if matches:
        print(f'\n   关键词 "{keyword}":')
        for match in matches[:5]:  # 只显示前5个
            print(f'      - {match}')
        if len(matches) > 5:
            print(f'      ... 还有 {len(matches) - 5} 个匹配')

print('\n' + '='*70)
print('调试完成!')
print('='*70)
