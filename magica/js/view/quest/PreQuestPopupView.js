define("underscore backbone backboneCommon ajaxControl command text!template/quest/PreQuestPopup.html cardUtil sortUtil".split(" "), function(k, m, b, q, g, u, v)
{
  var r, h = [],
    l, w = m.Collection.extend(
    {
      initialize: function(a)
      {
        this.position = [
        {
          pos: 1,
          view: null,
          index: null
        },
        {
          pos: 4,
          view: null,
          index: null
        },
        {
          pos: 5,
          view: null,
          index: null
        },
        {
          pos: 7,
          view: null,
          index: null
        },
        {
          pos: 9,
          view: null,
          index: null
        }];
        this.setCharaCnt = 0;
        this.listenTo(this, "add", this.modelAdd);
        this.listenTo(this, "remove", this.modelRemove)
      },
      modelAdd: function(a)
      {
        console.log("model已添加", a);
        var c = a.toJSON().attack + a.toJSON().defense,
          f = parseInt(b.doc.getElementsByClassName("combatPowerDisp")[0].innerText);
        b.doc.getElementsByClassName("combatPowerDisp")[0].innerText = f + c;
        var e = b.doc.createDocumentFragment(),
          d = new n(
          {
            model: a.toJSON()
          });
        k.some(this.position, function(a)
        {
          if (!a.view) return d.el.className = "pos_" + a.pos, a.view = d, e.appendChild(d.render().el), !0
        });
        b.doc.getElementsByClassName("miniCharaWrap")[0].appendChild(e);
        this.setCharaCnt++
      },
      modelRemove: function(a)
      {
        console.log("model已移除", a);
        var c = a.toJSON().attack + a.toJSON().defense,
          f = parseInt(b.doc.getElementsByClassName("combatPowerDisp")[0].innerText);
        b.doc.getElementsByClassName("combatPowerDisp")[0].innerText = f - c;
        k.each(this.position, function(b, c)
        {
          b.view && a.id == b.view.model.id && (b.view.remove(), b.view = null)
        });
        this.setCharaCnt--
      }
    }),
    x = m.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " #tapArea span"] = this.charaSelect;
        return a
      },
      initialize: function(a)
      {
        this.charaSelectFlag = !1;
        this.selectChara = null;
        this.listenTo(this.parentView, "removeView", this.removeView)
      },
      charaSelect: function(a)
      {
        var c = this,
          f = a.currentTarget.getAttribute("data-index"),
          e = null,
          d = null;
        k.each(this.collection.position, function(a, g)
        {
          f == a.pos && (a.view && !c.charaSelectFlag ? (b.addClass(a.view.el, "select"), c.selectChara = a, c.selectChara.index = g, c.charaSelectFlag = !0) : (a.view && a.view.el.classList.contains("select") ? b.removeClass(a.view.el, "select") : (e = c.selectChara, d = a, d.index = g, e && (e.view.el.className = "pos_" + d.pos), d.view && (d.view.el.className = "pos_" + e.pos)), c.selectChara = null, c.charaSelectFlag = !1))
        });
        e && (a = this.collection.position[e.index].view, this.collection.position[e.index].view = d.view, this.collection.position[d.index].view = a, d = e = null)
      }
    }),
    n = m.View.extend(
    {
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        return this
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    p = m.View.extend(
    {
      tagName: "li",
      initialize: function(a)
      {
        this.listenTo(this.parentView, "removeView", this.removeView)
      },
      events: function()
      {
        var a = {};
        a[b.cgti] = this.charaSelect;
        return a
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        this.el.className = this.model.card.attributeId + " " + this.model.card.rank;
        return this
      },
      charaSelect: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = this;
          if (this.el.classList.contains("select"))
          {
            var f = null;
            k.each(h, function(a, b)
            {
              a.userCardId === c.model.userCardId && (f = b)
            });
            4 === h.length && b.removeClass(charaListElms, "off");
            l.collection.remove(l.collection.at(f));
            h.splice(f, 1)
          }
          else
          {
            if (4 === h.length) return;
            l.collection.add(this.model);
            h.push(this.model);
            4 === h.length && b.addClass(charaListElms, "off")
          }
          this.el.classList.toggle("select")
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    t = m.View.extend(
    {
      className: "popupContent open typeB preQuestPopup",
      events: function()
      {
        var a = {};
        a[b.cgti + " #questStartBtn"] = this.preQuestStart;
        a[b.cgti + " #charaListElms li"] = this.charaSelect;
        a[b.cgti + " .popupCloseBtn"] = this.close;
        a.animationend = this.nextAnimation;
        a.webkitAnimationEnd = this.nextAnimation;
        a.webkitTransitionEnd = this.nextAnimation;
        return a
      },
      initialize: function(a)
      {
        this.selectCharaNum = 0;
        this.template = k.template(u);
        b.g_popup_instance = this;
        r = q.getPageJson();
        v.createCardList();
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
        b.addClass(b.doc.getElementById("curtain"), "show");
        $("#overlapContainer").append(this.render().el);
        this.createView()
      },
      createView: function()
      {
        n.prototype.parentView = this;
        p.prototype.parentView = this;
        n.prototype.template = k.template($("#FormationCharaTemp").text());
        p.prototype.template = k.template($("#UserCardListTemp").text());
        var a = b.doc.createDocumentFragment();
        b.storage.userCardListEx.each(function(b)
        {
          b = new p(
          {
            model: b.toJSON()
          });
          a.appendChild(b.render().el)
        });
        b.doc.getElementById("charaListElms").appendChild(a);
        var c = new w;
        l = new x(
        {
          el: b.doc.getElementById("formation"),
          collection: c
        })
      },
      preQuestStart: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
          if (0 === h.length) b.removeClass(b.doc.getElementById("curtain"), "show"), new b.PopupClass(
          {
            title: "关卡确认",
            content: "未选择魔法少女",
            closeBtnText: "关闭"
          }, null, null, [y, this]);
          else if (parseInt(b.doc.querySelector(".ACP").textContent) < this.model.ap) b.removeClass(b.doc.getElementById("curtain"), "show"), new b.PopupClass(
        {
          title: "关卡确认",
          content: "AP 不足",
          closeBtnText: "关闭"
        });
        else
        {
          console.log("preQuestStart:", this.model);
          console.log("selectCharaArr:", h);
          var c = {};
          c.questBattleId = this.model.questBattle.questBattleId;
          c.deckType = "MAIN";
          l.collection.each(function(a, b)
          {
            c["userCardId" + (b + 1)] = a.toJSON().userCardId;
            c["positionId" + (b + 1)] = l.collection.position[b].pos
          });
          z(this.model.questBattle.startStory, r.userQuestAdventureList, c)
        }
      },
      close: function(a)
      {
        a && a.preventDefault();
        b.isScrolled() || (b.removeClass(this.el, "open"), b.addClass(this.el, "close"), this.trigger("removeView"), this.removeView())
      },
      nextAnimation: function(a)
      {
        a.currentTarget.classList.contains("close") && (b.myScroll && b.scrollBarControl("destroy"), this.removeView())
      },
      removeView: function()
      {
        console.log("prepopup remove");
        $("#commandDiv").off();
        b.doc.getElementById("curtain").className = "";
        h = [];
        this.off();
        this.remove()
      }
    }),
    y = function(a)
    {
      var b = a.model;
      a.trigger("removeView");
      a.removeView();
      new t(
      {
        model: b
      })
    },
    z = function(a, c, f)
    {
      $(b.ready.target).on("webkitAnimationEnd", function()
      {
        $(b.ready.target).off();
        g.changeBg("web_black.jpg");
        window.isBrowser && (b.g_popup_instance.close(), console.log("quest:start:questPrm:", f), g.sendCommand("QuestStub," + JSON.stringify(f)));
        var e = !0;
        k.each(c, function(a) {});
        a || (e = !1);
        var d = null,
          d = e ? function(b)
          {
            $("#commandDiv").on("nativeCallback", function()
            {
              g.setWebView(!1);
              g.startQuest(b.userQuestBattleResult[0].id)
            });
            g.setWebView(!1);
            g.startStory(a)
          } : function(a)
          {
            console.log("questPrm!!!!!:", a);
            g.setWebView(!1);
            g.setWebView(!1);
            g.startQuest(a.userQuestBattleResult[0].id)
          };
        q.ajaxPost(b.linkList.questStart, f, d)
      });
      b.addClass(b.ready.target, "preNativeFadeIn")
    };
  return t
});
