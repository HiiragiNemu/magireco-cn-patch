define("underscore backbone backboneCommon ajaxControl command text!template/event/aprilfool2018/EventAprilFoolTop.html text!css/event/aprilfool2018/EventAprilFoolTop.css cardUtil text!template/chara/CharaList.html text!template/chara/CharaListParts.html sortUtil".split(" "), function(g, l, a, u, e, x, y, z, A, B, C)
{
  var D = l.Model.extend(),
    c, h, q, n = null,
    p = [1001, 1002, 1003, 1004, 1005, 2001, 2003, 2004, 2005, 2006],
    w = function(k, g)
    {
      if (k = k ? c.charaId + k : c.charaId + c.live2dId)
      {
        var f = {};
        f.id = String(k);
        f.x = 350;
        f.y = Math.floor(a.doc.getElementsByTagName("body")[0].offsetHeight / 2);
        g ? (f.type = 1, f.key = "idle", e.endL2d(), setTimeout(function()
        {
          "EventAprilFoolTop" === a.location && e.startL2d(f)
        }, 100)) : (f.key = "metamorphose", e.storyMotionL2d(f))
      }
    },
    t = function(a, c)
    {
      for (var f = [], g = "END" !== c ? "touches" : "changedTouches", b = 0; b < a.originalEvent[g].length; b++)
      {
        var d = a.originalEvent[g][b].identifier;
        0 > d && (d = -d);
        f[b] = {
          identifier: d,
          clientX: a.originalEvent[g][b].clientX,
          clientY: a.originalEvent[g][b].clientY
        }
      }
      switch (c)
      {
        case "START":
          e.callTouchesBegin(f);
          break;
        case "MOVE":
          e.callTouchesMove(f);
          break;
        case "END":
          e.callTouchesEnd(f)
      }
    },
    E = function()
    {
      var k = l.View.extend(
        {
          events: function()
          {
            var b = {};
            b[a.cgti + " #posToggle"] = this.posToggle;
            b[a.cgti + " .wearToggle"] = this.wearToggle;
            b[a.cgti + " .charaToggle"] = this.charaListToggle;
            b[a.cgti + " #cameraRun"] = this.running;
            b[a.cgti + " #shutter"] = this.shutter;
            b[a.cgti + " #startTimer"] = this.timer;
            b["touchstart .live2dArea"] = this.touchAction;
            b["touchmove .live2dArea"] = this.touchAction;
            b["touchend .live2dArea"] = this.touchAction;
            b["touchstart #touchArea"] = this.pinchStart;
            b["touchmove #touchArea"] = this.pinchMove;
            b["touchend #touchArea"] = this.pinchEnd;
            b[a.cgti + " #CameraPageBackLinkBtn"] = this.backBtn;
            return b
          },
          initialize: function(b)
          {
            this.toggleFlg = this.l2dTouchCnt = 0;
            this.zoomRatio = 1;
            this.cameraRunning = this.doubleTapFlg = !1;
            this.timerFunc = null;
            q = u.getPageJson();
            this.template = g.template(x);
            g.findWhere(q.eventList,
            {
              eventType: "APRILFOOL2018"
            }) ? this.createDom() : new a.PopupClass(
            {
              title: "错误",
              content: "「御魂的摄影会」已结束。",
              canClose: !1,
              popupType: "typeC",
              closeBtnText: "确定"
            }, null, function()
            {
              a.tapBlock(!1)
            }, function()
            {
              location.href = "#/MyPage"
            })
          },
          render: function()
          {
            this.$el.html(this.template(q));
            return this
          },
          createDom: function()
          {
            v.prototype.rootView = this;
            r.prototype.rootView = this;
            a.content.append(this.render().el);
            a.setGlobalView();
            a.doc.getElementById("globalMenuContainer").style.display = "none";
            e.getBaseData(a.getNativeObj());
            z.createCardList();
            c = a.storage.userCardListEx.findWhere(
            {
              id: a.storage.gameUser.toJSON().leaderId
            }).toJSON();
            this.live2dId = c.live2dId;
            this.charaListView = new v(
            {
              model: new D,
              collection: a.storage.userCardListEx
            });
            a.doc.getElementById("chara").appendChild(this.charaListView.render().el);
            this.charaListView.initSelectCardId = c.userCardId;
            this.charaListView.cardSort.multiSort();
            a.scrollSetX("charaListScrollWrap", "list");
            this.live2dListMake();
            a.scrollSet("scrollOuter", "scrollInner");
            e.getBaseData(a.getNativeObj());
            a.ready.hide();
            this.posToggle()
          },
          charaListToggle: function(b)
          {
            b.preventDefault();
            a.isScrolled() || this.lastToggle && 500 > (new Date).getTime() - this.lastToggle || (this.lastToggle = (new Date).getTime(), a.removeClass(a.doc.getElementById("chara"), "forceOff"), a.doc.getElementById("chara").classList.toggle("off"), a.doc.getElementById("CameraTop").classList.toggle("changing"), a.scrollRefresh())
          },
          changeDisplayChara: function(b)
          {
            b != c.userCardId && (c = a.storage.userCardListEx.findWhere(
            {
              id: b
            }).toJSON(), this.cameraRunning && -1 < p.indexOf(c.charaId) ? this.live2dId = "88" : this.live2dId = c.live2dId, a.removeClass(a.doc.getElementById("CameraTop"), "pos" + this.toggleFlg), this.l2dTouchCnt = this.toggleFlg = 0, this.live2dListMake(), this.posToggle())
          },
          touchAction: function(b)
          {
            switch (b.type)
            {
              case "touchstart":
                a.isDoubleTouch() && (this.doubleTapFlg = !0, this.pinchStart(b));
                break;
              case "touchmove":
                this.doubleTapFlg && this.pinchMove(b);
                break;
              case "touchend":
                this.doubleTapFlg ? (this.pinchEnd(b), this.doubleTapFlg = !1) : this.touch(b)
            }
          },
          touch: function(b)
          {
            if (!a.isDoubleTouch() && (b.preventDefault(), !a.isScrolled()))
              if (this.live2dTap) this.live2dTap = !1;
              else
              {
                b = b.originalEvent.changedTouches[0];
                b = {
                  id: c.charaId + this.live2dId,
                  x: b.pageX,
                  y: b.pageY
                };
                var d = c,
                  m = [32, 33, 34, 35];
                2 <= d.episodeLevel && m.push(36);
                3 <= d.episodeLevel && m.push(37);
                4 <= d.episodeLevel && m.push(38);
                5 <= d.episodeLevel && m.push(39);
                7 <= touchCnt && m.push(40);
                b.voice = "vo_char_" + c.charaId + "_" + c.live2dList[c.live2dIndex].voicePrefixNo + "_" + (m[Math.floor(Math.random() * m.length)] + 1);
                e.storyMotionL2dVoice(b);
                this.l2dTouchCnt++
              }
          },
          wearToggle: function(b)
          {
            b.preventDefault();
            if (!a.isScrolled())
            {
              b = c.charaId + this.live2dId;
              var d = {};
              this.wearChanging ? (a.addClass(a.doc.getElementById("wearWrap"), "off"), a.tapBlock(!0), this.wearChanging = !1, e.endL2d(), a.removeClass(a.doc.getElementById("CameraTop"), "wearing"), d.id = b, d.x = this.posX) : (a.removeClass(a.doc.getElementById("wearWrap"), "off"), a.tapBlock(!0), this.wearChanging = !0, e.endL2d(), a.addClass(a.doc.getElementById("CameraTop"), "wearing"), d.id = b, d.x = 350);
              d.y = Math.floor(a.doc.getElementsByTagName("body")[0].offsetHeight / 2);
              d.type = 1;
              d.key = "idle";
              e.startL2d(d);
              setTimeout(function()
              {
                "EventAprilFoolTop" === a.location && (a.scrollRefresh(), a.tapBlock(!1))
              }, 700)
            }
          },
          live2dListMake: function()
          {
            var b = a.doc.getElementById("scrollOuter").getElementsByClassName("scrollInner")[0];
            this.trigger("l2dListRemove");
            this.l2dListId = c.id;
            if (0 < c.live2dList.length) g.each(c.live2dList, function(a, d)
            {
              a = new r(
              {
                model: a
              });
              b.appendChild(a.render().el)
            });
            else
            {
              var d = new r(
              {
                model:
                {
                  live2dId: c.live2dId,
                  description: "魔法少女",
                  voicePrefixNo: "00"
                }
              });
              b.appendChild(d.render().el)
            }
          },
          live2dFunc: function(b)
          {
            a.addClass(a.doc.getElementById("wearWrap"), "block");
            n = setTimeout(function()
            {
              a.removeClass(a.doc.getElementById("wearWrap"), "block");
              n = null
            }, 1500);
            this.cameraRunning && -1 < p.indexOf(c.charaId) ? (this.live2dId = "88", w(this.live2dId)) : (c.live2dIndex = g.findIndex(c.live2dList,
            {
              live2dId: b
            }), this.live2dId = b = c.live2dList[c.live2dIndex].live2dId, w(b))
          },
          running: function(b)
          {
            b.preventDefault();
            if (!a.isScrolled())
            {
              a.tapBlock(!0);
              var d = this;
              this.cameraRunning ? (e.changeBg(a.settingBg), e.turnOffCamera(), a.removeClass(a.doc.getElementById("CameraTop"), "cameraActive"), this.cameraRunning = !1, a.tapEffectStop = !1, a.androidKeyStop = !1, -1 < p.indexOf(c.charaId) && (this.live2dId = c.live2dId, a.removeClass(a.doc.getElementById("CameraTop"), "pos" + this.toggleFlg), this.l2dTouchCnt = this.toggleFlg = 0, this.posToggle(), this.live2dListMake()), a.tapBlock(!1)) : ($("#commandDiv").on("nativeCallback", function(b, g)
              {
                $("#commandDiv").off();
                g.isSuccess ? (a.addClass(a.doc.getElementById("CameraTop"), "cameraActive"), e.removeBg(), -1 < p.indexOf(c.charaId) && (d.live2dId = "88", d.toggleFlg = 0, d.l2dTouchCnt = 0, d.posToggle()), d.cameraRunning = !0, a.tapEffectStop = !0, a.androidKeyStop = !0) : (new a.PopupClass(
                {
                  title: "错误",
                  content: g.message,
                  closeBtnText: "确定"
                }), a.androidKeyStop = !1, e.turnOffCamera());
                a.tapBlock(!1)
              }), e.turnOnCamera(), window.isBrowser && ($("#commandDiv").off(), a.addClass(a.doc.getElementById("CameraTop"), "cameraActive"), e.removeBg(), this.cameraRunning = !0, a.tapEffectStop = !0, a.androidKeyStop = !0, -1 < p.indexOf(c.charaId) && (this.live2dId = "88", a.removeClass(a.doc.getElementById("CameraTop"), "pos" + this.toggleFlg), this.l2dTouchCnt = this.toggleFlg = 0, this.posToggle()), a.tapBlock(!1)))
            }
          },
          shutter: function(b)
          {
            if (b && (b.preventDefault(), a.isScrolled())) return;
            this.cameraRunning && (a.tapBlock(!0), a.addClass(a.doc.getElementById("CameraTop"), "shuttering"), $("#commandDiv").on("nativeCallback", function(b, c)
            {
              $("#commandDiv").off();
              c.isSuccess ? new a.PopupClass(
              {
                title: "相机拍摄",
                content: "拍摄完成。",
                closeBtnText: "确定",
                popupType: "typeC"
              }) : new a.PopupClass(
              {
                title: "错误",
                content: c.message,
                closeBtnText: "确定"
              });
              a.removeClass(a.doc.getElementById("CameraTop"), "shuttering");
              a.tapBlock(!1)
            }), this.sutterFunc = setTimeout(function()
            {
              e.captureCamera()
            }, 500), window.isBrowser && setTimeout(function()
            {
              $("#commandDiv").off();
              new a.PopupClass(
              {
                title: "相机拍摄",
                content: "拍摄完成。",
                closeBtnText: "确定",
                popupType: "typeC"
              });
              a.removeClass(a.doc.getElementById("CameraTop"), "shuttering");
              a.tapBlock(!1)
            }, 1E3))
          },
          timer: function(b)
          {
            b.preventDefault();
            if (!a.isScrolled() && this.cameraRunning)
            {
              a.tapBlock(!0);
              a.addClass(a.doc.getElementById("CameraTop"), "shuttering");
              var d = this;
              this.timerFunc = setTimeout(function()
              {
                this.timerFunc = null;
                d.shutter()
              }, 4500)
            }
          },
          pinchStart: function(a)
          {
            this.cameraRunning && (a.preventDefault(), t(a, "START"))
          },
          pinchMove: function(a)
          {
            this.cameraRunning && (a.preventDefault(), t(a, "MOVE"))
          },
          pinchEnd: function(a)
          {
            this.cameraRunning && (a.preventDefault(), t(a, "END"))
          },
          posToggle: function(b)
          {
            if (b && (b.preventDefault(), a.isScrolled())) return;
            a.addClass(a.doc.getElementById("posToggle"), "off");
            a.addClass(a.doc.getElementById("CameraPageBackLinkBtn"), "off");
            switch (this.toggleFlg)
            {
              case 0:
                this.posX = 512;
                break;
              case 1:
                this.posX = 674;
                break;
              case 2:
                this.posX = 836;
                break;
              case 3:
                this.posX = 188;
                break;
              case 4:
                this.posX = 350
            }
            this.positionChange()
          },
          positionChange: function()
          {
            a.tapBlock(!0);
            e.endL2d();
            a.removeClass(a.doc.getElementById("CameraTop"), "pos" + this.toggleFlg);
            this.toggleFlg = 4 === this.toggleFlg ? 0 : this.toggleFlg + 1;
            a.addClass(a.doc.getElementById("CameraTop"), "pos" + this.toggleFlg);
            var b = {};
            b.id = c.charaId + this.live2dId;
            b.x = this.posX;
            b.y = Math.floor(a.doc.getElementsByTagName("body")[0].offsetHeight / 2);
            b.type = 1;
            b.key = "idle";
            e.startL2d(b);
            setTimeout(function()
            {
              "EventAprilFoolTop" === a.location && (a.tapBlock(!1), a.removeClass(a.doc.getElementById("CameraPageBackLinkBtn"), "off"), a.removeClass(a.doc.getElementById("posToggle"), "off"))
            }, 700)
          },
          backBtn: function(b)
          {
            b.preventDefault();
            a.isScrolled() || (location.href = "#/MyPage")
          },
          suspendAwake: function(b)
          {
            a.tapBlock(!0);
            var d = !1;
            this.timerFunc && (clearTimeout(this.timerFunc), this.timerFunc = null, d = !0);
            var c = function()
            {
              a.tapBlock(!1)
            };
            b = b.split(" ")[0].split("/");
            2018 !== Number(b[0]) || 4 !== Number(b[1]) || 1 !== Number(b[2]) ? new a.PopupClass(
            {
              title: "错误",
              content: "「御魂的摄影会」已结束。",
              canClose: !1,
              popupType: "typeC",
              closeBtnText: "确定"
            }, null, c, function()
            {
              location.href = "#/MyPage"
            }) : d ? new a.PopupClass(
            {
              title: "错误",
              content: "拍摄已中断。",
              canClose: !1,
              popupType: "typeC",
              closeBtnText: "确定"
            }, null, c, function()
            {
              a.removeClass(a.doc.getElementById("CameraTop"), "shuttering")
            }) : a.tapBlock(!1)
          },
          removeFunc: function(a)
          {
            this.off();
            this.remove();
            a && a()
          }
        }),
        v = l.View.extend(
        {
          id: "charaListWrap",
          events: function()
          {
            var b = {};
            b[a.cgti + " #sortPopup"] = this.sortPop;
            b[a.cgti + " #sortBtn"] = this.sortStart;
            b[a.cgti + " .orderBtn"] = this.sortOrder;
            return b
          },
          initialize: function(a)
          {
            this.listenTo(this, "remove", this.removeView);
            this.template = g.template(A);
            f.prototype.template = g.template(B);
            f.prototype.parentView = this;
            this.cardSort = new C("Camera_chara", this);
            this.charaViews = {};
            this.initSelectCardId = this.selectCardId = null;
            this.selectView = ""
          },
          charaSelect: function(a, d)
          {
            var b = this;
            a && (g.each(this.charaViews, function(c)
            {
              a == c.model.toJSON().userCardId && (c.charaSelectFunc(d), b.selectView = c)
            }), this.selectCardId = a)
          },
          filterFunc: function()
          {
            var b = null,
              c = this;
            if (this.cardSort)
            {
              var e = this.cardSort.getFilterType(),
                f = this.cardSort.getFilterRare(),
                k = e ? e.split(",") : [],
                h = f ? f.split(",") : [];
              g.each(this.charaViews, function(d)
              {
                var e = !1,
                  f = !1;
                k.length ? g.each(k, function(a)
                {
                  d.el.classList.contains(a) && (e = !0)
                }) : e = !0;
                h.length ? g.each(h, function(a)
                {
                  d.el.classList.contains(a) && (f = !0)
                }) : f = !0;
                e && f || d.el.classList.contains("formationRemove") || d.el.classList.contains("formationCurrent") ? (a.removeClass(d.el, "hide"), b || (b = d.model.toJSON().userCardId)) : (a.addClass(d.el, "hide"), c.selectCardId && d.model.toJSON())
              });
              k.length || h.length ? a.addClass(a.doc.querySelector("#sortPopup"), "filterOn") : a.removeClass(a.doc.querySelector("#sortPopup"), "filterOn");
              this.cardSort.memoryHash && (a.sfml[this.cardSort.memoryHash] = this.cardSort.sortPrm, a.sfm())
            }
            var l = 0;
            g.each(this.el.querySelectorAll(".userCharaIcon"), function(a)
            {
              a.classList.contains("hide") || l++
            });
            0 === l ? a.removeClass(a.doc.querySelector(".charaListCaution"), "hide") : a.addClass(a.doc.querySelector(".charaListCaution"), "hide");
            if (this.initSelectCardId) c.charaSelect(this.initSelectCardId, !0), c.initSelectCardId = null;
            else if (!this.selectCardId || this.selectCardId && this.charaViews[this.selectCardId].el.classList.contains("hide")) b = null, g.each(this.el.querySelectorAll("#charaListElms li"), function(a, d)
            {
              b || a.classList.contains("hide") || (b = a.querySelector(".prm_userCardId").innerText, c.charaSelect(b, !0))
            }), b || g.each(this.el.querySelectorAll("#charaListElms li"), function(a, d)
            {
              b || (b = a.querySelector(".prm_userCardId").innerText, c.charaSelect(b, !0))
            });
            a.scrollRefresh()
          },
          render: function()
          {
            var b = a.doc.createDocumentFragment(),
              c = this;
            this.$el.html(this.template(
            {
              model: this.model.toJSON()
            }));
            this.collection.each(function(a, d)
            {
              d = new f(
              {
                model: a
              });
              c.charaViews[a.toJSON().userCardId] = d;
              b.appendChild(d.render().el)
            });
            this.el.querySelector("#charaListElms").appendChild(b);
            return this
          },
          sortPop: function(b)
          {
            b.preventDefault();
            a.isScrolled() || this.cardSort.sortPopupOpen(b)
          },
          sortStart: function(b)
          {
            b.preventDefault();
            a.isScrolled() || (this.cardSort.sortPrm[0] = {
              get: "level",
              level: "rank",
              rank: "atk",
              atk: "def",
              def: "hp",
              hp: "eplv",
              eplv: "rev",
              rev: "mlv",
              mlv: "get"
            } [this.cardSort.sortPrm[0]], this.cardSort.multiSort(this.cardSort.sortPrm))
          },
          sortOrder: function(b)
          {
            b.preventDefault();
            a.isScrolled() || ("asc" === this.cardSort.getAscId() ? this.cardSort.sortPrm[1] = "desc" : this.cardSort.sortPrm[1] = "asc", this.cardSort.ascSort(this.cardSort.sortPrm[1]))
          },
          removeView: function()
          {
            this.off();
            this.remove()
          }
        }),
        f = l.View.extend(
        {
          tagName: "li",
          className: function()
          {
            var a = "userCharaIcon " + this.model.toJSON().card.attributeId + " " + this.model.toJSON().card.rank + " userCardId" + this.model.toJSON().userCardId;
            this.model.toJSON().eventFlag && (a += " eventChara");
            return a
          },
          events: function()
          {
            var b = {};
            b[a.cgti] = this.charaSelect;
            return b
          },
          initialize: function()
          {
            this.listenTo(this.parentView, "remove", this.removeView);
            this.listenTo(this.model, "charaSelect", this.charaSelectFunc);
            this.listenTo(this.model, "change", this.render);
            this.listenTo(this.model, "change", this.charaObjKeyUpdate);
            this.userCardId = this.model.toJSON().userCardId
          },
          render: function()
          {
            this.$el.html(this.template(
            {
              model: this.model.toJSON()
            }));
            e.getBaseData(a.getNativeObj());
            return this
          },
          charaObjKeyUpdate: function()
          {
            this.userCardId !== this.model.toJSON().userCardId && (this.parentView.charaViews[this.model.toJSON().userCardId] = this.parentView.charaViews[this.userCardId], delete this.parentView.charaViews[this.userCardId], this.parentView.selectCardId = this.model.toJSON().userCardId, this.userCardId = this.model.toJSON().userCardId)
          },
          charaSelect: function(b)
          {
            b.preventDefault();
            a.isScrolled() || a.content.hasClass("hide") || (e.startSe("1002"), this.charaSelectFunc())
          },
          charaSelectFunc: function(b)
          {
            this.parentView.selectView && a.removeClass(this.parentView.selectView.el, "select");
            a.addClass(this.el, "select");
            this.parentView.selectView = this;
            this.parentView.rootView.changeDisplayChara(this.model.toJSON().userCardId)
          },
          removeView: function()
          {
            this.off();
            this.remove()
          }
        }),
        r = l.View.extend(
        {
          tagName: "div",
          className: function()
          {
            var a = "commonFrame4 TE se_tabs wrap";
            c.live2dId === this.model.live2dId && (a += " current");
            return a
          },
          events: function()
          {
            var b = {};
            b[a.cgti] = this.wearSelect;
            return b
          },
          initialize: function()
          {
            this.listenTo(this.rootView, "l2dListRemove", this.removeView)
          },
          render: function()
          {
            this.$el.text(this.model.description);
            return this
          },
          wearSelect: function(b)
          {
            b.preventDefault();
            a.isScrolled() || this.el.classList.contains("current") || (a.removeClass(a.doc.getElementById("scrollOuter").getElementsByClassName("current")[0], "current"), a.addClass(this.el, "current"), this.rootView.live2dFunc(this.model.live2dId))
          },
          removeView: function()
          {
            this.off();
            this.remove()
          }
        });
      a.setStyle(y);
      h = new k
    };
  return {
    needModelIdObj: [
    {
      id: "user",
      refresh: !0
    },
    {
      id: "gameUser",
      refresh: !0
    },
    {
      id: "userStatusList",
      refresh: !0
    },
    {
      id: "userCharaList"
    },
    {
      id: "userCardList"
    },
    {
      id: "userDoppelList"
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
      id: "userDailyChallengeList"
    },
    {
      id: "userTotalChallengeList"
    },
    {
      id: "userLimitedChallengeList"
    },
    {
      id: "pieceList"
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
      id: "userLive2dList",
      refresh: !0
    },
    {
      id: "userPatrolList"
    }],
    fetch: function(a, c)
    {
      u.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      E()
    },
    startCommand: function()
    {
      e.changeBg(a.settingBg);
      e.startBgm(a.settingBgm)
    },
    awakeSuspend: function(a)
    {
      h && h.suspendAwake(a)
    },
    remove: function(c)
    {
      a.tapEffectStop = !1;
      a.doc.getElementById("globalMenuContainer") && (a.doc.getElementById("globalMenuContainer").style.display = "");
      e.changeBg(a.settingBg);
      e.turnOffCamera();
      h ? h.removeFunc(function()
      {
        n && clearTimeout(n);
        n = null;
        h.remove();
        c()
      }) : c()
    },
    removeCommand: function()
    {
      e.endL2d()
    }
  }
});
