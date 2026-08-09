define("underscore backbone backboneCommon ajaxControl command text!template/test/SoundTest.html text!css/test/SoundTest.css".split(" "), function(e, d, b, g, c, l, m)
{
  var n = [
      ["01", "卡牌详情中的自我介绍"],
      ["02", "扭蛋获得时"],
      ["03", "剧情第1话通关时"],
      ["04", "剧情第2话通关时"],
      ["05", "剧情第3话通关时"],
      ["06", "自我介绍演出用①"],
      ["07", "自我介绍演出用②"],
      ["08", "自我介绍演出用③"],
      ["09", "自我介绍演出用④"],
      ["10", "自我介绍演出用⑤"],
      ["11", "自我介绍演出用⑥"],
      ["12", "自我介绍演出用⑦"],
      ["13", "强化完成"],
      ["14", "强化（等级已满时）"],
      ["15", "剧情等级提升"],
      ["16", "魔力解放第1次"],
      ["17", "魔力解放第2次"],
      ["18", "魔力解放第3次"],
      ["19", "Magia等级提升"],
      ["20", "觉醒（稀有度提升）②"],
      ["21", "觉醒（稀有度提升）③"],
      ["22", "觉醒（稀有度提升）④"],
      ["23", "觉醒（稀有度提升）⑤"],
      ["24", "每日首次登录时"],
      ["25", "时间变化①（6～9时）"],
      ["26", "时间变化②（11～13时）"],
      ["27", "时间变化③（17～19时）"],
      ["28", "时间变化④（22～24时）"],
      ["29", "时间变化⑤（上述时段以外）"],
      ["30", "关卡"],
      ["31", "镜界"],
      ["32", "GvG"],
      ["33", "点击时台词（默认①）"],
      ["34", "点击时台词（默认②）"],
      ["35", "点击时台词（默认③）"],
      ["36", "点击时台词（默认④）"],
      ["37", "点击时台词（剧情等级2）"],
      ["38", "点击时台词（剧情等级3）"],
      ["39", "点击时台词（剧情等级4）"],
      ["40", "点击时台词（剧情等级5）"],
      ["41", "点击时台词（多次点击）"],
      ["42", "战斗开始时"],
      ["43", "胜利①（★1、2、3）"],
      ["44", "胜利②（★4）"],
      ["45", "胜利③（★5）"],
      ["46", "胜利④（★6）"],
      ["47", "行动盘选择①"],
      ["48", "行动盘选择②"],
      ["49", "行动盘选择③"],
      ["50", "行动盘选择④"],
      ["51", "行动盘选择（发起连携）"],
      ["52", "行动盘选择（接受连携）"],
      ["53", "第1次攻击时①（长台词）"],
      ["54", "第1次攻击时②（长台词）"],
      ["55", "第1次攻击时③（长台词）"],
      ["56", "第2、3次攻击时①"],
      ["57", "第2、3次攻击时②"],
      ["58", "第2、3次攻击时③"],
      ["59", "第2次攻击时①（同一角色）"],
      ["60", "第2次攻击时②（同一角色）"],
      ["61", "第3次攻击时①（同一角色）"],
      ["62", "第3次攻击时②（同一角色）"],
      ["63", "发动Magia时①（★1、2、3）"],
      ["64", "发动Magia时②（Magia★4）"],
      ["65", "发动Magia时③（Magia★5）"],
      ["66", "发动Magia时④（Magia★6）"],
      ["67", "发动魔女化身时"],
      ["68", "攻击时（发起连携）"],
      ["69", "攻击时（接受连携）"],
      ["70", "技能（目标：自身）"],
      ["71", "技能（目标：我方）"],
      ["72", "技能（目标：敌方）"],
      ["73", "受伤时（通常）"],
      ["74", "受伤时（濒死）"],
      ["75", "战斗不能"]
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
