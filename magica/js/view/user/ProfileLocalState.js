define(["backboneCommon"], function (common) {
  "use strict";

  // APK localstate.js owns the disk bridge and XHR lifecycle. Extend its route
  // table rather than installing another XHR wrapper or using WebView storage.
  var namespace = "profile_leader_v1";
  var installedState = null;
  var own = Object.prototype.hasOwnProperty;

  function bridge() {
    try { return window.CNLocalState || null; } catch (e) { return null; }
  }

  function load() {
    var b = bridge(), value;
    try {
      value = b && JSON.parse(b.get(namespace) || "null");
      if (value && value.version === 1 && Array.isArray(value.leaders)) return value;
    } catch (e) {}
    return { version: 1, leaders: [] };
  }

  function cardsContain(cards, id) {
    if (!Array.isArray(cards)) return false;
    for (var i = 0; i < cards.length; i++) {
      if (cards[i] && String(cards[i].id) === String(id)) return true;
    }
    return false;
  }

  function storageCards() {
    var storage = common.storage || {};
    var cards = storage.userCardList || storage.userCardListEx;
    return cards && cards.toJSON ? cards.toJSON() : [];
  }

  function ownPage(url) {
    // Other players' /friend/user responses are not our editable profile.
    return /\/magica\/api\/(?:page\/[^?]+|gameUser(?:\/[^?]*)?)(?:\?|$)/.test(String(url));
  }

  function overlay(json) {
    var user = json && json.gameUser;
    if (!user || !user.userId || json.resultCode === "error" || json.resultCode === "redirect") return false;
    var rows = load().leaders;
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (!row || String(row.userId) !== String(user.userId) || !row.userCardId) continue;
      // A fresh card list is authoritative. Do not revive a removed card.
      if (own.call(json, "userCardList") && !cardsContain(json.userCardList, row.userCardId)) return false;
      if (user.leaderId === row.userCardId) return false;
      user.leaderId = row.userCardId;
      return true;
    }
    return false;
  }

  function install() {
    var state = window.__MAGIACN_STATE__;
    if (!bridge() || !state || typeof state.route !== "function") return false;
    if (installedState === state) return true;
    state.route({ name: "profile:leader", test: ownPage, response: overlay });
    installedState = state;
    return true;
  }

  function recordLeader(id, response) {
    // The existing CharaTop callback runs only after ajaxControl accepts the
    // server response. Never persist an unconfirmed request or a helper change.
    if (!install()) return "unmanaged";
    var storage = common.storage || {};
    var current = storage.gameUser && storage.gameUser.toJSON();
    if (!current || !current.userId || !id || !cardsContain(storageCards(), id) ||
        !response || response.resultCode === "error" || response.resultCode === "redirect" ||
        !response.gameUser || String(response.gameUser.userId) !== String(current.userId)) return "failed";
    var saved = load(), rows = saved.leaders, found = false;
    for (var i = 0; i < rows.length; i++) {
      if (rows[i] && String(rows[i].userId) === String(current.userId)) {
        rows[i] = { userId: current.userId, userCardId: id }; found = true; break;
      }
    }
    if (!found) rows.push({ userId: current.userId, userCardId: id });
    try {
      var b = bridge(), text = JSON.stringify(saved);
      if (!b.set(namespace, text) || b.get(namespace) !== text) return "failed";
    } catch (e) { return "failed"; }
    response.gameUser.leaderId = id;
    return "saved";
  }

  install();
  return { install: install, recordLeader: recordLeader };
});
