define("underscore backbone backboneCommon ajaxControl command QuestUtil text!template/event/tower/EventTowerTop.html text!css/event/tower/EventTower.css text!css/quest/QuestCommon.css js/view/quest/QuestListPartsView js/view/quest/ClearAnimationsView".split(" "), function(k, F, b, v, l, A, G, H, I, w, J)
{
  function K()
  {
    var a = {};
    k.each(h.userSectionList, function(b)
    {
      var c = b.section.questType;
      "TOWER" == c && (console.log("sectionModel", b), b.section.questBattleList = [], k.each(h.userQuestBattleList, function(a)
      {
        b.section.sectionId === a.questBattle.sectionId && (r || (r = a.questBattle.consumeType), a.questType = c, b.section.questBattleList.push(a))
      }), b.section.questBattleList.sort(function(a, b)
      {
        return a.questBattle.sectionIndex - b.questBattle.sectionIndex
      }), b.eventObj = A.openEventCheck(b.section.eventId, h.eventList), 1 == b.section.genericIndex && (a.normal || (a.normal = []), b.section.titleParameter = "剧情关卡", b.questType = "TOWER_NORMAL", a.normal.push(b)), 2 == b.section.genericIndex && (a.challenge || (a.challenge = []), b.section.titleParameter = "挑战关卡", b.questType = "TOWER_CHALLENGE", a.challenge.push(b)))
    });
    a.normal && a.normal.sort(function(a, b)
    {
      return a.section.genericIndex < b.section.genericIndex ? -1 : a.section.genericIndex > b.section.genericIndex ? 1 : 0
    });
    a.challenge && a.challenge.sort(function(a, b)
    {
      return a.section.genericIndex < b.section.genericIndex ? -1 : a.section.genericIndex > b.section.genericIndex ? 1 : 0
    });
    return a
  }
  var t = null,
    x = null,
    g, n = null,
    B = null,
    C = !1,
    r = null,
    p = [],
    y = {
      TOWER_NORMAL: !1,
      TOWER_CHALLENGE: !1
    },
    h, u, L = F.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " .live2dArea"] = this.touch;
        a[b.cgti + " #helpBtn"] = this.helpPopup;
        a[b.cgti + " #tabBtns .normal"] = this.tabFunc;
        a[b.cgti + " #tabBtns .challenge"] = this.tabFunc;
        a[b.cgti + " .missionBtn"] = this.missionToggle;
        return a
      },
      initialize: function(a)
      {
        this.l2dTouchCnt = 0;
        this.template = k.template(G);
        this.createDom()
      },
      touch: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled() && n)
        {
          a = a.originalEvent.changedTouches ? a.originalEvent.changedTouches[0] : a.originalEvent;
          a = {
            id: n,
            x: a.pageX,
            y: a.pageY
          };
          var c = [32, 33, 34, 35];
          7 <= this.l2dTouchCnt && c.push(40);
          var c = c[Math.floor(Math.random() * c.length)] + 1,
            e = n.substring(0, n.length - 2);
          a.voice = "vo_char_" + e + "_00_" + c;
          l.storyMotionL2dVoice(a);
          this.l2dTouchCnt++
        }
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: h
        }));
        return this
      },
      helpPopup: function(a)
      {
        a.preventDefault();
        b.isScrolled() || b.eventFirstNavi(p, g.eventId, "tower", function() {}, !0)
      },
      modelSend: function(a)
      {
        var b = a.currentTarget.parentNode.querySelector(".params .questType").dataset.questtype;
        a = a.currentTarget.parentNode.querySelector(".params .sectionId").dataset.sectionid;
        switch (b)
        {
          case "TOWER_NORMAL":
            return b = k.findWhere(m.normal,
            {
              sectionId: Number(a)
            });
          case "TOWER_CHALLENGE":
            return b = k.findWhere(m.challenge,
            {
              sectionId: Number(a)
            })
        }
      },
      createView: function()
      {
        y = {
          TOWER_NORMAL: !1,
          TOWER_CHALLENGE: !1
        };
        w.prototype.parentView = this;
        w.prototype.template = k.template($("#QuestListParts").text());
        w.prototype.tagName = "div";
        var a = E(m.normal);
        b.doc.getElementById("normalQuest").appendChild(a);
        console.log("sectionObj", m);
        "challenge" in m ? (a = E(m.challenge), b.doc.getElementById("challengeQuest").appendChild(a)) : b.addClass(b.doc.querySelector(".challengeWrap"), "off")
      },
      createDom: function()
      {
        b.setGlobalView();
        m = K();
        h.questConsumeType = r;
        b.content.append(this.render().el);
        this.createView();
        var a = g.eventId,
          c = b.storage.userItemList.findWhere(
          {
            itemId: "EVENT_TOWER_" + a + "_KEY"
          }),
          a = b.storage.userItemList.findWhere(
          {
            itemId: "EVENT_TOWER_" + a + "_EXCHANGE_1"
          }),
          c = c ? c.toJSON().quantity : 0,
          a = a ? a.toJSON().quantity : 0;
        "ITEM" == r && (b.doc.querySelector(".questItemNumWrap .num").textContent = c);
        b.doc.querySelector(".itemNumWrap .num").textContent = a;
        b.scrollSet("scrollOuter", "scrollInner");
        c = "normal" == t ? "TOWER_NORMAL" : "TOWER_CHALLENGE";
        x && !y[c] && b.forceScrollPreset("scrollOuter", "scrollInner", x, !0);
        b.ready.hide()
      },
      tabFunc: function(a)
      {
        a.preventDefault();
        !b.isScrolled() && a.currentTarget.dataset && (b.forceScrollArr = null, this.selectQuestType(a.currentTarget.dataset.id), b.scrollRefresh(null, null, !0), q())
      },
      selectQuestType: function(a)
      {
        m.challenge || (a = "normal");
        var c = b.doc.querySelector("#tabBtns"),
          e = b.doc.querySelector("#questWrapTitle"),
          f = b.doc.querySelector("#questWrap"),
          d = "normal" != a && a ? "challenge" : "normal";
        a = "normal" != a && a ? "normal" : "challenge";
        var z = g.eventId,
          h = 'url("/magica/resource/image_web/event/tower/' + z + "/tab_" + d + '_on.png") left top no-repeat',
          z = 'url("/magica/resource/image_web/event/tower/' + z + "/tab_" + a + '_off.png") left top no-repeat';
        c.querySelector("." + d).style.background = h;
        c.querySelector("." + a).style.background = z;
        b.addClass(c.querySelector("." + d), "current");
        b.removeClass(c.querySelector("." + a), "current");
        e.textContent = {
          normal: "◆ 剧情关卡",
          challenge: "◆ 挑战关卡"
        } [d];
        f.className = "commonFrame2 " + d;
        c = d.toUpperCase() + "SECTIONID";
        d = m[d][m[d].length - 1];
        c = g.parameterMap[c];
        B = d.sectionId;
        String(B) !== c && d.cleared ? b.addClass(b.doc.querySelector(".allClear"), "show") : b.removeClass(b.doc.querySelector(".allClear"), "show");
        d.section.message ? (b.removeClass(b.doc.querySelector("#charaSerif"), "off"), d.section.message = d.section.message.replace(/＠/g, "<br>"), b.doc.querySelector(".charaName").textContent = d.section.charaName, b.doc.querySelector(".serifFont").innerHTML = d.section.message) : (b.addClass(b.doc.querySelector("#eventShopWrap"), "bottom"), b.addClass(b.doc.querySelector("#missionLinkBtn"), "bottom"))
      },
      missionToggle: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = b.doc.querySelector("#scrollOuter .scrollInner");
          var c = b.doc.querySelector("#scrollOuter .scrollInner").className; - 1 !== c.indexOf("first") ? a.className = "second scrollInner" : -1 !== c.indexOf("second") && (a.className = "first scrollInner")
        }
      }
    }),
    m, E = function(a, c)
    {
      var e = [],
        f = 1;
      k.each(a, function(a, b)
      {
        k.each(a.section.questBattleList, function(b, c)
        {
          var d = "";
          switch (c)
          {
            case 0:
              d = "①";
              break;
            case 1:
              d = "②";
              break;
            case 2:
              d = "③";
              break;
            case 3:
              d = "④";
              break;
            case 4:
              d = "⑤";
              break;
            case 5:
              d = "⑥";
              break;
            case 6:
              d = "⑦";
              break;
            case 7:
              d = "⑧";
              break;
            case 8:
              d = "⑨";
              break;
            case 9:
              d = "⑩";
              break;
            case 10:
              d = "⑪"
          }
          b.questBattleIndex = f - 1;
          b.questTitle = "战斗 " + f;
          b.questType = a.questType;
          b.charaId = a.section.charaId;
          b.charaTitle = a.section.charaName + "篇" + d;
          f++;
          console.log(a.questType);
          if (!y[a.questType] || b.cleared) e.push(b), b.cleared || (y[a.questType] = !0)
        })
      });
      e.sort(function(a, b)
      {
        return a.questBattleIndex > b.questBattleIndex ? -1 : a.questBattleIndex < b.questBattleIndex ? 1 : 0
      });
      var d = b.doc.createDocumentFragment();
      k.each(e, function(a, e)
      {
        console.log(e, a);
        a.missionRewardCode = b.itemSet(a.questBattle.missionRewardCode);
        a.chestColor = a.missionRewardCode.chestColor;
        e = new w(
        {
          model: a
        });
        c && (e.parentView = c);
        e.el.dataset.scrollHash = a.questBattleId;
        d.appendChild(e.render().el);
        if (g.viewParameterMap.VIEW_TYPE && "TOWER_NORMAL" == a.questType)
        {
          var f = g.viewParameterMap.VIEW_TYPE;
          b.addClass(e.el, f);
          switch (f)
          {
            case "charaBtn":
              f = b.doc.createElement("img"), f.className = "charaImg", f.src = "/magica/resource/image_web/event/tower/" + g.eventId + "/chara/chara_" + a.charaId + ".png", e.el.querySelector(".firstView").appendChild(f), e.el.querySelector(".questTitle").textContent = a.charaTitle
          }
        }
      });
      return d
    },
    D = function()
    {
      t || (t = "normal");
      b.setStyle(H + I);
      n = g.viewParameterMap.LIVE2D_ID || null;
      h = v.getPageJson();
      if (g = h.eventList.filter(function(a, b)
        {
          if ("TOWER" == a.eventType) return !0
        })[0])
      {
        h.eventMaster = g;
        var a = g.viewParameterMap.BGM;
        l.changeBg(g.viewParameterMap.BG_IMG + ".ExportJson");
        l.startBgm(a);
        u = new L;
        u.selectQuestType(t);
        b.scrollRefresh();
        A.supportPickUp(h);
        if (b.clearSectionModel && b.clearSectionModel.section.clearReward)
        {
          var c = b.clearSectionModel.section,
            a = A.clearRewardChestColor(c.clearReward);
          J.section(c.clearRewardCode, c, a, function()
          {
            1 == c.genericIndex ? new b.PopupClass(
            {
              title: "剧情通关",
              content: "挑战关卡已解放。",
              closeBtnText: "关闭",
              popupType: "typeC"
            }, null, null, function()
            {
              q()
            }) : q()
          });
          l.getBaseData(b.getNativeObj());
          b.clearSectionModel = null
        }
        else C && q(), l.getBaseData(b.getNativeObj())
      }
      else location.href = "#/MyPage"
    },
    q = function()
    {
      l.endL2d();
      var a = {
        type: 1,
        id: "0",
        x: 246
      };
      a.y = 1024 === b.displayWidth ? Math.floor(b.doc.getElementsByTagName("body")[0].offsetHeight / 2) : Math.ceil(b.shortSize / 2);
      if (n)
      {
        var c = "vo_char_" + n.substring(0, n.length - 2) + "_00_",
          e = [],
          f = Number(h.currentTime.split(" ")[1].split(":")[0]),
          d = Number(h.currentTime.split(" ")[1].split(":")[1]);
        6 <= f && 9 >= f && !(9 == f && 0 < d) ? e.push(24) : 11 <= f && 13 >= f && !(13 == f && 0 < d) ? e.push(25) : 17 <= f && 19 >= f && !(19 == f && 0 < d) ? e.push(26) : 22 <= f || 0 == f && !(0 == f && 0 < d) ? e.push(27) : e.push(23);
        b.storage.userStatusList.findWhere(
        {
          statusId: "ACP"
        }).toJSON().point >= b.storage.userStatusList.findWhere(
        {
          statusId: "MAX_ACP"
        }).toJSON().point && e.push(29);
        b.storage.userStatusList.findWhere(
        {
          statusId: "BTP"
        }).toJSON().point >= b.storage.userStatusList.findWhere(
        {
          statusId: "MAX_BTP"
        }).toJSON().point && e.push(30);
        a.key = c + (e[Math.floor(Math.random() * e.length)] + 1)
      }
      else a.key = String(B);
      l.startL2d(a)
    },
    M = function(a, c)
    {
      var e = !1;
      a && (e = !0, k.each(h.userQuestAdventureList, function(b)
      {
        a === b.adventureId && (e = !1)
      }));
      e ? ($(b.ready.target).off(), $(b.ready.target).on("webkitAnimationEnd", function()
      {
        l.changeBg("web_black.jpg");
        $(b.ready.target).off();
        $(b.ready.target).on("webkitAnimationEnd", function(a)
        {
          "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
        });
        v.ajaxPost(b.linkList.userQuestAdventureRegist,
        {
          adventureId: String(a)
        }, c)
      }), b.ready.target.classList.contains("preNativeFadeIn") ? $(b.ready.target).trigger("webkitAnimationEnd") : b.addClass(b.ready.target, "preNativeFadeIn")) : c()
    },
    N = function()
    {
      if (g)
      {
        var a = g.parameterMap.SWITCHDATE,
          c = g.viewParameterMap.SWITCH_NAVI.split(",");
        b.periodCheck(h.currentTime, a) && k.each(p, function(a, b)
        {
          k.each(c, function(c)
          {
            a == c && (p[b] += "_02")
          })
        })
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
      id: "itemList"
    },
    {
      id: "userItemList"
    },
    {
      id: "giftList"
    },
    {
      id: "pieceList"
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
      id: "userChapterList"
    },
    {
      id: "userSectionList"
    },
    {
      id: "userQuestBattleList"
    },
    {
      id: "userFollowList"
    },
    {
      id: "userQuestAdventureList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function(a, b)
    {
      a && (t = a);
      b && (x = b);
      v.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      h = v.getPageJson();
      g = k.findWhere(h.eventList,
      {
        eventType: "TOWER"
      });
      r = null;
      C = !0;
      p = ["navi_01", "navi_02", "navi_03"];
      g.parameterMap.SWITCHDATE && g.viewParameterMap.SWITCH_NAVI && N();
      var a = g.viewParameterMap.EVENT_CONSUME_ITEM_NAME,
        c = g.startStoryId || null;
      M(c, function(e)
      {
        e ? (C = !1, b.responseSetStorage(e), l.endL2d(), $("#commandDiv").on("nativeCallback", function(c, d)
        {
          $("#commandDiv").off();
          D();
          b.eventFirstNavi(p, g.eventId, "tower", function()
          {
            a ? new b.PopupClass(
            {
              popupType: "typeC",
              title: a + "到手！",
              content: a + "已发放。<br>消耗" + a + "<br>参加活动副本吧！",
              closeBtnText: "关闭"
            }, null, null, function()
            {
              q()
            }) : q()
          });
          l.setWebView(!0)
        }), setTimeout(function()
        {
          l.setWebView(!1);
          l.startStory(c,
          {
            canAuto: !1,
            canOpenLog: !1
          });
          window.isBrowser && (D(), b.eventFirstNavi(p, g.eventId, "tower", function()
          {
            a ? new b.PopupClass(
            {
              popupType: "typeC",
              title: a + "到手！",
              content: a + "已发放。<br>消耗" + a + "<br>参加活动副本吧！",
              closeBtnText: "关闭"
            }, null, null, function()
            {
              q()
            }) : q()
          }))
        }, 500)) : D()
      })
    },
    removeCommand: function()
    {
      l.endL2d()
    },
    remove: function(a)
    {
      x = null;
      p = [];
      u && (u.trigger("remove"), u.remove());
      a()
    }
  }
});
