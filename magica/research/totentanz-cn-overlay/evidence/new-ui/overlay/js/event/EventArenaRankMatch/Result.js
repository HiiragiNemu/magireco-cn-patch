define("underscore backbone backboneCommon ajaxControl command text!css/event/EventArenaRankMatch/Result.css text!template/event/EventArenaRankMatch/Result.html js/event/EventArenaRankMatch/Utility js/follow/FollowPopup js/view/item/ItemImgPartsView".split(" "), function(e, n, a, h, b, p, q, r, v, t)
{
  var f, g, m, u = n.View.extend(
  {
    events: function()
    {
      var d = {};
      d[a.cgti + " .replayBtn"] = this.replayBtn;
      d[a.cgti + " #touchScreen"] = this.toggles;
      d["webkitAnimationEnd .touch_screenTextWrap"] = this.touchScreen;
      return d
    },
    initialize: function(d)
    {
      this.model = d;
      g = h.getPageJson();
      this.model.userQuestBattleResultList && this.model.userQuestBattleResultList[0] && "TIME_UP" == this.model.userQuestBattleResultList[0].questBattleStatus ? (b.setWebView(), a.androidKeyStop = !0, new a.PopupClass(
      {
        title: "错误",
        content: "战斗耗时超过规定时间，<br>本次战斗无效。<br>返回活动首页。",
        closeBtnText: "OK"
      }, null, null, function()
      {
        b.endArena();
        location.href = "#/RegularEventArenaRankMatchTop"
      })) : this.model.userArenaBattleResultList && this.model.userArenaBattleResultList[0] ? this.checkDispResult() ? (this.tapFlag = !1, a.responseSetStorage(this.model), this.allInitialized(), this.template = e.template(q), this.createDom()) : (b.setWebView(), a.responseSetStorage(this.model), a.androidKeyStop = !0, new a.PopupClass(
      {
        title: "镜界排位赛",
        content: "当前不在排位赛开放期间，<br>对战结果不会被记录。<br>返回首页。",
        closeBtnText: "OK"
      }, null, null, function()
      {
        b.endArena();
        location.href = "#/TopPage"
      })) : (b.setWebView(), a.androidKeyStop = !0, new a.PopupClass(
      {
        title: "错误",
        content: "未能正确获取战斗结果。<br>返回首页。",
        closeBtnText: "OK"
      }, null, null, function()
      {
        b.endArena();
        location.href = "#/TopPage"
      }))
    },
    allInitialized: function()
    {
      var d = this,
        c = r.getDeckType(),
        b = a.currentArenaRankMatchDeckType;
      b || (b = c.attackBase + 1);
      this.model.arenaDecks = {};
      this.model.arenaDecks.noneLeader = [];
      for (var c = e.findWhere(a.storage.userDeckList.toJSON(),
        {
          deckType: b
        }), b = e.findWhere(a.storage.userCardList.toJSON(),
        {
          id: c.questEpisodeUserCardId
        }), k = 1; 6 > k; k++)
        if (c["userCardId" + k])
          if (c.questEpisodeUserCardId !== c["userCardId" + k])
          {
            var l = e.findWhere(a.storage.userCardList.toJSON(),
              {
                id: c["userCardId" + k]
              }),
              h = e.findWhere(a.storage.userCharaList.toJSON(),
              {
                charaId: l.card.charaNo
              });
            l.chara = h.chara;
            this.model.arenaDecks.noneLeader.push(l)
          }
      else this.model.arenaDecks.leaderCard = b, l = e.findWhere(a.storage.userCharaList.toJSON(),
      {
        charaId: b.card.charaNo
      }), this.model.arenaDecks.leaderCard.chara = l.chara;
      c = 999999;
      this.model.rankMatchRanking && (c = this.model.rankMatchRanking.ranking);
      this.model.rankMatchOrderRank = {
        rank: c
      };
      this.model.rankMatchOrderRank.isOrderRankUp = !1;
      a.EventArenaRankMatchPrm && a.EventArenaRankMatchPrm.orderRank && a.EventArenaRankMatchPrm.orderRank > c && (this.model.rankMatchOrderRank.isOrderRankUp = !0);
      var f = [];
      e.each(String(c), function(a, c, b)
      {
        f.push(String(a))
      });
      this.model.rankMatchOrderRank.textList = f;
      this.model.rankMatchBonusRewardList = [];
      var c = this.model.userArenaBattle.maxRankRewardsList,
        g = 0;
      c && c.length && (e.each(c, function(a, c, b)
      {
        e.each(a.presentList, function(a, c, b)
        {
          c = (new t(
          {
            model: a,
            type: a.presentType
          })).render().model;
          d.model.rankMatchBonusRewardList.push(
          {
            imagePath: c.imagePath,
            displayName: c.displayName,
            quantity: a.quantity
          })
        })
      }), e.each(this.model.rankMatchBonusRewardList, function(a, c, b)
      {
        g += a.quantity
      }), this.model.quantity = g);
      this.model.enemyData = a.EventArenaRankMatchPrm.opponentInfo;
      a.historyArr = ["MyPage", "ArenaTop", "RegularEventArenaRankMatchTop"];
      this.backLink = "#/RegularEventArenaRankMatchTop"
    },
    replayBtn: function(d)
    {
      if (!d.currentTarget.classList.contains("off") && (d.preventDefault(), !a.isScrolled()))
      {
        var c = this.model.userArenaBattleResultList[0].userQuestBattleResultId;
        new a.PopupClass(
        {
          title: "保存回放",
          content: "要将本次镜界对战<br>保存为回放吗？",
          closeBtnText: "不保存",
          decideBtnText: "保存",
          decideBtnEvent: function()
          {
            a.tapBlock(!0);
            a.androidKeyStop = !0;
            $("#commandDiv").on("nativeCallback", function(c, b)
            {
              $("#commandDiv").off();
              if ("error" === b.resultCode) new a.PopupClass(
              {
                title: b.title ? b.title : "错误",
                content: b.errorTxt ? b.errorTxt : "回放数据保存失败。",
                closeBtnText: "OK"
              });
              else
              {
                c = h.getPageJson();
                var d = new Date(c.currentTime);
                d.setDate(d.getDate() + 30);
                c = d.getFullYear();
                b = 10 > d.getMonth() ? "0" + (d.getMonth() + 1) : d.getMonth() + 1;
                d = 10 > d.getDate() ? "0" + d.getDate() : d.getDate();
                new a.PopupClass(
                {
                  title: "保存回放",
                  content: "已保存为回放。<br><br>有效期：" + c + "/" + b + "/" + d + "为止",
                  closeBtnText: "OK"
                });
                a.addClassId("replayBtn", "off");
                a.tapBlock(!1);
                a.androidKeyStop = !1
              }
            });
            b.saveQuestRelpay(
            {
              userQuestBattleResultId: c
            });
            window.isBrowser && $("#commandDiv").trigger("nativeCallback",
            {
              resultCode: ""
            })
          }
        })
      }
    },
    checkDispResult: function()
    {
      var b = !1,
        c = e.findWhere(g.regularEventList,
        {
          regularEventId: a.EventArenaRankMatchPrm.eventInfo.regularEventId
        });
      c && a.getStatusTargetTermInCurrentTime(
      {
        startAt: c.startAt,
        endAt: c.endAt,
        currentTime: g.currentTime
      }) && (b = !0);
      return b
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
      a.content.append(this.render().el);
      b.getBaseData(a.getNativeObj());
      a.ready.hide();
      a.globalMenuView && a.globalMenuView.trigger("removeView");
      "WIN" === this.model.userArenaBattleResultList[0].arenaBattleStatus ? this.model.rankMatchOrderRank.isOrderRankUp ? (a.addClass(a.doc.getElementsByClassName("touch_screenTextWrap")[0], "win"), a.addClass(a.doc.getElementsByClassName("touch_screen")[0], "win")) : (a.addClass(a.doc.getElementsByClassName("touch_screenTextWrap")[0], "win_noneReward"), a.addClass(a.doc.getElementsByClassName("touch_screen")[0], "win_noneReward")) : (a.addClass(a.doc.getElementsByClassName("touch_screenTextWrap")[0], "lose"), a.addClass(a.doc.getElementsByClassName("touch_screen")[0], "lose"));
      b.setWebView()
    },
    toggles: function(d)
    {
      d.preventDefault();
      a.isScrolled() || (b.endArena(), location.href = "#/RegularEventArenaRankMatchTop")
    },
    touchScreen: function()
    {
      a.addClass(a.doc.getElementById("touchScreen"), "on")
    },
    rankUps: function()
    {
      b.startSe(1703)
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
      id: "pieceList"
    },
    {
      id: "userPieceList"
    },
    {
      id: "userPieceSetList"
    },
    {
      id: "itemList"
    },
    {
      id: "userItemList"
    },
    {
      id: "userFollowList"
    },
    {
      id: "userSectionList"
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
      id: "userArenaBattle"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function()
    {
      a.battleEnemy = null;
      h.pageModelGet(this.needModelIdObj, null, null)
    },
    init: function()
    {
      a.ready.hide();
      b.startBgm("bgm03_story15");
      a.androidKeyStop = !0;
      m = a.questNativeResponse;
      a.setStyle(p);
      f = new u(m)
    },
    remove: function(b)
    {
      a.questNativeResponse = null;
      a.androidKeyStop = !1;
      a.oldModel = null;
      f && f.remove();
      b()
    }
  }
});
