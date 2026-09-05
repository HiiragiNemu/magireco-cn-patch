# 守卫「防犯蠢」护栏系统 — rev4

> 定位：**防 Agent 犯蠢/漏/误操作**，不是防恶意 Agent 的安全边界（Agent 是 root，任何本机护栏都能被它绕开）。
> 原则：**守卫自身判断失败 = Fail closed**。Claude hooks 层 = 快速提醒；Git hooks 层 = 本机强制。
> 说明：包内 `GH_TOKEN`/`ghp_`/`github_pat_` 等是**检测规则/占位符**，非真实密钥。`token-helper.cpp` 的 value 均为空。
>
> **rev4 最重要的变化：本包不再含任何私有仓库名、业务域名或内部标识。** R1(私有仓名) 和 R4(业务标识正则) 全部走
> `private-repos.json` 动态缓存；来源 = 环境变量 `GH_TOKEN_1..N`(各 Owner 的 Metadata:Read PAT，token-helper ELF 负责写进环境)
> + gh + 本机私有种子(owners/private/patterns)。**本包可以放 CDN；`local-only/` 里的两个文件不可以。**

## 结构

```
policy/
  policy.json        # 规则单一来源: 静态正则(R2 型号/会话) + secret 正则(R7) + agent_branch_prefixes(R5) + 指纹/签名指引(R6) + 作者邮箱(R3) + 各路径 + expected_owners
  check.py           # 引擎: content / commit / push 三模式, 三态 pass|violation|error；三模式都做 R1(动态)。--net 才联网(git 钩子/scan-repo 传)
  doctor.py          # 一键自检(路径按自身位置推导，bootstrap 搬家后仍可用)
  install-settings.py# 幂等注入 settings.json(用户级，或 <repo>/.claude/settings.json 仓库级)：5 个 PreToolUse + SessionStart + attribution.sessionUrl=false
  bootstrap.sh       # 铺设脚本 = claude.ai Environment 的 Setup Script，本机也用它装(见「部署」)
  msgcb-hygiene.py   # filter-repo --message-callback body(消息中性化；映射表读本机 sanitize-map.json)
  token-helper.cpp   # token 焊入 ELF 模板(填值后 g++ 编译；产物只放本机)。唯一职责：把 GH_TOKEN_n 写进环境，护栏本身只读环境变量
hooks/
  _lib.sh            # 五个 Claude hook 共用: 放行=不表态(exit 0 无输出), 拦截=deny JSON + exit 2
  forbid-content.sh  # Write|Edit|NotebookEdit: 拦新内容(content/new_string/new_source)
  forbid-commit.sh   # git … commit: 拦消息/作者 + 拦 --no-verify/-n/--no-gpg-sign/改 hooksPath/gpgsign
  forbid-push.sh     # git … push: 拦推向 Agent 分支(含 `push -u origin claude/x` 形态) + --no-verify
  forbid-read-secret.sh  # 拦"读 token/打 token 到会话"(提醒级)
  forbid-tamper.sh   # (新增, 可选) 拦改 core.hooksPath/disableAllHooks/删改护栏目录与 settings.json
  refresh-private.py # 私有仓并集: 种子(owners/private/patterns) + gh + 环境变量 GH_TOKEN_n，owner 覆盖校验，原子写缓存
  resolve-private.py # R1 补充: 对缓存里没有的 xxx-xxx 裸名 / 已知 owner 下的 owner/repo 单名查询(由 check.py --net 调用; 负缓存 24h)
  scan-repo.py       # 存量审计(HEAD 树 + 全历史消息；--scan-history 全历史树)；R1 同样读动态缓存
hooks/git/           # Git 层强制执行(只调 check.py)
  pre-commit / pre-merge-commit / commit-msg / pre-push
settings.json        # 本机 CLI 用的 Claude Code hooks 示例(env 已脱敏)
```

不随包分发、只放本机(`local-only/`)；bootstrap 装完后的位置是 `$GUARD`(默认 `/root/.claude/guardrails/`)：
- `$GUARD/private-seed.json`(云端：环境变量 `GUARD_SEED_B64`) —— `{"owners":[…], "private":["Owner/repo", …], "patterns":["业务标识正则", …]}`：
  离线兜底 + 声明哪些 owner 必须被覆盖 + R4 业务标识(域名/内部流水线名)正则。
- `$GUARD/sanitize-map.json` —— msgcb-hygiene.py 的 名字→中性名 映射。
- token-helper 编译产物(含 token)——把 `GH_TOKEN_1..N` 写进 Claude Code / 钩子的运行环境；云端直接在 Environment 环境变量里配。

## 规则 R1–R7
- **R1** 私有仓名：来自 `private-repos.json`(`Owner/repo` 与裸名两种形态；裸名为子串匹配，设计如此)。缓存缺失/损坏/过期 → **ERROR → 拦**：git 钩子(`--net`)会先就地刷新一次，Claude hooks 不联网、直接让 Agent 跑 `refresh-private.py`。
  补充(`--net`)：缓存里没有、但长得像仓名的裸名(`xxx-xxx`，≥6 字符、至少一段含 2 个字母、后面不跟 `:`) 与 已知 owner 下的 `owner/repo`，交给 `resolve-private.py` 逐个问 GitHub：private → 拦；public/不存在 → 放；查不到(无 token/网络) → ERROR。候选超过 `resolve_budget`(30) 时不逐个查，改为整体 refresh 一次再按新名单比。`Co-authored-by` 等 trailer 键与 `pre-commit` 等常见词在 `resolve_ignore` 里忽略。
- **R2** 具体型号 + 会话：`Claude <tier> <ver>`、`Claude 4.5`、`Claude Sonnet`、`Opus/Sonnet/Haiku/Fable/Mythos <ver>`、`claude_sonnet_4_6`、`GPT-x`、`OpenAI o3`/`o3-mini`、`Gemini x`、`DeepSeek-Vx/Rx`、`Kimi Kx`、`Qwen/Llama/Grok/Mistral <ver>`；`Claude-Session:`、`claude.ai`。
  形态上有误伤(`Claude found 3 bugs`)——按约定提交信息全中文，不处理；注意这些正则也作用于文件内容。
- **R3** 作者/提交者不得是 Agent 提供商 noreply；非根提交必须带 `Co-authored-by:`。
- **R4** 业务标识(域名/内部流水线名)：**不在包里**，来自本机种子 `patterns` → 缓存 → check.py/scan-repo。没有种子的环境 R4 不生效(doctor 会 WARN)。
- **R5** 禁止推送到任何 Agent 分支：`agent_branch_prefixes`(claude/ codex/ chatgpt/ gpt/ openai/ agent/ deepseek/ kimi/ copilot/ cursor/ devin/ gemini/ jules/ aider/ anthropic/，大小写不敏感，含删除)。不做 main/强推保护——那是 GitHub ruleset 的活。
  注意：claude.ai 云端的 GitHub 代理只允许推会话工作分支 `claude/…`，所以云端会话在 R5 下推不出任何东西(按设计)。
- **R6** 必须 SSH 签名，且不能是 Agent 通用密钥。验签方式：从提交对象剥出 `gpgsig`，`ssh-keygen -Y check-novalidate -n git` 密码学验签并取指纹——**不需要 `gpg.ssh.allowedSignersFile`**(git 自带的 `%G?`/`%GK` 没有它时全为空，rev3 就死在这里)。
  发现未签名/通用密钥/非 SSH 签名 → 拦下并输出 `policy.signing_instructions`：让 Agent 生成 ed25519 密钥、配置 git、把公钥完整内容发给你，你手动加到 GitHub。
- **R7** 禁提交凭据**值**(`gh[pousr]_`、`github_pat_`、私钥、AKIA、`sk-…`(含 sk-proj-/sk-ant-)、xox、AIza、glpat、npm_)。**不再匹配变量名**(`GH_TOKEN`/`GITHUB_TOKEN`)。deny 理由里的凭据只回显前 8 字符。

## rev4 相对 rev3 的改动(全部有沙箱测试)
1. **私有仓名出包**：policy.json / forbid-patterns(已删，无人读取) / refresh-private 写死种子 / private-repos.json / msgcb 映射 全部清除；名单进 `local-only/`。
2. **R1 三模式统一**：rev3 的 commit-msg / pre-push / scan-repo 只查静态表(只在缓存里、不在静态表里的私有仓名，在 commit 模式直接 pass)。
3. **deny 理由脱敏**：rev3 会把命中的完整 token 原文回显进 Agent 会话。
4. **Claude hooks 语义修正**：rev3 放行时输出 `permissionDecision:"allow"` = **跳过权限确认**——四个 hook 合起来等于把所有 Bash/Write/Edit 自动放行。rev4 放行=不表态；拦截 = deny JSON + `exit 2`；输入解析失败按拦截；豁免路径 realpath 归一化。
5. **R6 修复**：指纹比较(`SHA256:` 前缀)、pre-commit 指纹算法、`--no-gpg-sign` 等绕过开关在快速层被拦、`%G?`=B 也拒。
6. **pre-push 只审远端没有的提交**(`git rev-list <tip> --not --remotes=<remote>`)：rev3 推新分支会重审全历史，历史上任一未签名(人类)提交即永久卡死(实测)。
7. **pre-commit 只扫新增行 + 涉及路径**：rev3 扫整份 diff 含删除行，清理违规词的提交永远提交不上(实测)。新增 `pre-merge-commit`。
8. **refresh-private 修复**：`gh api --jq .login` 输出裸字符串致 `me` 永远为 None(个人私有仓从不枚举)；`user/repos` 只翻第 1 页；组织仓被错记到 username；403 限流被当"看不到"静默丢 owner；无任何来源时会写出空的"fresh"缓存(fail open)。rev4：无来源不回写、`expected_owners` 覆盖校验(只有"看到该 owner ≥1 个私有仓"或种子列出才算覆盖，HTTP 200 不算)、原子写。
9. **bootstrap 修复**：rev3 的 sed 漏掉 refresh/resolve/scan/doctor 与 token-helper 路径 → 缓存读写路径不一致，云端装出来即坏。rev4 覆盖 policy/*、hooks/*.sh、hooks/*.py、hooks/git/*。
10. **install-settings 修复**：rev3 漏装 forbid-read-secret.sh；matcher 补 NotebookEdit；hook timeout 15→120s(check.py 懒刷新最长 60s；**hook 超时 = 无决策 = 放行**，timeout 必须大于内部最慢路径)。
11. **快速层补漏**：`git push -u origin claude/x`(Claude Code 实际形态，rev3 放行)；`--no-verify`/`-c core.hooksPath=`；forbid-read-secret 去掉裸词 `token`/裸 `.env`(rev3 把 `grep -rn access_token src/`、`sed s/token/` 全拦)，补 printf/`${VAR:0:n}`/`env|`/`/proc/*/environ`/`os.environ`/`gh auth status -t`。
12. scan-repo：无 origin 远端时永远报"干净"(selfname='' 过滤掉全部命中)已修；不再按扩展名白名单(漏 .gitmodules/Dockerfile)。
13. 删除 check.py 里无人调用的 `tokens()/get_token()`；commit 模式先剥 `core.commentChar` 注释行。
14. **按你的决定**：R4 业务标识全部出包进种子；R5 = 禁推一切 Agent 分支、不做 main/强推保护；#8 resolve-private 接入(xxx-xxx 形态)；#10-1 pre-push 扫新提交内容(cherry-pick/rebase/am/合并/--no-verify 进来的内容在这里兜底，实测)；#10-2 TTL 6h + Claude hook 路径永不联网(过期直接 ERROR 并给出刷新命令)；R6 改为 check-novalidate 验签 + 签名指引文案(policy.signing_instructions)；R7 去掉变量名匹配、补 `sk-proj-/sk-ant-/ghu_/ghr_/glpat/npm_`；R2 补漏的型号；token 只从环境变量 `GH_TOKEN_n` 读(不再调用 token-helper get)。

## 部署(两边都用 bootstrap.sh，装出来的目录结构完全一致：`/root/.claude/guardrails/`)
### 云端：claude.ai/code → Environment → Setup Script
1. 把 `policy/bootstrap.sh` 整段粘进 Setup Script，改第一处 `PKG_URL_DEFAULT` 为 CDN 上的包地址(zip/tgz 均可)。
2. Environment 环境变量：`GH_TOKEN_1..N`(各 Owner 的 Metadata:Read PAT)、`GUARD_SEED_B64`(`base64 -w0 private-seed.json`)。
3. Environment 网络白名单：CDN 域名 + `api.github.com`。
4. 脚本做的事(幂等，不漏装不重装)：装包 → 改写路径 → `core.hooksPath`(git 层，所有仓库自动生效) → 当前仓库 `.claude/settings.json` 合并 5 个 PreToolUse + SessionStart + `attribution.sessionUrl=false`(云端唯一会读的 Claude 层来源；按脚本名去重，仓库里已提交过护栏 settings 的不会再装；新写的文件进 `.git/info/exclude`) → 用户级 settings(云端忽略) → 刷新名单(拿不到环境变量就留给 SessionStart) → doctor。
   下载/解包失败脚本退出 1(环境创建失败)——没有护栏就不该让 Agent 跑。
5. 云端已知限制：GitHub 代理只放挂载仓库、只允许推 `claude/…`(与 R5 相斥，云端推不出东西，按设计)；环境变量与 Setup Script 对环境使用者/Agent 可读。
### 本机 CLI(Droidspaces 容器)
```
HOOK_PACKAGE_URL=file:///sdcard/guardrails-rev4-package.zip bash bootstrap.sh     # 再跑一次 = 升级(种子/映射/缓存保留)
cp private-seed.json sanitize-map.json /root/.claude/guardrails/ && chmod 600 /root/.claude/guardrails/{private-seed.json,sanitize-map.json}
g++ -O2 -o /root/.claude/guardrails/token-helper policy/token-helper.cpp   # 先手填 token；chmod 700；由它把 GH_TOKEN_1..N 写进 Claude Code 的环境
apt-get install -y openssh-client                                            # ssh-keygen 是 R6 验签的硬依赖
python3 /root/.claude/guardrails/hooks/refresh-private.py && python3 /root/.claude/guardrails/policy/doctor.py
```
仓库级 `.claude/settings.json` 若要提交进仓库，两边路径一致(都是 `/root/.claude/guardrails/hooks/...`)，本机也直接生效；用户级 settings 里的同名 hook 会各跑一次(重复 deny 一次，无害)。

## 已按你的决定处理(rev4)
- token 设计：护栏只读环境变量 `GH_TOKEN_1..N`；token-helper 的职责就是把它们写进环境。
- R5：禁推一切 Agent 分支(claude/ codex/ chatgpt/ …)；不做 main/强推保护(ruleset 负责)。
- R4：域名/内部标识全部出包 → 本机种子 `patterns`。
- R6：不依赖 allowedSignersFile，直接验签；拦下即输出"生成 ed25519 + 发公钥给我"的指引。
- R2：只补漏的型号，不改形态；R7：去掉变量名匹配。
- #8 resolve 接入(xxx-xxx)；#9 裸名子串不改；#10-1 pre-push 扫内容、#10-2 TTL 6h + Claude 层不联网；#10-3/4/5 维持原设计。

## 已定(第二轮)
- 云端：Environment Setup Script = bootstrap.sh；Claude 层走仓库级 `.claude/settings.json`(幂等、去重、未跟踪即 exclude)；名单来源 = `GH_TOKEN_n` + `GUARD_SEED_B64`。`expected_owners` 因此不需要填(种子里的 owners 就是覆盖声明)。
- 护栏目录/`settings.json` 写入不再豁免，和普通文件一样扫(含规则词的 README 会被拦)。
- 放行 = 不表态，本机恢复正常权限弹窗；Claude hooks 不联网(缓存过期直接拦并给刷新命令；未知裸名只在 git 层查)。
