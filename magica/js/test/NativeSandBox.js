define("underscore backbone backboneCommon ajaxControl command text!template/test/NativeSandBox.html text!css/test/NativeSandBox.css".split(" "), function(f, g, a, d, c, h, k)
{
  var e, l = g.View.extend(
  {
    events: function()
    {
      var b = {};
      b[a.cgti + " .cmdBtn"] = this.cmdBtn;
      return b
    },
    initialize: function(a)
    {
      this.template = f.template(h);
      this.createDom()
    },
    render: function()
    {
      this.$el.html(this.template(d.getPageJson()));
      return this
    },
    createDom: function()
    {
      a.setGlobalView();
      a.content.append(this.render().el);
      a.nativeKeyBoard("inputTest", 100, 1);
      a.ready.hide()
    },
    getValue: function()
    {
      return a.doc.getElementById("inputTest").value
    },
    cmdBtn: function(b)
    {
      b.preventDefault();
      if (!a.isScrolled()) switch (b.currentTarget.dataset.cmd)
      {
        case "40":
          this.cmd40();
          break;
        case "41":
          this.cmd41();
          break;
        case "64":
          this.cmd64();
          break;
        case "275":
          this.cmd275()
      }
    },
    cmd40: function()
    {
      $("#commandDiv").on("nativeCallback", function(b)
      {
        $("#commandDiv").off();
        new a.PopupClass(
        {
          title: "command 40",
          content: "nativeCallback()",
          closeBtnText: "OK"
        })
      });
      c.userDataInitilize();
      window.isBrowser && nativeCallback()
    },
    cmd41: function()
    {
      $("#commandDiv").on("nativeCallback", function(b)
      {
        $("#commandDiv").off();
        new a.PopupClass(
        {
          title: "command 41",
          content: "nativeCallback()",
          closeBtnText: "OK"
        })
      });
      c.configDataInitilize();
      window.isBrowser && nativeCallback()
    },
    cmd64: function()
    {
      var b = $("#popup64Temp").text();
      new a.PopupClass(
      {
        popupId: "popup64"
      }, b, function()
      {
        c.getBaseData(a.getNativeObj())
      })
    },
    cmd275: function()
    {
      var b = this.getValue();
      b ? d.ajaxPost(a.linkList.questGetReplayData,
      {
        userQuestBattleResultId: b
      }, function(b)
      {
        var d = {
          replayData: b.replayData,
          replayVersion: b.replayVersion,
          retireUrl: "/magica/index.html#/NativeSandBox"
        };
        a.preNativeFadeIn(function()
        {
          a.ready.show();
          c.stopBgm();
          $("#commandDiv").on("nativeCallback", function(b)
          {
            $("#commandDiv").off();
            a.ready.target.className = "";
            c.changeBg(a.background);
            c.startBgm(a.bgm);
            a.androidKeyStop = !1;
            c.setWebView();
            a.ready.hide()
          });
          c.startQuestRelpay(d);
          window.isBrowser && nativeCallback()
        }, 500)
      }) : new a.PopupClass(
      {
        title: "错误",
        content: "请在输入框中输入userQuestBattleResultId。",
        closeBtnText: "OK"
      })
    }
  });
  g.View.extend(
  {
    id: "scenarioImage",
    initialize: function(a)
    {
      this.template = f.template($("#popup64Temp").text());
      this.createDom()
    },
    render: function()
    {
      this.$el.html(this.template());
      return this
    },
    createDom: function()
    {
      a.doc.getElementById("NativeSandBox").append(this.render().el)
    },
    remove: function()
    {
      this.off();
      this.remove()
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
      d.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      a.setStyle(k);
      e = new l
    },
    remove: function(a)
    {
      e && e.remove();
      a()
    }
  }
});
