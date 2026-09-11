"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const supportPath = path.join(root, "magica/template/quest/SupportSelect.html");
const battlePath = path.join(root, "magica/template/quest/QuestBattleSelect.html");
const support = fs.readFileSync(supportPath, "utf8");
const battle = fs.readFileSync(battlePath, "utf8");

const supportMatches = [...support.matchAll(/<%="<%= ((?:\(function\(v\).*?\)\(model\.chapterNoForView\))) %\\>"%>/g)];
assert.strictEqual(supportMatches.length, 2, "SupportSelect chapter expression count");
const battleMatch = battle.match(/<span class="chapterNo"><%= ((?:\(function\(v\).*?\)\(model\.chapterNoForView\))) %>：<\/span>/);
assert(battleMatch, "QuestBattleSelect chapter expression missing");

// SupportSelect is a template that emits another template, so its regex slashes
// are escaped once in the outer JavaScript string. Decode only that one layer.
const expressions = supportMatches.map((m) => m[1].replace(/\\\\/g, "\\"));
expressions.push(battleMatch[1]);

const fixtures = [
  ["10", "第10章", "numeric chapter 10"],
  ["第10章", "第10章", "official chapter 10 already wrapped"],
  [" 10 ", "第10章", "numeric chapter 10 with whitespace"],
  [" 第10章 ", "第10章", "official chapter 10 with whitespace"],
  ["9", "第9章", "other numeric chapter"],
  ["第9章", "第9章", "other wrapped chapter"],
  ["默示天灾", "默示天灾", "unknown non-chapter title unchanged"],
  [" 第第10章章 ", " 第第10章章 ", "unknown malformed value unchanged"],
];

for (const expression of expressions) {
  for (const [input, expected, label] of fixtures) {
    const output = vm.runInNewContext(expression, { model: { chapterNoForView: input } });
    assert.strictEqual(output, expected, `${label}: ${expression}`);
  }
}

const official = "第10章";
const codePoints = [...official].map((c) => `U+${c.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}`).join(",");
assert.strictEqual(codePoints, "U+7B2C,U+0031,U+0030,U+7AE0");
assert.strictEqual(vm.runInNewContext(`${battleMatch[1]} + "："`, { model: { chapterNoForView: official } }), "第10章：");

assert(!support.includes("第<%= model.chapterNoForView %>章"));
assert(!battle.includes("第<span class=\"chapterNo\"><%= model.chapterNoForView %>章"));

console.log("PASS51_CHAPTER_VM=PASS");
console.log(`EXPRESSIONS=${expressions.length}`);
console.log(`FIXTURES_PER_EXPRESSION=${fixtures.length}`);
console.log(`CHECKS=${expressions.length * fixtures.length + 4}`);
console.log(`OFFICIAL_SOURCE=${official}`);
console.log(`OFFICIAL_CODE_POINTS=${codePoints}`);
console.log("CHAPTER10_RENDER=第10章：");
console.log("UNKNOWN_VALUE=UNCHANGED");
