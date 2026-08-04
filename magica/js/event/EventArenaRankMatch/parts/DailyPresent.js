define("underscore backbone backboneCommon ajaxControl command text!template/event/EventArenaRankMatch/parts/DailyPresentPopup.html".split(" "), function(d, h, b, k, l, g)
{
  var a = {
    init: function(c)
    {
      a.model = c.model;
      a.pageJson = c.pageJson;
      a.callback = c.callback;
      a.model.presentInfo.daily.todayInfo ? a.openPopup(
      {
        model: a.model.presentInfo.daily.todayInfo
      }) : a.callback && a.callback()
    },
    openPopup: function(c)
    {
      var f = c.model,
        e = a;
      new b.PopupClass(
      {
        title: "每日报酬",
        content: d.template(g)(
        {
          model:
          {
            userRank: f.userRank
          }
        }),
        closeBtnText: "OK",
        popupId: "EventArenaRankMatchDailyPresentPopup"
      }, null, function()
      {
        $("#EventArenaRankMatchDailyPresentPopup #listSec").html(e.createItem(
        {
          itemList: f.itemList
        }));
        b.EventArenaRankMatchPrm.isOpenPopup = !0
      }, function()
      {
        b.EventArenaRankMatchPrm.isOpenPopup = !1;
        b.EventArenaRankMatchPrm.openTimeOverPopup && b.EventArenaRankMatchPrm.openTimeOverPopup();
        e.callback && e.callback()
      })
    },
    createItem: function(a)
    {
      a = a.itemList;
      var b = "",
        c = d.template($("#itemTemp").text());
      d.each(a, function(a, d, e)
      {
        b += c(
        {
          model:
          {
            num: a.num,
            img: a.img
          }
        })
      });
      return b
    }
  };
  return a
});
