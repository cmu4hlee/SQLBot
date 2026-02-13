"""
执行数据库自我学习的便捷脚本
支持通过命令行参数控制学习行为
"""

import argparse
import asyncio
from pathlib import Path
from sqlmodel import Session, select

from apps.datasource.embedding.db_description_parser import DatabaseDescriptionParser
from apps.datasource.embedding.db_self_learning import DatabaseSelfLearning
from apps.datasource.models.datasource import CoreDatasource
from apps.datasource.utils.utils import aes_decrypt
from common.core.db import engine
from common.utils.utils import SQLBotLogUtil


def find_zcgl_datasource(session: Session):
    """查找资产管理系统数据源"""
    ds_list = session.exec(select(CoreDatasource)).all()
    for ds in ds_list:
        if ds.name and "zcgl" in ds.name.lower():
            return ds
        if ds.description and "zcgl" in ds.description.lower():
            return ds
    for ds in ds_list:
        try:
            conf = json.loads(aes_decrypt(ds.configuration))
        except Exception:
            continue
        db_name = conf.get("database") or conf.get("dbSchema") or conf.get("db_schema")
        if db_name and str(db_name).lower() == "zcgl":
            return ds
    return None


def parse_only(args):
    """仅解析模式"""
    description_file = Path(args.file)
    if not description_file.exists():
        SQLBotLogUtil.error(f"文件不存在: {description_file}")
        return 1

    SQLBotLogUtil.info(f"解析数据库描述文件: {description_file}")
    parser = DatabaseDescriptionParser(str(description_file))
    modules = parser.parse()

    SQLBotLogUtil.info(f"\n{'='*60}")
    SQLBotLogUtil.info(f"解析结果: 共 {len(modules)} 个模块")
    SQLBotLogUtil.info(f"{'='*60}\n")

    for module in modules:
        SQLBotLogUtil.info(f"📦 模块: {module.module_name}")
        SQLBotLogUtil.info(f"   描述: {module.module_description}")
        SQLBotLogUtil.info(f"   包含 {len(module.tables)} 个表:")
        for table in module.tables:
            SQLBotLogUtil.info(f"      - {table.table_name} ({table.table_comment})")
            SQLBotLogUtil.info(f"        字段: {len(table.fields)}, 枚举: {len(table.enums)}, 索引: {len(table.indexes)}")
        SQLBotLogUtil.info("")

    return 0


def summary_only(args):
    """仅生成摘要"""
    description_file = Path(args.file)
    if not description_file.exists():
        SQLBotLogUtil.error(f"文件不存在: {description_file}")
        return 1

    SQLBotLogUtil.info(f"生成数据库架构摘要: {description_file}")
    parser = DatabaseDescriptionParser(str(description_file))
    modules = parser.parse()

    summary = parser.get_schema_summary()

    if args.output:
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(summary)
        SQLBotLogUtil.info(f"摘要已保存到: {output_file}")
    else:
        print("\n" + summary)

    return 0


def learn_only(args):
    """执行学习"""
    description_file = Path(args.file)
    if not description_file.exists():
        SQLBotLogUtil.error(f"文件不存在: {description_file}")
        return 1

    base_dir = description_file.parent

    SQLBotLogUtil.info(f"执行数据库自我学习: {description_file}")

    with Session(engine) as session:
        ds = find_zcgl_datasource(session)
        ds_id = None
        oid = 1

        if ds:
            SQLBotLogUtil.info(f"找到数据源: id={ds.id}, name={ds.name}")
            ds_id = ds.id
            oid = ds.oid or 1
        else:
            SQLBotLogUtil.warning("未找到资产管理系统数据源，将使用全局模式")

        learner = DatabaseSelfLearning(str(description_file), ds_id)

        async def do_learn():
            return await learner.learn_and_store(session, oid)

        try:
            result = asyncio.run(do_learn())
            SQLBotLogUtil.info(f"\n{'='*60}")
            SQLBotLogUtil.info(f"✅ 自我学习完成!")
            SQLBotLogUtil.info(f"   生成术语: {result['terms_count']} 个")
            SQLBotLogUtil.info(f"   生成训练数据: {result['trainings_count']} 条")
            SQLBotLogUtil.info(f"{'='*60}\n")
        except Exception as e:
            SQLBotLogUtil.error(f"❌ 学习过程出错: {e}")
            import traceback
            traceback.print_exc()
            return 1

    return 0


def all_in_one(args):
    """完整流程：解析摘要+学习"""
    description_file = Path(args.file)
    if not description_file.exists():
        SQLBotLogUtil.error(f"文件不存在: {description_file}")
        return 1

    base_dir = description_file.parent

    SQLBotLogUtil.info(f"\n{'='*60}")
    SQLBotLogUtil.info(f"🚀 数据库自我学习完整流程")
    SQLBotLogUtil.info(f"{'='*60}\n")

    # 步骤1: 解析
    SQLBotLogUtil.info("步骤1: 解析数据库描述文件...")
    parser = DatabaseDescriptionParser(str(description_file))
    modules = parser.parse()
    SQLBotLogUtil.info(f"  ✅ 解析完成: {len(modules)} 个模块")

    # 步骤2: 生成摘要
    SQLBotLogUtil.info("\n步骤2: 生成数据库架构摘要...")
    summary = parser.get_schema_summary()
    summary_file = base_dir / "data" / "db_schema_summary.md"
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary)
    SQLBotLogUtil.info(f"  ✅ 摘要已保存: {summary_file}")

    # 步骤3: 执行学习
    SQLBotLogUtil.info("\n步骤3: 执行自我学习并存储...")

    with Session(engine) as session:
        ds = find_zcgl_datasource(session)
        ds_id = None
        oid = 1

        if ds:
            SQLBotLogUtil.info(f"  📦 找到数据源: id={ds.id}, name={ds.name}")
            ds_id = ds.id
            oid = ds.oid or 1
        else:
            SQLBotLogUtil.warning("  ⚠️ 未找到资产管理系统数据源，将使用全局模式")

        learner = DatabaseSelfLearning(str(description_file), ds_id)

        async def do_learn():
            return await learner.learn_and_store(session, oid)

        try:
            result = asyncio.run(do_learn())
            SQLBotLogUtil.info(f"  ✅ 学习完成!")
            SQLBotLogUtil.info(f"     - 生成术语: {result['terms_count']} 个")
            SQLBotLogUtil.info(f"     - 生成训练数据: {result['trainings_count']} 条")
        except Exception as e:
            SQLBotLogUtil.error(f"  ❌ 学习出错: {e}")
            import traceback
            traceback.print_exc()
            return 1

    SQLBotLogUtil.info(f"\n{'='*60}")
    SQLBotLogUtil.info(f"✅ 所有步骤完成!")
    SQLBotLogUtil.info(f"{'='*60}\n")

    return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="数据库自我学习工具 - 根据数据库描述文件生成术语和训练数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_db_self_learning.py --parse                    # 仅解析文件
  python run_db_self_learning.py --summary                  # 生成摘要
  python run_db_self_learning.py --learn                    # 执行学习
  python run_db_self_learning.py --all                     # 完整流程
  python run_db_self_learning.py --summary -o summary.txt   # 生成摘要到文件
        """
    )

    parser.add_argument(
        '--file', '-f',
        default=str(Path(__file__).parent.parent / "数据库描述.md"),
        help='数据库描述文件路径 (默认: backend/数据库描述.md)'
    )

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # parse 命令
    parse_cmd = subparsers.add_parser('parse', help='仅解析数据库描述文件')
    parse_cmd.set_defaults(func=parse_only)

    # summary 命令
    summary_cmd = subparsers.add_parser('summary', help='生成数据库架构摘要')
    summary_cmd.add_argument('--output', '-o', help='输出文件路径')
    summary_cmd.set_defaults(func=summary_only)

    # learn 命令
    learn_cmd = subparsers.add_parser('learn', help='执行自我学习')
    learn_cmd.set_defaults(func=learn_only)

    # all 命令
    all_cmd = subparsers.add_parser('all', help='完整流程：解析+摘要+学习')
    all_cmd.set_defaults(func=all_in_one)

    args = parser.parse_args()

    if not args.command:
        # 默认执行完整流程
        args.func = all_in_one

    return args.func(args)


if __name__ == "__main__":
    import sys
    import json

    sys.exit(main())
