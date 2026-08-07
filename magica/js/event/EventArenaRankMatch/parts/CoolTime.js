define("underscore backbone backboneCommon ajaxControl command text!template/event/EventArenaRankMatch/parts/CoolTimePopup.html js/event/EventArenaRankMatch/Utility".split(" "), function(h, n, c, k, p, l, m)
{
  var a = {
    isEnd: !1,
    init: function(b)
    {
      a.isEnd = !1;
      a.model = b.model;
      a.pageJson = b.pageJson;
      a.setTimer(
      {
        currentTime: a.pageJson.currentTime,
        endTime: a.model.coolDownTimeInfo.nextTime
      });
      return a
    },
    setTimer: function(b)
    {
      a.timer = c.countDownTimerManager(
      {
        currentTime: b.currentTime,
        endTime: b.endTime,
        setSelector: "#coolDownTimeNumSec",
        isDispH: !1,
        callback: function()
        {
          a.isEnd = !0
        }
      });
      a.timer.start()
    },
    recoverPopup: function()
    {
      var b = c.calcExpendStone(
        {
          quantity: a.model.coolDownTimeInfo.recoverNeedNum,
          isPurchasedMoneyOnly: !1
        }),
        d = "statusCanUse",
        e = "",
        f = "取消",
        g = "解除";
      0 > b.totalMoney && (d = "statusCanNotUse", f = "确定", g = null, e = '魔法石<span class="c_pink">' + Math.abs(b.totalMoney) + "个</span>,<br>无法解除冷却时间。");
      a.popup = new c.PopupClass(
      {
        title: "解除冷却",
        content: h.template(l)(
        {
          model:
          {
            statusClass: d,
            canNotUseText: e,
            recoverNeedNum: a.model.coolDownTimeInfo.recoverNeedNum,
            userStone: c.getTotalStone(),
            remainStone: b
          }
        }),
        popupType: "typeB",
        decideBtnText: g,
        decideBtnEvent: function()
        {
          a.popup.remove();
          a.getCoolTimeInfo(
          {
            callback: a.callbackUnlockCoolTime
          })
        },
        closeBtnText: f,
        popupId: "EventArenaRankMatchAttackCountPopup"
      }, null, function() {}, function() {})
    },
    getCoolTimeInfo: function(b)
    {
      var d = this;
      if (1 == a.isEnd) new c.PopupClass(
      {
        title: "冷却结束",
        content: "冷却时间已结束。",
        popupType: "typeC",
        closeBtnText: "关闭"
      }, null, null, null);
      else if (m.isOpenEvent(
        {
          pageJson: d.pageJson,
          pageAccessLocalTime: d.model.pageAccessLocalTime,
          rankMatchEventInfo: d.model.eventInfo
        }))
      {
        var e = b.callback;
        c.tapBlock(!0);
        k.ajaxPost(c.linkList.eventArenaRankMatchUnlockCoolDownTime,
        {}, function(a)
        {
          c.tapBlock(!1);
          c.responseSetStorage(a);
          e(
          {
            _this: d,
            res: a
          })
        })
      }
      else new c.PopupClass(
      {
        title: "活动已结束",
        content: "不在活动开放期间。",
        closeBtnText: "确定",
        canClose: !1,
        popupType: "typeC"
      }, null, function() {}, function()
      {
        location.href = "#/ArenaTop"
      })
    },
    callbackUnlockCoolTime: function(b)
    {
      a.isEnd = !0;
      $("#coolDownTimeNumSec").html("00:00");
      a.timer.stop();
      new c.PopupClass(
      {
        title: "解除冷却",
        content: "已解除冷却时间。",
        closeBtnText: "确定"
      }, null, function() {}, function() {})
    },
    removeView: function()
    {
      a.timer && a.timer.stop()
    }
  };
  return a
});
