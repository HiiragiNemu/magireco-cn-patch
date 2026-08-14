define("underscore backbone backboneCommon ajaxControl command text!template/event/raid/EventRaidCloseTop.html text!css/event/raid/EventRaidTop.css".split(" "), function(h, m, a, n, r, t, u)
{
  var d, p = !1,
    f = !1,
    l, e, k, w = m.View.extend(
    {
      initialize: function(a)
      {
        this.template = h.template(t);
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template(e));
        return this
      },
      createDom: function()
      {
        a.setGlobalView();
        a.content.append(this.render().el);
        this.missionView = new v;
        a.ready.hide()
      }
    }),
    v = m.View.extend(
    {
      id: "MissionArea",
      events: function()
      {
        var b = {};
        b[a.cgti + " .closeBtn"] = this.closeBtn;
        b[a.cgti + " #tabBtn .btn"] = this.tabScreen;
        return b
      },
      initialize: function(b)
      {
        this.template = h.template($("#missionParts").text());
        this.createDom();
        a.scrollSet("missionScrollWrap", "mission1List");
        f && a.scrollSet("missionScrollWrap", "mission2List");
        $(this.el.getElementsByClassName("common_tab")[0].getElementsByClassName(d)[0]).trigger(a.cgti)
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
        a.doc.getElementById("overlapContainer").appendChild(this.render().el);
        a.doc.getElementById("curtain").className = "show";
        q.prototype.rootView = this;
        q.prototype.template = h.template($("#missionListParts").text());
        this.createMissionList();
        this.clearMissionCount()
      },
      createMissionList: function()
      {
        var b = a.doc.createDocumentFragment(),
          c = a.doc.createDocumentFragment(),
          g = l,
          g = h.sortBy(g, function(a)
          {
            return a.cleared && ("PERSONAL" == a.eventRaidChallenge.bean || "TOTAL" == a.eventRaidChallenge.bean && f) ? -999 + a.eventRaidChallenge.sortKey : a.eventRaidChallenge.sortKey
          });
        h.each(g, function(a, g)
        {
          a.receivedAt || (g = new q(
          {
            model: a
          }), "PERSONAL" == a.eventRaidChallenge.bean ? b.appendChild(g.render().el) : c.appendChild(g.render().el))
        });
        d = "mission1";
        1 > b.children.length ? (a.doc.getElementById("mission1").innerHTML = '<p class="noMission ts_white">已完成全部任务</p>', d = "mission2") : a.doc.getElementById("mission1").appendChild(b);
        1 > c.children.length ? (a.doc.getElementById("mission2").innerHTML = '<p class="noMission ts_white">已完成全部任务</p>', d = "mission1") : (a.doc.getElementById("mission2").appendChild(c), f || (a.doc.getElementById("mission2").innerHTML += "<div id='totalMissionValidityMask' class='c_pink'>全体击破报酬需击破自己发现的BOSS<br>【" + e.userEventRaid.eventRaid.totalChallengeOpenCount + "个以上】<br>即可解锁全体击败的报酬</div>"));
        this.el.className = d;
        r.getBaseData(a.getNativeObj());
        c = b = null
      },
      clearMissionCount: function()
      {
        var b = 0,
          c = 0;
        h.each(l, function(a, d)
        {
          !a.receivedAt && a.cleared && ("PERSONAL" == a.eventRaidChallenge.bean ? b++ : "TOTAL" == a.eventRaidChallenge.bean && f && c++)
        });
        0 < b ? (a.doc.getElementById("mission1Batch").innerText = b, a.addClass(a.doc.getElementById("mission1Batch"), "on")) : a.removeClass(a.doc.getElementById("mission1Batch"), "on");
        0 < c ? (a.doc.getElementById("mission2Batch").innerText = c, a.addClass(a.doc.getElementById("mission2Batch"), "on")) : a.removeClass(a.doc.getElementById("mission2Batch"), "on")
      },
      tabScreen: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          b = b.currentTarget;
          var c = a.doc.getElementById("tabBtn").getElementsByClassName("current")[0];
          a.removeClass(c, "current");
          a.removeClass(this.el, d);
          a.addClass(this.el, b.dataset.wrap);
          a.doc.getElementById("listTitle").innerText = b.dataset.missionName;
          a.addClass(b, "current");
          d = b.dataset.wrap;
          a.scrollRefresh("missionScrollWrap", d + "List", !0)
        }
      },
      closeBtn: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled())
        {
          var c = this;
          a.doc.getElementById("curtain").className = "";
          a.addClass(this.el, "close");
          $(c.el).on("webkitAnimationEnd", function()
          {
            $(c.el).off();
            location.href = "#/MyPage"
          })
        }
      },
      removeView: function()
      {
        this.trigger("removeChildView");
        this.remove()
      }
    }),
    q = m.View.extend(
    {
      tagName: "div",
      className: "missionChild wrap commonFrame4",
      events: function()
      {
        var b = {};
        b[a.cgti + " .missionBtn"] = this.missionBtn;
        return b
      },
      initialize: function(a)
      {
        this.listenTo(this.rootView, "removeChildView", this.removeView);
        this.missionValidity = "PERSONAL" == this.model.eventRaidChallenge.bean || "TOTAL" == this.model.eventRaidChallenge.bean && f;
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
      missionBtn: function(b)
      {
        b.preventDefault();
        if (!a.isScrolled() && !p)
        {
          p = !0;
          var c = this;
          n.ajaxPost(a.linkList.raidChallengeReceive,
          {
            challengeId: this.model.challengeId
          }, function(b)
          {
            if ("error" !== b.resultCode)
            {
              a.responseSetStorage(b);
              p = !1;
              var d = function()
              {
                c.rootView.clearMissionCount()
              };
              1 > Object.keys(b).length || window.isLocal && window.isBrowser && 2 > Object.keys(b).length ? new a.PopupClass(
              {
                content: "由于领取期限已过，<br>无法领取该任务报酬",
                closeBtnText: "确定",
                popupType: "typeC",
                exClass: "missionPop"
              }, null, null, d) : new a.PopupClass(
              {
                content: "已领取1个任务报酬。<br><br>※可直接获得领取的道具。",
                closeBtnText: "确定",
                popupType: "typeC",
                exClass: "missionPop"
              }, null, null, d);
              c.removeView();
              "PERSONAL" === c.model.eventRaidChallenge.bean ? (b = a.doc.getElementById("mission1").getElementsByClassName("wrap").length, 1 > b && (a.doc.getElementById("mission1").innerHTML = '<p class="noMission ts_white">已完成全部任务</p>')) : "TOTAL" === c.model.eventRaidChallenge.bean && (b = a.doc.getElementById("mission2").getElementsByClassName("wrap").length, 1 > b && (a.doc.getElementById("mission2").innerHTML = '<p class="noMission ts_white">已完成全部任务</p>'));
              b = new Date;
              c.model.receivedAt = b.getFullYear() + "/" + (b.getMonth() + 1) + "/" + b.getDate() + " " + b.getHours() + ":" + b.getMinutes() + ":" + b.getSeconds();
              a.scrollRefresh(null, null, !0)
            }
          })
        }
      },
      removeView: function()
      {
        this.off();
        this.remove()
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
      n.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      e = n.getPageJson();
      e.eventId = e.EventRaidSummary.eventId;
      a.historyArr = ["MyPage", "EventRaidCloseTop"];
      a.setStyle(u);
      f = e.userEventRaid.count >= e.userEventRaid.eventRaid.totalChallengeOpenCount;
      l = e.userEventRaidChallengeList;
      k = new w
    },
    startCommand: function() {},
    removeCommand: function() {},
    remove: function(b)
    {
      l = d = f = null;
      a.doc.getElementById("curtain").className = "";
      k && (k.missionView && k.missionView.removeView(), k.trigger("removeView"), k.remove());
      b()
    }
  }
});
