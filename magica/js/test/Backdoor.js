define("underscore backbone backboneCommon ajaxControl command text!template/test/Backdoor.html text!css/test/Backdoor.css".split(" "), function(g, v, b, e, m, w, x)
{
  var q, f, z = function()
  {
    b.setStyle(x);
    var y = v.View.extend(
    {
      tagName: "div",
      events: function()
      {
        var a = {};
        a[b.cgti + " #decideSend"] = this.decideSend;
        a[b.cgti + " .inputTextBtn"] = this.inputText;
        a[b.cgti + " #inputClearBtn"] = this.inputClear;
        a[b.cgti + " #inputDelete1Btn"] = this.inputDelete1;
        return a
      },
      initialize: function(b)
      {
        this.model = b;
        this.template = g.template($("#selectNumPopParts").text())
      },
      render: function()
      {
        this.$el.html(this.template());
        return this
      },
      inputClear: function(a)
      {
        a.preventDefault();
        !b.isScrolled() && (a = b.doc.getElementById("inputNum")) && (a.value = "")
      },
      inputDelete1: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a = b.doc.getElementById("inputNum"), a.value && (a.value = a.value.slice(0, -1)))
      },
      inputText: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = b.doc.getElementById("inputNum"),
            d = c.value,
            d = d + a.currentTarget.dataset.text;
          c.value = d
        }
      },
      popup: function()
      {
        var a = this;
        new b.PopupClass(
        {
          title: a.model.name,
          content: "",
          decideBtnText: "领取",
          decideBtnEvent: a.decideSend.bind(a),
          closeBtnText: "取消",
          popupId: "bdItemNumPopup",
          popupType: "typeB"
        }, null, function()
        {
          b.nativeKeyBoard("inputNum", 10, 1)
        }, function()
        {
          a.removeView()
        });
        b.doc.getElementById("popupArea").getElementsByClassName("popupTextArea")[0].append(this.render().el)
      },
      decideSend: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = b.doc.getElementById("inputNum");
          (c = parseInt(c.value)) ? (q.getItem(a,
          {
            dataId: this.model.itemCode,
            num: c
          }), b.g_popup_instance.popupView.close()) : new b.PopupClass(
          {
            title: "错误",
            content: "号码无效",
            popupType: "typeE",
            closeBtnText: "OK"
          })
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    });
    q = new(v.View.extend(
    {
      events: function()
      {
        var a = [];
        a[b.cgti + " #itemWrap .getBtn"] = this.getItem;
        a[b.cgti + " #bgWrap .getBtn"] = this.getItem;
        a[b.cgti + " #itemWrap .specifyBtn"] = this.specifyBtn;
        a[b.cgti + " #gachaWrap .specifyBtn"] = this.specifyBtn;
        a[b.cgti + " #gachaWrap .getBtn"] = this.getItem;
        a[b.cgti + " #giftWrap .getBtn"] = this.getGift;
        a[b.cgti + " #giftWrap .getEnhancementGiftBtn"] = this.getEnhancementGift;
        a[b.cgti + " #charaWrap .getBtn"] = this.getCard;
        a[b.cgti + " #charaWrap .getDoppelBtn"] = this.getDoppel;
        a[b.cgti + " #memoriaWrap .getBtn"] = this.getMemoria;
        a[b.cgti + " #memoriaWrap .getMaxBtn"] = this.getMaxMemoria;
        a[b.cgti + " .setComposeBtn"] = this.setCompose;
        a[b.cgti + " .set01GetBtn"] = this.set01Get;
        a[b.cgti + " .set02GetBtn"] = this.set02Get;
        a[b.cgti + " .setStickerGetBtn"] = this.setStickerGet;
        a[b.cgti + " .setEventGetBtn"] = this.setEventGet;
        a[b.cgti + " #rewardGetBtn"] = this.rewardGet;
        a[b.cgti + " #rewardInputClearBtn"] = this.rewardInputClear;
        a[b.cgti + " #rewardInputDelete1Btn"] = this.rewardInputDelete1;
        a[b.cgti + " .showAllBtn"] = this.showAll;
        a[b.cgti + " .rewardInputBtn"] = this.rewardInput;
        a[b.cgti + " .tabBtn"] = this.tabChange;
        a[b.cgti + " .filterBtn li"] = this.filterChange;
        a[b.cgti + " .scrollBtn li"] = this.scroll;
        a[b.cgti + " #memoriaScrollBtn"] = this.memoriaSearch;
        return a
      },
      initialize: function(a)
      {
        f = e.getPageJson();
        a = f.giftList;
        var c = f.pieceList;
        f.itemList.sort(function(b, a)
        {
          return b.name > a.name ? 1 : b.name < a.name ? -1 : 0
        });
        a.sort(function(b, a)
        {
          return b.attributeId > a.attributeId ? 1 : b.attributeId < a.attributeId || a.id > b.id ? -1 : a.id < b.id ? 1 : 0
        });
        c.sort(function(b, a)
        {
          return b.pieceId > a.pieceId ? -1 : b.pieceId < a.pieceId ? 1 : 0
        });
        b.setGlobalView();
        this.template = g.template(w);
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: f
        }));
        return this
      },
      createDom: function()
      {
        b.content.append(this.render().el);
        var a = [
          {
            itemCode: "riche",
            name: "诅咒晶片（CC）",
            num: 1E7
          },
          {
            itemCode: "YELL",
            name: "好友点数",
            num: 3E4
          },
          {
            itemCode: "MONEY",
            name: "Magia 石（免费）",
            num: 1E4
          },
          {
            itemCode: "PURCHASED_MONEY",
            name: "<span class='c_red'>Magia 石头（付费）</span>",
            num: 750
          },
          {
            itemCode: "SCENEZERO_PLAY_TICKET",
            name: "召回提灯",
            num: 100
          },
          {
            itemCode: "SCENEZERO_SIDE_TICKET",
            name: "抽奖胶卷",
            num: 100
          },
          {
            itemCode: "PRISM",
            name: "魔法碎片",
            num: 1E3
          },
          {
            itemCode: "ARENA_COIN",
            name: "镜界币",
            num: 1E4
          },
          {
            itemCode: "DAILY_COIN",
            name: "每日硬币",
            num: 100
          },
          {
            itemCode: "EVENT_ARENARANKING_EXCHANGE_1",
            name: "御魂勋章",
            num: 1
          },
          {
            itemCode: "LIMIT_BREAK_ALL",
            name: "纯真宝石",
            num: 1
          },
          {
            itemCode: "RESET_ENHANCE",
            name: "始发船",
            num: 1
          },
          {
            itemCode: "DESTINY_CRYSTAL",
            name: "命运水晶",
            num: 5
          },
          {
            itemCode: "GACHA_TICKET,GACHA10_TICKET",
            name: "抽卡票，10张连票套",
            num: 1
          },
          {
            itemCode: "SPECIAL_GACHA_818_TICKET",
            name: "赠品序列号 抽卡券",
            num: 1
          },
          {
            itemCode: "EPISODE_COMPOSE_PP",
            name: "章节强化道具",
            num: 30
          },
          {
            itemCode: "MEMORIA_CIRCUIT,MEMORIA_CIRCUIT_CORE,OVER_LIMITTER,OVER_LIMITTER_CORE",
            name: "记忆结晶强化道具各种",
            num: 10
          },
          {
            itemCode: "EVENTSTORY_OPEN_KEY",
            name: "回忆的片段",
            num: 10
          }],
          c = f.eventList.concat(f.campaignList),
          d = f.itemList.sort();
        g.each(d, function(b)
        {
          g.each(c, function(c)
          {
            -1 === b.itemCode.indexOf("HOME_") && (-1 !== b.itemCode.indexOf("EVENT") && -1 !== b.itemCode.indexOf("_" + c.eventId + "_") && -1 === b.itemCode.indexOf("_STICKER_") || -1 !== b.itemCode.indexOf("CAMPAIGN") && -1 !== b.itemCode.indexOf("_" + c.id + "_")) && (c = {}, c.itemCode = b.itemCode, c.name = b.name, c.num = 99, a.unshift(c))
          })
        });
        var h = b.doc.createDocumentFragment(),
          e = g.template($("#itemParts").text());
        g.each(a, function(a, c)
        {
          var d = [];
          c = a.itemCode.split(",");
          g.each(c, function(a, c)
          {
            switch (a)
            {
              case "riche":
                d.push(b.storage.gameUser.toJSON().riche);
                break;
              case "MONEY":
                a = b.storage.userItemList.findWhere(
                {
                  itemId: "PRESENTED_MONEY"
                });
                d.push(a ? a.toJSON().quantity : 0);
                break;
              case "PURCHASED_MONEY":
                a = b.storage.userItemList.findWhere(
                {
                  itemId: "MONEY"
                });
                d.push(a ? a.toJSON().quantity : 0);
                break;
              default:
                a = b.storage.userItemList.findWhere(
                {
                  itemId: a
                }), d.push(a ? a.toJSON().quantity : 0)
            }
          });
          a.quantityText = d.join(", ");
          c = b.doc.createElement("div");
          c.className = "listItem commonFrame4";
          c.innerHTML = e(
          {
            model: a
          });
          h.appendChild(c)
        });
        b.doc.getElementById("itemWrap").prepend(h);
        var l = b.doc.createDocumentFragment(),
          d = d.sort(function(b, a)
          {
            b = b.itemCode;
            a = a.itemCode;
            return b < a ? -1 : b > a ? 1 : 0
          }),
          k = b.doc.createElement("div");
        k.className = "listItem commonFrame4";
        var r = {
            itemCode: "GACHA_TICKET,GACHA10_TICKET",
            name: "抽卡票，10张连票套",
            num: 1
          },
          t = b.storage.userItemList.findWhere(
          {
            itemId: "GACHA_TICKET"
          }),
          p = b.storage.userItemList.findWhere(
          {
            itemId: "GACHA10_TICKET"
          });
        r.quantityText = String(t ? t.toJSON().quantity : 0) + "," + String(p ? p.toJSON().quantity : 0);
        k.innerHTML = e(
        {
          model: r
        });
        l.appendChild(k);
        var n = b.doc.createDocumentFragment();
        g.each(d, function(a, c)
        {
          -1 !== a.itemCode.indexOf("HOME_") ? (c = b.doc.createElement("div"), c.className = "listItem commonFrame4", c.innerHTML = e(
          {
            model: a
          }), n.appendChild(c)) : -1 !== a.itemCode.indexOf("GACHA_") && -1 === a.itemCode.indexOf("FREEBIE_") && (c = b.storage.userItemList.findWhere(
          {
            itemId: a.itemCode
          }), a.quantityText = c ? c.toJSON().quantity : 0, c = b.doc.createElement("div"), c.className = "listItem commonFrame4", c.innerHTML = e(
          {
            model: a
          }), l.appendChild(c))
        });
        b.doc.getElementById("gachaWrap").appendChild(l);
        b.doc.getElementById("bgWrap").appendChild(n);
        b.scrollSet("outerWrap", "itemWrap");
        b.scrollSet("outerWrap", "gachaWrap");
        b.scrollSet("outerWrap", "bgWrap");
        b.scrollSet("outerWrap", "giftWrap");
        b.scrollSet("outerWrap", "charaWrap");
        b.scrollSet("outerWrap", "memoriaWrap");
        b.scrollSet("outerWrap", "setWrap");
        b.scrollSet("tabScroll", "common_tab");
        b.ready.hide()
      },
      tabChange: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = a.currentTarget.getAttribute("data-tab"),
            d = b.doc.getElementById(c + "Wrap"),
            h = b.doc.getElementById(c + "ControlWrap");
          "memoria" == c && 0 >= b.doc.getElementById("memoriaWrap").getElementsByClassName("listItem").length && (b.removeClass(b.doc.getElementById("memoriaControlWrap"), "show"), this.createPiece());
          $(".tabBtn").removeClass("current");
          b.addClass(a.currentTarget, "current");
          $(".wrap").removeClass("show");
          b.addClass(d, "show");
          $(".controlWrap").removeClass("show");
          b.addClass(h, "show");
          b.scrollRefresh("outerWrap", "itemWrap", !0);
          b.scrollRefresh("outerWrap", "gachaWrap", !0);
          b.scrollRefresh("outerWrap", "bgWrap", !0);
          b.scrollRefresh("outerWrap", "giftWrap", !0);
          b.scrollRefresh("outerWrap", "charaWrap", !0);
          b.scrollRefresh("outerWrap", "memoriaWrap", !0);
          b.scrollRefresh("outerWrap", "setWrap", !0)
        }
      },
      createPiece: function()
      {
        var a = b.doc.createDocumentFragment(),
          c = g.template($("#pieceParts").text());
        g.each(f.pieceList, function(d, h)
        {
          var e = b.doc.createElement("div");
          e.className = "listItem commonFrame4";
          9 <= h && (e.className += " hide");
          e.dataset.scrollHash = d.pieceId;
          e.innerHTML = c(
          {
            model: d
          });
          a.appendChild(e)
        });
        b.doc.getElementById("memoriaWrap").appendChild(a);
        m.getBaseData(b.getNativeObj())
      },
      filterChange: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          $(".filterBtn ul li").removeClass("current");
          b.addClass(a.currentTarget, "current");
          var c = b.doc.getElementById("btns").getElementsByClassName("current")[0].dataset.tab + "Wrap";
          a.currentTarget.parentNode.parentNode.parentNode.className = c + " wrap show " + a.currentTarget.getAttribute("data-att");
          b.scrollRefresh(null, null, !0)
        }
      },
      scroll: function(a)
      {
        a.preventDefault();
        b.isScrolled() || this.memoriaScroll(a.currentTarget.dataset.id)
      },
      memoriaSearch: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a = b.doc.getElementById("memoriaScrollInput"), a.value && this.memoriaScroll(a.value))
      },
      memoriaScroll: function(a)
      {
        var c = b.doc.getElementById("memoriaWrap").getElementsByClassName("showAllBtn")[0];
        c && $(c).trigger(b.cgti);
        b.forceScroll("outerWrap", "memoriaWrap", a, !0)
      },
      specifyBtn: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = a.currentTarget.parentNode.getElementsByClassName("num");
          a = {
            itemCode: a.currentTarget.getAttribute("data-id"),
            name: a.currentTarget.getAttribute("data-name"),
            num: c[0] ? parseInt(c[0].innerHTML) : 99
          };
          (new y(a)).popup()
        }
      },
      getItem: function(a, c)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var d = c ? c.dataId : a.currentTarget.getAttribute("data-id"),
            h = c ? c.num : null;
          if ("BACKGROUND" == d) d = {}, d.itemCode = a.currentTarget.getAttribute("data-itemcode"), d.quantity = 1, e.ajaxPost(b.linkList.backdoorItemSend, d, function(a)
          {
            b.responseSetStorage(a)
          });
          else
          {
            h || (a = a.currentTarget.parentNode.getElementsByClassName("num"), h = a[0] ? parseInt(a[0].innerHTML) : 99);
            var f = d.split(","),
              g = function()
              {
                var a = function(a)
                  {
                    b.responseSetStorage(a);
                    f.splice(0, 1);
                    f.length && g()
                  },
                  c = {};
                switch (f[0])
                {
                  case "riche":
                    c.riche = h;
                    e.ajaxPost(b.linkList.backdoorAddRiche, c, a);
                    break;
                  case "PURCHASED_MONEY":
                    c.money = h;
                    e.ajaxPost(b.linkList.backdoorAddMoney, c, a);
                    break;
                  default:
                    c.itemCode = f[0], c.quantity = h, e.ajaxPost(b.linkList.backdoorItemSend, c, a)
                }
              };
            g()
          }
        }
      },
      getGift: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = {};
          a.currentTarget.getAttribute("data-id") && (c.giftId = a.currentTarget.getAttribute("data-id"), c.quantity = 99);
          e.ajaxPost(b.linkList.backdoorGiftSend, c, function(a)
          {
            b.responseSetStorage(a)
          })
        }
      },
      getEnhancementGift: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = function(a)
          {
            b.responseSetStorage(a)
          };
          g.each(f.giftList, function(a)
          {
            if (800 > a.id) return !0;
            var d = {};
            d.giftId = a.id;
            d.quantity = 999;
            e.ajaxPost(b.linkList.backdoorGiftSend, d, c)
          })
        }
      },
      getCard: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = {};
          a.currentTarget.getAttribute("data-id") && (c.cardId = a.currentTarget.getAttribute("data-id"));
          e.ajaxPost(b.linkList.backdoorCardSend, c, function(a)
          {
            b.responseSetStorage(a)
          })
        }
      },
      getMemoria: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = {};
          a.currentTarget.getAttribute("data-id") && (c.pieceId = a.currentTarget.getAttribute("data-id"));
          e.ajaxPost(b.linkList.backdoorPieceSend, c, function(a)
          {
            b.responseSetStorage(a)
          })
        }
      },
      getMaxMemoria: function(a)
      {
        a.preventDefault();
        !b.isScrolled() && a.currentTarget.getAttribute("data-id") && (a = {
          rewardCode: "MAXPIECE_" + a.currentTarget.getAttribute("data-id") + "_1"
        }, e.ajaxPost(b.linkList.backdoorPayReward, a, function(a)
        {
          b.responseSetStorage(a)
        }))
      },
      setCompose: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          b.tapBlock(!0);
          var c = function(a)
            {
              b.responseSetStorage(a)
            },
            d = {
              riche: 99999999
            };
          e.ajaxPost(b.linkList.backdoorAddRiche, d, c);
          g.each(f.giftList, function(a)
          {
            d = {};
            d.giftId = a.id;
            d.quantity = 800 > a.id ? 100 : 999;
            e.ajaxPost(b.linkList.backdoorGiftSend, d, c)
          });
          g.each(f.itemList, function(a)
          {
            if ("EPISODE_COMPOSE_PP" === a.itemCode || -1 !== a.itemCode.indexOf("COMPOSE_ITEM_")) d = {},
              d.itemCode = a.itemCode, d.quantity = 999, e.ajaxPost(b.linkList.backdoorItemSend, d, c)
          });
          b.tapBlock(!1);
          new b.PopupClass(
          {
            title: "领取完成",
            content: "收到一套强化道具",
            closeBtnText: "关闭"
          })
        }
      },
      set01Get: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          b.tapBlock(!0);
          var c = {},
            d = 0,
            h = function(a)
            {
              var b = {};
              b.cardId = f.charaList[a].defaultCardId;
              return b
            },
            u = function(a)
            {
              b.responseSetStorage(a);
              d++;
              f.charaList[d] ? l() : (console.log("卡牌结束"), p())
            },
            l = function()
            {
              e.ajaxPost(b.linkList.backdoorCardSend, h(d), u)
            };
          l();
          var k = 0,
            r = function(a)
            {
              var b = {};
              b.pieceId = f.pieceList[a].pieceId;
              return b
            },
            t = function(a)
            {
              b.responseSetStorage(a);
              k++;
              f.pieceList[k] ? p() : (console.log("记忆结晶 结束"), m())
            },
            p = function()
            {
              e.ajaxPost(b.linkList.backdoorPieceSend, r(k), t)
            },
            n = function(a)
            {
              b.responseSetStorage(a)
            },
            m = function()
            {
              g.each(f.itemList, function(a)
              {
                c = {};
                c.itemCode = a.itemCode;
                c.quantity = 200;
                e.ajaxPost(b.linkList.backdoorItemSend, c, n)
              });
              g.each(f.giftList, function(a)
              {
                c = {};
                c.giftId = a.id;
                c.quantity = 99;
                e.ajaxPost(b.linkList.backdoorGiftSend, c, n)
              });
              c = {
                riche: 1E7
              };
              e.ajaxPost(b.linkList.backdoorAddRiche, c, n);
              b.tapBlock(!1);
              new b.PopupClass(
              {
                title: "领取完成",
                content: "请收到 魔法少女 作为礼物。",
                closeBtnText: "关闭"
              })
            }
        }
      },
      set02Get: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          b.tapBlock(!0);
          var c = {};
          f = e.getPageJson();
          var d = 0,
            h = function(a)
            {
              var b = {};
              b.cardId = f.charaList[a].defaultCardId;
              return b
            },
            u = function(a)
            {
              b.responseSetStorage(a);
              d++;
              f.charaList[d] ? l() : (console.log("卡牌结束"), m())
            },
            l = function()
            {
              e.ajaxPost(b.linkList.backdoorCardSend, h(d), u)
            };
          l();
          var k = function(a)
            {
              b.responseSetStorage(a)
            },
            m = function()
            {
              g.each(f.itemList, function(a)
              {
                c = {};
                c.itemCode = a.itemCode;
                c.quantity = 200;
                e.ajaxPost(b.linkList.backdoorItemSend, c, k)
              });
              g.each(f.giftList, function(a)
              {
                c = {};
                c.giftId = a.id;
                c.quantity = 99;
                e.ajaxPost(b.linkList.backdoorGiftSend, c, k)
              });
              c = {
                riche: 1E7
              };
              e.ajaxPost(b.linkList.backdoorAddRiche, c, k);
              b.tapBlock(!1);
              new b.PopupClass(
              {
                title: "领取完成",
                content: "请收到 魔法少女 作为礼物。",
                closeBtnText: "关闭"
              })
            }
        }
      },
      setStickerGet: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = {};
          f = e.getPageJson();
          var d = function(a)
          {
            b.responseSetStorage(a)
          };
          g.each(f.itemList, function(a)
          {
            -1 !== a.itemCode.indexOf("_STICKER_") && (c = {}, c.itemCode = a.itemCode, c.quantity = 1, e.ajaxPost(b.linkList.backdoorItemSend, c, d))
          })
        }
      },
      setEventGet: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = {};
          f = e.getPageJson();
          var d = function(a)
            {
              b.responseSetStorage(a)
            },
            h = a.currentTarget.dataset.id;
          g.each(f.itemList, function(a)
          {
            -1 === a.itemCode.indexOf("HOME_") && -1 !== a.itemCode.indexOf("_" + h + "_") && (c = {}, c.itemCode = a.itemCode, c.quantity = 1E3, e.ajaxPost(b.linkList.backdoorItemSend, c, d))
          })
        }
      },
      showAll: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          switch (a.currentTarget.dataset.id)
          {
            case "item":
              this.itemShowAll();
              break;
            case "gift":
              this.giftShowAll();
              break;
            default:
              var c = a.currentTarget.parentNode.getElementsByClassName("listItem");
              $(c).removeClass("hide")
          }
          b.scrollRefresh();
          a.currentTarget.remove()
        }
      },
      itemShowAll: function()
      {
        var a = b.doc.createDocumentFragment(),
          c = g.template($("#itemParts").text());
        g.each(f.itemList, function(d, e)
        {
          if (-1 != d.itemCode.indexOf("COMPOSE_ITEM") || -1 != d.itemCode.indexOf("CURE_AP") || -1 != d.itemCode.indexOf("CURE_BP")) e = b.storage.userItemList.findWhere(
          {
            itemId: d.itemCode
          }), d.quantityText = e ? e.toJSON().quantity : 0, e = b.doc.createElement("div"), e.className = "listItem commonFrame4", e.innerHTML = c(
          {
            model: d
          }), a.appendChild(e)
        });
        b.doc.getElementById("itemWrap").appendChild(a);
        m.getBaseData(b.getNativeObj());
        b.scrollRefresh()
      },
      giftShowAll: function()
      {
        var a = f.giftList,
          c = b.doc.createDocumentFragment(),
          d = g.template($("#giftParts").text());
        g.each(a, function(a, e)
        {
          e = a.attributeId ? a.attributeId : "ALL";
          var f = b.doc.createElement("div");
          f.className = "listItem commonFrame4 " + e;
          f.innerHTML = d(
          {
            model: a
          });
          c.appendChild(f)
        });
        b.doc.getElementById("giftWrap").appendChild(c);
        m.getBaseData(b.getNativeObj());
        b.scrollRefresh()
      },
      rewardGet: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a = b.doc.getElementById("rewardGetInput"), a.value && (window.isLocal ? console.log(a.value) : e.ajaxPost(b.linkList.backdoorPayReward,
        {
          rewardCode: a.value
        }, function(a)
        {
          b.responseSetStorage(a);
          console.log(a)
        })))
      },
      rewardInputClear: function(a)
      {
        a.preventDefault();
        !b.isScrolled() && (a = b.doc.getElementById("rewardGetInput")) && (a.value = "")
      },
      rewardInputDelete1: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a = b.doc.getElementById("rewardGetInput"), a.value && (a.value = a.value.slice(0, -1)))
      },
      rewardInput: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = a.currentTarget;
          var c = b.doc.getElementById("rewardGetInput"),
            d = a.dataset.clear ? "" : c.value,
            d = d + a.dataset.text;
          c.value = d
        }
      }
    }));
    m.getBaseData(b.getNativeObj())
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
      id: "userStatusList"
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
    }],
    fetch: function()
    {
      e.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      z()
    },
    remove: function(b)
    {
      q && q.remove();
      b()
    }
  }
});
