define("underscore backbone backboneCommon ajaxControl command text!template/test/SoundTest.html text!css/test/SoundTest.css".split(" "), function(e, d, b, g, c, l, m)
{
  var n = [
      ["01", "卡片详情中的自我介绍"],
      ["02", "获取抽卡时"],
      ["03", "第①节通关"],
      ["04", "第二节通关"],
      ["05", "第三节通关"],
      ["06", "自己紹介演出用①"],
      ["07", "自己紹介演出用②"],
      ["08", "自己紹介演出用③"],
      ["09", "自己紹介演出用④"],
      ["10", "自己紹介演出用⑤"],
      ["11", "自己紹介演出用⑥"],
      ["12", "自己紹介演出用⑦"],
      ["13", "强化"],
      ["14", "強化MAX"],
      ["15", "章节Lv 上升"],
      ["16", "魔力解放１回目"],
      ["17", "魔力解放２回目"],
      ["18", "魔力解放３回目"],
      ["19", "MagiaLv 上升"],
      ["20", "觉醒（稀有度上升）②"],
      ["21", "觉醒（稀有度上升）③"],
      ["22", "觉醒（稀有度上升）④"],
      ["23", "觉醒（稀有度上升）⑤"],
      ["24", "当天第一时间 登录"],
      ["25", "時間変化①6-9時"],
      ["26", "時間変化②11-13時"],
      ["27", "時間変化③17-19時"],
      ["28", "時間変化④22-24時"],
      ["29", "時間変化⑤上記以外"],
      ["30", "关卡"],
      ["31", "镜界"],
      ["32", "GvG"],
      ["33", "点击时的线条（默认①）"],
      ["34", "点击时的对话（默认②）"],
      ["35", "点击时的线条（默认 ③）"],
      ["36", "点击时的对话（默认 ④）"],
      ["37", "点击时的线条 (章节Lv2)"],
      ["38", "点击时的线条 (章节Lv3)"],
      ["39", "点击时的线条 (章节Lv4)"],
      ["40", "点击时的线条 (章节Lv5)"],
      ["41", "点击时的线条（多次点击）"],
      ["42", "以战斗开头"],
      ["43", "勝利①（★１、２、３）"],
      ["44", "勝利②（★４）"],
      ["45", "勝利③（★５）"],
      ["46", "勝利④（★６）"],
      ["47", "光盘组①"],
      ["48", "光盘组②"],
      ["49", "光盘组③"],
      ["50", "光盘组 ④"],
      ["51", "磁盘组（连携）"],
      ["52", "磁盘组（连携）"],
      ["53", "第一次攻击①（长线）"],
      ["54", "第一次攻击②（长线）"],
      ["55", "第一次攻击③（长线）"],
      ["56", "2,3回目攻撃時①"],
      ["57", "2,3回目攻撃時②"],
      ["58", "2,3回目攻撃時③"],
      ["59", "第二次攻击①（同角色）"],
      ["60", "第二次攻击②（同角色）"],
      ["61", "第三次攻击①（同角色）"],
      ["62", "第三次攻击②（同角色）"],
      ["63", "Magia 时间① (★1,2,3)"],
      ["64", "Magia时间②（Magia★4）"],
      ["65", "Magia时间③（Magia★5）"],
      ["66", "Magia时间④（Magia★6）"],
      ["67", "在 Doppel"],
      ["68", "攻击时（连携）"],
      ["69", "受到攻击时（连携）"],
      ["70", "技能（目标：自身）"],
      ["71", "技能（目标：我方）"],
      ["72", "技能（目标：敌方）"],
      ["73", "伤害（正常）"],
      ["74", "伤害（垂死）"],
      ["75", "戦闘不能"]
    ],
    h, p = d.View.extend(
    {
      events: function()
      {
        var a = {};
        a[b.cgti + " .playMovie"] = this.playMovie;
        a[b.cgti + " #playBtn"] = this.playFile;
        a[b.cgti + " #stopBtn"] = this.stopFunc;
        a[b.cgti + " #playVoiceBtn"] = this.playVoice;
        a[b.cgti + " #charaVoCreateBtn"] = this.createBtn;
        return a
      },
      initialize: function(a)
      {
        this.template = e.template(l);
        this.createDom()
      },
      render: function()
      {
        this.$el.html(this.template(g.getPageJson()));
        return this
      },
      createDom: function()
      {
        b.setGlobalView();
        b.content.append(this.render().el);
        f.prototype.parentView = this;
        f.prototype.template = e.template($("#BtnTemp").text());
        b.ready.hide();
        b.scrollSet("hiddenWrap", "scrollInner")
      },
      stopFunc: function(a)
      {
        a.preventDefault();
        b.isScrolled() || c.stopBgm()
      },
      playFile: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a = a.currentTarget.parentNode.getElementsByClassName("commonInput")[0], a.value && (-1 !== a.value.indexOf("bgm") ? (c.stopBgm(), c.startBgm(a.value)) : -1 !== a.value.indexOf("se") && (c.stopSe(), c.startSe(a.value))))
      },
      playMovie: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled())
        {
          var k = a.currentTarget.parentNode.getElementsByClassName("commonInput")[0];
          k.value && ($(b.ready.target).on("webkitAnimationEnd", function()
          {
            c.changeBg("web_black.jpg");
            $(b.ready.target).off();
            $(b.ready.target).on("webkitAnimationEnd", function(a)
            {
              "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
            });
            $("#commandDiv").on("nativeCallback", function(a, q)
            {
              b.ready.target.className = "readyFadeOut";
              c.startBgm(b.settingBgm);
              c.changeBg("web_common.ExportJson");
              c.setWebView();
              $("#commandDiv").off()
            });
            setTimeout(function()
            {
              c.setWebView(!1);
              c.stopBgm();
              c.playCharaMovie(k.value + ".usm")
            }, 500)
          }), b.addClass(b.ready.target, "preNativeFadeIn"))
        }
      },
      playVoice: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (a = a.currentTarget.parentNode.getElementsByClassName("commonInput")[0], a.value && (c.stopVoice(), c.startVoice(a.value)))
      },
      createBtn: function(a)
      {
        a.preventDefault();
        if (!b.isScrolled() && (a = a.currentTarget.parentNode.getElementsByClassName("commonInput")[0], a.value))
        {
          this.trigger("btnRemove");
          var c = a.value,
            d = b.doc.createDocumentFragment();
          e.each(n, function(a)
          {
            var b = {};
            b.title = a[1];
            b.charaId = c;
            b.key = a[0];
            a = new f(
            {
              model: b
            });
            d.appendChild(a.render().el)
          });
          b.doc.querySelector("#voBtnWrap").appendChild(d);
          b.scrollRefresh(null, null, !0)
        }
      }
    }),
    f = d.View.extend(
    {
      className: "voiceWrap",
      initialize: function()
      {
        this.listenTo(this.parentView, "btnRemove", this.removeView)
      },
      events: function()
      {
        var a = {};
        a[b.cgti + " .voBtn"] = this.voBtnFunc;
        return a
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          model: this.model
        }));
        return this
      },
      removeView: function()
      {
        this.off();
        this.remove()
      },
      voBtnFunc: function(a)
      {
        a.preventDefault();
        b.isScrolled() || (c.stopVoice(), c.startVoice(a.currentTarget.dataset.filename))
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
      b.setStyle(m);
      h = new p;
      c.stopBgm()
    },
    remove: function(a)
    {
      h.remove();
      a()
    }
  }
});
