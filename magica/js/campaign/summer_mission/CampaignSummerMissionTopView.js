define("underscore backbone backboneCommon ajaxControl command text!template/campaign/summer_mission/CampaignSummerMissionTop.html js/campaign/summer_mission/CampaignSummerMissionTopListView".split(" "), function(f, p, b, n, t, u, q)
{
  var g, k;
  return p.View.extend(
  {
    events: function()
    {
      var a = {};
      a[b.cgti + " #allReserve"] = this.allReserve;
      return a
    },
    initialize: function(a)
    {
      g = n.getPageJson();
      this.firstViewId = a.dispId;
      this.template = f.template(u);
      this.createDom()
    },
    render: function()
    {
      this.$el.html(this.template(g));
      return this
    },
    createDom: function()
    {
      b.content.append(this.render().el);
      this.eventMission = this.makeEventMissionList();
      this.eventMissionClassList = [];
      this.createView();
      b.setGlobalView();
      k = this.eventMissionClassList[0];
      if (void 0 == k)
      {
        var a = b.doc.createElement("div");
        a.className = "limitedWrap";
        a.innerHTML = '<p class="noMission ts_white">没有可以挑战的任务</p>';
        b.doc.getElementById("missionScrollWrap").appendChild(a);
        a = null
      }
      var a = new Date(this.eventMission[0].startAt),
        c = new Date(this.eventMission[0].closeAt),
        a = a.getMonth() + 1 + "/" + a.getDate() + "～" + (c.getMonth() + 1) + "/" + c.getDate() + " " + c.getHours() + ":" + ("0" + c.getMinutes()).substr(-2, 2);
      b.doc.getElementById("campaignTime").innerText = a;
      f.groupBy(this.eventMission[0].missionList, function(a)
      {
        return a.challenge.startAt
      });
      void 0 != k && this.allReservCheck();
      if (0 < this.eventMissionClassList.length)
        for (a = this.eventMissionClassList.length; 0 < a;) a = a - 1 | 0, b.scrollSet("missionScrollWrap", this.eventMissionClassList[a]);
      t.getBaseData(b.getNativeObj());
      a = g.currentTime;
      c = g.limitedChallengeGroupList[0];
      if (void 0 != c.viewParameterMap && c.viewParameterMap)
      {
        for (var c = c.viewParameterMap.START_DATE, d = 0; d < c.length; d++)
          if (c[d] = c[d].replace(/-/g, "/"), (new Date(g.currentTime)).getTime() < (new Date(c[d])).getTime())
          {
            a = c[d];
            break
          }(new Date(g.currentTime)). getTime() != (new Date(a)).getTime() ? (a = new Date(a), b.doc.getElementById("listWrap").classList.add("next_add_time"), b.doc.getElementById("nexTime").innerText = a.getMonth() + 1 + "/" + a.getDate() + " " + a.getHours() + ":" + ("0" + a.getMinutes()).substr(-2, 2)) : b.doc.getElementById("nextTimeArea").classList.add("off")
      }
      else b.doc.getElementById("nextTimeArea").classList.add("off");
      b.ready.hide()
    },
    createView: function()
    {
      q.prototype.rootView = this;
      q.prototype.template = f.template(b.doc.getElementById("missionParts").textContent);
      this.eventMission && this.createEventMissionList();
      this.trigger("storyCheck")
    },
    makeEventMissionList: function()
    {
      if (b.storage.userLimitedChallengeList.toJSON())
      {
        var a = [],
          c = Date.parse(g.currentTime),
          d = f.sortBy(g.limitedChallengeGroupList, function(a)
          {
            return a.sortKey
          }),
          e = b.storage.userLimitedChallengeList.toJSON(),
          e = f.sortBy(e, function(a)
          {
            return a.challenge.sortKey
          }),
          l = f.groupBy(e, function(a)
          {
            return a.challenge.groupId
          });
        b.panelMissionList = [];
        f.each(d, function(d, e)
        {
          e = Date.parse(d.startAt);
          if ("PANEL" !== d.viewType)
          {
            var f = d.closeAt ? Date.parse(d.closeAt) : Date.parse(d.endAt);
            d.openFlag = e <= c && f >= c ? !0 : !1;
            d.checkId = "e_" + d.id;
            d.missionList = l[d.id] ? l[d.id] : [];
            a.push(d)
          }
          else d.openFlag = e <= c ? !0 : !1, d.missionList = l[d.id] ? l[d.id] : [], b.panelMissionList.push(d)
        });
        return a
      }
    },
    createEventMissionList: function()
    {
      var a = Date.parse(n.getPageJson().currentTime),
        c = [],
        d = this;
      f.each(this.eventMission, function(e, l)
      {
        c[l] = 0;
        if (e.openFlag)
        {
          var g = b.doc.createDocumentFragment(),
            m = e.checkId,
            k = e.id;
          b.addClass(b.doc.getElementById("MissionList"), m);
          var h = f.sortBy(e.missionList, function(a)
            {
              return a.clearedCount >= a.challenge.count ? -999 + a.challenge.sortKey : a.challenge.sortKey
            }),
            n = Date.parse(e.endAt),
            p = e.closeAt ? Date.parse(e.closeAt) : n,
            r = a > n && a < p ? !0 : !1;
          f.each(h, function(a, b)
          {
            a.challenge.groupId != k || a.receivedAt || r && a.clearedCount < a.challenge.count || (a = new q(a, m), g.appendChild(a.render().el), c[l]++)
          });
          0 < c[l] ? (h = b.doc.createElement("div"), h.id = m, h.className = "limitedWrap " + m + " on", h.appendChild(g), e.shortName ? e.shortName.replace(/＠/g, "<br>") : e.shortTitle.replace(/＠/g, "<br>"), d.eventMissionClassList.push(m), b.doc.getElementById("missionScrollWrap").appendChild(h), h = null) : r || (h = b.doc.createElement("div"), h.id = m, h.className = "limitedWrap " + m, h.innerHTML = '<p class="noMission ts_white">没有可以挑战的任务</p>', e.shortName ? e.shortName.replace(/＠/g, "<br>") : e.shortTitle.replace(/＠/g, "<br>"), d.eventMissionClassList.push(m), b.doc.getElementById("missionScrollWrap").appendChild(h), h = null)
        }
      })
    },
    checkFirstView: function()
    {
      var a = this,
        c = !1;
      f.each(this.eventMission, function(b, e)
      {
        b.eventId && b.eventId === Number(a.firstViewId) ? b.openFlag && (c = b.checkId) : b.campaignId && b.campaignId === Number(a.firstViewId) && b.openFlag && (c = b.checkId)
      });
      c || new b.PopupClass(
      {
        title: "不在期间内",
        content: "不在期间内,<br>该任务不存在",
        closeBtnText: "确定",
        popupType: "typeC"
      });
      this.firstViewId = null
    },
    dailyCalcLeftTime: function()
    {
      var a;
      a = Date.parse(g.currentTime) / 1E3;
      var c = new Date(1E3 * (a + 86400));
      a = (Date.parse(c.getFullYear() + "/" + (c.getMonth() + 1) + "/" + c.getDate() + " 0:00:00") / 1E3 - a) / 60;
      60 > a ? a = Math.floor(a) + "分" : 60 < a && 1440 > a ? a = Math.floor(a / 60) + "时间" : (a = a / 60 / 24, a = 30 < a ? Math.floor(a / 30) + "个月" : Math.floor(a) + "日");
      b.doc.getElementById("dailyTimeNum").textContent = a
    },
    eventCalcLeftTime: function(a)
    {
      a = a.closeAt ? new Date(a.closeAt) : new Date(a.endAt);
      a = a.getMonth() + 1 + "月" + a.getDate() + "日" + a.getHours() + ":" + a.getMinutes();
      b.doc.getElementById("eventTimeNum").textContent = a
    },
    allReserve: function(a)
    {
      a.preventDefault();
      b.isScrolled() || a.currentTarget.classList.contains("off") || 0 < this.tapCount || (this.tapCount++, b.addClass(b.doc.getElementById("allReserve"), "off"), this.allReserveAdvance())
    },
    allReserveAdvance: function()
    {
      var a = this,
        c = k.split("_"),
        d = {};
      "e" === c[0] && (d.groupId = Number(c[1]), n.ajaxPost(b.linkList.userLimitedChallengeAllReceieve, d, function(c)
      {
        if ("error" !== c.resultCode)
        {
          var d = f.findWhere(a.eventMission,
            {
              checkId: k
            }),
            e = 0,
            g = [];
          f.each(d.missionList, function(a, b)
          {
            a && !a.receivedAt && a.clearedCount >= a.challenge.count && (g.push(a.challengeId), e++)
          });
          d = function()
          {
            a.trigger("afterAllRecieve", k, g);
            a.allReservCheck();
            a.tapCount = 0;
            b.addClass(b.doc.getElementById("allReserve"), "off");
            b.scrollRefresh(null, null, !0)
          };
          1 > Object.keys(c).length || window.isLocal && window.isBrowser && 2 > Object.keys(c).length ? new b.PopupClass(
          {
            content: "已过领取期限,<br>无法领取该任务报酬",
            closeBtnText: "确定",
            popupType: "typeC",
            exClass: "missionPop"
          }, null, null, d) : new b.PopupClass(
          {
            content: "任务报酬" + e + "件已领取。<br><br>※魔法少女请到礼物盒领取。<br>※领取的道具已直接发放。",
            closeBtnText: "确定",
            popupType: "typeC",
            exClass: "missionPop"
          }, null, null, d);
          b.responseSetStorage(c);
          a.eventMission = a.makeEventMissionList()
        }
      }))
    },
    allReservCheck: function()
    {
      b.removeClass(b.doc.getElementById("allReserve"), "hide");
      var a = k.split("_");
      "e" === a[0] ? (a = f.findWhere(g.limitedChallengeGroupList,
      {
        id: Number(a[1])
      }), b.addClass(b.doc.getElementById("allReserve"), "off"), "剧情" === a.viewType && b.addClass(b.doc.getElementById("allReserve"), "hide")) : b.addClass(b.doc.getElementById("allReserve"), "off");
      this.allReserveCheckAdvance()
    },
    allReserveCheckAdvance: function()
    {
      var a = f.findWhere(this.eventMission,
        {
          checkId: k
        }),
        c = 0;
      a ? (f.each(a.missionList, function(a, b)
      {
        a.receivedAt || a.clearedCount >= a.challenge.count && c++
      }), 0 < c ? b.removeClass(b.doc.getElementById("allReserve"), "off") : b.addClass(b.doc.getElementById("allReserve"), "off")) : b.addClass(b.doc.getElementById("allReserve"), "off")
    },
    removeView: function()
    {
      this.trigger("removeChildView");
      this.off();
      this.remove()
    }
  })
});
