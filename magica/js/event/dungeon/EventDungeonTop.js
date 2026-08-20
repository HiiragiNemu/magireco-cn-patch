define("underscore backbone backboneCommon ajaxControl command text!template/event/dungeon/EventDungeonTop.html text!css/event/dungeon/EventDungeonTop.css js/event/dungeon/view/EventDungeonInfoPartsView js/event/dungeon/view/EventDungeonCpCureView js/event/dungeon/view/EventDungeonClearAnimationsView".split(" "), function(d, p, b, x, k, H, I, A, J, K)
{
  p.Model.extend(
  {});
  var g, q, r, v = !1,
    m, n, w, y, l = null,
    B = ["navi_04"],
    h, t, L = p.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " .live2dArea"] = this.touchL2d;
        a[b.cgti + " #partLinkBtn"] = this.partChange;
        a[b.cgti + " #helpBtn"] = this.announceOpen;
        a[b.cgti + " #shopBtn"] = this.shopLink;
        a[b.cgti + " .debugClearBtn"] = this.debugClear;
        a[b.cgti + " .debugFailedBtn"] = this.debugFailed;
        a[b.cgti + " .debugunitNaviBtn"] = this.debugUnitNavi;
        a[b.cgti + " .debugDisplayBtn"] = this.debugDisplay;
        return a
      },
      initialize: function(a)
      {
        this.areaViewList = [];
        this.template = d.template(H);
        this.createDom()
      },
      render: function()
      {
        var a = h;
        a.eventId = g.eventId;
        a.partModel = n;
        a.mapIconTypeMax = d.max(m, function(a)
        {
          return a.area.mapIconType
        }).area.mapIconType;
        this.$el.html(this.template(a));
        return this
      },
      createDom: function()
      {
        b.setGlobalView();
        A.prototype.rootView = this;
        this.infoView = new A;
        b.doc.getElementById("baseContainer").appendChild(this.infoView.render().el);
        C.prototype.rootView = this;
        this.areaDetailCurtainView = new C;
        b.content.append(this.render().el);
        this.areaList = b.doc.getElementById("areaList");
        this.lineList = b.doc.getElementById("lineList");
        this.createPartInfo();
        this.createAreaView();
        b.scrollSet("areaWrap", "scrollInner");
        !d.find(m, function(a)
        {
          return 0 == a.sectionModel.cleared
        }) && b.dungeonAreaModel && b.forceScrollPreset("areaWrap", "scrollInner", b.dungeonAreaModel.areaId, !0);
        b.ready.hide();
        if ("已通关" == b.dungeonEnd)
        {
          if (b.dungeonAreaModel)
          {
            var a = d.findWhere(m,
            {
              areaId: b.dungeonAreaModel.areaId
            });
            a.firstClear = a.firstClearedAt && !b.dungeonAreaModel.firstClearedAt;
            a.firstComp = a.missionCleared1 && a.missionCleared2 && a.missionCleared3 && (!b.dungeonAreaModel.missionCleared1 || !b.dungeonAreaModel.missionCleared2 || !b.dungeonAreaModel.missionCleared3);
            for (var c = 1; 3 >= c;) a["missionStatus" + c] = a["missionCleared" + c] ? b.dungeonAreaModel["missionCleared" + c] ? "cleared" : "firstClear" : "", c = c + 1 | 0;
            this.clearAction(a, u)
          }
        }
        else "FAILED" == b.dungeonEnd ? this.failedAction(u) : v || u();
        b.dungeonAreaModel = null;
        b.dungeonEnd = null
      },
      clearAction: function(a, b)
      {
        a.firstClearedAt || (a.firstClearedAt = null);
        K.section(a, b)
      },
      failedAction: function(a)
      {
        new b.PopupClass(
        {
          title: "区域攻略失败",
          content: "由于所有队员都进入无法战斗状态，<br>已从区域退出",
          popupType: "typeA",
          popupId: "areaFailed",
          closeBtnText: "确定"
        }, null, null, a)
      },
      touchL2d: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled() && l && !window.isBrowser)
        {
          a = a.originalEvent.changedTouches ? a.originalEvent.changedTouches[0] : a.originalEvent;
          a = {
            id: l,
            x: a.pageX,
            y: a.pageY
          };
          var c = [32, 33, 36, 37],
            c = c[Math.floor(Math.random() * c.length)] + 1,
            f = l.substring(0, l.length - 2);
          a.voice = "vo_char_" + f + "_00_" + c;
          k.storyMotionL2dVoice(a);
          this.l2dTouchCnt++
        }
      },
      createPartInfo: function()
      {
        var a = d.template($("#PartInfoParts").text()),
          c = n;
        c.eventId = g.eventId;
        c.partNum = r;
        b.doc.getElementById("partInfoWrap").innerHTML = a(c)
      },
      createAreaView: function()
      {
        D.prototype.template = d.template($("#AreaListParts").text());
        var a = b.doc.createDocumentFragment(),
          c = b.doc.createDocumentFragment(),
          f = this;
        d.each(w, function(e, d)
        {
          e.index = d;
          e = new D(
          {
            model: e
          });
          a.appendChild(e.render().el);
          f.areaViewList.push(e);
          0 != d && c.appendChild(b.doc.createElement("li"))
        });
        var e = "oddRight";
        0 != a.childElementCount % 2 && (e = "evenRight");
        this.areaList.appendChild(a);
        this.areaList.className = e;
        this.lineList.appendChild(c);
        this.lineList.className = e
      },
      removeAreaView: function()
      {
        d.each(this.areaViewList, function(a, b)
        {
          a.removeView()
        });
        for (this.areaViewList = []; this.lineList.firstChild;) this.lineList.removeChild(this.lineList.firstChild)
      },
      partChange: function(a)
      {
        if (a && (a.preventDefault(), b.isScrolled())) return;
        this.removeAreaView();
        b.scrollDestroy("areaWrap", "scrollInner");
        q = 1 == q ? 2 : 1;
        E();
        this.createPartInfo();
        this.createAreaView();
        b.scrollSet("areaWrap", "scrollInner");
        u()
      },
      announceOpen: function(a)
      {
        a.preventDefault();
        b.isScrolled() || b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], g.eventId, "dungeon", null, !0)
      },
      shopLink: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (location.href = "#/ShopTop/" + n.shopId)
      },
      debugClear: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = a.currentTarget.dataset;
          var c = m[0];
          c.missionCleared1 = "" != a.mission1;
          c.missionCleared2 = "" != a.mission2;
          c.missionCleared3 = "" != a.mission3;
          c.missionStatus1 = a.mission1;
          c.missionStatus2 = a.mission2;
          c.missionStatus3 = a.mission3;
          c.firstClear = 1 == a.firstclear;
          c.firstComp = 1 == a.firstcomp;
          this.clearAction(c, null)
        }
      },
      debugFailed: function(a)
      {
        a.preventDefault();
        b.isScrolled() || this.failedAction(null)
      },
      debugUnitNavi: function(a)
      {
        a.preventDefault();
        b.isScrolled() || b.eventFirstNavi(B, g.eventId, "dungeon")
      },
      debugDisplay: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = b.doc.getElementById("debugArea");
          c.style.display = "none";
          setTimeout(function()
          {
            c.style.display = "block"
          }, 3E4)
        }
      }
    }),
    D = p.View.extend(
    {
      tagName: "li",
      id: function()
      {
        return "area_" + this.model.area.areaId
      },
      className: "areaChild",
      events: function()
      {
        var a = {};
        a[b.cgti + " .chapter"] = this.titleTapFunc;
        return a
      },
      initialize: function(a) {},
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        this.el.setAttribute("data-scroll-hash", this.model.area.areaId);
        return this
      },
      setTouch: function(a)
      {
        b.addClass(this.el, "touch")
      },
      releaseTouch: function(a)
      {
        b.removeClass(this.el, "touch")
      },
      titleTapFunc: function(a)
      {
        a.preventDefault();
        !b.isScrolled() && this.model.sectionModel.section.sectionId && (F.prototype.rootView = this, new F(
        {
          model: this.model
        }))
      },
      removeView: function()
      {
        this.trigger("removeView");
        this.off();
        this.remove()
      }
    }),
    F = p.View.extend(
    {
      id: "AreaConfirm",
      events: function()
      {
        var a = {};
        a[b.cgti + " .arrow"] = this.carousel;
        a[b.cgti + " .closeBtn"] = this.closeBtn;
        a[b.cgti + " .decideBtn"] = this.decideBtnEvent;
        return a
      },
      initialize: function(a)
      {
        this.listenTo(this.rootView, "removeView", this.removeView);
        this.cnt = this.model.index;
        this.limit = w.length;
        this.template = d.template($("#AreaConfirmParts").text());
        this.createDom();
        this.createAreaDetail();
        b.addClass(b.doc.getElementById("areaDetailCurtain"), "on");
        b.addClass(b.doc.getElementById("infoPartsWrap"), "on")
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        2 <= this.limit && this.setArrow();
        return this
      },
      createDom: function()
      {
        b.doc.getElementById("overlapContainer").appendChild(this.render().el);
        overlapContainer.style.width = "100%"
      },
      setArrow: function()
      {
        0 >= this.cnt ? b.addClass(this.el.querySelector(".left"), "hide") : b.removeClass(this.el.querySelector(".left"), "hide");
        this.cnt + 1 >= this.limit ? b.addClass(this.el.querySelector(".right"), "hide") : b.removeClass(this.el.querySelector(".right"), "hide")
      },
      createAreaDetail: function()
      {
        this.areaDetailView && (this.areaDetailView.removeView(), this.areaDetailView = null);
        y = w[this.cnt];
        G.prototype.rootView = this;
        this.areaDetailView = new G(
        {
          model: y
        })
      },
      carousel: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a.currentTarget.classList.contains("right") ? this.cnt + 1 < this.limit && this.cnt++ : 0 <= this.cnt - 1 && this.cnt--, this.setArrow(), this.createAreaDetail())
      },
      decideBtnEvent: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (1 > b.storage.userStatusList.findWhere(
        {
          statusId: "CP"
        }).toJSON().point ? new b.PopupClass(
        {
          title: "错误",
          content: "CP不足。",
          closeBtnText: "关闭",
          decideBtnText: "回复",
          decideBtnEvent: function(a)
          {
            a.preventDefault();
            b.isScrolled() || J.popupStart()
          }
        }) : d.find(m, function(a)
        {
          return 1 == a.sectionModel.cleared
        }) ? this.linkNext() : b.eventFirstNavi(B, g.eventId, "dungeon", this.linkNext, !0))
      },
      linkNext: function()
      {
        b.userEventDungeon = h.userEventDungeon;
        b.dungeonAreaModel = y;
        location.href = "#/DeckFormation/dungeon"
      },
      closeBtn: function()
      {
        b.addClass(this.el, "close");
        setTimeout(function()
        {
          this.removeView()
        }.bind(this), 300)
      },
      removeView: function()
      {
        b.doc.getElementById("overlapContainer").style.width = "";
        b.removeClass(b.doc.getElementById("areaDetailCurtain"), "on");
        b.removeClass(b.doc.getElementById("infoPartsWrap"), "on");
        this.trigger("removeView");
        this.off();
        this.remove()
      }
    }),
    G = p.View.extend(
    {
      id: "AreaDetail",
      initialize: function(a)
      {
        this.listenTo(this.rootView, "removeView", this.removeView);
        this.template = d.template($("#AreaDetailParts").text());
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        return this
      },
      createDom: function()
      {
        b.doc.getElementById("AreaConfirm").appendChild(this.render().el);
        k.getBaseData(b.getNativeObj())
      },
      removeView: function()
      {
        this.trigger("removeView");
        this.off();
        this.remove()
      }
    }),
    C = p.View.extend(
    {
      id: "areaDetailCurtain",
      initialize: function()
      {
        this.listenTo(this.rootView, "removeView", this.removeView);
        this.createDom()
      },
      render: function()
      {
        this.$el.html();
        return this
      },
      createDom: function()
      {
        b.doc.getElementById("baseContainer").appendChild(this.render().el)
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    u = function()
    {
      k.endL2d();
      var a = {};
      a.id = l;
      a.x = 286;
      a.y = 1024 === b.displayWidth ? Math.floor(b.doc.getElementsByTagName("body")[0].offsetHeight / 2) : Math.ceil(b.shortSize / 2);
      if (l)
      {
        var c = "vo_char_" + l.substring(0, l.length - 2) + "_00_",
          f = [],
          e = Number(h.currentTime.split(" ")[1].split(":")[0]),
          d = Number(h.currentTime.split(" ")[1].split(":")[1]);
        6 <= e && 9 >= e && !(9 == e && 0 < d) ? f.push(24) : 11 <= e && 13 >= e && !(13 == e && 0 < d) ? f.push(25) : 17 <= e && 19 >= e && !(19 == e && 0 < d) ? f.push(26) : 22 <= e || 0 == e && !(0 == e && 0 < d) ? f.push(27) : f.push(23);
        a.key = c + (f[Math.floor(Math.random() * f.length)] + 1);
        a.type = 0
      }
      else a.key = "idle", a.type = 1;
      k.startL2d(a)
    },
    E = function()
    {
      w = d.filter(m, function(a)
      {
        return a.area.eventPartNo == q
      }).reverse();
      n = h.eventDungeonPartList[q - 1];
      var a = b.storage.userItemList.findWhere(
      {
        itemId: n.itemId
      });
      n.itemQuantity = a ? a.get("quantity") : 0;
      l = n.live2dId || null
    },
    z = function()
    {
      b.setStyle(I);
      r || (r = parseInt(g.viewParameterMap.PART_NUM));
      q = r;
      m = h.userEventDungeonAreaList;
      d.each(m, function(a, f)
      {
        a.area.captureInfo = a.area.captureInfo.replace(/＠/g, "<br>");
        f = (f = b.storage.userSectionList.findWhere(
        {
          sectionId: a.area.sectionId
        })) ? f.toJSON() :
        {};
        a.sectionModel = $.extend(!0,
        {}, f);
        a.sectionModel.section ? a.clearRewardCode = b.itemSet(f.section.clearRewardCode) : (a.sectionModel.section = {}, a.sectionModel.section.title = "？？？？？", a.sectionModel.section.difficulty = "--");
        a.missionRewardCode = b.itemSet(a.area.missionRewardCodes);
        a.pointComplete = !1;
        if (h.userEventDungeonPointListMap[a.areaId])
        {
          f = d.filter(h.userEventDungeonPointListMap[a.areaId], function(a)
          {
            return !a.clearedAt
          });
          var c = h.userEventDungeonPointListMap[a.areaId].length,
            g = c - f.length;
          a.totalPointNum = c;
          a.clearPointNum = g;
          a.pointComplete = 0 === f.length ? !0 : !1
        }
        console.log(a)
      });
      E();
      var a = g.viewParameterMap.BGM;
      k.changeBg(g.viewParameterMap.BG_IMG + ".ExportJson");
      k.startBgm(a);
      t = new L
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
      r = a ? a : null;
      x.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      h = x.getPageJson();
      b.historyArr = ["MyPage", "EventDungeonTop"];
      b.clearSectionModel = null;
      b.clearChapterModel = null;
      if (g = h.eventList.filter(function(a, b)
        {
          if ("DUNGEON" == a.eventType) return !0
        })[0])
        if (h.eventMaster = g, window.isBrowser) z();
        else
        {
          var a = g.startStoryId;
          a && (v = !0, d.each(h.userQuestAdventureList, function(b)
          {
            a === b.adventureId && (v = !1)
          }));
          v ? ($(b.ready.target).on("webkitAnimationEnd", function()
          {
            k.changeBg("web_black.jpg");
            $(b.ready.target).off();
            $(b.ready.target).on("webkitAnimationEnd", function(a)
            {
              "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
            });
            x.ajaxPost(b.linkList.userQuestAdventureRegist,
            {
              adventureId: String(a)
            }, function(c)
            {
              b.responseSetStorage(c);
              $("#commandDiv").on("nativeCallback", function(a, c)
              {
                $("#commandDiv").off();
                k.setWebView(!0);
                b.tapBlock(!1);
                z();
                b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], g.eventId, "dungeon", function()
                {
                  u()
                })
              });
              setTimeout(function()
              {
                var b = {
                  canAuto: !1,
                  canOpenLog: !1
                };
                k.setWebView(!1);
                window.isLocal ? $("#commandDiv").trigger("nativeCallback") : k.startStory(String(a), b)
              }, 500)
            })
          }), b.addClass(b.ready.target, "preNativeFadeIn")) : z()
        }
      else location.href = "#/MyPage"
    },
    startCommand: function() {},
    removeCommand: function()
    {
      k.endL2d()
    },
    remove: function(a)
    {
      t && (t.removeAreaView(), t.trigger("removeView"), t.remove());
      a()
    }
  }
});
