import json
from typing import Optional

from sqlmodel import Session, select

from apps.data_training.curd.data_training import create_training
from apps.data_training.models.data_training_model import DataTrainingInfo
from apps.datasource.models.datasource import CoreDatasource
from apps.datasource.utils.utils import aes_decrypt
from apps.terminology.curd.terminology import create_terminology
from apps.terminology.models.terminology_model import TerminologyInfo
from common.core.db import engine


def _trans(key: str, **kwargs) -> str:
    if kwargs:
        try:
            return key.format(**kwargs)
        except Exception:
            return key
    return key


def _find_zcgl_datasource(session: Session) -> Optional[CoreDatasource]:
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


def _seed_terminology(session: Session, oid: int, ds_id: Optional[int]) -> None:
    specific_ds = ds_id is not None
    datasource_ids = [ds_id] if ds_id is not None else []
    items = [
        TerminologyInfo(
            word="超声设备",
            other_words=["超声", "B超", "彩超", "超声仪", "超声诊断设备", "ultrasound", "ultrasound device"],
            description=(
                "指资产名称/型号/规格中包含超声、B超、彩超等关键词的设备，"
                "或分类为“医疗影像设备”(code=YL-01)的资产；资产类型通常为“医疗设备”。"
            ),
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="医疗影像设备",
            other_words=["影像设备", "医学影像设备", "影像类设备"],
            description="对应资产分类 asset_categories.name=医疗影像设备（code=YL-01）。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="医疗设备",
            other_words=["医用设备", "医疗器械"],
            description="对应 assets.asset_type='医疗设备'。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="资产编号",
            other_words=["资产编码", "编号", "资产码"],
            description="对应 assets.asset_code。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="设备型号",
            other_words=["型号", "model"],
            description="对应 assets.model。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="规格参数",
            other_words=["规格", "参数", "specification"],
            description="对应 assets.specification。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="使用科室",
            other_words=["使用部门", "科室", "department"],
            description="对应 assets.department。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="存放位置",
            other_words=["位置", "location"],
            description="对应 assets.location。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="当前价值",
            other_words=["现值", "current value"],
            description="对应 assets.current_value。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="购置价格",
            other_words=["采购价格", "原值", "purchase price"],
            description="对应 assets.purchase_price。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="资产状态",
            other_words=["在用", "闲置", "维修", "报废", "调配中", "status"],
            description="对应 assets.status。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="资产分类",
            other_words=["分类", "类别", "资产类别"],
            description="对应 asset_categories（id/name/code/parent_id），assets.category_id 关联分类。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="资产台账",
            other_words=["资产信息", "资产主表", "资产清单"],
            description="对应 assets。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="盘点",
            other_words=["盘点记录", "盘点任务", "盘点单"],
            description="对应 inventory_records。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="盘点明细",
            other_words=["盘点详情", "盘点资产明细"],
            description="对应 inventory_details（discrepancy_type 表示差异类型）。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="盘点差异",
            other_words=["差异类型", "异常盘点"],
            description="对应 inventory_details.discrepancy_type（正常/位置不符/状态不符/缺失/多余）。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="资产调配",
            other_words=["调配单", "调拨", "转移"],
            description="对应 transfer_records（status/transfer_date/from_department/to_department）。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="闲置资产",
            other_words=["闲置发布", "闲置资产发布"],
            description="对应 idle_assets（status 发布中/已分配/已取消）。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="验收申请",
            other_words=["验收单", "验收申请单"],
            description="对应 acceptance_applications。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="验收资产",
            other_words=["验收申请资产", "验收资产明细"],
            description="对应 acceptance_application_assets。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="验收文件",
            other_words=["验收附件", "验收资料"],
            description="对应 acceptance_application_files。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="验收签字",
            other_words=["验收签名", "验收签字记录"],
            description="对应 acceptance_application_signatures。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="验收记录",
            other_words=["资产验收记录", "验收结果"],
            description="对应 asset_acceptance_records。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="不良事件",
            other_words=["不良反应", "不良事件报告"],
            description="对应 adverse_reaction_records（status/occurrence_date/department）。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="不良事件附件",
            other_words=["不良事件材料", "事件附件"],
            description="对应 adverse_reaction_attachments。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="不良事件流程",
            other_words=["不良事件处理流程", "事件流程"],
            description="对应 adverse_reaction_workflow。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="维护工单",
            other_words=["维修工单", "工单"],
            description="对应 maintenance_workorders。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="工单材料",
            other_words=["维护材料", "工单材料明细"],
            description="对应 maintenance_workorder_materials。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="计量记录",
            other_words=["计量", "检定", "校准"],
            description="对应 metrology_records（next_metrology_date 表示下次计量日期）。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="质控记录",
            other_words=["质控", "QC"],
            description="对应 quality_control_records（next_qc_date 表示下次质控日期）。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="质量预警",
            other_words=["计量预警", "质控预警", "预警记录"],
            description="对应 quality_management_alerts。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="质量周期",
            other_words=["计量周期", "质控周期"],
            description="对应 quality_management_cycles。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="位置编码",
            other_words=["位置", "location code", "位置管理"],
            description="对应 location_codes。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="资产图片",
            other_words=["资产照片", "图片"],
            description="对应 asset_images。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="资产变更",
            other_words=["变更日志", "变更记录"],
            description="对应 asset_change_logs。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
        TerminologyInfo(
            word="资产设备绑定",
            other_words=["设备绑定", "解绑记录"],
            description="对应 asset_device_mapping。",
            specific_ds=specific_ds,
            datasource_ids=datasource_ids,
            enabled=True,
        ),
    ]

    for item in items:
        try:
            create_terminology(session, item, oid, _trans, skip_embedding=True)
            print(f"[terminology] created: {item.word}")
        except Exception as exc:
            print(f"[terminology] skip: {item.word} ({exc})")


def _seed_training(session: Session, oid: int, ds_id: Optional[int]) -> None:
    if ds_id is None:
        print("[training] datasource not found, skipping data training.")
        return

    examples = [
        (
            "统计超声设备数量",
            """
SELECT COUNT(*) AS asset_count
FROM assets a
LEFT JOIN asset_categories c ON a.category_id = c.id
WHERE a.asset_type = '医疗设备'
  AND (
    a.asset_name LIKE '%超声%' OR a.asset_name LIKE '%彩超%' OR a.asset_name LIKE '%B超%'
    OR a.model LIKE '%超声%' OR a.specification LIKE '%超声%'
    OR c.name = '医疗影像设备' OR c.code = 'YL-01'
  )
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询超声设备清单（资产编号、名称、型号、科室、状态、位置）",
            """
SELECT a.asset_code, a.asset_name, a.model, a.department, a.status, a.location
FROM assets a
LEFT JOIN asset_categories c ON a.category_id = c.id
WHERE a.asset_type = '医疗设备'
  AND (
    a.asset_name LIKE '%超声%' OR a.asset_name LIKE '%彩超%' OR a.asset_name LIKE '%B超%'
    OR a.model LIKE '%超声%' OR a.specification LIKE '%超声%'
    OR c.name = '医疗影像设备' OR c.code = 'YL-01'
  )
ORDER BY a.asset_code
LIMIT 1000;
            """.strip(),
        ),
        (
            "按科室统计超声设备数量和当前价值",
            """
SELECT a.department,
       COUNT(*) AS asset_count,
       SUM(a.current_value) AS total_current_value
FROM assets a
LEFT JOIN asset_categories c ON a.category_id = c.id
WHERE a.asset_type = '医疗设备'
  AND (
    a.asset_name LIKE '%超声%' OR a.asset_name LIKE '%彩超%' OR a.asset_name LIKE '%B超%'
    OR a.model LIKE '%超声%' OR a.specification LIKE '%超声%'
    OR c.name = '医疗影像设备' OR c.code = 'YL-01'
  )
GROUP BY a.department
ORDER BY total_current_value DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询超声设备的维修工单",
            """
SELECT w.work_order_no, w.title, w.status, w.assigned_to, w.planned_start_date, w.planned_end_date
FROM maintenance_workorders w
JOIN assets a ON w.asset_code = a.asset_code
LEFT JOIN asset_categories c ON a.category_id = c.id
WHERE a.asset_type = '医疗设备'
  AND (
    a.asset_name LIKE '%超声%' OR a.asset_name LIKE '%彩超%' OR a.asset_name LIKE '%B超%'
    OR a.model LIKE '%超声%' OR a.specification LIKE '%超声%'
    OR c.name = '医疗影像设备' OR c.code = 'YL-01'
  )
ORDER BY w.created_at DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "按分类统计资产数量",
            """
SELECT c.name AS category_name, COUNT(*) AS asset_count
FROM assets a
LEFT JOIN asset_categories c ON a.category_id = c.id
GROUP BY c.name
ORDER BY asset_count DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询闲置资产发布中列表",
            """
SELECT ia.publish_date, ia.status, a.asset_code, a.asset_name, a.department, a.location
FROM idle_assets ia
JOIN assets a ON ia.asset_id = a.id
WHERE ia.status = '发布中'
ORDER BY ia.publish_date DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询盘点差异资产",
            """
SELECT ir.inventory_no, ir.inventory_date, a.asset_code, a.asset_name,
       idt.discrepancy_type, idt.discrepancy_desc
FROM inventory_details idt
JOIN inventory_records ir ON idt.inventory_id = ir.id
JOIN assets a ON idt.asset_id = a.id
WHERE idt.discrepancy_type <> '正常'
ORDER BY ir.inventory_date DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询待审批调配单",
            """
SELECT transfer_no, asset_id, from_department, to_department, transfer_date, status
FROM transfer_records
WHERE status = '待审批'
ORDER BY transfer_date DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询验收申请待审核",
            """
SELECT application_no, company_name, asset_name, purchase_amount, status, created_at
FROM acceptance_applications
WHERE status = '待审核'
ORDER BY created_at DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询验收不合格的资产",
            """
SELECT asset_code, asset_name, supplier, acceptance_date, status, department
FROM asset_acceptance_records
WHERE status = '验收不合格'
ORDER BY acceptance_date DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询不良事件待处理",
            """
SELECT report_no, asset_name, department, occurrence_date, severity, status
FROM adverse_reaction_records
WHERE status = '待处理'
ORDER BY occurrence_date DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询维修工单进行中",
            """
SELECT work_order_no, title, status, assigned_to, planned_start_date, planned_end_date
FROM maintenance_workorders
WHERE status = 'in_progress'
ORDER BY planned_start_date DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询即将到期计量设备",
            """
SELECT asset_code, asset_name, next_metrology_date, metrology_agency, status
FROM metrology_records
WHERE next_metrology_date IS NOT NULL
  AND next_metrology_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
ORDER BY next_metrology_date
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询即将到期质控设备",
            """
SELECT asset_code, asset_name, next_qc_date, qc_type, status
FROM quality_control_records
WHERE next_qc_date IS NOT NULL
  AND next_qc_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
ORDER BY next_qc_date
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询未处理质量预警",
            """
SELECT alert_type, asset_code, asset_name, alert_level, alert_date, due_date
FROM quality_management_alerts
WHERE is_handled = 0
ORDER BY alert_level DESC, alert_date DESC
LIMIT 1000;
            """.strip(),
        ),
        (
            "查询资产变更记录",
            """
SELECT asset_id, field_name, old_value, new_value, changed_by, changed_at
FROM asset_change_logs
ORDER BY changed_at DESC
LIMIT 1000;
            """.strip(),
        ),
    ]

    for question, sql in examples:
        try:
            create_training(
                session,
                DataTrainingInfo(question=question, description=sql, datasource=ds_id, enabled=True),
                oid,
                _trans,
                skip_embedding=True,
            )
            print(f"[training] created: {question}")
        except Exception as exc:
            print(f"[training] skip: {question} ({exc})")


def main() -> None:
    with Session(engine) as session:
        ds = _find_zcgl_datasource(session)
        if ds:
            print(f"[datasource] found: id={ds.id}, name={ds.name}")
            oid = ds.oid or 1
            ds_id = ds.id
        else:
            print("[datasource] zcgl not found, using global terminology only.")
            oid = 1
            ds_id = None

        _seed_terminology(session, oid, ds_id)
        _seed_training(session, oid, ds_id)


if __name__ == "__main__":
    main()
