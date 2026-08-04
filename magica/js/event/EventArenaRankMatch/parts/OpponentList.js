define("underscore backbone backboneCommon ajaxControl command text!template/event/EventArenaRankMatch/parts/CoolTimePopup.html js/event/EventArenaRankMatch/parts/OpponentView js/event/EventArenaRankMatch/parts/recoverAttackCountBtnView".split(" "), function(e, r, c, t, h, u, k, l)
{
  var a = {
    init: function(b)
    {
      a.model = b.model;
      a._views = b._views;
      a.pageJson = b.pageJson;
      a.setList(
      {
        model: a.model,
        pageJson: a.pageJson,
        _views: a._views
      });
      a.setTimer(
      {
        model: a.model,
        currentTime: a.pageJson.currentTime,
        endTime: a.model.battleInfo.matchExpiredAt
      });
      return a
    },
    setList: function(b)
    {
      var m = b.model.opponentList,
        n = b.model.attackCountInfo,
        d = b._views,
        p = b.model;
      b = b.pageJson;
      d.opponentList = [];
      $("#matchingWrap").empty();
      var f = [];
      e.each(m, function(a, b, c)
      {
        0 < a.length && f.push(e.sample(a))
      });
      if (0 == n.num) $("#matchingWrap").html('<li class="nomatch"><div class="textSec">没有剩余的对战次数。<br>对战次数除每天16:00重置外,<br>也可以使用魔法石或排位赛对战券<br>进行回复。<br></div></li>'), d.RecoverAttackCountBtn = new l(
      {
        model: p,
        pageJson: b,
        _views: d
      });
      else if (0 < f.length)
      {
        var g = c.doc.createDocumentFragment(),
          q = e.template($("#arenaParts").text());
        e.each(f, function(a, b, c)
        {
          d.opponentList.push(new k(
          {
            model: a,
            template: q,
            _views: d
          }));
          g.appendChild(d.opponentList[b].render().el)
        });
        $("#matchingWrap").append(g)
      }
      else $("#matchingWrap").html('<li class="nomatch">现在没有可以对战的对手。<br>请稍后再来。</li>');
      h.getBaseData(c.getNativeObj());
      a.tapLimit()
    },
    openTimeOverPopup: function()
    {
      new c.PopupClass(
      {
        title: "超时",
        content: "匹配超时。<br>即将更换对战对手。",
        closeBtnText: "OK",
        canClose: !1,
        popupType: "typeC"
      }, null, function() {}, function()
      {
        c.EventArenaRankMatchPrm.isOpenPopup = !1;
        c.EventArenaRankMatchPrm.openTimeOverPopup = !1;
        location.href = "#/RegularEventArenaRankMatchRedirectTop"
      })
    },
    setTimer: function(b)
    {
      0 != b.model.attackCountInfo.num && (a.timer = c.countDownTimerManager(
      {
        currentTime: b.currentTime,
        endTime: b.endTime,
        setSelector: "#reloadListTimeSec",
        isDispH: !1,
        callback: function()
        {
          c.EventArenaRankMatchPrm.isOpenPopup ? c.EventArenaRankMatchPrm.openTimeOverPopup = a.openTimeOverPopup : a.openTimeOverPopup()
        }
      }), a.timer.start())
    },
    tapLimit: function()
    {
      c.EventArenaRankMatchPrm.isTapLimit = !0;
      setTimeout(function()
      {
        c.EventArenaRankMatchPrm.isTapLimit = !1
      }, 1E3)
    },
    removeView: function()
    {
      a.timer && a.timer.stop()
    }
  };
  return a
});
