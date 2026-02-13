"""
数据库描述文件解析器 - 修复版
解析 数据库描述.md 文件，提取表结构、字段、枚举值、业务说明等信息
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TableField:
    """表字段信息"""
    name: str
    field_type: str
    nullable: bool
    default: Optional[str]
    comment: str
    field_group: str = ""


@dataclass
class TableInfo:
    """表信息"""
    table_name: str
    table_comment: str
    engine: str = "InnoDB"
    charset: str = "utf8mb4"
    fields: List[TableField] = field(default_factory=list)
    indexes: List[Dict[str, Any]] = field(default_factory=list)
    foreign_keys: List[Dict[str, str]] = field(default_factory=dict)
    enums: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    business_notes: str = ""
    preinstall_data: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """模块信息"""
    module_name: str
    module_description: str = ""
    tables: List[TableInfo] = field(default_factory=list)


class DatabaseDescriptionParser:
    """数据库描述文件解析器"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.content = ""
        self.modules: List[ModuleInfo] = []

    def load_content(self):
        """加载文件内容"""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            self.content = f.read()

    def _is_module_header(self, line: str) -> bool:
        """判断是否是模块标题行（## 开头）"""
        stripped = line.strip()
        return stripped.startswith('## ')

    def _is_table_header(self, line: str) -> bool:
        """判断是否是表标题行（### 开头，后面有括号包含表名）"""
        stripped = line.strip()
        if stripped.startswith('### '):
            if '(' in stripped and ')' in stripped:
                return True
        return False

    def _get_next_header_level(self, line: str) -> int:
        """获取标题级别（#的数量）"""
        stripped = line.strip()
        for i, char in enumerate(stripped):
            if char != '#':
                return i
        return len(stripped) if stripped.startswith('#') else 0

    def _extract_table_name_and_comment(self, line: str) -> tuple:
        """从表标题行提取表名和注释"""
        match = re.search(r'###\s*[\d\.]+\s*(.+)\(([^)]+)\)', line)
        if match:
            comment = match.group(1).strip()
            name = match.group(2).strip()
            return name, comment
        return "", line.strip()

    def _extract_module_name(self, line: str) -> str:
        """从模块标题行提取模块名"""
        match = re.search(r'##\s*(.+)', line)
        if match:
            return match.group(1).strip()
        return line.strip()

    def parse(self) -> List[ModuleInfo]:
        """解析文件，返回模块列表"""
        self.load_content()
        lines = self.content.split('\n')

        current_module = None
        current_table = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            header_level = self._get_next_header_level(line)

            if header_level == 2:
                if current_module and current_module.tables:
                    self.modules.append(current_module)

                module_name = self._extract_module_name(line)

                description = ""
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line.startswith('#'):
                        break
                    if next_line and not next_line.startswith('|') and not next_line.startswith('-'):
                        description = next_line
                        break

                current_module = ModuleInfo(
                    module_name=module_name,
                    module_description=description
                )
                current_table = None

            elif header_level == 3 and '(' in line and ')' in line:
                if current_table and current_table.fields:
                    if current_module:
                        current_module.tables.append(current_table)

                table_name, table_comment = self._extract_table_name_and_comment(line)

                current_table = TableInfo(
                    table_name=table_name,
                    table_comment=table_comment
                )

            elif current_table:
                self._parse_table_content(current_table, line, lines, i)

            i += 1

        if current_module and current_module.tables:
            self.modules.append(current_module)

        return self.modules

    def _parse_table_content(self, table: TableInfo, line: str, lines: List[str], i: int):
        """解析表的详细内容"""
        if not table:
            return

        line_lower = line.lower()

        if '| 属性 |' in line and '| 值 |' in line:
            for j in range(i + 1, min(i + 10, len(lines))):
                content_line = lines[j].strip()
                if not content_line.startswith('|'):
                    break
                cells = [c.strip() for c in content_line.split('|')[1:-1]]
                if len(cells) >= 2:
                    if cells[0] == '引擎':
                        table.engine = cells[1]
                    elif cells[0] == '字符集':
                        table.charset = cells[1]

        elif line.startswith('| 字段名 |'):
            field_lines = []
            j = i + 1
            while j < len(lines):
                content_line = lines[j].strip()
                if not content_line.startswith('|'):
                    break
                if '|-------|------|' in content_line or '|-----+------|' in content_line:
                    j += 1
                    continue
                field_lines.append(content_line)
                j += 1

            current_group = ""
            for field_line in field_lines:
                if '**' in field_line and field_line.count('**') >= 2:
                    group_match = re.match(r'\*\*(.+?)\*\*', field_line)
                    if group_match:
                        current_group = group_match.group(1).strip()
                        continue

                cells = [c.strip() for c in field_line.split('|')[1:-1]]
                if len(cells) >= 5:
                    try:
                        field = TableField(
                            name=cells[0],
                            field_type=cells[1],
                            nullable=cells[2] == 'YES' if cells[2] else True,
                            default=cells[3] if cells[3] and cells[3] != 'NULL' else None,
                            comment=cells[4],
                            field_group=current_group
                        )
                        table.fields.append(field)
                    except Exception:
                        continue

        elif line.startswith('#### ') and '枚举值说明' in line:
            enum_type = ""

            enum_match = re.search(r'\*\*(.+?)\*\*', line)
            if enum_match:
                enum_type_line = enum_match.group(1).strip()
                enum_type_match = re.match(r'([^\(（]+)[(（]([^)）]+)[)）]', enum_type_line)
                if enum_type_match:
                    enum_type = enum_type_match.group(2).strip()
                else:
                    enum_type = enum_type_line

            enum_values = []
            j = i + 1
            while j < len(lines):
                content_line = lines[j].strip()

                if content_line.startswith('**') and '（' in content_line or '(' in content_line:
                    if enum_values and enum_type:
                        table.enums[enum_type] = enum_values
                    enum_type_match = re.search(r'\*\*(.+?)\*\*', content_line)
                    if enum_type_match:
                        type_str = enum_type_match.group(1).strip()
                        paren_match = re.match(r'([^\(（]+)[(（]([^)）]+)[)）]', type_str)
                        if paren_match:
                            enum_type = paren_match.group(2).strip()
                        else:
                            enum_type = type_str
                    enum_values = []
                elif content_line.startswith('- '):
                    val_line = content_line[2:].strip()
                    if '：' in val_line:
                        parts = val_line.split('：', 1)
                        enum_values.append({'value': parts[0].strip(), 'description': parts[1].strip()})
                    elif ':' in val_line:
                        parts = val_line.split(':', 1)
                        enum_values.append({'value': parts[0].strip(), 'description': parts[1].strip()})
                    else:
                        enum_values.append({'value': val_line, 'description': ''})
                elif content_line.startswith('|') and '|' in content_line[1:]:
                    cells = [c.strip() for c in content_line.split('|')[1:-1]]
                    if len(cells) >= 2:
                        val = cells[0].strip()
                        desc = cells[1].strip() if len(cells) > 1 else ""
                        if val and val not in ['NULL', '-', '']:
                            if '：' in desc:
                                parts = desc.split('：', 1)
                                enum_values.append({'value': val, 'description': parts[1].strip()})
                            else:
                                enum_values.append({'value': val, 'description': desc})
                elif content_line.startswith('---') or content_line == '' or content_line.startswith('####') or content_line.startswith('###'):
                    if enum_values and enum_type:
                        table.enums[enum_type] = enum_values
                    enum_values = []
                    enum_type = ""
                    if content_line.startswith('####') or content_line.startswith('###'):
                        break
                j += 1

            if enum_values and enum_type:
                table.enums[enum_type] = enum_values

        elif line.startswith('| 索引名 |'):
            index_lines = []
            j = i + 1
            while j < len(lines):
                content_line = lines[j].strip()
                if not content_line.startswith('|'):
                    break
                index_lines.append(content_line)
                j += 1

            for index_line in index_lines:
                cells = [c.strip() for c in index_line.split('|')[1:-1]]
                if len(cells) >= 3:
                    table.indexes.append({
                        'name': cells[0],
                        'type': cells[1],
                        'fields': cells[2]
                    })

        elif '外键关系' in line_lower or ('引用' in line_lower and '删除规则' in line):
            fk_lines = []
            j = i + 1
            while j < len(lines):
                content_line = lines[j].strip()
                if not content_line.startswith('|'):
                    break
                fk_lines.append(content_line)
                j += 1

            for fk_line in fk_lines:
                cells = [c.strip() for c in fk_line.split('|')[1:-1]]
                if len(cells) >= 4:
                    table.foreign_keys.append({
                        'field': cells[0],
                        'ref_table': cells[1],
                        'ref_field': cells[2],
                        'delete_rule': cells[3]
                    })

        elif '预置数据' in line or ('编码' in line and '名称' in line and '|' in line):
            data_lines = []
            j = i + 1
            while j < len(lines):
                content_line = lines[j].strip()
                if not content_line.startswith('|'):
                    break
                data_lines.append(content_line)
                j += 1

            for data_line in data_lines:
                cells = [c.strip() for c in data_line.split('|')[1:-1]]
                if len(cells) >= 4:
                    table.preinstall_data.append({
                        'code': cells[0],
                        'name': cells[1],
                        'parent': cells[2],
                        'description': cells[3]
                    })

    def get_schema_summary(self) -> str:
        """生成数据库Schema摘要"""
        summary_lines = ["# 数据库架构摘要\n"]
        summary_lines.append(f"模块总数: {len(self.modules)}\n")

        total_tables = sum(len(m.tables) for m in self.modules)
        summary_lines.append(f"数据表总数: {total_tables}\n")

        for module in self.modules:
            summary_lines.append(f"\n## {module.module_name}")
            summary_lines.append(f"表数量: {len(module.tables)}")

            for table in module.tables:
                summary_lines.append(f"\n### {table.table_name}")
                summary_lines.append(f"说明: {table.table_comment}")

                field_count = len([f for f in table.fields if f.name not in ['id', 'created_at', 'updated_at', 'created_by', 'updated_by', 'tenant_id']])
                summary_lines.append(f"业务字段数: {field_count}")

                if table.enums:
                    enum_info = ', '.join([f"{k}({len(v)})" for k, v in table.enums.items()])
                    summary_lines.append(f"枚举类型: {enum_info}")

        return '\n'.join(summary_lines)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/cjlee/Desktop/Project/SQLbot/backend')

    parser = DatabaseDescriptionParser("/Users/cjlee/Desktop/Project/SQLbot/backend/数据库描述.md")
    modules = parser.parse()

    print('='*70)
    print(f'✅ 解析成功！共 {len(modules)} 个模块')
    print('='*70)

    total_tables = 0
    total_fields = 0
    total_enums = 0

    for module in modules:
        print(f'\n📦 模块: {module.module_name}')
        print(f'   包含 {len(module.tables)} 个表:')
        total_tables += len(module.tables)

        for table in module.tables[:3]:
            field_count = len([f for f in table.fields if f.name not in ['id', 'created_at', 'updated_at']])
            total_fields += field_count
            total_enums += len(table.enums)

            print(f'      - {table.table_name} ({table.table_comment})')
            print(f'        字段: {len(table.fields)}, 枚举: {len(table.enums)}')

            if table.enums:
                enum_names = list(table.enums.keys())[:3]
                print(f'        枚举类型: {enum_names}')

        if len(module.tables) > 3:
            print(f'      ... 还有 {len(module.tables) - 3} 个表')

    print('\n' + '='*70)
    print(f'📊 统计:')
    print(f'   模块数: {len(modules)}')
    print(f'   表总数: {total_tables}')
    print(f'   字段总数: {total_fields}')
    print(f'   枚举类型总数: {total_enums}')
    print('='*70)
