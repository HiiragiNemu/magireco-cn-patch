define("underscore backbone backboneCommon ajaxControl command cardUtil text!template/event/training/EventTrainingCharaSelect.html text!css/event/training/EventTrainingCharaSelect.css js/view/chara/CharaListView js/card/CardPopup".split(" "), function(f, p, b, n, h, y, z, A, B, t)
{
  var u = p.Model.extend(),
    g, l, c, m, k, v = ["navi_01", "navi_02", "navi_03"],
    C = p.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " #helpBtn"] = this.helpPopup;
        a[b.cgti + " #decideBtn"] = this.charaSet;
        return a
      },
      initialize: function(a)
      {
        this.charaViews = [];
        this.template = f.template(z);
        this.createDom()
      },
      render: function()
      {
        g.eventMaster = l;
        g.eventTraining = m;
        g.eventTraining.message = g.eventTraining.message.replace(/＠/g, "<br>");
        this.$el.html(this.template(g));
        return this
      },
      visualChange: function()
      {
        console.log("visualChange");
        f.each(this.charaViews, function(a, d)
        {
          var e = a.model.toJSON() ||
          {};
          console.log(e);
          e.img = b.imgData;
          e.charaNum = d + 1;
          e.card && e.displayCardId && (d = b.storage.userCardListEx.findWhere(
          {
            charaId: e.charaId
          }), e.displayCardId = d.toJSON().displayCardId);
          a.model.clear(
          {
            silent: !0
          });
          a.model.set(e)
        })
      },
      createDom: function()
      {
        b.setGlobalView();
        b.content.append(this.render().el);
        this.createView();
        h.getBaseData(b.getNativeObj());
        w();
        b.ready.hide()
      },
      createView: function()
      {
        x();
        q.prototype.template = f.template($("#CharaPartsTemp").text());
        q.prototype.parentView = this;
        this.charaViews = [];
        for (var a = 0, d = b.doc.createDocumentFragment(); a < m.charaCount;)
        {
          var e = k[a] ||
          {};
          e.img = b.imgData;
          e.charaNum = a + 1;
          e = new q(
          {
            model: new u(e)
          });
          this.charaViews.push(e);
          d.appendChild(e.render().el);
          a = a + 1 | 0
        }
        b.doc.querySelector("#charaSelectWrap .charaOuter").appendChild(d)
      },
      helpPopup: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (console.log("ssss"), b.eventFirstNavi(v, l.eventId, "training", function() {}, !0))
      },
      charaSet: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled() && !a.currentTarget.classList.contains("off"))
        {
          b.addClass(a.currentTarget, "off");
          var d = {
            charaIdList: []
          };
          f.each(b.doc.querySelectorAll(".charaWrap"), function(a, b)
          {
            d.charaIdList.push(Number(a.querySelector(".prm_charaId").innerText))
          });
          n.ajaxPost(b.linkList.trainingCharaSet, d, function(a)
          {
            b.responseSetStorage(a);
            location.href = "#/EventTrainingTop"
          })
        }
      },
      afterMovieFunc: function()
      {
        w()
      }
    }),
    q = p.View.extend(
    {
      events: function()
      {
        var a = {};
        a["touchstart .tapArea"] = this.popupTimeStart;
        a[b.cgti + " .tapArea"] = this.charaListOpen;
        return a
      },
      initialize: function(a)
      {
        this.listenTo(this.model, "change", this.changeRender);
        this.listenTo(this.parentView, "removeView", this.removeView)
      },
      className: function()
      {
        var a = "charaWrap",
          b = this.model.toJSON(),
          a = a + (" chara" + b.charaNum);
        return a = b.eventCharaFlag ? a + " eventChara on" : b.card ? a + " on" : a + " off"
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model.toJSON()
        }));
        return this
      },
      changeRender: function()
      {
        this.$el.html(this.template(
        {
          model: this.model.toJSON()
        }));
        this.el.className = this.className();
        h.getBaseData(b.getNativeObj());
        return this
      },
      popupTimeStart: function(a)
      {
        !this.model.toJSON().eventCharaFlag && this.model.toJSON().card && t.cardDetailPopup(a, this.model.toJSON())
      },
      charaListOpen: function(a)
      {
        a.preventDefault();
        t.popupTimerStop(a);
        if (!b.isScrolled())
          if (c.selectView) b.removeClass(b.doc.querySelector("#charaListWrap"), "open"), b.removeClass(b.doc.querySelector(".charaWrap.select"), "select"), c.selectView = null, r();
          else if (this.model.toJSON().eventCharaFlag) new b.PopupClass(
        {
          title: "特训对象 不可更改",
          content: "无法更改活动指定的特训对象魔法少女。",
          closeBtnText: "关闭"
        });
        else
        {
          var d = "";
          f.each(b.doc.querySelectorAll(".charaWrap"), function(a, b)
          {
            (a = a.querySelector(".prm_charaId")) && (d += 1 == b ? "," + a.innerText : a.innerText)
          });
          x(d);
          var e = this.model.toJSON();
          D(e);
          b.addClass(a.currentTarget.parentNode, "select");
          b.addClass(b.doc.querySelector("#charaListWrap"), "open");
          c.selectView = this
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    r = function()
    {
      b.doc.querySelector(".charaWrap.off") ? b.addClass(b.doc.querySelector("#decideBtn"), "off") : b.removeClass(b.doc.querySelector("#decideBtn"), "off")
    },
    D = function(a)
    {
      b.removeClass(b.doc.querySelector("#charaListElms .select"), "select");
      b.removeClass(b.doc.querySelector("#charaListElms .remove"), "remove");
      f.each([].slice.call(b.doc.querySelectorAll("#charaListElms .trainingSelect")), function(a)
      {
        b.removeClass(a, "trainingSelect")
      });
      f.each([].slice.call(b.doc.querySelectorAll("#charaListElms .eventChara")), function(a)
      {
        b.removeClass(a, "eventChara")
      });
      f.each(k, function(d)
      {
        d.charaId && (a && a.charaId == d.charaId ? (b.addClass(b.doc.querySelector(".charaId" + d.charaId), "remove"), b.addClass(b.doc.querySelector(".charaId" + d.charaId), "select")) : b.addClass(b.doc.querySelector(".charaId" + d.charaId), "trainingSelect"), b.addClass(b.doc.querySelector(".charaId" + d.charaId), "eventChara"))
      })
    },
    x = function(a)
    {
      k = [];
      m.charaIdDefaultCardIdMap && f.each(m.charaIdDefaultCardIdMap, function(a, b)
      {
        k.push(
        {
          eventCharaFlag: !0,
          displayCardId: a,
          charaId: Number(b)
        })
      });
      a ? (a = a.split(","), f.each(a, function(a, c)
      {
        f.filter(k, function(b)
        {
          return b && b.charaId == a
        }).length || (c = b.storage.userCardListEx.findWhere(
        {
          charaId: Number(a)
        })) && k.push(c.toJSON())
      })) : 2 > k.length && g.gameUser.eventTrainingId && g.gameUser.eventTrainingId == l.eventId && g.gameUser.trainingSelectedCharaNos && (a = g.gameUser.trainingSelectedCharaNos.split(","), f.each(a, function(a, c)
      {
        f.filter(k, function(b)
        {
          return b && b.charaId == a
        }).length || (c = b.storage.userCardListEx.findWhere(
        {
          charaId: Number(a)
        })) && k.push(c.toJSON())
      }))
    },
    w = function()
    {
      if (m)
      {
        h.endL2d();
        var a = {};
        a.key = m.live2dDetail;
        a.type = 1;
        a.id = "0";
        a.x = 246;
        a.y = 1024 === b.displayWidth ? Math.floor(b.doc.getElementsByTagName("body")[0].offsetHeight / 2) : Math.ceil(b.shortSize / 2);
        h.startL2d(a)
      }
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
      id: "userCharaEnhancementCellList"
    },
    {
      id: "userCharaAtbEnhancementCellList"
    },
    {
      id: "userPieceList"
    },
    {
      id: "userPieceSetList"
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
      n.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      b.setStyle(A);
      y.createCardList();
      g = n.getPageJson();
      c = new C;
      var a = "EventTraining_" + l.eventId;
      localStorage.getItem(a) || (localStorage.setItem(a, !0), b.eventFirstNavi(v, l.eventId, "training"));
      r();
      c.charaListView = new B(
      {
        model: new u,
        collection: b.storage.userCardListEx
      });
      b.content.append(c.charaListView.render().el);
      c.charaListView.cardSort.multiSort();
      b.scrollSetX("charaListScrollWrap", "list");
      h.getBaseData(b.getNativeObj())
    },
    startCommand: function()
    {
      g = n.getPageJson();
      l = f.findWhere(g.eventList,
      {
        eventType: "TRAINING"
      });
      m = g.eventTraining;
      h.changeBg(l.viewParameterMap.BG_IMG + ".ExportJson");
      h.startBgm(l.viewParameterMap.BGM)
    },
    removeCommand: function()
    {
      h.endL2d()
    },
    charaSelect: function(a, d)
    {
      d || a.el.classList.contains("trainingSelect") || (c.selectView.model.toJSON() && c.selectView.model.toJSON().charaId && c.selectView.model.toJSON().charaId == a.model.toJSON().charaId ? (a = f.clone(c.selectView.model.toJSON()), c.selectView.model.clear(
      {
        silent: !0
      }), c.selectView.model.set(
      {
        charaNum: a.charaNum,
        img: a.img
      })) : c.selectView.model.set(a.model.toJSON()), b.removeClass(b.doc.querySelector("#charaListWrap"), "open"), c.selectView = null, r())
    },
    charaDetailClose: function()
    {
      c && c.visualChange()
    },
    beforeMovieStart: function()
    {
      c && h.endL2d()
    },
    afterMovieEnd: function()
    {
      c && c.afterMovieFunc()
    },
    remove: function(a)
    {
      c && (c.trigger("removeView"), c.remove(), c.charaListView.trigger("remove"), c.charaListView.remove());
      a()
    }
  }
});
