define("underscore backbone backboneCommon ajaxControl command js/event/EventArenaRankMatch/parts/AttackCount js/event/EventArenaRankMatch/parts/AttackCountItemPopup".split(" "), function(d, e, b, g, h, c, f)
{
  return e.View.extend(
  {
    className: "recoverAttackCountBtn btn b_pink TE se_decide",
    events: function()
    {
      var a = {};
      a[b.cgti] = this.tapBtn;
      return a
    },
    initialize: function(a)
    {
      this.model = a.model;
      this.pageJson = a.pageJson;
      this.template = d.template('<span class="b_screen"></span>回复');
      this._views = a._views;
      $("#matchingWrap .nomatch .textSec").append(this.render().el)
    },
    render: function()
    {
      this.$el.html(this.template(
      {
        model: this.model
      }));
      return this
    },
    tapBtn: function(a)
    {
      a.preventDefault();
      b.isScrolled() || 0 < this.model.attackCountInfo.num || (0 < this.model.attackCountInfo.itemNum ? this._views.AttackCountItemPopup = new f(
      {
        model: this.model,
        AttackCount: c,
        pageJson: this.pageJson
      }) : c.recoverByMoneyPopup(
      {
        model: this.model,
        pageJson: this.pageJson
      }))
    },
    removeView: function()
    {
      this.off();
      this.remove()
    }
  })
});
