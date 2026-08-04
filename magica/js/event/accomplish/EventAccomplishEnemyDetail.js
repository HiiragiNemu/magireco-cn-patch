define("underscore backbone backboneCommon ajaxControl command text!template/event/accomplish/EventAccomplishEnemyDetail.html text!css/event/accomplish/EventAccomplishEnemyDetail.css".split(" "), function(g, l, a, h, f, m, n)
{
  var k, e, d, b, p = l.View.extend(
  {
    events: function()
    {
      var b = {};
      b[a.cgti + " #deckFormationLinkBtn"] = this.formationLink;
      b[a.cgti + " .arrow"] = this.waveChange;
      b[a.cgti + " .debugBtn"] = this.debugBtn;
      return b
    },
    initialize: function(b)
    {
      this.waveMaxNum = a.EventAccomplishEnemyDetail.length;
      this.waveNum = 1;
      this.template = g.template(m);
      this.createDom()
    },
    render: function()
    {
      var b = e;
      b.lock = a.questBattleModel && a.questBattleModel.canPlay ? "" : "lock";
      b.questBattle = a.questBattleModel;
      b.eventMaster = k;
      b.waveMaxNum = this.waveMaxNum;
      b.enemyDetail = a.EventAccomplishEnemyDetail;
      b.bossQuestBattle = a.userEventAccomplishQuestBattleList;
      this.$el.html(this.template(b));
      return this
    },
    createDom: function()
    {
      a.setGlobalView();
      a.content.append(this.render().el);
      console.log(this.waveMaxNum);
      1 < this.waveMaxNum && a.removeClass(a.doc.querySelector("#arrowR"), "hide");
      b = "     ".split(" ");
      a.ready.hide()
    },
    debugBtn: function(c)
    {
      c.preventDefault();
      a.isScrolled() || (c = g.template($("#debug").text()), new a.PopupClass(
      {
        title: "指令",
        content: c(),
        closeBtnText: "关闭",
        decideBtnText: "变更",
        decideBtnEvent: function()
        {
          f.enemyFormationPreviewRemove();
          var c = a.EventAccomplishEnemyDetail[0].enemyList,
            e = c.length;
          b[0] = a.doc.getElementById("displayBase").checked;
          b[1] = a.doc.getElementById("displayAlignIcon").checked;
          b[2] = a.doc.getElementById("inputX").value - 0;
          b[3] = a.doc.getElementById("inputY").value - 0;
          b[4] = a.doc.getElementById("inputScale").value - 0;
          b[5] = a.doc.getElementById("inputHp").value - 0;
          for (var d = 0; d < e; d++) "" != a.doc.getElementById("inputHp").value ? c[d].currentHp = b[5] : delete c[d].currentHp;
          c = {
            displayBase: b[0],
            displayAlignIcon: b[1],
            x: b[2],
            y: b[3],
            scale: b[4],
            enemyList: c
          };
          console.log(c);
          f.enemyFormationPreview(c);
          a.g_popup_instance.popupView.close()
        },
        popupType: "typeA"
      }, null, function()
      {
        a.nativeKeyBoard("inputX", 10, 1);
        a.nativeKeyBoard("inputY", 10, 1);
        a.nativeKeyBoard("inputScale", 10, 1);
        a.nativeKeyBoard("inputHp", 10, 1);
        b && "" != b[2] && (a.doc.getElementById("displayBase").checked = b[0], a.doc.getElementById("displayAlignIcon").checked = b[1], a.doc.getElementById("inputX").value = b[2], a.doc.getElementById("inputY").value = b[3], a.doc.getElementById("inputScale").value = b[4], 0 == b[5] ? a.doc.getElementById("inputHp").value = "" : a.doc.getElementById("inputHp").value = b[5])
      }, null))
    },
    formationLink: function(b)
    {
      b.preventDefault();
      !a.isScrolled() && a.questBattleModel && a.questBattleModel.canPlay && (location.href = "#/DeckFormation/accomplish")
    },
    waveChange: function(b)
    {
      b.preventDefault();
      a.isScrolled() || ("arrowR" == b.currentTarget.id ? (this.waveNum++, this.waveNum == this.waveMaxNum && a.addClass(a.doc.querySelector("#arrowR"), "hide"), a.removeClass(a.doc.querySelector("#arrowL"), "hide")) : (this.waveNum--, 1 == this.waveNum && a.addClass(a.doc.querySelector("#arrowL"), "hide"), a.removeClass(a.doc.querySelector("#arrowR"), "hide")), a.doc.querySelector("#currentWaveNum").className = "num" + this.waveNum, f.enemyFormationPreviewRemove(), f.enemyFormationPreview(a.EventAccomplishEnemyDetail[this.waveNum - 1]))
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
      id: "userItemList"
    },
    {
      id: "userStatusList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function()
    {
      h.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      e = h.getPageJson();
      k = g.findWhere(e.eventList,
      {
        eventType: "ACCOMPLISH"
      });
      if (a.EventAccomplishEnemyDetail)
      {
        if (a.setStyle(n), e = h.getPageJson(), d = new p, console.log(a.questBattleModel), !a.questBattleModel.questBattle.bossFlag || a.questBattleModel.canPlay && a.questBattleModel.questBattle.bossFlag) console.log(a.EventAccomplishEnemyDetail[0]),
          f.enemyFormationPreview(a.EventAccomplishEnemyDetail[0])
      }
      else location.href = "#/EventAccomplishTop"
    },
    removeCommand: function()
    {
      f.enemyFormationPreviewRemove()
    },
    remove: function(a)
    {
      d && (d.trigger("remove"), d.remove());
      b && (b = null);
      k = e = null;
      a()
    }
  }
});
