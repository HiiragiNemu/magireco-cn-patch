define("underscore backbone backboneCommon ajaxControl command text!template/test/backdoorList.html".split(" "), function(f, m, b, e, d, n)
{
  return m.View.extend(
  {
    id: "content",
    className: "hide",
    events: function()
    {
      var a = {};
      a[b.cgti + " #seachable"] = this.seachableFunc;
      a[b.cgti + " #backdoorTutorial"] = this.tutorialFunc;
      a[b.cgti + " #backdoorTutorialReset"] = this.tutorialResetFunc;
      a[b.cgti + " #backdoorTutorialComp"] = this.tutorialCompFunc;
      a[b.cgti + " #regAccRepairReset"] = this.regAccRepairReset;
      a[b.cgti + " .reloadBtn"] = this.reloadFunc;
      a[b.cgti + " .nativeReload"] = this.nativeReloadTest;
      a[b.cgti + " .errorTestBtn"] = this.errorTest;
      a[b.cgti + " .randomError"] = this.rondomeErrorTest;
      a[b.cgti + " .tweetTest"] = this.tweetTest;
      a[b.cgti + " .fullVoiceTest"] = this.fullVoiceTest;
      a[b.cgti + " .chapterClearTest"] = this.chapterClearTest;
      a[b.cgti + " .chapter2ndClearTest"] = this.chapter2ndClearTest;
      a[b.cgti + " #chatTestBtn"] = this.chatTest;
      a[b.cgti + " .errorIdTestBtn"] = this.errorIdTestBtn;
      a[b.cgti + " #localStorageSave"] = this.localStorageSave;
      a[b.cgti + " #localStorageGet"] = this.localStorageGet;
      a[b.cgti + " #localStorageClear"] = this.localStorageClear;
      a[b.cgti + " #EventAccomplishDebugModeNormal"] = this.eventAccomplishDebugModeNormal;
      a[b.cgti + " #EventAccomplishDebugModeChallenge"] = this.eventAccomplishDebugModeChallenge;
      a[b.cgti + " #EventDungeonMapTest"] = this.eventDungeonMapTest;
      a[b.cgti + " .titlePopup"] = this.titlePopup;
      a[b.cgti + " .prologueTestBtn"] = this.prologueTest;
      a[b.cgti + " #startMirrorBattle"] = this.startMirrorBattle;
      a[b.cgti + " #commonStoryTest"] = this.commonStoryTest;
      a[b.cgti + " #mirrorBattleRetry"] = this.mirrorBattleRetry;
      a[b.cgti + " #getPurchaseStatus"] = this.getPurchaseStatus;
      a[b.cgti + " #mailSendTest"] = this.mailSendTest;
      a[b.cgti + " #ToEventWitchExchangeTest"] = this.ToEventWitchExchangeTest;
      return a
    },
    initialize: function(b)
    {
      this.template = f.template(n)
    },
    render: function()
    {
      this.$el.html(this.template());
      return this
    },
    regAccRepairReset: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        a = e.getPageJson();
        a = f.findWhere(a.regularEventList,
        {
          regularEventType: "ACCOMPLISH"
        });
        var c = 2013;
        a && (c = a.regularEventId);
        new b.PopupClass(
        {
          title: "バトルミュージアムの回復リセット",
          content: "バトルミュージアムの回復機能をリセットしますか？<br>eventId：<input id='inputEventId' class='commonFrame3' readonly='readonly' type='text' maxlength='4' value=''>",
          decideBtnEvent: function()
          {
            e.ajaxPost(b.linkList.accomplishResetCure,
            {
              regularEventId: c
            }, function(a)
            {
              new b.PopupClass(
              {
                title: "バトルミュージアムの回復リセット",
                content: "バトルミュージアムの回復機能をリセットしました",
                closeBtnText: "关闭"
              });
              b.responseSetStorage(a)
            })
          },
          decideBtnText: "重置",
          closeBtnText: "关闭"
        }, null, function()
        {
          b.doc.getElementById("inputEventId").value = c;
          b.nativeKeyBoard("inputEventId", 15, 1)
        })
      }
    },
    seachableFunc: function(a)
    {
      a.preventDefault();
      b.isScrolled() || e.ajaxPost(b.linkList.testSeachabke, null, function(a)
      {
        new b.PopupClass(
        {
          title: "完了",
          content: "検索サーバにユーザーを登録しました。<br>しばらく待つと検索できるようになります。（最長15分）",
          closeBtnText: "关闭"
        })
      })
    },
    chapterClearTest: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        var c = "";
        switch (a.currentTarget.dataset.target)
        {
          case "firstChapter":
            c = "１部一括クリア"
        }
        new b.PopupClass(
        {
          title: c,
          content: "実行するにはデッキ１が「いろは単デッキ」になっている<br>必要があります。",
          closeBtnText: "取消",
          decideBtnText: "実行する",
          decideBtnEvent: function()
          {
            e.ajaxPost(b.linkList.backdoor1stChapterClear, null, function(a)
            {
              new b.PopupClass(
              {
                title: c,
                content: "対象のストーリーをすべてクリア状態にしました。",
                closeBtnText: "关闭"
              }, null, null, function()
              {
                d.nativeReload("#/MyPage");
                window.isDebug && window.isBrowser && (location.href = "#/MyPage", location.reload())
              })
            })
          }
        })
      }
    },
    chapter2ndClearTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || new b.PopupClass(
      {
        title: "2部11章一括クリア",
        content: "第二部の11章まで一括クリアします。",
        closeBtnText: "取消",
        decideBtnText: "実行する",
        decideBtnEvent: function()
        {
          e.ajaxPost(b.linkList.backdoor2ndChapterClear, null, function(a)
          {
            new b.PopupClass(
            {
              title: "2部11章一括クリア",
              content: "対象のストーリーをすべてクリア状態にしました。",
              closeBtnText: "关闭"
            }, null, null, function()
            {
              d.nativeReload("#/MyPage");
              window.isDebug && window.isBrowser && (location.href = "#/MyPage", location.reload())
            })
          })
        }
      })
    },
    tutorialFunc: function(a)
    {
      a.preventDefault();
      b.isScrolled() || "TU999" == b.storage.user.get("tutorialId") || "TU997" == b.storage.user.get("tutorialId") || (b.tapBlock(!0), require(["js/util/TutorialUtil.js"], function(a)
      {
        b.tutorialUtil = a;
        b.tutorialId = b.tutorialUtil.getResumeId();
        a.tutorialResume();
        console.log("tutorialId:", b.storage.user.get("tutorialId"))
      }))
    },
    tutorialResetFunc: function(a)
    {
      a.preventDefault();
      b.isScrolled() || new b.PopupClass(
      {
        title: "チュートリアル設定",
        content: f.template($("#tutorialPop").text())(),
        popupType: "typeE",
        exClass: "transferPop",
        closeBtnText: "取消",
        decideBtnText: "OK",
        decideBtnEvent: function()
        {
          var a = b.doc.getElementById("tutorialSelect").value;
          e.ajaxPost(b.linkList.prologueRegister,
          {
            tutorialId: a
          }, function(c)
          {
            new b.PopupClass(
            {
              title: "tutorial reset",
              content: a + "を登録しました。",
              closeBtnText: "关闭"
            });
            console.log("tutorialIdRegistComp", c);
            b.responseSetStorage(c)
          })
        }
      })
    },
    tutorialCompFunc: function(a)
    {
      a.preventDefault();
      b.isScrolled() || e.ajaxPost(b.linkList.prologueRegister,
      {
        tutorialId: "TU999"
      }, function(a)
      {
        new b.PopupClass(
        {
          title: "tutorial comp",
          content: "TU999を登録しました。",
          closeBtnText: "关闭"
        });
        console.log("tutorialIdRegistComp", a);
        b.responseSetStorage(a)
      })
    },
    reloadFunc: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (b.pageObj.removeCommand(), 160 > (window.app_ver.split(".").join("") | 0) || window.isBrowser ? (d.setWebView(!1), location.href = a.currentTarget.getAttribute("data-href"), location.reload()) : d.nativeReload(a.currentTarget.getAttribute("data-href")))
    },
    nativeReloadTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || d.nativeReload("#/MyPage")
    },
    errorTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (a = f.template($("#errorTestPop").text()), new b.PopupClass(
      {
        title: "更改小组名",
        content: a(),
        closeBtnText: "关闭",
        decideBtnText: "确定",
        decideBtnEvent: function(a)
        {
          a = b.doc.getElementById("errorCode").value;
          e.ajaxPost(b.linkList.backdoorError + "/" + a, "", function(b) {})
        }
      }, null, function()
      {
        b.nativeKeyBoard("errorCode", 3)
      }))
    },
    rondomeErrorTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || e.ajaxPost(b.linkList.randomError, "", function(b)
      {
        console.log("server ramdom error test", b)
      })
    },
    tweetTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (a = f.template($("#groupNameChangePop").text()), new b.PopupClass(
      {
        title: "更改小组名",
        content: a(),
        closeBtnText: "关闭",
        decideBtnText: "ツイート",
        decideBtnEvent: function(a)
        {
          a = b.doc.getElementById("changeName").value.split("?");
          a = a[0].split("/");
          6 > a.length ? new b.PopupClass(
          {
            title: "错误",
            content: "URLが不正です",
            closeBtnText: "关闭"
          }) : (a = " ★おためしついーと★%0a https://twitter.com/" + a[3] + "/status/" + a[5] + "/photo/1%0a★おためしついーと★", a = encodeURI(a).replace(/%250a/g, "%0a"), d.browserOpen("https://twitter.com/share?text=" + a + "%0a&count=none&lang=ja"))
        }
      }, null, function()
      {
        b.nativeKeyBoard("changeName", 200)
      }))
    },
    fullVoiceTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || ($(b.ready.target).on("webkitAnimationEnd", function()
      {
        d.changeBg("web_black.jpg");
        $(b.ready.target).off();
        $(b.ready.target).on("webkitAnimationEnd", function(a)
        {
          "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
        });
        $("#commandDiv").on("nativeCallback", function()
        {
          $("#commandDiv").off();
          b.removeClass(b.ready.target, "preNativeFadeIn");
          d.setWebView(!0);
          d.startBgm(b.settingBgm);
          d.changeBg(b.settingBg)
        });
        setTimeout(function()
        {
          d.setWebView(!1);
          d.downloadFileFullVoice("section_event_1033")
        }, 500)
      }), b.addClass(b.ready.target, "preNativeFadeIn"))
    },
    chatTest: function()
    {
      d.startChat()
    },
    errorIdTestBtn: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        $(document).ajaxSend(function(b, a, c)
        {
          a.setRequestHeader("USER-ID-FBA9X88MAE", null)
        });
        var c = function()
        {
          $(document).ajaxSend(function(b, a, c)
          {
            a.setRequestHeader("USER-ID-FBA9X88MAE", window.g_sns)
          })
        };
        $.ajax(
        {
          url: b.linkList.backdoorError,
          type: "POST",
          contentType: "application/JSON",
          dataType: "JSON"
        }).done(function(a)
        {
          "error" !== a.resultCode && c && c(a);
          b.loading.hide()
        })
      }
    },
    prologueTest: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
      {
        var c = a.currentTarget.dataset.opid;
        d.endL2d();
        $(b.ready.target).on("webkitAnimationEnd", function()
        {
          $(b.ready.target).off();
          $(b.ready.target).on("webkitAnimationEnd", function(a)
          {
            "readyFadeOut" == a.originalEvent.animationName && (b.ready.target.className = "")
          });
          $("#commandDiv").on("nativeCallback", function(a, b)
          {
            console.log("nativeCallback", b);
            b && "prologue" === b && ($("#commandDiv").off(), d.setWebView())
          });
          setTimeout(function()
          {
            d.startPrologue(c);
            d.setWebView(!1);
            b.removeClass(b.ready.target, "preNativeFadeIn")
          }, 500)
        });
        b.addClass(b.ready.target, "preNativeFadeIn")
      }
    },
    localStorageGet: function(a)
    {
      a.preventDefault();
      b.isScrolled() || console.log("localStorage:", localStorage.getItem("LocalStorageTest"))
    },
    localStorageSave: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (localStorage.setItem("LocalStorageTest", "test"), console.log("localStorage:", localStorage.getItem("LocalStorageTest")))
    },
    localStorageClear: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (localStorage.clear(), b.sfml = {}, console.log("localStorage:", localStorage.getItem("LocalStorageTest")), new b.PopupClass(
      {
        title: "localStorage clear",
        content: "localStorageのデータを削除しました。",
        closeBtnText: "关闭"
      }))
    },
    titlePopup: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (a = f.template($("#titlePopupTemp").text()), new b.PopupClass(
      {
        title: "更换称号",
        content: a(),
        popupType: "typeB",
        closeBtnText: "OK"
      }))
    },
    eventAccomplishDebugModeNormal: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (b.accomplishDebug = "normal", new b.PopupClass(
      {
        title: "踏破イベントデバッグモード",
        content: "ストーリークエストデバッグモードをオンにしました。<br>オフにするにはアプリを再起動してください。",
        closeBtnText: "关闭"
      }))
    },
    eventAccomplishDebugModeChallenge: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (b.accomplishDebug = "challenge", new b.PopupClass(
      {
        title: "踏破イベントデバッグモード",
        content: "チャレンジクエストデバッグモードをオンにしました。<br>オフにするにはアプリを再起動してください。",
        closeBtnText: "关闭"
      }))
    },
    eventDungeonMapTest: function(a)
    {
      a.preventDefault();
      if (!b.isScrolled())
        if (f.findWhere(e.getPageJson().eventList,
          {
            eventType: "DUNGEON"
          }))
        {
          var c = function(a)
          {
            a = window.isLocal ? JSON.parse(a) : a;
            a.interrupt ? (b.interrupt = null, location.href = a.interrupt.page) : (a = {
              areaId: a.userEventDungeonAreaList[a.userEventDungeonAreaList.length - 1].areaId,
              deckType: 41
            }, console.log("dungeon start Api:", a), e.ajaxPost(b.linkList.dungeonStart, a, function(a)
            {
              console.log("-------- dungeonStart --------");
              console.log("dungeonStartResponse:", a);
              b.responseSetStorage(a);
              location.href = "#/EventDungeonMap"
            }))
          };
          if (window.isLocal) require(["text!/magica/json/page/EventDungeonTop.json"], function(a)
          {
            c(a)
          });
          else
          {
            var d = [],
              g = [],
              h = [],
              k, p = {
                0: 1,
                1: 3,
                2: 5,
                3: 7,
                4: 9,
                5: 10,
                6: 11
              },
              l = b.storage.userPieceList.toJSON();
            b.storage.userCardListEx.each(function(a, b)
            {
              if (7 > b)
              {
                a.toJSON();
                d.push(a.id);
                g.push(p[b]);
                var c = [];
                l[b] && c.push(l[b].id);
                h.push(c);
                0 === b && (k = a.id)
              }
            });
            a = {
              deckType: 41,
              formationSheetId: 111,
              name: "ダンジョン1",
              episodeUserCardId: k
            };
            a.userCardIds = d;
            a.questPositionIds = g;
            a.userPieceIdLists = h;
            console.log("dungeon deck savePrm:", a);
            e.ajaxPost(b.linkList.userDeckSave, a, function(a)
            {
              b.responseSetStorage(a);
              e.ajaxSimpleGet("/magica/api/page/EventDungeonTop", "", c)
            })
          }
        }
      else new b.PopupClass(
      {
        title: "错误",
        content: "ダンジョンイベントの開催期間外です。",
        closeBtnText: "关闭"
      })
    },
    startMirrorBattle: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (d.setWebView(!1), d.startMirrorBattle(
      {
        resultUrl: "/magica/index.html#/MainQuest",
        retireUrl: "/magica/index.html#/TopPage"
      }))
    },
    commonStoryTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || b.playStory(
      {
        cmd: d,
        ajaxControl: e,
        storyId: "101203-8",
        fullVoiceSectionId: 101203,
        isForcePlay: !0,
        callback: function()
        {
          new b.PopupClass(
          {
            title: "ストーリー再生終了",
            content: "ストーリーが終わりました。",
            closeBtnText: "关闭"
          })
        }
      })
    },
    mirrorBattleRetry: function(a)
    {
      a.preventDefault();
      b.isScrolled() || e.ajaxPost(b.linkList.backdoorMirrorBattleRetry, null, function(a)
      {
        new b.PopupClass(
        {
          title: "理違いバトル再挑戦",
          content: "理違いバトルに再挑戦できるようになりました。",
          closeBtnText: "关闭"
        })
      })
    },
    getPurchaseStatus: function(a)
    {
      a.preventDefault();
      b.isScrolled() || ($("#commandDiv").on("nativeCallback", function(a, d)
      {
        $("#commandDiv").off();
        var c = "ロック状態のはありません";
        a = d.product_ids;
        0 < a.length && (c = "ロック状態のproduct_idリスト<br>", f.each(a, function(a, b, d)
        {
          c += "・" + String(a);
          c += "<br>"
        }));
        new b.PopupClass(
        {
          title: "マギアストーン購入状況確認",
          content: c,
          popupType: "typeB",
          closeBtnText: "关闭"
        })
      }), d.getPurchaseStatus(), a = {
        product_ids: ["aaaa", "bbbb", "cccc"]
      }, window.isBrowser && nativeCallback(a))
    },
    mailSendTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (location.href = "#/MailSendTest")
    },
    ToEventWitchExchangeTest: function(a)
    {
      a.preventDefault();
      b.isScrolled() || (b.EventWitchMemoriaExchangeAnimePrm = {
        charaId: 1001,
        rewardPieceId: 2016,
        storyId: "501301-0"
      }, location.href = "#/EventWitchExchangeAnimePage")
    }
  })
});
