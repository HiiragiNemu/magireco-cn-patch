define("underscore backbone backboneCommon ajaxControl command text!template/test/SdCharaTest.html text!css/test/SdCharaTest.css".split(" "), function(h, k, b, f, d, l, m)
{
  var g, n = k.View.extend(
  {
    events: function()
    {
      var a = {};
      a[b.cgti + " .groupBattleBtn"] = this.groupBattle;
      a[b.cgti + " .displayCharaBtn"] = this.displayChara;
      a[b.cgti + " .hideCharaBtn"] = this.hideChara;
      a[b.cgti + " #reverseBtn"] = this.reverseBtn;
      a[b.cgti + " .displayMultiCharaBtn"] = this.displayMultiChara;
      a[b.cgti + " .hideMultiCharaBtn"] = this.hideMultiChara;
      a[b.cgti + " .addNumBtn"] = this.addNum;
      a[b.cgti + " .stockBtn"] = this.stock;
      a[b.cgti + " .stockPopupBtn"] = this.stockPopup;
      a[b.cgti + " .stockClearBtn"] = this.stockClear;
      return a
    },
    initialize: function(a)
    {
      this.template = h.template(l);
      this.miniArray = [];
      this.createDom();
      d.changeBg("web_regular_battle_bg_19186.ExportJson")
    },
    render: function()
    {
      console.log("render", f.getPageJson());
      this.$el.html(this.template(f.getPageJson()));
      return this
    },
    createDom: function()
    {
      b.setGlobalView();
      b.content.append(this.render().el);
      b.ready.hide();
      b.nativeKeyBoard("inputCharaId", 15, 1);
      b.nativeKeyBoard("inputCharaX", 5, 1);
      b.nativeKeyBoard("inputCharaY", 5, 1);
      b.nativeKeyBoard("inputCharaScale", 4, 1);
      b.nativeKeyBoard("inputCharaFade", 4, 1)
    },
    groupBattle: function(a)
    {
      a.preventDefault();
      b.isScrolled() || $(b.doc.getElementById("RegularEventGroupBattleBoss")).toggleClass("hide")
    },
    getSdCharaPrm: function()
    {
      var a = {};
      a.index = parseInt(b.doc.getElementById("inputIndex").value);
      a.id = String(b.doc.getElementById("inputCharaId").value) + "00";
      a.x = parseFloat(b.doc.getElementById("inputCharaX").value);
      a.y = parseFloat(b.doc.getElementById("inputCharaY").value);
      a.scale = parseFloat(b.doc.getElementById("inputCharaScale").value);
      a.fade = parseFloat(b.doc.getElementById("inputCharaFade").value);
      a.isReverse = !$("#reverseBtn").hasClass("noReverse");
      a.animeList = [b.doc.getElementById("animeSelect").value];
      return a
    },
    reverseBtn: function(a)
    {
      a.preventDefault();
      b.isScrolled() || $(a.currentTarget).toggleClass("noReverse")
    },
    addNum: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        var c = a.currentTarget;
        a = b.doc.getElementById(c.dataset.target);
        var e = c.dataset.limit,
          c = parseInt(c.dataset.add),
          d = parseInt(a.value) + c;
        e && (0 < c && e <= d || 0 > c && e > d) && (d = e);
        a.value = d
      }
    },
    stock: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        a = this.getSdCharaPrm();
        var c = -1,
          e;
        for (e in this.miniArray)
          if (this.miniArray[e].index == a.index)
          {
            c = e;
            break
          } - 1 < c ? this.miniArray[c] = a : this.miniArray.push(a)
      }
    },
    stockClear: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (this.miniArray = [])
    },
    stockPopup: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        var c = "没有库存";
        0 < this.miniArray.length && (c = "<table class='popupCharaPrm'><tbody>", h.each(this.miniArray, function(a, b)
        {
          c += "<tr>";
          c += "<td>index:" + a.index + "</td>";
          c += "<td>id:" + a.id + "</td>";
          c += "<td>x:" + a.x + "</td>";
          c += "<td>y:" + a.y + "</td>";
          c += "<td>scale:" + a.scale + "</td>";
          c += "<td>fade:" + a.fade + "</td>";
          c += "<td>" + a.animeList[0] + "</td>";
          c += "</tr>"
        }), c += "</tbody></table>");
        new b.PopupClass(
        {
          content: c,
          popupType: "typeC",
          popupId: "stockPopup"
        })
      }
    },
    displayChara: function(a)
    {
      a.preventDefault();
      b.isScrolled() || d.showMiniChara(this.getSdCharaPrm())
    },
    hideChara: function(a)
    {
      a.preventDefault();
      b.isScrolled() || d.hideMiniChara()
    },
    displayMultiChara: function(a)
    {
      a.preventDefault();
      b.isScrolled() || d.showMultiMiniChara(this.miniArray)
    },
    hideMultiChara: function(a)
    {
      a.preventDefault();
      b.isScrolled() || d.hideMultiMiniChara()
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
      f.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      b.setStyle(m);
      g = new n
    },
    remove: function(a)
    {
      d.hideMultiMiniChara();
      g && g.remove();
      a()
    }
  }
});
