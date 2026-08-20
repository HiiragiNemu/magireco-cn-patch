define("underscore backbone backboneCommon ajaxControl command text!template/event/arenaMission/EventArenaMissionTop.html text!css/event/arenaMission/EventArenaMissionTop.css text!css/event/arenaMission/EventArenaMissionCommon.css".split(" "), function(h, l, b, t, e, A, B, C)
{
  var u = l.Model.extend(),
    v, p = null,
    m, f, q, n, D = l.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " #helpBtn"] = this.announceOpen;
        a[b.cgti + " .missionBtn"] = this.missionToggle;
        a[b.cgti + " #clearRewardBtn"] = this.clearRewardPop;
        return a
      },
      initialize: function(a)
      {
        this.template = h.template(A);
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template(f));
        return this
      },
      createDom: function()
      {
        b.setGlobalView();
        b.content.append(this.render().el);
        this.createView();
        b.ready.hide()
      },
      createView: function()
      {
        var a = !0,
          d = null,
          c = b.doc.createDocumentFragment(),
          g = null;
        w.prototype.template = h.template($("#StageTemplate").text());
        y.prototype.template = h.template($("#ClearConditionTemplate").text());
        h.each(n, function(b, c)
        {
          b.canPlay && !d && (d = c);
          b.canPlay && !b.rewardDone && (a = !1)
        }, this);
        h.each(n, function(k, e)
        {
          var f = k.eventArenaMissionStage.stageClearRewardCode;
          k.stageClearRewardData = b.itemSet(f);
          k.rewardType = -1 < f.indexOf("GIFT_") ? "gift" : -1 < f.indexOf("LIVE2D_") ? "live2d" : -1 < f.indexOf("DOPPEL_") ? "doppel" : -1 < f.indexOf("GEM_") ? "gem" : -1 < f.indexOf("PIECE_") ? "memoria" : "main";
          k.canPlay ? (g || (g = k), k = new w(
          {
            model: new u(k)
          }), c.appendChild(k.render().el)) : a && d - 1 == e && k.eventArenaMissionStage.openDate && (k = new w(
          {
            model: new u(k)
          }), c.appendChild(k.render().el))
        }, this);
        b.doc.querySelector("#stageListWrap .scrollInner").appendChild(c);
        b.scrollSet("stageListWrap", "scrollInner");
        c = b.doc.createDocumentFragment();
        if (!a && g)
        {
          var e = new y(
          {
            model: new u(g)
          });
          c.appendChild(e.render().el)
        }
        b.doc.querySelector("#stageListWrap .scrollInner").appendChild(c)
      },
      announceOpen: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          b.tapBlock(!0);
          var d = this,
            c = 6E4 * ((new Date).getTime() / 6E4 | 0);
          require(["js/view/system/AnnounceView", "text!template/user/AnnouncePopupTemp.html", "text!json/event_banner/event_banner.json?bust=" + c, "text!json/announcements/announcements.json?bust=" + c], function(c, e, k, f)
          {
            new b.PopupClass(
            {
              title: "公告",
              exClass: "announcementPopup",
              announce: !0
            }, e, function()
            {
              setTimeout(function()
              {
                b.tapBlock(!1)
              }, 500)
            }, function()
            {
              d.announceView && d.announceView.trigger("removeView")
            });
            d.announceView = new c(
            {
              bannerJson: k,
              announcementJson: f,
              targetEvent: Number(a.currentTarget.dataset.eventid)
            })
          })
        }
      },
      missionToggle: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = b.doc.querySelector("#stageListWrap");
          var d = b.doc.querySelector("#stageListWrap").className; - 1 !== d.indexOf("first") ? a.className = "second" : -1 !== d.indexOf("second") && (a.className = "first")
        }
      },
      clearRewardPop: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a = f.userEventArenaMissionStageList, a.sort(function(b, a)
        {
          return b.stageId < a.stageId ? -1 : b.stageId > a.stageId ? 1 : 0
        }), h.each(a, function(a, c)
        {
          a.openDateText = a.eventArenaMissionStage.openDate ? b.getTimeText(a.eventArenaMissionStage.openDate, !0) : "-";
          c = a.eventArenaMissionStage.stageClearRewardCode;
          a.stageClearRewardData = b.itemSet(c);
          a.rewardType = -1 < c.indexOf("GIFT_") ? "gift" : -1 < c.indexOf("LIVE2D_") ? "live2d" : -1 < c.indexOf("DOPPEL_") ? "doppel" : -1 < c.indexOf("GEM_") ? "gem" : -1 < c.indexOf("PIECE_") ? "memoria" : "main"
        }), new b.PopupClass(
        {
          popupType: "typeB",
          eventArenaMissionStageList: a,
          eventModel: f.eventModel
        }, $("#ClearRewardPopTemp").text(), function()
        {
          b.scrollSet("stageClearRewardList", "scrollInner");
          e.getBaseData(b.getNativeObj())
        }))
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    w = l.View.extend(
    {
      className: function()
      {
        var a = "stage se_decide";
        this.model.toJSON().canPlay || (a += " off");
        return a
      },
      events: function()
      {
        var a = {};
        a[b.cgti] = this.stageSelect;
        return a
      },
      initialize: function(a) {},
      render: function()
      {
        var a = this.model.toJSON();
        this.model.set(
        {
          clearRewardItem: b.itemSet(a.eventArenaMissionStage.stageClearRewardCode)
        });
        this.$el.html(this.template(
        {
          model: this.model.toJSON()
        }));
        return this
      },
      stageSelect: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var d = this.model.toJSON();
          d.canPlay && (b.eventArenaMissionStage = d, b.userEventArenaMission = f.userEventArenaMission, z(d.eventArenaMissionStage.startStory, function(a)
          {
            a ? (b.responseSetStorage(a), e.endL2d(), $("#commandDiv").on("nativeCallback", function(a, b)
            {
              $("#commandDiv").off();
              location.href = "#/EventArenaMissionStage/" + d.stageId;
              e.setWebView(!0)
            }), setTimeout(function()
            {
              e.setWebView(!1);
              e.startStory(d.eventArenaMissionStage.startStory);
              window.isBrowser && ($("#commandDiv").off(), location.href = "#/EventArenaMissionStage/" + d.stageId, e.setWebView(!0))
            }, 500)) : location.href = "#/EventArenaMissionStage/" + d.stageId
          }))
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    y = l.View.extend(
    {
      initialize: function(a)
      {
        this.listenTo(this.model, "change", this.render)
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model.toJSON()
        }));
        return this
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    x = function()
    {
      b.eventArenaMissionStage = null;
      b.userEventArenaMission = null;
      var a = b.storage.userItemList.findWhere(
        {
          itemId: "EVENT_ARENAMISSION_" + m.eventId + "_EXCHANGE"
        }),
        a = a ? a.toJSON().quantity : 0;
      f.exchangeItemNum = a;
      p = m.viewParameterMap.LIVE2D_ID;
      a = m.viewParameterMap.BGM;
      e.changeBg(m.viewParameterMap.BG_IMG + ".ExportJson");
      e.startBgm(a);
      m ? (f.eventModel = m, b.setStyle(B + C), q = new D, v && r(), e.getBaseData(b.getNativeObj())) : e.nativeReload("#/MyPage")
    },
    z = function(a, d)
    {
      var c = !1,
        c = !0;
      h.each(f.userQuestAdventureList, function(b)
      {
        a === b.adventureId && (c = !1)
      });
      c ? ($(b.ready.target).off(), $(b.ready.target).on("webkitAnimationEnd", function()
      {
        e.changeBg("web_black.jpg");
        $(b.ready.target).off();
        $(b.ready.target).on("webkitAnimationEnd", function(a)
        {
          "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
        });
        t.ajaxPost(b.linkList.userQuestAdventureRegist,
        {
          adventureId: String(a)
        }, d)
      }), b.ready.target.classList.contains("preNativeFadeIn") ? $(b.ready.target).trigger("webkitAnimationEnd") : b.addClass(b.ready.target, "preNativeFadeIn")) : d()
    },
    r = function()
    {
      e.endL2d();
      var a = {};
      a.id = p;
      a.x = 350;
      a.y = 1024 === b.displayWidth ? Math.floor(b.doc.getElementsByTagName("body")[0].offsetHeight / 2) : Math.ceil(b.shortSize / 2);
      a.type = 0;
      var d = p.substring(0, p.length - 2),
        c = [],
        g = Number(f.currentTime.split(" ")[1].split(":")[0]),
        h = Number(f.currentTime.split(" ")[1].split(":")[1]);
      6 <= g && 9 >= g && !(9 == g && 0 < h) ? c.push(24) : 11 <= g && 13 >= g && !(13 == g && 0 < h) ? c.push(25) : 17 <= g && 19 >= g && !(19 == g && 0 < h) ? c.push(26) : 22 <= g || 0 == g && !(0 == g && 0 < h) ? c.push(27) : c.push(23);
      b.storage.userStatusList.findWhere(
      {
        statusId: "ACP"
      }).toJSON().point >= b.storage.userStatusList.findWhere(
      {
        statusId: "MAX_ACP"
      }).toJSON().point && c.push(29);
      b.storage.userStatusList.findWhere(
      {
        statusId: "BTP"
      }).toJSON().point >= b.storage.userStatusList.findWhere(
      {
        statusId: "MAX_BTP"
      }).toJSON().point && c.push(30);
      a.key = "vo_char_" + d + "_00_" + (c[Math.floor(Math.random() * c.length)] + 1);
      e.startL2d(a)
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
      id: "userQuestAdventureList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function()
    {
      t.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      f = t.getPageJson();
      m = h.findWhere(f.eventList,
      {
        eventType: "ARENAMISSION"
      });
      v = !0;
      n = [];
      n = f.userEventArenaMissionStageList;
      n.sort(function(a, b)
      {
        return a.stageId > b.stageId ? -1 : a.stageId < b.stageId ? 1 : 0
      });
      var a = null,
        d = null;
      h.each(n, function(a, b)
      {
        a.canPlay && a.rewardDone && (d || (d = a))
      }, this);
      d && d.eventArenaMissionStage.endStory && (a = d.eventArenaMissionStage.endStory);
      var c = a ? a : m.startStoryId,
        g = a ? !1 : !0,
        l = m.viewParameterMap.EVENT_DOPING_ITEM_NAME;
      z(c, function(a)
      {
        a ? (v = !1, b.responseSetStorage(a), e.endL2d(), $("#commandDiv").on("nativeCallback", function(a, c)
        {
          $("#commandDiv").off();
          g ? b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], 1006, "arenaMission", function()
          {
            new b.PopupClass(
            {
              popupType: "typeC",
              title: l + "到手！",
              content: l + "已各发送一个。<br>使用道具，让战斗进行得更加顺利吧！",
              closeBtnText: "关闭"
            }, null, null, function()
            {
              r()
            })
          }) : r();
          x();
          e.setWebView(!0)
        }), setTimeout(function()
        {
          e.setWebView(!1);
          e.startStory(c);
          window.isBrowser && (g && b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], 1006, "arenaMission", function()
          {
            new b.PopupClass(
            {
              popupType: "typeC",
              title: l + "到手！",
              content: l + "已各发送一个。<br>使用道具，让战斗进行得更加顺利吧！",
              closeBtnText: "关闭"
            }, null, null, function()
            {
              r()
            })
          }), x())
        }, 500)) : x()
      })
    },
    removeCommand: function()
    {
      e.endL2d()
    },
    remove: function(a)
    {
      q && (q.trigger("remove"), q.remove());
      a()
    }
  }
});
