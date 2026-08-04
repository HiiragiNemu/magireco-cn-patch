define("underscore backbone backboneCommon ajaxControl command text!template/test/StyleTemplate.html text!css/test/StyleTemplate.css js/view/tutorial/TutorialPopupView".split(" "), function(l, m, b, g, r, n, p, k)
{
  var f, h, q = m.View.extend(
  {
    events: function()
    {
      var a = {};
      a[b.cgti + " .common_tab li"] = this.tabBtn;
      a[b.cgti + " .popupBtn"] = this.popup;
      a[b.cgti + " .tutPopupBtn"] = this.tutorialPopupBtn;
      return a
    },
    initialize: function(a)
    {
      this.template = l.template(n);
      this.createDom()
    },
    render: function()
    {
      console.log("render", g.getPageJson());
      this.$el.html(this.template(g.getPageJson()));
      return this
    },
    createDom: function()
    {
      b.setGlobalView();
      b.content.append(this.render().el);
      b.ready.hide()
    },
    tabBtn: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
        for (var d = a.currentTarget.parentNode, c = d.children, g = c.length, e = 0, d = d.className, f = d.replace("common_tab ", "").replace(" ", "+"); e < g;) c[e] == a.currentTarget ? (b.addClass(c[e], "current"), -1 < d.indexOf("ml_tab") ? c[e].innerHTML = "<span>" + f + "<br>+current</span>" : c[e].innerHTML = "<span>" + f + "+current</span>") : (b.removeClass(c[e], "current"), c[e].innerHTML = "<span>" + f + "</span>"), e = e + 1 | 0
    },
    popup: function(a)
    {
      console.log(a);
      a.preventDefault();
      b.isScrolled() || (a = "true" == a.currentTarget.getAttribute("data-simple") ?
      {
        title: "ポップアップタイトル",
        content: "ポップアップテスト",
        decideBtnText: "OK",
        closeBtnText: "关闭",
        simple: !0
      } : a.currentTarget.getAttribute("data-type") ?
      {
        title: "ポップアップタイトル",
        content: "ポップアップテスト",
        decideBtnText: "OK",
        closeBtnText: "关闭",
        popupType: a.currentTarget.getAttribute("data-type")
      } :
      {
        title: "ポップアップタイトル",
        content: "ポップアップテスト",
        closeBtnText: "关闭",
        decideBtnText: "OK"
      }, new b.PopupClass(a))
    },
    tutorialPopupBtn: function(a)
    {
      console.log(a);
      a.preventDefault();
      b.isScrolled() || ("tutorial" == a.currentTarget.getAttribute("data-type") ? new b.PopupClass(
      {
        popupType: "tutorial"
      }, null, this.tutPopCallback(
      {
        type: "tutorial"
      }, a.currentTarget.getAttribute("data-img").split(",")), this.tutPopCloseEvent) : "event" == a.currentTarget.getAttribute("data-type") && b.eventFirstNavi(a.currentTarget.getAttribute("data-img").split(","), a.currentTarget.getAttribute("data-event-id"), a.currentTarget.getAttribute("data-event-type"), function() {}, !0))
    },
    tutPopCallback: function(a, d)
    {
      k.prototype.parentView = this;
      h = new k(
      {
        type: a.type,
        imgArr: d
      });
      setTimeout(function()
      {
        b.doc.getElementsByClassName("popupInner")[0].appendChild(h.render().el)
      }, 500)
    },
    tutPopCloseEvent: function()
    {
      h.removeView()
    }
  });
  return {
    needModelIdObj: [
    {
      id: "user"
    },
    {
      id: "gameUser"
    },
    {
      id: "itemList"
    },
    {
      id: "userItemList"
    },
    {
      id: "userStatusList"
    }],
    fetch: function()
    {
      g.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      b.setStyle(p);
      f = new q;
      b.scrollSet("StyleTemplate", "scrollInner");
      for (var a = b.doc.getElementsByClassName("common_tab"), d = a.length, c = 0; c < d;) $(a[c].children[0]).trigger(b.cgti), c = c + 1 | 0
    },
    remove: function(a)
    {
      f && f.remove();
      a()
    }
  }
});
