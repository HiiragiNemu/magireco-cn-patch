define("underscore backbone backboneCommon ajaxControl command text!template/event/arenaMission/EventArenaMissionConfirm.html".split(" "), function(g, l, b, k, h, m)
{
  return l.View.extend(
  {
    tagName: "div",
    id: "confirmPopWrap",
    events: function()
    {
      var a = {};
      a[b.cgti + " #battleStartBtn"] = this.battleStart;
      a[b.cgti + " .closeBtn"] = this.removeView;
      a[b.cgti + " .controller .item"] = this.buffItemSet;
      a[b.cgti + " #itemUseWrap .cancelBtn"] = this.buffItemReset;
      return a
    },
    buffItemSet: function(a)
    {
      a.preventDefault();
      if (!(b.isScrolled() || 3 <= this.useBuffItem.length))
      {
        h.startSe(1002);
        a = a.currentTarget;
        var d = a.dataset.id,
          f = a.querySelector(".itemNum .quantity").textContent | 0,
          e = a.querySelector(".selectNum"),
          c = e.textContent | 0;
        f >= c + 1 && (c++, e.textContent = c, a.classList.contains("select") || b.addClass(a, "select"), this.useBuffItem.push(d));
        this.effectViewUpdate()
      }
    },
    effectViewUpdate: function()
    {
      var a = b.doc.querySelector(".effectView"),
        d = {
          hp: 0,
          atk: 0,
          def: 0
        },
        f = [0, 20, 50, 100];
      g.each(this.useBuffItem, function(e, c)
      {
        d[e] += 1;
        c = a.querySelector("." + e);
        var n = c.querySelector(".per");
        c.classList.contains("show") || b.addClass(c, "show");
        n.textContent = f[d[e]]
      })
    },
    getUseBuffItemNum: function()
    {
      var b = {
        hp: 0,
        atk: 0,
        def: 0
      };
      g.each(this.useBuffItem, function(a, f)
      {
        b[a] += 1
      });
      return b
    },
    buffItemReset: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        h.startSe(1008);
        var d = b.doc.querySelector(".effectView");
        g.each(["hp", "atk", "def"], function(a, e)
        {
          a = d.querySelector("." + a);
          e = a.querySelector(".per");
          b.removeClass(a, "show");
          e.textContent = 0
        });
        a = b.doc.querySelector(".controller").querySelectorAll(".item");
        g.each(a, function(a, e)
        {
          b.removeClass(a, "select");
          a.querySelector(".selectNum").textContent = 0
        });
        this.useBuffItem = []
      }
    },
    initialize: function()
    {
      this.useBuffItem = [];
      this.listenTo(this.parentView.rootView, "removeView", this.removeView);
      this.template = g.template(m)
    },
    render: function()
    {
      var a = k.getPageJson(),
        d = a.eventList.filter(function(b, a)
        {
          if ("ARENAMISSION" == b.eventType) return !0
        }),
        f = {};
      g.each(d[0].parameterMap, function(a, c)
      {
        c = c.split("UP_ITEM_ID")[0].toLowerCase();
        var e = b.storage.userItemList.findWhere(
          {
            itemId: a
          }),
          d = {};
        d.itemId = a;
        d.quantity = e ? e.toJSON().quantity : 0;
        f[c] = d
      }, this);
      this.$el.html(this.template(
      {
        model: this.model,
        pageModel: a,
        eventMaster: d[0],
        buffItem: f,
        userEventArenaMission: b.userEventArenaMission,
        eventArenaMissionStage: b.eventArenaMissionStage
      }));
      b.addClass(b.doc.getElementById("curtain"), "show");
      return this
    },
    battleStart: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled() && !this.started)
      {
        var d = this;
        a = (Date.parse(new Date) / 1E3 | 0) - this.parentView.rootView.accessClientTime;
        if (this.parentView.rootView.accessServerTime + a >= this.parentView.rootView.matchExpiredAt) new b.PopupClass(
        {
          title: "更换对手",
          content: "因时间经过,对战对手已变更<br>返回活动首页",
          decideBtnText: "前往活动页面",
          canClose: !1,
          popupType: "typeC"
        }, null, function()
        {
          $(".decideBtn").on(b.cgti, function()
          {
            d.removeView();
            $(".decideBtn").off(b.cgti);
            location.href = "#/EventArenaMissionTop"
          })
        });
        else if (1 > b.storage.userStatusList.findWhere(
          {
            statusId: "BTP"
          }).toJSON().point)
        {
          new b.PopupClass(
          {
            title: "错误",
            content: "BP 不足。",
            closeBtnText: "关闭",
            decideBtnText: "回复"
          });
          var f = function(a)
          {
            a.preventDefault();
            b.isScrolled() || (b.doc.removeEventListener(b.cgti, f), d.parentView.rootView.infoView.bpCurePop(a))
          };
          b.doc.getElementById("popupArea").getElementsByClassName("decideBtn")[0].addEventListener(b.cgti, f)
        }
        else this.started = !0, this.parentView.rootView.infoView.timerStop(), a = this.getUseBuffItemNum(), this.startJson = {
          stageId: String(b.eventArenaMissionStage.stageId),
          opponentUserId: this.model.userId,
          hpUpItemNum: a.hp,
          attackUpItemNum: a.atk,
          defenseUpItemNum: a.def
        }, b.battleEnemy = this.model.userId, window.isBrowser ? (b.arenaJson = this.startJson, h.sendCommand("EventArenaMissionStub," + JSON.stringify(this.startJson)), d.removeView()) : k.ajaxPost(b.linkList.arenaMissionStart, this.startJson, function(a)
        {
          b.responseSetStorage(a);
          b.acpTimeCure && (clearInterval(b.acpTimeCure), b.acpTimeCure = null);
          $(b.ready.target).on("webkitAnimationEnd", function()
          {
            h.changeBg("web_black.jpg");
            $(b.ready.target).off("webkitAnimationEnd");
            $(b.ready.target).on("webkitAnimationEnd", function(a)
            {
              "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
            });
            var c = {};
            c.questId = a.userQuestBattleResultList[0].id;
            c.replayId = a.userQuestBattleResultList[0].replayId;
            c.resultUrl = "/magica/index.html#/EventArenaMissionResult";
            c.retireUrl = "/magica/index.html#/EventArenaMissionTop";
            c.tips = {
              type: 2
            };
            b.globalMenuView && b.globalMenuView.trigger("removeView");
            setTimeout(function()
            {
              h.setWebView(!1);
              $("#commandDiv").on("nativeCallback", function(a, c)
              {
                $("#commandDiv").off();
                c && c.webData && b.responseSetStorage(c.webData);
                location.href = "#/QuestBackground";
                d.removeView()
              });
              h.startArena(c)
            }, 500)
          });
          b.addClass(b.ready.target, "preNativeFadeIn")
        })
      }
    },
    removeView: function()
    {
      b.removeClass(b.doc.getElementById("curtain"), "show");
      b.arenaConfirmView = null;
      this.off();
      this.remove()
    }
  })
});
