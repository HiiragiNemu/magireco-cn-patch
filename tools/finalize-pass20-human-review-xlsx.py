from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description="Harden worksheet protection in the artifact-tool review workbook")
parser.add_argument(
    "--xlsx", type=Path,
    default=ROOT / "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx",
)
parser.add_argument(
    "--delivery", type=Path,
    default=ROOT / "outputs/019fd6ce-093f-7d63-ac45-ca01a7008cf8/magireco_v26_translation_review_1565.xlsx",
)
args = parser.parse_args()
XLSX = args.xlsx.resolve()
DELIVERY = args.delivery.resolve()
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("", NS)
q = lambda tag: f"{{{NS}}}{tag}"


with zipfile.ZipFile(XLSX, "r") as zin:
    infos = zin.infolist()
    if len(infos) != len({item.filename for item in infos}):
        raise SystemExit("duplicate XLSX member")
    blobs = {item.filename: zin.read(item.filename) for item in infos}
    if zin.testzip() is not None:
        raise SystemExit("input XLSX CRC failure")

workbook = ET.fromstring(blobs["xl/workbook.xml"])
rels = ET.fromstring(blobs["xl/_rels/workbook.xml.rels"])
targets = {
    rel.get("Id"): rel.get("Target", "").lstrip("/")
    for rel in rels.findall(f"{{{PKG_REL_NS}}}Relationship")
}
sheet_paths = {}
for sheet in workbook.findall(f"./{q('sheets')}/{q('sheet')}"):
    name = sheet.get("name", "")
    target = targets.get(sheet.get(f"{{{REL_NS}}}id", ""), "")
    if target not in blobs or not target.startswith("xl/worksheets/"):
        raise SystemExit(f"unsafe worksheet target: {name}")
    sheet_paths[name] = target
expected_sheets = {"人工审核1565"}
if set(sheet_paths) != expected_sheets:
    raise SystemExit(f"sheet set drifted: {set(sheet_paths)}")

styles = ET.fromstring(blobs["xl/styles.xml"])
cell_xfs = styles.find(q("cellXfs"))
if cell_xfs is None:
    raise SystemExit("cellXfs missing")
unlocked_cache = {}


def unlocked_style(base_id: int) -> int:
    if base_id in unlocked_cache:
        return unlocked_cache[base_id]
    xfs = list(cell_xfs)
    if not 0 <= base_id < len(xfs):
        raise SystemExit(f"invalid base style {base_id}")
    xf = deepcopy(xfs[base_id])
    xf.set("applyProtection", "1")
    xf.set("applyNumberFormat", "1")
    xf.set("numFmtId", "49")
    for old in list(xf):
        if old.tag == q("protection"):
            xf.remove(old)
    protection = ET.Element(q("protection"), {"locked": "0", "hidden": "0"})
    children = list(xf)
    alignment_index = next((i for i, child in enumerate(children) if child.tag == q("alignment")), None)
    if alignment_index is None:
        xf.append(protection)
    else:
        xf.insert(alignment_index + 1, protection)
    new_id = len(list(cell_xfs))
    cell_xfs.append(xf)
    cell_xfs.set("count", str(new_id + 1))
    unlocked_cache[base_id] = new_id
    return new_id


def cell_map(sheet: ET.Element) -> dict[str, ET.Element]:
    return {cell.get("r", ""): cell for cell in sheet.findall(f".//{q('c')}")}


def add_protection(sheet: ET.Element, *, allow_sort_filter: bool) -> None:
    for old in sheet.findall(q("sheetProtection")):
        sheet.remove(old)
    data = sheet.find(q("sheetData"))
    if data is None:
        raise SystemExit("sheetData missing")
    index = list(sheet).index(data) + 1
    attrs = {
        "sheet": "1", "objects": "1", "scenarios": "1", "formatCells": "1",
        "formatColumns": "1", "formatRows": "1", "insertColumns": "1", "insertRows": "1",
        "insertHyperlinks": "1", "deleteColumns": "1", "deleteRows": "1",
        "selectLockedCells": "1", "selectUnlockedCells": "0", "pivotTables": "1",
        "sort": "0" if allow_sort_filter else "1",
        "autoFilter": "0" if allow_sort_filter else "1",
    }
    sheet.insert(index, ET.Element(q("sheetProtection"), attrs))


def set_pane(sheet: ET.Element, attrs: dict[str, str], selections: list[dict[str, str]]) -> None:
    view = sheet.find(f"./{q('sheetViews')}/{q('sheetView')}")
    if view is None:
        raise SystemExit("sheetView missing")
    for child in list(view):
        if child.tag in {q("pane"), q("selection")}:
            view.remove(child)
    view.append(ET.Element(q("pane"), attrs))
    for selection in selections:
        view.append(ET.Element(q("selection"), selection))


def hide_columns(sheet: ET.Element, start: int, end: int) -> None:
    cols = sheet.find(q("cols"))
    if cols is None:
        data = sheet.find(q("sheetData"))
        if data is None:
            raise SystemExit("sheetData missing")
        cols = ET.Element(q("cols"))
        sheet.insert(list(sheet).index(data), cols)
    for col in list(cols):
        minimum = int(col.get("min", "0"))
        maximum = int(col.get("max", "0"))
        if minimum <= end and maximum >= start:
            cols.remove(col)
    cols.append(ET.Element(q("col"), {
        "min": str(start), "max": str(end), "width": "0", "hidden": "1", "customWidth": "1",
    }))


sheets = {name: ET.fromstring(blobs[path]) for name, path in sheet_paths.items()}
sheet = sheets["人工审核1565"]
cells = cell_map(sheet)
for row in range(2, 1567):
    ref = f"C{row}"
    cell = cells.get(ref)
    if cell is None:
        raise SystemExit(f"missing editable cell 人工审核1565!{ref}")
    cell.set("s", str(unlocked_style(int(cell.get("s", "0")))))
set_pane(sheet, {"ySplit": "1", "topLeftCell": "A2", "activePane": "bottomLeft", "state": "frozen"}, [
    {"pane": "bottomLeft", "activeCell": "C2", "sqref": "C2"},
])
hide_columns(sheet, 4, 14)
add_protection(sheet, allow_sort_filter=True)

blobs["xl/styles.xml"] = ET.tostring(styles, encoding="utf-8", xml_declaration=True)
for name, sheet in sheets.items():
    blobs[sheet_paths[name]] = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)

temporary = XLSX.with_suffix(".xlsx.tmp")
with zipfile.ZipFile(temporary, "w") as zout:
    for info in infos:
        zout.writestr(info, blobs[info.filename])
temporary.replace(XLSX)
DELIVERY.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(XLSX, DELIVERY)

with zipfile.ZipFile(XLSX, "r") as check:
    if check.testzip() is not None:
        raise SystemExit("output XLSX CRC failure")
    if len(check.namelist()) != len(set(check.namelist())):
        raise SystemExit("output XLSX duplicate member")
print("PASS: one-sheet 1565 workbook freeze/hide/unlock/protection hardened")
