# 字体替换与补字（客户端 1.0.194）

外部文件名只是既有加载接口的兼容别名，不表示文件仍是腾祥字体。
TTDaYuanGB3.ttf：寒蝉全圆体 Bold 3.200 补字版，内部名 Magius Round Symbols Bold。
TTZhiHeiGB3-W4.ttf 及 Web mbm_20160902.ttf：MiSans Semibold 4.009 补字版，内部名 Magius Sans Symbols Semibold。

仅增加目标缺失的字符；原版已有轮廓、字宽和垂直度量逐一校验不变。需求覆盖旧版49个补字字符、七种音乐符号及现行游戏文本。补充轮廓来自Apache-2.0的Droid字体与独立几何音乐符号；圆体可另用OFL的Noto Sans CJK。半角韩文字形按Unicode规范化对应关系适配。未从腾祥字体复制轮廓。

寒蝉修改版遵守OFL并使用不同家族名，版权和许可证均随包保留。使用了MiSans，其上游版权与许可信息保留；此补字版不是小米官方原版。项目维护者指定的改动不等于小米对修改的额外许可，不能以修改幅度或被发现概率推断许可。官方说明：https://hyperos.mi.com/font/zh/faq/

原生MTF4a5kp.ttf和assets/fonts/mbm_20160902.ttf历史字节不动，字体路由和文本布局不改。U+F6DB语义仍未明确，不伪造字形；真机显示由维护者验收。
