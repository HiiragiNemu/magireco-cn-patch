define("underscore backbone backboneCommon ajaxControl command text!template/test/MailSendTest.html text!css/test/MailSendTest.css".split(" "), function(e, f, b, c, l, g, h)
{
  var d, k = f.View.extend(
  {
    events: function()
    {
      var a = {};
      a[b.cgti + " .sendMailBtn"] = this.sendMailBtn;
      a[b.cgti + " .sendAuthNumBtn"] = this.sendAuthNumBtn;
      return a
    },
    initialize: function(a)
    {
      this.template = e.template(g);
      this.createDom()
    },
    render: function()
    {
      this.$el.html(this.template(c.getPageJson()));
      return this
    },
    createDom: function()
    {
      b.setGlobalView();
      b.content.append(this.render().el);
      b.ready.hide()
    },
    sendMailBtn: function(a)
    {
      a.preventDefault();
      b.isScrolled() || ((a = $("#inputMail").val()) ? (console.log("address", a), c.ajaxPost(b.linkList.sendRepaymentMail,
      {
        mailAddress: a
      }, function(a)
      {
        console.log("res", a);
        new b.PopupClass(
        {
          title: "送信完了",
          content: "邮箱地址已发送",
          closeBtnText: "关闭"
        })
      })) : new b.PopupClass(
      {
        title: "错误",
        content: "请输入邮箱地址",
        closeBtnText: "关闭"
      }))
    },
    sendAuthNumBtn: function(a)
    {
      a.preventDefault();
      b.isScrolled() || ((a = $("#inputAuthNum").val()) ? (console.log("repaymentCode", a), c.ajaxPost(b.linkList.registerRepaymentMail,
      {
        repaymentCode: a
      }, function(a)
      {
        console.log("res", a);
        a.errorMessage ? new b.PopupClass(
        {
          title: "错误",
          content: "错误留言<br><br>【 " + a.errorMessage + " 】",
          closeBtnText: "关闭"
        }) : new b.PopupClass(
        {
          title: "送信完了",
          content: "验证码已发送",
          closeBtnText: "关闭"
        })
      })) : new b.PopupClass(
      {
        title: "错误",
        content: "请输入验证码",
        closeBtnText: "关闭"
      }))
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
      c.pageModelGet(this.needModelIdObj)
    },
    init: function()
    {
      b.setStyle(h);
      d = new k
    },
    remove: function(a)
    {
      d && d.remove();
      a()
    }
  }
});
