#!/usr/bin/env python3
"""
调试关键词提取逻辑
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

from apps.datasource.embedding.db_context_injector import DatabaseContextInjector
import re

# 创建新的注入器实例
injector = DatabaseContextInjector()

print('='*70)
print('调试关键词提取逻辑')
print('='*70)

test_question = '查询盘点记录'

print(f'\n1. 测试问题: "{test_question}"')

# 手动模拟提取过程
text = re.sub(r'[，。！？、：；""''【】（）\(\)\[\]]', ' ', test_question)
print(f'   去除标点后: "{text}"')

words = text.split()
print(f'   split后: {words}')

stopwords = {'的', '是', '在', '有', '和', '与', '或', '及', '等', '查询', '统计', '获取', '查找',
             '请问', '我想', '请', '帮我', '多少', '哪些', '什么', '如何', '怎样', '显示', '所有', '列表',
             '一个', '这个', '那个', '哪些', '各种', '不同'}

keywords = set()
for word in words:
    word = word.strip()
    if not word:
        continue
    if word in stopwords:
        print(f'   跳过停用词: {word}')
        continue
    if len(word) >= 2:
        keywords.add(word)
        print(f'   添加关键词: {word}')

print(f'   最终关键词: {list(keywords)}')

# 测试n-gram
if not keywords:
    text_clean = re.sub(r'[^\w\s]', '', text).strip()
    print(f'\n   清理后文本: "{text_clean}"')
    print(f'   清理后长度: {len(text_clean)}')

    if len(text_clean) >= 4:
        for i in range(len(text_clean) - 1):
            if '\u4e00' <= text_clean[i] <= '\u9fff':
                ngram = text_clean[i:i+2]
                print(f'   n-gram: "{ngram}"')

print('\n' + '='*70)
