import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const sourcePath = fileURLToPath(new URL("../magica/js/_common/base.js", import.meta.url));
const source = fs.readFileSync(sourcePath, "utf8");
const boundary = source.indexOf(";window.app_ver");
assert.ok(boundary > 0, "base.js boundary missing");
const handlerSource = source.slice(0, boundary);

function storage(backing = new Map()) {
  return {
    backing,
    getItem(key) { return backing.has(key) ? backing.get(key) : null; },
    setItem(key, value) { backing.set(key, String(value)); },
    removeItem(key) { backing.delete(key); }
  };
}

function createRuntime(sharedStorage, options = {}) {
  const calls = { require: 0, post: [], reload: [], popups: [], timers: [], setWebView: [] };
  let decideHandler = null;
  const windowObject = {
    isDebug: true,
    isBrowser: false,
    console,
    localStorage: sharedStorage,
    location: {
      hash: options.route || "#/MyPage",
      reload() { calls.reload.push("browser-reload:" + this.hash); }
    },
    setTimeout(fn, ms) { calls.timers.push({ fn, ms }); },
    jQuery(selector) {
      assert.equal(selector, "#resultCodeError .decideBtn");
      return {
        off() { return this; },
        on(event, fn) { decideHandler = fn; return this; }
      };
    }
  };
  windowObject.$ = windowObject.jQuery;

  const common = {
    location: options.page || options.route || "#/MyPage",
    cgti: "click",
    tapBlock() {},
    loading: options.noDom ? null : { hide() {} },
    doc: options.noDom ? null : { querySelector() { return { style: {} }; } },
    linkList: { jsErrorSend: "/magica/api/test/logger/error" },
    PopupClass: function PopupClass(config, unused, ready) {
      calls.popups.push(config);
      ready();
    }
  };
  const ajax = {
    ajaxPlainPost(path, body) { calls.post.push({ path, body }); }
  };
  const command = {
    setWebView(value) { calls.setWebView.push(value); },
    nativeReload(target) { calls.reload.push(target); }
  };
  const context = {
    window: windowObject,
    console,
    Date,
    JSON,
    Number,
    String,
    require(deps, callback) {
      calls.require++;
      callback({}, {}, common, ajax, command);
    }
  };
  vm.runInNewContext(handlerSource, context, { filename: sourcePath });
  return {
    handler: windowObject.onerror,
    calls,
    click() { assert.ok(decideHandler, "popup decide handler missing"); decideHandler(); },
    lastError() { return JSON.parse(sharedStorage.getItem("__MAGIACN_LAST_JS_ERROR_V2__")); }
  };
}

const backing = new Map();
const shared = storage(backing);
const first = createRuntime(shared);
assert.equal(first.handler("Boom", "base.js", 12, 34, { toString(){ return "Error: Boom"; }, stack: "STACK:first" }), true);
assert.equal(first.calls.require, 1);
assert.equal(first.calls.post.length, 1);
assert.equal(first.calls.popups[0].decideBtnText, "重新载入");
assert.match(first.calls.post[0].body, /STACK:first/);
assert.equal(first.lastError().page, "#/MyPage");
assert.equal(first.lastError().repeated, false);
first.click();
assert.deepEqual(first.calls.reload, ["#/MyPage"]);

const second = createRuntime(shared);
second.handler("Boom", "base.js", 12, 34, { toString(){ return "Error: Boom"; }, stack: "STACK:second" });
assert.equal(second.lastError().repeated, true);
assert.equal(second.calls.popups[0].decideBtnText, "返回首页");
second.click();
assert.deepEqual(second.calls.reload, ["#/TopPage"]);

const undefinedErrorStore = storage(new Map());
const undefinedError = createRuntime(undefinedErrorStore, { noDom: true, route: "#/GachaTop" });
assert.doesNotThrow(() => undefinedError.handler("No object", "gacha.js", 4, 9, undefined));
assert.equal(undefinedError.lastError().stack, "");
assert.equal(undefinedError.calls.popups[0].decideBtnText, "重新载入");
undefinedError.click();
assert.deepEqual(undefinedError.calls.reload, ["#/GachaTop"]);

const reentrantStore = storage(new Map());
const reentrant = createRuntime(reentrantStore);
reentrant.handler("Once", "x.js", 1, 2, new Error("Once"));
reentrant.handler("Again", "y.js", 3, 4, new Error("Again"));
assert.equal(reentrant.calls.require, 1);
assert.equal(reentrant.calls.post.length, 1);

console.log("PASS first-error reloads current route");
console.log("PASS repeated identical error offers TopPage fallback");
console.log("PASS undefined Error object is null-safe");
console.log("PASS missing optional DOM/loading objects is tolerated");
console.log("PASS reentrant onerror is suppressed");
console.log("PASS structured logger body and last-error persistence");
