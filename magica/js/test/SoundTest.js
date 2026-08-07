define("underscore backbone backboneCommon ajaxControl command text!template/test/SoundTest.html text!css/test/SoundTest.css".split(" "), function(e, d, b, g, c, l, m)
{
  var n = [
      ["01", "卡牌详情中的自我介绍"],
      ["02", "扭蛋获得时"],
      ["03", "セクション①クリア時"],
      ["04", "セクション②クリア時"],
      ["05", "セクション③クリア時"],
      ["06", "自己紹介演出用①"],
      ["07", "自己紹介演出用②"],
      ["08", "自己紹介演出用③"],
      ["09", "自己紹介演出用④"],
      ["10", "自己紹介演出用⑤"],
      ["11", "自己紹介演出用⑥"],
      ["12", "自己紹介演出用⑦"],
      ["13", "强化"],
      ["14", "強化MAX"],
      ["15", "剧情等级提升"],
      ["16", "魔力解放１回目"],
      ["17", "魔力解放２回目"],
      ["18", "魔力解放３回目"],
      ["19", "Magia等级提升"],
      ["20", "覚醒（レアリティアップ）②"],
      ["21", "覚醒（レアリティアップ）③"],
      ["22", "覚醒（レアリティアップ）④"],
      ["23", "覚醒（レアリティアップ）⑤"],
      ["24", "1日の初回ログイン時"],
      ["25", "時間変化①6-9時"],
      ["26", "時間変化②11-13時"],
      ["27", "時間変化③17-19時"],
      ["28", "時間変化④22-24時"],
      ["29", "時間変化⑤上記以外"],
      ["30", "关卡"],
      ["31", "镜界"],
      ["32", "GvG"],
      ["33", "タップ時セリフ（デフォルト①）"],
      ["34", "タップ時セリフ（デフォルト②）"],
      ["35", "タップ時セリフ（デフォルト③）"],
      ["36", "タップ時セリフ（デフォルト④）"],
      ["37", "タップ時セリフ（エピソードLv２）"],
      ["38", "タップ時セリフ（エピソードLv３）"],
      ["39", "タップ時セリフ（エピソードLv４）"],
      ["40", "タップ時セリフ（エピソードLv５）"],
      ["41", "タップ時セリフ（複数回タップ）"],
      ["42", "战斗开始时"],
      ["43", "勝利①（★１、２、３）"],
      ["44", "勝利②（★４）"],
      ["45", "勝利③（★５）"],
      ["46", "勝利④（★６）"],
      ["47", "ディスクセット①"],
      ["48", "ディスクセット②"],
      ["49", "ディスクセット③"],
      ["50", "ディスクセット④"],
      ["51", "ディスクセット（コネクトした）"],
      ["52", "ディスクセット（コネクトされた）"],
      ["53", "1回目攻撃時①（長い台詞）"],
      ["54", "1回目攻撃時②（長い台詞）"],
      ["55", "1回目攻撃時③（長い台詞）"],
      ["56", "2,3回目攻撃時①"],
      ["57", "2,3回目攻撃時②"],
      ["58", "2,3回目攻撃時③"],
      ["59", "2回目攻撃時①（同一キャラ）"],
      ["60", "2回目攻撃時②（同一キャラ）"],
      ["61", "3回目攻撃時①（同一キャラ）"],
      ["62", "3回目攻撃時②（同一キャラ）"],
      ["63", "マギア時①（★１、２、３）"],
      ["64", "マギア時②（マギア★４）"],
      ["65", "マギア時③（マギア★５）"],
      ["66", "マギア時④（マギア★６）"],
      ["67", "发动魔女化身时"],
      ["68", "攻撃時（コネクトした）"],
      ["69", "攻撃時（コネクトされた）"],
      ["70", "スキル(対象：自分)"],
      ["71", "スキル(対象：味方)"],
      ["72", "スキル(対象：敵)"],
      ["73", "ダメージ(通常)"],
      ["74", "ダメージ（瀕死)"],
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
