define("underscore backbone backboneCommon ajaxControl command text!template/event/accomplish/EventAccomplishTop.html text!css/event/accomplish/EventAccomplishTop.css js/view/quest/QuestListPartsView js/view/quest/ClearAnimationsView js/event/accomplish/CompleteAnimationsView text!css/quest/QuestCommon.css QuestUtil".split(" "), function(g, D, b, r, f, E, F, u, G, B, H, I)
{
  var v, w = null,
    x, y, l, h, m, q, t, p = null,
    k, c, z, J = D.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " #helpBtn"] = this.helpPopup;
        a[b.cgti + " .missionBtn"] = this.missionToggle;
        a[b.cgti + " #schedulePopBtn"] = this.rewardPopup;
        return a
      },
      initialize: function(a)
      {
        this.template = g.template(E);
        this.createDom()
      },
      render: function()
      {
        var a = r.getPageJson();
        a.questMode = m;
        a.clearCnt = p;
        a.eventId = c.eventId;
        a.shopId = c.shopId;
        this.$el.html(this.template(a));
        return this
      },
      createDom: function()
      {
        b.setGlobalView();
        b.content.append(this.render().el);
        this.createView()
      },
      createView: function()
      {
        u.prototype.parentView = this;
        u.prototype.template = g.template($("#QuestListParts").text());
        u.prototype.tagName = "div";
        var a = !1,
          d = b.doc.createDocumentFragment(),
          n = null;
        g.each(t, function(e, c)
        {
          e.missionRewardCode = b.itemSet(e.questBattle.missionRewardCode);
          e.chestColor = e.missionRewardCode.chestColor;
          c = new u(
          {
            model: e
          });
          a ? (e.canPlay = !1, b.accomplishDebug && (e.canPlay = !0, b.addClass(c.el, "canPlay"))) : (e.canPlay = !0, b.addClass(c.el, "canPlay"), n = c, a = !0);
          e.questBattle.bossFlag && b.addClass(c.el, "typeBoss");
          c.el.dataset.scrollHash = e.questBattleId;
          d.appendChild(c.render().el)
        });
        b.doc.querySelector("#scrollOuter .scrollInner").appendChild(d);
        b.doc.querySelector("#scrollOuter .quest") ? (b.scrollSet("scrollOuter", "scrollInner"), b.scrollMemory && (b.forceScrollPreset("scrollOuter", "scrollInner", b.scrollMemory, !0), b.scrollMemory = null)) : b.addClass(b.doc.querySelector("#scrollOuter .allClear"), "show");
        var e = p / ("normal" == m ? x : y) * 100;
        b.doc.querySelector("#gauge").style.height = e + "%";
        e = 0 < q.length ? g.find(q, function(a)
        {
          return a.sectionId == n.model.questBattle.sectionId
        }) : h[h.length - 1];
        e.section.message = e.section.message.replace(/＠/g, "<br>");
        b.doc.querySelector("#charaName").innerText = e.section.charaName;
        b.doc.querySelector("#charaSerif").innerHTML = e.section.message;
        w = e.sectionId;
        b.ready.hide()
      },
      missionToggle: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = b.doc.querySelector("#scrollOuter .scrollInner");
          var d = b.doc.querySelector("#scrollOuter .scrollInner").className; - 1 !== d.indexOf("first") ? a.className = "second scrollInner" : -1 !== d.indexOf("second") && (a.className = "first scrollInner")
        }
      },
      helpPopup: function(a)
      {
        a.preventDefault();
        b.isScrolled() || b.eventFirstNavi(v, c.eventId, "accomplish", function() {}, !0)
      },
      rewardPopup: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var d = function()
          {
            setTimeout(function()
            {
              b.scrollSet("popScrollOuter", "popScrollInner");
              b.scrollRefresh(null, null, !0)
            }, 500)
          };
          a = new Image;
          a.src = "/magica/resource/image_web/event/accomplish/" + c.eventId + "/reward_list.png";
          a.onload = function()
          {
            new b.PopupClass(
            {
              popupType: "typeB",
              exClass: "rewardPopup"
            }, $("#ScheduleTemp").text(), d)
          }
        }
      },
      modelSend: function(a)
      {
        var d = a.currentTarget.parentNode.querySelector(".params .sectionId").dataset.sectionid,
          c = a.currentTarget.parentNode.querySelector(".params .questBattleId").dataset.questbattleid;
        a = g.find(q, function(a)
        {
          return a.sectionId == Number(d)
        });
        a.questBattle = g.find(t, function(a)
        {
          return a.questBattleId == Number(c)
        });
        console.log(a.questBattle);
        a.nextPage = "#/EventAccomplishEnemyDetail";
        b.EventAccomplishEnemyDetail = k.questBattlePreviewJsonMap[c];
        return a
      }
    }),
    A = function()
    {
      b.setStyle(F + H);
      k = r.getPageJson();
      z = new J;
      var a = b.storage.userItemList.findWhere(
        {
          itemId: "EVENT_ACCOMPLISH_" + c.eventId + "_EXCHANGE_1"
        }),
        a = a ? a.toJSON().quantity : 0;
      b.doc.querySelector("#itemNum").textContent = a;
      if (b.clearSectionModel && b.clearSectionModel.section.clearReward)
      {
        var d = b.clearSectionModel.section,
          a = I.clearRewardChestColor(d.clearReward),
          n = function()
          {
            C();
            f.getBaseData(b.getNativeObj())
          };
        G.section(d.clearRewardCode, d, a, function()
        {
          console.log("通关小节", m, d);
          console.log("剧情最后", l[l.length - 1]);
          console.log("挑战最后", h[h.length - 1]);
          d.sectionId == l[l.length - 1].sectionId ? B.start("story", n) : d.sectionId == h[h.length - 1].sectionId ? B.start("challenge", n) : n()
        });
        f.getBaseData(b.getNativeObj());
        b.clearSectionModel = null
      }
      else C(), f.getBaseData(b.getNativeObj())
    },
    K = function()
    {
      l = g.filter(k.userSectionList, function(a)
      {
        return "ACCOMPLISHTYPE=NORMAL" == a.section.parameter
      });
      h = g.filter(k.userSectionList, function(a)
      {
        return "ACCOMPLISHTYPE=CHALLENGE" == a.section.parameter
      });
      l.sort(function(a, b)
      {
        return a.sectionId < b.sectionId ? -1 : a.sectionId > b.sectionId ? 1 : 0
      });
      h.sort(function(a, b)
      {
        return a.sectionId < b.sectionId ? -1 : a.sectionId > b.sectionId ? 1 : 0
      });
      console.log("normalSectionList:", l);
      console.log("challengeSectionList:", h)
    },
    L = function()
    {
      m = 0 < g.filter(l, function(a)
      {
        return 0 == a.cleared
      }).length ? "normal" : "challenge";
      b.accomplishDebug && (m = b.accomplishDebug);
      b.eventAccomplishQuestMode = m;
      console.log("questMode:", m)
    },
    M = function()
    {
      var a = k.userQuestBattleList;
      a.sort(function(a, b)
      {
        return a.questBattleId < b.questBattleId ? -1 : a.questBattleId > b.questBattleId ? 1 : 0
      });
      var d = 0,
        n = 0;
      t = g.filter(a, function(a)
      {
        var e = a.questBattle.eventId == c.eventId,
          f = !1;
        if (e && (d++, (!a.cleared || b.accomplishDebug) && n < (b.accomplishDebug ? 999 : 10)))
        {
          n++;
          var h = g.find(q, function(b)
          {
            return a.questBattle.sectionId == b.sectionId
          });
          if (h)
          {
            var k = h.section.parameter.split("=")[1].toLowerCase(),
              f = k == m ? !0 : !1,
              l = "normal" == k ? d : d - x;
            a.questTitle = "战斗 " + l;
            a.accomplishType = k;
            null == p && (p = l - 1);
            a.questType = h.section.questType
          }
        }
        return e && f && 11 > n || b.accomplishDebug && e && f
      });
      null == p && (p = y);
      console.log("pickUpViewQuestBattleList", t)
    },
    N = function()
    {
      var a = [],
        c = 0;
      g.each("normal" == m ? l : h, function(d)
      {
        if (!d.cleared || b.accomplishDebug) a.push(d),
          c++
      });
      console.log("pickUpViewSectionList:", a);
      q = a
    },
    O = function(a, c)
    {
      var d = b.storage.userQuestAdventureList.toJSON(),
        e = !1,
        e = !0;
      g.each(d, function(b)
      {
        a === b.adventureId && (e = !1)
      });
      e ? ($(b.ready.target).off(), $(b.ready.target).on("webkitAnimationEnd", function()
      {
        f.changeBg("web_black.jpg");
        $(b.ready.target).off();
        $(b.ready.target).on("webkitAnimationEnd", function(a)
        {
          "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
        });
        r.ajaxPost(b.linkList.userQuestAdventureRegist,
        {
          adventureId: String(a)
        }, c)
      }), b.ready.target.classList.contains("preNativeFadeIn") ? $(b.ready.target).trigger("webkitAnimationEnd") : b.addClass(b.ready.target, "preNativeFadeIn")) : c()
    },
    C = function()
    {
      if (w)
      {
        f.endL2d();
        var a = {};
        a.key = String(w);
        a.type = 1;
        a.id = "0";
        a.x = 246;
        a.y = 1024 === b.displayWidth ? Math.floor(b.doc.getElementsByTagName("body")[0].offsetHeight / 2) : Math.ceil(b.shortSize / 2);
        f.startL2d(a)
      }
    };
  return {
    needModelIdObj: [
    {
      id: "user"
    },
    {
      id: "gameUser"
    },
    {
      id: "pieceList"
    },
    {
      id: "itemList"
    },
    {
      id: "giftList"
    },
    {
      id: "userItemList"
    },
    {
      id: "userGiftList"
    },
    {
      id: "userStatusList"
    },
    {
      id: "userCharaList"
    },
    {
      id: "userCardList"
    },
    {
      id: "userDeckList"
    },
    {
      id: "userDoppelList"
    },
    {
      id: "userLive2dList"
    },
    {
      id: "userFollowList"
    },
    {
      id: "userChapterList"
    },
    {
      id: "userSectionList"
    },
    {
      id: "userQuestBattleList"
    },
    {
      id: "userQuestAdventureList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function()
    {
      r.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      console.log(c);
      b.EventAccomplishEnemyDetail = null;
      v = ["navi_01", "navi_02", "navi_03"];
      x = parseInt(c.viewParameterMap.NORMAL_QUEST_COUNT);
      y = parseInt(c.viewParameterMap.CHALLENGE_QUEST_COUNT);
      b.userEventAccomplishQuestBattleList = k.userEventAccomplishQuestBattleList;
      b.userEventAccomplish = k.userEventAccomplish;
      b.userEventAccomplishCharaArr = {};
      g.each(k.userEventAccomplishCharaList, function(a)
      {
        b.userEventAccomplishCharaArr[a.charaId] = a
      });
      K();
      L();
      N();
      M();
      var a = c && c.startStoryId ? c.startStoryId : null,
        d = function(d)
        {
          d ? (b.responseSetStorage(d), $("#commandDiv").on("nativeCallback", function(a, d)
          {
            $("#commandDiv").off();
            f.setWebView(!0);
            b.tapBlock(!1);
            b.androidKeyStop = !1;
            f.changeBg(c.viewParameterMap.BG_IMG + ".ExportJson");
            f.startBgm(c.viewParameterMap.BGM);
            b.ready.target.className = "nativeFadeOut";
            b.eventFirstNavi(v, c.eventId, "accomplish", function()
            {
              A()
            })
          }), setTimeout(function()
          {
            f.setWebView(!1);
            f.startStory(a,
            {
              canAuto: !1,
              canOpenLog: !1
            })
          }, 500)) : (f.changeBg(c.viewParameterMap.BG_IMG + ".ExportJson"), f.startBgm(c.viewParameterMap.BGM), A())
        };
      a && !window.isLocal ? O(a, d) : A()
    },
    startCommand: function()
    {
      k = r.getPageJson();
      c = g.findWhere(k.eventList,
      {
        eventType: "ACCOMPLISH"
      })
    },
    removeCommand: function()
    {
      f.endL2d()
    },
    remove: function(a)
    {
      z && (z.trigger("removeView"), z.remove());
      v = [];
      y = x = w = p = t = q = m = h = l = c = k = null;
      a()
    }
  }
});
