$ && ($.fn.num = function()
{
  return parseInt(this.text())
}, $.fn.exist = function()
{
  return 0 < $(this).length
});
if (void 0 == window.orientation && -1 == location.href.search("ExtendedNotSupportAccessErrorPage"))
{
  var not_support_error_link = document.getElementById("not_support_error_link");
  not_support_error_link && not_support_error_link.innerText && (location.href = not_support_error_link.innerText)
}

function getAndroidOSVersion()
{
  if (!ua.android) return 0;
  for (var a = navigator.userAgent.split("Android ")[1].split(";")[0].split("."), b = "", c = 0; 3 > c; c++) b += c < a.length ? a[c] : "0";
  return parseInt(b)
}
var uaMatch = function()
  {
    for (var a = navigator.userAgent.toLowerCase(), b = 0; b < arguments.length; b++)
      if (a.match(arguments[b])) return !0;
    return !1
  },
  ua = {
    ios: uaMatch("ipad", "iphone", "ipod"),
    ios6: uaMatch("iphone os 6_"),
    ios7: uaMatch("iphone os 7_"),
    ipad: uaMatch("ipad"),
    ipod: uaMatch("ipod"),
    android: uaMatch("android"),
    isAndroidOs5: uaMatch("android 5"),
    isAndroidOs4_4: uaMatch("android 4.4"),
    isAndroidOs4_2: uaMatch("android 4.2"),
    isAndroidOs4_1: uaMatch("android 4.1"),
    isGalaxyNote: uaMatch("sc-02e", "sc-01g", "sc-05d", "scl22", "scl24", "sc-01f"),
    isGalaxysTab: uaMatch("sc-01e"),
    isGalaxys2: uaMatch("isw11sc", "sc-02c", "sc-03d"),
    isGalaxys3: uaMatch("sc-03e", "sc-06d", "scl21"),
    isGalaxyNote2: uaMatch("sc-02e"),
    isGalaxys3a: uaMatch("sc-03e"),
    isGalaxyJ: uaMatch("sc-02f"),
    isXperia: uaMatch("is11s", "is12s", "so-01b", "so-01c", "so-01e", "so-02e", "so-03d", "sol21", "sol22"),
    isXperiaAX: uaMatch("so-01e"),
    isArrows: uaMatch("f-05d", "f-10d", "fjl"),
    isEluga: uaMatch("p-02e"),
    isINFOBAR_A02: uaMatch("htx21"),
    isNexus6: uaMatch("nexus 6"),
    isNexus: uaMatch("nexus 6", "nexus 5"),
    isNexus5x: uaMatch("nexus 5x"),
    isSO_04E: uaMatch("so-04e"),
    isLowAnimeRate: uaMatch("201f", "201m", "202f", "203sh", "206sh", "301f", "302hw", "302sh", "303sh", "403sc", "404kc", "asus_t00p", "dm015k", "f-01f", "f-02e", "f-02f", "f-04e", "f-05e", "f-06e", "fjl22", "htl21", "htl22", "htl23", "l-01e", "l-04e", "l-05d", "l-05e", "lgl24", "lgv31", "n-02e", "n-03e", "n-04e", "n-06e", "nexus 10", "nexus 7", "p-02e", "p-03e", "sc-01f", "sc-01g", "sc-02e", "sc-02f", "sc-03e", "sc-04e", "sc-06d", "scl22", "scl24", "sh-02e", "sh-02f", "sh-04f", "sh-05f", "sh-06e", "sh-08e", "shl21", "shl22", "shl23", "so-01e", "so-04d", "sol21", "wx10k")
  };
ua.ios && (ua.iosVersion = parseInt(navigator.userAgent.toLowerCase().split("os ")[1].substr(0, 1)), uaMatch("iphone") && 480 == screen.availWidth && 320 == screen.availHeight ? ua.iphone4 = !0 : 3 == window.devicePixelRatio && (ua.iphone6plus = !0));
var uaMatch = null,
  SCREEN_WIDTH = 1280,
  SCREEN_HEIGHT = 720,
  g_move_span = 0,
  g_move_span_limit = 30,
  g_window_posY = 0,
  g_popup_name = "",
  commonLocal = commonLocal,
  g_iscroll_instance, g_iscroll_bottom_event_flag = !1,
  g_scrollajax_fin = !1,
  g_scrollajax_up_fin = !1,
  g_scrollajax_down_fin = !1,
  g_scrollajax_loadimg_up, g_scrollajax_loadimg_down, g_scrollajax_end_type, g_body, g_historyBackFlag = !1,
  g_showStatusPanel = !1,
  g_production_flag = commonLocal || -1 != location.hostname.indexOf("dev") && -1 != location.hostname.indexOf("127.0.0.1") ? !1 : !0,
  g_wkFlag = window.webkit ? !0 : !1,
  DeviceMotionData = function()
  {
    this.z = this.y = this.x = 0
  };
DeviceMotionData.prototype.copy = function(a)
{
  a.x = this.x;
  a.y = this.y;
  a.z = this.z
};
var DeviceMotionDatas = function()
  {
    this.timeStamp = 0;
    this.gyro = new DeviceMotionData;
    this.accl = new DeviceMotionData;
    this.magne = new DeviceMotionData;
    this.att = new DeviceMotionData
  },
  MediaPlayer = function()
  {
    this.bgmPause = !1;
    this.seSetting = this.bgmSetting = !0;
    this.voiceVolumeSetting = this.seVolumeSetting = this.bgmVolumeSetting = 1;
    this.device = new DeviceMotionDatas;
    this.deviceMotionCallBack = !1;
    this.submitBtnId = this.callback = null
  },
  commandDiv;
MediaPlayer.prototype.sendCommand = function(a)
{
  if (commonLocal) commonLocal.audio(a);
  else if (a = "game:" + a, ua.android) alert(a);
  else if (g_wkFlag) webkit.messageHandlers.gameCommand.postMessage(a);
  else
  {
    commandDiv || (commandDiv = document.getElementById("commandDiv"));
    var b = document.createElement("object");
    b.setAttribute("data", a);
    commandDiv.appendChild(b)
  }
};
var Command = {
  DATA_GET_REQUEST_HEADER: 1,
  DATA_CLEAR_WEB_CACHE: 10,
  SOUND_BGM_PLAY: 100,
  SOUND_BGM_STOP: 101,
  SOUND_BGM_RESUME: 102,
  SOUND_BGM_PAUSE: 103,
  SOUND_BGM_SET_VOL: 104,
  SOUND_BGM_GET_VOL: 105,
  SOUND_SE_PLAY: 110,
  SOUND_SE_STOP: 111,
  SOUND_SE_SET_VOL: 114,
  SOUND_SE_GET_VOL: 115,
  SOUND_VO_PLAY: 120,
  SOUND_VO_STOP: 121,
  SOUND_VO_SET_VOL: 124,
  SOUND_VO_GET_VOL: 125,
  FILE_CLEAR_DLC: 200,
  SCENE_CHANGE_QUEST: 300,
  SCENE_CHANGE_STORY: 320,
  DISPLAY_SHOW_MOVIE: 400,
  DISPLAY_HIDE_MOVIE: 401,
  DISPLAY_SHOW_BG: 410,
  DISPLAY_HIDE_BG: 411,
  DISPLAY_SHOW_L2D: 420,
  DISPLAY_HIDE_L2D: 421,
  ANIMATION_COMPOSE_START: 500,
  ANIMATION_COMPOSE_END: 501,
  ANIMATION_GACHA_START: 510,
  ANIMATION_GACHA_END: 511,
  APP_END: 600
};
MediaPlayer.prototype.playBGM = function(a)
{
  this.bgmPause = !1;
  this.sendCommand(Command.SOUND_BGM_PLAY + "," + a)
};
MediaPlayer.prototype.stopBGM = function()
{
  this.sendCommand(Command.SOUND_BGM_STOP)
};
MediaPlayer.prototype.pauseBGM = function()
{
  0 == this.bgmPause ? (this.sendCommand(Command.SOUND_BGM_PAUSE), this.bgmPause = !0) : (this.sendCommand(Command.SOUND_BGM_RESUME), this.bgmPause = !1)
};
MediaPlayer.prototype.BGMVolumeSet = function(a)
{
  this.sendCommand(Command.SOUND_BGM_SET_VOL + "," + a)
};
MediaPlayer.prototype.playSE = function(a)
{
  this.sendCommand(Command.SOUND_SE_PLAY + "," + a)
};
MediaPlayer.prototype.stopSE = function()
{
  this.sendCommand(Command.SOUND_SE_STOP)
};
MediaPlayer.prototype.SEVolumeSet = function(a)
{
  this.sendCommand(Command.SOUND_SE_SET_VOL + "," + a)
};
MediaPlayer.prototype.playVOICE = function(a)
{
  this.sendCommand(Command.SOUND_VO_PLAY + "," + a)
};
MediaPlayer.prototype.stopVOICE = function()
{
  this.sendCommand(Command.SOUND_VO_STOP)
};
MediaPlayer.prototype.VoiceVolumeSet = function(a)
{
  this.sendCommand(Command.SOUND_VO_SET_VOL + "," + a)
};
MediaPlayer.prototype.settingCheck = function()
{
  this.sendCommand("SOUND_BGM_GET_VOL");
  this.sendCommand("SOUND_SE_GET_VOL");
  this.sendCommand("SOUND_VO_GET_VOL")
};
MediaPlayer.prototype.clearCache = function()
{
  this.sendCommand(Command.FILE_CLEAR_DLC)
};
MediaPlayer.prototype.playMOVIE = function(a, b)
{
  this.sendCommand(Command.SHOW_MOVIE + "," + a)
};
MediaPlayer.prototype.webviewClearCache = function(a)
{
  this.sendCommand(Command.DATA_CLEAR_WEB_CACHE)
};
MediaPlayer.prototype.appEnd = function()
{
  this.sendCommand(Command.APP_END)
};
MediaPlayer.prototype.getRequestHeader = function(a, b)
{
  a()
};
MediaPlayer.prototype.setRequestHeader = function(a, b)
{
  g_sns = a;
  g_token = b;
  this.callback && (this.callback(), this.submitBtnId = this.callback = null)
};
MediaPlayer.prototype.gotoQuest = function(a)
{
  this.sendCommand(Command.SCENE_CHANGE_QUEST + "," + a)
};
MediaPlayer.prototype.gotoCompose = function(a)
{
  this.sendCommand(Command.SCENE_CHANGE_COMPOSE + "," + a)
};
MediaPlayer.prototype.gotoGacha = function(a)
{
  this.sendCommand(Command.SCENE_CHANGE_GACHA + "," + a)
};
var gMediaPlayer = new MediaPlayer;

function mediaBGMVolumeSetting(a)
{
  gMediaPlayer.bgmVolumeSetting = a
}

function mediaSEVolumeSetting(a)
{
  gMediaPlayer.seVolumeSetting = a
}

function mediaVoiceVolumeSetting(a)
{
  gMediaPlayer.voiceVolumeSetting = a
}

function mediaPlayBgm()
{
  var a = document.getElementById("main_bgm");
  null != a && 0 < a.innerText.length && gMediaPlayer.playBGM(a.innerText)
}
var g_sns, g_token;

function mediaHeaderFooter_set()
{
  var a = document.getElementById("isNativeHeaderEnabled");
  a ? gMediaPlayer.headerfooterOn(a.innerText) : gMediaPlayer.headerfooterOff()
}

function mediaHeaderFooter_show()
{
  var a = document.getElementById("isNativeHeaderEnabled");
  a && gMediaPlayer.headerfooterOn(a.innerText)
}

function mediaHeaderFooter_hide()
{
  document.getElementById("isNativeHeaderEnabled") && gMediaPlayer.headerfooterOff()
}

function mediaFooterTouch(a)
{
  document.getElementById("isNativeHeaderEnabled") && gMediaPlayer.footerTouch(a)
}

function ajaxTimeoutError(a)
{
  var b = document.getElementById("commonAjaxLoading"),
    c = document.getElementById("commonJsErrorPopup"),
    d = document.getElementById("touchBlock");
  b && (b.style.display = "none");
  c && (document.getElementById("commonJsErrorLinkBtn").addEventListener(cgti, function()
  {
    a ? location.href = a : location.reload()
  }), document.getElementById("commonJsErrorCautionText").innerHTML = "发生通信错误。<span style='display:block;margin-top:20px;font-size:20px'>※内部处理可能已被执行。</span>", document.getElementById("commonJsErrorLinkBtn").innerText = "重新加载", popupStart("commonJsErrorPopup"));
  d && (d.style.display = "none")
}
var curtainMoveEvent = function(a)
  {
    a.preventDefault();
    a.stopPropagation();
    return !1
  },
  popupStart = function(a, b)
  {
    function c(c)
    {
      g_move_span < g_move_span_limit && (c.preventDefault(), -1 == d.className.indexOf("close") && (gMediaPlayer.playSE("se_cancel"), popupClose(a, b)))
    }
    if (g_popup_name != a)
    {
      g_popup_name && popupClose(g_popup_name);
      document.getElementById("backboneContent") && "commonJsErrorPopup" != a && (document.getElementById("globalNaviFix").style.zIndex = "990");
      g_popup_name = a;
      var d = document.getElementById(a),
        e = d.getElementsByClassName("popupInner")[0],
        k = Array.prototype.slice.call(d.getElementsByClassName("popupCloseBtn")),
        g = parseInt(d.getAttribute("data-width")),
        f = d.getAttribute("data-height"),
        h = d.getAttribute("data-top"),
        m = d.getAttribute("data-right"),
        n = d.getAttribute("data-anim-type"),
        n = 2 == n && ua.isAndroidOs4_4 ? 3 : n,
        p = d.style,
        e = e.style,
        q = d.getElementsByClassName("popupCurtain")[0],
        l;
      d.getElementsByClassName("popupScrollWrap") && (l = d.getElementsByClassName("popupScrollWrap"));
      0 == l.length ? document.addEventListener("touchmove", curtainMoveEvent) : ua.android && 430 > getAndroidOSVersion() && (p.position = "fixed");
      g && (e.left = (1280 - g) / 2 + "px", e.width = g + "px");
      f && (e.top = (720 - f) / 2 + "px", e.height = f + "px");
      h && (e.top = h + "px");
      m && (e.left = "auto", e.right = m + "px");
      q.hasEvent || q.addEventListener(cgti, c, !1);
      q.hasEvent = !0;
      d.className = "popupContent open" + (n ? " anim" + n : "");
      p.display = "block";
      gMediaPlayer.playSE("se_kettei02");
      g = k.length;
      for (f = 0; f < g; f++) h = k[f], h.hasEvent || h.addEventListener(cgti, c), h.hasEvent = !0;
      ua.ios && (window.scrollBy(0, 1), setTimeout(function()
      {
        window.scrollBy(0, -1)
      }, 100));
      l = q = e = p = n = m = h = f = g = k = e = null
    }
  },
  popupClose = function(a, b)
  {
    function c(c)
    {
      -1 != d.className.indexOf("close") && (d.style.display = "none", $(d).removeClass("close"), void 0 != b && null != b && "function" == typeof b && b(), c = document.createEvent("HTMLEvents"), c.initEvent(a + "关闭", !0, !1), d.dispatchEvent(c), g_popup_name = a == g_popup_name ? "" : g_popup_name)
    }
    document.getElementById("backboneContent") && (document.getElementById("globalNaviFix").style.zIndex = "1001");
    var d = document.getElementById(a),
      e = d.querySelectorAll(".popupInner")[0],
      k = d.getAttribute("data-anim-type");
    document.removeEventListener("touchmove", curtainMoveEvent);
    ua.ios && (window.scrollBy(0, -1), setTimeout(function()
    {
      window.scrollBy(0, 1)
    }, 100));
    e.hasCloseEvent || e.addEventListener("webkitAnimationEnd", c);
    e.hasCloseEvent = !0;
    d.className = "popupContent close" + (k ? " anim" + k : "");
    k = null
  },
  popupCloseAll_historyBack = function()
  {
    var a = document,
      b = a.getElementById("globalMenuBackBtn");
    if (!(a.getElementById("Tutorial020SectionPage") || a.getElementById("Tutorial110SectionPage") || a.getElementById("Tutorial080ComposeTopPage") || a.getElementById("Tutorial120QuestAssistSelectPage") || a.getElementById("ClanNavi")))
    {
      var c = a.getElementById("popup_common_menu");
      if (g_popup_name) popupClose(g_popup_name), g_popup_name = "", gMediaPlayer.playSE("se_cancel");
      else if (c)
        if ("show" == c.className) c.className = "";
        else if (a.getElementById("CardBasePage") || a.getElementById("EventBCBasePage"))
      {
        if (-1 == location.href.indexOf("UnitTop") || -1 == location.href.indexOf("EventBCTop")) c = a.createEvent("HTMLEvents"), c.initEvent("androidBackBtn", !0, !1), b.dispatchEvent(c)
      }
      else b && (location.href = b.href);
      a.getElementById("MyPage") && popupStart("popupAppEndConf")
    }
  };
(function(a)
{
  a.fn.scrollAjax = function(b)
  {
    b = a.extend(
    {
      proximity: 0,
      upAjax: !1
    }, b);
    return this.each(function()
    {
      var c = this;
      a(c).bind("scroll", function()
      {
        var d;
        d = c == window ? a(document).height() : a(c)[0].scrollHeight;
        scrollPosition = a(c).height() + a(c).scrollTop();
        if ((d - scrollPosition) / d <= b.proximity)
        {
          if (g_scrollajax_end_type && "" != g_scrollajax_end_type.value) return !1;
          a(c).trigger("scrollLimit", "down")
        }
        if (a(c).height() == scrollPosition && 1 == b.upAjax)
        {
          if (g_scrollajax_end_type && "" != g_scrollajax_end_type.value) return !1;
          a(c).trigger("scrollLimit", "up")
        }
      });
      return !1
    })
  };
  a.fn.scrollAjaxOff = function(b)
  {
    return this.each(function()
    {
      a(this).off("scroll");
      return !1
    })
  }
})(jQuery);
var scrollAjax = function(a, b, c)
  {
    c = c ? c : !1;
    var d = $(b);
    g_scrollajax_end_type = document.getElementById("scroll-end-type");
    g_scrollajax_loadimg_up = document.getElementById("scrollAjaxLoadingUp");
    g_scrollajax_loadimg_down = document.getElementById("scrollAjaxLoadingDown");
    a = "window" != a ? $(a) : $(window);
    null != a && 0 != a.length && null != d && 0 != d.length && (a.scrollAjax(
    {
      proximity: .002,
      upAjax: c
    }), a.bind("scrollLimit", function(a, b)
    {
      if (!g_scrollajax_fin)
      {
        if (g_scrollajax_end_type)
        {
          if ("down" == b && g_scrollajax_down_fin || "up" == b && g_scrollajax_up_fin) return;
          g_scrollajax_end_type.value = b
        }
        d.trigger("click");
        g_scrollajax_loadimg_down && "down" == b && (g_scrollajax_loadimg_down.style.display = "block");
        g_scrollajax_loadimg_up && "up" == b && (g_scrollajax_loadimg_up.style.display = "block")
      }
    }))
  },
  iscrollStart = function()
  {
    document.getElementById("scene_wrap").style.height = "720px";
    setTimeout(function()
    {
      g_iscroll_instance = new IScroll("#scene_wrap",
      {
        bounce: !1,
        hScroll: !1
      })
    }, 100)
  },
  scrollAjaxLoadComp = function()
  {
    scrollAjaxCompFunc()
  },
  scrollAjaxLoadFin = function()
  {
    g_scrollajax_end_type ? ("down" == g_scrollajax_end_type.value ? g_scrollajax_down_fin = !0 : g_scrollajax_up_fin = !0, g_scrollajax_down_fin && g_scrollajax_up_fin && (g_scrollajax_fin = !0)) : g_scrollajax_fin = !0;
    scrollAjaxCompFunc()
  },
  scrollAjaxCompFunc = function()
  {
    g_iscroll_instance && (g_iscroll_instance.refresh(), g_iscroll_bottom_event_flag = !1);
    g_scrollajax_end_type && (g_scrollajax_end_type.value = "");
    g_scrollajax_loadimg_down && (g_scrollajax_loadimg_down.style.display = "none");
    g_scrollajax_loadimg_up && (g_scrollajax_loadimg_up.style.display = "none")
  },
  ajaxCompFuncHref = function(a)
  {
    location.href = a
  },
  ajaxCompFuncReplace = function(a)
  {
    location.replace(a)
  },
  questStartFunc = function(a)
  {
    gMediaPlayer.gotoQuest(a)
  },
  gvgStartFunc = function(a)
  {
    gMediaPlayer.gotoGvG(a)
  };

function menuGvgTimeSet()
{
  document.getElementById("popup_common_menu");
  if (-1 == document.getElementById("naviCombat").className.indexOf("lock"))
  {
    var a, b = document.getElementById("popupGuildTimer"),
      c = document.getElementById("popupGuildTimerView"),
      d = ((new Date).getTime() / 1E3 | 0) + parseInt(b.innerText),
      e = document.getElementById("locBattleBtn");
    "-1" == b.innerText ? c.innerText = "停战中" : a = setInterval(function()
    {
      var b = (new Date).getTime() / 1E3 | 0,
        b = d - b,
        g = b | 0,
        f = g / 60 | 0,
        h = f / 60 | 0,
        f = f % 60,
        g = String(g % 60 + 100).substr(1, 2),
        f = String(f + 100).substr(1, 2),
        h = String(h + 100).substr(1, 2);
      0 >= b ? (c.innerText = "00:00:00", e && (e.innerText = "00:00:00"), $("#naviCombat").removeClass("battle"), document.getElementById("naviCombat").href = document.getElementById("popupCombatLink").innerText, b = document.createEvent("HTMLEvents"), b.initEvent("battleEnd", !0, !1), c.dispatchEvent(b), clearInterval(a)) : (c.innerText = h + ":" + f + ":" + g, e && (e.innerText = h + ":" + f + ":" + g))
    }, 1E3)
  }
}
var StatusFunc = function()
{
  var a = document,
    b, c, d, e, k, g, f, h, m, n, p, q = !1,
    l = function()
    {
      var c = (new Date).getTime() / 1E3 | 0,
        c = d - c,
        g = 1 + c / 60 | 0,
        l = g / 60 | 0,
        r = 1 + c / 300 | 0;
      0 >= c ? (k.style.display = "none", m.innerText = f, h.width = "100%", r = a.createEvent("HTMLEvents"), r.initEvent("APMax", !0, !1), b.dispatchEvent(r), clearInterval(n)) : (p = f - r, m.innerText = p, h.width = p / f * 100 + "%", q && (r = a.createEvent("HTMLEvents"), r.initEvent("APCountDown", !0, !1), b.dispatchEvent(r), q = !1), 0 == c % 300 && (q = !0), g = String(g % 60 + 100).substr(1, 2), l = String(l + 100).substr(1, 2), e.innerText = l + ":" + g)
    };
  return {
    statusApTimeStart: function()
    {
      if (b = a.getElementById("menuStatusApMaxTime")) c = (new Date).getTime() / 1E3 | 0, d = c + parseInt(b.innerText), e = a.getElementById("statusMenuApTime"), k = a.getElementById("statusMenuApTimeWrap"), h = a.getElementById("menuApGauge").style, m = a.getElementById("menuStatusApCurrent"), g = parseInt(m.innerText), f = parseInt(a.getElementById("menuStatusApMax").innerText), g && g > f ? (k.style.display = "none", h.width = "100%", m.className = "c_gold") : (b && l(), n = setInterval(function()
      {
        l()
      }, 1E3))
    },
    resetTime: function(c, e)
    {
      t = (new Date).getTime() / 1E3 | 0;
      d = t + parseInt(e);
      c > f ? (clearInterval(n), p = c, m.innerText = c, k.style.display = "none", h.width = "100%", c = a.createEvent("HTMLEvents"), c.initEvent("APMax", !0, !1), b.dispatchEvent(c)) : (0 == e && (p = f), l())
    },
    getCurrentAp: function()
    {
      return p
    }
  }
}();

function localAjax(a)
{
  var b = document.getElementById("scriptDummy");
  $.ajax(
  {
    url: a,
    dataType: "html",
    cache: !1
  }).done(function(a)
  {
    b.innerHTML = a;
    if (a = b.getElementsByClassName("ajaxScript"))
      for (var c = 0; c < a.length; c++) eval(a[c].innerHTML)
  })
}

function isScrolled()
{
  return g_move_span < g_move_span_limit ? !1 : !0
}
var cgti = function()
{
  return !ua.ios && !ua.android || ua.isGalaxys2 || ua.isGalaxys3 ? "click" : "touchend"
}();

function spf()
{
  for (var a = arguments[0], b = 1; b < arguments.length; b++) a = a.replace(/%d|%f|%s/, arguments[b]);
  return a
}

function cpf()
{
  if (commonLocal)
    for (var a = arguments[0], b = 1; b < arguments.length; b++) a = a.replace(/%d|%f|%s/, arguments[b])
}

function cpt()
{
  var a = arguments;
  switch (a.length)
  {
    case 2:
      (function()
      {
        var b = $(a[1]).exist() ? $(a[1]).text() : a[1];
        $(a[0]).text(b)
      })();
      break;
    case 3:
      (function()
      {
        var b = $(a[2]).exist() ? $(a[2]).text() : a[2];
        switch (a[1])
        {
          case "html":
            $(a[0]).html(b);
            break;
          case "class":
            $(a[0]).attr("class", b);
            break;
          default:
            $(a[0]).attr(a[1], b)
        }
      })()
  }
  return $(a[0])
}

function sendMessageToApp(a)
{
  if (!commonLocal)
    if (a = "game:" + a, ua.android) alert(a);
    else if (ua.ios)
  {
    var b = document.createElement("object");
    b.setAttribute("hight", "0px");
    b.setAttribute("width", "0px");
    b.setAttribute("data", a);
    document.documentElement.appendChild(b);
    b.parentNode.removeChild(b)
  }
}

function hideLoadingWait()
{
  sendMessageToApp("LOAD_HIDE")
};
