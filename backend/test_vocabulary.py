#!/usr/bin/env python3
"""
语义向量搜索词汇测试
测试各种类型的词汇和短语
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.semantic_search import SemanticSearchEngine, get_semantic_search_engine
from apps.datasource.embedding.db_context_injector import DatabaseContextInjector

print('='*80)
print('语义向量搜索词汇测试')
print('='*80)

engine = get_semantic_search_engine()
injector = DatabaseContextInjector()

# 1. 同义词测试
print('\n' + '='*80)
print('1. 同义词测试')
print('='*80)

synonym_tests = [
    ("资产", ["资产", "设备", "物资"]),
    ("盘点", ["盘点", "清点", "盘库"]),
    ("维修", ["维修", "维护", "保养"]),
    ("报废", ["报废", "销毁", "处置"]),
    ("验收", ["验收", "接收", "检验"]),
    ("查询", ["查询", "查找", "获取"]),
    ("统计", ["统计", "计数", "汇总"]),
]

for word, synonyms in synonym_tests:
    print(f'\n词: "{word}"')
    results = engine.search(word, top_k=3)
    for result in results[:1]:
        print(f'   → 匹配: {result.table_name} ({result.table_comment})')
        print(f'     相似度: {result.relevance_score:.4f}')
    
    print(f'   同义词: {", ".join(synonyms)}')

# 2. 口语化表达测试
print('\n' + '='*80)
print('2. 口语化表达测试')
print('='*80)

colloquial_tests = [
    ("设备坏了", "设备故障"),
    ("资产出问题了", "资产问题"),
    ("东西在哪里", "资产位置"),
    ("查一下有多少", "资产统计"),
    ("什么时候买的", "采购日期"),
    ("谁负责的", "负责人"),
    ("能不能用", "资产状态"),
    ("有没有问题", "问题查询"),
]

for spoken, formal in colloquial_tests:
    print(f'\n口语: "{spoken}"')
    print(f'期望: 匹配到与 "{formal}" 相关的表')
    results = engine.search(spoken, top_k=3)
    for result in results[:2]:
        print(f'   → {result.table_name} ({result.table_comment})')
        print(f'     相似度: {result.relevance_score:.4f}')
        if result.matched_fields:
            print(f'     匹配字段: {", ".join(result.matched_fields[:3])}')

# 3. 描述性查询测试
print('\n' + '='*80)
print('3. 描述性查询测试')
print('='*80)

descriptive_tests = [
    ("需要盘点的资产", "盘点相关"),
    ("正在维修的设备", "维修状态"),
    ("已报废的物资", "报废资产"),
    ("待验收的设备", "待验收"),
    ("本月采购的资产", "采购查询"),
    ("各部门资产分布", "资产统计"),
    ("高价值的设备", "价值查询"),
    ("使用频率高的资产", "使用频率"),
]

for desc, intent in descriptive_tests:
    print(f'\n查询: "{desc}"')
    print(f'意图: {intent}')
    results = engine.search(desc, top_k=3)
    for result in results[:2]:
        print(f'   → {result.table_name} ({result.table_comment})')
        print(f'     相似度: {result.relevance_score:.4f}')

# 4. 混合搜索效果对比
print('\n' + '='*80)
print('4. 混合搜索效果对比')
print('='*80)

comparison_tests = [
    ("查资产情况", "查询资产状态"),
    ("设备有问题", "设备故障"),
    ("盘点下资产", "盘点记录"),
    ("修一下设备", "维修工单"),
]

for hybrid, keyword in comparison_tests:
    print(f'\n测试: "{hybrid}" vs "{keyword}"')
    
    kw_context = injector.generate_relevant_context(hybrid, use_hybrid=False)
    hybrid_context = injector.generate_relevant_context(hybrid, use_hybrid=True)
    
    kw_len = len(kw_context)
    hybrid_len = len(hybrid_context)
    
    print(f'   关键词搜索: {kw_len} 字符')
    print(f'   混合搜索: {hybrid_len} 字符')
    
    if hybrid_len > kw_len:
        improvement = ((hybrid_len - kw_len) / kw_len * 100) if kw_len > 0 else 0
        print(f'   提升: {improvement:.1f}%')
    else:
        print(f'   效果相同或更少')

# 5. 完整上下文生成测试
print('\n' + '='*80)
print('5. 完整上下文生成测试')
print('='*80)

context_tests = [
    "维修工单",
    "盘点记录",
    "验收申请",
    "资产分类",
    "质控管理",
    "计量检测",
    "不良事件",
]

for question in context_tests:
    print(f'\n问题: "{question}"')
    context = injector.generate_relevant_context(question, use_hybrid=True)
    lines = context.strip().split('\n')
    
    if lines:
        print(f'   生成 {len(lines)} 行上下文')
        for line in lines[:4]:
            if line.strip():
                print(f'   {line[:60]}...' if len(line) > 60 else f'   {line}')

# 6. 枚举值匹配测试
print('\n' + '='*80)
print('6. 枚举值匹配测试')
print('='*80)

enum_tests = [
    ("资产状态", ["在用", "闲置", "维修", "报废"]),
    ("盘点类型", ["全面盘点", "抽查盘点", "专项盘点"]),
    ("优先级", ["紧急", "高", "中", "低"]),
    ("验收状态", ["待审核", "审核中", "已通过"]),
    ("质控结果", ["合格", "不合格", "待处理"]),
]

for enum_name, values in enum_tests:
    print(f'\n枚举: "{enum_name}"')
    print(f'   期望值: {", ".join(values)}')
    results = engine.search(enum_name, top_k=3)
    
    for result in results[:2]:
        if result.matched_enums:
            print(f'   → {result.table_name}: {", ".join(result.matched_enums)}')
        else:
            print(f'   → {result.table_name} (相似度: {result.relevance_score:.4f})')

# 7. 字段匹配测试
print('\n' + '='*80)
print('7. 字段匹配测试')
print('='*80)

field_tests = [
    ("资产编号", "asset_code"),
    ("盘点日期", "inventory_date"),
    ("工单编号", "work_order_no"),
    ("采购日期", "purchase_date"),
    ("存放位置", "location"),
    ("责任人", "responsible_person"),
]

for question, expected_field in field_tests:
    print(f'\n问题: "{question}"')
    print(f'期望字段: {expected_field}')
    results = engine.search(question, top_k=3)
    
    for result in results[:2]:
        if result.matched_fields:
            print(f'   → {result.table_name}: {", ".join(result.matched_fields)}')
        else:
            matched = False
            for field in result.matched_fields or []:
                if expected_field.lower() in field.lower():
                    matched = True
                    break
            print(f'   → {result.table_name} (相似度: {result.relevance_score:.4f})')

print('\n' + '='*80)
print('测试完成!')
print('='*80)
