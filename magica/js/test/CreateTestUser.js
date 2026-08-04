define("underscore backbone backboneCommon ajaxControl text!../../template/test/CreateTestUser.html text!../../css/test/CreateTestUser.css".split(" "), function(e, f, a, d, g, h)
{
  var c, k = function()
  {
    a.setStyle(h);
    var b = [];
    b[a.cgti + " #UserCreateBtn"] = function()
    {
      var b = a.doc.getElementById("userName").value;
      if (b)
      {
        var c = {};
        c.userName = b;
        $.ajax(
        {
          url: a.linkList.createGameUser,
          type: "POST",
          contentType: "application/JSON",
          dataType: "JSON",
          data: JSON.stringify(c)
        }).done(function(b)
        {
          a.loading.hide();
          new a.PopupClass(
          {
            title: "成功",
            popupId: "successPopup",
            content: "ゲームユーザーが作成されました",
            decideBtnText: "返回主页"
          }, null, function()
          {
            $("#successPopup .decideBtn").on(a.cgti, function(b)
            {
              $("#successPopup .decideBtn").off();
              a.g_popup_instance.remove();
              location.href = "#/MyPage"
            });
            window.isBrowser || localStorage.clear()
          }, !1)
        })
      }
    };
    c = new(f.View.extend(
    {
      events: function()
      {
        return b
      },
      initialize: function(a)
      {
        this.template = e.template(g);
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template(d.getPageJson()));
        return this
      },
      createDom: function()
      {
        a.content.append(this.render().el);
        a.ready.hide()
      }
    }))
  };
  return {
    needModelIdObj: [
    {
      id: "user",
      refresh: !0
    },
    {
      id: "gameUser",
      refresh: !0
    }],
    fetch: function()
    {
      d.pageModelGet(this.needModelIdObj, !0)
    },
    init: function()
    {
      k()
    },
    remove: function(a)
    {
      c && c.remove();
      a()
    }
  }
});
