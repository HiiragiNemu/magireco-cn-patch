define("underscore backbone backboneCommon ajaxControl command text!template/regularEvent/groupBattle/RegularEventGroupBattleSelectUnion.html text!css/regularEvent/groupBattle/RegularEventGroupBattleSelectUnion.css".split(" "), function(d, f, b, k, g, l, m)
{
  f.Model.extend();
  var c, e, h, p = f.View.extend(
  {
    events: function()
    {
      var a = {};
      a[b.cgti + " #unionDetailBtn"] = this.unionDetail;
      a[b.cgti + " #helpBtn"] = this.helpPopup;
      a[b.cgti + " .changeUnionBtn"] = this.changeUnion;
      a["touchstart #unionBtnWrap"] = this.swipeStart;
      a["touchmove  #unionBtnWrap"] = this.swipeing;
      a["touchend   #unionBtnWrap"] = this.swipeEnd;
      a["webkitTransitionEnd #unionLogoWrap"] = this.unionLogoAnimeEnd;
      a["webkitAnimationEnd #unionLogoWrap"] = this.unionLogoAnimeEnd;
      a["webkitanimationend #unionLogoWrap"] = this.unionLogoAnimeEnd;
      a["animationend #unionLogoWrap"] = this.unionLogoAnimeEnd;
      return a
    },
    swipeStart: function(a)
    {
      this.touching = !0;
      this.touchPoint = a.originalEvent.changedTouches[0].clientX
    },
    swipeing: function(a)
    {
      if (this.touching && (a = a.originalEvent.changedTouches[0].clientX - this.touchPoint, !(50 > a && -50 < a)))
      {
        this.touching = !1;
        g.startSe(1002);
        var b = 0; - 50 > a ? b = 1 : 50 < a && (b = -1);
        0 != b && this.changeUnion(null, b)
      }
    },
    swipeEnd: function(a)
    {
      this.touching && (this.touching = !1, this.decidePop())
    },
    initialize: function(a)
    {
      this.unionIndex = 0;
      this.listenTo(this.model, "change", this.render);
      this.template = d.template(l);
      this.createDom()
    },
    render: function()
    {
      var a = c,
        b = d.sortBy(c.groupMemberList, function(a, b)
        {
          return a.groupPoint
        });
      a.sortedGroupMemberList = b;
      this.$el.html(this.template(a));
      return this
    },
    createDom: function()
    {
      b.content.append(this.render().el);
      this.unionLogoTemp = d.template($("#unionLogoPartsTemp").text());
      this.selectUnionTemp = d.template($("#selectUnionPartsTemp").text());
      this.changeRender();
      b.ready.hide()
    },
    selectUnion: function(a)
    {
      a.preventDefault();
      b.isScrolled()
    },
    unionDetail: function(a)
    {
      a.preventDefault();
      b.isScrolled() || new b.PopupClass(
      {
        title: "所属势力详情",
        content: "<div id='unionImg'><img src='/magica/resource/image_web/regularEvent/groupBattle/union_logo_0" + c.charaUnionList[this.unionIndex].unionId + ".png'/></div>",
        popupType: "typeC",
        popupId: "unionDetailPopuo"
      })
    },
    changeRender: function()
    {
      var a = c.charaUnionList[this.unionIndex];
      b.doc.getElementById("unionInfoWrap").innerHTML = this.unionLogoTemp(
      {
        union: a
      });
      b.doc.getElementById("unionDetailBtn").className = "hide";
      var n = c.charaUnionList[0 > this.unionIndex - 1 ? c.charaUnionList.length - 1 : this.unionIndex - 1],
        d = c.charaUnionList[this.unionIndex + 1 >= c.charaUnionList.length ? 0 : this.unionIndex + 1];
      b.doc.getElementById("unionBtnWrap").innerHTML = this.selectUnionTemp(
      {
        selectedUnion: a,
        union1: n,
        union2: d
      });
      g.changeBg("web_regular_hideout_bg_" + [18081, 13133, 16133, 21203, 17201][this.unionIndex] + ".ExportJson")
    },
    changeUnion: function(a, d)
    {
      if (a)
      {
        a.preventDefault();
        if (b.isScrolled()) return;
        d = "rightArrow" == a.currentTarget.id ? 1 : -1
      }
      this.unionIndex += d;
      0 > this.unionIndex ? this.unionIndex = c.charaUnionList.length - 1 : this.unionIndex >= c.charaUnionList.length && (this.unionIndex = 0);
      this.changeRender()
    },
    decidePop: function()
    {
      var a = function(a)
      {
        a.preventDefault();
        b.isScrolled() || (b.g_popup_instance.remove(), location.href = "#/RegularEventGroupBattleTop")
      }.bind(this);
      new b.PopupClass(
      {
        title: "决定所属势力",
        content: "<div id='unionLogo' class='union0" + this.unionIndex + "'></div><p>" + c.charaUnionList[this.unionIndex].name + "开始小组对战。<br>确定吗?<br><br><p class='c_red'>※所属势力到下次举办前无法更改。</p>",
        popupType: "typeC",
        popupId: "unionDecidePopup",
        closeBtnText: "取消",
        decideBtnText: "开始",
        decideBtnEvent: a
      })
    },
    helpPopup: function(a)
    {
      a.preventDefault();
      b.isScrolled() || b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], h.regularEventId, "groupBattle", null, !0, "regularEvent")
    },
    unionLogoAnimeEnd: function(a)
    {
      b.doc.getElementById("unionDetailBtn").className = ""
    }
  });
  f.View.extend(
  {
    initialize: function(a)
    {
      this.listenTo(this.model, "change", this.render);
      this.createDom();
      this.status = ""
    },
    render: function()
    {
      this.$el.html(this.template(this.model));
      return this
    },
    createDom: function()
    {
      b.content.append(this.render().el)
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
      k.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      b.setGlobalView();
      b.setStyle(m);
      c = k.getPageJson();
      h = d.findWhere(c.regularEventList,
      {
        regularEventType: "GROUPBATTLE"
      });
      c.eventMaster = h;
      b.tapBlock(!1);
      b.androidKeyStop = !1;
      e = new p
    },
    remove: function(a)
    {
      e && (e.trigger("remove"), e.remove(), e = null);
      g.endL2d();
      a()
    }
  }
});
