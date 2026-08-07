define("underscore backbone backboneCommon ajaxControl command text!css/event/arenaMission/EventArenaMissionResult.css text!css/event/arenaMission/EventArenaMissionCommon.css text!template/event/arenaMission/EventArenaMissionResult.html js/follow/FollowPopup".split(" "), function(g, m, a, h, f, n, p, q, r)
{
  var k, l, t = m.View.extend(
  {
    events: function()
    {
      var b = {};
      b[a.cgti + " #enemyClip"] = this.enemyPopup;
      b[a.cgti + " #touchScreen"] = this.toggles;
      b["webkitTransitionEnd #resultTitle"] = this.toggleTapBlock;
      b["webkitAnimationEnd #resultTitle"] = this.toggleTapBlock;
      b["webkitanimationend #resultTitle"] = this.toggleTapBlock;
      b["animationend #resultTitle"] = this.toggleTapBlock;
      b["webkitTransitionEnd #pointsWrap"] = this.toggleTapStep;
      b["webkitAnimationEnd #pointsWrap"] = this.toggleTapStep;
      b["webkitanimationend #pointsWrap"] = this.toggleTapStep;
      b["animationend #pointsWrap"] = this.toggleTapStep;
      b["webkitTransitionEnd #enemyBtn"] = this.enemyBtnActive;
      b["webkitAnimationEnd #enemyBtn"] = this.enemyBtnActive;
      b["webkitanimationend #enemyBtn"] = this.enemyBtnActive;
      b["animationend #enemyBtn"] = this.enemyBtnActive;
      return b
    },
    initialize: function(b)
    {
      this.template = g.template(q);
      this.model = b;
      this.newestModel = h.getPageJson();
      this.model.userArenaBattleResultList ? (this.tapFlag = !1, this.tapStep = "first", a.responseSetStorage(this.model), this.allInitialized(), this.checkEnemy(), this.createDom()) : (f.setWebView(), a.androidKeyStop = !0, new a.PopupClass(
      {
        title: "错误",
        content: "无法正确获取战斗结果。<br>返回活动首页。",
        closeBtnText: "确定"
      }, null, null, function()
      {
        f.endArena();
        f.nativeReload("#/TopPage")
      }))
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
      a.globalMenuView && a.globalMenuView.trigger("removeView");
      a.content.append(this.render().el);
      f.getBaseData(a.getNativeObj());
      var b;
      b = "WIN" === this.model.userArenaBattleResultList[0].arenaBattleStatus ? 1701 : 1702;
      var c = this;
      this.resultSe = setTimeout(function()
      {
        f.startSe(b);
        c.resultSe = null
      }, 2666);
      f.setWebView()
    },
    toggleTapBlock: function(a)
    {
      this.tapFlag = !0
    },
    toggleTapStep: function(a)
    {
      this.tapStep = "second"
    },
    checkEnemy: function()
    {
      for (var a = h.getPageJson().userProfile, c = [], d = 1; 6 > d; d++) a.userDeck["userCardId" + d] && c.push(g.findWhere(a.userCardList,
      {
        id: a.userDeck["userCardId" + d]
      }));
      c = Date.parse(this.newestModel.currentTime) / 1E3;
      (d = a.lastAccessDate ? Date.parse(a.lastAccessDate) / 1E3 : null) ? (c = (c - d) / 60, 16 > c ? c = "15 分钟以内" : 60 > c ? c = Math.floor(c) + "分钟前" : 60 < c && 1440 > c ? c = Math.floor(c / 60) + "小时前" : (c = c / 60 / 24, c = 30 < c ? Math.floor(c / 30) + "个月前" : Math.floor(c) + "天前")) : c = "-天前";
      a.loginTimeLag = c;
      this.model.enemyData = a
    },
    allInitialized: function()
    {
      this.clearAnim = !1;
      var b = this;
      this.model.eventModel = g.findWhere(h.getPageJson().eventList,
      {
        eventType: "ARENAMISSION"
      });
      this.model.playedStageModel = a.eventArenaMissionStage;
      var c = g.findWhere(b.model.userEventArenaMissionStageList,
      {
        stageId: b.model.playedStageModel.stageId
      });
      c ? (this.model.nowCleared = !this.model.playedStageModel.rewardDone && c.rewardDone ? !0 : !1, a.eventArenaMissionStage = c) : this.model.nowCleared = !1;
      this.model.missionData = {};
      for (var d = 0, b = this; 3 > d;)
      {
        var e = {},
          f = "mission" + (d + 1);
        e.reward = a.itemSet(b.model.playedStageModel.eventArenaMissionStage[f + "RewardCode"]);
        e.text = b.model.playedStageModel.eventArenaMissionStage["missionMaster" + (d + 1)].description;
        e.oldState = b.model.playedStageModel["missionStatus" + (d + 1)];
        e.newState = c ? c["missionStatus" + (d + 1)] : b.model.playedStageModel["missionStatus" + (d + 1)];
        e.classTxt = "NON_CLEAR" == e.oldState && "CLEARED" == e.newState ? "clear" : "CLEARED" == e.oldState ? "cleared" : "off";
        b.model.missionData[f] = e;
        d = d + 1 | 0
      }
      d = this.model.playedStageModel.eventArenaMissionStage.stageClearRewardCode;
      this.model.rewardData = {};
      this.model.rewardData.rewardType = -1 < d.indexOf("GIFT_") ? "gift" : -1 < d.indexOf("LIVE2D_") ? "live2d" : -1 < d.indexOf("DOPPEL_") ? "doppel" : -1 < d.indexOf("GEM_") ? "gem" : -1 < d.indexOf("PIECE_") ? "memoria" : "main";
      this.model.rewardData.itemData = a.itemSet(this.model.playedStageModel.eventArenaMissionStage.stageClearRewardCode);
      this.model.rewardData.displayName = this.model.playedStageModel.eventArenaMissionStage.stageClearReward.displayName;
      this.model.oldUserEventArenaMission = a.userEventArenaMission;
      a.userEventArenaMission = this.model.userEventArenaMission;
      d = this.model.playedStageModel.eventArenaMissionStage.needClearPoint;
      this.model.eventPointObj = {
        firstViewPoint: d - this.model.oldUserEventArenaMission.eventPoint,
        secondPoint: d - this.model.userEventArenaMission.eventPoint
      };
      this.model.arenaDecks = {};
      this.model.arenaDecks.noneLeader = [];
      b = g.findWhere(a.storage.userDeckList.toJSON(),
      {
        deckType: 22
      });
      c = g.findWhere(a.storage.userCardList.toJSON(),
      {
        id: b.questEpisodeUserCardId
      });
      for (d = 1; 6 > d; d++) b["userCardId" + d] && (b.questEpisodeUserCardId !== b["userCardId" + d] ? (e = g.findWhere(a.storage.userCardList.toJSON(),
      {
        id: b["userCardId" + d]
      }), this.model.arenaDecks.noneLeader.push(e)) : this.model.arenaDecks.leaderCard = c);
      a.historyArray = this.model.nowCleared ? ["MainQuest", "EventArenaMissionTop"] : ["EventArenaMissionTop", "EventArenaMissionStage"];
      this.backLink = this.model.nowCleared ? "#/EventArenaMissionTop" : "#/EventArenaMissionStage/" + this.model.playedStageModel.stageId
    },
    enemyPopup: function(b)
    {
      b.preventDefault();
      a.isScrolled() || (b.currentTarget.classList.contains("canTap") || b.currentTarget.classList.contains("skipAnim") ? r.instantPopup(b, this.model.enemyData, "arena", this) : this.toggles(b))
    },
    toggles: function(b)
    {
      b.preventDefault();
      if (!a.isScrolled() && this.tapFlag)
        if (this.tapFlag = !1, "first" === this.tapStep)
        {
          a.addClass(a.doc.getElementById("touchScreen"), "nodisp");
          a.addClass(a.doc.getElementById("mainWrap"), "skipAnim");
          a.addClass(a.doc.getElementById("resultTitle"), "skipAnim");
          a.addClass(a.doc.getElementById("enemyBtn"), "skipAnim");
          a.addClass(a.doc.getElementById("enemyClip"), "skipAnim");
          a.addClass(a.doc.getElementById("missionWrap"), "skipAnim");
          this.tapStep = "second";
          var c = this;
          setTimeout(function()
          {
            c.tapFlag = !0;
            a.removeClass(a.doc.getElementById("touchScreen"), "nodisp")
          }, 300)
        }
      else if (a.addClass(a.doc.getElementById("touchScreen"), "nodisp"), a.addClass(a.doc.getElementById("mainWrap").getElementsByClassName("touch_screen")[0], "off"), a.addClass(a.doc.getElementById("enemyBtn"), "off"), this.clearAnim) a.addClass(a.doc.getElementById("resultMirror"), "endAnim"), a.addClass(a.doc.getElementById("resultTitle"), "endAnim"), a.addClass(a.doc.getElementById("stageClearWrap"), "endAnim"), this.nextPageHandler(b);
      else if (this.model.playedStageModel.rewardDone) a.addClass(a.doc.getElementById("mainWrap"), "endAnim"), a.addClass(a.doc.getElementById("resultMirror"), "endAnim"), a.addClass(a.doc.getElementById("resultTitle"), "endAnim"), a.addClass(a.doc.getElementById("enemyBtn"), "fadeOut"), this.nextPageHandler(b);
      else
      {
        var c = this,
          d = a.doc.querySelector("#leftCount"),
          e = Number(d.textContent),
          g = function()
          {
            0 == e ? setTimeout(function()
            {
              c.rankUps()
            }, 300) : setTimeout(function()
            {
              a.addClass(a.doc.getElementById("mainWrap"), "endAnim");
              a.addClass(a.doc.getElementById("resultMirror"), "endAnim");
              a.addClass(a.doc.getElementById("resultTitle"), "endAnim");
              a.addClass(a.doc.getElementById("enemyBtn"), "fadeOut");
              c.nextPageHandler(b)
            }, 500)
          };
        if (c.model.eventPointObj.firstPoint !== c.model.eventPointObj.secondPoint) var h = setInterval(function()
        {
          f.startSe(1007);
          e--;
          d.textContent = e;
          c.model.eventPointObj.secondPoint >= e && (clearInterval(h), g())
        }, 20);
        else this.nextPageHandler(b)
      }
    },
    rankUpAfter: function()
    {
      this.tapFlag = !0;
      a.removeClass(a.doc.getElementById("touchScreen"), "nodisp");
      a.addClass(a.doc.querySelector("#stageClearWrap .touch_screen"), "show")
    },
    rankUps: function()
    {
      var b = this;
      a.addClass(a.doc.getElementById("enemyBtn"), "fadeOut");
      a.addClass(a.doc.getElementById("mainWrap"), "fadeOut");
      setTimeout(function()
      {
        a.addClass(a.doc.getElementById("stageClearBg"), "anim");
        a.addClass(a.doc.getElementById("stageClearWrap"), "anim");
        b.clearAnim = !0
      }, 300);
      f.startSe(1703);
      setTimeout(function()
      {
        b.rankUpAfter()
      }, 2E3)
    },
    nextPageHandler: function(a)
    {
      a && a.preventDefault();
      this.storyCheck(this.backLink)
    },
    storyCheck: function(b)
    {
      $(a.ready.target).on("webkitAnimationEnd", function()
      {
        $(a.ready.target).off("webkitAnimationEnd");
        $(a.ready.target).on("webkitAnimationEnd", function(b)
        {
          "readyFadeOut" == b.originalEvent.animationName && (a.ready.target.className = "")
        });
        setTimeout(function()
        {
          f.endArena();
          location.href = b
        }, 500)
      });
      a.addClass(a.ready.target, "preNativeFadeIn")
    },
    enemyBtnActive: function(b)
    {
      a.addClass(a.doc.getElementById("enemyClip"), "canTap")
    },
    removeView: function()
    {
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
      id: "pieceList"
    },
    {
      id: "itemList"
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
      id: "userDeckList"
    },
    {
      id: "userGiftList"
    },
    {
      id: "userPieceList"
    },
    {
      id: "userPieceSetList"
    },
    {
      id: "userItemList"
    },
    {
      id: "userFollowList"
    },
    {
      id: "userDailyChallengeList"
    },
    {
      id: "userTotalChallengeList"
    },
    {
      id: "userLimitedChallengeList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function()
    {
      a.oldModel = {};
      a.storage.userArenaBattle && (a.oldModel.userArenaBattle = a.storage.userArenaBattle.toJSON());
      var b = {
        strUserId: a.battleEnemy
      };
      a.battleEnemy = null;
      h.pageModelGet(this.needModelIdObj, null, b)
    },
    init: function()
    {
      a.ready.hide();
      f.startBgm("bgm03_story09");
      a.androidKeyStop = !0;
      l = a.questNativeResponse;
      a.setStyle(n + p);
      k = new t(l)
    },
    remove: function(b)
    {
      a.questNativeResponse = null;
      a.androidKeyStop = !1;
      a.oldModel = null;
      k && k.remove();
      b()
    }
  }
});
