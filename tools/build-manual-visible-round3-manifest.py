#!/usr/bin/env python3
"""Materialize the bounded Round3 translation decisions as UTF-8 TSV/JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "magica/research/totentanz-full-localization-20260817/authority-source-exhaustion-round3/manual_translation_candidates.tsv"
OUT = ROOT / "magica/research/totentanz-full-localization-20260817/manual-visible-round3"

WELCOME = (
    '<p class="newsHeadUnder">【欢迎】Totentanz 正式启动！</p>\n'
    '<p class="mb20">Totentanz 作为《魔法纪录 魔法少女小圆外传》的重构版正式发布。'
    '本版本从一开始便开放全部剧情章节与游戏模式，不需要注册账号，也不记录游戏进度。'
    '各项功能均经过细致整合与优化，让你流畅、不间断地体验源自原作的丰富剧情与战斗。</p>\n'
    '<p class="mb20">请尽情沉浸于完整故事，体验长久以来吸引世界各地玩家的策略战斗。'
    '全部内容均可立即使用，让每位玩家都能不受阻碍地体验每一段展开。</p>'
)

FAQ = (
    '<p class="newsHeadUnder">【常见问题】关于 Totentanz</p>\n<ol>\n'
    '<li class="mb20">\n<b>Q</b>：Totentanz 是什么？\n<br />\n<b>A</b>：Totentanz 是《魔法纪录 魔法少女小圆外传》的重构版，剧情与全部游戏模式从一开始便完全开放。\n</li>\n'
    '<li class="mb20">\n<b>Q</b>：需要注册账号吗？\n<br />\n<b>A</b>：不需要。Totentanz 以无状态模式运行，所有功能均可立即使用。\n</li>\n'
    '<li class="mb20">\n<b>Q</b>：游戏进度如何管理？\n<br />\n<b>A</b>：每次会话开始时都可访问全部内容，会话之间不会保存进度。\n</li>\n'
    '<li class="mb20">\n<b>Q</b>：有应用内购买或使用限制吗？\n<br />\n<b>A</b>：Totentanz 是完全免费、非商业用途的项目，所有内容均可不受限制地使用。\n</li>\n'
    '<li class="mb20">\n<b>Q</b>：Totentanz 支持哪些平台？\n<br />\n<b>A</b>：目前仅支持 Android 版，未来可能会实现 iOS 版。\n</li>\n'
    '<li class="mb20">\n<b>Q</b>：Totentanz 与原版有什么不同？\n<br />\n<b>A</b>：Totentanz 保留《魔法纪录 魔法少女小圆外传》的精彩剧情与策略战斗，同时移除进度限制，提供可自由探索全部内容的连贯体验。\n</li>\n'
    '</ol>\n<p class="mb20">如有需要，今后还会继续补充问题与回答。</p>'
)

CONTACT = (
    '<p class="newsHeadUnder">【联系我们】支持与贡献</p>\n'
    '<p class="mb20">一般咨询与建议请发送至：<b>livia@cirno.name</b></p>\n'
    '<p class="mb20">法律或官方事项请发送至：<b>9@cirno.name</b></p>\n'
    '<p class="mb20">欢迎通过以下 GitHub 仓库贡献资源与翻译：</p>\n'
    '<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://github.com/Puella-Care/en-download"><span>可下载资源</span></p>\n'
    '<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://github.com/Puella-Care/en-image_web"><span>Web 资源</span></p>\n'
    '<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://github.com/Puella-Care/en-text"><span>Web 文本文件</span></p>\n'
    '<p class="mb20">如愿意协助承担域名、开发与服务器维护费用，也请联系一般咨询邮箱。</p>\n'
    '<p class="mb20">衷心感谢所有支持 Totentanz 发展的人。</p>'
)

T: dict[str, str] = {
    "HELP-16-GROUP-TITLE": "心魔战",
    "HELP-17-GROUP-TITLE": "魔法少女总战力",
    "HELP-18-GROUP-TITLE": "歼灭战",
    "HELP-19-GROUP-TITLE": "巡逻",
    "HELP-20-GROUP-TITLE": "战斗博物馆",
    "HELP-04-08-TITLE": "强化道具",
    "HELP-04-08-TEXT": "■《魔法纪录》中存在以下强化道具。<br/>·强化宝石：可用于魔力强化，使魔法少女的等级上升。<br/>·透明相册：可用于强化剧情Lv，获得剧情Pt。<br/>·命运宝石：可用于魔力解放，使记忆结晶装备框扩张。<br/>·纯真宝石：可用于所有魔法少女的魔力解放，使记忆结晶装备框扩张。<br/>·觉醒素材：可用于觉醒，使能力值与稀有度上升。<br/>·书：可用于Magia强化，使Magia等级上升。<br/>·属性强化宝石：可用于属性强化，使魔法少女的能力值上升。",
    "HELP-04-09-TITLE": "精神强化",
    "HELP-04-09-TEXT": "■魔法少女通过精神强化，可以提升能力值，并习得其固有的潜在技能与潜在能力。<br/>精神强化需要使用精神强化盘格子所指定的道具和诅咒晶片（CC）。<br/><br/>每位魔法少女各有100个精神强化盘格子。",
    "HELP-04-10-TITLE": "属性强化",
    "HELP-04-10-TEXT": "■属性强化是使用属性强化宝石、各属性宝石++、大师宝石++等<br/>道具来提升魔法少女能力值的功能。<br/><br/>每位魔法少女都有用于提升各项能力值（HP、ATK、DEF）的魔力印，<br/>消耗魔力印指定的必要道具后，<br/>属性魔力会得到强化，能力值也会提升。<br/><br/>属性强化宝石分为以下3种。<br/>·生命宝石<br/>·力量宝石<br/>·守护宝石<br/><br/>属性强化宝石可通过限时活动商店兑换，<br/>也可在觉醒强化副本的超级难度中获得。<br/><br/>属性强化所提升的能力值不仅适用于接受强化的魔法少女，<br/>也适用于与其属性相同的所有魔法少女。<br/><br/>此外，属性强化会根据对象魔法少女的魔力解放次数，<br/>解锁可强化的魔力印；魔力解放次数越多，<br/>就越能进一步提升能力值。",
    "HELP-13-02-TITLE": "Magia通行证30",
    "HELP-13-02-TEXT": "■购买Magia通行证30后可立即获得33个魔法石，并在之后30天内（含购买当天）每天获得5个免费魔法石和1枚每日硬币。<br/><br/>购买当天可获得33个付费魔法石＋5个免费魔法石，共计38个魔法石。<br/>从次日起的29天内，将随登录奖励一同获得5个免费魔法石和1枚每日硬币。<br/><br/>注意事项<br/>·“Magia通行证30”可在魔法石购买画面购买。<br/><br/>·“Magia通行证30”有效期内，未登录的日期无法获得5个免费魔法石和1枚每日硬币，也无法在之后一次性补领。<br/><br/>·“Magia通行证30”有效期结束后，可从次日起再次购买。",
    "HELP-14-11-TITLE": "教程【精神强化】",
    "HELP-14-12-TITLE": "教程【属性强化】",
    "HELP-15-11-TITLE": "许可信息",
    "HELP-15-10-TITLE": "开源许可信息",
    "HELP-16-01-TITLE": "心魔战",
    "HELP-16-01-TEXT": "■心魔战是挑战限时出现的“心魔”的战斗。<br>每天可挑战3次规则不同于普通战斗的特殊战斗。<br>·回合限制<br>心魔战的每场战斗都有回合限制。<br>·属性克制<br>心魔战中，属性有利与不利的计算方式不同于普通战斗。<br>有利属性造成的伤害会进一步增加，其他属性造成的伤害则会降低。<br>·Charge数与MP<br>在下次挑战次数恢复前，战斗中的Charge数与MP可以继承。",
    "HELP-16-02-TITLE": "模拟战",
    "HELP-16-02-TEXT": "■可在不消耗每日挑战次数的情况下进行心魔战。<br>模拟战中无法获得小组积分和心魔奖章，也无法继承MP与Charge数。",
    "HELP-16-03-TITLE": "心魔奖章",
    "HELP-16-03-TEXT": "■根据在心魔战中获得的小组积分，可获得心魔奖章。<br>心魔奖章可在商店中兑换感情的碎片等各种道具。",
    "HELP-16-04-TITLE": "小组积分",
    "HELP-16-04-TEXT": "■在心魔战中可以获得的积分。<br>根据造成的伤害、敌人的强度，以及战斗中的编成和行动可获得加成。",
    "HELP-17-01-TITLE": "魔法少女总战力值",
    "HELP-17-01-TEXT": "■“魔法少女总战力值”是所持全部魔法少女战力的总和。<br>持有的魔法少女越多、培养程度越高，该数值就越高。<br>出现以下情况时，总战力会增加或减少。<br><br>■增加<br>·魔法少女Lv提升，或开放“精神强化”格子（能力值提升）时<br>各项能力值的提升量会直接计入。<br><br>·设置觉醒素材时<br>每个素材增加200。<br><br>·魔力解放时<br>每次增加500。<br><br>·开放精神强化格子（能力值提升以外）时<br>每格增加100。<br><br>·通过Magia强化提升Lv时<br>每提升1Lv增加300。<br><br>·解放魔女化身时<br>每解放1位魔法少女的魔女化身增加1000。<br><br>·获得魔法少女时<br>获得时该魔法少女各项能力值的总和会计入。<br><br>·属性强化时<br>各项能力值的提升量会直接计入。<br>会按对象魔法少女的人数分别计入；获得对象魔法少女时，<br>属性强化带来的能力值提升量也会一并计入。<br><br>■减少<br>·使用“原点之器”重置“精神强化”时<br>会根据被重置的精神强化格子数量和能力值减少。<br>减少量等于这些项目此前计入的总值。<br><br>·觉醒时<br>会扣除觉醒前能力值与觉醒后初始能力值之间的差额。<br>同时，由于已设置的觉醒素材会被重置，其计入值也会扣除。<br><br>※持有的记忆结晶数量与能力值等，不会影响“魔法少女总战力”的计算。",
    "HELP-17-02-TITLE": "魔法少女总战力排名",
    "HELP-17-02-TEXT": "■“魔法少女总战力排名”可在个人资料画面查看；当自己的排名位于前50000名时会显示具体名次。<br>排名在50001名之后的玩家会显示为“排名外”，并可查看进入前50000名所需的“魔法少女总战力”。<br>“魔法少女总战力排名”每天04:00开始统计。<br><br>※“魔法少女总战力”和“魔法少女总战力排名”不会向其他玩家显示。<br>※2020年10月30日17:00以后至少登录过1次的玩家会被纳入排名统计。<br>※统计结果可能需要一段时间才会反映。",
    "HELP-18-01-TITLE": "歼灭战",
    "HELP-18-01-TEXT": "■歼灭战是压制突然出现的5个魔女结界的活动。<br>歼灭战设有分为5档难度的关卡。<br>关卡中会出现5个魔女结界，打倒结界深处的魔女后，<br>即可压制对应的魔女结界。<br>玩家的目标是压制关卡内的全部魔女结界。<br>",
    "HELP-18-02-TITLE": "歼灭战队伍编成",
    "HELP-18-02-TEXT": "■在“歼灭战”中，挑战关卡前需要编成5支队伍。<br>·编成限制<br>歼灭战有以下编成限制：<br>只有★4及以上的魔法少女可以编入队伍。<br>同一位魔法少女不能重复编入多支队伍。<br>在关卡内打倒魔女的队伍成员会进入压制该魔女结界的状态，<br>无法再编入关卡内其他魔女结界的战斗。<br>",
    "HELP-19-01-TITLE": "巡逻",
    "HELP-19-01-TEXT": "■巡逻是派遣3支队伍分别前往3个区域探索的功能，每支队伍最多可编入5位魔法少女。经过一定时间后探索完成，并可获得各种道具。",
    "HELP-19-02-TITLE": "区域",
    "HELP-19-02-TEXT": "■共有3个可探索区域，各区域能够获得的道具不同。<br>·繁华街<br>·镜屋<br>·心魔结界<br><span class='c_red'>※区域“镜屋”会在通关主线剧情第1部第2章第5话后开放；区域“心魔结界”会在通关主线剧情第2部序章后开放。</span>",
    "HELP-19-03-TITLE": "编成",
    "HELP-19-03-TEXT": "■为前往探索的队伍编入最多5位魔法少女。<br>·总战力值<br>　已编成魔法少女的战力值总和会显示为“总战力值”。<br>　<span class='c_red'>※即使探索开始后“总战力值”发生更新，<br>　　获得道具时仍以探索开始时的“总战力值”为准。</span><br><br>·有利属性带来的战力值提升<br>　每个区域都有适合探索的有利属性。<br>　当已编成魔法少女的属性与区域有利属性一致时，<br>　该魔法少女的战力值会提升至1.5倍。<br><br>·自动编成<br>　点击编成画面中的“自动编成”按钮后，<br>　会优先编入玩家持有的魔法少女中战力值较高的成员。<br>　<span class='c_red'>※自动编成时也会计算有利属性带来的战力值提升。</span>",
    "HELP-19-04-TITLE": "掉落预期",
    "HELP-19-04-TEXT": "■开始探索时，已编成魔法少女的“总战力值”越高，探索完成时能够获得的道具就越多。",
    "HELP-19-05-TITLE": "报酬",
    "HELP-19-05-TEXT": "■探索完成后，可以获得“感情的碎片”、觉醒素材、诅咒晶片等各种道具。探索完成后，区域中可获得的报酬内容和有利属性也会切换。",
    "HELP-20-01-TITLE": "战斗博物馆",
    "HELP-20-01-TEXT": "■在战斗博物馆中，可以挑战连续出现的特殊关卡；通关时魔法少女的HP和MP会继承至下一关。<br>每次举办“战斗博物馆”时，还会追加更多关卡。<br>※已继承的HP与MP会在下次举办时重置。",
}

# The remaining bounded groups are kept separately so duplicate IDs fail closed.
T.update({
    "SECOND-LAST-GROUP-NAME": "最终决战",
    "SECOND-LAST-0-ENEMYNAME": "镜之魔女的手臂1",
    "SECOND-LAST-0-ENEMYNAMESHORTHAND": "镜之魔女的手臂1",
    "SECOND-LAST-0-ENEMYSKILLINFO": "[状态异常] 烧伤,[增益] 攻击力 & 防御力 & 状态异常耐性提升",
    "SECOND-LAST-1-ENEMYNAME": "镜之魔女的手臂2",
    "SECOND-LAST-1-ENEMYNAMESHORTHAND": "镜之魔女的手臂2",
    "SECOND-LAST-1-ENEMYSKILLINFO": "[状态强化] 状态异常时伤害提升,[状态异常] 黑暗 & 幻惑 & 强化毒 & 烧伤,[状态异常] 诅咒 & 虚弱 & 禁止回复HP & 禁止回复MP",
    "SECOND-LAST-2-ENEMYNAME": "镜之魔女的手臂3",
    "SECOND-LAST-2-ENEMYNAMESHORTHAND": "镜之魔女的手臂3",
    "SECOND-LAST-2-ENEMYSKILLINFO": "[状态强化] 暴击 & Magia伤害削减,[增益] 攻击力提升",
    "SECOND-LAST-3-ENEMYNAME": "镜之魔女的手臂4",
    "SECOND-LAST-3-ENEMYNAMESHORTHAND": "镜之魔女的手臂4",
    "SECOND-LAST-3-ENEMYSKILLINFO": "[状态强化] 伤害提升状态,[状态异常] 禁止回复HP,[特殊] 回避无效 & 减益无效",
    "SECOND-LAST-4-ENEMYNAME": "镜之魔女的头部",
    "SECOND-LAST-4-ENEMYNAMESHORTHAND": "镜之魔女的头部",
    "SECOND-LAST-4-ENEMYSKILLINFO": "[状态强化] 自动回复MP,[状态强化] 无视伤害削减 & 无视防御,[增益] 攻击力提升",

    "WALPURGIS-STAMP-0": "请多关照～",
    "WALPURGIS-STAMP-1": "加油！",
    "WALPURGIS-STAMP-2": "要上了！",
    "WALPURGIS-STAMP-3": "早上好",
    "WALPURGIS-STAMP-4": "晚安",
    "WALPURGIS-STAMP-5": "辛苦了",
    "WALPURGIS-STAMP-6": "太好了！",
    "WALPURGIS-STAMP-7": "漂亮！",

    "CSS-PatrolDeckView-0": "加成",
    "CSS-PatrolDeckView-1": "经验",
    "CSS-PatrolDeckView-2": "总战力值",
    "CSS-PatrolDeckView-3": "掉落预期",
    "CSS-RegularEventGroupBattleRanking-0": "伤害",
    "CSS-RegularEventGroupBattleRanking-1": "击退Lv",
    "CSS-RegularEventGroupBattleRanking-2": "领取",
    "CSS-RegularEventGroupBattleUser-0": "伤害",
    "CSS-RegularEventGroupBattleUser-1": "击退Lv",
    "CSS-RegularEventGroupBattleUser-2": "领取",

    "ANNOUNCEMENT-1-SUBJECT": "【欢迎】Totentanz 正式启动！",
    "ANNOUNCEMENT-1-TEXT": WELCOME,
    "ANNOUNCEMENT-2-SUBJECT": "【常见问题】关于 Totentanz",
    "ANNOUNCEMENT-2-TEXT": FAQ,
    "ANNOUNCEMENT-3-SUBJECT": "【联系我们】支持与贡献",
    "ANNOUNCEMENT-3-TEXT": CONTACT,
    "ANNOUNCEMENT-4-SUBJECT": "【欢迎】Totentanz 正式启动！",
    "ANNOUNCEMENT-4-TEXT": WELCOME,
    "ANNOUNCEMENT-5-SUBJECT": "【常见问题】关于 Totentanz",
    "ANNOUNCEMENT-5-TEXT": FAQ,
    "ANNOUNCEMENT-6-SUBJECT": "【联系我们】支持与贡献",
    "ANNOUNCEMENT-6-TEXT": CONTACT,
    "ANNOUNCEMENT-7-SUBJECT": "【推广】Magia Exedra 现已上线！",
    "ANNOUNCEMENT-7-TEXT": '<p class="newsHeadUnder">【推广】Magia Exedra 现已上线！</p>\n<p class="mb20">Magia Exedra 的魔法世界现已开放。史诗般的任务、策略战斗与精彩故事正等待着你。</p>\n<p class="mb20">请选择喜爱的平台，开始这段旅程：</p>\n<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://apps.apple.com/us/app/6480402391"><span>App Store</span></p>\n<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://play.google.com/store/apps/details?id=com.aniplex.magia.exedra.en"><span>Google Play</span></p>\n<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://store.steampowered.com/app/2987800/Madoka_Magica_Magia_Exedra/"><span>Steam</span></p>',
    "ANNOUNCEMENT-8-SUBJECT": "【推广】Magia Exedra 现已上线！",
    "ANNOUNCEMENT-8-TEXT": '<p class="newsHeadUnder">【推广】Magia Exedra 现已上线！</p>\n<p class="mb20">以魔法世界为舞台的宏大冒险——Magia Exedra 现已登场。敬请体验史诗般的任务、策略战斗与精彩故事。</p>\n<p class="mb20">请通过以下链接选择下载平台：</p>\n<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://play.google.com/store/apps/details?id=com.aniplex.magia.exedra.jp"><span>Google Play</span></p>\n<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://apps.apple.com/jp/app/6480167901"><span>App Store</span></p>\n<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://store.steampowered.com/app/2987800/Madoka_Magica_Magia_Exedra/"><span>Steam</span></p>',
    "ANNOUNCEMENT-9-SUBJECT": "【新闻】7月更新",
    "ANNOUNCEMENT-9-TEXT": '<p class="newsHeadUnder">【新闻】7月更新</p>\n<p class="mb20">游戏计划于2025年7月7日恢复上线。</p>\n<p class="mb20">主要变化：支持IPv6；服务器重启后可保留状态。</p>\n<p class="btn b_pink TE announceOuterLink" style="width:500px;" data-outlink="https://boosty.to/PuellaCare/donate"><span>可通过Boosty捐助</span></p>',

    "BANNER-9991-DESCRIPTION": "魔法少女小圆 Magia Exedra",
    "BANNER-9991-BANNERTEXT": "举办期间：04/01～",
    "BANNER-9992-DESCRIPTION": "魔法少女小圆 Magia Exedra",
    "BANNER-9992-BANNERTEXT": "举办期间：04/01～",
    "BANNER-701-DESCRIPTION": "莉薇娅的特别优惠",
    "BANNER-701-BANNERTEXT": "举办期间：11/12～11/19 14:59",
    "BANNER-844-DESCRIPTION": "御魂的特训",
    "BANNER-844-BANNERTEXT": "举办期间：7/11～7/22 14:59",
    "BANNER-880-DESCRIPTION": "魔法纪录奇迹问答",
    "BANNER-880-BANNERTEXT": "举办期间：8/22～9/5 14:59",
    "BANNER-1202-DESCRIPTION": "右上：魔法纸相扑 豪华版・极",
    "BANNER-1235-DESCRIPTION": "【开始】举办“战斗博物馆”",
    "BANNER-1235-BANNERTEXT": "举办期间：5/31～6/7 14:59",
    "BANNER-1237-DESCRIPTION": "【开始】举办“BEYOND MAGIA”",
    "BANNER-1237-BANNERTEXT": "举办期间：6/7～6/12 14:59",
    "BANNER-1238-DESCRIPTION": "【开始】举办“笼目的百怪波澜～炎夏之宴～”",
    "BANNER-1238-BANNERTEXT": "举办期间：6/12～6/24 14:59",
    "BANNER-1240-DESCRIPTION": "【开始】举办“歼灭战～魔女们的悖论～”",
    "BANNER-1240-BANNERTEXT": "举办期间：6/24～7/1 14:59",
    "BANNER-1242-DESCRIPTION": "【开始】举办“阿莉娜的工作室～Factor of Despair～”",
    "BANNER-1242-BANNERTEXT": "举办期间：7/1～7/12 14:59",
    "BANNER-1245-DESCRIPTION": "【开始】举办“心魔战特别篇 幸福的魔女”",
    "BANNER-1245-BANNERTEXT": "举办期间：7/16～7/21 15:59",
})

KEEP = {
    "HELP-14-11-TEXT": "structural-image-only-html",
    "HELP-14-12-TEXT": "structural-image-only-html",
    "HELP-15-11-TEXT": "legal-license-verbatim",
    "HELP-15-10-TEXT": "legal-license-verbatim",
}


def main() -> int:
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle, delimiter="\t"))
    source_ids = {row["candidate_id"] for row in source_rows}
    expected_ids = set(T) | set(KEEP)
    if source_ids != expected_ids or len(source_ids) != len(source_rows):
        raise SystemExit(
            f"inventory mismatch missing={sorted(source_ids - expected_ids)} "
            f"extra={sorted(expected_ids - source_ids)} duplicates={len(source_rows)-len(source_ids)}"
        )

    rows = []
    for original in source_rows:
        item_id = original["candidate_id"]
        retained = item_id in KEEP
        final_cn = original["source_text"] if retained else T[item_id]
        support = "root-careful-translation"
        if item_id in {"BANNER-1238-DESCRIPTION", "BANNER-1242-DESCRIPTION", "BANNER-1245-DESCRIPTION"}:
            support = "wiki-title-supported-root-composition"
        elif item_id.startswith("HELP-") or item_id.startswith("SECOND-"):
            support = "official-terminology-supported-root-translation"
        rows.append({
            "item_id": item_id,
            "target_path": original["path"],
            "stable_key": original["stable_key"],
            "field": original["field"],
            "source_text": original["source_text"],
            "final_cn": final_cn,
            "upstream_source_path": original["evidence_path"],
            "authority_support": KEEP[item_id] if retained else support,
            "machine_translated": "false" if retained else "true",
            "human_review_status": "not-applicable" if retained else "not-yet-human-reviewed",
            "product_write_allowed": "false" if retained else "true",
            "final_status": KEEP[item_id] if retained else "rough-production-root-translation",
            "source_text_length": len(original["source_text"]),
            "final_cn_length": len(final_cn),
            "notes": original["notes"],
        })

    OUT.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (OUT / "manual_translation_round3.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    counts = {
        "inventory": len(rows),
        "product_write_allowed": sum(row["product_write_allowed"] == "true" for row in rows),
        "retained_nontranslatable_or_structural": sum(row["product_write_allowed"] == "false" for row in rows),
        "not_yet_human_reviewed": sum(row["human_review_status"] == "not-yet-human-reviewed" for row in rows),
    }
    (OUT / "manual_translation_round3.json").write_text(
        json.dumps({"schema": 1, "counts": counts, "items": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
