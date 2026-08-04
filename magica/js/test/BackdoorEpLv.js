define("underscore backbone backboneCommon ajaxControl command text!template/test/BackdoorEpLv.html text!css/test/BackdoorEpLv.css js/view/chara/CharaListView cardUtil CharaCommon".split(" "), function(m, k, a, f, g, n, p, q, h, r)
{
  var l = k.Model.extend(),
    c, t = k.View.extend(
    {
      events: function()
      {
        var b = {};
        b[a.cgti + " #epUpBtn"] = this.epUp;
        b[a.cgti + " #storyOpenBtn"] = this.storyOpen;
        b[a.cgti + " #lvUpBtn"] = this.lvUp;
        b[a.cgti + " #doppelBtn"] = this.getDoppel;
        return b
      },
      initialize: function(a)
      {
        this.prm = {};
        this.template = m.template(n);
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template(f.getPageJson()));
        return this
      },
      lvUp: function(b)
      {
        b.preventDefault();
        if (!(a.isScrolled() || !window.isBrowser || b.currentTarget.classList.contains("off") || (b = a.storage.userItemList.findWhere(
          {
            itemId: "COMPOSE_ITEM_ALL_PP"
          }), 10 > (b ? b.get("quantity") : 0))))
        {
          b = {
            userCardId: a.storage.userCardListEx.findWhere(
            {
              charaId: this.prm.charaId
            }).toJSON().userCardId,
            useItem:
            {
              COMPOSE_ITEM_ALL_PP: 10
            }
          };
          var e = this;
          f.ajaxPost(a.linkList.userCardCompose, b, function(b)
          {
            a.responseSetStorage(b);
            var d = e.targetView.model.toJSON(),
              c = a.storage.userCharaList.findWhere(
              {
                charaId: d.charaId
              }).toJSON();
            b = h.addExStatus($.extend(b.userCardList[0], c));
            d = a.storage.userCardListEx.findWhere(
            {
              id: d.id
            });
            d.clear(
            {
              silent: !0
            });
            d.set(b);
            g.getBaseData(a.getNativeObj());
            a.pageObj.charaSelect(e.targetView)
          })
        }
      },
      epUp: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled() && !b.currentTarget.classList.contains("off"))
        {
          var e = this;
          f.ajaxPost(a.linkList.testEpsodeUp, this.prm, function(b)
          {
            a.responseSetStorage(b);
            var d = e.targetView.model.toJSON(),
              c = a.storage.userCardList.findWhere(
              {
                id: d.id
              }).toJSON();
            b = h.addExStatus($.extend(b.userCharaList[0], c));
            c = a.storage.userCardListEx.findWhere(
            {
              id: d.id
            });
            c.clear(
            {
              silent: !0
            });
            c.set(b);
            d = new r.CharaResultView(
            {
              model: new l(
              {
                before: d,
                after: b,
                type: "episode"
              })
            });
            $("#overlapContainer").append(d.render().el);
            g.getBaseData(a.getNativeObj());
            a.pageObj.charaSelect(e.targetView)
          })
        }
      },
      storyOpen: function(b)
      {
        b.preventDefault();
        a.isScrolled() || f.ajaxPost(a.linkList.testStoryOpen,
        {}, function(b)
        {
          a.responseSetStorage(b);
          new a.PopupClass(
          {
            title: "キャラストーリー解放",
            content: "キャラストーリーを解放しました",
            closeBtnText: "关闭"
          })
        })
      },
      getDoppel: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          var c = this;
          f.ajaxPost(a.linkList.backdoorPayReward,
          {
            rewardCode: "DOPPEL_" + this.prm.charaId + "00"
          }, function(b)
          {
            a.responseSetStorage(b);
            new a.PopupClass(
            {
              title: "ドッペル受け取り",
              content: c.targetView.model.toJSON().chara.name + "のドッペルを受け取りました",
              closeBtnText: "关闭"
            })
          })
        }
      },
      createDom: function()
      {
        a.setGlobalView();
        h.createCardList();
        a.content.append(this.render().el);
        a.ready.hide()
      }
    });
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
      id: "userChapterList"
    },
    {
      id: "userSectionList"
    },
    {
      id: "userQuestBattleList"
    }],
    fetch: function()
    {
      window.isDebug && f.pageModelGet(this.needModelIdObj)
    },
    charaSelect: function(b)
    {
      if (c)
      {
        $("#charaListElms .select").removeClass("select");
        a.addClass(b.el, "select");
        var e = b.model.toJSON(),
          f = e.charaId,
          d = e.chara.name,
          g = e.episodeLevel,
          h = parseInt(String(e.cardId).slice(-1));
        console.log(e);
        a.doc.querySelector("#charaNameDisp").textContent = d;
        a.doc.querySelector("#epLvDisp").textContent = g;
        5 <= g ? (a.addClass(a.doc.querySelector("#epUpBtn"), "off"), 5 <= h ? a.removeClass(a.doc.querySelector("#doppelBtn"), "off") : a.addClass(a.doc.querySelector("#doppelBtn"), "off")) : (a.removeClass(a.doc.querySelector("#epUpBtn"), "off"), a.addClass(a.doc.querySelector("#doppelBtn"), "off"));
        c.prm.charaId = f;
        c.targetView = b
      }
    },
    init: function()
    {
      a.setStyle(p);
      c = new t;
      c.charaListView = new q(
      {
        model: new l,
        collection: a.storage.userCardListEx
      });
      a.content.append(c.charaListView.render().el);
      c.charaListView.cardSort.sortStart();
      g.getBaseData(a.getNativeObj());
      a.scrollSetX("charaListScrollWrap", "list")
    },
    remove: function(a)
    {
      c.charaListView.removeView();
      c.remove();
      a()
    }
  }
});
