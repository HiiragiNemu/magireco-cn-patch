define("underscore backbone backboneCommon js/event/EventArenaRankMatch/Utility DeckUtil cardUtil".split(" "), function(d, p, e, f, m, q)
{
  return {
    getTopModel: function(c)
    {
      var a = {},
        b = c.pageJson;
      c = e.getDateShortening(
      {
        date: new Date
      });
      a.pageAccessLocalTime = c.yr + "/" + c.mo + "/" + c.da + " " + c.ho + ":" + c.mi + ":" + c.se;
      a.eventInfo = b.regularEventArenaRankMatch;
      a.userInfo = {
        name: d.escape(b.user.loginName),
        rank: b.gameUser.level,
        orderRank: b.regularEventArenaRankMatch.npcNum + 1,
        highestOrderRank: b.userArenaBattle.rankMatchMaxRank,
        classRank: "",
        isEnableDefenseDeck: b.enableDefenseDeck
      };
      d.each([b.userArenaRankMatchRanking], function(b, c, d)
      {
        b && (a.userInfo.orderRank = Number(b.ranking))
      });
      a.userInfo.classRank = f.getEmblemRank(
      {
        orderRank: a.userInfo.orderRank,
        emblemList: b.emblemList
      });
      a.battleInfo = {
        arenaBattleType: b.arenaBattleType,
        matchExpiredAt: !1,
        matchId: !1
      };
      b.userArenaRankMatch && (a.battleInfo.matchExpiredAt = b.userArenaRankMatch.expiredAt, a.battleInfo.matchId = b.userArenaRankMatch.matchId);
      a.userInfo.displayCardId = e.storage.userCardListEx.findWhere(
      {
        id: b.gameUser.leaderId
      }).toJSON().displayCardId;
      a.userInfo.displayCardId || (a.userInfo.displayCardId = 10011);
      a.presentInfo = f.createRewardModel(
      {
        rewardList: b.rewardList,
        emblemList: b.emblemList
      });
      if (b.dailyRewards && b.dailyRewards.length)
      {
        var k = [];
        d.each(b.dailyRewards, function(a, b, c)
        {
          a = a.presentList[0];
          a = {
            img: f.getItemInfo(
            {
              model: a,
              type: a.presentType
            }).imagePath,
            name: a.displayName,
            num: a.quantity
          };
          k.push(a)
        });
        a.presentInfo.daily.todayInfo = {
          userRank: a.userInfo.highestOrderRank,
          itemList: k
        }
      }
      a.specialRuleInfo = {
        list: ["没有特殊规则"],
        deckMinNumList:
        {
          arenaRankMatchAttack: 1,
          arenaRankMatchDefence: 1
        },
        deckMaxNumList:
        {
          arenaRankMatchAttack: 5,
          arenaRankMatchDefence: 5
        }
      };
      c = a.eventInfo.specialRuleMap;
      var g = {};
      c && (a.specialRuleInfo.deckMinNumList.arenaRankMatchAttack = c.MUST_KEEP_ATTACK_DECK, a.specialRuleInfo.deckMinNumList.arenaRankMatchDefence = c.MUST_KEEP_DEFENSE_DECK, g = f.getSpRulesList(
      {
        spRulesMap: c
      }), a.specialRuleInfo.plusList = g, a.specialRuleInfo.list = f.getSpRulesText(
      {
        spRulesMap: c,
        plusList: g
      }));
      e.EventArenaRankMatchPrm = {
        spPlusList: a.specialRuleInfo.plusList
      };
      c = f.getDeckType();
      g = c.attackBase + 1;
      e.currentArenaRankMatchDeckType && (g = e.currentArenaRankMatchDeckType);
      a.userDeckInfo = {
        attack: d.findWhere(b.userDeckList,
        {
          deckType: g
        }),
        defence: d.findWhere(b.userDeckList,
        {
          deckType: c.defence
        })
      };
      c = new m("arenaRankMatchAttack");
      a.userInfo.teamStatus = "---";
      a.userDeckInfo.attack && (c = c.deckDataCreate(a.userDeckInfo.attack), a.userInfo.teamStatus = c.teamStatus);
      a.attackCountInfo = {
        num: b.battlePossibleCount,
        numMax: 5,
        recoverNeedNum: a.eventInfo.recoveryBattleCost,
        itemNum: 0,
        itemName: "",
        reloadBtnClass: ""
      };
      0 == a.attackCountInfo.num && (a.attackCountInfo.reloadBtnClass = "off");
      var l = function()
      {
        var a = !1;
        d.each(b.regularEventList, function(b, c, d)
        {
          "ARENARANKMATCH" == b.regularEventType && (a = b.regularEventId)
        });
        return a
      }();
      l && (c = e.storage.userItemList.toJSON(), d.each(c, function(b, c, d)
      {
        b.itemId == "RANK_MATCH_BATTLE_RECOVERY_" + l && (a.attackCountInfo.itemNum = b.quantity, a.attackCountInfo.itemName = b.item.name)
      }));
      a.coolDownTimeInfo = {
        nextTime: b.battleCoolTime,
        recoverNeedNum: a.eventInfo.recoverCoolTimeCost
      };
      a.opponentList = {
        higher: [],
        midst: [],
        lower: []
      };
      var h = b.userArenaRankMatch,
        n = ["higherOpponentUserArenaBattleInfo", "midstOpponentUserArenaBattleInfo", "lowerOpponentUserArenaBattleInfo"];
      d.each(a.opponentList, function(a, b, c)
      {
        d.each([1, 2, 3, 4, 5], function(c, e, f)
        {
          d.each(n, function(d, e, f)
          {
            h && h[d + c] && (e = h[d + c], e.battleType = h.arenaBattleType, -1 != d.indexOf(b) && a.push(e))
          })
        })
      });
      return a
    }
  }
});
