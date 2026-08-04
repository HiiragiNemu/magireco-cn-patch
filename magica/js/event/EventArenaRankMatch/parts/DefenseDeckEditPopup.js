define(["underscore", "backbone", "backboneCommon", "ajaxControl", "command"], function(c, d, a, e, f)
{
  return {
    open: function(b)
    {
      new a.PopupClass(
      {
        title: "防卫编成",
        content: "设置防卫编成后才能<br>进行镜界排位赛对战。<br>请设置防卫编成。",
        popupType: "typeC",
        decideBtnText: "前往防卫编成界面",
        decideBtnEvent: function()
        {
          location.href = "#/DeckFormation/arenaRankMatchDefence"
        },
        popupId: "EventArenaRankMatchDefenseDeckEditPopup"
      }, null, function()
      {
        a.EventArenaRankMatchPrm.isOpenPopup = !0
      }, function()
      {
        a.EventArenaRankMatchPrm.isOpenPopup = !1;
        a.EventArenaRankMatchPrm.openTimeOverPopup && a.EventArenaRankMatchPrm.openTimeOverPopup()
      })
    },
    isEnableDefenseDeck: function()
    {
      var b;
      a.EventArenaRankMatchPrm && (b = a.EventArenaRankMatchPrm.isEnableDefenseDeck);
      return b
    }
  }
});
