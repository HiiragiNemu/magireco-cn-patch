define("underscore backbone backboneCommon ajaxControl command text!template/campaign/story_mission/CampaignStoryMission.html text!css/campaign/story_mission/CampaignStoryMission.css".split(" "), function(e, k, c, f, d, l, m)
{
  k.Model.extend();
  var g, h, n = function()
  {
    var b = k.View.extend(
    {
      events: function()
      {
        var a = {};
        a[c.cgti + " #helpBtn"] = this.naviPop;
        return a
      },
      initialize: function(a)
      {
        h = f.getPageJson();
        e.findWhere(h.campaignList,
        {
          campaignType: "MISSION_STORY"
        }) ? (this.template = e.template(l), this.createDom()) : location.href = "#/MyPage"
      },
      render: function()
      {
        this.$el.html(this.template(
        {
          campaign: this.campaignModel
        }));
        return this
      },
      naviPop: function(a)
      {
        a.preventDefault();
        c.isScrolled() || c.eventFirstNavi(["navi_01"], this.campaignModel.id, "mission_story", function() {}, !1, "campaign")
      },
      rewardPop: function(a)
      {
        a.preventDefault();
        c.isScrolled() || new c.PopupClass(
        {
          title: "服装一览",
          content: "",
          exClass: "missionStoryPop",
          popupType: "typeB"
        })
      },
      createDom: function()
      {
        this.campaignModel = e.findWhere(h.campaignList,
        {
          campaignType: "MISSION_STORY"
        });
        c.content.append(this.render().el);
        c.setGlobalView();
        d.getBaseData(c.getNativeObj());
        c.ready.hide()
      },
      removeFunc: function(a)
      {
        console.log("remove");
        this.off();
        this.remove();
        a && a()
      }
    });
    c.setStyle(m);
    g = new b
  };
  return {
    needModelIdObj: [
    {
      id: "user"
    },
    {
      id: "gameUser"
    },
    {
      id: "userStatusList"
    },
    {
      id: "userItemList"
    },
    {
      id: "userPatrolList"
    }],
    fetch: function(b, a)
    {
      f.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      n()
    },
    startCommand: function()
    {
      var b = f.getPageJson();
      if (e.findWhere(b.campaignList,
        {
          campaignType: "MISSION_STORY"
        }))
      {
        var a = e.findWhere(b.campaignList,
          {
            campaignType: "MISSION_STORY"
          }).parameterMap.BG_IMG,
          b = e.findWhere(b.campaignList,
          {
            campaignType: "MISSION_STORY"
          }).parameterMap.BGM;
        a ? d.changeBg(a + ".ExportJson") : d.changeBg("web_common.ExportJson");
        b ? d.startBgm(b) : d.startBgm("bgm01_anime07")
      }
      else d.changeBg("web_common.ExportJson");
      d.startBgm(c.settingBgm)
    },
    remove: function(b)
    {
      g ? g.removeFunc(b) : b()
    }
  }
});
