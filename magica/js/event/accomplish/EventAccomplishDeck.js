define("underscore backbone backboneCommon ajaxControl command text!template/event/accomplish/EventAccomplishDeck.html text!css/formation/DeckFormation.css text!css/event/accomplish/EventAccomplishDeck.css cardUtil memoriaUtil js/view/chara/CharaListView js/card/CardPopup js/memoria/MemoriaPopup QuestUtil".split(" "), function(g, C, a, z, k, V, W, X, O, Y, Z, F, G, fa)
{
  function P(b)
  {
    if (b)
    {
      b = b.webData;
      var c = b.userQuestBattleResultList[0].questBattle;
      a.responseSetStorage(b);
      if (b = (b = a.storage.userSectionList.findWhere(
        {
          sectionId: c.sectionId
        })) ? b.toJSON() : null) c = (c = a.storage.userChapterList.findWhere(
      {
        chapterId: b.section.genericId
      })) ? c.toJSON() : null, a.playChapter = c, a.playSection = b
    }
  }
  var H = C.Model.extend(),
    I = null,
    x = null,
    t, J, u = null,
    w = null,
    p = null,
    f = null,
    K = !1,
    v, ba = C.View.extend(
    {
      initialize: function(a)
      {
        this.template = g.template(V);
        this.createDom()
      },
      render: function()
      {
        var a = z.getPageJson();
        a.deckCatType = u;
        this.$el.html(this.template(a));
        return this
      },
      createDom: function()
      {
        a.setGlobalView();
        a.addClass(a.doc.querySelector("#globalMenuContainer"), "questFormation");
        a.content.append(this.render().el);
        this.createView()
      },
      createView: function()
      {
        L.prototype.parentView = this;
        L.prototype.template = g.template($("#DeckViewTemp").text());
        var b = a.doc.createDocumentFragment();
        f = new L(
        {
          model: new H(p)
        });
        b.appendChild(f.render().el);
        a.doc.querySelector("#DeckFormation").appendChild(b);
        a.doc.querySelector(".memoriaEquipMode") && a.addClass(a.doc.querySelector("#pieceEquipBtn"), "on");
        a.questBattleModel && (a.addClass(a.doc.querySelector(".attBox"), "enemyDetail"), g.each(a.questBattleModel.questBattle.waveEnemyAttributeIdList, function(b)
        {
          b = b.toLowerCase();
          a.addClass(a.doc.querySelector(".enemyDetail ." + b), "on")
        }));
        k.getBaseData(a.getNativeObj());
        y(f.model.toJSON(), p);
        M.prototype.parentView = this;
        M.prototype.template = g.template($("#UserFormationListTemp").text());
        b = a.doc.createDocumentFragment();
        a.storage.userFormationSheetList.comparator = function(a)
        {
          return a.get("formationSheetId")
        };
        a.storage.userFormationSheetList.sort();
        a.storage.userFormationSheetList.each(function(a)
        {
          var c = a.toJSON(),
            d = [];
          g.each(c.formationSheet, function(a, b)
          {
            -1 !== b.indexOf("placeSkill") && -1 === b.indexOf("placeSkillId") && d.push(b.split("placeSkill")[1])
          });
          a.set(
          {
            posArr: d
          });
          a = new M(
          {
            model: a
          });
          b.appendChild(a.render().el)
        });
        a.doc.querySelector(".formationSheetListInner").appendChild(b);
        N.prototype.parentView = this;
        N.prototype.template = g.template($("#deckChangeModeTemp").text());
        var c = Q(),
          b = a.doc.createDocumentFragment();
        console.log("deckList:", c);
        this.deckChangeModeView = new N(
        {
          model: new H(c)
        });
        b.appendChild(this.deckChangeModeView.render().el);
        a.doc.querySelector("#deckSelectWrap").appendChild(b);
        a.ready.hide()
      },
      events: function()
      {
        var b = {};
        b[a.cgti + " #mainBtn"] = this.deckSave;
        b[a.cgti + " #nextPageBtn"] = this.questFunc;
        b[a.cgti + " #pieceEquipBtn"] = this.pieceEquipMode;
        b[a.cgti + " #formationSheetChangeBtn"] = this.formationSheetChange;
        b[a.cgti + " #dispModeChangeBtn"] = this.dispModeChange;
        b[a.cgti + " #previewBtn"] = this.deckPreview;
        b[a.cgti + " #deckRemovePopBtn"] = this.deckRemovePop;
        b[a.cgti + " #previewCloseBtn"] = this.deckPreviewClose;
        b[a.cgti + " #formationSheetDecideBtn"] = this.formationSheetClose;
        b[a.cgti + " #formationDetailBtn"] = this.formationDetailOpen;
        return b
      },
      deckSave: function(b)
      {
        if (b && (b.preventDefault(), a.isScrolled() || b.currentTarget.classList.contains("off"))) return;
        var c = this,
          d = f.model.toJSON();
        b = {
          deckType: d.deckType,
          formationSheetId: d.formationSheetId,
          name: d.name,
          episodeUserCardId: d.questEpisodeUserCardId
        };
        for (var e = [], h = [], B = [], n = 0; 10 > n;)
        {
          if (d["userCardId" + (n + 1)])
          {
            e.push(d["userCardId" + (n + 1)]);
            h.push(d["questPositionId" + (n + 1)]);
            for (var l = "place" + d["questPositionId" + (n + 1)], m = [], q = 0; 4 > q;)
            {
              if (d.userPieceObj[l] && d.userPieceObj[l][q] && !d.userPieceObj[l][q].invalidFlag)
              {
                var R = "userPieceId" + ("000" + (n + 1) + (q + 1)).slice(-3);
                d[R] && m.push(d[R])
              }
              q = q + 1 | 0
            }
            B.push(m)
          }
          n = n + 1 | 0
        }
        b.userCardIds = e;
        b.questPositionIds = h;
        b.userPieceIdLists = B;
        d = function(b)
        {
          a.responseSetStorage(b);
          k.getBaseData(a.getNativeObj());
          a.holdDeck = null;
          var d = Q();
          c.deckChangeModeView.model.clear(
          {
            silent: !0
          });
          c.deckChangeModeView.model.set(d);
          b = b.userDeckList[0];
          b.formationSheet || (b.formationSheet = g.findWhere(t.userFormationSheetList,
          {
            formationSheetId: b.formationSheetId
          }).formationSheet, a.storage.userDeckList.findWhere(
          {
            deckType: b.deckType
          }).set(
          {
            formationSheet: b.formationSheet
          }));
          p = r(b);
          f.model.clear(
          {
            silent: !0
          });
          f.model.set(r(p));
          y(f.model.toJSON(), p)
        };
        k.startSe(1002);
        window.isLocal || z.ajaxPost(a.linkList.userDeckSave, b, d)
      },
      questFunc: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled() && !K)
        {
          a.androidKeyStop = !0;
          var c = f.model.toJSON();
          b = function()
          {
            for (var a = [], b = 0; 10 > b;)
            {
              var d = c["userCardId" + (b + 1)];
              d && a.push(d);
              b = b + 1 | 0
            }
            return a
          }();
          if (a.eventAccomplishQuestMode && "challenge" == a.eventAccomplishQuestMode && 3 > b.length) k.startSe(1002), new a.PopupClass(
          {
            title: "编成错误",
            content: "开始战斗需要队伍中<br>编有3个以上的魔法少女。",
            closeBtnText: "OK"
          }), a.androidKeyStop = !1;
          else if (b.length)
          {
            var d = !1;
            g.each(c.userCardObj, function(a, b)
            {
              a.isDeath && (d = !0)
            });
            if (d) k.startSe(1002), new a.PopupClass(
            {
              title: "编成错误",
              content: "其中包含无法战斗的魔法少女。",
              closeBtnText: "OK"
            }), a.androidKeyStop = !1;
            else
            {
              var e = {};
              e.questBattleId = a.questBattleModel.questBattle.questBattleId;
              e.deckType = c.deckType;
              g.each(c, function(a, b)
              {
                -1 != b.indexOf("questPositionId") && (e[b] = a); - 1 != b.indexOf("userCardId") && (e[b] = a); - 1 != b.indexOf("userPieceId") && (e[b] = a)
              });
              b = null;
              var h = a.questBattleModel.questBattle.startStory;
              a.questBattleModel.secret && (b = a.questBattleModel.secret);
              K = !0;
              aa(h, a.questBattleModel.userQuestAdventureList, e, b);
              k.startSe(1001)
            }
          }
          else k.startSe(1002), new a.PopupClass(
          {
            title: "编成错误",
            content: "请至少设置 1 名角色",
            closeBtnText: "OK"
          }), a.androidKeyStop = !1
        }
      },
      pieceEquipMode: function(b)
      {
        if (b && (b.preventDefault(), a.isScrolled())) return;
        a.doc.querySelector(".deckViewWrap").classList.contains("memoriaEquipMode") ? (a.removeClass(a.doc.querySelector(".deckViewWrap"), "memoriaEquipMode"), a.removeClass(a.doc.querySelector("#pieceEquipBtn"), "on")) : (a.addClass(a.doc.querySelector(".deckViewWrap"), "memoriaEquipMode"), a.addClass(a.doc.querySelector("#pieceEquipBtn"), "on"))
      },
      formationSheetChange: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (f.selectModel = null, f.selectPos = null, a.removeClass(a.doc.querySelector("#charaListWrap"), "open"), setTimeout(function()
        {
          a.addClass(a.doc.querySelector("#DeckFormation"), "formation");
          var b = a.doc.querySelectorAll('[data-fsid="' + f.model.toJSON().formationSheetId + '"]')[0];
          a.addClass(b, "select");
          a.addClass(a.doc.querySelector("#deckFooter .default"), "noneDisp");
          a.removeClass(a.doc.querySelector("#deckFooter .fs"), "noneDisp");
          a.addClass(a.doc.querySelector("#globalBackBtn"), "noneDisp");
          a.removeClass(a.doc.querySelector("#sideMenu"), "anim");
          a.addClass(a.doc.querySelector("#menu"), "noneDisp");
          a.scrollSet("formationSheetListOuter", "formationSheetListInner");
          a.scrollRefresh(null, null, !0)
        }, 0))
      },
      dispModeChange: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (b = a.doc.querySelector(".deckViewWrap"), b.classList.contains("memoriaEquipMode") ? (a.removeClass(b, "memoriaEquipMode"), a.removeClass(a.doc.querySelector("#pieceEquipBtn"), "on")) : b.classList.contains("charaStatusMode") ? (a.removeClass(b, "charaStatusMode"), a.addClass(b, "diskMode")) : b.classList.contains("diskMode") ? (a.removeClass(b, "diskMode"), a.addClass(b, "skillMode")) : b.classList.contains("skillMode") && (a.removeClass(b, "skillMode"), a.addClass(b, "charaStatusMode")))
      },
      deckPreview: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          setTimeout(function()
          {
            a.addClass(a.doc.querySelector("#DeckFormation"), "preview");
            a.addClass(a.doc.querySelector("#deckFooter .default"), "noneDisp");
            a.removeClass(a.doc.querySelector("#deckFooter .preview"), "noneDisp");
            a.addClass(a.doc.querySelector("#globalBackBtn"), "noneDisp");
            a.removeClass(a.doc.querySelector("#sideMenu"), "anim");
            a.addClass(a.doc.querySelector("#menu"), "noneDisp")
          }, 0);
          var c = [],
            d = {
              1: 8,
              2: 5,
              3: 2,
              4: 7,
              5: 4,
              6: 1,
              7: 6,
              8: 3,
              9: 0
            };
          g.each(f.model.toJSON().userCardObj, function(a, b)
          {
            if (a.card)
            {
              var e = f.model.toJSON().questEpisodeUserCardId == a.id ? !0 : !1,
                h = {};
              h.miniCharId = a.card.miniCharaNo;
              h.positionId = d[b.split("place")[1]];
              h.isLeader = e;
              h.isSupport = a.support;
              a.faceHidden && (h.isUnknown = !0);
              c.push(h)
            }
          });
          setTimeout(function()
          {
            k.formationPreview(c)
          }, 100)
        }
      },
      deckRemovePop: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          a.removeClass(a.doc.querySelector(".deckViewWrap"), "memoriaEquipMode");
          b = $("#TeamRemovePop").text();
          var c = f.model.toJSON();
          c.popupType = "typeC";
          var d = new a.PopupClass(c, b, function()
          {
            $("#popupArea .decideBtn").on(a.cgti, function(b)
            {
              b = f.model.toJSON();
              b = r(
              {
                deckType: b.deckType,
                formationSheet: b.formationSheet,
                formationSheetId: b.formationSheetId,
                questPositionHelper: b.questPositionHelper,
                name: b.name
              });
              f.model.clear(
              {
                silent: !0
              });
              f.model.set(b);
              y(b, p);
              k.getBaseData(a.getNativeObj());
              d.remove()
            })
          })
        }
      },
      deckPreviewClose: function(b)
      {
        b.preventDefault();
        a.isScrolled() || (setTimeout(function()
        {
          a.removeClass(a.doc.querySelector("#DeckFormation"), "preview");
          a.removeClass(a.doc.querySelector("#deckFooter .default"), "noneDisp");
          a.addClass(a.doc.querySelector("#deckFooter .preview"), "noneDisp");
          a.removeClass(a.doc.querySelector("#globalBackBtn"), "noneDisp");
          a.removeClass(a.doc.querySelector("#menu"), "noneDisp")
        }, 0), setTimeout(function()
        {
          k.formationPreviewRemove()
        }, 20))
      },
      formationSheetClose: function(b)
      {
        b.preventDefault();
        a.isScrolled() || setTimeout(function()
        {
          a.removeClass(a.doc.querySelector("#DeckFormation"), "formation");
          a.doc.getElementById("formationDetail").classList.contains("disp") && (a.removeClassId("formationDetail", "disp"), a.removeClass(a.doc.getElementById("formationSheetListOuter"), "hide"), "formationSheetDecideBtn" !== b.currentTarget.id && (b.currentTarget.textContent = "阵形详情"), a.scrollDestroy("formationDetailScrollWrap", "fromationDetailScrollInner"), a.doc.getElementById("formationDetail").innerHTML = "");
          var c = a.doc.querySelectorAll('[data-fsid="' + f.model.toJSON().formationSheetId + '"]')[0];
          a.removeClass(c, "select");
          a.removeClass(a.doc.querySelector("#deckFooter .default"), "noneDisp");
          a.addClass(a.doc.querySelector("#deckFooter .fs"), "noneDisp");
          a.removeClass(a.doc.querySelector("#globalBackBtn"), "noneDisp");
          a.removeClass(a.doc.querySelector("#menu"), "noneDisp")
        }, 0)
      },
      formationDetailOpen: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
          if (a.doc.getElementById("formationDetail").classList.contains("disp")) a.removeClassId("formationDetail", "disp"), a.removeClass(a.doc.getElementById("formationSheetListOuter"), "hide"), b.currentTarget.textContent = "阵形详情", a.scrollDestroy("formationDetailScrollWrap", "fromationDetailScrollInner"), a.doc.getElementById("formationDetail").innerHTML = "";
          else
          {
            var c = g.clone(f.model.toJSON()),
              d = a.doc.getElementById("formationSheetListOuter").getElementsByClassName("select")[0],
              c = c.formationSheet = a.storage.userFormationSheetList.findWhere(
              {
                formationSheetId: d.dataset.fsid | 0
              }).toJSON().formationSheet;
            console.log("deckPrev", c);
            var e = a.doc.createElement("div"),
              h = g.template($("#formationDetailTemp").text());
            e.innerHTML = h(
            {
              model: c
            });
            a.doc.getElementById("formationDetail").appendChild(e);
            c = a.doc.getElementById("formationDetailScrollWrap").getElementsByClassName("detailMiniMap");
            for (e = 0; e < c.length; e++) h = d.getElementsByClassName("formationMiniMap")[0].cloneNode(!0), c[e].appendChild(h);
            k.getBaseData(a.getNativeObj());
            a.addClassId("formationDetail", "disp");
            a.scrollSet("formationDetailScrollWrap", "fromationDetailScrollInner");
            a.addClass(a.doc.getElementById("formationSheetListOuter"), "hide");
            b.currentTarget.textContent = "阵型一览"
          }
      }
    }),
    M = C.View.extend(
    {
      initialize: function(a)
      {
        this.listenTo(this.parentView, "removeView", this.removeView)
      },
      className: "list se_decide commonFrame4 flexBox",
      events: function()
      {
        var b = {};
        b[a.cgti] = this.previewSet;
        return b
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model.toJSON()
        }));
        this.el.dataset.fsid = this.model.toJSON().formationSheetId;
        return this
      },
      previewSet: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          a.removeClass(a.doc.querySelector(".list.select"), "select");
          a.addClass(this.el, "select");
          b = this.model.toJSON().formationSheetId;
          var c = g.clone(f.model.toJSON());
          c.formationSheetId = b;
          c.formationSheet = a.storage.userFormationSheetList.findWhere(
          {
            formationSheetId: b
          }).toJSON().formationSheet;
          var d = [];
          g.each(c.formationSheet, function(a, b)
          {
            -1 !== b.indexOf("placeSkillId") && d.push(b.split("placeSkillId")[1])
          });
          g.each(c, function(a, b)
          {
            -1 !== b.indexOf("questPosition") && (a = c.posArr.indexOf(String(a)), c[b] = Number(d[a]))
          });
          c.posArr = d;
          b = r(c);
          f.model.set(b);
          y(f.model.toJSON(), p)
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    N = C.View.extend(
    {
      className: "deckSelectInner",
      events: function()
      {
        var b = {};
        b[a.cgti + " .deckSelectDetail"] = this.deckSelect;
        return b
      },
      initialize: function(a)
      {
        this.listenTo(this.model, "change", this.render);
        this.listenTo(this.parentView, "removeView", this.removeView)
      },
      render: function()
      {
        g.each(this.model.toJSON(), function(b, c)
        {
          c = g.findWhere(a.storage.userCardListEx.toJSON(),
          {
            userCardId: b.questEpisodeUserCardId
          });
          b.userCardId1 && (b.leaderCardModel = c || null)
        });
        this.$el.html(this.template(
        {
          model: this.model.toJSON(),
          img: a.imgData
        }));
        return this
      },
      deckSelect: function(b)
      {
        b.preventDefault();
        a.isScrolled() || this.deckViewCreate(b.currentTarget.dataset.decktype)
      },
      deckViewCreate: function(b)
      {
        b = Number(b);
        var c = {
          deckType: b,
          formationSheetId: 111,
          formationSheet: g.findWhere(t.userFormationSheetList,
          {
            formationSheetId: 111
          }).formationSheet,
          name: "队伍" + String(b).slice(-1)
        };
        b = a.storage.userDeckList.findWhere(
        {
          deckType: b
        }) ? a.storage.userDeckList.findWhere(
        {
          deckType: b
        }).toJSON() : c;
        p = b = r(b);
        w = p.deckType;
        f.model.clear(
        {
          silent: !0
        });
        f.model.set(b);
        f.bonusTextUpdate();
        k.getBaseData(a.getNativeObj());
        setTimeout(function()
        {
          a.removeClass(a.doc.querySelector("#DeckFormation"), "deckChange");
          a.removeClass(a.doc.querySelector("#deckFooter .default"), "noneDisp");
          a.removeClass(a.doc.querySelector("#globalBackBtn"), "noneDisp");
          a.removeClass(a.doc.querySelector("#menu"), "noneDisp")
        }, 0)
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    L = C.View.extend(
    {
      bonusTextUpdate: function()
      {
        a.doc.querySelector("#bonusTextWrap").innerHTML = "";
        var b = this.model.toJSON(),
          c = {};
        g.each(b.userCardObj, function(a, b)
        {
          a.eventEffect && g.each(a.eventEffect, function(a, b)
          {
            b in c || (c[b] = 0);
            c[b] += a | 0
          })
        });
        var d = {
            DROPADD: "个数"
          },
          e = {
            DROPADD: "＋"
          },
          h = {
            DROPADD: "个"
          };
        0 !== Object.keys(c).length ? g.each(c, function(b, c)
        {
          var l = c.split("_"),
            g = l[0];
          l.shift();
          l = l.join("_").toLowerCase();
          if (!a.doc.querySelector("." + c))
          {
            var q = document.createElement("span"),
              f = document.createElement("span"),
              B = document.createElement("span"),
              k = document.createElement("span");
            q.className = "bonusText " + c;
            f.className = "bonusIcon";
            f.style.cssText = "background:url('/magica/resource/image_web/common/icon/event/icon_" + l + "_f.png') left top no-repeat; background-size:26px 26px;";
            B.className = "iconText ts_gold";
            B.innerText = d[g];
            k.className = "text ts_pink02";
            q.appendChild(f);
            q.appendChild(B);
            q.appendChild(k);
            a.doc.querySelector("#bonusTextWrap").appendChild(q)
          }
          b /= 1E3;
          a.doc.querySelector("." + c + " .text").textContent = e[g] + b + h[g]
        }) : a.doc.querySelector("#bonusTextWrap").innerHTML = ""
      },
      className: function()
      {
        var b = "deckViewWrap";
        return b = a.holdDeck && a.holdDeck.deckType == w ? b + " memoriaEquipMode charaStatusMode" : b + " charaStatusMode"
      },
      initialize: function(b)
      {
        this.selectPos = this.selectModel = null;
        console.log("common.holdDeck:", a.holdDeck);
        b = a.holdDeck && a.holdDeck.deckType == w ? a.holdDeck : this.model.toJSON();
        b = r(b);
        console.log("deckView:", b);
        this.model.clear(
        {
          silent: !0
        });
        this.model.set(b);
        this.listenTo(this.model, "change", this.changeRender);
        this.listenTo(this, "timer", this.timer);
        this.listenTo(this.parentView, "removeView", this.removeView)
      },
      timer: function()
      {
        var b = g.clone(this.model.toJSON());
        !a.doc.querySelector("#charaListWrap").classList.contains("open") && a.doc.querySelector(".recoveryWrap") && (g.each(b.userCardObj, function(a, b)
        {
          console.log(a);
          a.reviveAtDisp = D(x, a.revivedAt);
          a.reviveAtDisp || (a.isDeath = !1)
        }), this.changeRender())
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model.toJSON(),
          deckCatType: u,
          img: a.imgData
        }));
        return this
      },
      changeRender: function()
      {
        this.$el.html(this.template(
        {
          model: this.model.toJSON(),
          deckCatType: u,
          img: a.imgData
        }));
        return this
      },
      events: function()
      {
        var b = {};
        b[a.cgti + " .deckParts"] = this.deckSet;
        b[a.cgti + " .epSetBtn"] = this.leaderSet;
        b[a.cgti + " .deckName"] = this.nameChange;
        b[a.cgti + " .deckChangeArrow"] = this.deckChange;
        b[a.cgti + " .deckChangeModeBtn"] = this.deckChangeMode;
        b[a.cgti + " .memoriaWrap span"] = this.pieceEquip;
        b[a.cgti + " .memoriaWrap .memoriaSetEquipBtn"] = this.memoriaSetEquipLink;
        b["touchstart .tapArea"] = this.popupTimeStart;
        b["touchstart .memoriaSkillWrap"] = this.popupTimeStart;
        b["touchstart .memoriaWrap .equiped"] = this.memoriaPopupTimeStart;
        return b
      },
      deckSet: function(b, c)
      {
        if (!a.doc.querySelector(".deckViewWrap").classList.contains("memoriaEquipMode") && !a.detailView)
        {
          var d = null;
          if (b)
          {
            b.preventDefault();
            if (a.isScrolled()) return;
            d = b.currentTarget.dataset.posindex;
            k.startSe(1002)
          }
          F.popupTimerStop();
          var e = g.clone(this.model.toJSON()),
            h = g.clone(e.userCardObj),
            f = g.clone(e.userPieceObj),
            n = d ? h["place" + d] : g.clone(c.model.toJSON());
          if (this.selectModel || this.selectPos)
          {
            if (d) h["place" + d] = this.selectModel, h["place" + this.selectPos] = n || null, c = b = null, f["place" + d] && (b = g.clone(f["place" + d])), f["place" + this.selectPos] && (c = g.clone(f["place" + this.selectPos])), c ? f["place" + d] = c : delete f["place" + d], b ? f["place" + this.selectPos] = b : delete f["place" + this.selectPos];
            else if (this.selectModel && n.userCardId == this.selectModel.userCardId) h["place" + this.selectPos] = null;
            else
            {
              var l = null;
              g.each(h, function(a, b)
              {
                var c = !1;
                a && a.userCardId == n.userCardId && (c = !0);
                c && (h[b] = null, l = b)
              });
              h["place" + this.selectPos] = n;
              d = null;
              f[l] && (d = g.clone(f[l]));
              d && (f["place" + this.selectPos] = d)
            }
            for (d = 0; 10 > d;) delete e["userCardId" + (d + 1)], delete e["questPositionId" + (d + 1)], d = d + 1 | 0;
            for (d = 0; 10 > d;)
            {
              b = "userPieceId" + ("00" + (d + 1)).slice(-2);
              for (c = 0; 4 > c;) delete e[b + (c + 1)], c = c + 1 | 0;
              d = d + 1 | 0
            }
            var m = 1;
            g.each(h, function(a, b)
            {
              var c = b.split("place")[1];
              if (a && a.support && 20 !== e.deckType) e.questPositionHelper = Number(c);
              else if (a)
              {
                var d = "questPositionId" + m,
                  l = "userCardId" + m,
                  h = "userPieceId" + ("00" + m).slice(-2);
                e[d] = Number(c);
                e[l] = a.userCardId;
                g.each(f[b], function(a, b)
                {
                  a && a.id && (e[h + (b + 1)] = a.id)
                });
                m++
              }
            });
            e.userCardObj = h;
            e.userPieceObj = f;
            20 !== e.deckType && (e = S(e));
            e = r(e);
            this.model.clear(
            {
              silent: !0
            });
            this.model.set(e);
            y(this.model.toJSON(), p);
            k.getBaseData(a.getNativeObj());
            this.selectModel = this.selectPos = null;
            a.removeClass(a.doc.querySelector(".deckParts.select"), "select");
            20 == this.model.toJSON().deckType ? (a.doc.querySelector("#charaListWrap").className = "", a.removeClass(a.doc.querySelector(".deckPartsWrap"), "tapBlock")) : a.removeClass(a.doc.querySelector("#charaListWrap"), "open")
          }
          else if (a.removeClass(a.doc.querySelector(".deckParts.select"), "select"), a.removeClass(a.doc.querySelector("#charaListWrap"), "open"), this.selectPos = d, this.selectModel = g.clone(n), a.addClass(b.currentTarget, "select"), this.selectModel && !this.selectModel.support || !this.selectModel) v.charaListView.cardSort.multiSort(), ca(), a.addClass(a.doc.querySelector("#charaListWrap"), "open"), a.scrollRefresh(null, null, !0, null)
        }
      },
      leaderSet: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled() && (b.stopPropagation(), F.popupTimerStop(), G.popupTimerStop(), b = b.currentTarget, !b.classList.contains("on")))
        {
          k.startSe(1008);
          var c = g.clone(this.model.toJSON());
          c.questEpisodeUserCardId = c.userCardObj["place" + Number(b.parentNode.dataset.posindex)].userCardId;
          c = S(c);
          c = r(c);
          this.model.set(c);
          y(this.model.toJSON(), p);
          k.getBaseData(a.getNativeObj());
          this.selectModel = this.selectPos = null;
          a.removeClass(a.doc.querySelector(".deckParts.select"), "select");
          a.removeClass(a.doc.querySelector("#charaListWrap"), "open")
        }
      },
      nameChange: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled() && !a.doc.querySelector(".deckParts.select"))
        {
          var c = this;
          b = $("#DeckNameChangeTemp").text();
          var d = f.model.toJSON();
          d.popupType = "typeC";
          var e = new a.PopupClass(d, b, function()
          {
            a.nativeKeyBoard("commentInput", 10, null, "textCount");
            a.doc.getElementById("commentDecide").addEventListener(a.cgti, function(b)
            {
              b.preventDefault();
              a.isScrolled() || (a.tapBlock(!0), c.model.set(
              {
                name: a.doc.getElementById("commentInput").value
              }), y(c.model.toJSON(), p), k.getBaseData(a.getNativeObj()), e.remove(), a.tapBlock(!1))
            })
          })
        }
      },
      deckChange: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled() && !a.doc.querySelector(".deckViewWrap").classList.contains("deckChangeBg"))
        {
          this.selectModel = this.selectPos = null;
          a.removeClass(a.doc.querySelector(".deckParts.select"), "select");
          a.removeClass(a.doc.querySelector("#charaListWrap"), "open");
          var c = p.deckType;
          b = b.currentTarget.classList.contains("arrowR") ? 1 : -1;
          c += b;
          c = 35 < c ? 31 : c;
          c = 31 > c ? 35 : c;
          b = {
            deckType: c,
            formationSheetId: 111,
            formationSheet: g.findWhere(t.userFormationSheetList,
            {
              formationSheetId: 111
            }).formationSheet,
            name: "队伍" + String(c).slice(-1)
          };
          b = a.storage.userDeckList.findWhere(
          {
            deckType: c
          }) ? a.storage.userDeckList.findWhere(
          {
            deckType: c
          }).toJSON() : b;
          p = b = r(b);
          w = c;
          this.model.clear(
          {
            silent: !0
          });
          this.model.set(b);
          f.bonusTextUpdate();
          a.removeClass(a.doc.querySelector(".deckViewWrap"), "memoriaEquipMode");
          a.removeClass(a.doc.querySelector("#pieceEquipBtn"), "on");
          k.getBaseData(a.getNativeObj())
        }
      },
      deckChangeMode: function(b)
      {
        b.preventDefault();
        a.isScrolled() || a.doc.querySelector(".deckViewWrap").classList.contains("deckChangeBg") || (this.selectModel = this.selectPos = null, a.removeClass(a.doc.querySelector(".deckParts.select"), "select"), a.removeClass(a.doc.querySelector("#charaListWrap"), "open"), setTimeout(function()
        {
          a.addClass(a.doc.querySelector("#DeckFormation"), "deckChange");
          a.addClass(a.doc.querySelector("#deckFooter .default"), "noneDisp");
          a.addClass(a.doc.querySelector("#globalBackBtn"), "noneDisp");
          a.addClass(a.doc.querySelector("#menu"), "noneDisp")
        }, 0))
      },
      pieceEquip: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled() && (b.stopPropagation(), G.popupTimerStop(), !(a.detailPopup || b.currentTarget.parentNode.parentNode.classList.contains("support") && "quest" == u) && (b.currentTarget.classList.contains("canEquip") || b.currentTarget.classList.contains("equiped") || b.currentTarget.classList.contains("tapBlock"))))
        {
          k.startSe(1002);
          var c = Number(b.currentTarget.parentNode.parentNode.dataset.posindex),
            d = Number(b.currentTarget.dataset.pieceindex),
            e = Number(b.currentTarget.parentNode.parentNode.dataset.charaid),
            h = b.currentTarget.parentNode.parentNode.dataset.charaname;
          b = b.currentTarget.parentNode.parentNode.dataset.charaatt;
          var f = this.model.toJSON().userPieceObj["place" + c] || [],
            n = 0 < f.length ? f[d - 1] : null,
            l = a.storage.userCardListEx.findWhere(
            {
              charaId: e
            }).toJSON().revision,
            m = {},
            q = this;
          g.each(this.model.toJSON().userPieceObj, function(a, b)
          {
            g.each(a, function(a, c)
            {
              a && a.id && (m[a.id] = {
                name: q.model.toJSON().userCardObj[b].chara.name,
                charaId: q.model.toJSON().userCardObj[b].card.miniCharaNo
              }, q.model.toJSON().userCardObj[b].chara.title && (m[a.id].name += " " + q.model.toJSON().userCardObj[b].chara.title))
            })
          });
          a.equipInfo = {
            charaName: h,
            charaId: e,
            charaAtt: b,
            posIndex: c,
            pieceIndex: d,
            pieceArr: f,
            pieceModel: n,
            allPiece: m,
            selectPieceId: n ? n.id : null,
            revision: l
          };
          a.holdDeck = this.model.toJSON();
          location.href = "#/MemoriaEquip"
        }
      },
      memoriaSetEquipLink: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          var c = Number(b.currentTarget.parentNode.parentNode.dataset.posindex),
            d = Number(b.currentTarget.parentNode.parentNode.dataset.charaid),
            e = b.currentTarget.parentNode.parentNode.dataset.charaname;
          b = b.currentTarget.parentNode.parentNode.dataset.charaatt;
          var h = this.model.toJSON().userPieceObj["place" + c] || [],
            f = a.storage.userCardListEx.findWhere(
            {
              charaId: d
            }).toJSON().revision,
            k = {},
            l = this;
          g.each(this.model.toJSON().userPieceObj, function(a, b)
          {
            g.each(a, function(a, c)
            {
              a && a.id && (k[a.id] = {
                name: l.model.toJSON().userCardObj[b].chara.name,
                charaId: l.model.toJSON().userCardObj[b].card.miniCharaNo
              }, l.model.toJSON().userCardObj[b].chara.title && (k[a.id].name += " " + l.model.toJSON().userCardObj[b].chara.title))
            })
          });
          a.equipInfo = {
            charaName: e,
            charaId: d,
            charaAtt: b,
            posIndex: c,
            pieceIndex: 0,
            pieceArr: h,
            pieceModel: null,
            allPiece: k,
            selectPieceId: null,
            revision: f
          };
          a.holdDeck = this.model.toJSON();
          location.href = "#/MemoriaSetEquip"
        }
      },
      popupTimeStart: function(b)
      {
        var c = this.model.toJSON(),
          d = c.userCardObj["place" + b.currentTarget.parentNode.dataset.posindex];
        if ((!d || !d.isNpc) && d && d.card)
        {
          var e = this;
          b.currentTarget.classList.contains("memoriaSkillWrap") && (d.initTabType = "memoria");
          a.holdDeck && (d.linkBlock = !0);
          d.deckFormationFlag = !0;
          F.cardDetailPopup(b, d, function()
          {
            if (a.storage.userCardListEx)
            {
              var b = r(c);
              e.model.clear(
              {
                silent: !0
              });
              e.model.set(b);
              k.getBaseData(a.getNativeObj())
            }
            e.selectModel = null;
            e.selectPos = null;
            a.removeClass(a.doc.querySelector("#charaListWrap"), "open")
          })
        }
      },
      memoriaPopupTimeStart: function(b)
      {
        var c = this.model.toJSON(),
          d = b.currentTarget.parentNode.parentNode.dataset.posindex,
          e = b.currentTarget.dataset.pieceindex,
          h = c.userPieceObj["place" + d][e - 1],
          g = c.userCardObj["place" + d];
        !a.tutorialId && h && (h = c.userPieceObj["place" + d][e - 1], g.supportFlag && 20 !== u ? (h.supportFlag = !0, h.btnHide = !0) : (c = (c = a.storage.userPieceList.findWhere(
        {
          id: h.id
        })) ? c.toJSON() : null, h.protect = c ? c.protect : h.protect), G.cardDetailPopup(b, h))
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    ca = function()
    {
      T();
      a.removeClass(a.doc.querySelector("#charaListElms .select"), "select");
      a.removeClass(a.doc.querySelector("#charaListElms .formationRemove"), "formationRemove");
      g.each([].slice.call(a.doc.querySelectorAll("#charaListElms .formationCurrent")), function(b)
      {
        a.removeClass(b, "formationCurrent")
      });
      g.each(f.model.toJSON().userCardObj, function(b, c)
      {
        b.card && (f.selectModel && f.selectModel.userCardId == b.userCardId ? (a.addClass(a.doc.querySelector(".userCardId" + f.selectModel.userCardId), "formationRemove"), a.addClass(a.doc.querySelector(".userCardId" + f.selectModel.userCardId), "select")) : a.addClass(a.doc.querySelector(".userCardId" + b.userCardId), "formationCurrent"))
      })
    },
    T = function()
    {
      a.storage.userCardListEx.each(function(b)
      {
        var c = g.clone(b.toJSON()),
          d = a.doc.querySelector("#charaListElms .userCardId" + c.userCardId);
        if (d.querySelector(".gauge")) c.isDeath && (c.revivedAtDisp = D(x, c.revivedAt), c.isDeath = c.revivedAtDisp ? !0 : !1, b.clear(
        {
          silent: !0
        }), b.set(c,
        {
          silent: !0
        }), c.isDeath || (b = d.querySelector(".gauge"), e = g.template($("#gaugeTemp").text()), e(
        {
          model: c
        }), $(b).html(e(
        {
          model: c
        })), a.removeClass(d, "death")));
        else
        {
          b = a.doc.createElement("span");
          b.className = "gauge";
          var e = g.template($("#gaugeTemp").text());
          e(
          {
            model: c
          });
          $(b).html(e(
          {
            model: c
          }));
          d.appendChild(b);
          c.isDeath && a.addClass(d, "death")
        }
      });
      !a.doc.querySelector(".userCharaIcon.death") && A && (clearInterval(A), A = null)
    },
    S = function(a)
    {
      var b = g.clone(a),
        d = !1;
      g.each(b.userCardObj, function(a, c)
      {
        a && a.userCardId && a.userCardId == b.questEpisodeUserCardId && (d = !0)
      });
      if (!d)
      {
        var e = null;
        g.each(b.userCardObj, function(a, b)
        {
          !e && a && a.card && !a.supportFlag && (e = a.userCardId)
        });
        b.questEpisodeUserCardId = e
      }
      return b
    },
    y = function(b, c)
    {
      var d = !1;
      g.each(b, function(a, h)
      {
        if ("formationSheetId" == h || "name" == h || "questEpisodeUserCardId" == h || "questPositionHelper" == h || -1 !== h.indexOf("questPositionId") || -1 !== h.indexOf("userCardId") || -1 !== h.indexOf("userPieceId")) d = b[h] !== c[h] ? !0 : d
      });
      g.each(c, function(a, h)
      {
        if ("formationSheetId" == h || "name" == h || "questEpisodeUserCardId" == h || "questPositionHelper" == h || -1 !== h.indexOf("questPositionId") || -1 !== h.indexOf("userCardId") || -1 !== h.indexOf("userPieceId")) d = b[h] !== c[h] ? !0 : d
      });
      f.bonusTextUpdate();
      console.log("deckCatType", u);
      d ? (a.addClass(a.doc.querySelector(".deckViewWrap"), "deckChangeBg"), a.doc.querySelector("#sideMenu").className = "anim" == a.doc.querySelector("#sideMenu").className ? "close" : "", a.androidKeyStop = !0, a.holdDeck = b, setTimeout(function()
      {
        a.addBackHandler(a.pageObj.deckChangeConf)
      }, 0), "quest" == u ? (a.addClass(a.doc.querySelector("#nextPageBtn"), "noneDisp"), a.removeClass(a.doc.querySelector("#mainBtn"), "noneDisp"), a.removeClass(a.doc.querySelector("#mainBtn"), "off"), a.addClass(a.doc.querySelector(".recoveryLink"), "hide")) : a.removeClass(a.doc.querySelector("#mainBtn"), "off")) : (a.removeClass(a.doc.querySelector(".deckViewWrap"), "deckChangeBg"), a.removeBackHandler(), a.androidKeyStop = !1, a.holdDeck = null, "quest" == u ? (a.removeClass(a.doc.querySelector("#nextPageBtn"), "noneDisp"), a.addClass(a.doc.querySelector("#mainBtn"), "noneDisp"), a.addClass(a.doc.querySelector("#mainBtn"), "off"), a.removeClass(a.doc.querySelector(".recoveryLink"), "hide")) : a.addClass(a.doc.querySelector("#mainBtn"), "off"));
      f.selectModel = null;
      f.selectPos = null;
      a.removeClass(a.doc.querySelector("#charaListWrap"), "open");
      return d
    },
    da = function()
    {
      w = null;
      u && "quest" != u || (w = a.currentEventDeckType ? a.currentEventDeckType : a.userEventAccomplish && a.userEventAccomplish.deckType ? a.userEventAccomplish.deckType : 31);
      var b = a.storage.userDeckList.findWhere(
      {
        deckType: w
      });
      b ? p = r(b.toJSON()) : (b = {
        deckType: w,
        formationSheetId: 111,
        formationSheet: g.findWhere(t.userFormationSheetList,
        {
          formationSheetId: 111
        }).formationSheet,
        name: "队伍" + String(w).slice(-1)
      }, p = r(b))
    },
    Q = function()
    {
      var b = [];
      console.log(a.storage.userDeckList.toJSON());
      g.each(a.storage.userDeckList.toJSON(), function(a, c)
      {
        if (31 <= a.deckType && 35 >= a.deckType)
        {
          var d = [];
          g.each(a.formationSheet, function(a, b)
          {
            -1 !== b.indexOf("placeSkillId") && d.push(b.split("placeSkillId")[1])
          });
          a.posArr = d;
          b.push(a)
        }
      });
      for (var c = 0; 5 > c;)
      {
        var d = "3" + (c + 1);
        g.findWhere(b,
        {
          deckType: Number(d)
        }) || b.push(
        {
          deckType: Number(d)
        });
        c = c + 1 | 0
      }
      b.sort(function(a, b)
      {
        return a.deckType < b.deckType ? -1 : a.deckType > b.deckType ? 1 : 0
      });
      return b
    },
    r = function(b)
    {
      console.log("deckDataCreate");
      console.log("_model.formationSheet", b);
      var c = g.clone(b);
      if (!c.name && 31 <= b.deckType && 35 >= b.deckType)
      {
        var d = "队伍" + String(b.deckType).slice(-1);
        c.name = d
      }
      var e = {},
        h = [];
      g.each(c.formationSheet, function(a, b)
      {
        if (-1 !== b.indexOf("placeSkill") && -1 === b.indexOf("placeSkillId"))
        {
          h.push(b.split("placeSkill")[1]);
          var c = null;
          a.art1 && (c = [a.viewAttributeId]);
          e[b] = c;
          console.log("key", b, " val", a)
        }
      });
      c.placeEffect = e;
      c.posArr = h;
      console.log("_model.placeEffect", c.placeEffect);
      console.log("_model.placeEffect", c.posArr);
      var f = {};
      c.leaderPos = null;
      g.each(c.posArr, function(d, e)
      {
        d = "userCardId" + (e + 1);
        if (c[d])
        {
          d = c[d];
          d = g.findWhere(a.storage.userCardListEx.toJSON(),
          {
            id: d
          });
          d.userCardId == c.questEpisodeUserCardId && (c.leaderPos = Number(b["questPositionId" + (e + 1)]));
          if (!d.revivedAt)
          {
            var l = a.userEventAccomplishCharaArr[d.charaId];
            a.userEventAccomplishCharaArr[d.charaId] ? (d.damage = l.damage, d.mp = l.mp, d.dp = 0, 0 < l.mp && (d.mp = Math.floor(l.mp / 10), 0 == d.mp && (d.mp = 1)), 100 < d.mp && (d.dp = d.mp - 100, d.mp = 100), d.isDeath = !1, l.revivedAt ? a.periodCheck(t.currentTime, l.revivedAt) ? d.revivedAt = null : (d.isDeath = !0, d.revivedAt = l.revivedAt, d.reviveAtDisp = D(x, d.revivedAt), console.log(d.reviveAtDisp), E.push(b)) : d.revivedAt = null) : (d.damage = 0, d.mp = 0, d.dp = 0, d.revivedAt = null)
          }
          d.reviveAtDisp = D(x, d.revivedAt);
          d.isDeath = d.reviveAtDisp ? !0 : !1;
          f["place" + c["questPositionId" + (e + 1)]] = d
        }
      });
      c.userCardObj = f;
      var k = {};
      g.each(c.posArr, function(d, e)
      {
        if (b["questPositionId" + (e + 1)])
        {
          d = "place" + b["questPositionId" + (e + 1)];
          var l = "userPieceId" + ("00" + (e + 1)).slice(-2),
            f = c.userCardObj[d],
            h = f ? f.revision + 1 : 0;
          for (e = 0; 4 > e;)
          {
            var m = l + (e + 1);
            if (c[m])
            {
              0 == d in k && (k[d] = []);
              var m = g.findWhere(a.storage.userPieceList.toJSON(),
                {
                  id: c[m]
                }),
                n = !1;
              0 >= h && (n = "invalidRev");
              m.piece.charaList && (g.findWhere(m.piece.charaList,
              {
                charaId: f.charaId | 0
              }) || (n = "invalidChara"));
              "ALL" !== m.piece.attributeId && m.piece.attributeId !== f.chara.attributeId && (n = "invalidAtt");
              console.log(m);
              h--;
              m.maxLevel = Y.getMaxLevel(m.piece.rank, m.lbCount);
              m.invalidFlag = n;
              k[d][e] = m
            }
            else h--;
            e = e + 1 | 0
          }
        }
      });
      c.userPieceObj = k;
      g.each(c.userCardObj, function(a, b)
      {
        c.userPieceObj[b] && (g.each(c.userPieceObj[b], function(b, c)
        {
          b && (a["equipPiece" + (c + 1)] = b)
        }), a = O.totalEventEffectSet(a))
      });
      console.log(a.userEventAccomplishCharaList);
      g.each(c.userCardObj, function(b, d)
      {
        b.composeAttribute = a.getTargetComposeAttribute(
        {
          attributeId: b.chara.attributeId
        });
        b.supportFlag || (b.addHp = b.hp ? b.hp : 0, b.addAttack = b.attack ? b.attack : 0, b.addDefense = b.defense ? b.defense : 0, b.memoriaHp = 0, b.memoriaAttack = 0, b.memoriaDefense = 0, c.userPieceObj[d] && g.each(c.userPieceObj[d], function(a)
        {
          a && !a.invalidFlag && (b.addHp += a.hp, b.addAttack += a.attack, b.addDefense += a.defense, b.memoriaHp += a.hp, b.memoriaAttack += a.attack, b.memoriaDefense += a.defense)
        }))
      });
      return c
    },
    U = function(b)
    {
      a.acpTimeCure && (clearInterval(a.acpTimeCure), a.acpTimeCure = null);
      var c = null;
      b.userQuestBattleResultList[0] && b.userQuestBattleResultList[0].questBattle && b.userQuestBattleResultList[0].questBattle.sectionId && (c = {
        resultUrl: "/magica/index.html#/QuestResult",
        retireUrl: "/magica/index.html#/EventAccomplishTop"
      });
      k.setWebView(!1);
      k.startQuest(b.userQuestBattleResultList[0].id, c)
    },
    aa = function(b, c, d, e)
    {
      $(a.ready.target).on("webkitAnimationEnd", function()
      {
        k.changeBg("web_black.jpg");
        $(a.ready.target).off();
        $(a.ready.target).on("webkitAnimationEnd", function(b)
        {
          "readyFadeOut" == b.originalEvent.animationName && (a.ready.target.className = "")
        });
        var f = !0;
        a.questBattleModel.storyForceStart || (g.each(c, function(a)
        {
          b === a.adventureId && (f = !1)
        }), b || (f = !1));
        k.endL2d();
        var p = null;
        if (window.isBrowser) a.stubQuest = d, k.sendCommand("QuestStub");
        else
        {
          if (f)
          {
            var n = function(c)
              {
                $("#commandDiv").on("nativeCallback", function(d, e)
                {
                  $("#commandDiv").off();
                  e && e.isSkipped && (d = {}, d.adventureId = String(b), z.ajaxPost(a.linkList.adventureSkip, d, function(b)
                  {
                    a.responseSetStorage(b)
                  }));
                  $("#commandDiv").on("nativeCallback", function(a, b)
                  {
                    $("#commandDiv").off();
                    P(b);
                    location.href = "#/QuestBackground"
                  });
                  U(c)
                })
              },
              p = function(a)
              {
                var c = String(b);
                e && (c += "_" + e);
                setTimeout(function()
                {
                  k.setWebView(!1);
                  n(a);
                  k.startStory(c)
                }, 500)
              };
            $("#popupArea").on(a.cgti, "#resultCodeError .popupCloseBtn", function(b)
            {
              b.preventDefault();
              a.isScrolled() || ($("#popupArea").off(), k.nativeReload("#/TopPage"))
            })
          }
          else p = function(a)
          {
            setTimeout(function()
            {
              k.setWebView(!1);
              $("#commandDiv").on("nativeCallback", function(a, b)
              {
                $("#commandDiv").off();
                P(b);
                location.href = "#/QuestBackground"
              });
              U(a)
            }, 500)
          }, $("#popupArea").on(a.cgti, "#resultCodeError .popupCloseBtn", function(b)
          {
            b.preventDefault();
            a.isScrolled() || ($("#popupArea").off(), k.nativeReload("#/TopPage"))
          });
          z.ajaxPost(a.linkList.questStart, d, p)
        }
      });
      a.addClass(a.ready.target, "preNativeFadeIn")
    },
    E = [],
    A = null,
    ea = function()
    {
      E = [];
      O.createCardList();
      a.storage.userCardListEx.each(function(b)
      {
        var c = b.toJSON(),
          d = a.userEventAccomplishCharaArr[c.charaId];
        a.userEventAccomplishCharaArr[c.charaId] ? (c.damage = d.damage, c.mp = d.mp, c.dp = 0, 0 < d.mp && (c.mp = Math.floor(d.mp / 10), 0 == c.mp && (c.mp = 1)), 100 < c.mp && (c.dp = c.mp - 100, c.mp = 100), c.isDeath = !1, d.revivedAt ? a.periodCheck(t.currentTime, d.revivedAt) ? c.revivedAt = null : (c.isDeath = !0, c.revivedAt = d.revivedAt, c.reviveAtDisp = D(x, c.revivedAt), console.log(c.reviveAtDisp), E.push(b)) : c.revivedAt = null) : (c.damage = 0, c.mp = 0, c.dp = 0, c.revivedAt = null);
        b.clear(
        {
          silent: !0
        });
        b.set(c,
        {
          silent: !0
        })
      });
      t = z.getPageJson();
      da();
      a.setStyle(W + X);
      v = new ba;
      v.charaListView = new Z(
      {
        model: new H,
        collection: a.storage.userCardListEx
      });
      a.content.append(v.charaListView.render().el);
      T();
      a.scrollSetX("charaListScrollWrap", "list");
      k.getBaseData(a.getNativeObj());
      0 <= E.length && (A = setInterval(function()
      {
        x += 1E3;
        f.trigger("timer")
      }, 1E3))
    },
    D = function(a, c)
    {
      c = (new Date(c)).getTime();
      var b = c - a,
        e = b / 36E5 | 0,
        b = b % 36E5,
        f = b / 6E4 | 0,
        b = b % 6E4 / 1E3 | 0,
        e = 0 < e ? e + ":" + ("0" + f).slice(-2) + ":" + ("0" + b).slice(-2) : f + ":" + ("0" + b).slice(-2);
      c < a && (e = !1);
      return e
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
      id: "userPieceArchiveList"
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
      id: "userCharaEnhancementCellList"
    },
    {
      id: "userCharaAtbEnhancementCellList"
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
      z.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      t = z.getPageJson();
      J = g.findWhere(t.eventList,
      {
        eventType: "ACCOMPLISH"
      });
      x = (new Date(t.currentTime)).getTime();
      a.userEventAccomplishCharaArr || (a.userEventAccomplishCharaArr = {}, a.storage.userCharaList.each(function(b)
      {
        b = b.toJSON();
        a.userEventAccomplishCharaArr[b.charaId] = {
          charaId: b.charaId,
          damage: 0,
          mp: 0,
          eventId: J.eventId
        }
      }));
      console.log("common.userEventAccomplishCharaArr", a.userEventAccomplishCharaArr);
      u = "quest";
      ea()
    },
    charaSelect: function(a, c)
    {
      c || f.deckSet(null, a)
    },
    deckChangeConf: function(b)
    {
      b && b.type && (b = null);
      var c = new a.PopupClass(
      {
        canClose: !1,
        title: "结束队伍编成",
        content: "要保存魔法少女·记忆结晶装备的更改</br>并结束队伍编成吗?",
        closeBtnText: "放弃变更并退出",
        decideBtnText: "保存变更并退出"
      }, null, function()
      {
        $("#popupArea .popupCloseBtn").on(a.cgti, function()
        {
          $("#popupArea .popupCloseBtn").off();
          var d = r(p);
          f.model.clear(
          {
            silent: !0
          });
          f.model.set(d);
          y(f.model.toJSON(), p);
          c.remove();
          a.holdDeck = null;
          k.getBaseData(a.getNativeObj());
          f.selectModel = null;
          f.selectPos = null;
          a.removeClass(a.doc.querySelector("#charaListWrap"), "open");
          b && b()
        });
        $("#popupArea .decideBtn").on(a.cgti, function()
        {
          $("#popupArea .decideBtn").off();
          v.deckSave();
          c.remove();
          f.selectModel = null;
          f.selectPos = null;
          a.removeClass(a.doc.querySelector("#charaListWrap"), "open");
          b && b()
        });
        v.deckChangeFlag = !1
      })
    },
    awakeSuspend: function(a)
    {
      console.log(a);
      x = (new Date(a)).getTime()
    },
    remove: function(b)
    {
      v && (a.removeBackHandler(), F.popupTimerStop(), G.popupTimerStop(), a.currentEventDeckType = f.model.toJSON().deckType, v.charaListView.trigger("remove"), v.charaListView.remove(), v.trigger("removeView"), v.remove());
      J = t = null;
      a.removeClass(a.doc.querySelector("#globalMenuContainer"), "questFormation");
      p = w = u = null;
      K = !1;
      x = null;
      A && clearInterval(A);
      E = A = null;
      I && clearInterval(I);
      t = I = null;
      b()
    }
  }
});
