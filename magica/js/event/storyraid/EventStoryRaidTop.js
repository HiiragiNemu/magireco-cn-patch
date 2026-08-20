define("underscore backbone backboneCommon ajaxControl command text!template/event/storyraid/EventStoryRaidTop.html text!template/event/storyraid/EventStoryRaidSelect.html text!template/event/storyraid/EventStoryRaidBoss.html text!css/event/storyraid/EventStoryRaidTop.css js/event/storyraid/view/FinalAnimationsView text!css/event/storyraid/FinalAnimation.css js/view/quest/ClearAnimationsView js/view/quest/QuestListPartsView text!css/quest/QuestCommon.css QuestUtil".split(" "), function(g, z, b, y, f, aa, ba, ca, da, Q, ea, fa, E, ga, C)
{
  var v = !1,
    D = !1,
    R = 0,
    S = 0,
    F = 0,
    T = null,
    ha = function()
    {
      if (window.isBrowser && window.isDebug)
      {
        var a = b.doc.createDocumentFragment();
        g.each(k.userEventStoryRaidPointList, function(c)
        {
          var d = !0,
            e = G(c.pointId);
          c = e.pointModel;
          e.clearedAt && (d = !1);
          e = document.createElement("div");
          H(c) ? e.className = "debugMapBtn sb_gold_01 TE" : e.className = "debugMapBtn sb_pink TE";
          d || b.addClass(e, "off");
          e.dataset.id = c.pointId;
          e.textContent = c.point.title;
          a.appendChild(e)
        });
        b.doc.getElementById("mapWrap").appendChild(a);
        $(".debugMapBtn").off();
        $(".debugMapBtn").on(b.cgti, function(a)
        {
          a.preventDefault();
          b.isScrolled() || a.currentTarget.classList.contains("off") || ($(".debugMapBtn").off(), p.mapHide(G(a.currentTarget.dataset.id)))
        })
      }
    };
  z.Model.extend();
  var k, h, l, n, w, q, ia = {
      raidType: "HUGE",
      mapWidth: 1,
      mapHeight: 1,
      centerPointId: 103,
      pointList: [
      {
        pointId: 101,
        iconType: "NORMAL",
        status: "NEW",
        x: 1200,
        y: 1200,
        questClearList: ["NO_CLEAR"],
        connectPointId: 102
      },
      {
        pointId: 102,
        iconType: "NORMAL",
        status: "已通关",
        x: 1500,
        y: 1100,
        questClearList: ["COMPLETE"],
        connectPointId: 103
      },
      {
        pointId: 103,
        iconType: "BOSS",
        status: "IN_BATTLE",
        x: 1200,
        y: 1E3,
        miniCharIdList: [10],
        connectPointId: 104,
        dayId: 2,
        raidHpRate: 70,
        miniCharScale: 60
      },
      {
        pointId: 104,
        iconType: "BOSS",
        status: "FINAL_BATTLE",
        x: 900,
        y: 900,
        miniCharIdList: [10],
        connectPointId: 105,
        dayId: 3,
        raidHpRate: 3,
        miniCharScale: 60
      },
      {
        pointId: 105,
        iconType: "BOSS",
        status: "已通关",
        x: 1200,
        y: 800,
        questClearList: ["COMPLETE"],
        connectPointId: 106,
        dayId: 1
      },
      {
        pointId: 106,
        iconType: "LAST",
        status: "IN_BATTLE",
        x: 1500,
        y: 700,
        miniCharIdList: [10],
        dayId: 4,
        raidHpRate: 30,
        miniCharScale: 60,
        connectPointId: 107
      },
      {
        pointId: 107,
        iconType: "LAST",
        status: "FINAL_BATTLE",
        x: 1200,
        y: 600,
        dayId: 4,
        miniCharIdList: [10],
        raidHpRate: 3,
        miniCharScale: 60,
        connectPointId: 108
      },
      {
        pointId: 108,
        iconType: "LAST",
        status: "已通关",
        x: 900,
        y: 500,
        dayId: 4,
        questClearList: ["COMPLETE"]
      }]
    },
    U = {
      attribute: "DARK",
      hpStart: 25E5,
      hp: 2499940,
      fieldFilename: "web_ev_1053_24012",
      miniCharaId: 10,
      x: 0,
      y: 0,
      name: "玩家名78",
      cardId: 10011,
      playerComment: "１２３４５６７８９０１２３４５６７８９０１２３４５６７８９０１２３４５６７８９０１２３４５６７８９０",
      userBalloonList: [
      {
        userName: "1用户名78",
        cardId: 10011,
        comment: "测试文字６７８９０＠测试文字６７８９０",
        attack: 100
      },
      {
        userName: "2用户名78",
        cardId: 21023,
        comment: "２评论６７８９０１２３４５６７８９０",
        attack: 100
      },
      {
        userName: "3用户名78",
        cardId: 10013,
        comment: "３评论６７８９０１２３４５６７８９０",
        attack: 100
      },
      {
        userName: "4用户名78",
        comment: "４评论６７８９０１２３４５６７８９０",
        attack: 100
      },
      {
        userName: "5用户名78",
        comment: "５评论６７８９０１２３４５６７８９０",
        attack: 100
      }]
    },
    p, r, x, t, B = z.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " #helpBtn"] = I;
        a[b.cgti + " #logBtn"] = this.logPopup;
        a[b.cgti + " #epilogueBtn"] = this.startEpilogue;
        a[b.cgti + " #epilogueMovieBtn"] = this.startEpilogueMovie;
        a[b.cgti + " .debugBtn"] = this.debugBtn;
        if (window.isBrowser && window.isDebug) return a;
        a["touchstart #mapWrap"] = this.touchStart;
        a["touchmove #mapWrap"] = this.touchMove;
        a["touchend #mapWrap"] = this.touchEnd;
        return a
      },
      debugBtn: function(a)
      {
        a.preventDefault();
        if (l)
        {
          var c = {};
          $.extend(c, ia);
          var d = {};
          $.extend(d, U);
          var e = a.currentTarget.dataset.mode;
          if ("basic" == e) console.log("【DEBUG】原样输出收到的Json"), u(c, "top");
          else if ("newPoint" == e) console.log("【DEBUG】区域解放"), c.newPointIdList = [Number(a.currentTarget.dataset.pointid)], u(c, "top");
          else if ("destroyed" == e) console.log("【DEBUG】击破演出"), c.needRaidDestroyedCutin = !0, u(c, "top");
          else if ("mapEffect" == e) console.log("【DEBUG】地图特效"), c.mapEffectList = [
          {
            name: "evt_raid_anime_map_00",
            priority: 1,
            x: 1024,
            y: 1024
          }], u(c, "top");
          else if ("boss" == e) a = a.currentTarget.dataset.status, console.log("【DEBUG】BOSS指令(" + a + "）"), d.state = a, u(d, "boss");
          else if ("hideSingleRaid" == e) f.hideEventSingleRaid();
          else if ("resumeSingleRaid" == e) f.resumeEventSingleRaid();
          else if ("popSingleRaid" == e) f.popEventSingleRaid();
          else if ("popStoryRaid" == e) f.popEventStoryRaid();
          else if ("eventCondPopup" == e) V();
          else if ("noDisplay" == e)
          {
            var m = b.doc.getElementById("debugArea");
            m.style.display = "none";
            setTimeout(function()
            {
              m.style.display = "block"
            }, 3E4)
          }
          else "finale" == e && (f.stopBgm(), t && (t.removeHandler(), t = null), t = Q, t.finish("finalAnimationWrap"))
        }
      },
      touchStart: function(a)
      {
        a.preventDefault();
        l && (b.tapEffectStop = !0, J(a, "START"))
      },
      touchMove: function(a)
      {
        a.preventDefault();
        l && J(a, "MOVE")
      },
      touchEnd: function(a)
      {
        a.preventDefault();
        l && (b.tapEffectStop = !1, J(a, "END"))
      },
      initialize: function(a)
      {
        this.clearedSectionModel = null;
        a && a.sectionModel && (this.clearedSectionModel = a.sectionModel);
        this.template = g.template(aa);
        this.createDom()
      },
      render: function()
      {
        var a = k;
        a.isFinal = v;
        a.isEpAlreadyRead = D;
        a.itemQuantity = F;
        this.$el.html(this.template(a));
        return this
      },
      createDom: function()
      {
        var a = this.render().el;
        l ? b.addClass(a.querySelector("#EventStoryRaidTop"), "pageFadein") : v && b.addClass(a.querySelector("#EventStoryRaidTop"), "finale");
        if (l) b.content.append(a),
          $("#commandDiv").off(), K(), $("#EventStoryRaidTop").off(), $("#EventStoryRaidTop").on("webkitAnimationEnd", function()
          {
            $("#EventStoryRaidTop").off();
            b.removeClass(b.doc.querySelector("#EventStoryRaidTop"), "pageFadein");
            b.tapBlock(!1);
            b.androidKeyStop = !1
          });
        else
        {
          var c = function()
          {
            t = Q;
            b.content.append(a);
            t.finish("finalAnimationWrap", function()
            {
              f.changeBg(h.viewParameterMap.BG_END_IMG + ".ExportJson");
              f.startBgm(h.viewParameterMap.END_BGM)
            }, function()
            {
              b.removeClass(b.doc.querySelector("#EventStoryRaidTop"), "finale")
            })
          };
          v && !this.clearedSectionModel ? c() : (this.clearedSectionModel ? ($("#commandDiv").on("nativeCallback", function(d, e)
          {
            $("#commandDiv").off();
            d = null;
            v ? d = function()
            {
              f.popEventSingleRaid();
              f.changeBg("web_black.jpg");
              f.stopBgm();
              c()
            } : (b.content.append(a), K());
            e = q.section;
            var m = C.clearRewardChestColor(e.clearReward);
            fa.section(e.clearRewardCode, e, m, d)
          }), window.isBrowser && nativeCallback()) : ($("#commandDiv").off(), K(), b.content.append(a)), setTimeout(function()
          {
            L()
          }, 300));
          b.ready.hide();
          l = !0
        }
        window.isDebug && !v && ha()
      },
      mapHide: function(a)
      {
        b.tapBlock(!0);
        b.androidKeyStop = !0;
        $("#commandDiv").off();
        $("#EventStoryRaidTop").off();
        $("#EventStoryRaidTop").on("webkitAnimationEnd", function()
        {
          $("#EventStoryRaidTop").off();
          var c = function()
          {
            p && (p.remove(), p = null);
            var b = {
              sectionModel: a
            };
            f.setWebView(!0);
            H(a.pointModel) ? W(b) : r = new X(b)
          };
          f.hideEventSingleRaid();
          window.isBrowser ? c() : (f.setWebView(!1), Y(function()
          {
            f.startBgm(h.viewParameterMap.BGM);
            a.pointModel.point.startStory ? M(a.pointModel.point.startStory, function(d)
            {
              d ? (b.responseSetStorage(d), $("#commandDiv").on("nativeCallback", function(a, d)
              {
                $("#commandDiv").off();
                b.ready.target.className = "nativeFadeOut";
                f.startBgm(h.viewParameterMap.BGM);
                c()
              }), f.startStory(a.pointModel.point.startStory), window.isBrowser && nativeCallback()) : c()
            }) : c()
          }))
        });
        b.addClass(b.doc.querySelector("#EventStoryRaidTop"), "pageFadeout");
        b.removeBackHandler();
        b.addBackHandler(A)
      },
      logPopup: function(a)
      {
        a.preventDefault();
        b.isScrolled() || new ja
      },
      startEpilogue: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (f.setWebView(!1), Y(function()
        {
          f.stopBgm();
          var a = h.viewParameterMap.EPILOGUE_STORY_ID;
          M(a, function(c)
          {
            b.responseSetStorage(c);
            $("#commandDiv").on("nativeCallback", function(a, c)
            {
              $("#commandDiv").off();
              f.setWebView(!0);
              b.tapBlock(!1);
              b.androidKeyStop = !1;
              location.href = "#/MyPage"
            });
            f.startStory(a,
            {
              canSkip: D,
              canAuto: !0,
              canOpenLog: !0
            });
            window.isBrowser && nativeCallback()
          }, !0)
        }))
      },
      startEpilogueMovie: function(a)
      {
        a.preventDefault();
        b.isScrolled() || ($(b.ready.target).on("webkitAnimationEnd", function()
        {
          f.changeBg("web_black.jpg");
          $(b.ready.target).off();
          $(b.ready.target).on("webkitAnimationEnd", function(a)
          {
            "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
          });
          $("#commandDiv").on("nativeCallback", function(a, d)
          {
            b.ready.target.className = "readyFadeOut";
            f.changeBg(h.viewParameterMap.BG_END_IMG + ".ExportJson");
            f.startBgm(h.viewParameterMap.END_BGM);
            f.setWebView(!0);
            $("#commandDiv").off()
          });
          setTimeout(function()
          {
            f.setWebView(!1);
            f.stopBgm();
            f.playMovie("resource/movie/other/102005_epilogue.usm");
            window.isBrowser && nativeCallback()
          }, 500)
        }), b.addClass(b.ready.target, "preNativeFadeIn"))
      }
    }),
    ja = z.View.extend(
    {
      initialize: function(a)
      {
        this.template = g.template($("#battleLogParts").text());
        this.createDom()
      },
      createDom: function()
      {
        var a = [];
        $.extend(a, n);
        a.sort(function(a, b)
        {
          return a.pointModel.pointId < b.pointModel.pointId ? 1 : a.pointModel.pointId > b.pointModel.pointId ? -1 : 0
        });
        var c = function()
        {
          this.removeView()
        }.bind(this);
        new b.PopupClass(
        {
          content: "",
          popupType: "typeC"
        }, this.template(
        {
          eventSectionList: a
        }), function()
        {
          b.scrollSet("battleLogListWrap", "scrollInner")
        }, c)
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    X = z.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " #helpBtn"] = I;
        a[b.cgti + " .missionBtn"] = this.missionToggle;
        return a
      },
      initialize: function(a)
      {
        this.newSectionModel = a.newSectionModel || null;
        this.oldSectionModel = a.sectionModel || null;
        this.model = a.sectionModel ? a.sectionModel : a.newSectionModel;
        this.model.eventObj = C.openEventCheck(h.eventId, k.eventList);
        this.template = g.template(ba);
        this.createDom()
      },
      render: function()
      {
        this.model.pointModel.point.displayCharaMessage = this.model.pointModel.point.displayCharaMessage.replace(/＠/g, "<br>").replace(/userName/g, b.storage.user.get("loginName"));
        this.$el.html(this.template(this.model));
        return this
      },
      modelSend: function(a)
      {
        return this.model
      },
      createDom: function()
      {
        var a = this,
          c = this.render().el;
        l && b.addClass(c.querySelector("#EventStoryRaidSelect"), "pageFadein");
        this.model.section.imagePath && f.changeBg("bg_adv_" + this.model.section.imagePath + ".jpg");
        b.content.append(c);
        var d = function(e)
        {
          E.prototype.parentView = a;
          E.prototype.template = g.template($("#questPartsTemp").text());
          var d = b.doc.createDocumentFragment();
          g.each(e.section.questBattleList, function(a)
          {
            a = new E(
            {
              model: a
            });
            d.appendChild(a.render().el)
          });
          c.querySelector("#questLinkList").appendChild(d);
          $("#questLinkList .quest .touchObj").bind(b.cgti, function(a)
          {
            a.preventDefault();
            b.isScrolled() || (T = e.pointModel.point.title, b.oldEventStoryRaidSectionList = n)
          })
        };
        setTimeout(function()
        {
          var a = {};
          a.key = String(this.model.sectionId);
          a.type = 1;
          a.id = "0";
          a.x = 230;
          a.y = 1024 === b.displayWidth ? Math.floor(b.doc.getElementsByTagName("body")[0].offsetHeight / 2) : Math.ceil(b.shortSize / 2);
          f.startL2d(a)
        }.bind(this), 500);
        l ? (d(this.model), $("#EventStoryRaidSelect").off(), $("#EventStoryRaidSelect").on("webkitAnimationEnd", function()
        {
          $("#EventStoryRaidSelect").off();
          b.removeBackHandler();
          b.addBackHandler(A);
          b.removeClass(b.doc.querySelector("#EventStoryRaidSelect"), "pageFadein");
          b.tapBlock(!1);
          b.androidKeyStop = !1
        })) : (d(this.newSectionModel), setTimeout(function()
        {
          L();
          b.removeBackHandler();
          b.addBackHandler(A.bind(null,
          {
            mapPushFlag: !0
          }))
        }, 300), b.ready.hide(), l = !0)
      },
      missionToggle: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = b.doc.querySelector("#questLinkList");
          var c = b.doc.querySelector("#questLinkList").className; - 1 !== c.indexOf("first") ? a.className = "second" : -1 !== c.indexOf("second") && (a.className = "first")
        }
      }
    }),
    la = z.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " .debugBtn"] = this.debugBtn;
        a[b.cgti + " #helpBtn"] = I;
        a[b.cgti + " #battleStartBtn"] = this.battleStartBtn;
        a[b.cgti + " #commentPopBtn"] = this.commentPopBtn;
        return a
      },
      debugBtn: function(a)
      {
        a.preventDefault();
        if (l)
        {
          var c = {};
          $.extend(c, U);
          var d = a.currentTarget.dataset.mode;
          if ("PUSH_STORYRAID" == d) a = a.currentTarget.dataset.mode, "IN_BATTLE" == a ? console.log("【DEBUG】BOSS交战中(第2次起)") : "FIRST_BATTLE" == a ? console.log("【DEBUG】BOSS交战中(首次)") : "FINAL_BATTLE" == a && console.log("【DEBUG】BOSS最终战HELP"), c.state = a, $("#commandDiv").off(), f.popEventStoryRaid(), u(c, "boss");
          else if ("COMMENT_ANIME" == d)
          {
            var e = b.doc.getElementById("cutinComment");
            e.className = "";
            setTimeout(function()
            {
              $(e).on("webkitAnimationEnd", function(a)
              {
                $(e).off("webkitAnimationEnd");
                e.className = ""
              });
              e.className = "anim"
            }, 500)
          }
        }
      },
      initialize: function(a)
      {
        this.model = Object.assign(
        {}, a.sectionModel ? a.sectionModel : a.newSectionModel,
        {
          eventObj: h
        });
        this.model.status = a.status;
        this.model.commentCount = a.commentCount;
        this.model.itemQuantity = F;
        this.template = g.template(ca);
        this.createDom();
        "FINAL_BATTLE" != this.model.status && (this.commentList = a.commentList, this.commentIndex = 0, this.commentAbleFlag = !0, this.commentList && 0 < this.commentList.length && setTimeout(function()
        {
          this.commentEventSet();
          this.commentUpdate(this.commentList[0])
        }.bind(this), 200))
      },
      render: function()
      {
        this.$el.html(this.template(this.model));
        return this
      },
      createDom: function()
      {
        var a = this.render().el;
        l && b.addClass(a.querySelector("#EventStoryRaidBoss"), "pageFadein");
        b.content.append(a);
        if (l) $("#EventStoryRaidBoss").on("webkitAnimationEnd", function()
        {
          $("#EventStoryRaidBoss").off();
          b.removeBackHandler();
          b.addBackHandler(A.bind(null,
          {
            mapPushFlag: !0
          }));
          b.removeClass(b.doc.querySelector("#EventStoryRaidBoss"), "pageFadein");
          b.tapBlock(!1);
          b.androidKeyStop = !1
        });
        else setTimeout(function()
        {
          L();
          b.removeBackHandler();
          b.addBackHandler(A.bind(null,
          {
            mapPushFlag: !0
          }))
        }, 300), b.ready.hide(), l = !0
      },
      battleStartBtn: function(a)
      {
        a.preventDefault();
        b.isScrolled() || this.questStart()
      },
      questStart: function()
      {
        var a = g.findWhere(n,
          {
            sectionId: this.model.sectionId
          }),
          c, d;
        if (a)
        {
          d = g.find(k.userEventStoryRaidPointList, function(b)
          {
            return a.sectionId === b.point.sectionId
          });
          var e = d.point.raidQuestBattleId;
          c = "IN_BATTLE" == this.model.status ? g.findWhere(k.userQuestBattleList,
          {
            questBattleId: e
          }) : g.find(k.userQuestBattleList, function(b)
          {
            return a.sectionId === b.questBattle.sectionId && b.questBattleId !== e
          })
        }
        b.questBattleModel = ka(a, c, d);
        console.log(b.questBattleModel);
        if (b.questBattleModel)
          if (d = b.globalMenuView.getUserStatus(), c = b.questBattleModel.overwriteAp || 0 === b.questBattleModel.overwriteAp ? Number(b.questBattleModel.overwriteAp) : b.questBattleModel.ap, d = d.ACP, c && d < c)
          {
            new b.PopupClass(
            {
              title: "关卡确认",
              content: "AP 不足",
              closeBtnText: "关闭"
            });
            var m = this;
            b.globalMenuView.apPopup(null, "AP 不足", function()
            {
              m.questStart()
            })
          }
        else f.changeBg(h.viewParameterMap.BG_BOSS_IMG + ".ExportJson"), b.oldEventStoryRaidSectionList = null, b.oldEventStoryRaidSectionList = n, b.storyRaidpointType = "", location.href = "#/SupportSelect";
        else new b.PopupClass(
        {
          title: "关卡确认",
          content: "无法开始关卡",
          closeBtnText: "关闭"
        }, null, null, function()
        {
          location.href = "#/MyPage"
        })
      },
      commentEventSet: function()
      {
        var a = b.doc.getElementById("commentText");
        $(a).on("webkitAnimationEnd", function(a)
        {
          this.commentIndex++;
          this.commentIndex >= this.commentList.length && (this.commentIndex = 0);
          this.commentUpdate(this.commentList[this.commentIndex])
        }.bind(this))
      },
      commentUpdate: function(a, c)
      {
        var d = b.doc.getElementById("commentText");
        d.className = "";
        a = a.comment + "　【" + a.userName + "】";
        var e = "anim";
        c && (e += " own");
        d.textContent = a;
        setTimeout(function()
        {
          d.className = e
        }, 200)
      },
      commentPopBtn: function(a)
      {
        if (a && (a.preventDefault(), b.isScrolled())) return;
        a = function()
        {
          this.commentAbleFlag || b.addClass(b.doc.getElementById("commentDecide"), "off")
        }.bind(this);
        new b.PopupClass(
        {
          title: "应援留言",
          content: "",
          exClass: "storyraidCommentPopup",
          popupType: "typeC"
        }, null, a);
        a = b.doc.createElement("div");
        a.innerHTML = $("#commentParts").html();
        b.doc.getElementById("popupArea").getElementsByClassName("popupTextArea")[0].appendChild(a);
        $("#commandDiv").off();
        b.nativeKeyBoard("commentInput", 20, 0, "textCount");
        var c = !1;
        b.doc.getElementById("commentDecide").addEventListener(b.cgti, function(a)
        {
          a.preventDefault();
          if (!b.isScrolled() && !c)
          {
            c = !0;
            var e = b.doc.getElementById("commentInput").value;
            a = function(a)
            {
              if ("error" !== a.resultCode)
              {
                b.g_popup_instance && b.g_popup_instance.popupView.close();
                var c = b.doc.getElementById("bonusWrap");
                if ("show" != c.className)
                {
                  var d = b.doc.getElementById("cutinComment");
                  $(d).on("webkitAnimationEnd", function(a)
                  {
                    $(d).off("webkitAnimationEnd");
                    c.className = "show"
                  });
                  d.className = "anim";
                  setTimeout(function()
                  {
                    f.startSe(3203)
                  }, 800)
                }
                this.commentAbleFlag = !1;
                setTimeout(function()
                {
                  this.commentAbleFlag = !0;
                  b.removeClass(b.doc.getElementById("commentDecide"), "off")
                }.bind(this), 3E4);
                a = {
                  userName: b.storage.user.get("loginName"),
                  comment: e
                };
                this.commentUpdate(a, !0)
              }
            }.bind(this);
            "" === e ? (a = function()
            {
              this.commentPopBtn()
            }.bind(this), new b.PopupClass(
            {
              title: "应援留言",
              content: "请输入留言。",
              closeBtnText: "关闭",
              popupType: "typeC"
            }, null, null, a)) : y.ajaxPost(b.linkList.storyraidCommentSend,
            {
              pointId: this.model.pointModel.pointId,
              comment: e
            }, a)
          }
        }.bind(this))
      }
    }),
    O = function()
    {
      f.changeBg("web_black.jpg");
      if (v && !w) f.stopBgm(), p = new B;
      else if (f.startBgm(h.viewParameterMap.BGM), w)
      {
        $(b.ready.content).off("webkitAnimationEnd");
        var a = g.findWhere(b.storage.userQuestBattleList.toJSON(),
        {
          questBattleId: w
        });
        q = g.findWhere(b.oldEventStoryRaidSectionList,
        {
          sectionId: a.questBattle.sectionId
        });
        var c = g.findWhere(n,
        {
          sectionId: a.questBattle.sectionId
        });
        console.log("playedQuestModel", a);
        console.log("playedSectionModel", q);
        console.log("eventSectionList", n);
        console.log("newSectionModel", c);
        var d = !1;
        !q.clearedAt && c.clearedAt && (d = !0);
        var a = H(q.pointModel),
          e = {
            sectionModel: q,
            newSectionModel: c
          };
        if (d) c = N(), d = Z(), d != q.pointModel.pointId && (c.centerPointId = q.pointModel.pointId, c.newPointIdList = [d]), a && (c.needRaidDestroyedCutin = a), $("#commandDiv").off(), $("#commandDiv").on("nativeCallback", function(a, b)
        {
          $("#commandDiv").off();
          p = new B(e)
        }), u(c, "top"), window.isBrowser && nativeCallback();
        else if (b.tapBlock(!0), b.androidKeyStop = !0, a)
        {
          if (a = q.pointModel.clearCount < c.pointModel.clearCount) e.playerCommentFlag = a;
          W(e)
        }
        else r = new X(e)
      }
      else $("#commandDiv").on("nativeCallback", function(a, b)
      {
        $("#commandDiv").off();
        p = new B
      }), c = N(), u(c, "top"), window.isBrowser && nativeCallback();
      C.supportPickUp(k)
    },
    H = function(a)
    {
      return "BOSS" == a.point.pointType || "LAST" == a.point.pointType
    },
    I = function(a, c)
    {
      if (a && (a.preventDefault(), b.isScrolled())) return;
      b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], h.eventId, "storyraid", c, !0)
    },
    V = function()
    {
      b.tapBlock(!1);
      b.androidKeyStop = !1;
      var a = h.endAt.substr(5, 11);
      "0" == a[0] && (a = a.substr(1));
      a = a.replace("/", "月");
      a = a.replace(" ", "日 ");
      new b.PopupClass(
      {
        title: "活动参加条件",
        content: "活动『" + h.name + "』<br>" + a + "截止。<br><br>参加活动需要满足<br>【" + k.conditionDescript + "】<br>这一条件。",
        exClass: "eventCondPopup",
        decideBtnText: "前往主线剧情",
        decideBtnLink: "#/MainQuest",
        closeBtnText: "取消",
        popupType: "typeC"
      }, null, null, function()
      {
        location.href = "#/MyPage"
      })
    },
    L = function(a)
    {
      $(b.ready.content).on("webkitAnimationEnd", function(c)
      {
        "readyFadeIn" == c.originalEvent.animationName && (b.tapBlock(!1), b.androidKeyStop = !1, b.scrollRefresh(null, null, null, !0), a && a())
      })
    },
    P = function()
    {
      var a = b.storage.userQuestBattleList.toJSON(),
        c = b.storage.userSectionList.toJSON(),
        d = k.userEventStoryRaidPointList;
      n = [];
      g.each(c, function(a)
      {
        "STORYRAID" == a.section.questType && n.push(a)
      });
      g.each(d, function(a)
      {
        if (a && a.point)
        {
          var b = g.findWhere(n,
          {
            sectionId: a.point.sectionId
          });
          b.pointModel = a ||
          {};
          a.sectionModel = b
        }
      });
      var e = 1;
      g.each(n, function(c)
      {
        var d = c.sectionId;
        c.section.questBattleList = [];
        g.each(a, function(a, f)
        {
          d == a.questBattle.sectionId && (a.title = "战斗 " + e, a.missionRewardObj = b.itemSet(a.questBattle.missionRewardCode), c.section.questBattleList.push(a), e++)
        });
        c.section.questBattleList.sort(function(a, b)
        {
          return a.questBattle.sectionIndex < b.questBattle.sectionIndex ? -1 : a.questBattle.sectionIndex > b.questBattle.sectionIndex ? 1 : 0
        })
      });
      console.log("eventSectionList:old", b.oldEventStoryRaidSectionList);
      console.log("eventSectionList", n);
      console.log("userEventStoryRaidPointList", k.userEventStoryRaidPointList)
    },
    ka = function(a, b, d)
    {
      if (!a || !b || !d) return !1;
      var c = {};
      a = a.section;
      c.questType = a.questType;
      c.title = h.name;
      c.battleTitle = d.point.title;
      c.userQuestAdventureList = y.getPageJson().userQuestAdventureList;
      c.rewardCodeArr = [];
      a.secret && (c.secret = a.secret);
      c.questBattle = b.questBattle;
      c.eventFlag = !0;
      c.ap = b.questBattle.ap;
      c.difficulty = b.questBattle.difficulty;
      c.cleared = b.cleared;
      c.missionStatus1 = b.missionStatus1;
      c.missionStatus2 = b.missionStatus2;
      c.missionStatus3 = b.missionStatus3;
      b = C.dropItemJson(b);
      b.firstClearReward && (c.firstClearReward = b.firstClearReward);
      b.firstClearRewardName && (c.firstClearRewardName = b.firstClearRewardName);
      b.firstClearRewardQuantity && (c.firstClearRewardQuantity = b.firstClearRewardQuantity);
      b.addDropItem && (c.addDropItem = b.addDropItem);
      b.addDropItemName && (c.addDropItemName = b.addDropItemName);
      b.addDropItemQuantity && (c.addDropItemQuantity = b.addDropItemQuantity);
      c.rewardCodeArr = b.list;
      c.rewardNameArr = b.nameList;
      c.rewardQuantityArr = b.quantityList;
      return c
    },
    J = function(a, c)
    {
      for (var d = [], e = "END" !== c ? "touches" : "changedTouches", m = 0; m < a.originalEvent[e].length; m++)
      {
        var g = a.originalEvent[e][m].identifier;
        0 > g && (g = -g);
        d[m] = {
          identifier: g,
          clientX: 1024 === b.displayWidth ? a.originalEvent[e][m].clientX : 1024 * a.originalEvent[e][m].clientX / 1280,
          clientY: 1024 === b.displayWidth ? a.originalEvent[e][m].clientY : 1024 * a.originalEvent[e][m].clientY / 1280
        }
      }
      switch (c)
      {
        case "START":
          f.callTouchesBegin(d);
          break;
        case "MOVE":
          f.callTouchesMove(d);
          break;
        case "END":
          f.callTouchesEnd(d)
      }
    },
    K = function()
    {
      $("#commandDiv").on("nativeCallback", function(a, b)
      {
        b && b.pointId && (a = G(b.pointId), a.clearedAt ? (f.startSe(1003), f.enableTapEventSingleRaid(
        {
          enable: !0
        })) : (f.startSe(1002), p.mapHide(a)))
      })
    },
    A = function(a)
    {
      b.tapBlock(!0);
      b.androidKeyStop = !0;
      f.endL2d();
      f.changeBg("web_black.jpg");
      var c = "#EventStoryRaidSelect";
      x && (c = "#EventStoryRaidBoss");
      $(c).off();
      $(c).on("webkitAnimationEnd", function()
      {
        $(c).off();
        r && (r.trigger("removeView"), r.remove(), r = null);
        x && (x.remove(), x = null, f.popEventStoryRaid());
        if (a.mapPushFlag)
        {
          var d = N();
          $("#commandDiv").off();
          $("#commandDiv").on("nativeCallback", function(a, b)
          {
            $("#commandDiv").off();
            p = new B
          });
          u(d, "top");
          window.isBrowser && nativeCallback()
        }
        else p = new B, f.resumeEventSingleRaid();
        b.removeBackHandler()
      });
      b.addClass(b.doc.querySelector(c), "pageFadeout")
    },
    Z = function()
    {
      var a = k.userEventStoryRaidPointList;
      return 0 < a.length ? a[a.length - 1].pointId : null
    },
    N = function()
    {
      var a = {
          raidType: "HUGE",
          mapWidth: R,
          mapHeight: S,
          pointList: k.pointList,
          mapEffectList: k.mapEffectList
        },
        b = Z();
      b && (a.centerPointId = b);
      return a
    },
    G = function(a)
    {
      var b;
      g.each(n, function(c)
      {
        c.pointModel && c.pointModel.pointId == a && (b = c)
      });
      return b
    },
    W = function(a)
    {
      var c = a.newSectionModel ? a.newSectionModel : a.sectionModel;
      y.ajaxPost(b.linkList.storyraidBossDetail,
      {
        pointId: c.pointModel.pointId
      }, function(d)
      {
        if ("error" !== d.resultCode)
        {
          b.responseSetStorage(d);
          a.commentList = d.commentList;
          a.status = d.status;
          a.commentCount = d.commentCount;
          var e = d.battleDetail;
          d = d.status;
          "IN_BATTLE" == d && (c.pointModel.clearCount || (d = "FIRST_BATTLE"));
          e.state = d;
          a.playerCommentFlag && "FINAL_BATTLE" != d || (e.name = "");
          $("#commandDiv").off();
          $("#commandDiv").on("nativeCallback", function(b, c)
          {
            $("#commandDiv").off();
            x = new la(a)
          });
          u(e, "boss");
          window.isBrowser && nativeCallback()
        }
      })
    },
    M = function(a, c, d)
    {
      var e = !1,
        e = !0;
      d || g.each(b.storage.userQuestAdventureList.toJSON(), function(b)
      {
        a === b.adventureId && (e = !1)
      });
      e ? ($(b.ready.target).off(), $(b.ready.target).on("webkitAnimationEnd", function()
      {
        f.changeBg("web_black.jpg");
        $(b.ready.target).off();
        $(b.ready.target).on("webkitAnimationEnd", function(a)
        {
          "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
        });
        y.ajaxPost(b.linkList.userQuestAdventureRegist,
        {
          adventureId: String(a)
        }, c)
      }), b.ready.target.classList.contains("preNativeFadeIn") ? $(b.ready.target).trigger("webkitAnimationEnd") : b.addClass(b.ready.target, "preNativeFadeIn")) : c()
    },
    Y = function(a)
    {
      h.existsVoice ? ($("#commandDiv").off(), $("#commandDiv").on("nativeCallback", function()
      {
        $("#commandDiv").off();
        a()
      }), f.downloadFileFullVoice("section_event_" + h.eventId), window.isBrowser && nativeCallback()) : a()
    },
    u = function(a, b)
    {
      "top" == b ? f.pushEventSingleRaid(a) : "boss" == b && f.pushEventStoryRaid(a)
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
    fetch: function(a)
    {
      a && (w = a | 0);
      y.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      b.setGlobalView();
      b.setStyle(da + ea + ga);
      b.clearSectionModel = null;
      b.clearChapterModel = null;
      k = y.getPageJson();
      h = g.findWhere(k.eventList,
      {
        eventType: "STORYRAID"
      });
      k.eventMaster = h;
      if (k.userEventStoryRaidPointList)
      {
        b.historyArr = ["MyPage", "EventStoryRaidTop"];
        v = !1;
        var a = k.userEventStoryRaidPointList.length;
        k.pointCount <= a && (a = k.userEventStoryRaidPointList[a - 1].point.sectionId, v = g.findWhere(b.storage.userSectionList.toJSON(),
        {
          sectionId: a
        }).clearedAt ? !0 : !1);
        D = !1;
        if (v)
        {
          var c = h.viewParameterMap.EPILOGUE_STORY_ID;
          this.isEpAlreadyRead = !1;
          g.each(b.storage.userQuestAdventureList.toJSON(), function(a)
          {
            c === a.adventureId && (D = !0)
          })
        }
        R = Number(h.viewParameterMap.MAP_WIDTH);
        S = Number(h.viewParameterMap.MAP_HEIGHT);
        F = (a = b.storage.userItemList.findWhere(
        {
          itemId: "EVENT_STORYRAID_" + h.eventId + "_EXCHANGE_1"
        })) ? a.get("quantity") : 0;
        !w && b.questBattleModel && "STORYRAID" == b.questBattleModel.questType && (w = b.questBattleModel.questBattle.questBattleId);
        if (w)
          if (b.eventStoryRaidResumeData)
          {
            console.log("common.eventStoryRaidResumeData", b.eventStoryRaidResumeData);
            P();
            var d = [];
            g.each(b.eventStoryRaidResumeData.userSectionList, function(a)
            {
              "STORYRAID" == a.section.questType && d.push(a)
            });
            g.each(b.eventStoryRaidResumeData.userEventStoryRaidPointList, function(a)
            {
              a && a.point && (g.findWhere(d,
              {
                sectionId: a.point.sectionId
              }).pointModel = a ||
              {})
            });
            b.oldEventStoryRaidSectionList = d;
            b.eventStoryRaidResumeData = null
          }
        else P(), b.oldEventStoryRaidSectionList || (b.oldEventStoryRaidSectionList = n);
        else P();
        if (window.isBrowser) O();
        else
        {
          var e = h.startStoryId;
          M(e, function(a)
          {
            a ? (b.responseSetStorage(a), $("#commandDiv").on("nativeCallback", function(a, c)
            {
              $("#commandDiv").off();
              f.setWebView(!0);
              b.tapBlock(!1);
              b.androidKeyStop = !1;
              f.startBgm(h.viewParameterMap.BGM);
              b.ready.target.className = "nativeFadeOut";
              b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], h.eventId, "storyraid", function()
              {
                O()
              })
            }), setTimeout(function()
            {
              f.setWebView(!1);
              f.startStory(e,
              {
                canSkip: !1,
                canAuto: !1,
                canOpenLog: !1
              });
              window.isBrowser && nativeCallback()
            }, 500)) : O()
          })
        }
      }
      else V()
    },
    remove: function(a)
    {
      p && (p.remove(), p = null);
      r && (r.trigger("removeView"), r.remove(), r = null, b.questBattleModel && (b.questBattleModel.title = h.name, b.questBattleModel.battleTitle = T));
      x && (x.remove(), x = null, f.popEventStoryRaid());
      t && (t.removeHandler(), t = null);
      f.endL2d();
      l = !1;
      n = q = w = null;
      $(b.ready.content).on("webkitAnimationEnd", function(a)
      {
        "readyFadeIn" == a.originalEvent.animationName && (b.tapBlock(!1), b.scrollRefresh(null, null, null, !0))
      });
      $("#commandDiv").off();
      b.removeBackHandler();
      f.popEventSingleRaid();
      f.callTouchesClear();
      a()
    }
  }
});
