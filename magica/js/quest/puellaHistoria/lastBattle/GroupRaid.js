define("underscore backbone backboneCommon ajaxControl command QuestUtil text!template/quest/puellaHistoria/lastBattle/GroupRaid.html text!css/quest/PuellaHistoriaLastBattle/GroupRaid.css js/quest/puellaHistoria/lastBattle/Model js/quest/puellaHistoria/lastBattle/Utility js/quest/puellaHistoria/lastBattle/parts/GroupRaid/NativeMain js/quest/puellaHistoria/lastBattle/parts/GroupRaid/Stamp".split(" "), function(g, n, b, h, k, z, p, q, l, f, r, t)
{
  var c = {},
    m = !1,
    v = n.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " #toMissionBtn"] = this.tapToMissionBtn;
        a[b.cgti + " #toSingleRaidBtn"] = this.tapToSingleRaidBtn;
        a[b.cgti + " #groupRaidHelp"] = this.tapGroupRaidHelp;
        return a
      },
      initialize: function()
      {
        this.template = g.template(p);
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
        b.content.append(this.render().el);
        c.NativeMain = new r(
        {
          model: this.model.pageModel,
          getIsStampDisp: this.getIsStampDisp,
          _views: c
        });
        $("#mainSec").append(c.NativeMain.render().el);
        c.Stamp = new t(
        {
          model: this.model.pageModel,
          getIsStampDisp: this.getIsStampDisp,
          setIsStampDisp: this.setIsStampDisp,
          _views: c
        });
        $("#stampSec").append(c.Stamp.render().el);
        u(
        {
          model: this.model.pageModel
        });
        b.ready.hide()
      },
      getIsStampDisp: function()
      {
        return m
      },
      setIsStampDisp: function(a)
      {
        m = a
      },
      tapToMissionBtn: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a = "#/MissionTop", this.model.pageModel.eventId && (a = a + "/" + this.model.pageModel.eventId), location.href = a)
      },
      tapToSingleRaidBtn: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (location.href = "#/PuellaHistoriaSingleRaid")
      },
      tapGroupRaidHelp: function(a)
      {
        a.preventDefault();
        b.isScrolled() || f.openFirstNavi(
        {
          type: "groupRaid",
          isForceOpen: !0
        })
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    w = function(a)
    {
      var d = a.pageModel;
      b.PuellaHistoriaLastBattleGroupRaidPrm = {
        battleType: !1,
        isUseItem: !1,
        sectionInfo: d.questInfo.sectionInfoList[0],
        userQuestAdventureList: a.pageJson.userQuestAdventureList,
        beforeDP: d.DP,
        bossUseItemQuantity: 0
      };
      f.setQuestBeforeDP(
      {
        groupRaidPrm: b.PuellaHistoriaLastBattleGroupRaidPrm
      })
    },
    u = function(a)
    {
      a = String(a.model.DP).split("");
      a.reverse();
      var b = 0;
      g.each(a, function(a, e, c)
      {
        a = '<span class="numImg num' + a + '"></span>';
        b++;
        3 == b && e + 1 < c.length && (a = '<span class="numImg numcomma"></span>' + a, b = 0);
        $("#DPNum").prepend(a)
      })
    },
    y = function()
    {
      var a = h.getPageJson();
      if (f.isClearSingleRaid(
        {
          singleRaidQuestList: f.getSingleRaidQuestInfo(
          {
            pageJson: a
          })
        }))
      {
        var d = function()
          {
            b.setStyle(q);
            k.startBgm("bgm01_battle02");
            k.changeBg("web_PuellaHistoria_19094_01.ExportJson");
            m = !1;
            var e = l.getGroupRaidModel(
            {
              pageJson: a
            });
            w(
            {
              pageModel: e,
              pageJson: a
            });
            var d = "";
            1024 !== b.displayWidth && (d = "iPhoneX");
            b.ua.ipad && (d = "iPad");
            var h = function()
            {
              c.pageView = new v(
              {
                model:
                {
                  pageModel: e,
                  terminalClass: d
                }
              });
              b.setGlobalView();
              setTimeout(function()
              {
                f.openFirstNavi(
                {
                  type: "groupRaid"
                })
              }, 3500)
            };
            l.getStampList(
            {
              callback: function(a)
              {
                g.each(a.res.stampList, function(a, b, d)
                {
                  e.nativeModel.stampList.push(
                  {
                    userName: a.userName,
                    comment: a.comment,
                    filename: "event_dailytower_" + a.stampId + "_s.png"
                  })
                });
                l.getAttackInfoList(
                {
                  mode: "INIT",
                  callback: function(a)
                  {
                    var b = 0;
                    g.each(a.res.damageList, function(a, d, c)
                    {
                      e.nativeModel.damageList.push(
                      {
                        userName: a.userName,
                        damage: a.damage
                      });
                      b += a.damage
                    });
                    e.nativeModel.hp < b && (e.nativeModel.hp = b);
                    h()
                  }
                })
              }
            })
          },
          x = f.getStoryIdList();
        b.playStory(
        {
          cmd: k,
          ajaxControl: h,
          storyId: x.event[8].storyId,
          callback: function()
          {
            d();
            setTimeout(function()
            {
              b.removeClass(b.ready.target, "fadeout")
            }, 500)
          }
        })
      }
      else b.setGlobalView(), b.ready.hide(), new b.PopupClass(
      {
        title: "错误",
        content: "未满足<br>关卡开始条件",
        popupType: "typeC",
        closeBtnText: "返回首页"
      }, null, null, function()
      {
        b.historyArr = ["MyPage"];
        location.href = "#/PuellaHistoriaTop"
      })
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
      id: "userChapterList"
    },
    {
      id: "userSectionList"
    },
    {
      id: "userQuestBattleList"
    },
    {
      id: "userDeckList"
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
      id: "userCharaList"
    },
    {
      id: "userQuestAdventureList"
    },
    {
      id: "userFollowList"
    },
    {
      id: "userPatrolList"
    },
    {
      id: "userEventPuellaRaid"
    }],
    fetch: function()
    {
      h.pageModelGet(this.needModelIdObj, null)
    },
    init: function()
    {
      k.endQuest();
      b.PuellaHistoriaLastBattleSingleRaidPrm = null;
      b.PuellaHistoriaLastBattleGroupRaidPrm = null;
      y()
    },
    remove: function(a)
    {
      g.each(c, function(a, b, c)
      {
        a.removeView && a.removeView()
      });
      a()
    }
  }
});
