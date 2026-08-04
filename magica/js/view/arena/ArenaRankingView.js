define("underscore backbone backboneCommon ajaxControl command text!template/arena/ArenaRanking.html js/view/arena/ArenaPartsView js/view/arena/ArenaInfoPartsView".split(" "), function(f, h, c, k, l, m, g, d)
{
  return h.View.extend(
  {
    events: function()
    {
      return {}
    },
    initialize: function()
    {
      this.template = f.template(m);
      this.createDom()
    },
    render: function()
    {
      this.model = k.getPageJson();
      this.$el.html(this.template(
      {
        model: this.model
      }));
      return this
    },
    createDom: function()
    {
      c.content.append(this.render().el);
      this.createView();
      c.setGlobalView();
      l.getBaseData(c.getNativeObj());
      c.ready.hide()
    },
    createView: function()
    {
      d.prototype.rootView = this;
      this.infoView = new d;
      c.doc.getElementById("bpGuageRanking").appendChild(this.infoView.render().el);
      this.createMattingList()
    },
    createMattingList: function()
    {
      var b = this.model.userArenaBattleMatch,
        e = [];
      if (b.opponentUserId1)
      {
        var a = {},
          a = b.opponentUserArenaBattleInfo1;
        a.userId = b.opponentUserId1;
        a.difficult = "HIGHER" === a.type ? 2 : "SAME" === a.type ? 1 : 0;
        a.battleType = b.arenaBattleType;
        e.push(a);
        a = null
      }
      b.opponentUserId2 && (a = {}, a = b.opponentUserArenaBattleInfo2, a.userId = b.opponentUserId2, a.difficult = "HIGHER" === a.type ? 2 : "SAME" === a.type ? 1 : 0, a.battleType = b.arenaBattleType, e.push(a), a = null);
      b.opponentUserId3 && (a = {}, a = b.opponentUserArenaBattleInfo3, a.userId = b.opponentUserId3, a.difficult = "HIGHER" === a.type ? 2 : "SAME" === a.type ? 1 : 0, a.battleType = b.arenaBattleType, e.push(a), a = null);
      g.prototype.rootView = this;
      g.prototype.template = f.template($("#arenaParts").text());
      if (0 < e.length)
      {
        var d = c.doc.createDocumentFragment();
        f.each(e, function(a, b)
        {
          a = new g(a);
          d.appendChild(a.render().el)
        });
        c.doc.getElementById("matchingWrap").appendChild(d)
      }
      else c.doc.getElementById("matchingWrap").innerHTML = '<p class="nomatch commonFrame4">现在没有可以对战的对手<br>请稍后再来</p>'
    },
    removeHandler: function()
    {
      this.trigger("removeView");
      this.off();
      this.remove()
    }
  })
});
