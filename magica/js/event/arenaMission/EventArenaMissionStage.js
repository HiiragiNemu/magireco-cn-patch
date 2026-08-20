define("underscore backbone backboneCommon ajaxControl command text!template/event/arenaMission/EventArenaMissionStage.html text!css/event/arenaMission/EventArenaMissionStage.css text!css/event/arenaMission/EventArenaMissionCommon.css js/event/arenaMission/view/ArenaPartsView js/view/arena/ArenaInfoPartsView".split(" "), function(f, n, a, g, k, p, q, r, h, l)
{
  var m, e, t = n.View.extend(
  {
    events: function()
    {
      var c = {};
      c[a.cgti + " .arenaReloadBtn"] = this.matchingReload;
      c[a.cgti + " #missionBtn"] = this.missionConf;
      return c
    },
    initialize: function()
    {
      this.template = f.template(p);
      this.createDom()
    },
    render: function()
    {
      this.model = g.getPageJson();
      this.$el.html(this.template(
      {
        model: this.model,
        userEventArenaMission: a.userEventArenaMission,
        eventArenaMissionStage: a.eventArenaMissionStage
      }));
      return this
    },
    createDom: function()
    {
      a.content.append(this.render().el);
      this.matchExpiredAt = Date.parse(this.model.userArenaMissionStageMatch.expiredAt) / 1E3 | 0;
      this.accessServerTime = Date.parse(this.model.currentTime) / 1E3 | 0;
      this.accessClientTime = Date.parse(new Date) / 1E3 | 0;
      this.createView();
      a.setGlobalView();
      k.getBaseData(a.getNativeObj());
      a.ready.hide()
    },
    createView: function()
    {
      l.prototype.rootView = this;
      this.infoView = new l;
      a.doc.getElementById("bpGuageFreeRank").appendChild(this.infoView.render().el);
      this.createMattingList()
    },
    createMattingList: function()
    {
      var c = this.model.userArenaMissionStageMatch,
        d = [];
      if (c.opponentUserId1)
      {
        var b = {},
          b = c.opponentUserArenaBattleInfo1;
        b.userId = c.opponentUserId1;
        b.difficult = "HIGHER" === b.type ? 2 : "SAME" === b.type ? 1 : 0;
        b.battleType = c.arenaBattleType;
        d.push(b);
        b = null
      }
      c.opponentUserId2 && (b = {}, b = c.opponentUserArenaBattleInfo2, b.userId = c.opponentUserId2, b.difficult = "HIGHER" === b.type ? 2 : "SAME" === b.type ? 1 : 0, b.battleType = c.arenaBattleType, d.push(b), b = null);
      c.opponentUserId3 && (b = {}, b = c.opponentUserArenaBattleInfo3, b.userId = c.opponentUserId3, b.difficult = "HIGHER" === b.type ? 2 : "SAME" === b.type ? 1 : 0, b.battleType = c.arenaBattleType, d.push(b), b = null);
      d = f.sortBy(d, function(a)
      {
        return -1 * a.difficult
      });
      h.prototype.rootView = this;
      h.prototype.template = f.template($("#arenaParts").text());
      if (0 < d.length)
      {
        var e = a.doc.createDocumentFragment();
        f.each(d, function(a, c)
        {
          a = new h(a);
          e.appendChild(a.render().el)
        });
        a.doc.getElementById("matchingWrap").appendChild(e)
      }
      else a.doc.getElementById("matchingWrap").innerHTML = '<li class="nomatch">现在没有可以对战的对手。<br>请稍后再来。</li>'
    },
    missionConf: function(c)
    {
      c.preventDefault();
      if (!a.isScrolled())
      {
        console.log(a.eventArenaMissionStage);
        c = [];
        for (var d = 0; 3 > d;)
        {
          var b = {};
          b.text = a.eventArenaMissionStage.eventArenaMissionStage["missionMaster" + (d + 1)].description;
          b.classTxt = "NON_CLEAR" == a.eventArenaMissionStage["missionStatus" + (d + 1)] ? "off" : "clear";
          c.push(b);
          d = d + 1 | 0
        }
        console.log(c);
        new a.PopupClass(
        {
          popupType: "typeC",
          popupId: "missionConf",
          missionData: c
        }, $("#missionPopTemp").text())
      }
    },
    matchingReload: function(c)
    {
      c.preventDefault();
      if (!a.isScrolled())
      {
        var d = this.matchExpiredAt - this.accessServerTime - ((Date.parse(new Date) / 1E3 | 0) - this.accessClientTime);
        if (0 > d) new a.PopupClass(
        {
          title: "更换对手",
          content: "经过一定时间，对战对手发生了变化<br>即将回到活动首页",
          decideBtnText: "前往活动首页",
          canClose: !1,
          popupType: "typeC"
        }, null, function()
        {
          $(".decideBtn").on(a.cgti, function()
          {
            $(".decideBtn").off(a.cgti);
            location.href = "#/EventArenaMissionTop"
          })
        });
        else
        {
          c = d / 60 | 0;
          d = d - 60 * c | 0;
          10 > d && (d = "0" + d);
          var b = this;
          this.reloadPop = new a.PopupClass(
          {
            title: "更换对手",
            content: "消耗1BP变更对战对手吗？<br>(离重选对战对手还有" + c + ":" + d + ")",
            closeBtnText: "关闭",
            decideBtnText: "变更",
            popupType: "typeC"
          }, null, function()
          {
            $(".decideBtn").on(a.cgti, function()
            {
              a.isScrolled() || ($(".decideBtn").off(), a.tapBlock(!0), b.reloadFunc())
            })
          }, function()
          {
            $(".decideBtn").off()
          })
        }
      }
    },
    reloadFunc: function()
    {
      var c = this;
      if (0 < a.storage.userStatusList.findWhere(
        {
          statusId: "BTP"
        }).toJSON().point) g.ajaxPost(a.linkList.arenaMissionReload,
      {
        stageId: String(m.userArenaMissionStageMatch.stageId)
      }, function(b)
      {
        a.responseSetStorage(b);
        c.reCreateView(b)
      });
      else
      {
        a.tapBlock(!1);
        new a.PopupClass(
        {
          title: "错误",
          content: "BP 不足。",
          closeBtnText: "关闭",
          decideBtnText: "回复"
        });
        this.reloadPop = null;
        var d = function(b)
        {
          b.preventDefault();
          a.isScrolled() || (a.doc.removeEventListener(a.cgti, d), c.infoView.bpCurePop(b))
        };
        a.doc.getElementById("popupArea").getElementsByClassName("decideBtn")[0].addEventListener(a.cgti, d)
      }
    },
    reCreateView: function(c)
    {
      this.model.userArenaMissionStageMatch = c.userArenaMissionStageMatch;
      this.matchExpiredAt = Date.parse(this.model.userArenaMissionStageMatch.expiredAt) / 1E3 | 0;
      this.accessServerTime = Date.parse(this.model.userArenaMissionStageMatch.matchedAt) / 1E3 | 0;
      this.accessClientTime = Date.parse(new Date) / 1E3 | 0;
      this.trigger("resetListView");
      this.createMattingList();
      k.getBaseData(a.getNativeObj());
      this.infoView.afterReload(this.accessServerTime);
      this.reloadPop.remove();
      this.reloadPop = null;
      a.tapBlock(!1)
    },
    checkMatchingSpend: function(c)
    {
      this.matchExpiredAt > c ? (this.accessServerTime = c | 0, this.accessClientTime = Date.parse(new Date) / 1E3 | 0) : new a.PopupClass(
      {
        title: "更换对手",
        content: "经过一定时间，对战对手发生了变化<br>即将回到活动首页",
        decideBtnText: "前往活动首页",
        canClose: !1,
        popupType: "typeC"
      }, null, function()
      {
        $(".decideBtn").on(a.cgti, function()
        {
          $(".decideBtn").off(a.cgti);
          location.href = "#/EventArenaMissionTop"
        })
      })
    },
    removeHandler: function()
    {
      this.trigger("removeView");
      this.off();
      this.remove()
    }
  });
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
      id: "userDeckList"
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
      id: "userDoppelList"
    },
    {
      id: "userLive2dList"
    },
    {
      id: "userFollowList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function(a)
    {
      g.pageModelGet(this.needModelIdObj, null,
      {
        stageId: a
      })
    },
    init: function()
    {
      a.eventArenaMissionStage && a.userEventArenaMission ? (a.setStyle(q + r), m = g.getPageJson(), e = new t) : location.href = "#/EventArenaMissionTop"
    },
    remove: function(a)
    {
      e && (e.trigger("remove"), e.trigger("removeView"), e.remove());
      a()
    }
  }
});
