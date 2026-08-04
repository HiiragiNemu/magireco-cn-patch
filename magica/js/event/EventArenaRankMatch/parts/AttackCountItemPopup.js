define("underscore backbone backboneCommon ajaxControl command text!template/event/EventArenaRankMatch/parts/AttackCountItemPopup.html".split(" "), function(f, g, b, k, l, h)
{
  return g.View.extend(
  {
    events: function()
    {
      var a = {};
      a[b.cgti + " .statusItemUse #amountMinus"] = this.tapAmountMinus;
      a[b.cgti + " .statusItemUse #amountPlus"] = this.tapAmountPlus;
      a[b.cgti + " .statusItemUse .maxBtn"] = this.tapMaxBtn;
      return a
    },
    initialize: function(a)
    {
      this.model = a.model;
      this.pageJson = a.pageJson;
      this.AttackCount = a.AttackCount;
      this.template = f.template(h);
      this.popupModel = this.createModel(
      {
        model: this.model
      });
      this.createDom()
    },
    render: function()
    {
      this.$el.html(this.template(
      {
        model: this.popupModel
      }));
      return this
    },
    createDom: function()
    {
      var a = this;
      a.popup = new b.PopupClass(
      {
        title: "对战次数回复",
        popupType: "typeB",
        decideBtnText: "回复",
        decideBtnEvent: function()
        {
          var c = Number($(".statusItemUse #amountSelects").text());
          a.popup.remove();
          a.AttackCount.recoverAttackCount(
          {
            recoverInfo:
            {
              type: "Item",
              num: c
            },
            pageJson: a.pageJson,
            model: a.model,
            callback: a.AttackCount.callbackRecoverAttackCount
          })
        },
        closeBtnText: "取消",
        popupId: "EventArenaRankMatchAttackCountPopup"
      }, null, function()
      {
        $("#EventArenaRankMatchAttackCountPopup .popupTextArea").append(a.render().el);
        a.controlAmountBtn()
      }, function() {})
    },
    createModel: function(a)
    {
      a = a.model;
      var c = {
        statusClass: "statusItemUse",
        attackCountInfo: a.attackCountInfo,
        maxNum: 5 - a.attackCountInfo.num,
        itemUseNum: a.attackCountInfo.itemNum - 1
      };
      a.attackCountInfo.itemNum < c.maxNum && (c.maxNum = a.attackCountInfo.itemNum);
      return c
    },
    controlAmountBtn: function()
    {
      var a = this.popupModel.maxNum,
        c = Number($(".statusItemUse #amountSelects").text()),
        b = $(".statusItemUse #amountMinus"),
        d = $(".statusItemUse #amountPlus"),
        e = $(".statusItemUse .maxBtn");
      b.removeClass("off");
      d.removeClass("off");
      e.removeClass("off");
      1 == c && b.addClass("off");
      c == a && (d.addClass("off"), e.addClass("off"));
      a = this.popupModel.attackCountInfo.itemNum;
      $(".statusItemUse #itemUseNum").html(a - c);
      this.popupModel.attackCountInfo.recoverNum = c + this.popupModel.attackCountInfo.num
    },
    tapAmountMinus: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (a = Number($(".statusItemUse #amountSelects").text()), $(".statusItemUse #amountSelects").html(a - 1), this.controlAmountBtn())
    },
    tapAmountPlus: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (a = Number($(".statusItemUse #amountSelects").text()), $(".statusItemUse #amountSelects").html(a + 1), this.controlAmountBtn())
    },
    tapMaxBtn: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (a = this.popupModel.maxNum, $(".statusItemUse #amountSelects").html(a), this.controlAmountBtn())
    },
    removeView: function()
    {
      this.off();
      this.remove()
    }
  })
});
