define("underscore backbone backboneCommon ajaxControl command text!template/event/dungeon/EventDungeonMap.html text!css/event/dungeon/EventDungeonMap.css cardUtil".split(" "), function(m, v, a, k, e, z, A, B)
{
  v.Model.extend(
  {});
  var l, n, u, p, r = v.View.extend(
    {
      events: function()
      {
        var b = {};
        b["touchstart #mapWrap"] = this.touchStart;
        b["touchmove #mapWrap"] = this.touchMove;
        b["touchend #mapWrap"] = this.touchEnd;
        b[a.cgti + " #closeBtn"] = this.wrapHide;
        b[a.cgti + " #openBtn"] = this.wrapShow;
        b[a.cgti + " #resetPosition"] = this.resetPosition;
        b[a.cgti + " .btnRetire"] = this.retirePop;
        b[a.cgti + " .missionBtn"] = this.missionPop;
        b[a.cgti + " .btnCure"] = this.cureOn;
        b[a.cgti + " .cureCancel"] = this.cureCancel;
        b[a.cgti + " .btnMember"] = this.linkToDeck;
        b[a.cgti + " .debugRun"] = this.debugRun;
        return b
      },
      initialize: function(b)
      {
        this.cureFlg = this.initFlag = !1;
        this.template = m.template(z);
        this.currentPoint = p;
        this.eventMaster = m.findWhere(l.eventList,
        {
          eventType: "DUNGEON"
        });
        this.areaMaster = l.userEventDungeonArea;
        a.dungeonAreaModel = l.userEventDungeonArea;
        this.userEventDungeon = l.userEventDungeon;
        a.userEventDungeon = l.userEventDungeon;
        this.sectionMaster = m.findWhere(l.userSectionList,
        {
          sectionId: this.areaMaster.area.sectionId
        }).section;
        this.areaType = -1 < this.sectionMaster.parameter.indexOf("CHALLENGE") ? "challenge" : "story";
        console.log("currentPoint:", this.currentPoint);
        console.log("this.sectionMaster", this.sectionMaster);
        this.createDom();
        setTimeout(function()
        {
          this.showMapInfo()
        }.bind(this), 1E3)
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: l,
          event: this.eventMaster,
          area: this.areaMaster,
          areaType: this.areaType,
          section: this.sectionMaster
        }));
        return this
      },
      createDom: function()
      {
        a.content.append(this.render().el);
        w.prototype.rootView = this;
        w.prototype.template = m.template($("#deckParts").text());
        this.createDeckView();
        e.getBaseData(a.getNativeObj());
        a.ready.hide();
        a.dungeonReshow && (a.removeClass(a.doc.getElementById("EventDungeonMap"), "initial"), a.removeClass(a.doc.getElementById("EventDungeonMap"), "uiHide"));
        this.initFlag = !0;
        this.cureCount();
        if (window.isDebug && window.isBrowser)
        {
          var b = a.doc.createDocumentFragment();
          m.each(this.currentPoint.point.connectPointIdList, function(c, d)
          {
            d = a.doc.createElement("div");
            d.className = "mb_white se_decide debugRun";
            d.dataset.targetId = c;
            d.innerHTML = c;
            b.appendChild(d)
          });
          a.doc.getElementById("debugArea").appendChild(b);
          b = null
        }
      },
      createDeckView: function()
      {
        var b = a.doc.createDocumentFragment(),
          c = a.doc.createDocumentFragment(),
          d = m.sortBy(u, "position"),
          e = 0,
          f = 0;
        m.each(d, function(a, d)
        {
          d = new w(
          {
            model: a.card,
            piece: a.piece
          });
          10 > a.position ? (b.appendChild(d.render().el), e++) : (c.appendChild(d.render().el), f++)
        });
        if (5 > e)
          for (; 5 > e;) d = a.doc.createElement("div"), d.className = "charaWrap", d.innerHTML = a.doc.getElementById("emptyParts").innerHTML, b.appendChild(d), e = e + 1 | 0, d = null;
        if (2 > f)
          for (; 2 > f;) d = a.doc.createElement("div"), d.className = "charaWrap empty", d.innerHTML = a.doc.getElementById("emptyParts").innerHTML, c.appendChild(d), f = f + 1 | 0, d = null;
        a.doc.getElementById("partyWrap").getElementsByClassName("mainPartyWrap")[0].appendChild(b);
        a.doc.getElementById("partyWrap").getElementsByClassName("subPartyWrap")[0].appendChild(c);
        d = c = b = null
      },
      cureCount: function()
      {
        for (var b = this.userEventDungeon.cureRemain, c = a.doc.getElementById("cureIcons").getElementsByClassName("cure"), d = 0; 5 > d; d++) c[d].className = b > d ? "cure" : "cure off";
        0 === b && a.addClass(a.doc.getElementById("bottomWrap").getElementsByClassName("btnCure")[0], "off")
      },
      touchStart: function(b)
      {
        b.preventDefault();
        this.initFlag && !this.movingFlag && ($("#commandDiv").off(), a.tapEffectStop = !0, x(b, "START"))
      },
      touchMove: function(a)
      {
        a.preventDefault();
        this.initFlag && (this.movingFlag || x(a, "MOVE"))
      },
      touchEnd: function(b)
      {
        b.preventDefault();
        a.tapEffectStop = !1;
        if (this.initFlag && !this.movingFlag)
        {
          var c = this;
          $("#commandDiv").off();
          $("#commandDiv").on("nativeCallback", function(a, b)
          {
            $("#commandDiv").off();
            c.checkNativeCallback(b)
          });
          x(b, "END");
          a.isScrolled()
        }
      },
      checkNativeCallback: function(b)
      {
        this.movingFlag = !0;
        if (b && b.pointId)
        {
          var c = m.findWhere(l.userEventDungeonPointList,
          {
            pointId: b.pointId
          });
          if (void 0 === c || null === c) this.movingFlag = !1;
          else if (-1 === this.currentPoint.point.connectPointIdList.indexOf(c.pointId)) this.movingFlag = !1;
          else
          {
            var d = this;
            e.startSe(1002);
            new a.PopupClass(
            {
              title: "移动点位",
              content: "要前往下一个点位吗?",
              exClass: "missionPop",
              popupType: "typeC",
              closeBtnText: "关闭",
              decideBtnText: "确定",
              decideBtnEvent: function(b)
              {
                b.preventDefault();
                if (!a.isScrolled()) switch (a.androidKeyStop = !0, c.point.type)
                {
                  case "BATTLE":
                  case "END":
                    a.tapBlock(!0);
                    d.battlePoint(c);
                    break;
                  case "DAMAGE":
                  case "HEAL":
                  case "REWARD":
                  case "RANDOM":
                    a.tapBlock(!0), d.effectPoint(c)
                }
              }
            }, null, null, function()
            {
              d.movingFlag = !1
            })
          }
        }
        else this.movingFlag = !1
      },
      battlePoint: function(b)
      {
        a.g_popup_instance && a.g_popup_instance.remove();
        this.movingFlag = !0;
        var c = this,
          d = {};
        d.questBattleId = b.point.questBattleId;
        d.deckType = c.userEventDungeon.selectedDeckType;
        for (var h = a.storage.userDeckList.findWhere(
          {
            deckType: d.deckType
          }).toJSON(), f = !1, g = 1; 11 > g; g++)
          if (h["userCardId" + g] && !a.storage.userCharaList.findWhere(
            {
              userCardId: h["userCardId" + g]
            }).toJSON().retired && 10 > h["questPositionId" + g])
          {
            f = !0;
            d["userCardId" + g] = h["userCardId" + g];
            d["questPositionId" + g] = h["questPositionId" + g];
            for (var q = 1; 5 > q; q++)
            {
              var t = ("0" + g + "" + q).slice(-3);
              h["userPieceId" + t] && (d["userPieceId" + t] = h["userPieceId" + t])
            }
          } f ? (h = {
          pointId: b.pointId
        }, console.log("dungeon move Api:", b), k.ajaxPost(a.linkList.dungeonMove, h, function(f)
        {
          console.log("-------- move api success --------");
          console.log("move api Response(battle):", f);
          a.responseSetStorage(f);
          c.currentPoint = m.findWhere(l.userEventDungeonPointList,
          {
            pointId: b.pointId
          });
          var g = function(b)
          {
            console.log("battleCallback:", b);
            e.changeBg("web_black.jpg");
            setTimeout(function()
            {
              e.hideEventDungeon();
              e.setWebView(!1);
              window.isBrowser ? (a.stubQuest = d, e.sendCommand("QuestStub")) : ($("#commandDiv").on("nativeCallback", function(b, c)
              {
                $("#commandDiv").off();
                c && (b = c.webData, c = b.userQuestBattleResultList[0].questBattle, a.responseSetStorage(b), b = (b = a.storage.userSectionList.findWhere(
                {
                  sectionId: c.sectionId
                })) ? b.toJSON() : null) && (c = (c = a.storage.userChapterList.findWhere(
                {
                  chapterId: b.section.genericId
                })) ? c.toJSON() : null, a.playChapter = c, a.playSection = b);
                a.androidKeyStop = !1;
                location.href = "#/QuestBackground"
              }), C(b))
            }, 500)
          };
          $("#commandDiv").on("nativeCallback", function(b, e)
          {
            $("#commandDiv").off();
            b = function()
            {
              k.ajaxPost(a.linkList.questStart, d, g)
            };
            c.currentPoint.point.startStoryId ? c.pointStory(c.currentPoint.point.startStoryId, b) : b()
          });
          a.addClass(a.doc.getElementById("globalMenuContainer"), "hide");
          a.addClass(a.doc.getElementById("EventDungeonMap"), "hide");
          e.decideEventDungeon();
          window.isBrowser && nativeCallback()
        })) : (new a.PopupClass(
        {
          title: "不可移动",
          content: "请将未失去战斗能力的魔法少女<br>编入主力成员。",
          popupType: "typeC",
          closeBtnText: "关闭"
        }), a.tapBlock(!1), this.movingFlag = a.androidKeyStop = !1)
      },
      effectPoint: function(b)
      {
        a.g_popup_instance && a.g_popup_instance.remove();
        this.movingFlag = !0;
        var c = this,
          d = {
            pointId: b.pointId
          };
        console.log("dungeon move Api:", b);
        k.ajaxPost(a.linkList.dungeonMove, d, function(d)
        {
          console.log("-------- move api success --------");
          console.log("move api Response(effect):", d);
          a.responseSetStorage(d);
          d.userEventDungeon && (a.userEventDungeon = d.userEventDungeon);
          c.currentPoint = m.findWhere(l.userEventDungeonPointList,
          {
            pointId: b.pointId
          });
          console.log("new currentPoint:", c.currentPoint);
          if (window.isBrowser)
          {
            a.removeClass(a.doc.getElementById("EventDungeonMap"), "uiHide");
            c.trigger("hpCheck");
            e.getBaseData(a.getNativeObj());
            c.movingFlag = !1;
            var f = a.doc.createDocumentFragment();
            m.each(c.currentPoint.point.connectPointIdList, function(b, c)
            {
              c = a.doc.createElement("div");
              c.className = "mb_white se_decide debugRun";
              c.dataset.targetId = b;
              c.innerHTML = b;
              f.appendChild(c)
            });
            a.doc.getElementById("debugArea").innerHTML = null;
            a.doc.getElementById("debugArea").appendChild(f);
            f = null;
            a.androidKeyStop = !1;
            a.tapBlock(!1)
          }
          else $("#commandDiv").on("nativeCallback", function(b, d)
          {
            $("#commandDiv").off();
            c.currentPoint.point.clearStoryId ? (c.trigger("hpCheck"), e.getBaseData(a.getNativeObj()), c.pointStory(c.currentPoint.point.clearStoryId, c.showMapInfo)) : (c.trigger("hpCheck"), e.getBaseData(a.getNativeObj()), a.dungeonReshow && a.removeClass(a.doc.getElementById("EventDungeonMap"), "uiHide"), a.androidKeyStop = !1, c.movingFlag = !1, a.tapBlock(!1), c.showMapInfo())
          }), a.addClass(a.doc.getElementById("EventDungeonMap"), "uiHide"), "RANDOM" == b.point.type ? e.randomIconEventDungeon(
          {
            icon: d.processedIcon
          }) : e.decideEventDungeon()
        })
      },
      pointStory: function(b, c)
      {
        var d = this,
          h = function()
          {
            d.movingFlag = !1;
            a.tapBlock(!1);
            a.androidKeyStop = !1;
            a.dungeonReshow && a.removeClass(a.doc.getElementById("EventDungeonMap"), "uiHide");
            c && (c(), c = null)
          };
        if (b)
        {
          var f = a.storage.userQuestAdventureList.findWhere(
          {
            adventureId: b
          });
          console.log("pointStory:", b, f);
          f ? h() : (a.androidKeyStop = !0, f = function()
          {
            $("#commandDiv").on("nativeCallback", function(c, f)
            {
              f && f.pointId || ($("#commandDiv").off(), f && f.isSkipped && (c = {}, c.adventureId = String(b), k.ajaxPost(a.linkList.adventureSkip, c, function(b)
              {
                a.responseSetStorage(b)
              })), c = d.areaMaster.area.areaBgmId, e.setWebView(), e.startBgm(c), h())
            });
            k.ajaxPost(a.linkList.userQuestAdventureRegist,
            {
              adventureId: String(b)
            }, function(c)
            {
              "error" !== c.resultCode && (a.responseSetStorage(c), e.stopBgm(), e.stopSe(), setTimeout(function()
              {
                e.startStory(String(b));
                setTimeout(function()
                {
                  e.setWebView(!1)
                }, 500)
              }, 500))
            })
          }, window.isBrowser ? (k.ajaxPost(a.linkList.userQuestAdventureRegist,
          {
            adventureId: String(b)
          }, function(b)
          {
            "error" !== b.resultCode && a.responseSetStorage(b)
          }), a.androidKeyStop = !1, window.isDebug && window.isBrowser && h()) : f())
        }
        else h()
      },
      wrapHide: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (a.addClass(a.doc.getElementById("EventDungeonMap"), "uiHide"), a.dungeonReshow = !1, this.cureFlg && this.cureCancel())
      },
      linkToDeck: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (e.changeBg("bg_adv_" + this.areaMaster.area.orgBackground + ".jpg"), location.href = "#/DeckFormation/dungeonInMap")
      },
      wrapShow: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (a.dungeonReshow = !0, a.removeClass(a.doc.getElementById("EventDungeonMap"), "initial"), a.removeClass(a.doc.getElementById("EventDungeonMap"), "uiHide"))
      },
      resetPosition: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          b = (new Date).getTime();
          var c = this.pushTimer ? b - this.pushTimer : 0;
          this.pushTimer && 300 > c || (this.pushTimer = b, e.positionResetEventDungeon())
        }
      },
      retirePop: function(b)
      {
        b.preventDefault();
        a.isScrolled() || new a.PopupClass(
        {
          title: "放弃",
          content: $("#retirePop").text(),
          exClass: "retirePop",
          popupType: "typeA",
          closeBtnText: "取消",
          decideBtnText: "放弃",
          decideBtnEvent: function(b)
          {
            b.preventDefault();
            a.isScrolled() || k.ajaxPost(a.linkList.dungeonEnd,
            {}, function(b)
            {
              a.responseSetStorage(b);
              a.dungeonEnd = "RETIRED";
              a.dungeonReshow = null;
              a.historyArr = ["MyPage", "EventDungeonTop"];
              location.href = "#/EventDungeonTop"
            })
          }
        })
      },
      missionPop: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (new a.PopupClass(
        {
          title: "任务",
          content: "",
          exClass: "missionPop",
          popupType: "typeC",
          closeBtnText: "关闭"
        }), b = m.template($("#missionPop").text()), a.doc.getElementById("popupArea").getElementsByClassName("popupTextArea")[0].innerHTML = b(
        {
          model: this.areaMaster
        }))
      },
      cureOn: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (0 < this.userEventDungeon.cureRemain ? (this.cureFlg = !0, a.addClass(a.doc.getElementById("bottomWrap"), "useCure")) : (b = m.template($("#cantCurePop").text()), new a.PopupClass(
        {
          title: "魔法少女回复",
          content: b(
          {
            model: this.userEventDungeon
          }),
          exClass: "curePopEx",
          popupType: "typeA",
          closeBtnText: "关闭"
        })))
      },
      cureCancel: function(b)
      {
        if (b && (b.preventDefault(), a.isScrolled())) return;
        this.cureFlg = !1;
        a.removeClass(a.doc.getElementById("bottomWrap"), "useCure")
      },
      showMapInfo: function()
      {
        var b = a.doc.getElementById("mapInfo");
        a.addClass(b, "show");
        setTimeout(function()
        {
          a.removeClass(b, "show")
        }, 1E3)
      },
      debugRun: function(b)
      {
        b.preventDefault();
        !a.isScrolled() && window.isDebug && window.isBrowser && ($("#commandDiv").off(), console.log("debug move to", Number(b.currentTarget.dataset.targetId)), this.checkNativeCallback(
        {
          pointId: Number(b.currentTarget.dataset.targetId)
        }))
      },
      removeHandler: function()
      {
        this.trigger("removeView");
        this.off();
        this.remove()
      }
    }),
    w = v.View.extend(
    {
      className: "charaWrap",
      events: function()
      {
        var b = {};
        b[a.cgti] = this.tapped;
        return b
      },
      initialize: function()
      {
        this.listenTo(this.rootView, "hpCheck", this.changeDamage);
        this.listenTo(this.rootView, "removeView", this.removeView)
      },
      render: function()
      {
        console.log("charaModel:", this.model);
        this.$el.html(this.template(
        {
          model: this.model,
          hp: this.model.remainHp,
          damage: this.model.damage,
          memoria: this.model.memoriaAdd,
          mp1: this.model.mp ? this.model.mp : 0,
          mp2: this.model.dp ? this.model.dp : 0,
          isRetire: this.model.retired
        }));
        return this
      },
      changeDamage: function(b)
      {
        var c = a.storage.userCharaList.findWhere(
          {
            charaId: this.model.charaId
          }).toJSON(),
          d = a.getTargetComposeAttribute(
          {
            attributeId: c.chara.attributeId
          });
        this.model.damage = c.damage ? c.damage : 0;
        (this.model.retired = c.retired) ? (this.model.memoriaAdd = 0, this.model.remainHp = 0) : (d = this.model.hp + c.addendHp + this.model.memoriaHp + d.composed.HP, c = Math.ceil(((d - c.damage) / d * 1E4 | 0) / 100), this.model.memoriaAdd = Math.ceil((this.model.memoriaHp / d * 1E4 | 0) / 100) / 100 * c, this.model.remainHp = Math.max(c - this.model.memoriaAdd, 1));
        this.render();
        b && a.g_popup_instance && a.g_popup_instance.popupView.close()
      },
      tapped: function(b)
      {
        b.preventDefault();
        this.rootView.cureFlg && !a.isScrolled() && (e.startSe(1002), b = this.model.chara.name, this.model.chara.title && (b += " (" + this.model.chara.title + ")"), !1 === this.model.retired && 0 === this.model.damage ? new a.PopupClass(
        {
          title: "魔法少女回复",
          content: "<span class='cureName'>" + b + "</span>的HP已满。",
          exClass: "curePop",
          popupType: "typeA",
          closeBtnText: "OK"
        }) : this.curePop(b))
      },
      curePop: function(b)
      {
        var c = this,
          d = function()
          {
            c.changeDamage(!0);
            e.getBaseData(a.getNativeObj());
            setTimeout(function()
            {
              e.startSe(3201)
            }, 250)
          },
          h = m.template($("#curePop").text());
        new a.PopupClass(
        {
          title: "魔法少女回复",
          content: h(
          {
            name: b,
            model: this.rootView.userEventDungeon
          }),
          exClass: "curePopEx",
          popupType: "typeA",
          closeBtnText: "取消",
          decideBtnText: "回复",
          decideBtnEvent: function(b)
          {
            b.preventDefault();
            a.isScrolled() || (console.log("cure charaId:", c.model.charaId), k.ajaxPost(a.linkList.dungeonCure,
            {
              charaId: c.model.charaId
            }, function(b)
            {
              a.responseSetStorage(b);
              b.userEventDungeon && (a.userEventDungeon = b.userEventDungeon);
              c.rootView.userEventDungeon.cureRemain--;
              c.rootView.cureCount();
              0 === c.rootView.userEventDungeon.cureRemain && c.rootView.cureCancel();
              d()
            }))
          }
        })
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    D = function()
    {
      var b = !1,
        c = a.storage.userDeckList.findWhere(
        {
          deckType: l.userEventDungeon.selectedDeckType
        }).toJSON();
      u = [];
      for (var d = 1; 8 > d; d++)
      {
        var e = c["questPositionId" + d];
        if (e)
        {
          for (var f = a.storage.userCardListEx.findWhere(
            {
              userCardId: c["userCardId" + d]
            }).toJSON(), g = a.storage.userCharaList.findWhere(
            {
              charaId: f.charaId
            }).toJSON(), k = a.getTargetComposeAttribute(
            {
              attributeId: g.chara.attributeId
            }), p = "userPieceId0" + d, y = [], n = 1; 5 > n; n++)
            if (c[p + n])
            {
              var r = a.storage.userPieceList.findWhere(
              {
                id: c[p + n]
              }).toJSON();
              y.push(r)
            } f.equipedMemoria = y;
          f.memoriaHp = 0;
          0 < f.equipedMemoria.length && m.each(f.equipedMemoria, function(a, b)
          {
            f.memoriaHp += a.hp
          });
          g.retired ? (f.memoriaAdd = 0, f.remainHp = 0) : (g.damage || (g.damage = 0), b = f.hp + g.addendHp + f.memoriaHp + k.composed.HP, g = Math.ceil(((b - g.damage) / b * 1E4 | 0) / 100), f.memoriaAdd = Math.ceil((f.memoriaHp / b * 1E4 | 0) / 100) / 100 * g, f.remainHp = Math.max(g - f.memoriaAdd, 1), b = !0);
          u.push(
          {
            position: e,
            card: f
          })
        }
      }
      return b
    },
    x = function(b, c)
    {
      for (var d = [], h = "END" !== c ? "touches" : "changedTouches", f = 0; f < b.originalEvent[h].length; f++)
      {
        var g = b.originalEvent[h][f].identifier;
        0 > g && (g = -g);
        d[f] = {
          identifier: g,
          clientX: 1024 === a.displayWidth ? b.originalEvent[h][f].clientX : 1024 * b.originalEvent[h][f].clientX / 1280,
          clientY: 1024 === a.displayWidth ? b.originalEvent[h][f].clientY : 1024 * b.originalEvent[h][f].clientY / 1280
        }
      }
      switch (c)
      {
        case "START":
          e.callTouchesBegin(d);
          break;
        case "MOVE":
          e.callTouchesMove(d);
          break;
        case "END":
          e.callTouchesEnd(d)
      }
    },
    C = function(b)
    {
      a.acpTimeCure && (clearInterval(a.acpTimeCure), a.acpTimeCure = null);
      var c = null;
      b.userQuestBattleResultList[0] && b.userQuestBattleResultList[0].questBattle && b.userQuestBattleResultList[0].questBattle.sectionId && (c = {
        resultUrl: "/magica/index.html#/QuestResult",
        retireUrl: "/magica/index.html#/EventDungeonMap"
      });
      e.setWebView(!1);
      e.startQuest(b.userQuestBattleResultList[0].id, c)
    },
    E = function(b)
    {
      console.log("endStoryCheck", b.clearStoryId);
      if (b.clearStoryId)
      {
        var c = a.storage.userQuestAdventureList.findWhere(
        {
          adventureId: b.clearStoryId
        });
        console.log("storyCheck", c);
        if (!c)
        {
          a.androidKeyStop = !0;
          c = function()
          {
            e.changeBg("web_black.jpg");
            $("#commandDiv").on("nativeCallback", function(c, h)
            {
              $("#commandDiv").off();
              h && h.isSkipped && (c = {}, c.adventureId = String(b.clearStoryId), k.ajaxPost(a.linkList.adventureSkip, c, function(b)
              {
                a.responseSetStorage(b)
              }));
              a.ready.target.className = "show";
              e.setWebView(!0);
              a.androidKeyStop = !1;
              a.dungeonEnd = "CLEAR";
              a.dungeonReshow = null;
              a.historyArr = ["MyPage", "EventDungeonTop"];
              location.href = "#/EventDungeonTop"
            });
            k.ajaxPost(a.linkList.userQuestAdventureRegist,
            {
              adventureId: String(b.clearStoryId)
            }, function(c)
            {
              "error" !== c.resultCode && (a.responseSetStorage(c), e.stopBgm(), e.stopSe(), setTimeout(function()
              {
                e.setWebView(!1);
                e.startStory(String(b.clearStoryId))
              }, 500))
            })
          };
          if (!window.isBrowser)
          {
            c();
            return
          }
          k.ajaxPost(a.linkList.userQuestAdventureRegist,
          {
            adventureId: String(b.clearStoryId)
          }, function(b)
          {
            "error" !== b.resultCode && a.responseSetStorage(b)
          })
        }
      }
      a.androidKeyStop = !1;
      a.dungeonEnd = "CLEAR";
      a.dungeonReshow = null;
      a.historyArr = ["MyPage", "EventDungeonTop"];
      location.href = "#/EventDungeonTop"
    },
    F = function()
    {
      a.setStyle(A);
      l = k.getPageJson();
      a.setGlobalView();
      p = m.findWhere(l.userEventDungeonPointList,
      {
        pointId: l.userEventDungeon.currentPointId
      });
      console.log("init currentPoint:", p);
      if ("END" === p.point.type) k.ajaxPost(a.linkList.dungeonEnd,
      {}, function(b)
      {
        a.responseSetStorage(b);
        console.log("finishFunc:", p.point);
        E(p.point)
      });
      else if (B.createCardList(), D())
      {
        m.findWhere(l.eventList,
        {
          eventType: "DUNGEON"
        });
        var b = l.userEventDungeonArea,
          c = b.area.width,
          d = b.area.height,
          h = {
            mapId: m.findWhere(l.userSectionList,
            {
              sectionId: b.area.sectionId
            }).section.areaMapId,
            pointList: l.pointList,
            mapWidth: c,
            mapHeight: d
          },
          f = b.area.areaBgmId,
          g = "bg_adv_" + b.area.orgBackground + ".jpg",
          q = "START" === p.point.type ? b.area.startStoryId : p.point.clearStoryId ? p.point.clearStoryId : !1;
        if (q)
          if (a.storage.userQuestAdventureList.findWhere(
            {
              adventureId: q
            })) window.isDebug && window.isBrowser && (n = new r), $("#commandDiv").on("nativeCallback", function(a, b)
          {
            $("#commandDiv").off();
            setTimeout(function()
            {
              e.changeBg(g);
              e.startBgm(f);
              n = new r
            }, 500)
          });
          else
          {
            a.androidKeyStop = !0;
            var t = function()
            {
              $("#commandDiv").on("nativeCallback", function(b, c)
              {
                $("#commandDiv").off();
                c && c.isSkipped && (b = {}, b.adventureId = String(q), k.ajaxPost(a.linkList.adventureSkip, b, function(b)
                {
                  a.responseSetStorage(b)
                }));
                a.ready.target.className = "show";
                e.setWebView();
                $("#commandDiv").on("nativeCallback", function(a, b)
                {
                  $("#commandDiv").off();
                  setTimeout(function()
                  {
                    e.changeBg(g);
                    e.startBgm(f);
                    n = new r
                  }, 500)
                });
                a.androidKeyStop = !1;
                e.pushEventDungeon(h)
              });
              k.ajaxPost(a.linkList.userQuestAdventureRegist,
              {
                adventureId: String(q)
              }, function(b)
              {
                "error" !== b.resultCode && (a.responseSetStorage(b), e.stopBgm(), e.stopSe(), setTimeout(function()
                {
                  e.setWebView(!1);
                  e.startStory(String(q))
                }, 500))
              })
            };
            if (!window.isBrowser)
            {
              a.ready.target.classList.contains("preNativeFadeIn") ? (e.changeBg("web_black.jpg"), t()) : ($(a.ready.target).on("webkitAnimationEnd", function()
              {
                $(a.ready.target).off("webkitAnimationEnd");
                $(a.ready.target).on("webkitAnimationEnd", function(b)
                {
                  "readyFadeOut" == b.originalEvent.animationName && (a.ready.target.className = "")
                });
                e.changeBg("web_black.jpg");
                t()
              }), a.addClass(a.ready.target, "preNativeFadeIn"));
              return
            }
            if (!window.isBrowser) return;
            k.ajaxPost(a.linkList.userQuestAdventureRegist,
            {
              adventureId: String(q)
            }, function(b)
            {
              "error" !== b.resultCode && a.responseSetStorage(b)
            });
            a.androidKeyStop = !1;
            window.isDebug && window.isBrowser && (n = new r)
          }
        else window.isDebug && window.isBrowser && (n = new r), $("#commandDiv").on("nativeCallback", function(a, b)
        {
          $("#commandDiv").off();
          e.changeBg(g);
          e.startBgm(f);
          n = new r
        });
        e.pushEventDungeon(h)
      }
      else k.ajaxPost(a.linkList.dungeonEnd,
      {}, function(b)
      {
        a.responseSetStorage(b);
        a.dungeonEnd = "FAILED";
        a.historyArr = ["MyPage", "EventDungeonTop"];
        location.href = "#/EventDungeonTop"
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
      id: "userItemList"
    },
    {
      id: "userStatusList"
    },
    {
      id: "userDeckList"
    },
    {
      id: "userCharaList"
    },
    {
      id: "userCardList"
    },
    {
      id: "userPieceList"
    },
    {
      id: "userPieceSetList"
    },
    {
      id: "userLive2dList"
    },
    {
      id: "userDoppelList"
    },
    {
      id: "userSectionList"
    },
    {
      id: "userQuestBattleList"
    },
    {
      id: "userChapterList"
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
      F()
    },
    remove: function(b)
    {
      e.hideEventDungeon();
      n && (n.trigger("removeView"), n.remove());
      a.removeClass(a.doc.getElementById("globalMenuContainer"), "hide");
      u = p = l = null;
      b()
    }
  }
});
