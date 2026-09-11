"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const jquery = fs.readFileSync(path.join(root, "magica/js/libs/jquery-3.7.1.min.js"), "utf8");
const view = fs.readFileSync(path.join(root, "magica/js/view/quest/QuestResultView.js"), "utf8");
const start = jquery.lastIndexOf("(function(){");
assert(start >= 0, "injector IIFE marker missing");

function XMLHttpRequest() {}
XMLHttpRequest.prototype.open = function () {};
XMLHttpRequest.prototype.addEventListener = function () {};
const context = {
  console: { warn() {} },
  window: {},
  XMLHttpRequest,
  setInterval() { return 1; },
  clearInterval() {},
};
context.window.setInterval = context.setInterval;
context.window.clearInterval = context.clearInterval;
vm.createContext(context);
vm.runInContext(jquery.slice(start), context, { timeout: 15000 });
assert.strictEqual(typeof context.window.__MAGIACN_TRANSLATE__, "function");

const hook = 'var __magiaCnQuestBattle=a.questBattleModel&&a.questBattleModel.questBattle?a.questBattleModel.questBattle:this.model.questBattleModel&&this.model.questBattleModel.questBattle?this.model.questBattleModel.questBattle:null;__magiaCnQuestBattle&&"function"==typeof window.__MAGIACN_TRANSLATE__&&window.__MAGIACN_TRANSLATE__(__magiaCnQuestBattle);"function"==typeof window.__MAGIACN_TRANSLATE__&&window.__MAGIACN_TRANSLATE__(this.model);';
assert.strictEqual(view.split(hook).length - 1, 1, "QuestResult stable-model hook count");

function runFixture(questBattle, useGlobalModel = true) {
  const outer = { userQuestBattleResultList: [{}] };
  if (!useGlobalModel) outer.questBattleModel = { questBattle };
  context.a = useGlobalModel ? { questBattleModel: { questBattle } } : {};
  context.currentView = { model: outer };
  vm.runInContext(`(function(){${hook}}).call(currentView)`, context, { timeout: 15000 });
  return questBattle;
}

const complete = runFixture({
  questBattleId: 1020041,
  chapterNoForView: "第10章",
  mission1: "NOT_DEAD",
  mission2: "ACTION_15",
  mission3: "COUNT_CONNECT_1",
  missionMaster1: { description: "Clear without losing any Magical Girls" },
  missionMaster2: { description: "Clear within 15 Turn(s)" },
  missionMaster3: { description: "Connect 1 time(s)" },
});
assert.strictEqual(complete.chapterNoForView, "第10章");
assert.strictEqual(complete.missionMaster1.description, "无人退场下通关");
assert.strictEqual(complete.missionMaster2.description, "15回合内通关");
assert.strictEqual(complete.missionMaster3.description, "发动1次Connect");

const nestedFallback = runFixture({
  mission1: "NOT_DEAD",
  missionMaster1: { description: "Clear without losing any Magical Girls" },
}, false);
assert.strictEqual(nestedFallback.missionMaster1.description, "无人退场下通关");

const wrongSource = runFixture({
  mission1: "ACTION_15",
  missionMaster1: { description: "Clear within 14 Turn(s)" },
});
assert.strictEqual(wrongSource.missionMaster1.description, "Clear within 14 Turn(s)");

const wrongCode = runFixture({
  mission1: "ACTION_10",
  missionMaster1: { description: "Clear within 15 Turn(s)" },
});
assert.strictEqual(wrongCode.missionMaster1.description, "Clear within 15 Turn(s)");

console.log("PASS51_QUEST_RESULT_FULL_MODEL_VM=PASS");
console.log("REAL_PATH=questBattleModel.questBattle");
console.log("QUEST_BATTLE_ID=1020041");
console.log("STABLE_CODES=NOT_DEAD,ACTION_15,COUNT_CONNECT_1");
console.log("EXACT_FIELDS=missionMaster1.description,missionMaster2.description,missionMaster3.description");
console.log("OFFICIAL_TARGETS=无人退场下通关|15回合内通关|发动1次Connect");
console.log("CHAPTER_SOURCE=第10章");
console.log("WRONG_SOURCE=UNCHANGED");
console.log("WRONG_CODE=UNCHANGED");
console.log("OUTER_MODEL_FALLBACK=PASS");
