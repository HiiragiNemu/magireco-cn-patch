define("underscore backbone backboneCommon ajaxControl command text!template/event/branch/EventBranchTop.html text!css/event/branch/EventBranch.css text!css/quest/QuestCommon.css QuestUtil js/view/quest/ClearAnimationsView".split(" "), function(l, B, a, t, d, I, J, K, C, L)
{
  var F = B.Model.extend(),
    h, D, u, m, f, y, n, v, G, p, r = !1,
    w = !1,
    e = {},
    M = B.View.extend(
    {
      events: function()
      {
        var b = {};
        window.isBrowser ? b[a.cgti + " #debugChartBtn"] = this.debugChart : (b["touchstart #chartWrap"] = this.touchStart, b["touchmove #chartWrap"] = this.touchMove, b["touchend #chartWrap"] = this.touchEnd);
        b[a.cgti + " #partLinkBtn"] = this.partChange;
        b[a.cgti + " #helpBtn"] = this.announceOpen;
        return b
      },
      debugChart: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (b.stopPropagation(), $("#commandDiv").trigger("nativeCallback", [f.chartList[0][0]]))
      },
      partChange: function(b)
      {
        if (b && (b.preventDefault(), a.isScrolled())) return;
        if (!v) new a.PopupClass(
        {
          title: "确认",
          content: "第2部当前尚未公开。<br>请等待公开。",
          closeBtnText: "OK"
        });
        else if (!w)
        {
          w = !0;
          a.tapBlock(!0);
          this.el.className = "partChange";
          var c = this;
          m = 1 == m ? 2 : 1;
          H();
          $(".bgWrap").on("webkitAnimationEnd", function()
          {
            $("#sideWrap").off();
            c.partChangeRender();
            d.popEventBranch();
            e && e.part2.length ? ($("#commandDiv").on("nativeCallback", function(b)
            {
              $("#commandDiv").off();
              $(a.ready.content).on("webkitAnimationEnd", function(b)
              {
                "readyFadeIn" == b.originalEvent.animationName && (a.tapBlock(!1), a.scrollRefresh(null, null, null, !0))
              });
              z();
              a.androidKeyStop = !1;
              c.initFlag = !0;
              a.tapBlock(!1);
              e = null;
              w = !1
            }), d.pushEventBranch(f.chartList[m - 1], null, e.part2)) : d.pushEventBranch(f.chartList[m - 1])
          })
        }
      },
      touchStart: function(b)
      {
        b.preventDefault();
        this.initFlag && (a.tapEffectStop = !0, E(b, "START"))
      },
      touchMove: function(a)
      {
        a.preventDefault();
        this.initFlag && E(a, "MOVE")
      },
      touchEnd: function(b)
      {
        b.preventDefault();
        this.initFlag && (a.tapEffectStop = !1, E(b, "END"), !a.isScrolled() && r && (r = !1, d.resumeEventBranch(), a.removeClass(a.doc.querySelector("#questDetail"), "open"), p && (d.startSe(1003), p.removeView(), p = null, a.removeClass(a.doc.querySelector(".chartCautionText"), "show"))))
      },
      initialize: function(a)
      {
        this.initFlag = !1;
        this.template = l.template(I);
        this.createDom()
      },
      render: function()
      {
        var a = f;
        a.eventId = h.eventId;
        a.partCloseFlag = G;
        a.eventType = h.eventType.toLowerCase();
        a.partModel = n;
        a.partOpenFlag = v;
        this.$el.html(this.template(a));
        return this
      },
      partChangeRender: function()
      {
        var b = f;
        b.eventId = h.eventId;
        b.eventType = h.eventType.toLowerCase();
        b.partModel = n;
        b.partOpenFlag = v;
        this.el.className = "partChangeComp";
        this.$el.html(this.template(b));
        $(".bgWrap").on("webkitAnimationEnd", function()
        {
          $("#sideWrap").off();
          e || (a.tapBlock(!1), r = w = !1)
        })
      },
      createDom: function()
      {
        a.setGlobalView();
        $(a.ready.content).off();
        a.content.append(this.render().el);
        a.ready.hide();
        if (a.clearSectionModel && a.clearSectionModel.section.clearReward)
        {
          var b = this;
          a.tapBlock(!1);
          var c = a.clearSectionModel.section,
            k = C.clearRewardChestColor(c.clearReward);
          L.section(c.clearRewardCode, c, k, function()
          {
            b.mapInit()
          });
          d.getBaseData(a.getNativeObj());
          a.clearSectionModel = null
        }
        else a.clearSectionModel = null, this.mapInit()
      },
      mapInit: function()
      {
        if (e && e.part1.length || e && e.part2.length)
        {
          var b = e.part1.length && e.part2.length ? !0 : !1,
            c = e.part1.length ? e.part1 : e.part2,
            k = this;
          $("#commandDiv").on("nativeCallback", function(c)
          {
            b ? ($("#commandDiv").off(), k.partChange()) : ($("#commandDiv").off(), $(a.ready.content).on("webkitAnimationEnd", function(c)
            {
              "readyFadeIn" == c.originalEvent.animationName && (a.tapBlock(!1), a.scrollRefresh(null, null, null, !0))
            }), z(), a.androidKeyStop = !1, k.initFlag = !0, a.tapBlock(!1), e = null)
          });
          c.length ? (a.tapBlock(!0), d.pushEventBranch(f.chartList[m - 1], u, c)) : (z(), a.androidKeyStop = !1, d.pushEventBranch(f.chartList[m - 1], u), $(a.ready.content).on("webkitAnimationEnd", function(c)
          {
            "readyFadeIn" == c.originalEvent.animationName && (a.tapBlock(!1), a.scrollRefresh(null, null, null, !0))
          }), this.initFlag = !0)
        }
        else z(), a.androidKeyStop = !1, d.pushEventBranch(f.chartList[m - 1], u), $(a.ready.content).on("webkitAnimationEnd", function(c)
        {
          "readyFadeIn" == c.originalEvent.animationName && (a.tapBlock(!1), a.scrollRefresh(null, null, null, !0))
        }), this.initFlag = !0
      },
      announceOpen: function(b)
      {
        b.preventDefault();
        a.isScrolled() || a.eventFirstNavi(["navi_01", "navi_02", "navi_03", "navi_04_a"], h.eventId, "branch", null, !0)
      }
    }),
    x = function()
    {
      r = w = !1;
      v = 1 < f.chartList.length ? !0 : !1;
      G = 1 == parseInt(h.viewParameterMap.PART_NUM) ? !0 : !1;
      u = null;
      if (D) l.each(f.userEventBranchPointList, function(a, b)
      {
        a.point.questBattleId == D && (m = a.point.eventPartNo, u = a.pointId)
      });
      else
      {
        var b = !1;
        v && l.each(f.userEventBranchPointList, function(a, k)
        {
          2 != a.point.eventPartNo || "NEW" != a.status && "CLEAR" != a.status && "AGAIN" != a.status || (b = !0)
        });
        m = b ? 2 : 1
      }
      e = null;
      f.openedPointIdList.length && (e = {
        part1: [],
        part2: []
      }, l.each(f.openedPointIdList, function(a)
      {
        var b = f.userEventBranchPointList.filter(function(b, c)
        {
          if (b.pointId == a) return !0
        })[0];
        b && (1 == b.point.eventPartNo ? e.part1.push(b.pointId) : e.part2.push(b.pointId))
      }), e.part1.length ? m = 1 : e.part2.length && (m = 2));
      H();
      d.startBgm(h.viewParameterMap.BGM);
      d.changeBg(h.viewParameterMap.BG_IMG + ".ExportJson");
      a.setStyle(J + K);
      y = new M
    },
    A = B.View.extend(
    {
      events: function()
      {
        var b = {};
        b[a.cgti + " #mainBtn"] = this.questStart;
        return b
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model.toJSON()
        }));
        return this
      },
      questStart: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          var c = this.model.toJSON();
          a.questBattleModel = N(c.sectionModel, c.questModel, c.pointModel);
          var k = a.globalMenuView.getUserStatus(),
            c = c.questModel.questBattle.ap,
            k = k.ACP;
          if (c && k < c)
          {
            new a.PopupClass(
            {
              title: "关卡确认",
              content: "AP 不足",
              closeBtnText: "关闭"
            });
            var g = this;
            a.globalMenuView.apPopup(b, "AP 不足", function()
            {
              g.questStart(b)
            })
          }
          else location.href = "#/SupportSelect"
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    H = function()
    {
      n = f.eventBranchPartList[m - 1];
      var b = a.storage.userItemList.findWhere(
      {
        itemId: n.itemId
      });
      n.itemQuantity = b ? b.get("quantity") : 0;
      n.charaItemObj = function()
      {
        var b = [];
        l.each(n.charaIds.split(","), function(c)
        {
          var g = a.storage.userItemList.findWhere(
            {
              itemId: "EVENT_BRANCH_" + n.eventId + "_CHARA_" + c
            }),
            g = g ? g.get("quantity") : 0,
            d = {};
          d.key = c;
          d.quantity = g;
          b.push(d)
        });
        return b
      }();
      n.clearCount = 0;
      l.each(f.userEventBranchPointList, function(b)
      {
        n.eventPartNo == b.point.eventPartNo && (b = a.storage.userQuestBattleList.findWhere(
        {
          questBattleId: b.point.questBattleId
        })) && b.toJSON().cleared && n.clearCount++
      })
    },
    z = function()
    {
      $("#commandDiv").on("nativeCallback", function(b, c)
      {
        if (c && c.questBattleId && c.status && ("NEW" == c.status || "CLEAR" == c.status || "AGAIN" == c.status || "DISABLE" == c.status))
          if ("DISABLE" == c.status)
          {
            var k = l.findWhere(f.userEventBranchPointList,
              {
                pointId: c.pointId
              }),
              g = a.storage.userQuestBattleList.findWhere(
              {
                questBattleId: c.questBattleId
              }),
              g = g ? g.toJSON() :
              {};
            b = {};
            var e = [];
            console.log(k);
            e = k.conditionDetailList;
            b.conditionList = function()
            {
              var a = [],
                b = !1,
                c = !1;
              l.each(e, function(g, d, k)
              {
                d = "";
                console.log(g);
                g.cleared && (d = "clear");
                d = "<p class='" + d + "'>" + g.description + "</p>";
                g.operand && (b = !0, d += "<span>或</span>");
                b && c ? a[a.length - 1] += d : (b && !c && (c = !0), a.push(d))
              });
              return a
            }();
            r = !0;
            c = a.doc.createDocumentFragment();
            A.prototype.template = l.template($("#OpenConditionTemp").text());
            p = new A(
            {
              model: new F(b)
            });
            c.appendChild(p.render().el);
            a.doc.querySelector("#questDetail").appendChild(c);
            d.startSe(1002);
            a.addClass(a.doc.querySelector("#questDetail"), "open");
            a.addClass(a.doc.querySelector(".chartCautionText"), "show");
            a.scrollSet("scrollOuter", "scrollInner")
          }
        else if (g = (g = a.storage.userQuestBattleList.findWhere(
          {
            questBattleId: c.questBattleId
          })) ? g.toJSON() : !1)
        {
          var q = a.storage.userSectionList.findWhere(
            {
              sectionId: g.questBattle.sectionId
            }),
            q = q ? q.toJSON() :
            {},
            k = l.findWhere(f.userEventBranchPointList,
            {
              pointId: c.pointId
            });
          b = {};
          b.sectionModel = $.extend(!0,
          {}, q);
          b.questModel = $.extend(!0,
          {}, g);
          b.pointModel = $.extend(!0,
          {}, k);
          b.missionRewardCode = a.itemSet(b.questModel.questBattle.missionRewardCode);
          b.chestColor = b.missionRewardCode.chestColor;
          b.branchCharaId = c.charId;
          b.eventId = h.eventId;
          b.pointModel.point.hidden && !g.cleared && (b.sectionModel.section.title = "？？？？？");
          r = !0;
          c = a.doc.createDocumentFragment();
          A.prototype.template = l.template($("#QuestDetailTemp").text());
          p = new A(
          {
            model: new F(b)
          });
          c.appendChild(p.render().el);
          a.doc.querySelector("#questDetail").appendChild(c);
          d.startSe(1002);
          a.addClass(a.doc.querySelector("#questDetail"), "open");
          a.addClass(a.doc.querySelector(".chartCautionText"), "show")
        }
        else d.resumeEventBranch()
      })
    },
    N = function(a, c, d)
    {
      if (!a || !c) return !1;
      var b = {};
      a = a.section;
      b.questType = a.questType;
      b.title = h.shortName;
      b.battleTitle = d.point.title + " " + a.title;
      b.userQuestAdventureList = t.getPageJson().userQuestAdventureList;
      b.rewardCodeArr = [];
      a.secret && (b.secret = a.secret);
      b.questBattle = c.questBattle;
      b.eventFlag = !0;
      b.ap = c.questBattle.ap;
      b.difficulty = c.questBattle.difficulty;
      b.eventBranchData = d;
      b.storyForceStart = !0;
      b.cleared = c.cleared;
      b.missionStatus1 = c.missionStatus1;
      b.missionStatus2 = c.missionStatus2;
      b.missionStatus3 = c.missionStatus3;
      c = C.dropItemJson(c);
      c.firstClearReward && (b.firstClearReward = c.firstClearReward);
      c.firstClearRewardName && (b.firstClearRewardName = c.firstClearRewardName);
      c.firstClearRewardQuantity && (b.firstClearRewardQuantity = c.firstClearRewardQuantity);
      c.addDropItem && (b.addDropItem = c.addDropItem);
      c.addDropItemName && (b.addDropItemName = c.addDropItemName);
      c.addDropItemQuantity && (b.addDropItemQuantity = c.addDropItemQuantity);
      b.rewardCodeArr = c.list;
      b.rewardNameArr = c.nameList;
      b.rewardQuantityArr = c.quantityList;
      return b
    },
    E = function(b, c)
    {
      if (!window.isBrowser)
      {
        for (var f = [], g = "END" !== c ? "touches" : "changedTouches", e = 0; e < b.originalEvent[g].length; e++)
        {
          var q = b.originalEvent[g][e].identifier;
          0 > q && (q = -q);
          f[e] = {
            identifier: q,
            clientX: 1024 === a.displayWidth ? b.originalEvent[g][e].clientX : 1024 * b.originalEvent[g][e].clientX / 1280,
            clientY: 1024 === a.displayWidth ? b.originalEvent[g][e].clientY : 1024 * b.originalEvent[g][e].clientY / 1280
          }
        }
        switch (c)
        {
          case "START":
            d.callTouchesBegin(f);
            break;
          case "MOVE":
            d.callTouchesMove(f);
            break;
          case "END":
            d.callTouchesEnd(f)
        }
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
      id: "userChapterList"
    },
    {
      id: "pieceList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function(a)
    {
      a && (D = a);
      t.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      a.androidKeyStop = !0;
      f = t.getPageJson();
      C.supportPickUp(f);
      h = f.eventList.filter(function(a, b)
      {
        if ("BRANCH" == a.eventType) return !0
      })[0];
      f.eventMaster = h;
      var b = function()
      {
        var b = !1,
          c = h.startStoryId;
        c && (b = !0, l.each(f.userQuestAdventureList, function(a)
        {
          c === a.adventureId && (b = !1)
        }));
        if (b) $(a.ready.target).on("webkitAnimationEnd", function()
        {
          d.changeBg("web_black.jpg");
          $(a.ready.target).off();
          $(a.ready.target).on("webkitAnimationEnd", function(b)
          {
            "readyFadeOut" == b.originalEvent.animationName && (a.ready.target.className = "")
          });
          t.ajaxPost(a.linkList.userQuestAdventureRegist,
          {
            adventureId: String(c)
          }, function(b)
          {
            a.responseSetStorage(b);
            $("#commandDiv").on("nativeCallback", function(b, c)
            {
              $("#commandDiv").off();
              d.setWebView(!0);
              a.tapBlock(!1);
              a.eventFirstNavi(["navi_01", "navi_02", "navi_03", "navi_04_a"], h.eventId, "branch", function()
              {
                a.tapBlock(!0);
                x()
              })
            });
            setTimeout(function()
            {
              d.setWebView(!1);
              d.startStory(String(c),
              {
                canAuto: !1,
                canOpenLog: !1
              });
              window.isBrowser && $("#commandDiv").trigger("nativeCallback")
            }, 500)
          })
        }), a.addClass(a.ready.target, "preNativeFadeIn");
        else
        {
          var e = f.endStoryJson ? f.endStoryJson : null;
          e ? ($(a.ready.target).off(), $(a.ready.target).on("webkitAnimationEnd", function()
          {
            d.changeBg("web_black.jpg");
            $(a.ready.target).off();
            $(a.ready.target).on("webkitAnimationEnd", function(b)
            {
              "readyFadeOut" == b.originalEvent.animationName && (a.ready.target.className = "")
            });
            $("#commandDiv").on("nativeCallback", function(b, c)
            {
              $("#commandDiv").off();
              c && c.alternativeIdList ? t.ajaxPost(a.linkList.branchAlternativeEnd,
              {
                alternativeIdList: c.alternativeIdList
              }, function(b)
              {
                a.responseSetStorage(b);
                f = b;
                d.setWebView(!0);
                x()
              }) : (d.setWebView(!0), x())
            });
            setTimeout(function()
            {
              d.setWebView(!1);
              d.startBranchStory(e);
              window.isBrowser && (window.isBrowser && $("#commandDiv").trigger("nativeCallback"), x())
            }, 500)
          }), a.ready.target.classList.contains("preNativeFadeIn") ? $(a.ready.target).trigger("webkitAnimationEnd") : a.addClass(a.ready.target, "preNativeFadeIn")) : x()
        }
      };
      if (!a.branchVoiceCheck && h.existsVoice)
      {
        a.branchVoiceCheck = !0;
        var c = "section_event_" + h.eventId;
        $("#commandDiv").on("nativeCallback", function()
        {
          $("#commandDiv").off();
          d.setWebView(!0);
          b()
        });
        d.setWebView(!1);
        d.downloadFileFullVoice(c);
        window.isBrowser && $("#commandDiv").trigger("nativeCallback")
      }
      else a.branchVoiceCheck = !0, b()
    },
    remove: function(a)
    {
      y && (y.trigger("remove"), y.remove());
      p && p.removeView();
      p = null;
      $("#commandDiv").off();
      d.popEventBranch();
      a()
    }
  }
});
