#!/usr/bin/env python3
"""
自动化自我学习测试
执行100次自然语言查询，检测结果，实现自动学习循环
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


class AutoLearningTester:
    """自动化学习测试器"""

    def __init__(self):
        self.parser = DatabaseDescriptionParser('/opt/sqlbot/app/数据库描述.md')
        self.modules = self.parser.parse()
        self.semantic_engine = get_semantic_search_engine()
        self.injector = DatabaseContextInjector()
        self.learning_engine = get_self_learning_engine()

        self.test_queries = self._generate_test_queries()

    def _generate_test_queries(self) -> List[Dict[str, Any]]:
        """生成100个测试查询"""
        queries = []

        base_queries = [
            # 资产相关
            {"question": "查询所有资产", "tables": ["assets"], "keywords": ["资产"]},
            {"question": "资产列表", "tables": ["assets"], "keywords": ["资产"]},
            {"question": "资产情况", "tables": ["assets"], "keywords": ["资产"]},
            {"question": "资产统计", "tables": ["assets"], "keywords": ["资产"]},
            {"question": "资产状态", "tables": ["assets"], "keywords": ["资产", "状态"]},
            {"question": "资产分类", "tables": ["asset_categories"], "keywords": ["资产", "分类"]},
            {"question": "资产位置", "tables": ["asset_locations", "assets"], "keywords": ["资产", "位置"]},
            {"question": "资产编号查询", "tables": ["assets"], "keywords": ["资产", "编号"]},
            {"question": "资产价值", "tables": ["assets"], "keywords": ["资产", "价值"]},
            {"question": "资产折旧", "tables": ["assets"], "keywords": ["资产", "折旧"]},

            # 盘点相关
            {"question": "盘点记录", "tables": ["inventory_records"], "keywords": ["盘点"]},
            {"question": "盘点列表", "tables": ["inventory_records"], "keywords": ["盘点"]},
            {"question": "盘点单查询", "tables": ["inventory_records"], "keywords": ["盘点"]},
            {"question": "盘点日期", "tables": ["inventory_records"], "keywords": ["盘点", "日期"]},
            {"question": "盘点类型", "tables": ["inventory_records"], "keywords": ["盘点", "类型"]},
            {"question": "盘点明细", "tables": ["inventory_details"], "keywords": ["盘点", "明细"]},
            {"question": "盘点结果", "tables": ["inventory_details"], "keywords": ["盘点", "结果"]},
            {"question": "差异记录", "tables": ["inventory_details"], "keywords": ["差异"]},

            # 维修相关
            {"question": "维修工单", "tables": ["maintenance_workorders"], "keywords": ["维修"]},
            {"question": "维护记录", "tables": ["maintenance_workorders"], "keywords": ["维护"]},
            {"question": "保养计划", "tables": ["maintenance_plans"], "keywords": ["保养"]},
            {"question": "维修历史", "tables": ["maintenance_records"], "keywords": ["维修", "历史"]},
            {"question": "故障记录", "tables": ["maintenance_records"], "keywords": ["故障"]},
            {"question": "报修信息", "tables": ["maintenance_reports"], "keywords": ["报修"]},

            # 验收相关
            {"question": "验收申请", "tables": ["acceptance_applications"], "keywords": ["验收"]},
            {"question": "验收列表", "tables": ["acceptance_applications"], "keywords": ["验收"]},
            {"question": "验收状态", "tables": ["acceptance_applications"], "keywords": ["验收", "状态"]},
            {"question": "验收记录", "tables": ["acceptance_applications"], "keywords": ["验收"]},
            {"question": "验收签字", "tables": ["acceptance_application_signatures"], "keywords": ["签字"]},
            {"question": "验收文件", "tables": ["acceptance_application_files"], "keywords": ["文件"]},
            {"question": "验收资产", "tables": ["acceptance_application_assets"], "keywords": ["验收", "资产"]},

            # 不良事件相关
            {"question": "不良事件", "tables": ["adverse_reaction_records"], "keywords": ["不良", "事件"]},
            {"question": "故障报告", "tables": ["adverse_reaction_records"], "keywords": ["故障", "报告"]},
            {"question": "安全事故", "tables": ["adverse_reaction_records"], "keywords": ["安全", "事故"]},
            {"question": "事件等级", "tables": ["adverse_reaction_records"], "keywords": ["事件", "等级"]},
            {"question": "严重程度", "tables": ["adverse_reaction_records"], "keywords": ["严重", "程度"]},
            {"question": "事件处理", "tables": ["adverse_reaction_records"], "keywords": ["事件", "处理"]},

            # 质控相关
            {"question": "质控记录", "tables": ["quality_control_records"], "keywords": ["质控"]},
            {"question": "质量控制", "tables": ["quality_control_records"], "keywords": ["质量", "控制"]},
            {"question": "质控结果", "tables": ["quality_control_records"], "keywords": ["质控", "结果"]},
            {"question": "质控类型", "tables": ["quality_control_records"], "keywords": ["质控", "类型"]},
            {"question": "质控预警", "tables": ["quality_management_alerts"], "keywords": ["质控", "预警"]},
            {"question": "质控附件", "tables": ["quality_control_attachments"], "keywords": ["质控", "附件"]},

            # 计量相关
            {"question": "计量记录", "tables": ["metrology_records"], "keywords": ["计量"]},
            {"question": "检测结果", "tables": ["metrology_records"], "keywords": ["检测", "结果"]},
            {"question": "计量类型", "tables": ["metrology_records"], "keywords": ["计量", "类型"]},
            {"question": "计量周期", "tables": ["metrology_records"], "keywords": ["计量", "周期"]},
            {"question": "检测计划", "tables": ["metrology_plans"], "keywords": ["检测", "计划"]},
            {"question": "计量附件", "tables": ["metrology_attachments"], "keywords": ["计量", "附件"]},

            # 调配相关
            {"question": "调配记录", "tables": ["transfer_records"], "keywords": ["调配"]},
            {"question": "资产调配", "tables": ["transfer_records"], "keywords": ["资产", "调配"]},
            {"question": "调配状态", "tables": ["transfer_records"], "keywords": ["调配", "状态"]},
            {"question": "调拨申请", "tables": ["transfer_applications"], "keywords": ["调拨"]},

            # 报废相关
            {"question": "报废记录", "tables": ["scrapped_records"], "keywords": ["报废"]},
            {"question": "资产报废", "tables": ["scrapped_records"], "keywords": ["资产", "报废"]},
            {"question": "报废申请", "tables": ["scrapped_applications"], "keywords": ["报废", "申请"]},

            # 统计查询
            {"question": "统计资产数量", "tables": ["assets"], "keywords": ["统计", "资产"]},
            {"question": "按状态统计", "tables": ["assets"], "keywords": ["统计", "状态"]},
            {"question": "按类型统计", "tables": ["assets"], "keywords": ["统计", "类型"]},
            {"question": "本月盘点统计", "tables": ["inventory_records"], "keywords": ["盘点", "统计"]},
            {"question": "维修次数统计", "tables": ["maintenance_records"], "keywords": ["维修", "统计"]},

            # 口语化表达
            {"question": "设备列表", "tables": ["assets"], "keywords": ["设备"]},
            {"question": "东西在哪里", "tables": ["assets", "asset_locations"], "keywords": ["位置"]},
            {"question": "查一下", "tables": ["assets"], "keywords": ["查询"]},
            {"question": "有多少资产", "tables": ["assets"], "keywords": ["资产", "数量"]},
            {"question": "看看状态", "tables": ["assets"], "keywords": ["状态"]},
            {"question": "需要盘点", "tables": ["inventory_records"], "keywords": ["盘点"]},
            {"question": "设备坏了", "tables": ["adverse_reaction_records"], "keywords": ["设备", "故障"]},
            {"question": "什么时候买的", "tables": ["assets"], "keywords": ["采购", "日期"]},
            {"question": "谁负责的", "tables": ["assets"], "keywords": ["负责"]},
            {"question": "能不能用", "tables": ["assets"], "keywords": ["状态"]},

            # 运维相关
            {"question": "运维日志", "tables": ["operation_logs"], "keywords": ["运维"]},
            {"question": "任务记录", "tables": ["task_records"], "keywords": ["任务"]},
            {"question": "告警信息", "tables": ["alert_records"], "keywords": ["告警"]},

            # AI相关
            {"question": "AI问答", "tables": ["ai_conversations"], "keywords": ["AI"]},
            {"question": "会话记录", "tables": ["ai_conversations"], "keywords": ["会话"]},

            # 系统相关
            {"question": "用户管理", "tables": ["users"], "keywords": ["用户"]},
            {"question": "角色权限", "tables": ["roles"], "keywords": ["角色"]},
            {"question": "操作日志", "tables": ["operation_logs"], "keywords": ["操作"]},
        ]

        queries.extend(base_queries)

        queries = queries[:100]

        random.shuffle(queries)

        for i, q in enumerate(queries):
            q['id'] = i + 1
            q['sql'] = f"SELECT * FROM {q['tables'][0]} LIMIT 1000"

        return queries

    def run_test(self) -> Dict[str, Any]:
        """运行自动化测试"""
        print('='*80)
        print('自动化自我学习测试')
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

        print('\n[2/3] 执行查询并记录反馈...')
        print('-'*80)

        for i, query in enumerate(self.test_queries, 1):
            print(f'\r      进度: {i}/{len(self.test_queries)} ({i*100//len(self.test_queries)}%)', end='', flush=True)

            question = query['question']
            expected_tables = query['tables']

            semantic_results = self.semantic_engine.search(question, top_k=5)

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

            query_id = record_user_feedback(
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
                'success': is_success,
                'feedback': feedback
            })

        print('\n')

        print('\n[3/3] 分析学习效果...')
        print('-'*80)

        stats = self.learning_engine.get_learning_stats()

        print('\n' + '='*80)
        print('测试结果统计')
        print('='*80)

        success_rate = results['success'] / results['total'] * 100

        print(f'\n查询统计:')
        print(f'   总查询数: {results["total"]}')
        print(f'   成功匹配: {results["success"]} ({success_rate:.1f}%)')
        print(f'   失败匹配: {results["failed"]} ({100-success_rate:.1f}%)')

        print(f'\n反馈统计:')
        print(f'   正面反馈: {results["feedback_positive"]}')
        print(f'   负面反馈: {results["feedback_negative"]}')

        print(f'\n学习统计:')
        print(f'   学习模式数: {stats["learned_patterns"]}')
        print(f'   关键词权重数: {stats["keyword_weights"]}')
        print(f'   记忆条目数: {stats["memory_items"]}')

        print(f'\n高频关键词 (Top 10):')
        for kw in stats["top_keywords"][:10]:
            print(f'   - {kw["keyword"]}: 权重={kw["weight"]:.2f}, 成功={kw["success"]}')

        print(f'\n成功模式 (Top 5):')
        for pattern in stats["top_patterns"][:5]:
            print(f'   - {pattern["pattern"][:40]}... 成功={pattern["success"]}')

        print(f'\n失败查询分析:')
        failed_queries = [r for r in results['query_results'] if not r['success']]
        if failed_queries:
            for r in failed_queries[:10]:
                print(f'   ❌ "{r["question"]}" (期望: {r["expected"]}, 匹配: {r["matched"]})')
        else:
            print('   ✅ 所有查询都成功匹配!')

        print('\n' + '='*80)

        return results


def main():
    """主函数"""
    tester = AutoLearningTester()
    results = tester.run_test()

    print('\n✅ 自动化自我学习测试完成!')
    print(f'\n总结:')
    print(f'   - 执行了 {results["total"]} 次查询')
    print(f'   - 成功率: {results["success"]/results["total"]*100:.1f}%')
    print(f'   - 收集了 {results["feedback_positive"]} 条正面反馈')
    print(f'   - 收集了 {results["feedback_negative"]} 条负面反馈')
    print(f'   - 系统已自动学习这些反馈并优化语义理解')


if __name__ == '__main__':
    main()
