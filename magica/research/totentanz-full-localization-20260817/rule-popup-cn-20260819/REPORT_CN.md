# RulePopup 简体中文翻译报告

## 结论

`magica/template/etc/RulePopup.html` 已使用当前 Totentanz 日文法务页的完整结构生成并写入产品树。

- 唯一结构源：`A:\totentanz-frontend\template\etc\RulePopup.html`，29,770 字节、173 行。
- 中文来源层：`root-reviewed-translation`。
- 本页中文不是国服官方中文，也没有套用旧国服上海幻电／哔哩哔哩条款。
- 可见文本记录：146 条，其中翻译 144 条，原样保护 2 条。
- 产品文件：`magica/template/etc/RulePopup.html`。

## 法律名称与公司名称闭合

- `株式会社アニプレックス` → `Aniplex股份有限公司`；
- `著作権法` → `《著作权法》`；
- `資金決済法` → `《资金结算法》`；
- `個人情報の保護に関する法律` → `《个人信息保护法》`；
- `日本法` → `日本法律`；
- `前払式支払手段` → `预付式支付手段`；
- `東京地方裁判所` → `东京地方法院`；
- `adjust株式会社` → `adjust股份有限公司`；
- `株式会社セガ`／`セガ公司` → `世嘉股份有限公司`／`世嘉公司`。

原样保护的是 Sauce Labs、Backtrace、Adjust、Pnote 等拉丁专名及工具名，以及：

- 两个原始 URL；
- `rulesBase`、`rulePolicyLink`、`ruleLinkAdjust` 三个 DOM id。

## 结构验证

- HTML 标签序列：177/177 原样一致；
- EJS 令牌：0/0；
- DOM id：3/3 原样一致；
- URL：2/2 原样一致；
- 行结构：173/173；
- 可见日文法律名、公司名及假名残留：0；URL 路径中的拉丁字母 `ja` 不属于可见日文文本。

## 审计与回撤

- `input/RulePopup.ja.html`：对当前 A: 源文件的精确镜像；
- `input/reviewed_translation_lines.tsv`：146 条逐行审定译文；
- `runtime/comparison.tsv`：日文原行／最终中文／操作／来源层对照；
- `runtime/manifest.json`：来源、计数、结构合同与受保护词；
- `runtime/verification.json`：产品验证结果；
- `runtime/rollback.json` 与 `runtime/rollback.ps1`：通过精确字节门后移除本轮新建产品文件。

`tools/test-apply-rule-popup-cn.py` 共 12 项测试，覆盖正常应用、现有目标拒绝、源镜像漂移、翻译缺行、HTML 标签漂移、DOM id 漂移、URL 漂移、Aniplex 中文公司名漂移、准备文件漂移、产品漂移、应用失败补偿和回撤失败补偿。

已实测“应用 → 验证 → 回撤 → 再应用 → 再验证”，最终产品树保持中文应用状态。
