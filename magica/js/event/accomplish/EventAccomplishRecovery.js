define("underscore backbone backboneCommon ajaxControl command text!template/event/accomplish/EventAccomplishRecovery.html text!css/event/accomplish/EventAccomplishRecovery.css cardUtil".split(" "), function(f, p, a, m, q, w, x, y)
{
  var g = null,
    h = null,
    z = p.Model.extend(),
    k, l, n, A = p.View.extend(
    {
      events: function()
      {
        var b = {};
        b["touchstart #scrollOuter"] = this.touchStart;
        b[a.cgti + " #scrollOuter"] = this.touchEnd;
        b[a.cgti + " #sortBtn"] = this.sortStart;
        b[a.cgti + " .orderBtn"] = this.sortOrder;
        return b
      },
      initialize: function(a)
      {
        this.touchFlg = !1;
        this.template = f.template(w);
        this.createDom()
      },
      render: function()
      {
        var b = m.getPageJson();
        b.eventMaster = l;
        b.userEventAccomplish = a.userEventAccomplish ||
        {
          deckType: 31,
          remainCount: 10
        };
        this.$el.html(this.template(b));
        return this
      },
      createDom: function()
      {
        a.setGlobalView();
        a.content.append(this.render().el);
        this.createView()
      },
      createView: function()
      {
        var b = this;
        r.prototype.parentView = this;
        r.prototype.template = f.template($("#charaWrapTemp").text());
        var c = 0,
          d = a.doc.createDocumentFragment();
        f.each(a.storage.userCardListEx.toJSON(), function(a)
        {
          if (a.isDeath || a.damage) a = new r(
          {
            model: new z(a)
          }), d.appendChild(a.render().el), c++
        });
        0 < c ? (a.doc.querySelector("#scrollOuter .scrollInner").appendChild(d), q.getBaseData(a.getNativeObj()), a.scrollSet("scrollOuter", "scrollInner"), a.doc.querySelector("#scrollOuter .death") && (h = setInterval(function()
        {
          g += 1E3;
          a.doc.querySelector("#scrollOuter .death") ? b.trigger("timer") : (clearInterval(h), h = null)
        }, 1E3))) : a.doc.querySelector(".recoveryCaution").style.display = "block";
        this.sortPrm = ["level", "desc"];
        t(this.sortPrm);
        a.ready.hide()
      },
      touchStart: function(a)
      {
        this.touchFlg = !0
      },
      touchEnd: function(a)
      {
        this.touchFlg = !1
      },
      sortStart: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (this.sortPrm[0] = {
          get: "level",
          level: "rank",
          rank: "atk",
          atk: "def",
          def: "hp",
          hp: "eplv",
          eplv: "rev",
          rev: "mlv",
          mlv: "mp",
          mp: "revivedAt",
          revivedAt: "get"
        } [this.sortPrm[0]], t(this.sortPrm))
      },
      sortOrder: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (this.sortPrm[1] = "asc" === this.sortPrm[1] ? "desc" : "asc", t(this.sortPrm))
      }
    }),
    r = p.View.extend(
    {
      className: function()
      {
        var a = "charaWrap";
        this.model.toJSON().isDeath && (a += " death");
        return a
      },
      events: function()
      {
        var b = {};
        b[a.cgti] = this.recoveryPop;
        return b
      },
      initialize: function(a)
      {
        this.listenTo(this.parentView, "removeView", this.removeView);
        this.listenTo(this.parentView, "timer", this.timer);
        this.listenTo(this.model, "change", this.timerRender)
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model.toJSON()
        }));
        return this
      },
      timerRender: function()
      {
        this.parentView.touchFlg || a.g_popup_instance || (this.el.querySelector(".reviveAtDisp").innerText = this.model.toJSON().reviveAtDisp)
      },
      recoveryPop: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
          if (q.startSe(1002), a.userEventAccomplish && 0 >= a.userEventAccomplish.remainCount) b = String(l.parameterMap.TERMINATION_TIME).split(""), b = b[0] + b[1] + ":" + b[2] + b[3], console.log(b), new a.PopupClass(
          {
            title: "回复确认",
            content: "今日回复次数已达上限。<br>回复次数" + b + "时更新。",
            closeBtnText: "关闭"
          });
          else if (this.el.classList.contains("comp")) new a.PopupClass(
        {
          title: "回复确认",
          content: "所选中的魔法少女已经回复完毕",
          closeBtnText: "关闭"
        });
        else
        {
          var c = this,
            d = null;
          b = "「" + this.model.toJSON().chara.name + "」要回复吗?<br>";
          this.model.toJSON().reviveAtDisp && (b += '距回复还有 <span id="popupTimer">' + this.model.toJSON().reviveAtDisp + "</span>");
          console.log(a.userEventAccomplish);
          b += "<br><br>今日回复次数：" + (a.userEventAccomplish ? a.userEventAccomplish.remainCount : 0) + "/" + l.parameterMap.CURE_COUNT + "次";
          new a.PopupClass(
          {
            title: "魔法少女回复",
            content: b,
            decideBtnText: "回复",
            closeBtnText: "取消"
          }, null, function()
          {
            c.model.toJSON().isDeath && (a.addClass(a.doc.querySelector("#popupArea .decideBtn"), "off"), d = setInterval(function()
            {
              var b = u(g, c.model.toJSON().revivedAt);
              b && a.doc.querySelector("#popupTimer") ? (a.doc.querySelector("#popupTimer") && (a.doc.querySelector("#popupTimer").innerText = b), 2 == b.split(":").length && 10 >= Number(b.split(":")[1]) ? a.addClass(a.doc.querySelector("#popupArea .decideBtn"), "off") : a.removeClass(a.doc.querySelector("#popupArea .decideBtn"), "off")) : (a.doc.querySelector("#popupTimer") && (a.doc.querySelector("#popupTimer").innerText = "0:00"), a.addClass(a.doc.querySelector("#popupArea .decideBtn"), "off"))
            }, 500));
            $("#popupArea .decideBtn").on(a.cgti, function(b)
            {
              b.preventDefault();
              if (!a.isScrolled() && !a.doc.querySelector("#popupArea .decideBtn").classList.contains("off"))
              {
                d && (clearInterval(d), d = null);
                var e = {
                  charaId: c.model.toJSON().charaId
                };
                m.ajaxPost(a.linkList.accomplishCure, e, function(b)
                {
                  console.log(b);
                  a.userEventAccomplish = b.userEventAccomplish;
                  a.userEventAccomplishCharaArr[e.charaId] = b.userEventAccomplishCharaList[0];
                  c.removeView();
                  new a.PopupClass(
                  {
                    title: "回复确认",
                    content: "回复完成",
                    closeBtnText: "关闭"
                  });
                  a.doc.querySelector(".remainNumImgWrap").innerHTML = "";
                  var d = a.doc.createDocumentFragment();
                  f.each(String(a.userEventAccomplish.remainCount).split(""), function(a)
                  {
                    var b = document.createElement("span");
                    b.className = "num num" + a;
                    d.appendChild(b)
                  });
                  a.doc.querySelector(".remainNumImgWrap").appendChild(d)
                })
              }
            })
          }, function()
          {
            d && (clearInterval(d), d = null)
          })
        }
      },
      timer: function()
      {
        var b = u(g, this.model.toJSON().revivedAt);
        if (b)
        {
          var c = f.clone(this.model.toJSON());
          c.reviveAtDisp = b;
          this.model.set(c)
        }
        else this.el.classList.contains("death") && (c = f.clone(this.model.toJSON()), c.reviveAtDisp = null, c.isDeath = !1, this.model.set(c,
        {
          silent: !0
        }), this.render(), q.getBaseData(a.getNativeObj()), a.removeClass(this.el, "death"), a.addClass(this.el, "comp"))
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    u = function(a, c)
    {
      c = (new Date(c)).getTime();
      var b = c - a,
        e = b / 36E5 | 0,
        b = b % 36E5,
        v = b / 6E4 | 0,
        b = b % 6E4 / 1E3 | 0,
        e = 0 < e ? e + ":" + ("0" + v).slice(-2) + ":" + ("0" + b).slice(-2) : v + ":" + ("0" + b).slice(-2);
      c < a && (e = !1);
      return e
    },
    B = function()
    {
      a.setStyle(x);
      y.createCardList();
      a.storage.userCardListEx.each(function(b)
      {
        var c = b.toJSON(),
          d = a.userEventAccomplishCharaArr[c.charaId];
        a.userEventAccomplishCharaArr[c.charaId] ? (c.damage = d.damage, c.mp = d.mp, c.dp = 0, 0 < d.mp && (c.mp = Math.floor(d.mp / 10), 0 == c.mp && (c.mp = 1)), 100 < c.mp && (c.dp = c.mp - 100, c.mp = 100), c.isDeath = !1, d.revivedAt ? a.periodCheck(k.currentTime, d.revivedAt) ? c.revivedAt = null : (c.isDeath = !0, c.revivedAt = d.revivedAt, c.reviveAtDisp = u(g, c.revivedAt)) : c.revivedAt = null) : (c.damage = 0, c.mp = 0, c.dp = 0, c.revivedAt = null);
        b.clear(
        {
          silent: !0
        });
        b.set(c,
        {
          silent: !0
        })
      });
      k = m.getPageJson();
      n = new A
    },
    C = {
      FIRE: 0,
      WATER: 1,
      TIMBER: 2,
      LIGHT: 3,
      DARK: 4
    },
    D = {
      get: "获得",
      level: "等级",
      rank: "稀有度",
      atk: "ATK",
      def: "DEF",
      hp: "HP",
      eplv: "剧情等级",
      rev: "魔力解放",
      mlv: "Magia等级",
      mp: "MP",
      revivedAt: "回复时间"
    },
    E = {
      get: "sortGet",
      level: "sortLv",
      rank: "sortRank",
      atk: "sortAtk",
      def: "sortDef",
      hp: "sortHp",
      eplv: "sortEplv",
      rev: "sortRev",
      mlv: "sortMlv",
      mp: "sortLv",
      revivedAt: "sortLv"
    },
    t = function(b)
    {
      var c = "asc" === b[1] ? -1 : 1,
        d = a.doc.querySelector("#scrollOuter .scrollInner");
      console.log(d.querySelectorAll(".charaWrap"));
      [].slice.call(d.querySelectorAll(".charaWrap")).map(function(a)
      {
        var c = Number(a.querySelector(".prm_" + b[0]).innerText),
          d = C[a.querySelector(".prm_att").innerText],
          e = Number(a.querySelector(".prm_charaId").innerText),
          f = Number(a.querySelector(".prm_rank").innerText);
        return {
          dom: a,
          value: c,
          value2: d,
          value3: e,
          value4: f
        }
      }).sort(function(a, d)
      {
        if (d.value < a.value) return -1 * c;
        if (d.value > a.value) return 1 * c;
        if ("get" !== b[0] && "revivedAt" !== b[0])
        {
          if (d.value2 < a.value2) return 1;
          if (d.value2 > a.value2) return -1;
          if (d.value4 > a.value4) return 1;
          if (d.value4 < a.value4) return -1;
          if (d.value3 > a.value3) return 1;
          if (d.value3 < a.value3) return -1
        }
        else
        {
          if (d.value3 < a.value3) return -1;
          if (d.value3 > a.value3) return 1
        }
        return 0
      }).forEach(function(a)
      {
        d.appendChild(a.dom)
      });
      console.log(b[1]);
      a.doc.querySelector("#sortBtn").dataset.id = b[0];
      a.doc.querySelector("#sortBtn").textContent = D[b[0]];
      a.doc.querySelector(".orderBtn").dataset.id = b[1];
      a.doc.querySelector(".orderBtn").className = "orderBtn se_tabs TE " + b[1];
      a.doc.querySelector("#scrollOuter").className = E[b[0]]
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
      id: "userFormationSheetList"
    },
    {
      id: "userPieceList"
    },
    {
      id: "userPieceSetList"
    },
    {
      id: "userCardList"
    },
    {
      id: "userCharaList"
    },
    {
      id: "userDoppelList"
    },
    {
      id: "userLive2dList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function()
    {
      m.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      k = m.getPageJson();
      l = f.findWhere(k.eventList,
      {
        eventType: "ACCOMPLISH"
      });
      g = (new Date(k.currentTime)).getTime();
      a.userEventAccomplishCharaArr || (a.userEventAccomplishCharaArr = {}, a.storage.userCharaList.each(function(b)
      {
        b = b.toJSON();
        a.userEventAccomplishCharaArr[b.charaId] = {
          charaId: b.charaId,
          damage: 0,
          mp: 1500,
          eventId: l.eventId,
          revivedAt: "2018/03/22 04:48:00"
        }
      }));
      console.log("common.userEventAccomplishCharaArr", a.userEventAccomplishCharaArr);
      B()
    },
    awakeSuspend: function(a)
    {
      console.log(a);
      g = (new Date(a)).getTime()
    },
    remove: function(a)
    {
      n && (n.trigger("removeView"), n.remove());
      l = k = null;
      h && clearInterval(h);
      g = h = null;
      a()
    }
  }
});
