define("underscore backbone backboneCommon ajaxControl command text!template/campaign/quiz/CampaignQuizTop.html text!css/campaign/quiz/CampaignQuizTop.css js/view/tutorial/TutorialPopupView".split(" "), function(k, t, a, p, f, w, x, u)
{
  function g(a)
  {
    var b = {
      id: "0"
    };
    b.key = v[a];
    f.storyMotionL2d(b)
  }
  t.Model.extend();
  var q, h, r, n = {
      0: "魔纪奇迹问答~＠你能全部答对吗＠也会计时哦,要注意♪",
      1: "辛苦了＠机会可不止一次哦＠可以的话再挑战一次吧",
      2: "啪啪啪♪＠恭喜全对!＠全部答完真是痛快呢"
    },
    v = {
      0: "quiz1",
      1: "quiz5",
      2: "quiz6",
      3: "quiz2",
      4: "quiz3"
    },
    y = function()
    {
      var m = t.View.extend(
      {
        events: function()
        {
          var b = {};
          b[a.cgti + " .start"] = this.startQuiz;
          b[a.cgti + " .selectAnswerBtn"] = this.answer;
          b[a.cgti + " #nextBlock"] = this.next;
          b[a.cgti + " #tweetBtn"] = this.tweetBtn;
          b[a.cgti + " #backto"] = this.backToTop;
          b[a.cgti + " #retry"] = this.retry;
          b[a.cgti + " #helpBtn"] = this.helpPopup;
          return b
        },
        initialize: function(a)
        {
          h = p.getPageJson();
          this.beforeChallenge = h.userQuizSectionList;
          this.correctNum = this.nowQuizNum = this.totalQuizNum = 0;
          this.template = k.template(w);
          this.createDom()
        },
        render: function()
        {
          var a = k.findWhere(h.campaignList,
          {
            campaignType: "QUIZ"
          });
          this.$el.html(this.template(
          {
            quizList: h.quizSectionList,
            userList: h.userQuizSectionList,
            currentTime: h.currentTime,
            cpId: a.id
          }));
          return this
        },
        createDom: function()
        {
          a.content.append(this.render().el);
          a.setGlobalView();
          f.getBaseData(a.getNativeObj());
          var b = {};
          b.key = v[0];
          b.type = 1;
          b.id = "0";
          b.x = 248;
          b.y = 1024 === a.displayWidth ? Math.floor(a.doc.getElementsByTagName("body")[0].offsetHeight / 2) : Math.ceil(a.shortSize / 2);
          f.startL2d(b);
          b = n[0].replace(/＠/g, "<br>");
          a.doc.getElementById("charaSerif").getElementsByClassName("charaName")[0].textContent = "八云 御魂";
          a.doc.getElementById("charaSerif").getElementsByClassName("serifFont")[0].innerHTML = b;
          a.ready.hide()
        },
        startQuiz: function(b)
        {
          b.preventDefault();
          if (!a.isScrolled())
          {
            var c = b.currentTarget.dataset.section | 0;
            c && (this.correctNum = this.nowQuizNum = this.totalQuizNum = 0, this.section = c, b = {}, b.quizSectionId = c, c = function(a)
            {
              this.quizList = a.quizList;
              this.totalQuizNum = this.quizList.length;
              this.firstQuizSet()
            }.bind(this), p.ajaxPost(a.linkList.campaignQuizStart, b, c))
          }
        },
        firstQuizSet: function()
        {
          a.androidKeyStop = !0;
          a.addClassId("globalMenuContainer", "hide");
          a.addClassId("helpBtn", "hide");
          a.doc.getElementById("correctNums").textContent = this.correctNum;
          a.doc.getElementById("totalNums").textContent = this.totalQuizNum;
          var b = k.findWhere(h.quizSectionList,
          {
            quizSectionId: this.section
          });
          a.doc.getElementById("diffTtl").innerHTML = b.title + "&nbsp;&nbsp;挑战中";
          a.doc.getElementById("resultTtl").innerHTML = b.title + "&nbsp;&nbsp;结果";
          for (var c = b.firstClearReward, b = b.completeReward, c = c.split("_"), e = -1 < c.indexOf("EVENT") ? "event" : -1 < c.indexOf("GIFT") ? "gift" : "main", l = "", d = 1; d < c.length - 1; d++) 1 < d && (l += "_"), l += c[d].toLowerCase();
          for (var b = b.split("_"), c = -1 < b.indexOf("EVENT") ? "event" : -1 < b.indexOf("GIFT") ? "gift" : "main", g = "", d = 1; d < b.length - 1; d++) 1 < d && (g += "_"), g += b[d].toLowerCase();
          a.doc.getElementById("firstClearImg").innerHTML = '<img src="/magica/resource/image_web/item/' + e + "/" + l + '.png">';
          a.doc.getElementById("completeClearImg").innerHTML = '<img src="/magica/resource/image_web/item/' + c + "/" + g + '.png">';
          a.doc.getElementById("retry").dataset.section = this.section;
          a.addClassId("countDown", "show");
          var m = this;
          a.addClass(a.doc.getElementById("countDown").getElementsByClassName("three")[0], "on");
          f.startSe(1008);
          $(".three").on("webkitAnimationEnd", function(b)
          {
            $(".three").off();
            f.startSe(1008);
            a.removeClass(b.currentTarget, "on");
            a.addClass(a.doc.getElementById("countDown").getElementsByClassName("two")[0], "on")
          });
          $(".two").on("webkitAnimationEnd", function(b)
          {
            $(".two").off();
            f.startSe(1008);
            a.removeClass(b.currentTarget, "on");
            a.addClass(a.doc.getElementById("countDown").getElementsByClassName("one")[0], "on")
          });
          $(".one").on("webkitAnimationEnd", function(b)
          {
            $(".one").off();
            f.startSe(1002);
            a.removeClass(b.currentTarget, "on");
            a.addClass(a.doc.getElementById("countDown").getElementsByClassName("start")[0], "on")
          });
          $(".start").on("webkitAnimationEnd", function(b)
          {
            $(".start").off();
            a.removeClass(b.currentTarget, "on");
            m.startTime = (new Date).getTime();
            m.quizFunc();
            a.removeClassId("countDown", "show");
            a.addClassId("selectWrap", "hide");
            a.removeClassId("quizWrap", "hide");
            a.addClassId("quizBase", "during");
            a.addClassId("charaSerif", "hide");
            m.timerCount()
          })
        },
        quizFunc: function(b)
        {
          b = this.quizList[this.nowQuizNum];
          a.doc.getElementById("quizTtl").textContent = "第 " + (this.nowQuizNum + 1) + " 問";
          a.doc.getElementById("selectAnswer").getElementsByClassName("answer1")[0].innerHTML = '<span class="b_screen"></span><div class="maskWrap"></div><div class="effect01"></div><div class="effect02"></div>' + b.options1;
          a.doc.getElementById("selectAnswer").getElementsByClassName("answer2")[0].innerHTML = '<span class="b_screen"></span><div class="maskWrap"></div><div class="effect01"></div><div class="effect02"></div>' + b.options2;
          a.doc.getElementById("selectAnswer").getElementsByClassName("answer3")[0].innerHTML = '<span class="b_screen"></span><div class="maskWrap"></div><div class="effect01"></div><div class="effect02"></div>' + b.options3;
          a.doc.getElementById("selectAnswer").getElementsByClassName("answer4")[0].innerHTML = '<span class="b_screen"></span><div class="maskWrap"></div><div class="effect01"></div><div class="effect02"></div>' + b.options4;
          a.doc.getElementById("quizTumb").innerHTML = "";
          if (b.imagePath && "0" != b.imagePath)
          {
            a.removeClassId("quizTumb", "none");
            var c = a.createElement("img");
            c.src = b.imagePath;
            a.doc.getElementById("quizTumb").appendChild = c
          }
          else a.addClassId("quizTumb", "none");
          this.typewriter(b.body)
        },
        answer: function(b)
        {
          b.preventDefault();
          if (!a.isScrolled())
          {
            a.tapBlock(!0);
            clearInterval(r);
            var c = this.quizList[this.nowQuizNum];
            a.doc.getElementById("quizBodyWrap").innerHTML = c.body.replace(/＠/g, "<br>");
            var e = this;
            $(".maskWrap").on("webkitAnimationEnd", function()
            {
              $(".maskWrap").off();
              e.nowQuizNum < e.totalQuizNum ? (a.addClassId("nextBlock", "show"), a.tapBlock(!1)) : e.finish()
            });
            var l = b.currentTarget.dataset.ansernum | 0;
            this.selectAnswer = b.currentTarget;
            this.nowQuizNum++;
            l === c.correctAnswerNum ? (f.startSe("1607"), g(3), a.addClass(b.currentTarget, "correct"), this.correctNum = this.correctNum + 1 | 0, a.doc.getElementById("correctNums").textContent = this.correctNum) : (f.startSe("1702"), g(4), a.addClass(b.currentTarget, "wrong"))
          }
        },
        next: function(b)
        {
          b.preventDefault();
          a.isScrolled() || (a.removeClassId("nextBlock", "show"), a.removeClass(this.selectAnswer, "correct"), a.removeClass(this.selectAnswer, "wrong"), this.selectAnswer = null, this.quizFunc())
        },
        finish: function()
        {
          this.clearTime = (new Date).getTime() - this.startTime;
          clearInterval(this.countupTimer);
          3599990 < this.clearTime && (this.clearTime = 3599990);
          var b = this.timeParser(this.clearTime);
          a.doc.getElementById("correctResult").textContent = this.correctNum + "/" + this.totalQuizNum + "题";
          a.doc.getElementById("timeResult").textContent = b;
          a.doc.getElementById("timeWrap").textContent = b;
          this.nowQuizNum = 0;
          b = {};
          b.quizSectionId = this.section;
          b.correctNum = this.correctNum;
          b.clearRecord = this.clearTime;
          var c = function(b)
          {
            a.responseSetStorage(b);
            var c = this;
            setTimeout(function()
            {
              c.afterFinish(b);
              a.tapBlock(!1)
            }, 400)
          }.bind(this);
          p.ajaxPost(a.linkList.campaignQuizEnd, b, c)
        },
        afterFinish: function(b)
        {
          a.addClassId("finish", "show");
          b = k.findWhere(b.userQuizSectionList,
          {
            quizSectionId: this.section
          });
          var c = k.findWhere(h.quizSectionList,
            {
              quizSectionId: this.section
            }),
            e = this.timeParser(this.clearTime);
          a.doc.getElementById("correctResult").textContent = this.correctNum + "/" + this.totalQuizNum + "题";
          a.doc.getElementById("timeResult").textContent = e;
          c = k.findWhere(this.beforeChallenge,
          {
            quizSectionId: this.section,
            campaignId: c.campaignId
          });
          console.log(b);
          c || a.addClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("firstClearReward")[0], "newGet");
          b.completeRewardAt && (!c || c && !c.completeRewardAt) ? a.addClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("completeClearReward")[0], "newGet") : b.completeRewardAt || a.addClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("completeClearReward")[0], "notGet");
          (!c || c && this.correctNum > c.maxCorrectNum) && a.addClass(a.doc.getElementsByClassName("correctResultWrap")[0], "newRecord");
          e = a.doc.getElementById("quiz_" + b.campaignId + "_" + b.quizSectionId);
          e.getElementsByClassName("correctCountNum")[0].textContent = b.maxCorrectNum + "/" + this.totalQuizNum + "题";
          var l = this.timeParser(b.fastestRecord);
          b.fastestRecord && (e.getElementsByClassName("timeNum")[0].textContent = l);
          b.firstClearRewardAt && a.addClass(e.querySelector(".entryReward .itemWrap"), "cleared");
          b.completeRewardAt && a.addClass(e.querySelector(".completeReward .itemWrap"), "cleared");
          c && (this.beforeChallenge = k.without(this.beforeChallenge, c));
          this.beforeChallenge.push(b);
          console.log(this.beforeChallenge);
          this.correctNum < this.totalQuizNum ? (a.doc.getElementById("charaSerif").getElementsByClassName("serifFont")[0].innerHTML = n[1].replace(/＠/g, "<br>"), g(1)) : (a.doc.getElementById("charaSerif").getElementsByClassName("serifFont")[0].innerHTML = n[2].replace(/＠/g, "<br>"), g(2));
          var d = this;
          setTimeout(function()
          {
            f.startSe(1601);
            setTimeout(function()
            {
              a.removeClass(d.selectAnswer, "correct");
              a.removeClass(d.selectAnswer, "wrong");
              d.selectAnswer = null;
              a.removeClassId("finish", "show");
              a.addClassId("quizWrap", "hide");
              a.removeClassId("quizBase", "during");
              a.removeClassId("charaSerif", "hide");
              a.addClassId("quizBase", "finish");
              a.removeClassId("quizResultWrap", "hide");
              d.correctNum < d.totalQuizNum ? f.startSe(1701) : f.startSe(1306);
              setTimeout(function()
              {
                a.removeClassId("backto", "off");
                a.removeClassId("retry", "off")
              }, 1E3)
            }, 1750)
          }, 250)
        },
        tweetBtn: function(b)
        {
          b.preventDefault();
          if (!a.isScrolled())
          {
            b = k.findWhere(h.quizSectionList,
            {
              quizSectionId: this.section
            });
            var c = "★八云御魂的魔纪奇迹问答★%0a［难度:" + b.title + "］%0a［答对数：" + this.correctNum + "／" + this.totalQuizNum + "］%0a魔法纪录正在举办问答活动!%0a";
            this.correctNum === this.totalQuizNum && (c = this.timeParser(this.clearTime), c = "★八云御魂的魔纪奇迹问答★%0a［难度:" + b.title + "］%0a［答对数:全部答对］%0a［时间:" + c + "］%0a魔法纪录正在举办问答活动!%0a");
            c = encodeURI(c).replace(/%250a/g, "%0a");
            b = encodeURI("魔纪,魔纪5周年,魔纪奇迹问答");
            f.browserOpen("https://twitter.com/share?text=" + c + "%0a&hashtags=" + b + "&count=none&lang=ja")
          }
        },
        backToTop: function(b)
        {
          b.preventDefault();
          a.isScrolled() || (a.doc.getElementById("charaSerif").getElementsByClassName("serifFont")[0].innerHTML = n[0].replace(/＠/g, "<br>"), g(0), a.removeClass(a.doc.getElementsByClassName("correctResultWrap")[0], "newRecord"), a.removeClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("firstClearReward")[0], "newGet"), a.removeClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("completeClearReward")[0], "newGet"), a.removeClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("completeClearReward")[0], "notGet"), a.addClassId("quizResultWrap", "hide"), a.androidKeyStop = !1, a.removeClassId("globalMenuContainer", "hide"), a.removeClassId("quizBase", "finish"), a.removeClassId("selectWrap", "hide"), a.addClassId("backto", "off"), a.addClassId("retry", "off"), a.removeClassId("helpBtn", "hide"))
        },
        retry: function(b)
        {
          b.preventDefault();
          a.isScrolled() || (setTimeout(function()
          {
            a.doc.getElementById("charaSerif").getElementsByClassName("serifFont")[0].innerHTML = n[0].replace(/＠/g, "<br>");
            g(0);
            a.removeClass(a.doc.getElementsByClassName("correctResultWrap")[0], "newRecord");
            a.removeClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("firstClearReward")[0], "newGet");
            a.removeClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("completeClearReward")[0], "newGet");
            a.removeClass(a.doc.getElementById("quizResultWrap").getElementsByClassName("completeClearReward")[0], "notGet");
            a.addClassId("quizResultWrap", "hide");
            a.removeClassId("quizBase", "finish");
            a.addClassId("backto", "off");
            a.addClassId("retry", "off")
          }, 4E3), this.startQuiz(b))
        },
        timerCount: function()
        {
          var b = a.doc.getElementById("timeWrap"),
            c = this.startTime,
            e = function()
            {
              clearInterval(this.countupTimer)
            }.bind(this);
          this.countupTimer = setInterval(function()
          {
            var a = (new Date).getTime() - c,
              d = new Date(a);
            if (3599990 < d) b.textContent = "59分59秒99", e();
            else
            {
              var a = d.getMinutes(),
                f = d.getSeconds(),
                d = d.getMilliseconds() / 10 | 0,
                a = (0 < a ? a + "分" : "") + (f + "秒" + ("0" + d).substr(-2, 2));
              b.textContent = a
            }
          }, 80)
        },
        typewriter: function(b)
        {
          var c = a.doc.getElementById("quizBodyWrap"),
            e = 0,
            f = b.length;
          c.innerHTML = "";
          r = setInterval(function()
          {
            var a = b.substr(e, 1);
            "＠" === a && (a = "<br>");
            c.innerHTML += a;
            e = e + 1 | 0;
            e === f && clearInterval(r)
          }, 90)
        },
        timeParser: function(a)
        {
          var b = new Date(a);
          a = b.getMinutes();
          var e = b.getSeconds(),
            b = b.getMilliseconds() / 10 | 0;
          return (0 < a ? a + "分" : "") + (e + "秒" + ("0" + b).substr(-2, 2))
        },
        helpPopup: function(b)
        {
          b.preventDefault();
          if (!a.isScrolled())
          {
            var c;
            new a.PopupClass(
            {
              popupType: "tutorial"
            }, null, function()
            {
              u.prototype.parentView = this;
              c = new u(
              {
                imgArr: ["navi_01"],
                type: "campaign",
                eventType: "quiz",
                eventId: "1325"
              });
              a.doc.getElementsByClassName("popupInner")[0].appendChild(c.render().el)
            }, function()
            {
              c.removeView()
            })
          }
        },
        removeFunc: function(a)
        {
          this.off();
          this.remove();
          a && a()
        }
      });
      a.setStyle(x);
      q = new m
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
    fetch: function(a, b)
    {
      p.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      y()
    },
    startCommand: function()
    {
      f.changeBg("web_0016.ExportJson");
      f.startBgm("bgm03_story16")
    },
    removeCommand: function()
    {
      f.endL2d()
    },
    remove: function(a)
    {
      q ? q.removeFunc(a) : a()
    }
  }
});
