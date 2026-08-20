define("underscore backbone backboneCommon ajaxControl command text!template/event/singleraid/EventSingleRaidTop.html text!template/event/singleraid/EventSingleRaidSelect.html text!css/event/singleraid/EventSingleRaidTop.css text!css/quest/QuestCommon.css js/view/quest/QuestListPartsView QuestUtil".split(" "), function(f, B, a, C, d, R, S, T, U, D, V)
{
  var E = 0,
    F = 0,
    x = 0,
    W = function()
    {
      if (window.isBrowser && window.isDebug)
      {
        var b = a.doc.createDocumentFragment();
        f.each(k.pointList, function(c)
        {
          var e, d = !0;
          f.each(r, function(a)
          {
            a.pointModel.pointId == c.pointId && (a.canPlay || (d = !1), e = a.pointModel)
          });
          var g = document.createElement("div");
          "BOSS" == e.point.pointType ? g.className = "debugMapBtn sb_gold_01 TE" : "EXTRA_BOSS" == e.point.pointType ? g.className = "debugMapBtn sb_gold_01 TE" : "LARGE" == e.point.pointType ? g.className = "debugMapBtn sb_gold_02 TE" : "SMALL" == e.point.pointType ? g.className = "debugMapBtn sb_pink TE" : "CHALLENGE" == e.point.pointType && (g.className = "debugMapBtn sb_pink TE");
          d || a.addClass(g, "off");
          g.dataset.id = e.pointId;
          g.textContent = e.point.areaNo + "-" + e.point.areaSubNo;
          b.appendChild(g)
        });
        a.doc.getElementById("mapWrap").appendChild(b);
        $(".debugMapBtn").off();
        $(".debugMapBtn").on(a.cgti, function(b)
        {
          b.preventDefault();
          a.isScrolled() || (b.currentTarget.classList.contains("off") ? new a.PopupClass(
          {
            exClass: "openConditionPopup",
            popupType: "typeC",
            conditionList: A(b.currentTarget.dataset.id).pointModel.conditionDetailList
          }, $("#openConditionTemp").text(), null, function()
          {
            d.resumeEventSingleRaid()
          }) : ($(".debugMapBtn").off(), h.mapHide(A(b.currentTarget.dataset.id)), setTimeout(function()
          {
            $(".missionState").off();
            $(".missionState").on(a.cgti, function(b)
            {
              b.currentTarget.classList.contains("clearAnim") ? a.removeClass(b.currentTarget, "clearAnim") : ($("#areaMissionWrap .missionState").off("webkitAnimationEnd"), $("#areaMissionWrap .missionState").on("webkitAnimationEnd", function()
              {
                $("#areaMissionWrap .missionState").off("webkitAnimationEnd");
                setTimeout(function()
                {
                  a.addClass(a.doc.querySelector(".rewardWrap"), "clearAnim");
                  a.addClass(a.doc.querySelector("#areaMissionWrap .rewardWrap .title"), "clear")
                }, 300)
              }), a.addClass(b.currentTarget, "clearAnim"))
            });
            $(".rewardWrap").off();
            $(".rewardWrap").on(a.cgti, function(b)
            {
              b.currentTarget.classList.contains("clearAnim") ? a.removeClass(b.currentTarget, "clearAnim") : a.addClass(b.currentTarget, "clearAnim")
            })
          }, 1E3)))
        })
      }
    };
  B.Model.extend();
  var k, m, p, r, w, y, u, q = [],
    h, n, v = B.View.extend(
    {
      events: function()
      {
        var b = {};
        b[a.cgti + " #helpBtn"] = this.helpPopup;
        b[a.cgti + " #scaleChangePlus"] = this.scaleUp;
        b[a.cgti + " #scaleChangeMinus"] = this.scaleDown;
        b[a.cgti + " #resetPosition"] = this.resetPosition;
        if (window.isBrowser && window.isDebug) return b;
        b["touchstart #mapWrap"] = this.touchStart;
        b["touchmove #mapWrap"] = this.touchMove;
        b["touchend #mapWrap"] = this.touchEnd;
        return b
      },
      touchStart: function(b)
      {
        b.preventDefault();
        p && (a.tapEffectStop = !0, a.isDoubleTouch() ? (this.doubleTapFlg = !0, this.pinchStart(b)) : H(b, "START"))
      },
      touchMove: function(a)
      {
        a.preventDefault();
        p && (this.doubleTapFlg ? this.pinchMove(a) : H(a, "MOVE"))
      },
      touchEnd: function(b)
      {
        b.preventDefault();
        p && (a.tapEffectStop = !1, this.doubleTapFlg ? (this.pinchEnd(b), this.doubleTapFlg = !1) : H(b, "END"))
      },
      pinchStart: function(a)
      {
        a.preventDefault();
        a = M(a, "START");
        2 > a.length ? this.doubleTapFlg = !1 : this.startDistance = Math.sqrt(Math.pow(a[1].clientX - a[0].clientX, 2) + Math.pow(a[1].clientY - a[0].clientY, 2))
      },
      pinchMove: function(b)
      {
        b.cancelable && b.preventDefault();
        b = M(b, "MOVE");
        2 > b.length ? this.doubleTapFlg = !1 : (b = Math.sqrt(Math.pow(b[1].clientX - b[0].clientX, 2) + Math.pow(b[1].clientY - b[0].clientY, 2)), b = parseInt(a.eventSingleRaidScale + (b < this.startDistance ? -this.startDistance / b : b / this.startDistance)), a.eventSingleRaidScale = b, this.updateScale())
      },
      pinchEnd: function(a)
      {
        a.preventDefault();
        this.startDistance = null
      },
      initialize: function(b)
      {
        this.SCALE_MAX = 100;
        this.SCALE_MIN = 60;
        a.eventSingleRaidScale || (a.eventSingleRaidScale = this.SCALE_MAX);
        this.template = f.template(R);
        this.createDom()
      },
      render: function()
      {
        var b = k;
        a.setTitleCollectionObserved();
        b.areaCompCount = X();
        var c = null;
        if (m.viewParameterMap.ITEM_GAUGE_MAX)
        {
          var e = Number(m.viewParameterMap.ITEM_GAUGE_MAX);
          window.isLocal && (a.singleRaidGaugeItemNum = 0);
          this.newItemGaugeRatio = null;
          null != a.singleRaidGaugeItemNum && x > a.singleRaidGaugeItemNum ? (c = Math.round(a.singleRaidGaugeItemNum / e * 1E3) / 1E3 * 100, this.newItemGaugeRatio = Math.round(x / e * 1E3) / 1E3 * 100) : c = Math.round(x / e * 1E3) / 1E3 * 100;
          a.singleRaidGaugeItemNum = null;
          100 < c && (c = 100);
          this.newItemGaugeRatio && 100 < this.newItemGaugeRatio && (this.newItemGaugeRatio = 100)
        }
        b.itemGaugeRatio = c;
        this.$el.html(this.template(b));
        return this
      },
      createDom: function()
      {
        var b = this.render().el;
        p && a.addClass(b.querySelector("#EventSingleRaidTop"), "pageFadein");
        a.content.append(b);
        $("#commandDiv").off();
        I();
        p ? ($("#EventSingleRaidTop").off(), $("#EventSingleRaidTop").on("webkitAnimationEnd", function()
        {
          $("#EventSingleRaidTop").off();
          a.removeClass(a.doc.querySelector("#EventSingleRaidTop"), "pageFadein");
          a.tapBlock(!1);
          a.androidKeyStop = !1
        })) : (a.ready.hide(), p = !0);
        this.newItemGaugeRatio && (this.gaugeTimer = setTimeout(function()
        {
          if (-1 < location.hash.indexOf("#/EventSingleRaidTop"))
          {
            var b = a.doc.getElementById("itemGaugeInner");
            b && (b.style.height = this.newItemGaugeRatio + "%")
          }
        }.bind(this), 1E3));
        f.each(a.doc.querySelectorAll(".itemListWrap .itemWrap"), function(b)
        {
          var c = a.storage.userItemList.findWhere(
            {
              itemId: b.dataset.itemid.toUpperCase()
            }),
            c = c ? c.toJSON().quantity : 0;
          b.querySelector(".itemNum").textContent = "×" + c
        });
        this.updateScale();
        window.isBrowser && window.isDebug && W()
      },
      mapHide: function(b)
      {
        a.tapBlock(!0);
        a.androidKeyStop = !0;
        clearTimeout(this.gaugeTimer);
        $("#EventSingleRaidTop").off();
        $("#EventSingleRaidTop").on("webkitAnimationEnd", function()
        {
          $("#EventSingleRaidTop").off();
          var c = function()
          {
            h && (h.remove(), h = null);
            n = new N(
            {
              sectionModel: b
            })
          };
          window.isBrowser ? c() : b.pointModel.point.startStory ? z(b.pointModel.point.startStory, function(e)
          {
            e ? (a.responseSetStorage(e), $("#commandDiv").on("nativeCallback", function(b, e)
            {
              $("#commandDiv").off();
              d.setWebView(!0);
              a.ready.target.className = "nativeFadeOut";
              d.startBgm(m.viewParameterMap.BGM);
              c()
            }), setTimeout(function()
            {
              d.setWebView(!1);
              d.startStory(b.pointModel.point.startStory);
              window.isBrowser && nativeCallback()
            }, 500)) : c()
          }) : c()
        });
        a.addClass(a.doc.querySelector("#EventSingleRaidTop"), "pageFadeout");
        a.removeBackHandler();
        a.addBackHandler(l)
      },
      scaleUp: function(b)
      {
        b.preventDefault();
        a.isScrolled() || a.isDoubleTouch() || b.currentTarget.classList.contains("off") || (a.eventSingleRaidScale = a.eventSingleRaidScale + 5 | 0, this.updateScale())
      },
      scaleDown: function(b)
      {
        b.preventDefault();
        a.isScrolled() || a.isDoubleTouch() || b.currentTarget.classList.contains("off") || (a.eventSingleRaidScale = a.eventSingleRaidScale - 5 | 0, this.updateScale())
      },
      resetPosition: function(b)
      {
        b.preventDefault();
        a.isScrolled() || a.isDoubleTouch() || (a.eventSingleRaidScale = this.SCALE_MAX, this.updateScale())
      },
      updateScale: function()
      {
        a.eventSingleRaidScale >= this.SCALE_MAX ? (a.eventSingleRaidScale = this.SCALE_MAX, a.addClassId("scaleChangePlus", "off"), a.removeClassId("scaleChangeMinus", "off")) : a.eventSingleRaidScale <= this.SCALE_MIN ? (a.eventSingleRaidScale = this.SCALE_MIN, a.removeClassId("scaleChangePlus", "off"), a.addClassId("scaleChangeMinus", "off")) : (a.removeClassId("scaleChangePlus", "off"), a.removeClassId("scaleChangeMinus", "off"));
        d.scaleEventSingleRaid(a.eventSingleRaidScale)
      },
      helpPopup: function(b)
      {
        b.preventDefault();
        a.isScrolled() || a.isDoubleTouch() || a.eventFirstNavi(["navi_01", "navi_02", "navi_03"], m.eventId, "singleraid", function() {}, !0)
      }
    }),
    N = B.View.extend(
    {
      events: function()
      {
        var b = {};
        b[a.cgti + " .missionBtn"] = this.missionToggle;
        b[a.cgti + " .debugBtn"] = this.debugBtn;
        return b
      },
      debugBtn: function(b)
      {
        b.preventDefault();
        "missionClearAnim" == b.currentTarget.dataset.mode && O(function()
        {
          a.tapBlock(!1);
          a.androidKeyStop = !1
        })
      },
      initialize: function(a)
      {
        this.newSectionModel = a.newSectionModel || null;
        this.oldSectionModel = a.sectionModel || null;
        this.nowCleared = a.nowCleared;
        this.nowCompleted = a.nowCompleted;
        this.model = Object.assign(
        {}, a.sectionModel ? a.sectionModel : a.newSectionModel,
        {
          eventObj: m
        });
        this.model.section.title = this.model.eventObj.shortName;
        a = "CHALLENGE" == this.model.pointModel.point.pointType;
        this.model.section.parameter = "BOSS" == this.model.pointModel.point.pointType || "EXTRA_BOSS" == this.model.pointModel.point.pointType ? "第" + this.model.pointModel.point.areaNo + "章 BOSS" : a ? "挑战区域 " + this.model.pointModel.point.areaSubNo : "第" + this.model.pointModel.point.areaNo + "章 区域" + this.model.pointModel.point.areaSubNo;
        this.template = f.template(S);
        this.createDom()
      },
      render: function()
      {
        this.model.pointModel.point.displayCharaMessage = this.model.pointModel.point.displayCharaMessage.replace(/＠/g, "<br>");
        this.$el.html(this.template(this.model));
        return this
      },
      modelSend: function(a)
      {
        return this.model
      },
      createDom: function()
      {
        var b = this,
          c = this.render().el;
        p && a.addClass(c.querySelector("#EventSingleRaidSelect"), "pageFadein");
        this.model.section.imagePath && d.changeBg("bg_adv_" + this.model.section.imagePath + ".jpg");
        a.content.append(c);
        this.nowCleared && "EXTRA_BOSS" == this.oldSectionModel.pointModel.point.pointType && a.addClass(a.doc.querySelector(".memoriaEquip"), "show");
        var e = function(d)
        {
          D.prototype.parentView = b;
          D.prototype.template = f.template($("#questPartsTemp").text());
          var e = a.doc.createDocumentFragment();
          f.each(d.section.questBattleList, function(b)
          {
            var c = new D(
            {
              model: b
            });
            b.canPlay || a.addClass(c.el, "off");
            e.appendChild(c.render().el)
          });
          c.querySelector("#questLinkList").appendChild(e);
          $("#questLinkList .quest .touchObj").bind(a.cgti, function(b)
          {
            b.preventDefault();
            a.isScrolled() || (a.singleRaidGaugeItemNum = x, a.oldEventSectionList = r)
          })
        };
        $("#commandDiv").off();
        I();
        Y(this.model.sectionId);
        if (p) e(this.model), b.oldSectionModel.pointModel.completedAt && a.addClass(a.doc.querySelector("#areaMissionWrap .rewardWrap .title"), "clear"), $("#EventSingleRaidSelect").off(), $("#EventSingleRaidSelect").on("webkitAnimationEnd", function()
        {
          $("#EventSingleRaidSelect").off();
          a.removeBackHandler();
          a.addBackHandler(l);
          a.removeClass(a.doc.querySelector("#EventSingleRaidSelect"), "pageFadein");
          a.tapBlock(!1);
          a.androidKeyStop = !1
        });
        else
        {
          e(this.newSectionModel);
          if (b.oldSectionModel.pointModel.completedAt) a.addClass(a.doc.querySelector("#areaMissionWrap .rewardWrap .title"), "clear"), setTimeout(function()
          {
            P();
            q.length ? l(
            {
              mapPushFlag: !0
            }) : (a.tapBlock(!1), a.androidKeyStop = !1, a.removeBackHandler(), a.addBackHandler(l.bind(null,
            {
              mapPushFlag: !0
            })))
          }, 300);
          else $(a.ready.content).on("webkitAnimationEnd", function(c)
          {
            $(a.ready.content).off("webkitAnimationEnd");
            setTimeout(function()
            {
              P();
              b.gaugeAdvance()
            }, 300)
          });
          a.ready.hide();
          p = !0
        }
        d.getBaseData(a.getNativeObj())
      },
      gaugeAdvance: function()
      {
        var b = this,
          c = this.oldSectionModel.pointModel,
          e = this.newSectionModel.pointModel,
          t = "BOSS" == c.point.pointType || "EXTRA_BOSS" == c.point.pointType ? !0 : !1,
          g = t ? (c.point.missionRequiredCount - c.missionCount) / c.point.missionRequiredCount * 100 : c.missionCount / c.point.missionRequiredCount * 100,
          G = t ? (e.point.missionRequiredCount - e.missionCount) / e.point.missionRequiredCount * 100 : e.missionCount / e.point.missionRequiredCount * 100,
          J = t ? c.point.missionRequiredCount - c.missionCount : c.missionCount,
          c = t ? e.point.missionRequiredCount - e.missionCount : e.missionCount,
          h = 0,
          Q;
        Q = t ? -((g - G) / 20) : (G - g) / 20;
        var k = (c - J) / 20;
        u = setInterval(function()
        {
          g !== G && d.startSe(1007);
          if (a.doc.getElementById("areaMissionGauge"))
          {
            h++;
            var b = Math.round(g + Q * h);
            a.doc.getElementById("areaMissionGauge").style.width = b + "%";
            if (t)
            {
              var b = String(Math.round(J + k * h)).split(""),
                c = a.doc.getElementById("arenaMissionCount"),
                e = a.doc.createDocumentFragment(),
                l = document.createElement("div");
              l.id = "arenaMissionCount";
              l.className = "flexBox";
              f.each(b, function(a)
              {
                var b = document.createElement("div");
                b.className = "num" + a;
                l.appendChild(b)
              });
              e.appendChild(l);
              a.doc.getElementById("arenaMissionCountWrap").replaceChild(e, c)
            }
            else a.doc.getElementById("arenaMissionCount").innerText = Math.round(J + k * h);
            19 < h && (clearInterval(u), u = null, setTimeout(function()
            {
              a.tapBlock(!0);
              a.androidKeyStop = !0;
              m()
            }, 500))
          }
          else clearInterval(u), u = null, a.tapBlock(!1), a.androidKeyStop = !1
        }, 50);
        var m = function()
        {
          if (b.nowCompleted) $("#areaMissionWrap .missionState").off("webkitAnimationEnd"), $("#areaMissionWrap .missionState").on("webkitAnimationEnd", function()
          {
            $("#areaMissionWrap .missionState").off("webkitAnimationEnd");
            $(".rewardWrap").off("webkitAnimationEnd");
            $(".rewardWrap").on("webkitAnimationEnd", function()
            {
              $(".rewardWrap").off("webkitAnimationEnd");
              a.addClass(a.doc.querySelector("#areaMissionWrap .rewardWrap .title"), "clear");
              var c = function()
              {
                setTimeout(function()
                {
                  if (b.oldSectionModel.pointModel.point.completeStory)
                  {
                    var c = b.oldSectionModel.pointModel.point.completeStory;
                    z(c, function(b)
                    {
                      b ? (d.endL2d(), a.responseSetStorage(b), $("#commandDiv").on("nativeCallback", function(b, c)
                      {
                        $("#commandDiv").off();
                        setTimeout(function()
                        {
                          d.changeBg(a.background);
                          d.startBgm(a.bgm);
                          d.setWebView(!0);
                          a.ready.target.className = "nativeFadeOut";
                          l(
                          {
                            mapPushFlag: !0
                          })
                        }, 300)
                      }), setTimeout(function()
                      {
                        d.setWebView(!1);
                        d.startStory(c);
                        window.isBrowser && nativeCallback()
                      }, 500)) : q.length ? l(
                      {
                        mapPushFlag: !0
                      }) : (a.tapBlock(!1), a.androidKeyStop = !1, a.removeBackHandler(), a.addBackHandler(l.bind(null,
                      {
                        mapPushFlag: !0
                      })))
                    })
                  }
                  else q.length ? l(
                  {
                    mapPushFlag: !0
                  }) : (a.tapBlock(!1), a.androidKeyStop = !1, a.removeBackHandler(), a.addBackHandler(l.bind(null,
                  {
                    mapPushFlag: !0
                  })))
                }, 300)
              };
              setTimeout(function()
              {
                O(c);
                d.startSe(1603)
              }, 700)
            });
            setTimeout(function()
            {
              a.addClass(a.doc.querySelector(".rewardWrap"), "clearAnim");
              setTimeout(function()
              {
                d.startSe(1604)
              }, 900)
            }, 500)
          }), a.addClass(a.doc.querySelector("#areaMissionWrap .missionState"), "clearAnim"), setTimeout(function()
          {
            d.startSe(1101)
          }, 200);
          else if (b.nowCleared && b.oldSectionModel.pointModel.point.clearStory)
            if (window.isBrowser) a.tapBlock(!1), a.androidKeyStop = !1, a.removeBackHandler(), a.addBackHandler(l.bind(null,
            {
              mapPushFlag: !0
            }));
            else
            {
              var c = b.oldSectionModel.pointModel.point.clearStory;
              z(c, function(b)
              {
                b ? (d.endL2d(), a.responseSetStorage(b), $("#commandDiv").on("nativeCallback", function(b, c)
                {
                  $("#commandDiv").off();
                  setTimeout(function()
                  {
                    d.changeBg(a.background);
                    d.startBgm(a.bgm);
                    d.setWebView(!0);
                    a.ready.target.className = "nativeFadeOut";
                    l(
                    {
                      mapPushFlag: !0
                    })
                  }, 300)
                }), setTimeout(function()
                {
                  d.setWebView(!1);
                  d.startStory(c);
                  window.isBrowser && nativeCallback()
                }, 500)) : (a.tapBlock(!1), a.androidKeyStop = !1, a.removeBackHandler(), a.addBackHandler(l.bind(null,
                {
                  mapPushFlag: !0
                })))
              })
            }
          else q.length ? l(
          {
            mapPushFlag: !0
          }) : (a.tapBlock(!1), a.androidKeyStop = !1, a.removeBackHandler(), a.addBackHandler(l.bind(null,
          {
            mapPushFlag: !0
          })))
        }
      },
      missionToggle: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          b = a.doc.querySelector("#questLinkList");
          var c = a.doc.querySelector("#questLinkList").className; - 1 !== c.indexOf("first") ? b.className = "second" : -1 !== c.indexOf("second") && (b.className = "first")
        }
      },
      selectHide: function()
      {
        a.tapBlock(!0);
        a.androidKeyStop = !0;
        $("#EventSingleRaidSelect").off();
        $("#EventSingleRaidSelect").on("webkitAnimationEnd", function()
        {
          $("#EventSingleRaidSelect").off();
          n && (n.remove(), n = null);
          $("#commandDiv").on("nativeCallback", function(a, c)
          {
            $("#commandDiv").off();
            h = new v
          });
          d.pushEventSingleRaid(prm)
        });
        window.isDebug && window.isBrowser && (h = new v);
        a.addClass(a.doc.querySelector("#EventSingleRaidSelect"), "pageFadeout");
        a.removeBackHandler()
      }
    }),
    K = function()
    {
      a.setStyle(T + U);
      d.startBgm(m.viewParameterMap.BGM);
      d.changeBg("web_black.jpg");
      if (w)
      {
        $(a.ready.content).off("webkitAnimationEnd");
        a.tapBlock(!0);
        a.androidKeyStop = !0;
        var b = f.findWhere(a.storage.userQuestBattleList.toJSON(),
        {
          questBattleId: w
        });
        if (!b)
        {
          d.nativeReload("#/EventSingleRaidTop");
          return
        }
        y = f.findWhere(a.oldEventSectionList,
        {
          sectionId: b.questBattle.sectionId
        });
        b = f.findWhere(r,
        {
          sectionId: b.questBattle.sectionId
        });
        a.singleRaidCenterPoint = b.pointModel ? b.pointModel.pointId : null;
        var c = !1,
          e = !1;
        !y.pointModel.clearedAt && b.pointModel.clearedAt && (c = !0);
        !y.pointModel.completedAt && b.pointModel.completedAt && (e = !0);
        n = new N(
        {
          sectionModel: y,
          newSectionModel: b,
          nowCleared: c,
          nowCompleted: e
        })
      }
      else b = {
        pointList: k.pointList,
        mapWidth: E,
        mapHeight: F
      }, k.openedPointIdList && (b.newPointIdList = k.openedPointIdList), a.singleRaidCenterPoint && (b.centerPointId = a.singleRaidCenterPoint), window.isDebug && window.isBrowser && (h = new v), $("#commandDiv").on("nativeCallback", function(a, b)
      {
        $("#commandDiv").off();
        h = new v;
        d.setWebView(!0)
      }), d.pushEventSingleRaid(b), q = [];
      a.oldEventSectionList = null;
      V.supportPickUp(k)
    },
    P = function()
    {
      $(a.ready.content).on("webkitAnimationEnd", function(b)
      {
        "readyFadeIn" == b.originalEvent.animationName && (a.tapBlock(!1), a.androidKeyStop = !1, a.scrollRefresh(null, null, null, !0))
      })
    },
    X = function()
    {
      var a = 0;
      f.each(k.pointList, function(b)
      {
        b.isTaskClear && a++
      });
      return a
    },
    L = function(b)
    {
      var c = k.userQuestBattleList;
      b = k.userSectionList;
      var e = k.userEventSingleRaidPointList;
      q = [];
      r = [];
      f.each(b, function(a)
      {
        "SINGLERAID" == a.section.questType && r.push(a)
      });
      var t = a.singleRaidCenterPoint ? !0 : !1,
        g = !1;
      f.each(e, function(b)
      {
        if (b && b.point && !g)
        {
          var c = f.findWhere(r,
          {
            sectionId: b.point.sectionId
          });
          c ? (c.pointModel = b ||
          {}, c.pointModel.areaMissionRewardArr = c.pointModel.point.missionRewardCodes.split(","), c.pointModel.missionRewardObjArr = [], f.each(c.pointModel.areaMissionRewardArr, function(b)
          {
            b = a.itemSet(b);
            c.pointModel.missionRewardObjArr.push(b)
          }), t || "BOSS" === b.point.pointType || "EXTRA_BOSS" === b.point.pointType || "CHALLENGE" === b.point.pointType || (a.singleRaidCenterPoint = b.pointId)) : g = !0
        }
      });
      g ? d.nativeReload("#/EventSingleRaidTop") : (f.each(r, function(b)
      {
        var e = b.sectionId;
        b.section.questBattleList = [];
        if (a.oldEventSectionList)
        {
          var d = !0;
          f.each(a.oldEventSectionList, function(a)
          {
            b.sectionId == a.sectionId && (d = b.canPlay && !a.canPlay ? !0 : !1)
          });
          d && b.canPlay && q.push(b.pointModel.pointId)
        }
        f.each(c, function(c)
        {
          e == c.questBattle.sectionId && ("BOSS" == b.pointModel.point.pointType || "EXTRA_BOSS" == b.pointModel.point.pointType ? (c.fontColor = "colorB", c.title = "战斗") : (c.fontColor = "CHALLENGE" == b.pointModel.point.pointType ? "colorD" : "colorA", c.title = 1 == c.questBattle.sectionIndex ? "战斗◆初级" : 2 == c.questBattle.sectionIndex ? "战斗◆中级" : "战斗◆上级"), c.missionRewardObj = a.itemSet(c.questBattle.missionRewardCode), b.section.questBattleList.push(c))
        });
        b.section.questBattleList.sort(function(a, b)
        {
          return a.questBattle.sectionIndex < b.questBattle.sectionIndex ? -1 : a.questBattle.sectionIndex > b.questBattle.sectionIndex ? 1 : 0
        });
        f.each(b.section.questBattleList, function(a)
        {
          a.canPlay = !0;
          "BOSS" != b.pointModel.point.pointType && "EXTRA_BOSS" != b.pointModel.point.pointType || !b.pointModel.completedAt || (a.canPlay = !1)
        })
      }), console.log("eventSectionList:old", a.oldEventSectionList), console.log("eventSectionList", r), console.log("pointList", k.pointList))
    },
    M = function(b, c)
    {
      var e = [];
      c = "END" !== c ? "touches" : "changedTouches";
      for (var d = 0; d < b.originalEvent[c].length; d++)
      {
        var g = b.originalEvent[c][d].identifier;
        0 > g && (g = -g);
        e[d] = {
          identifier: g,
          clientX: 1024 === a.displayWidth ? b.originalEvent[c][d].clientX : 1024 * b.originalEvent[c][d].clientX / 1280,
          clientY: 1024 === a.displayWidth ? b.originalEvent[c][d].clientY : 1024 * b.originalEvent[c][d].clientY / 1280
        }
      }
      return e
    },
    H = function(b, c)
    {
      for (var e = [], f = "END" !== c ? "touches" : "changedTouches", g = 0; g < b.originalEvent[f].length; g++)
      {
        var h = b.originalEvent[f][g].identifier;
        0 > h && (h = -h);
        e[g] = {
          identifier: h,
          clientX: 1024 === a.displayWidth ? b.originalEvent[f][g].clientX : 1024 * b.originalEvent[f][g].clientX / 1280,
          clientY: 1024 === a.displayWidth ? b.originalEvent[f][g].clientY : 1024 * b.originalEvent[f][g].clientY / 1280
        }
      }
      switch (c)
      {
        case "START":
          d.callTouchesBegin(e);
          break;
        case "MOVE":
          d.callTouchesMove(e);
          break;
        case "END":
          d.callTouchesEnd(e)
      }
    },
    I = function()
    {
      $("#commandDiv").on("nativeCallback", function(b, c)
      {
        c && c.pointId && ("DISABLE" !== c.status ? (d.startSe(1002), d.hideEventSingleRaid(), h.mapHide(A(c.pointId))) : (d.startSe(1002), new a.PopupClass(
        {
          exClass: "openConditionPopup",
          popupType: "typeC",
          conditionList: A(c.pointId).pointModel.conditionDetailList
        }, $("#openConditionTemp").text(), null, function()
        {
          d.resumeEventSingleRaid()
        })))
      })
    },
    l = function(b)
    {
      a.tapBlock(!0);
      a.androidKeyStop = !0;
      d.endL2d();
      d.changeBg("web_black.jpg");
      $("#EventSingleRaidSelect").off();
      $("#EventSingleRaidSelect").on("webkitAnimationEnd", function()
      {
        $("#EventSingleRaidSelect").off();
        n && (n.remove(), n = null);
        if (b.mapPushFlag)
        {
          var c = {
            pointList: k.pointList,
            mapWidth: E,
            mapHeight: F
          };
          a.singleRaidCenterPoint && (c.centerPointId = a.singleRaidCenterPoint);
          if (q.length) a.tapBlock(!0), a.androidKeyStop = !0, c.newPointIdList = q, $("#commandDiv").on("nativeCallback", function(b, f)
          {
            $("#commandDiv").off();
            if (c.newPointIdList) $("#commandDiv").on("nativeCallback", function(b, c)
            {
              $("#commandDiv").off();
              I();
              a.tapBlock(!1);
              a.androidKeyStop = !1;
              d.resumeEventSingleRaid()
            });
            h = new v
          });
          else $("#commandDiv").on("nativeCallback", function(a, b)
          {
            $("#commandDiv").off();
            h = new v
          });
          d.pushEventSingleRaid(c);
          window.isDebug && window.isBrowser && (h = new v);
          q = []
        }
        else h = new v, d.resumeEventSingleRaid();
        a.removeBackHandler()
      });
      a.addClass(a.doc.querySelector("#EventSingleRaidSelect"), "pageFadeout")
    },
    A = function(a)
    {
      var b;
      f.each(r, function(c)
      {
        c.pointModel.pointId == a && (b = c)
      });
      return b
    },
    Y = function(b)
    {
      var c = {};
      c.key = String(b);
      c.type = 1;
      c.id = "0";
      c.x = 230;
      c.y = 1024 === a.displayWidth ? Math.floor(a.doc.getElementsByTagName("body")[0].offsetHeight / 2) - 50 : Math.ceil(a.shortSize / 2);
      d.startL2d(c)
    },
    z = function(b, c)
    {
      var e = !1,
        e = !0;
      f.each(a.storage.userQuestAdventureList.toJSON(), function(a)
      {
        b === a.adventureId && (e = !1)
      });
      e ? ($(a.ready.target).off(), $(a.ready.target).on("webkitAnimationEnd", function()
      {
        d.changeBg("web_black.jpg");
        $(a.ready.target).off();
        $(a.ready.target).on("webkitAnimationEnd", function(b)
        {
          "readyFadeOut" == b.originalEvent.animationName && (a.ready.target.className = "")
        });
        C.ajaxPost(a.linkList.userQuestAdventureRegist,
        {
          adventureId: String(b)
        }, c)
      }), a.ready.target.classList.contains("preNativeFadeIn") ? $(a.ready.target).trigger("webkitAnimationEnd") : a.addClass(a.ready.target, "preNativeFadeIn")) : c()
    },
    Z = function()
    {
      var a = "circle_05.png raid_mission_star_01.png raid_mission_star_01.png raid_mission_tx04.png raid_mission_tx03.png raid_mission_tx02.png raid_mission_tx01.png raid_mission_flag_02_a.png raid_mission_flag_01_a.png circle_06.png raid_mission_star_02.png".split(" "),
        c = function()
        {
          var b = a[0],
            d = new Image;
          d.src = "/magica/resource/image_web/event/singleraid/common/animation/" + b;
          d.onload = function()
          {
            a.shift();
            0 < a.length && c()
          }
        };
      c()
    },
    O = function(b)
    {
      var c = $("#raidAnimationTemp").text();
      a.doc.getElementById("overlapContainer").innerHTML += c;
      $(".raidStar01_1").on("webkitAnimationEnd", function()
      {
        $(".raidStar01_1").off();
        a.tapBlock(!1);
        a.androidKeyStop = !1;
        $(".raidAnimationDom").on(a.cgti, function(c)
        {
          c.preventDefault();
          a.isScrolled() || (a.tapBlock(!0), a.androidKeyStop = !0, $(".raidAnimationDom").off(), a.addClass(a.doc.getElementById("overlapContainer").getElementsByClassName("raidAnimationDom")[0], "allAnimationFadeOut"), $(".animDoms").on("webkitAnimationEnd", function()
          {
            $(".animDoms").off();
            a.doc.getElementById("overlapContainer").innerHTML = '<div id="curtain"></div>';
            b()
          }))
        })
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
      id: "userTitleList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function(a)
    {
      a && (w = a | 0);
      C.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      a.setGlobalView();
      k = C.getPageJson();
      a.historyArr = ["MyPage", "EventSingleRaidTop"];
      m = f.findWhere(k.eventList,
      {
        eventType: "SINGLERAID"
      });
      k.eventMaster = m;
      E = Number(m.viewParameterMap.MAP_WIDTH);
      F = Number(m.viewParameterMap.MAP_HEIGHT);
      var b = a.storage.userItemList.findWhere(
      {
        itemId: "EVENT_SINGLERAID_" + m.eventId + "_EXCHANGE_3"
      });
      x = b ? b.toJSON().quantity : 0;
      !w && a.questBattleModel && "SINGLERAID" == a.questBattleModel.questType && a.oldEventSectionList && (w = a.questBattleModel.questBattle.questBattleId);
      if (w)
      {
        if (!a.oldEventSectionList && !a.eventSingleRaidResumeData)
        {
          d.nativeReload("#/EventSingleRaidTop");
          return
        }
        if (a.eventSingleRaidResumeData)
        {
          console.log("common.eventSingleRaidResumeData", a.eventSingleRaidResumeData);
          L(a.eventSingleRaidResumeData);
          var c = [];
          f.each(a.eventSingleRaidResumeData.userSectionList, function(a)
          {
            "SINGLERAID" == a.section.questType && c.push(a)
          });
          f.each(a.eventSingleRaidResumeData.userEventSingleRaidPointList, function(b)
          {
            if (b && b.point)
            {
              var e = f.findWhere(c,
              {
                sectionId: b.point.sectionId
              });
              e ? (e.pointModel = b ||
              {}, e.pointModel.areaMissionRewardArr = e.pointModel.point.missionRewardCodes.split(","), e.pointModel.missionRewardObjArr = [], f.each(e.pointModel.areaMissionRewardArr, function(b)
              {
                b = a.itemSet(b);
                e.pointModel.missionRewardObjArr.push(b)
              })) : d.nativeReload("#/EventSingleRaidTop")
            }
          });
          a.oldEventSectionList = c;
          a.eventSingleRaidResumeData = null
        }
        else L()
      }
      else L();
      Z();
      if (window.isBrowser) K();
      else
      {
        var e = m.startStoryId,
          h = function(b)
          {
            b ? (a.responseSetStorage(b), $("#commandDiv").on("nativeCallback", function(b, c)
            {
              $("#commandDiv").off();
              d.setWebView(!0);
              a.tapBlock(!1);
              a.androidKeyStop = !1;
              d.startBgm(m.viewParameterMap.BGM);
              a.ready.target.className = "nativeFadeOut";
              a.eventFirstNavi(["navi_01", "navi_02", "navi_03"], k.eventMaster.eventId, "singleraid", function()
              {
                K()
              })
            }), setTimeout(function()
            {
              d.setWebView(!1);
              d.startStory(e,
              {
                canAuto: !1,
                canOpenLog: !1
              });
              window.isBrowser && nativeCallback()
            }, 500)) : setTimeout(function()
            {
              K()
            }, 500)
          };
        !a.singleRaidVoiceCheck && m.existsVoice ? (a.singleRaidVoiceCheck = !0, b = "section_event_" + m.eventId, $("#commandDiv").on("nativeCallback", function()
        {
          $("#commandDiv").off();
          d.setWebView(!0);
          z(e, h)
        }), d.setWebView(!1), d.downloadFileFullVoice(b), window.isBrowser && $("#commandDiv").trigger("nativeCallback")) : (a.singleRaidVoiceCheck = !0, z(e, h))
      }
    },
    remove: function(b)
    {
      h && (h.trigger("removeView"), h.remove(), h = null);
      n && (n.trigger("removeView"), n.remove(), n = null);
      d.endL2d();
      u && (clearInterval(u), u = null);
      p = !1;
      x = y = w = null;
      $(a.ready.content).on("webkitAnimationEnd", function(b)
      {
        "readyFadeIn" == b.originalEvent.animationName && (a.tapBlock(!1), a.scrollRefresh(null, null, null, !0))
      });
      a.removeBackHandler();
      d.popEventSingleRaid();
      d.callTouchesClear();
      b()
    }
  }
});
