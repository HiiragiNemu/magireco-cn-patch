define("underscore backbone backboneCommon ajaxControl text!template/present/PresentList.html js/view/present/PresentListPartsView".split(" "), function(e, h, b, f, k, l)
{
  return h.View.extend(
  {
    events: function()
    {
      var a = {};
      a[b.cgti + " .receiveBtn"] = this.receivePresent;
      return a
    },
    initialize: function(a)
    {
      this.selectPresentId = [];
      this.template = e.template(k);
      this.createDom()
    },
    render: function()
    {
      this.$el.html(this.template(f.getPageJson()));
      return this
    },
    createDom: function()
    {
      b.content.append(this.render().el);
      var a = this;
      this.presentItemCnt = this.presentCardCnt = 0;
      var c = b.doc.createDocumentFragment(),
        g = b.doc.createDocumentFragment();
      b.storage.presentList.each(function(b, d)
      {
        d = new l(
        {
          model: b
        });
        d.parentView = a;
        "CARD" == b.toJSON().presentType ? (c.appendChild(d.render().el), a.presentCardCnt += 1) : (g.appendChild(d.render().el), a.presentItemCnt += 1)
      });
      this.presentCntUpdate();
      b.doc.getElementById("cardWrap").appendChild(c);
      b.doc.getElementById("itemWrap").appendChild(g);
      b.ready.hide()
    },
    presentDeleteCheck: function(a)
    {
      var c = this;
      a.deleted && e.each(a.deleted.presentList, function(a)
      {
        a = b.storage.presentList.findWhere(
        {
          id: a.id
        });
        b.storage.presentList.remove(a);
        a && (a.toJSON().cardId ? --c.presentCardCnt : --c.presentItemCnt, a.clear())
      });
      this.presentCntUpdate();
      delete a.deleted;
      return a
    },
    presentCntUpdate: function()
    {
      b.doc.getElementById("presentCardCnt").innerText = this.presentCardCnt;
      b.doc.getElementById("presentItemCnt").innerText = this.presentItemCnt
    },
    receiveFunc: function(a)
    {
      var c = this;
      f.ajaxPost(b.linkList.receivePresent, a, function(a)
      {
        a = c.presentDeleteCheck(a);
        b.responseSetStorage(a);
        new b.PopupClass(
        {
          title: "成功",
          popupId: "successPopup",
          content: "プレゼントを受け取りました",
          closeBtnText: "关闭"
        })
      });
      b.storage.presentList.trigger("selectReset");
      this.selectPresentId = []
    },
    receivePresent: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        var c = {};
        switch (a.target.getAttribute("data-sale-type"))
        {
          case "ALL":
            c.receiveType = "ALL";
            break;
          case "ITEM":
            c.receiveType = "ITEM";
            break;
          case "CARD":
            c.receiveType = "CARD";
            break;
          case "SELECT":
            c.presentId = this.selectPresentId
        }
        this.receiveFunc(c)
      }
    }
  })
});
