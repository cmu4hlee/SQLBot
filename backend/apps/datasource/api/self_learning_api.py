"""
数据库自我学习API接口
提供触发自我学习、获取学习状态的接口
"""

import asyncio
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlmodel import Session, select

from apps.system.crud.user import get_current_user
from apps.system.schemas.system_schema import UserInfoDTO
from common.core.deps import SessionDep, CurrentUser
from common.utils.utils import SQLBotLogUtil
from apps.datasource.embedding.db_description_parser import DatabaseDescriptionParser
from apps.datasource.embedding.db_self_learning import DatabaseSelfLearning
from apps.datasource.models.datasource import CoreDatasource
from apps.datasource.utils.utils import aes_decrypt
import json

router = APIRouter(tags=["self_learning"], prefix="/self_learning")


class LearningResponse(BaseModel):
    """学习响应"""
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None


class LearningStatusResponse(BaseModel):
    """学习状态"""
    is_learning: bool = False
    last_learning_time: Optional[str] = None
    terms_count: int = 0
    trainings_count: int = 0
    db_description_exists: bool = False


learning_state = {
    "is_learning": False,
    "last_learning_time": None,
    "terms_count": 0,
    "trainings_count": 0
}


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


@router.post("/trigger", response_model=LearningResponse, summary="触发自我学习")
async def trigger_learning(
    session: SessionDep,
    current_user: CurrentUser
) -> LearningResponse:
    """
    触发数据库自我学习过程
    - 解析数据库描述文件
    - 生成术语和训练数据
    - 存储到数据库
    """
    if learning_state["is_learning"]:
        return LearningResponse(
            status="warning",
            message="学习过程正在进行中，请勿重复触发",
            details={
                "is_learning": True,
                "started_at": learning_state.get("last_learning_time")
            }
        )

    try:
        learning_state["is_learning"] = True

        base_dir = None
        for path in ["/Users/cjlee/Desktop/Project/SQLbot/backend", "."]:
            p = path if path.startswith("/") else f"backend/{path}"
            import os
            if os.path.exists(f"{p}/数据库描述.md"):
                base_dir = p
                break

        if not base_dir:
            # 尝试在当前目录查找
            import os
            for root, dirs, files in os.walk("."):
                for file in files:
                    if file == "数据库描述.md":
                        base_dir = root
                        break
                if base_dir:
                    break

        if not base_dir:
            learning_state["is_learning"] = False
            raise HTTPException(
                status_code=404,
                detail="未找到数据库描述文件 (数据库描述.md)"
            )

        description_file = f"{base_dir}/数据库描述.md"
        SQLBotLogUtil.info(f"开始自我学习，读取文件: {description_file}")

        ds = find_zcgl_datasource(session)
        ds_id = None
        oid = current_user.oid or 1

        if ds:
            SQLBotLogUtil.info(f"找到数据源: id={ds.id}, name={ds.name}")
            ds_id = ds.id
            oid = ds.oid or 1
        else:
            SQLBotLogUtil.warning("未找到资产管理系统数据源，将使用全局模式")

        learner = DatabaseSelfLearning(description_file, ds_id)

        async def do_learn():
            return await learner.learn_and_store(session, oid)

        result = await asyncio.coroutine(do_learn)()

        learning_state["is_learning"] = False
        learning_state["last_learning_time"] = str(datetime.now())
        learning_state["terms_count"] = result.get("terms_count", 0)
        learning_state["trainings_count"] = result.get("trainings_count", 0)

        return LearningResponse(
            status="success",
            message=f"自我学习完成！生成了 {result.get('terms_count', 0)} 个术语和 {result.get('trainings_count', 0)} 条训练数据",
            details=result
        )

    except Exception as e:
        learning_state["is_learning"] = False
        SQLBotLogUtil.error(f"自我学习失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"学习过程出错: {str(e)}"
        )


@router.get("/status", response_model=LearningStatusResponse, summary="获取学习状态")
async def get_learning_status() -> LearningStatusResponse:
    """获取当前自我学习状态"""
    import os
    db_description_exists = False
    for path in ["/Users/cjlee/Desktop/Project/SQLbot/backend", "."]:
        if os.path.exists(f"{path}/数据库描述.md"):
            db_description_exists = True
            break

    return LearningStatusResponse(
        is_learning=learning_state["is_learning"],
        last_learning_time=learning_state.get("last_learning_time"),
        terms_count=learning_state.get("terms_count", 0),
        trainings_count=learning_state.get("trainings_count", 0),
        db_description_exists=db_description_exists
    )


@router.get("/preview", summary="预览数据库描述解析结果")
async def preview_description():
    """预览数据库描述文件的解析结果（不存储到数据库）"""
    import os
    description_file = None
    for path in ["/Users/cjlee/Desktop/Project/SQLbot/backend", "."]:
        if os.path.exists(f"{path}/数据库描述.md"):
            description_file = f"{path}/数据库描述.md"
            break

    if not description_file:
        raise HTTPException(
            status_code=404,
            detail="未找到数据库描述文件 (数据库描述.md)"
        )

    try:
        parser = DatabaseDescriptionParser(description_file)
        modules = parser.parse()

        preview_data = []
        for module in modules:
            module_data = {
                "name": module.module_name,
                "description": module.module_description,
                "tables_count": len(module.tables),
                "tables": []
            }
            for table in module.tables:
                table_data = {
                    "name": table.table_name,
                    "comment": table.table_comment,
                    "fields_count": len(table.fields),
                    "enums_count": len(table.enums),
                    "indexes_count": len(table.indexes),
                    "foreign_keys_count": len(table.foreign_keys)
                }
                module_data["tables"].append(table_data)
            preview_data.append(module_data)

        return {
            "status": "success",
            "modules_count": len(modules),
            "preview": preview_data
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"解析失败: {str(e)}"
        )


@router.get("/summary", summary="获取数据库架构摘要")
async def get_schema_summary():
    """获取数据库架构的摘要信息"""
    import os
    description_file = None
    for path in ["/Users/cjlee/Desktop/Project/SQLbot/backend", "."]:
        if os.path.exists(f"{path}/数据库描述.md"):
            description_file = f"{path}/数据库描述.md"
            break

    if not description_file:
        raise HTTPException(
            status_code=404,
            detail="未找到数据库描述文件 (数据库描述.md)"
        )

    try:
        parser = DatabaseDescriptionParser(description_file)
        modules = parser.parse()
        summary = parser.get_schema_summary()

        return {
            "status": "success",
            "summary": summary
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"生成摘要失败: {str(e)}"
        )


from datetime import datetime
