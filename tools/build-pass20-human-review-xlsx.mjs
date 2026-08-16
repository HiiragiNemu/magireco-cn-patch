import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const toolDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(toolDir, "..");
const buildDir = path.join(root, "_artifacts/spreadsheet_build");
const artifactModule = process.env.OAI_ARTIFACT_TOOL_ENTRY
  ? await import(pathToFileURL(process.env.OAI_ARTIFACT_TOOL_ENTRY).href)
  : await import("@oai/artifact-tool");
const { SpreadsheetFile, Workbook } = artifactModule;
const inputPath = path.join(buildDir, "v26_translation_review_1565_input.json");
const canonicalPath = process.env.PASS20_XLSX_OUTPUT || path.join(
  root,
  "magica/i18n_audit/release_v26_authority/magireco_v26_translation_review_1565.xlsx",
);
const defaultDeliveryDir = path.join(root, "outputs/019fd6ce-093f-7d63-ac45-ca01a7008cf8");
const deliveryPath = process.env.PASS20_XLSX_DELIVERY || path.join(defaultDeliveryDir, "magireco_v26_translation_review_1565.xlsx");
const deliveryDir = path.dirname(deliveryPath);
const previewPaths = {
  instruction: path.join(buildDir, "v26_translation_review_1565_instructions.png"),
  priority: path.join(buildDir, "v26_translation_review_1565_priority.png"),
  approved: path.join(buildDir, "v26_translation_review_1565_approved.png"),
  excluded: path.join(buildDir, "v26_translation_review_1565_excluded.png"),
};

const input = JSON.parse(await fs.readFile(inputPath, "utf8"));
const expected = { inventory: 1589, human: 1565, priority: 199, approved: 1366, excluded: 347, authority: 323, shadowed: 24 };
for (const [key, value] of Object.entries(expected)) {
  if (input.counts?.[key] !== value) throw new Error(`count drift ${key}: ${input.counts?.[key]}`);
}
if (input.priority_rows.length !== expected.priority) throw new Error("priority rows drifted");
if (input.approved_rows.length !== expected.approved) throw new Error("approved rows drifted");
if (input.excluded_rows.length !== expected.excluded) throw new Error("excluded rows drifted");

const workbook = Workbook.create();
const instruction = workbook.worksheets.add("说明");
const priority = workbook.worksheets.add("①优先审核199");
const approved = workbook.worksheets.add("②DS已审1366");
const excluded = workbook.worksheets.add("只读排除347");
for (const sheet of [instruction, priority, approved, excluded]) sheet.showGridLines = false;

const navy = "#17365D";
const teal = "#0F6B78";
const paleBlue = "#EAF3F8";
const paleGold = "#FFF2CC";
const paleGreen = "#E2F0D9";
const paleRed = "#FCE4D6";
const palePurple = "#E4DFEC";
const grey = "#E7E6E6";
const bodyFont = { name: "Microsoft YaHei", size: 11, color: "#1F2937" };

instruction.mergeCells("A1:H2");
instruction.getRange("A1:H2").values = [["魔法纪录 JS v26 · 低权重译文人工审核（1,565 项）"]];
instruction.getRange("A1:H2").format = {
  fill: navy,
  font: { name: "Microsoft YaHei", size: 18, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
instruction.getRange("A1:H2").format.rowHeight = 30;

instruction.getRange("A4:B14").values = [
  ["机器来源总清单", expected.inventory],
  ["本工作簿需人工审核", expected.human],
  ["优先审核", expected.priority],
  ["DS已审但仍需人工", expected.approved],
  ["只读排除", expected.excluded],
  ["已填写决定", null],
  ["人工保留现译", null],
  ["采用DS建议", null],
  ["人工自行修改", null],
  ["暂时无法判断", null],
  ["剩余未填", null],
];
const pEnd = expected.priority + 1;
const aEnd = expected.approved + 1;
instruction.getRange("B9").formulas = [[`=COUNTA('①优先审核199'!O2:O${pEnd})+COUNTA('②DS已审1366'!O2:O${aEnd})`]];
instruction.getRange("B10").formulas = [[`=COUNTIF('①优先审核199'!O2:O${pEnd},"保留现译")+COUNTIF('②DS已审1366'!O2:O${aEnd},"保留现译")`]];
instruction.getRange("B11").formulas = [[`=COUNTIF('①优先审核199'!O2:O${pEnd},"采用建议")+COUNTIF('②DS已审1366'!O2:O${aEnd},"采用建议")`]];
instruction.getRange("B12").formulas = [[`=COUNTIF('①优先审核199'!O2:O${pEnd},"自行修改")+COUNTIF('②DS已审1366'!O2:O${aEnd},"自行修改")`]];
instruction.getRange("B13").formulas = [[`=COUNTIF('①优先审核199'!O2:O${pEnd},"暂时无法判断")+COUNTIF('②DS已审1366'!O2:O${aEnd},"暂时无法判断")`]];
instruction.getRange("B14").formulas = [["=B5-B9"]];
instruction.getRange("A4:A14").format = { fill: paleBlue, font: { ...bodyFont, bold: true, color: navy } };
instruction.getRange("B4:B14").format = {
  fill: "#FFFFFF", font: { ...bodyFont, bold: true }, horizontalAlignment: "center", numberFormat: "#,##0",
};
instruction.getRange("A4:B14").format.borders = { preset: "all", style: "thin", color: "#B8C7D1" };

instruction.mergeCells("D4:H14");
instruction.getRange("D4:H14").values = [[
  "操作方法\n\n1. 先完成“①优先审核199”，再检查“②DS已审1366”。\n2. DS已审通过不等于人工确认；这1,366项仍是最低权重机器来源。\n3. 只编辑黄色列：人工决定、最终中文、人工备注。\n4. 保留现译：认可当前机器译文；导入后会记录为“机器来源、人工已批准”。\n5. 采用建议：仅用于有建议中文的项目；最终中文可留空。\n6. 自行修改：必须在“最终中文”填写新译文。\n7. 暂时无法判断：保留争议，不会进入产品应用。\n8. 可自由排序和筛选；稳定ID与隐藏校验字段会确保逐项回填。\n9. 保存为新的XLSX并交回Codex；用户不运行脚本。"
]];
instruction.getRange("D4:H14").format = {
  fill: paleGold, font: bodyFont, wrapText: true, verticalAlignment: "top",
};
instruction.getRange("D4:H14").format.borders = { preset: "outside", style: "medium", color: "#D6B656" };
instruction.getRange("A4:H14").format.rowHeight = 34;

instruction.getRange("A17:B21").values = [
  ["人工输入", "填写内容"],
  ["审核人", null],
  ["审核时间（ISO 8601）", null],
  ["推荐时间格式", "示例：2026-08-16T22:30:00+08:00"],
  ["黄色单元格", "仅黄色单元格可编辑；其余内容均锁定"],
];
instruction.getRange("A17:B17").format = { fill: teal, font: { ...bodyFont, bold: true, color: "#FFFFFF" } };
instruction.getRange("A18:A21").format = { fill: paleBlue, font: { ...bodyFont, bold: true } };
instruction.getRange("B18:B19").format = { fill: paleGold, font: bodyFont };
instruction.getRange("B20:B21").format = { fill: "#F3F4F6", font: bodyFont };
instruction.getRange("A17:B21").format.borders = { preset: "all", style: "thin", color: "#B8C7D1" };

instruction.getRange("A24:B35").values = [
  ["页面", "含义"],
  ["①优先审核199", "29项DS纠错、34项DS未决、136项未完成DS审查；优先处理"],
  ["②DS已审1366", "DS认为当前译文可接受，但仍未经人工确认、仍属最低权重机器来源"],
  ["只读排除347", "323项已有高权威裁决，另24项机器候选被更高权威遮蔽；禁止人工回填机器候选"],
  ["frontend-strings.tsv", "全局原文映射：同一原文在多个界面使用同一译文"],
  ["overrides.tsv", "路径限定覆盖：同一原文在指定文件内使用特定译文"],
  ["fragments.tsv", "指定文件代码片段：处理跨节点语序或完整片段"],
  ["magica/", "最终运行时副本；工作簿本身不会直接修改产品文件"],
  ["人工队列", input.source_tsv],
  ["目标合同", input.target_manifest],
  ["封存源文本", input.sealed_review],
  ["工作簿结构", input.schema],
];
instruction.getRange("A24:A35").format = { fill: grey, font: { ...bodyFont, bold: true } };
instruction.getRange("B24:B35").format = { fill: "#F8F9FA", font: { name: "Microsoft YaHei", size: 9, color: "#374151" }, wrapText: true };
instruction.getRange("A24:B35").format.borders = { preset: "all", style: "thin", color: "#D1D5DB" };
instruction.getRange("A1:A35").format.columnWidth = 24;
instruction.getRange("B1:B35").format.columnWidth = 58;
instruction.getRange("C1:C35").format.columnWidth = 3;
instruction.getRange("D1:H35").format.columnWidth = 18;
instruction.freezePanes.freezeRows(2);

const headers = [
  "序号", "稳定ID", "原文（日文/源文）", "当前中文", "建议中文", "审查状态", "审查说明（含DS原始理由）",
  "维护层类型", "维护表", "原文键", "路径前缀", "产品目标路径", "匹配次数", "上下文片段",
  "人工决定", "最终中文", "人工备注", "__source_text_sha256", "__source_record_sha256",
  "__target_contract_sha256", "__target_row_sha256", "__stable_business_key", "__target_manifest_index", "__schema_version", "__partition",
];
const excelCellText = (value) => typeof value === "string" ? value.replace(/[ \t\r\n]+$/u, "") : value;
const literal = (value) => {
  const normalized = excelCellText(value);
  return typeof normalized === "string" && normalized.startsWith("=") ? `'${normalized}` : normalized;
};
const decisionLabels = ["保留现译", "采用建议", "自行修改", "暂时无法判断"];

function buildReviewSheet(sheet, rows, tableName, verdictColor) {
  const end = rows.length + 1;
  const values = [headers];
  for (const row of rows) {
    const displayContext = `${row.match_status}\n${row.context_snippets}`.replace(/[ \r\n]+$/u, "");
    values.push([
      row.sequence, row.item_id, literal(row.original), literal(row.current_cn), literal(row.suggested_cn),
      row.parent_verdict_display, literal(row.review_explanation), row.maintenance_layer_type,
      row.maintenance_table, row.source_key, row.path_prefix, literal(row.product_target_paths),
      row.match_count, literal(displayContext), null, null, null,
      row.source_text_sha256, row.source_record_sha256, input.target_contract_sha256,
      row.target_row_sha256, row.stable_business_key, row.target_manifest_index, input.schema, row.partition,
    ]);
  }
  sheet.getRange(`A1:Y${end}`).values = values;
  sheet.getRange("A1:Q1").format = {
    fill: navy, font: { name: "Microsoft YaHei", size: 11, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
  };
  sheet.getRange(`A2:Q${end}`).format = { font: bodyFont, verticalAlignment: "top", wrapText: true };
  sheet.getRange(`A2:B${end}`).format.horizontalAlignment = "center";
  sheet.getRange(`F2:F${end}`).format = { horizontalAlignment: "center", fill: verdictColor };
  sheet.getRange(`M2:M${end}`).format.horizontalAlignment = "center";
  sheet.getRange(`O2:O${end}`).format = { fill: paleGold, font: { ...bodyFont, bold: true }, horizontalAlignment: "center" };
  sheet.getRange(`P2:Q${end}`).format = { fill: paleGold, font: bodyFont, wrapText: true };
  sheet.getRange(`A2:Q${end}`).format.rowHeight = 78;
  sheet.getRange(`O2:O${end}`).dataValidation = { rule: { type: "list", values: decisionLabels } };
  for (const [label, fill, color] of [
    ["保留现译", paleGreen, "#375623"], ["采用建议", palePurple, "#5F497A"],
    ["自行修改", "#DDEBF7", "#1F4E78"], ["暂时无法判断", paleRed, "#9C0006"],
  ]) {
    sheet.getRange(`O2:O${end}`).conditionalFormats.add("containsText", {
      text: label, format: { fill, font: { color, bold: true } },
    });
  }
  sheet.getRange(`A1:A${end}`).format.columnWidth = 7;
  sheet.getRange(`B1:B${end}`).format.columnWidth = 19;
  sheet.getRange(`C1:E${end}`).format.columnWidth = 38;
  sheet.getRange(`F1:F${end}`).format.columnWidth = 31;
  sheet.getRange(`G1:G${end}`).format.columnWidth = 52;
  sheet.getRange(`H1:H${end}`).format.columnWidth = 16;
  sheet.getRange(`I1:I${end}`).format.columnWidth = 28;
  sheet.getRange(`J1:J${end}`).format.columnWidth = 25;
  sheet.getRange(`K1:K${end}`).format.columnWidth = 30;
  sheet.getRange(`L1:L${end}`).format.columnWidth = 42;
  sheet.getRange(`M1:M${end}`).format.columnWidth = 10;
  sheet.getRange(`N1:N${end}`).format.columnWidth = 54;
  sheet.getRange(`O1:O${end}`).format.columnWidth = 20;
  sheet.getRange(`P1:P${end}`).format.columnWidth = 40;
  sheet.getRange(`Q1:Q${end}`).format.columnWidth = 34;
  sheet.getRange(`R1:Y${end}`).format.columnHidden = true;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(2);
  const table = sheet.tables.add(`A1:Y${end}`, true, tableName);
  table.style = "TableStyleMedium2";
  table.showFilterButton = true;
}

buildReviewSheet(priority, input.priority_rows, "V26PriorityReviewTable", paleRed);
buildReviewSheet(approved, input.approved_rows, "V26ApprovedReviewTable", paleBlue);

const excludedHeaders = [
  "序号", "稳定ID", "排除原因", "原文（日文/源文）", "机器候选", "高权威／最终中文", "权威层级", "权威证据",
  "来源位置", "产品回填状态", "__source_record_sha256", "__excluded_row_sha256", "__excluded_row_json", "__schema_version",
];
const excludedValues = [excludedHeaders];
for (const row of input.excluded_rows) {
  excludedValues.push([
    row.sequence, row.item_id, row.exclusion_reason, literal(row.original), literal(row.machine_candidate),
    literal(row.authority_value), row.authority_tier, literal(row.authority_evidence), row.source_location,
    "禁止机器候选回填", row.source_record_sha256, row.excluded_row_sha256, row.excluded_row_json, input.schema,
  ]);
}
const xEnd = expected.excluded + 1;
excluded.getRange(`A1:N${xEnd}`).values = excludedValues;
excluded.getRange("A1:J1").format = {
  fill: navy, font: { name: "Microsoft YaHei", size: 11, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
};
excluded.getRange(`A2:J${xEnd}`).format = { font: bodyFont, verticalAlignment: "top", wrapText: true, fill: "#F8F9FA" };
excluded.getRange(`C2:C${xEnd}`).format = { fill: paleGreen, font: { ...bodyFont, bold: true, color: "#375623" } };
excluded.getRange(`J2:J${xEnd}`).format = { fill: grey, font: { ...bodyFont, bold: true }, horizontalAlignment: "center" };
excluded.getRange(`A2:J${xEnd}`).format.rowHeight = 68;
excluded.getRange(`A1:A${xEnd}`).format.columnWidth = 7;
excluded.getRange(`B1:B${xEnd}`).format.columnWidth = 19;
excluded.getRange(`C1:C${xEnd}`).format.columnWidth = 29;
excluded.getRange(`D1:F${xEnd}`).format.columnWidth = 40;
excluded.getRange(`G1:G${xEnd}`).format.columnWidth = 24;
excluded.getRange(`H1:H${xEnd}`).format.columnWidth = 52;
excluded.getRange(`I1:I${xEnd}`).format.columnWidth = 38;
excluded.getRange(`J1:J${xEnd}`).format.columnWidth = 22;
excluded.getRange(`K1:N${xEnd}`).format.columnHidden = true;
excluded.freezePanes.freezeRows(1);
excluded.freezePanes.freezeColumns(2);
const excludedTable = excluded.tables.add(`A1:N${xEnd}`, true, "V26ExcludedAuthorityTable");
excludedTable.style = "TableStyleMedium4";
excludedTable.showFilterButton = true;

const inspectChunks = [];
for (const request of [
  { kind: "table", range: "说明!A1:H35", include: "values,formulas", tableMaxRows: 35, tableMaxCols: 8, maxChars: 6000 },
  { kind: "table", range: "①优先审核199!A1:Q5", include: "values,formulas", tableMaxRows: 5, tableMaxCols: 17, maxChars: 5000 },
  { kind: "table", range: "②DS已审1366!A1:Q5", include: "values,formulas", tableMaxRows: 5, tableMaxCols: 17, maxChars: 5000 },
  { kind: "table", range: "只读排除347!A1:J5", include: "values,formulas", tableMaxRows: 5, tableMaxCols: 10, maxChars: 4000 },
]) {
  inspectChunks.push((await workbook.inspect(request)).ndjson);
}
const errors = await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 200 }, summary: "final formula error scan",
});
inspectChunks.push(errors.ndjson);
await fs.writeFile(path.join(buildDir, "v26_translation_review_1565.inspect.ndjson"), inspectChunks.join("\n"), "utf8");

for (const [key, options] of Object.entries({
  instruction: { sheetName: "说明", range: "A1:H35", scale: 1.25 },
  priority: { sheetName: "①优先审核199", range: "A1:Q7", scale: 1.1 },
  approved: { sheetName: "②DS已审1366", range: "A1:Q7", scale: 1.1 },
  excluded: { sheetName: "只读排除347", range: "A1:J7", scale: 1.1 },
})) {
  const preview = await workbook.render({ ...options, format: "png" });
  await fs.writeFile(previewPaths[key], new Uint8Array(await preview.arrayBuffer()));
}

await fs.mkdir(path.dirname(canonicalPath), { recursive: true });
await fs.mkdir(deliveryDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(canonicalPath);
await fs.copyFile(canonicalPath, deliveryPath);
console.log(JSON.stringify({ status: "PASS", canonicalPath, deliveryPath, counts: input.counts, previewPaths }));
