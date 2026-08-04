define("underscore backbone backboneCommon ajaxControl command text!template/test/BackdoorQuestList.html text!css/test/BackdoorQuestList.css".split(" "), function(l, g, b, f, w, t, u)
{
  g.Model.extend();
  var n, q, h, v = g.View.extend(
    {
      events: function()
      {
        var c = {};
        c[b.cgti + " .allBtn"] = this.allBtn;
        return c
      },
      initialize: function(b)
      {
        this.prm = {};
        this.template = l.template(t);
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template(f.getPageJson()));
        return this
      },
      createDom: function()
      {
        b.setGlobalView();
        b.content.append(this.render().el);
        this.createQuestBtn();
        b.ready.hide()
      },
      allBtn: function(c)
      {
        c.preventDefault();
        b.isScrolled() || (h = c.currentTarget.dataset.target, b.tapBlock(!0), p())
      },
      createQuestBtn: function()
      {
        var c = b.storage.userQuestBattleList.toJSON();
        c.sort(function(a, b)
        {
          if ("NORMAL" === a.questBattle.questBattleType && "HARD" === b.questBattle.questBattleType) return -1;
          if ("HARD" === a.questBattle.questBattleType && "NORMAL" === b.questBattle.questBattleType) return 1;
          var d = parseInt(String(a.questBattleId).substr(0, 6)),
            e = parseInt(String(b.questBattleId).substr(0, 6));
          return d < e ? -1 : d > e ? 1 : a.questBattle.sectionIndex < b.questBattle.sectionIndex ? -1 : a.questBattle.sectionIndex > b.questBattle.sectionIndex ? 1 : 0
        });
        k.prototype.rootView = this;
        k.prototype.template = l.template($("#QuestBtn").text());
        var f = b.doc.createDocumentFragment();
        l.each(c, function(a, d)
        {
          if (199999 >= a.questBattle.sectionId && !a.cleared || 299999 >= a.questBattle.sectionId && !a.cleared)
          {
            if (d = b.storage.userSectionList.findWhere(
              {
                sectionId: a.questBattle.sectionId
              })) a.sectionModel = d.toJSON();
            d = "";
            var c = "btn ",
              e = String(a.questBattle.sectionId).substr(3, 1);
            if ("MAIN" == a.sectionModel.section.questType)
              if (104201 <= a.questBattle.sectionId) d += "S0 ", c += "b_scene0", e = String(parseInt(e) - 1);
              else if (103401 == a.questBattle.sectionId || 103500 <= a.questBattle.sectionId) switch (d += "PH ", c += "b_puellaHistoria", a.questBattle.sectionId)
            {
              case 103401:
                e = "現代神浜編";
                break;
              case 103501:
              case 103502:
                e = "神浜の戦神子編";
                break;
              case 103601:
              case 103602:
                e = "アレクサンドリアの蜃気楼編";
                break;
              case 103701:
              case 103702:
                e = "ヴィークのワルキューレ編";
                break;
              case 103801:
              case 103802:
                e = "チベットのラクシャーシー編";
                break;
              case 103901:
              case 103902:
                e = "邪馬台国の跡目編";
                break;
              case 104001:
              case 104002:
              case 104003:
                e = "パクス・ロマーナの恋人編"
            }
            else 103E3 <= a.questBattle.sectionId ? (d += "M2 ", c += "b_blue", e = String(parseInt(e) - 1 + 10)) : 102100 <= a.questBattle.sectionId ? (d += "M2 ", c += "b_blue", e = String(parseInt(e) - 1)) : 102E3 <= a.questBattle.sectionId ? (d += "M1 ", c += "b_purple", e = 10) : (d += "M1 ", c += "b_purple");
            else 207101 <= a.questBattle.sectionId ? (d += "S2 ", c += "b_pale") : (d += "S1 ", c += "b_green");
            e = "0" === e ? "序" : e;
            e = "PH " == d ? e + " Battle" + String(a.questBattle.sectionIndex) : e + "章" + String(a.questBattle.sectionId).substr(4, 2) + "話 Battle" + String(a.questBattle.sectionIndex);
            a.title = d + e;
            "HARD" == a.questBattle.questBattleType && (a.questType = a.questBattle.questBattleType);
            a.btnClass = c;
            console.log(a);
            d = new k(
            {
              model: a
            });
            f.appendChild(d.render().el)
          }
          if (!a.cleared && 3E5 <= a.questBattle.sectionId && 399999 >= a.questBattle.sectionId)
          {
            if (d = b.storage.userSectionList.findWhere(
              {
                sectionId: a.questBattle.sectionId
              })) a.sectionModel = d.toJSON();
            a.sectionModel.canPlay && (d = a.sectionModel.section.charaName, e = String(a.questBattleId).substr(5, 1) + "-" + String(a.questBattleId).substr(6, 1), a.title = d + " " + e, a.btnClass = "btn b_pink", d = new k(
            {
              model: a
            }), f.appendChild(d.render().el))
          }!a.cleared && 5E5 <= a.questBattle.sectionId && 599999 >= a.questBattle.sectionId && (d = b.storage.userSectionList.findWhere(
          {
            sectionId: a.questBattle.sectionId
          })) && (a.sectionModel = d.toJSON(), a.sectionModel.canPlay && (a.questType = a.sectionModel.section.questType, d = new k(
          {
            model: a
          }), f.appendChild(d.render().el)))
        });
        b.doc.querySelector("#scrollOuter .scrollInner").appendChild(f);
        b.scrollSet("scrollOuter", "scrollInner")
      }
    }),
    k = g.View.extend(
    {
      events: function()
      {
        var c = {};
        c[b.cgti] = this.questClear;
        return c
      },
      initialize: function()
      {
        this.listenTo(this.rootView, "remove", this.removeView);
        this.model.btnClass || (this.model.btnClass = "btn b_white")
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        this.$el.addClass(this.model.btnClass);
        return this
      },
      questClear: function(c)
      {
        c.preventDefault();
        if (!b.isScrolled())
        {
          var k = this;
          if (this.model.questBattle.onlyCharaIds || this.model.questBattle.containCharaIds) new b.PopupClass(
          {
            title: "关卡确认",
            content: "条件が設定されているクエストです",
            decideBtnText: "前往关卡"
          }, null, function()
          {
            $(".decideBtn").on(b.cgti, function(a)
            {
              a.preventDefault();
              b.isScrolled() || (location.href = "#/MainQuest", location.leroad())
            })
          }), b.tapBlock(!1);
          else
          {
            if (this.model.questBattle.useItemId)
            {
              var a = b.storage.userItemList.findWhere(
              {
                itemId: this.model.questBattle.useItemId
              });
              c = a ? a.get("quantity") : 0;
              var d = this.model.questBattle.needItemNum - c,
                g = null;
              c = function()
              {
                f.ajaxPost(b.linkList.backdoorItemSend,
                {
                  itemCode: a.toJSON().item.itemCode,
                  quantity: d
                }, function(a)
                {
                  b.responseSetStorage(a);
                  g && g.popupView.close();
                  h ? p() : b.tapBlock(!1)
                })
              };
              if (0 < d)
              {
                g = new b.PopupClass(
                {
                  title: "关卡确认",
                  content: "「" + this.model.questBattle.useItem.name + "」が <span class='c_red'>" + d + "</span> 不足しています",
                  decideBtnText: "必要分補充する",
                  decideBtnEvent: c,
                  closeBtnText: "关闭"
                });
                b.tapBlock(!1);
                return
              }
            }
            else if (b.globalMenuView.getUserStatus().ACP < (this.model.questBattle.ap ? this.model.questBattle.ap : this.model.sectionModel.section.ap))
            {
              var e = function()
              {
                f.ajaxPost(b.linkList.useItem,
                {
                  itemId: "CURE_AP",
                  num: 1
                }, function(a)
                {
                  b.responseSetStorage(a);
                  h ? p() : b.tapBlock(!1)
                })
              };
              c = (c = b.storage.userItemList.findWhere(
              {
                itemId: "CURE_AP"
              })) ? c.get("quantity") : 0;
              0 !== c ? e() : f.ajaxPost(b.linkList.backdoorItemSend,
              {
                itemCode: "CURE_AP",
                quantity: 999
              }, function(a)
              {
                b.responseSetStorage(a);
                e()
              });
              return
            }
            var m = {};
            m.questBattleId = this.model.questBattleId;
            m.deckType = 11;
            var r = null;
            l.each(q.userDeckList, function(a, b)
            {
              11 == a.deckType && (r = a)
            });
            l.each(r, function(a, b)
            {
              -1 != b.indexOf("questPositionId") && (m[b] = a); - 1 != b.indexOf("userCardId") && (m[b] = a)
            });
            f.ajaxPost(b.linkList.questStart, m, function(a)
            {
              setTimeout(function()
              {
                var c = {};
                c.userQuestBattleResultId = a.userQuestBattleResultList[0].id;
                f.ajaxPost(b.linkList.questNativeGet, c, function(a)
                {
                  b.responseSetStorage(a.webData);
                  setTimeout(function()
                  {
                    c.result = "SUCCESSFUL";
                    c.continueNum = 0;
                    c.totalTurn = 3;
                    c.rateHp = 100;
                    c.deadNum = 0;
                    c.chargeNum = 10;
                    c.skillNum = 10;
                    c.connectNum = 10;
                    c.lastAttackCardId = 10011;
                    c.waveList = [
                    {
                      totalDamage: 100
                    }];
                    f.ajaxPost(b.linkList.questNativeResultSend, c, function(a)
                    {
                      b.responseSetStorage(a);
                      a.userQuestBattleList && l.findWhere(a.userQuestBattleList,
                      {
                        cleared: !1
                      }) && (n.trigger("remove"), n.createQuestBtn());
                      k.removeView();
                      h ? p() : b.tapBlock(!1);
                      b.scrollRefresh()
                    })
                  }, 100)
                })
              }, 100)
            })
          }
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    p = function()
    {
      var c = b.doc.getElementById("scrollOuter").getElementsByClassName("b_" + h);
      c && c[0] ? $(c[0]).trigger(b.cgti) : (h = null, b.tapBlock(!1))
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
      id: "userDeckList"
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
      id: "userFollowList"
    },
    {
      id: "pieceList"
    }],
    fetch: function()
    {
      f.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      window.isDebug && (q = f.getPageJson(), b.setStyle(u), n = new v, console.log(q.userQuestBattleList))
    },
    remove: function(b)
    {
      h = null;
      n.remove();
      b()
    }
  }
});
