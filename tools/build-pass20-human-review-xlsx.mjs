import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const toolDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(toolDir, "..");
const buildDir = path.join(root, "_artifacts/spreadsheet_build");
const reviewCount = 1564;
const workbookFileName = `magireco_v26_translation_review_${reviewCount}.xlsx`;
const inputFileName = `v26_translation_review_${reviewCount}_input.json`;
const previewFileName = `v26_translation_review_${reviewCount}_review.png`;
const inspectFileName = `v26_translation_review_${reviewCount}.inspect.ndjson`;
const reviewSheetName = `人工审核${reviewCount}`;
const artifactModule = process.env.OAI_ARTIFACT_TOOL_ENTRY
  ? await import(pathToFileURL(process.env.OAI_ARTIFACT_TOOL_ENTRY).href)
  : await import("@oai/artifact-tool");
const { SpreadsheetFile, Workbook } = artifactModule;
const inputPath = path.join(buildDir, inputFileName);
const canonicalPath = process.env.PASS20_XLSX_OUTPUT || path.join(
  root,
  "magica/i18n_audit/release_v26_authority",
  workbookFileName,
);
const defaultDeliveryDir = path.join(root, "outputs/019fd6ce-093f-7d63-ac45-ca01a7008cf8");
const deliveryPath = process.env.PASS20_XLSX_DELIVERY || path.join(
  defaultDeliveryDir,
  workbookFileName,
);
const deliveryDir = path.dirname(deliveryPath);
const previewPath = path.join(buildDir, previewFileName);

const input = JSON.parse(await fs.readFile(inputPath, "utf8"));
if (input.schema !== "magireco-cn-v26-translation-human-review-workbook/5") {
  throw new Error(`workbook input schema drifted: ${input.schema}`);
}
const expected = {
  inventory: 1589,
  human: reviewCount,
  priority: 199,
  approved: 1365,
  excluded: 348,
  authority: 323,
  shadowed: 25,
};
for (const [key, value] of Object.entries(expected)) {
  if (input.counts?.[key] !== value) throw new Error(`count drift ${key}: ${input.counts?.[key]}`);
}
if (!Array.isArray(input.review_rows) || input.review_rows.length !== expected.human) {
  throw new Error("review rows drifted");
}
if (Object.hasOwn(input, "priority_rows") || Object.hasOwn(input, "approved_rows") || Object.hasOwn(input, "excluded_rows")) {
  throw new Error("legacy workbook partitions must remain outside the one-sheet input");
}

const headers = [
  "日文原文",
  "旧中文",
  "最终中文",
  "__item_id",
  "__seed_origin",
  "__seed_final_sha256",
  "__source_text_sha256",
  "__source_record_sha256",
  "__target_contract_sha256",
  "__target_row_sha256",
  "__stable_business_key",
  "__target_manifest_index",
  "__schema_version",
  "__partition",
];
const excelCellText = (value) => typeof value === "string" ? value.replace(/[ \t\r\n]+$/u, "") : value;
const literal = (value) => {
  const normalized = excelCellText(value);
  return typeof normalized === "string" && normalized.startsWith("=") ? `'${normalized}` : normalized;
};

const workbook = Workbook.create();
if (
  input.workbook?.file_name !== workbookFileName
  || input.workbook?.sheet_name !== reviewSheetName
  || input.workbook?.input_name !== inputFileName
) {
  throw new Error("workbook identity contract drifted");
}
const sheet = workbook.worksheets.add(reviewSheetName);
sheet.showGridLines = false;

const values = [headers];
for (const row of input.review_rows) {
  values.push([
    literal(row.original),
    literal(row.current_cn),
    literal(row.final_seed),
    row.item_id,
    row.seed_origin,
    row.seed_final_sha256,
    row.source_text_sha256,
    row.source_record_sha256,
    input.target_contract_sha256,
    row.target_row_sha256,
    row.stable_business_key,
    row.target_manifest_index,
    input.schema,
    row.partition,
  ]);
}

const end = expected.human + 1;
sheet.getRange(`A1:N${end}`).values = values;
sheet.getRange("A1:N1").format = {
  fill: "#17365D",
  font: { name: "Microsoft YaHei", size: 11, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
sheet.getRange(`A2:C${end}`).format = {
  font: { name: "Microsoft YaHei", size: 11, color: "#1F2937" },
  verticalAlignment: "top",
  wrapText: true,
};
sheet.getRange(`A2:B${end}`).format.fill = "#EAF3F8";
sheet.getRange(`C2:C${end}`).format = {
  fill: "#FFF2CC",
  font: { name: "Microsoft YaHei", size: 11, bold: true, color: "#1F2937" },
  verticalAlignment: "top",
  wrapText: true,
};
sheet.getRange(`A2:C${end}`).format.borders = {
  insideHorizontal: { style: "thin", color: "#D7E1E8" },
  insideVertical: { style: "thin", color: "#D7E1E8" },
};
sheet.getRange(`A2:C${end}`).format.rowHeight = 66;
sheet.getRange(`A1:A${end}`).format.columnWidth = 58;
sheet.getRange(`B1:C${end}`).format.columnWidth = 52;
sheet.getRange(`D1:N${end}`).format.columnHidden = true;
sheet.freezePanes.freezeRows(1);
const table = sheet.tables.add(`A1:N${end}`, true, "V26HumanReviewTable");
table.style = "TableStyleMedium2";
table.showFilterButton = true;

const inspectChunks = [];
inspectChunks.push((await workbook.inspect({
  kind: "table",
  range: `${reviewSheetName}!A1:C7`,
  include: "values,formulas",
  tableMaxRows: 7,
  tableMaxCols: 3,
  maxChars: 6000,
})).ndjson);
inspectChunks.push((await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 200 },
  summary: "final formula error scan",
})).ndjson);
await fs.writeFile(
  path.join(buildDir, inspectFileName),
  inspectChunks.join("\n"),
  "utf8",
);

const preview = await workbook.render({
  sheetName: reviewSheetName,
  range: "A1:C7",
  scale: 1.15,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(path.dirname(canonicalPath), { recursive: true });
await fs.mkdir(deliveryDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(canonicalPath);
await fs.copyFile(canonicalPath, deliveryPath);
console.log(JSON.stringify({
  status: "PASS",
  canonicalPath,
  deliveryPath,
  counts: input.counts,
  prefilledFromSuggestion: input.review_rows.filter((row) => row.seed_origin === "adopted_suggestion").length,
  prefilledFromCurrent: input.review_rows.filter((row) => row.seed_origin === "current").length,
  previewPath,
}));
