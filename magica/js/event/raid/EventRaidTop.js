define("underscore backbone backboneCommon ajaxControl command text!template/event/raid/EventRaidTop.html text!css/event/raid/EventRaidTop.css js/event/raid/view/EventRaidRewardPartsView js/event/raid/view/EventRaidInfoPartsView js/event/raid/view/EventRaidRpCureView js/view/common/PagingView text!js/event/raid/EventRaidMessage.json QuestUtil".split(" "), function(e, p, b, t, g, Z, aa, ba, S, ca, T, da, U)
{
  var ea = p.Model.extend(
    {}),
    l, z, C = !1,
    u = 0,
    v = !1,
    x, D = !1,
    q, H = !1,
    V, A = !1,
    y, m, B, E, h, k, n = !1,
    ha = p.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " #helpBtn"] = this.announceOpen;
        a[b.cgti + " #logBtn"] = this.popupLog;
        a[b.cgti + " #appEnemyBtn"] = this.appEnemy;
        a[b.cgti + " #missionBtn"] = this.popupMission;
        a[b.cgti + " #bossDetailCurtain"] = this.bossDetailCurtain;
        a[b.cgti + " #bossListShowBtn"] = this.showBossList;
        a[b.cgti + " #bossListCloseBtn"] = this.closeBossList;
        a[b.cgti + " .debugTapWimpBtn"] = this.debugTapWimpBtn;
        a[b.cgti + " .debugTapBossBtn"] = this.debugTapBossBtn;
        a[b.cgti + " .debugReliefBtn"] = this.debugReliefBtn;
        a[b.cgti + " .debugRewardPopupBtn"] = this.debugRewardPopupBtn;
        a[b.cgti + " .debugSuspendBtn"] = this.debugSuspendBtn;
        if (window.isBrowser) return a;
        a["touchstart #mapWrap"] = this.touchStart;
        a["touchmove #mapWrap"] = this.touchMove;
        a["touchend #mapWrap"] = this.touchEnd;
        return a
      },
      touchStart: function(a)
      {
        a.preventDefault();
        D && n && (b.tapEffectStop = !0, I(a, "START"))
      },
      touchMove: function(a)
      {
        a.preventDefault();
        D && I(a, "MOVE")
      },
      touchEnd: function(a)
      {
        a.preventDefault();
        D && n && (b.tapEffectStop = !1, I(a, "END"))
      },
      initialize: function(a)
      {
        this.areaViewList = [];
        this.logScrollTarget = "";
        this.selectRaidId = this.battleLogView = null;
        this.template = e.template(Z);
        this.createDom();
        this.sideWrap = b.doc.getElementById("sideWrap");
        this.bossListWrap = b.doc.getElementById("bossListWrap");
        this.bossDetailWrap = b.doc.getElementById("bossDetailWrap");
        this.bossDetailCurtain = b.doc.getElementById("bossDetailCurtain")
      },
      render: function()
      {
        var a = h;
        a.eventId = l.eventId;
        a.shopId = l.shopId;
        var c = b.storage.userItemList.findWhere(
        {
          itemId: "EVENT_RAID_" + l.eventId + "_EXCHANGE_1"
        });
        a.itemQuantity = c ? c.get("quantity") : 0;
        this.$el.html(this.template(a));
        return this
      },
      createDom: function()
      {
        b.setGlobalView();
        b.content.append(this.render().el);
        S.prototype.rootView = this;
        this.infoView = new S;
        b.doc.getElementById("rpInfoPartsWrap").appendChild(this.infoView.render().el);
        this.bossListCount();
        this.clearMissionCount();
        b.ready.hide()
      },
      appEnemy: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (b.tapBlock(!0), n = !1, g.appEnemyEventRaid(
        {
          enemyList: h.enemyList
        }), window.isBrowser && $("#commandDiv").trigger("nativeCallback", ["SCENE_APP_ENEMY_EVENT_RAID"]))
      },
      pageShow: function()
      {
        b.removeClass(b.doc.querySelector("#mainContent"), "hide");
        b.removeClass(b.doc.querySelector("#globalMenuContainer"), "hide")
      },
      pageHide: function()
      {
        b.addClass(b.doc.querySelector("#mainContent"), "hide");
        b.addClass(b.doc.querySelector("#globalMenuContainer"), "hide")
      },
      createBossList: function(a)
      {
        this.trigger("removeBossListView");
        J.prototype.rootView = this;
        J.prototype.template = e.template($("#bossListParts").text());
        var c = this.selectRaidId ? this.selectRaidId : a,
          d = b.doc.createDocumentFragment();
        e.each(m, function(a, b)
        {
          a.index = b;
          a = new J(
          {
            model: a
          });
          d.appendChild(a.render().el);
          c && a.id() == c && a.addClassSelected()
        });
        b.doc.getElementById("bossList").appendChild(d)
      },
      showBossList: function(a, c)
      {
        if (a && (a.preventDefault(), b.isScrolled())) return;
        this.createBossList(c);
        b.scrollSet("bossListRoot", "scrollInner");
        this.sideWrap.className = "hide";
        this.bossListWrap.className = "show"
      },
      closeBossList: function(a)
      {
        a.preventDefault();
        b.isScrolled() || ($(this.bossListWrap).on("webkitAnimationEnd", function()
        {
          $(this).off()
        }), this.bossListWrap.className = "hide", this.sideWrap.className = "show", this.closeBossDetail(), b.scrollRefresh("bossListRoot", "scrollInner", !0))
      },
      showBossDetail: function(a)
      {
        this.bossDetailView && k.removeBossDetail();
        W.prototype.template = e.template($("#bossDetailParts").text());
        this.bossDetailView = new W(
        {
          model: a
        });
        this.bossDetailWrap.appendChild(this.bossDetailView.render().el);
        this.bossDetailWrap.className = "show";
        this.bossDetailCurtain.className = "on";
        this.selectRaidId = a.raidId;
        g.focusPointEventRaid(
        {
          id: a.raidId
        })
      },
      closeBossDetail: function()
      {
        this.selectRaidId = null;
        g.cancelSelectBossEventRaid();
        this.bossDetailWrap.className = "hide";
        this.bossDetailCurtain.className = "off";
        this.trigger("removeClassName")
      },
      removeBossDetail: function()
      {
        this.bossDetailView && (this.bossDetailView.removeView(), this.bossDetailView = null)
      },
      bossDetailCurtain: function(a)
      {
        a.preventDefault();
        b.isScrolled() || this.closeBossDetail()
      },
      popupLog: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (this.battleLogView = new fa)
      },
      updateLog: function(a)
      {
        this.battleLogView.updateLog(a)
      },
      popupMission: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (this.missionView = new ga)
      },
      bossListCount: function()
      {
        var a = m.length;
        0 < a ? (b.doc.getElementById("bossListBatch").innerText = a, b.addClass(b.doc.getElementById("bossListBatch"), "on")) : b.removeClass(b.doc.getElementById("bossListBatch"), "on")
      },
      clearMissionCount: function()
      {
        var a = 0;
        e.each(B, function(b, d)
        {
          !b.receivedAt && b.cleared && ("PERSONAL" == b.eventRaidChallenge.bean || "TOTAL" == b.eventRaidChallenge.bean && v) && a++
        });
        0 < a ? (b.doc.getElementById("missionBtnBatch").innerText = a, b.addClass(b.doc.getElementById("missionBtnBatch"), "on")) : b.removeClass(b.doc.getElementById("missionBtnBatch"), "on")
      },
      debugTapWimpBtn: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = [];
          for (var c = 0; c < h.enemyList.length; ++c) a.push(h.enemyList[c].id);
          $("#commandDiv").trigger("nativeCallback",
          {
            touchedEnemyIdList: a
          })
        }
      },
      debugTapBossBtn: function(a)
      {
        a.preventDefault();
        b.isScrolled() || $("#commandDiv").trigger("nativeCallback",
        {
          touchedBossId: m[0].raidId
        })
      },
      debugRewardPopupBtn: function(a)
      {
        a.preventDefault();
        b.isScrolled() || K()
      },
      debugReliefBtn: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (x = {
          raidId: m[0].raidId
        }, L())
      },
      debugSuspendBtn: function(a)
      {
        a.preventDefault();
        b.isScrolled() || $("#suspendAwake").trigger("suspendAwake")
      },
      announceOpen: function(a)
      {
        a.preventDefault();
        b.isScrolled() || b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], l.eventId, "raid", null, !0)
      }
    }),
    J = p.View.extend(
    {
      tagName: "li",
      id: function()
      {
        return this.model.raidId
      },
      events: function()
      {
        var a = {};
        a[b.cgti] = this.tapFunc;
        return a
      },
      initialize: function(a)
      {
        this.listenTo(this.rootView, "removeBossListView", this.removeView);
        this.listenTo(this.rootView, "removeClassName", this.removeClassName)
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        this.el.setAttribute("data-scroll-hash", this.model.raidId);
        return this
      },
      tapFunc: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (g.cancelSelectBossEventRaid(), this.rootView.trigger("removeClassName"), this.addClassSelected(), k.showBossDetail(this.model))
      },
      addClassSelected: function()
      {
        b.addClass(this.el, "selected")
      },
      removeClassName: function()
      {
        this.el.className = ""
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    W = p.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " .participantBtn"] = this.participantBtn;
        a[b.cgti + " #battleStartBtn"] = this.battleStartBtn;
        return a
      },
      initialize: function(a)
      {
        this.escapeTime = Date.parse(this.model.discoveredAt) / 1E3 + 60 * this.model.raidBoss.ttlMinutes - z | 0;
        0 >= this.escapeTime && (this.model.isEscape = !0);
        a = "";
        if (this.model.isEscape) a = "已逃离";
        else
        {
          var b = this.escapeTime / 3600 | 0,
            d = (this.escapeTime - 3600 * b) / 60 | 0;
          0 != b && (a += b + "时间");
          a += d + "分"
        }
        this.model.displayEscapeTime = a
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        return this
      },
      battleStartBtn: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = (a = b.storage.userQuestBattleList.findWhere(
          {
            questBattleId: this.model.raidBoss.questBattleId
          })) ? a.toJSON() : !1;
          var c;
          a && (c = (c = b.storage.userSectionList.findWhere(
          {
            sectionId: a.questBattle.sectionId
          })) ? c.toJSON() :
          {});
          b.questBattleModel = ia(c, a, this.model);
          console.log(b.questBattleModel);
          b.questBattleModel ? 1 > b.storage.userStatusList.findWhere(
          {
            statusId: "RP"
          }).toJSON().point ? new b.PopupClass(
          {
            title: "关卡确认",
            content: "RP不足。",
            closeBtnText: "关闭",
            decideBtnText: "回复",
            decideBtnEvent: function(a)
            {
              a.preventDefault();
              b.isScrolled() || ca.popupStart()
            }
          }) : location.href = "#/SupportSelect" : new b.PopupClass(
          {
            title: "关卡确认",
            content: "无法开始关卡",
            closeBtnText: "关闭"
          }, null, null, function(a)
          {
            location.href = "#/MyPage"
          })
        }
      },
      participantBtn: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = null,
            d = this.model;
          new b.PopupClass(
          {
            exClass: "Participant"
          }, null, function()
          {
            c = new X(
            {
              model: d
            })
          }, function()
          {
            c.removeView()
          })
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    fa = p.View.extend(
    {
      id: "BattleLog",
      events: function()
      {
        var a = {};
        a[b.cgti + " .closeBtn"] = this.closeBtn;
        a[b.cgti + " .paging li"] = this.paging;
        return a
      },
      initialize: function(a)
      {
        this.template = e.template($("#battleLogParts").text());
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template());
        return this
      },
      createDom: function()
      {
        b.doc.getElementById("overlapContainer").appendChild(this.render().el);
        b.doc.getElementById("curtain").className = "show";
        T.parentView = this;
        var a = new ea(
        {
          count: h.closedUserEventRaidBossList.length,
          pageLimit: 5
        });
        this.pagingView = new T(
        {
          model: a,
          another: "battleLogPagingWrap"
        });
        this.updateLog(1);
        b.scrollSet("battleLogListWrap", "scrollInner")
      },
      updateLog: function(a)
      {
        this.pagingView.model.set(
        {
          count: h.closedUserEventRaidBossList.length,
          pageLimit: 10
        });
        this.trigger("removeChildView");
        M.prototype.rootView = this;
        M.prototype.template = e.template($("#battleLogListParts").text());
        var c = b.doc.createDocumentFragment();
        e.each(h.closedUserEventRaidBossList, function(b, f)
        {
          f >= 10 * (a - 1) && f < 10 * a && (b = new M(
          {
            model: b
          }), c.appendChild(b.render().el))
        });
        b.doc.getElementById("battleLogList").appendChild(c);
        g.getBaseData(b.getNativeObj());
        b.scrollRefresh(null, null, !0)
      },
      closeBtn: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = this;
          k.clearMissionCount();
          b.doc.getElementById("curtain").className = "";
          b.addClass(this.el, "close");
          $(c.el).on("webkitAnimationEnd", function()
          {
            $(c.el).off();
            c.removeView()
          })
        }
      },
      removeView: function()
      {
        this.pagingView.removeView();
        this.trigger("removeChildView");
        this.off();
        this.remove()
      }
    }),
    M = p.View.extend(
    {
      tagName: "li",
      events: function()
      {
        var a = {};
        a[b.cgti + " .participantBtn"] = this.participantBtn;
        return a
      },
      initialize: function(a)
      {
        this.listenTo(this.rootView, "removeChildView", this.removeView)
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        this.el.setAttribute("data-scroll-hash", this.model.bossId);
        return this
      },
      participantBtn: function(a)
      {
        a.preventDefault();
        b.isScrolled() || t.ajaxPost(b.linkList.raidShowLog,
        {
          raidId: this.model.raidId
        }, function(a)
        {
          var c = null;
          new b.PopupClass(
          {
            exClass: "Participant"
          }, null, function()
          {
            c = new X(
            {
              model: a.userEventRaidBoss,
              close: !0
            })
          }, function()
          {
            c.removeView()
          })
        })
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    X = p.View.extend(
    {
      id: "Participant",
      initialize: function(a)
      {
        this.template = e.template($("#participantParts").text());
        var c = [],
          d = b.storage.gameUser.toJSON().userId;
        e.each(this.model.resultList, function(a, b)
        {
          (b = e.findWhere(c,
          {
            attackUserId: a.attackUserId
          })) ? b.damage += a.damage: c.push(e.clone(a))
        });
        c = e.sortBy(c, function(a)
        {
          return -a.damage
        });
        c = e.sortBy(c, function(a)
        {
          if (a.attackUserId == d) return -1
        });
        this.model.attackUserList = c;
        this.createDom(a.close ? this.model.resultList : this.model.attackUserList);
        a.close && b.addClass(this.el, "close")
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        return this
      },
      createDom: function(a)
      {
        b.doc.getElementsByClassName("popupInner")[0].appendChild(this.render().el);
        N.prototype.rootView = this;
        N.prototype.template = e.template($("#participantListParts").text());
        var c = b.doc.createDocumentFragment();
        e.each(a, function(a, b)
        {
          a.index = b;
          a = new N(
          {
            model: a
          });
          c.appendChild(a.render().el)
        });
        b.doc.getElementById("participantList").appendChild(c);
        g.getBaseData(b.getNativeObj());
        b.scrollSet("participantListWrap", "scrollInner")
      },
      removeView: function()
      {
        this.trigger("removeChildView");
        this.remove()
      }
    }),
    N = p.View.extend(
    {
      tagName: "li",
      className: "participantChild commonFrame4",
      initialize: function(a)
      {
        this.listenTo(this.rootView, "removeChildView", this.removeView)
      },
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
        this.remove()
      }
    }),
    ga = p.View.extend(
    {
      id: "MissionArea",
      events: function()
      {
        var a = {};
        a[b.cgti + " .closeBtn"] = this.closeBtn;
        a[b.cgti + " #tabBtn .btn"] = this.tabScreen;
        return a
      },
      initialize: function(a)
      {
        this.template = e.template($("#missionParts").text());
        this.createDom();
        b.scrollSet("missionScrollWrap", "mission1List");
        v && b.scrollSet("missionScrollWrap", "mission2List");
        $(this.el.getElementsByClassName("common_tab")[0].getElementsByClassName(q)[0]).trigger(b.cgti)
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
        b.doc.getElementById("overlapContainer").appendChild(this.render().el);
        b.doc.getElementById("curtain").className = "show";
        b.doc.getElementById("storyCond").innerText = V;
        O.prototype.rootView = this;
        O.prototype.template = e.template($("#missionListParts").text());
        this.createMissionList();
        this.clearMissionCount()
      },
      createMissionList: function()
      {
        var a = b.doc.createDocumentFragment(),
          c = b.doc.createDocumentFragment(),
          d = B,
          d = e.sortBy(d, function(a)
          {
            return a.cleared && ("PERSONAL" == a.eventRaidChallenge.bean || "TOTAL" == a.eventRaidChallenge.bean && v) ? -999 + a.eventRaidChallenge.sortKey : a.eventRaidChallenge.sortKey
          });
        e.each(d, function(b, d)
        {
          b.receivedAt || (d = new O(
          {
            model: b
          }), "PERSONAL" == b.eventRaidChallenge.bean ? a.appendChild(d.render().el) : c.appendChild(d.render().el))
        });
        q = "mission1";
        1 > a.children.length ? (b.doc.getElementById("mission1").innerHTML = '<p class="noMission ts_white">已完成全部任务</p>', q = "mission2") : b.doc.getElementById("mission1").appendChild(a);
        1 > c.children.length ? (b.doc.getElementById("mission2").innerHTML = '<p class="noMission ts_white">已完成全部任务</p>', q = "mission1") : (b.doc.getElementById("mission2").appendChild(c), v || (b.doc.getElementById("mission2").innerHTML += "<div id='totalMissionValidityMask' class='c_pink'>全体击破报酬需击破自己发现的BOSS<br>【" + h.userEventRaid.eventRaid.totalChallengeOpenCount + "个以上】<br>即可解锁全体击败的报酬</div>"));
        this.el.className = q;
        g.getBaseData(b.getNativeObj());
        c = a = null
      },
      clearMissionCount: function()
      {
        var a = 0,
          c = 0;
        e.each(B, function(b, f)
        {
          !b.receivedAt && b.cleared && ("PERSONAL" == b.eventRaidChallenge.bean ? a++ : "TOTAL" == b.eventRaidChallenge.bean && v && c++)
        });
        0 < a ? (b.doc.getElementById("mission1Batch").innerText = a, b.addClass(b.doc.getElementById("mission1Batch"), "on")) : b.removeClass(b.doc.getElementById("mission1Batch"), "on");
        0 < c ? (b.doc.getElementById("mission2Batch").innerText = c, b.addClass(b.doc.getElementById("mission2Batch"), "on")) : b.removeClass(b.doc.getElementById("mission2Batch"), "on")
      },
      tabScreen: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          a = a.currentTarget;
          var c = b.doc.getElementById("tabBtn").getElementsByClassName("current")[0];
          b.removeClass(c, "current");
          b.removeClass(this.el, q);
          b.addClass(this.el, a.dataset.wrap);
          b.doc.getElementById("listTitle").innerText = a.dataset.missionName;
          b.addClass(a, "current");
          q = a.dataset.wrap;
          b.scrollRefresh("missionScrollWrap", q + "List", !0)
        }
      },
      closeBtn: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var c = this;
          k.clearMissionCount();
          b.doc.getElementById("curtain").className = "";
          b.addClass(this.el, "close");
          $(c.el).on("webkitAnimationEnd", function()
          {
            $(c.el).off();
            c.removeView()
          })
        }
      },
      removeView: function()
      {
        this.trigger("removeChildView");
        this.remove()
      }
    }),
    O = p.View.extend(
    {
      tagName: "div",
      className: "missionChild wrap commonFrame4",
      events: function()
      {
        var a = {};
        a[b.cgti + " .missionBtn"] = this.missionBtn;
        return a
      },
      initialize: function(a)
      {
        this.listenTo(this.rootView, "removeChildView", this.removeView);
        this.missionValidity = "PERSONAL" == this.model.eventRaidChallenge.bean || "TOTAL" == this.model.eventRaidChallenge.bean && v;
        this.model.eventRaidChallenge.displayName = this.model.eventRaidChallenge.displayName.replace(/＠/g, "<br>")
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model,
          missionValidity: this.missionValidity
        }));
        this.model.cleared && this.missionValidity && this.el.classList.add("clear");
        return this
      },
      missionBtn: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled() && !H)
        {
          H = !0;
          var c = this;
          t.ajaxPost(b.linkList.raidChallengeReceive,
          {
            challengeId: this.model.challengeId
          }, function(a)
          {
            if ("error" !== a.resultCode)
            {
              b.responseSetStorage(a);
              H = !1;
              var d = function()
              {
                c.rootView.clearMissionCount()
              };
              1 > Object.keys(a).length || window.isLocal && window.isBrowser && 2 > Object.keys(a).length ? new b.PopupClass(
              {
                content: "已过领取期限,<br>无法领取该任务报酬",
                closeBtnText: "确定",
                popupType: "typeC",
                exClass: "missionPop"
              }, null, null, d) : new b.PopupClass(
              {
                content: "已领取1个任务报酬。<br><br>※可直接获得领取的道具。",
                closeBtnText: "确定",
                popupType: "typeC",
                exClass: "missionPop"
              }, null, null, d);
              c.removeView();
              "PERSONAL" === c.model.eventRaidChallenge.bean ? (a = b.doc.getElementById("mission1").getElementsByClassName("wrap").length, 1 > a && (b.doc.getElementById("mission1").innerHTML = '<p class="noMission ts_white">已完成全部任务</p>')) : "TOTAL" === c.model.eventRaidChallenge.bean && (a = b.doc.getElementById("mission2").getElementsByClassName("wrap").length, 1 > a && (b.doc.getElementById("mission2").innerHTML = '<p class="noMission ts_white">已完成全部任务</p>'));
              a = new Date(1E3 * z);
              c.model.receivedAt = a.getFullYear() + "/" + (a.getMonth() + 1) + "/" + a.getDate() + " " + a.getHours() + ":" + a.getMinutes() + ":" + a.getSeconds();
              b.scrollRefresh(null, null, !0)
            }
          })
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
      }
    }),
    I = function(a, c)
    {
      for (var d = [], f = "END" !== c ? "touches" : "changedTouches", e = 0; e < a.originalEvent[f].length; e++)
      {
        var h = a.originalEvent[f][e].identifier;
        0 > h && (h = -h);
        d[e] = {
          identifier: h,
          clientX: 1024 === b.displayWidth ? a.originalEvent[f][e].clientX : 1024 * a.originalEvent[f][e].clientX / 1280,
          clientY: 1024 === b.displayWidth ? a.originalEvent[f][e].clientY : 1024 * a.originalEvent[f][e].clientY / 1280
        }
      }
      switch (c)
      {
        case "START":
          g.callTouchesBegin(d);
          break;
        case "MOVE":
          g.callTouchesMove(d);
          break;
        case "END":
          g.callTouchesEnd(d)
      }
    },
    K = function(a)
    {
      new ba(
      {
        eventId: l.eventId,
        logRaidBossList: E,
        closeCallback: a
      })
    },
    ja = function()
    {
      $("#commandDiv").on("nativeCallback", function(a, c)
      {
        if (c && c.touchedEnemyIdList)
        {
          a = function(a)
          {
            b.responseSetStorage(a);
            if (a && a.rewardList)
            {
              var d = [];
              e.each(a.rewardList, function(a, b)
              {
                a.lotted && (a.id = c.touchedEnemyIdList[b], d.push(a))
              });
              0 < d.length ? (g.showRewardEventRaid(
              {
                rewardList: d
              }), a && 0 < a.bossList.length && (y = a, P(y.userEventRaidBossList), k.bossListCount(), z = Date.parse(y.userEventRaidBossList[y.userEventRaidBossList.length - 1].discoveredAt) / 1E3), window.isBrowser && $("#commandDiv").trigger("nativeCallback", ["SCENE_SHOW_REWARD_EVENT_RAID"])) : a && 0 < a.bossList.length ? (P(a.userEventRaidBossList), k.bossListCount(), z = Date.parse(a.userEventRaidBossList[a.userEventRaidBossList.length - 1].discoveredAt) / 1E3, setTimeout(function()
              {
                var b = {
                  bossList: a.bossList
                };
                k.pageHide();
                g.appBossEventRaid(b);
                window.isBrowser && $("#commandDiv").trigger("nativeCallback", ["SCENE_APP_BOSS_EVENT_RAID"])
              }, 500)) : Q()
            }
          };
          b.tapBlock(!0);
          n = !1;
          u -= c.touchedEnemyIdList.length;
          0 > u && (u = 0);
          var d = [];
          e.each(m, function(a, b)
          {
            d.push(a.point.pointId)
          });
          t.ajaxPost(b.linkList.raidDraw,
          {
            count: c.touchedEnemyIdList.length,
            pointIdList: d
          }, a)
        }
        else if (c && c.touchedBossId) a = e.findWhere(m,
        {
          raidId: c.touchedBossId
        }), g.startSe(1002), k.createBossList(a.raidId), k.showBossDetail(a);
        else if ("SCENE_PUSH_EVENT_RAID" == c) g.changeBg(l.viewParameterMap.BG_IMG), k = new ha, b.tapBlock(!1), n = D = !0, A ? (a = F, x && (a = function()
        {
          L(F)
        }), K(a)) : x ? L(F) : F();
        else if ("SCENE_SHOW_REWARD_EVENT_RAID" == c)
          if (y)
          {
            var f = {
              bossList: y.bossList
            };
            setTimeout(function()
            {
              k.pageHide();
              g.appBossEventRaid(f);
              y = null;
              window.isBrowser && $("#commandDiv").trigger("nativeCallback", ["SCENE_APP_BOSS_EVENT_RAID"])
            }, 500)
          }
        else Q();
        else "SCENE_APP_BOSS_EVENT_RAID" == c && (k.pageShow(), Q(), "show" == k.bossListWrap.className && k.showBossList())
      })
    },
    Q = function()
    {
      u <= l.viewParameterMap.REPOP_COUNT ? (g.appEnemyEventRaid(
      {
        enemyList: h.enemyList
      }), window.isBrowser && $("#commandDiv").trigger("nativeCallback", ["SCENE_APP_ENEMY_EVENT_RAID"]), setTimeout(function()
      {
        b.tapBlock(!1);
        n = !0;
        u = h.enemyList.length;
        console.log("cntEnemy", u)
      }, 1E3)) : (b.tapBlock(!1), n = !0)
    },
    F = function()
    {
      var a = JSON.parse(da),
        c = b.storage.userStatusList.findWhere(
        {
          statusId: "RP"
        }).toJSON().point,
        d = e.find(B, function(a)
        {
          return a.cleared
        }) ? !0 : !1,
        f = e.find(m, function(a)
        {
          return "SELF" == a.type && 0 == a.combo
        }) ? !0 : !1,
        k = e.find(m, function(a)
        {
          return "RELIEF" == a.type
        }) ? !0 : !1,
        l = 0 >= m.length,
        r = [],
        w = !1;
      e.every(a, function(a)
      {
        "RP" == a.type ? c == a.threshold && (r.push(a.text), w = a.force) : "RANDOM" == a.type ? (r.push(a.text), w = a.force) : "SELF_BEAT" == a.type ? h.userEventRaid.count >= a.threshold && (r.push(a.text), w = a.force) : "MISSION" == a.type ? d && (r.push(a.text), w = a.force) : "SELF_BOSS" == a.type ? f && (r.push(a.text), w = a.force) : "OTHER_BOSS" == a.type ? k && (r.push(a.text), w = a.force) : "NO_BOSS" == a.type && l && (r.push(a.text), w = a.force);
        return !w
      });
      a = "";
      a = w ? r[r.length - 1] : r[Math.floor(Math.random() * r.length)];
      a = a.replace(/＠/g, "\n");
      g.pushMessageEventRaid(
      {
        message: a
      })
    },
    L = function(a)
    {
      var c = e.findWhere(m,
      {
        raidId: x.raidId
      });
      c && !c.reliefRequestedAt && "SELF" == c.type ? new b.PopupClass(
      {
        title: "救援请求",
        content: "还未能击破交战的BOSS。<br>向其他玩家发送救援请求,<br>请他们协助击破BOSS吧。<br><br><span class='c_red'>※发送救援请求后其他玩家即可攻击该BOSS</span>",
        closeBtnText: "关闭",
        decideBtnText: "发送救援请求",
        decideBtnEvent: function(d)
        {
          d.preventDefault();
          b.isScrolled() || (d = {
            raidId: x.raidId,
            userIdList: b.raidRequestPickUpUserIdList
          }, console.log(d), t.ajaxPost(b.linkList.raidReliefRequest, d, function()
          {
            R();
            var d = new Date(1E3 * z);
            c.reliefRequestedAt = d.getFullYear() + "/" + (d.getMonth() + 1) + "/" + d.getDate() + " " + d.getHours() + ":" + d.getMinutes() + ":" + d.getSeconds();
            new b.PopupClass(
            {
              title: "救援请求",
              content: "已发送救援请求。",
              closeBtnText: "确定"
            }, null, null, a)
          }))
        },
        exClass: "Relief"
      }, null, null, a) : a && a()
    },
    R = function()
    {
      if (!b.tutorialId)
      {
        var a, c = Date.parse(h.currentTime) / 1E3,
          d = new Date(1E3 * (c - 3600)),
          c = new Date(1E3 * (c + 600)),
          f, g, k, l, m, n, p, q;
        f = 10 > d.getMonth() + 1 ? "0" + (d.getMonth() + 1) : d.getMonth() + 1;
        g = 10 > d.getDate() ? "0" + d.getDate() : d.getDate();
        k = 10 > d.getHours() ? "0" + d.getHours() : d.getHours();
        l = 10 > d.getMinutes() ? "0" + d.getMinutes() : d.getMinutes();
        m = 10 > c.getMonth() + 1 ? "0" + (c.getMonth() + 1) : c.getMonth() + 1;
        n = 10 > c.getDate() ? "0" + c.getDate() : c.getDate();
        p = 10 > c.getHours() ? "0" + c.getHours() : c.getHours();
        q = 10 > c.getMinutes() ? "0" + c.getMinutes() : c.getMinutes();
        d = d.getFullYear() + "-" + f + "-" + g + "T" + k + ":" + l + ":00.000+0900";
        c = c.getFullYear() + "-" + m + "-" + n + "T" + p + ":" + q + ":00.000+0900";
        a = {
          size: 40,
          query:
          {
            function_score:
            {
              query:
              {
                bool:
                {
                  must: [
                  {
                    range:
                    {
                      lastAccessDate:
                      {
                        gte: d,
                        lte: c
                      }
                    }
                  }],
                  must_not:
                  {
                    term:
                    {
                      _id: String(b.storage.gameUser.get("userId"))
                    }
                  }
                }
              },
              functions: [
              {
                random_score:
                {}
              }]
            }
          },
          stored_fields: "id userName attributeId lastAccessDate inviteCode userRank cardId cardRank displayCardId level revision lbCount".split(" ")
        };
        console.log("searchQuery", JSON.stringify(a));
        var u = !1,
          v = function(c)
          {
            if (u || 0 < c.hits.total)
            {
              b.raidRequestPickUpUserIdList = [];
              b.raidRequestPickUpSavedAt = Date.parse(new Date) / 1E3 | 0;
              var d = c.hits.hits;
              e.each(d, function(a)
              {
                var c;
                c = !1;
                d[0] && d[0].fields && (c = !0);
                if (c)
                {
                  c = {};
                  for (var f in a.fields) c[f] = a.fields[f][0]
                }
                else c = a._source;
                b.raidRequestPickUpUserIdList.push(c.id)
              })
            }
            else
            {
              u = !0;
              var f = Date.parse(h.currentTime) / 1E3;
              c = new Date(1E3 * (f - 86400));
              var f = new Date(1E3 * (f + 600)),
                g, k, l, m, n, p, q, r;
              g = 10 > c.getMonth() + 1 ? "0" + (c.getMonth() + 1) : c.getMonth() + 1;
              k = 10 > c.getDate() ? "0" + c.getDate() : c.getDate();
              l = 10 > c.getHours() ? "0" + c.getHours() : c.getHours();
              m = 10 > c.getMinutes() ? "0" + c.getMinutes() : c.getMinutes();
              n = 10 > f.getMonth() + 1 ? "0" + (f.getMonth() + 1) : f.getMonth() + 1;
              p = 10 > f.getDate() ? "0" + f.getDate() : f.getDate();
              q = 10 > f.getHours() ? "0" + f.getHours() : f.getHours();
              r = 10 > f.getMinutes() ? "0" + f.getMinutes() : f.getMinutes();
              c = c.getFullYear() + "-" + g + "-" + k + "T" + l + ":" + m + ":00.000+0900";
              f = f.getFullYear() + "-" + n + "-" + p + "T" + q + ":" + r + ":00.000+0900";
              a.query.function_score.query.bool.must = [
              {
                range:
                {
                  lastAccessDate:
                  {
                    gte: c,
                    lte: f
                  }
                }
              }];
              console.log("new searchQuery", JSON.stringify(a));
              t.ajaxPost(b.searchLinkList.friend, a, v)
            }
          };
        t.ajaxPost(b.searchLinkList.friend, a, v)
      }
    },
    ia = function(a, b, d)
    {
      if (!a || !b) return !1;
      var c = {};
      a = a.section;
      c.questType = a.questType;
      c.title = l.name;
      c.battleTitle = a.title;
      c.userQuestAdventureList = t.getPageJson().userQuestAdventureList;
      c.rewardCodeArr = [];
      a.secret && (c.secret = a.secret);
      c.questBattle = b.questBattle;
      c.eventFlag = !0;
      c.ap = b.questBattle.ap ? b.questBattle.ap : 0;
      c.difficulty = b.questBattle.difficulty;
      c.cleared = b.cleared;
      c.missionStatus1 = b.missionStatus1;
      c.missionStatus2 = b.missionStatus2;
      c.missionStatus3 = b.missionStatus3;
      c.raidId = d.raidId;
      b = U.dropItemJson(b);
      b.firstClearReward && (c.firstClearReward = b.firstClearReward);
      b.firstClearRewardName && (c.firstClearRewardName = b.firstClearRewardName);
      b.firstClearRewardQuantity && (c.firstClearRewardQuantity = b.firstClearRewardQuantity);
      b.addDropItem && (c.addDropItem = b.addDropItem);
      b.addDropItemName && (c.addDropItemName = b.addDropItemName);
      b.addDropItemQuantity && (c.addDropItemQuantity = b.addDropItemQuantity);
      c.rewardCodeArr = b.list;
      c.rewardNameArr = b.nameList;
      c.rewardQuantityArr = b.quantityList;
      return c
    },
    P = function(a)
    {
      e.each(a, function(a, b)
      {
        (b = e.findWhere(h.bossList,
        {
          id: a.raidId
        })) ? (a.combo = b.combo, b = 1 + .1 * a.resultList.length, "RELIEF" == a.type && (b += .2), 3 < b && (b = 3), a.bonus = b.toFixed(1)) : a.combo = 0;
        b = 9999;
        "SELF" == a.type ? b = 0 < a.resultList.length ? 1 : 2 : "RELIEF" == a.type && (b = e.findWhere(a.resultList,
        {
          attackUserId: a.userId
        }) ? 3 : 4);
        a.sortKey = b;
        m.push(a)
      });
      m = e.sortBy(m, "sortKey")
    },
    Y = function(a, c)
    {
      $(b.ready.target).on("webkitAnimationEnd", function()
      {
        g.changeBg("web_black.jpg");
        $(b.ready.target).off();
        $(b.ready.target).on("webkitAnimationEnd", function(a)
        {
          "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
        });
        t.ajaxPost(b.linkList.userQuestAdventureRegist,
        {
          adventureId: String(a)
        }, function(d)
        {
          b.responseSetStorage(d);
          $("#commandDiv").on("nativeCallback", function(d, e)
          {
            $("#commandDiv").off();
            g.setWebView(!0);
            e && e.isSkipped && (d = {}, d.adventureId = String(a), t.ajaxPost(b.linkList.adventureSkip, d, function(a)
            {
              b.responseSetStorage(a)
            }));
            c && c()
          });
          setTimeout(function()
          {
            var b = {
              canAuto: !0,
              canOpenLog: !0
            };
            g.setWebView(!1);
            window.isBrowser ? $("#commandDiv").trigger("nativeCallback") : g.startStory(String(a), b)
          }, 500)
        })
      });
      b.addClass(b.ready.target, "preNativeFadeIn")
    },
    G = function()
    {
      b.setStyle(aa);
      m = [];
      P(h.userEventRaidBossList);
      B = h.userEventRaidChallengeList;
      v = h.userEventRaid.count >= h.userEventRaid.eventRaid.totalChallengeOpenCount;
      C && (A = !1);
      var a = {
        mapWidth: 1,
        mapHeight: 1,
        enemyList: h.enemyList,
        bossList: h.bossList,
        shouldCallCutin: A
      };
      g.changeBg("web_black.jpg");
      g.startBgm(l.viewParameterMap.BGM);
      ja();
      g.pushEventRaid(a);
      b.tapBlock(!0);
      n = !1;
      window.isBrowser && $("#commandDiv").trigger("nativeCallback", ["SCENE_PUSH_EVENT_RAID"])
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
      id: "userSectionList"
    },
    {
      id: "userQuestBattleList"
    },
    {
      id: "userFollowList"
    },
    {
      id: "userQuestAdventureList"
    },
    {
      id: "userChapterList"
    },
    {
      id: "pieceList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function()
    {
      if (b.questNativeResponse)
      {
        b.responseSetStorage(b.questNativeResponse);
        g.endQuest();
        g.setWebView(!0);
        if (b.questBattleModel)
        {
          x = null;
          if (0 < b.questNativeResponse.userQuestBattleResultList[0].diskAcceleNum || 0 < b.questNativeResponse.userQuestBattleResultList[0].diskBlastNum || 0 < b.questNativeResponse.userQuestBattleResultList[0].diskChargeNum) x = b.questBattleModel;
          b.questBattleModel = null
        }
        b.supportUserList = null;
        b.questNativeResponse = null
      }
      t.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      h = t.getPageJson();
      z = Date.parse(h.currentTime) / 1E3;
      u = h.enemyList.length;
      U.supportPickUp(h);
      if (b.raidRequestPickUpUserIdList)
      {
        var a = Date.parse(new Date) / 1E3 | 0;
        (1 > b.raidRequestPickUpUserIdList.length || 3600 < a - b.raidRequestPickUpSavedAt) && R()
      }
      else R();
      b.historyArr = ["MyPage", "EventRaidTop"];
      b.clearSectionModel = null;
      b.clearChapterModel = null;
      if (l = h.eventList.filter(function(a, b)
        {
          if ("RAID" == a.eventType) return !0
        })[0])
      {
        h.eventMaster = l;
        E = e.filter(h.closedUserEventRaidBossList, function(a)
        {
          return "CLOSE" == a.status && a.modified
        });
        A = 0 < E.length;
        var c, d;
        e.filter(h.eventRaidStoryList, function(a)
        {
          C || (c = a.clearStoryId, V = a.description, d = a.sequenceId, C = b.storage.userQuestAdventureList.findWhere(
          {
            adventureId: c
          }) ? !1 : !0)
        });
        C ? 1 == d ? Y(c, function()
        {
          b.tapBlock(!1);
          n = !0;
          b.eventFirstNavi(["navi_01", "navi_02", "navi_03"], l.eventId, "raid", function()
          {
            G()
          })
        }) : A ? (g.startBgm(l.viewParameterMap.BGM), $("#commandDiv").on("nativeCallback", function(a, d)
        {
          $("#commandDiv").off();
          b.tapBlock(!1);
          n = !0;
          K(function()
          {
            g.hideEventRaid();
            g.stopBgm();
            Y(c, function()
            {
              G()
            })
          })
        }), g.pushEventRaid(
        {
          mapWidth: 1,
          mapHeight: 1,
          enemyList: [],
          bossList: [],
          shouldCallCutin: A
        }), b.tapBlock(!0), n = !1, window.isBrowser && $("#commandDiv").trigger("nativeCallback", ["SCENE_PUSH_EVENT_RAID"])) : G() : G()
      }
      else location.href = "#/MyPage"
    },
    startCommand: function() {},
    removeCommand: function() {},
    paging: function(a)
    {
      k.pageNum = a;
      k.updateLog(a)
    },
    awakeSuspend: function(a)
    {
      k && (k.infoView.awakeSuspend(a), z = a)
    },
    remove: function(a)
    {
      g.hideEventRaid();
      q = D = x = v = u = C = null;
      A = !1;
      E = B = m = y = null;
      $("#commandDiv").off();
      k && (k.removeBossDetail(), k.trigger("removeBossListView"), k.trigger("removeView"), k.remove());
      a()
    }
  }
});
