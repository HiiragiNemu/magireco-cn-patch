define(["underscore", "backbone", "backboneCommon", "ajaxControl"], function(e, f, b, g)
{
  return f.View.extend(
  {
    tagName: "div",
    className: "present",
    events: function()
    {
      var a = {};
      a[b.cgti + " .wrap"] = this.selectPresent;
      a[b.cgti + " .btn"] = this.receivePresent;
      return a
    },
    initialize: function(a)
    {
      this.template = e.template($("#presentParts").text());
      this.listenTo(this.model.collection, "selectReset", this.selectReset);
      this.listenTo(this.model.collection, "removeView", this.removeView);
      this.listenTo(this.model, "change", this.removeView)
    },
    render: function()
    {
      this.$el.html(this.template(
      {
        model: this.model.toJSON()
      }));
      return this
    },
    selectPresent: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        var d = this.model.toJSON(),
          c = this.parentView.selectPresentId;
        this.$el.hasClass("select") ? c.some(function(a, b)
        {
          a == d.id && c.splice(b, 1)
        }) : c.push(d.id);
        this.el.className = this.$el.hasClass("select") ? "present" : "present select"
      }
    },
    selectReset: function()
    {
      this.el.className = "present"
    },
    receivePresent: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        var d = this;
        a = b.linkList.receivePresent;
        var c = {};
        c.presentId = [this.model.toJSON().id];
        g.ajaxPost(a, c, function(a)
        {
          a = d.parentView.presentDeleteCheck(a);
          b.responseSetStorage(a);
          b.storage.presentList.trigger("presentListUpdate");
          new b.PopupClass(
          {
            title: "成功",
            popupId: "successPopup",
            content: "プレゼントを受け取りました",
            closeBtnText: "关闭"
          })
        });
        b.storage.presentList.trigger("selectReset");
        this.parentView.selectPresentId = []
      }
    },
    removeView: function()
    {
      this.off();
      this.remove()
    }
  })
});
