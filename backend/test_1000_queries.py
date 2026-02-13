#!/usr/bin/env python3
"""
大规模自动化自我学习测试
执行1000次自然语言查询，检测结果，实现自动学习循环
"""
import sys
sys.path.insert(0, '/opt/sqlbot/app')

import random
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any

from apps.datasource.embedding.db_description_parser import DatabaseDescriptionParser
from apps.datasource.embedding.semantic_search import get_semantic_search_engine
from apps.datasource.embedding.db_context_injector import DatabaseContextInjector
from apps.datasource.embedding.self_learning import (
    SelfLearningEngine,
    get_self_learning_engine,
    record_user_feedback
)


class LargeScaleLearningTester:
    """大规模学习测试器"""

    def __init__(self):
        self.parser = DatabaseDescriptionParser('/opt/sqlbot/app/数据库描述.md')
        self.modules = self.parser.parse()
        self.semantic_engine = get_semantic_search_engine()
        self.injector = DatabaseContextInjector()
        self.learning_engine = get_self_learning_engine()

        self.test_queries = self._generate_1000_queries()

    def _generate_1000_queries(self) -> List[Dict[str, Any]]:
        """生成1000个测试查询"""
        queries = []

        noun_keywords = {
            "资产": ["assets"],
            "资产列表": ["assets"],
            "资产信息": ["assets"],
            "资产情况": ["assets"],
            "资产状态": ["assets"],
            "资产统计": ["assets"],
            "资产分类": ["asset_categories"],
            "资产位置": ["asset_locations"],

            "盘点": ["inventory_records"],
            "盘点记录": ["inventory_records"],
            "盘点列表": ["inventory_records"],
            "盘点结果": ["inventory_details"],
            "盘点明细": ["inventory_details"],

            "维修": ["maintenance_workorders"],
            "维修工单": ["maintenance_workorders"],
            "维护记录": ["maintenance_records"],
            "保养计划": ["maintenance_plans"],
            "故障记录": ["maintenance_records"],

            "验收": ["acceptance_applications"],
            "验收申请": ["acceptance_applications"],
            "验收记录": ["acceptance_applications"],
            "签字": ["acceptance_application_signatures"],
            "文件": ["acceptance_application_files"],

            "不良事件": ["adverse_reaction_records"],
            "故障报告": ["adverse_reaction_records"],
            "事故": ["adverse_reaction_records"],
            "事件等级": ["adverse_reaction_records"],
            "严重程度": ["adverse_reaction_records"],

            "质控": ["quality_control_records"],
            "质控记录": ["quality_control_records"],
            "质量控制": ["quality_control_records"],
            "质控结果": ["quality_control_records"],
            "预警": ["quality_management_alerts"],

            "计量": ["metrology_records"],
            "计量记录": ["metrology_records"],
            "检测结果": ["metrology_records"],
            "检测计划": ["metrology_plans"],

            "调配": ["transfer_records"],
            "调配记录": ["transfer_records"],
            "资产调配": ["transfer_records"],
            "调拨": ["transfer_applications"],

            "报废": ["scrapped_records"],
            "报废记录": ["scrapped_records"],
            "报废申请": ["scrapped_applications"],

            "日志": ["operation_logs"],
            "用户": ["users"],
            "角色": ["roles"],
            "任务": ["task_records"],
            "告警": ["alert_records"],
            "AI问答": ["ai_conversations"],
            "会话": ["ai_conversations"],
        }

        actions = ["查询", "查看", "获取", "统计", "列出", "展示"]
        modifiers = ["", "列表", "信息", "情况", "状态", "统计", "查询", "查看", "记录", "详情", "历史", "最新", "今天", "本周", "本月", "所有", "全部", "多少", "哪些"]

        for i in range(1000):
            if random.random() < 0.3:
                noun, tables = random.choice(list(noun_keywords.items()))
                action = random.choice(actions)
                question = f"{action}{noun}"
            elif random.random() < 0.3:
                noun, tables = random.choice(list(noun_keywords.items()))
                modifier = random.choice(modifiers)
                question = f"{modifier}{noun}" if modifier else noun
            else:
                noun, tables = random.choice(list(noun_keywords.items()))
                question = noun

            query = {
                'id': i + 1,
                'question': question,
                'tables': tables,
                'keywords': [noun],
                'sql': f"SELECT * FROM {tables[0]} LIMIT 1000"
            }
            queries.append(query)

        return queries

    def run_test(self) -> Dict[str, Any]:
        """运行大规模测试"""
        print('='*80)
        print('大规模自动化自我学习测试 - 1000次查询')
        print('='*80)
        print(f'\n测试时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'测试查询数: {len(self.test_queries)}')

        results = {
            'total': len(self.test_queries),
            'success': 0,
            'failed': 0,
            'feedback_positive': 0,
            'feedback_negative': 0,
            'query_results': []
        }

        print('\n[1/3] 构建语义向量索引...')
        if not self.semantic_engine.index_built:
            self.semantic_engine.build_index(self.modules, force=True)
        print(f'      索引表数量: {len(self.semantic_engine.table_vectors)}')

        print('\n[2/3] 执行1000次查询并记录反馈...')
        print('-'*80)

        start_time = time.time()

        for i, query in enumerate(self.test_queries, 1):
            if i % 100 == 0:
                elapsed = time.time() - start_time
                eta = (elapsed / i) * (len(self.test_queries) - i)
                print(f'\r      进度: {i}/{len(self.test_queries)} ({i*100//len(self.test_queries)}%) '
                      f'已用时: {elapsed:.1f}秒 预计剩余: {eta:.1f}秒', end='', flush=True)

            question = query['question']
            expected_tables = query['tables']

            semantic_results = self.semantic_engine.search(question, top_k=3)
            matched_tables = [r.table_name for r in semantic_results[:3]]

            is_success = len(set(matched_tables) & set(expected_tables)) > 0

            if is_success:
                results['success'] += 1
                feedback = 'positive'
                results['feedback_positive'] += 1
            else:
                results['failed'] += 1
                feedback = 'negative'
                results['feedback_negative'] += 1

            record_user_feedback(
                question=question,
                generated_sql=query['sql'],
                feedback=feedback,
                matched_tables=matched_tables,
                matched_fields=[],
                matched_enums=[]
            )

            results['query_results'].append({
                'id': query['id'],
                'question': question,
                'expected': expected_tables,
                'matched': matched_tables,
                'success': is_success
            })

        total_time = time.time() - start_time
        print('\n')

        print('\n[3/3] 分析学习效果...')
        print('-'*80)

        stats = self.learning_engine.get_learning_stats()

        print('\n' + '='*80)
        print('大规模测试结果统计')
        print('='*80)

        success_rate = results['success'] / results['total'] * 100

        print(f'\n查询统计:')
        print(f'   总查询数: {results["total"]}')
        print(f'   成功匹配: {results["success"]} ({success_rate:.1f}%)')
        print(f'   失败匹配: {results["failed"]} ({100-success_rate:.1f}%)')
        print(f'   总耗时: {total_time:.1f}秒')
        print(f'   平均每查询: {total_time/results["total"]*1000:.1f}毫秒')

        print(f'\n反馈统计:')
        print(f'   正面反馈: {results["feedback_positive"]}')
        print(f'   负面反馈: {results["feedback_negative"]}')

        print(f'\n学习统计:')
        print(f'   学习模式数: {stats["learned_patterns"]}')
        print(f'   关键词权重数: {stats["keyword_weights"]}')
        print(f'   记忆条目数: {stats["memory_items"]}')

        print(f'\n高频关键词 (Top 20):')
        for kw in stats["top_keywords"][:20]:
            print(f'   - {kw["keyword"][:30]}: 权重={kw["weight"]:.2f}, 成功={kw["success"]}')

        print(f'\n成功模式 (Top 10):')
        for pattern in stats["top_patterns"][:10]:
            print(f'   - {pattern["pattern"][:40]}... 成功={pattern["success"]}, 置信度={pattern["confidence"]:.2f}')

        print(f'\n失败查询示例 (前20个):')
        failed_queries = [r for r in results['query_results'] if not r['success']]
        for r in failed_queries[:20]:
            print(f'   ❌ "{r["question"][:30]}" (期望: {r["expected"]}, 匹配: {r["matched"][:2]})')

        print('\n' + '='*80)

        return results


def main():
    """主函数"""
    tester = LargeScaleLearningTester()
    results = tester.run_test()

    print('\n✅ 大规模自动化自我学习测试完成!')
    print(f'\n📊 总结:')
    print(f'   - 执行了 {results["total"]} 次查询')
    print(f'   - 成功率: {results["success"]/results["total"]*100:.1f}%')
    print(f'   - 收集了 {results["feedback_positive"]} 条正面反馈')
    print(f'   - 收集了 {results["feedback_negative"]} 条负面反馈')
    print(f'   - 系统已自动学习这些反馈并持续优化语义理解')


if __name__ == '__main__':
    main()
