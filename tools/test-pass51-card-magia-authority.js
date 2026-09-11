#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const libs = path.join(root, "magica", "js", "libs");
const runtimePath = path.join(libs, "runtimeNameMap.json");
const canonicalPath = path.join(libs, "cardMagiaMap.json");
const jqueryPath = path.join(libs, "jquery-3.7.1.min.js");
const officialRoot = process.argv[2] ||
  "D:\\magia\\MyProducts\\MAGIA RECORD CN\\Full_Raw_Dump_V2\\magica\\api\\page";

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
}

function composite(id, source) {
  return JSON.stringify(["CARD_MAGIA", String(id), source]);
}

function extractPayload(source) {
  const marker = "var cn = ";
  const start = source.indexOf(marker);
  if (start < 0) throw new Error("jQuery dictionary payload marker missing");
  let i = start + marker.length;
  const payloadStart = i;
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (; i < source.length; i += 1) {
    const ch = source[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === "\\") escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') inString = true;
    else if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) return JSON.parse(source.slice(payloadStart, i + 1));
    }
  }
  throw new Error("jQuery dictionary payload did not terminate");
}

function extractFunction(source, name) {
  const marker = `function ${name}(`;
  const start = source.indexOf(marker);
  if (start < 0) throw new Error(`${name} missing from jQuery runtime`);
  const body = source.indexOf("{", start);
  let depth = 0;
  let inString = false;
  let quote = "";
  let escaped = false;
  for (let i = body; i < source.length; i += 1) {
    const ch = source[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (ch === "\\") escaped = true;
      else if (ch === quote) inString = false;
      continue;
    }
    if (ch === '"' || ch === "'") {
      inString = true;
      quote = ch;
    } else if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error(`${name} did not terminate`);
}

function findOfficialNames(value, output = [], fieldPath = "") {
  if (Array.isArray(value)) {
    value.forEach((item, index) => findOfficialNames(item, output, `${fieldPath}/${index}`));
  } else if (value && typeof value === "object") {
    if (value.id !== undefined && typeof value.name === "string" &&
        fieldPath.endsWith("/cardMagia") &&
        Object.prototype.hasOwnProperty.call(expected, String(value.id))) {
      output.push([String(value.id), value.name]);
    }
    for (const [key, child] of Object.entries(value)) {
      findOfficialNames(child, output, `${fieldPath}/${key}`);
    }
  }
  return output;
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const expected = {
  "20014": { source: "プルウィア☆マギカ", target: "魔法☆之雨", file: "ShopTop_001.json" },
  "20015": { source: "プルウィア☆マギカ", target: "魔法☆之雨", file: "MyPage_001.json" },
  "20054": { source: "ティロ・フィナーレ", target: "Tiro·Finale（最终射击）", file: "ShopTop_001.json" },
  "20055": { source: "ティロ・フィナーレ", target: "Tiro·Finale（最终射击）", file: "ArenaFreeRank_001.json" },
};

const runtime = readJson(runtimePath);
const canonical = readJson(canonicalPath);
const official = new Map();
for (const [id, spec] of Object.entries(expected)) {
  const officialRows = findOfficialNames(readJson(path.join(officialRoot, spec.file)))
    .filter(([rowId]) => rowId === id);
  for (const [, name] of officialRows) {
    if (official.has(id) && official.get(id) !== name) {
      throw new Error(`official cardMagia id=${id} has conflicting names`);
    }
    official.set(id, name);
  }
}

for (const [id, spec] of Object.entries(expected)) {
  const key = composite(id, spec.source);
  const rule = runtime[key];
  assert(rule, `runtime rule missing: ${key}`);
  assert(rule.source === spec.source, `runtime source drift: ${id}`);
  assert(rule.target === spec.target, `runtime target drift: ${id}`);
  assert(rule.sourceTier === "official-cn-exact-field", `sourceTier drift: ${id}`);
  assert(rule.evidence === `Full_Raw_Dump_V2/magica/api/page/${spec.file}#cardMagia[id=${id}].name`, `evidence drift: ${id}`);
  assert(canonical[id] && canonical[id].name === spec.target, `canonical/runtime conflict: ${id}`);
  assert(official.get(id) === spec.target, `official/runtime conflict: ${id}`);
}

const jquerySource = fs.readFileSync(jqueryPath, "utf8");
const payload = extractPayload(jquerySource);
for (const [id, spec] of Object.entries(expected)) {
  const rule = payload.runtimeNameMap[composite(id, spec.source)];
  assert(rule && rule.target === spec.target, `rebuilt jQuery target mismatch: ${id}`);
}

const sandbox = { cn: { runtimeNameMap: payload.runtimeNameMap }, JSON, Object, String };
vm.createContext(sandbox);
vm.runInContext(`${extractFunction(jquerySource, "applyStableNameRule")}; this.applyStableNameRule = applyStableNameRule;`, sandbox);

for (const [id, spec] of Object.entries(expected)) {
  const positive = { id: Number(id), name: spec.source };
  sandbox.applyStableNameRule(positive, "card/cardMagia", "cardmagia");
  assert(positive.name === spec.target, `runtime positive fixture failed: ${id}`);

  const wrongSource = { id: Number(id), name: `${spec.source}X` };
  sandbox.applyStableNameRule(wrongSource, "card/cardMagia", "cardmagia");
  assert(wrongSource.name === `${spec.source}X`, `wrong source changed: ${id}`);
}

const unknown = { id: 29999, name: "プルウィア☆マギカ" };
sandbox.applyStableNameRule(unknown, "card/cardMagia", "cardmagia");
assert(unknown.name === "プルウィア☆マギカ", "unknown id changed");

console.log("PASS51_CARD_MAGIA_AUTHORITY=PASS");
console.log("OFFICIAL_EXACT=4");
console.log("CANONICAL_RUNTIME_CONFLICTS=0");
console.log("POSITIVE_FIXTURES=4");
console.log("WRONG_SOURCE_UNCHANGED=4");
console.log("UNKNOWN_ID_UNCHANGED=1");
console.log("INDEPENDENT_STABLE_IDS=4");
