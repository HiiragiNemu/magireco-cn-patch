"""Record the final recovery verification and deliver a usable handoff; docs-only main commits."""
from pathlib import Path
import datetime, gzip, json, sys
W = Path(__file__).resolve().parent
OUT = W / 'resume-finalization-20261003'
sys.path.insert(0, str(W))
from integrate import R, P, run, tree, enc, sha
from record_progress import commit_docs
C = 'docs/story-quality/client-integration/'
D = 'docs/story-quality/reader-final-20261003/'


def main():
    destination = OUT / 'handoff-completion.json'
    assert not destination.exists(), 'Already committed; read existing receipt instead of duplicating'
    result = json.loads((OUT / 'resume-verification.json').read_bytes())
    assert result['passed'] and result['rechecked_live_failed'] == 0
    assert result['client_target_states'] == {'pending': 359, 'unchanged_target': 2}, 'Client progressed; reconcile delivery states first'
    assert not result['client_receipt_paths'], 'Read new client delivery receipt before continuing'
    run(P, 'fetch', 'origin', 'main')
    ph = run(P, 'rev-parse', 'FETCH_HEAD').decode().strip()
    pt = tree(P, ph)
    raw_ready = run(P, 'show', ph + ':' + C + 'READY.json')
    assert sha(raw_ready) == result['ready_sha256'], 'READY changed concurrently'
    policy_raw = run(P, 'show', ph + ':' + C + 'release-policy.json')
    assert sha(policy_raw) == result['policy_sha256']
    handoff = run(P, 'show', ph + ':' + C + 'DELTA_ONLY_HANDOFF.md').decode('utf8')
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    versions = {x['url'].rsplit('/', 1)[-1]: x['data'] for x in result['game_versions']}
    assert versions['version_scenario.json']['version'] == 3323
    assert versions['version_js_delta.json']['version'] == 22
    assert versions['version_js.json']['version'] == 103
    summary = f'''# Reader正式新稿与游戏delta-only接手：中断恢复终检

核验时间：{result['verified_at']}。本次恢复不重新部署Reader，也不构建或发布游戏包。

## Reader已经完成

正式源码`{result['reader_source_revision']}`，部署`{result['reader_deployment_id']}`。已重新检查当前main中的601份输入，全部等于最终校订候选；其中361份JSON、240份TXT/网页配对文件。主域名构建信息、ADV current、校对配置三个入口均指向该构建源。

恢复后重新请求全部新稿普通接口及别名、网页正文、目录分片和搜索产物，共{result['rechecked_live_resources']}项，{result['rechecked_live_passed']}通过、{result['rechecked_live_failed']}失败，{result['rechecked_live_retries']}项使用重试。不是只看部署版本号。原2,929项全量验收结果逐条与原始预期哈希核对，并完整保留；原生产构建、测试和浏览器记录仍归属于那次固定源码，不冒称在本次重复运行。

## 游戏仍须完成的工作

现网仍是Scenario3323、完整JS103、累计JS delta22。361个客户端目标中359个需要改字节的文件仍未合入，2个原本无需改字节；没有新CLIENT_RECEIPT。Reader上线不能结算游戏待发稿。当前确认AI首次校订和已列残余复查均已闭合，游戏侧待交付仍为361个。

必须使用CN patch当前`docs/story-quality/client-integration/READY.json`、`release-policy.json`、`DELTA_ONLY_HANDOFF.md`。内容manifest `{result['client_manifest_sha256']}`；政策SHA `{result['policy_sha256']}`。

新的发布方式只有累计JS delta，固定现有Scenario3323和JS103。现有生产工作流还会共同重建完整Scenario，必须先实现delta-only路径，不能直接触发旧流程。源码整合、构建、两仓/Cloudflare发布和设备验收由游戏窗口完成；本次没有修改对方工作流或客户端代码。

累计路径需包含旧delta全部有效修复、新校订目标、当前权威剧情相对固定基础包的全部差异和新增，以及完整JS基线之后的有效产品差异。每个载荷都取同一个最新受审Git提交的字节，不能保留旧delta中对应文件的旧内容。本次快照至少489剧情＋107非剧情＝596载荷，数字不是未来上限。旧路径应保留，落后字节应替换。

包验收使用`delta_only_guard.py`：允许新delta有意覆盖固定Scenario，但最终基础包＋最新delta必须等于权威源；不能使用要求delta字节等于旧Scenario的旧验收入口。已从当前远端取回工具并校验哈希，重新运行21项反例测试，全部通过。静态反例验证不等于客户端已经实现缓存阻断或设备已验收。

**旧缓存重放、离线导入、手动重下和异步安装的防回退仍必须在客户端生产实现并实测。** 比较版本、包哈希与固定基线；拒绝旧版本、同版本异哈希、错误基线；同一资源安装事务串行；完整基线重装后最后应用当前最新累计delta；全部最终文件验证成功后才记录新版本。不能只以界面显示版本或下载成功作为验收。

全部贡献、完整清单和恢复材料只留CN patch。原工作树状态和{result['old_contribution_paths_preserved']}份贡献记录已验证保全。未知来源/确认人工稿未重新翻译。

正式接手文档：`docs/story-quality/client-integration/DELTA_ONLY_HANDOFF.md`。
一段式交接：`docs/story-quality/client-integration/PASTE_TO_GAME_WINDOW.md`。
本次原始复验：`docs/story-quality/reader-final-20261003/resume-verification.json`和`resume-live-recheck.json.gz`。
'''
    paste = f'''# 游戏窗口接手指令：只更新累计JS delta

Reader已正式采用最终校订稿，构建源码`{result['reader_source_revision']}`、部署`{result['reader_deployment_id']}`；无需再等待Reader上线，也不要从Reader抓取JSON替代客户端稿。

请实际接手`HiiragiNemu/magireco-cn-patch`既有main，先读`docs/story-quality/client-integration/DELTA_ONLY_HANDOFF.md`、`release-policy.json`和实时`READY.json`。固定内容manifest SHA-256：`{result['client_manifest_sha256']}`。361个目标/11,226条字段操作已经校订，359个有实际字节变化。按当前源逐字段合入，保留521110-9的客户端专用图片结构、人工保护及所有并行修改。

维护者要求以后游戏只更新**累计JS delta**。完整Scenario3323与完整JS103保持现有文件/版本/哈希，不共同重发。现有`publish-js-delta.yml`仍通向共同发布器，先在main适配并验证delta-only流程及客户端回退保护，再触发生产。不要直接运行旧共同发行或已停用的编号Scenario发行器。

累计delta必须保留旧修复路径并用最新同一Git提交的内容刷新，纳入新校订目标以及全部相对固定基础包变化的剧情。初步489剧情＋107非剧情＝596个载荷；保留原128补充剧情并扩展，不能仅加入新文件而留着delta内同名落后剧情。运行新鲜度/已整合检查，以及`delta_only_guard.py`全源计划和真实ZIP验收；新delta与旧Scenario不同是必要的，验收标准是基础包＋新delta最终等于最新权威源。

必须实测普通delta更新、跳版本更新、固定基础包重装后重放最新delta、离线导入、手动重下、安装中断。旧缓存21/22不能在新delta后回写；拒绝旧版本、同版本不同哈希和错误基线，安装全程串行/事务化，所有文件验证成功后才更新偏好中的版本。静态ZIP模拟不能冒称设备成功。

发包前重新获取两仓latest/Cloudflare身份和父代delta版本，遵循当前串行锁及防回退检查；仅更新新累计delta及真实引用它的元数据，所有不变完整包和无关附件保持。验收后在CN patch留下带当前manifest和政策SHA的CLIENT_RECEIPT，包含整合/构建提交、新delta版本/哈希、入口读回、基线未变证据和设备最终字节检查。不得将Reader上线或材料就绪当作游戏已发布。全部贡献和完整清单仅CN patch，不复制到Reader或公开发行仓。无分支、无PR、无强推，不清理未知本地改动。
'''
    files = {
        D + 'resume-verification.json': (OUT / 'resume-verification.json').read_bytes(),
        D + 'resume-live-recheck.json.gz': gzip.compress((OUT / 'live-recheck.json').read_bytes(), mtime=0),
        D + 'resume-delta-only-tests.log': (OUT / 'delta-only-tests.log').read_bytes(),
        D + 'resume-handoff.md': summary.encode(),
        D + 'tools/resume_final_delivery.py': (W / 'resume_final_delivery.py').read_bytes(),
        D + 'tools/finish_resumed_handoff.py': Path(__file__).read_bytes(),
        C + 'PASTE_TO_GAME_WINDOW.md': paste.encode(),
    }
    cp = commit_docs(P, files, 'reader-delivery-interruption-recovered-and-game-delta-handoff', expected={p: pt.get(p, (None, None))[1] for p in files})
    run(R, 'fetch', 'origin', 'main')
    rh = run(R, 'rev-parse', 'FETCH_HEAD').decode().strip()
    rt = tree(R, rh)
    marker = '<!-- READER-DELIVERY-RESUMED-20261003 -->'
    pointer = f'''{marker}
## 中断恢复终检完成：Reader新稿已上线，游戏仅累计delta待接手

{now}：Reader仍为`{result['reader_source_revision']}` / `{result['reader_deployment_id']}`。本次重新核验全部最终输入和新稿接口/导出/分片/搜索，结果记录于CN patch `{D}resume-handoff.md`，提交`{cp['commit']}`。没有重复部署。

客户端接手仅使用CN patch `docs/story-quality/client-integration/PASTE_TO_GAME_WINDOW.md`和`DELTA_ONLY_HANDOFF.md`、最新READY/政策。必须先适配delta-only生产路径及旧缓存/离线/重下/异步安装防回退，再发累计delta；固定完整基线，不运行旧共同重建Scenario流程。本窗口没有发布游戏包，累计清单不复制到Reader。
<!-- /READER-DELIVERY-RESUMED-20261003 -->

'''
    reader_files = {}
    for path in ['STORY_QUALITY_HANDOFF.md', 'docs/story-quality/CONTINUATION.md']:
        old = run(R, 'show', rh + ':' + path)
        assert marker.encode() not in old, 'Resume pointer already exists'
        reader_files[path] = pointer.encode() + old
    path = 'docs/story-quality/CONTINUATION_STATE.json'
    state = json.loads(run(R, 'show', rh + ':' + path))
    state['updated_at'] = now
    state['checkpoint'] = 'Reader正式新剧情已独立复验并完成接手文档；游戏361目标仍待客户端delta-only整合/防回退/发包验收'
    state['resume_final_handoff'] = {
        'status': 'reader_deployed_handoff_verified', 'canonical_repository': 'HiiragiNemu/magireco-cn-patch',
        'path': D + 'resume-handoff.md', 'commit': cp['commit'],
        'client_handoff': C + 'DELTA_ONLY_HANDOFF.md', 'client_release_policy': 'delta_only_cumulative',
        'game_package_published_by_this_task': False, 'repeated_reader_deployment': False,
        'task_id': 'tsk_22d3901ec44282ee'
    }
    reader_files[path] = enc(state)
    rc = commit_docs(R, reader_files, 'reader-final-handoff-resume-proof-pointer', expected={p:rt[p][1] for p in reader_files})
    for path, raw in files.items():
        assert run(P, 'show', cp['commit'] + ':' + path) == raw
    for path, raw in reader_files.items():
        assert run(R, 'show', rc['commit'] + ':' + path) == raw
    complete = {'patch': cp, 'reader': rc, 'game_package_published': False, 'reader_redeployed': False, 'verified_at': now, 'canonical_handoff': C + 'DELTA_ONLY_HANDOFF.md'}
    destination.write_bytes(enc(complete))
    # This is a human-readable handoff export, not a game resource bundle.
    report = handoff + '\n\n---\n\n' + summary + f'\n本次恢复终检记录提交：CN patch `{cp["commit"]}`；Reader仅交接指针 `{rc["commit"]}`。\n'
    (OUT / 'Reader_Deployed_Game_Delta_Only_Handoff_20261003.md').write_text(report, encoding='utf8')
    (OUT / 'Game_Delta_Only_Takeover_20261003.md').write_text(paste + '\n\nCN patch恢复终检提交：`' + cp['commit'] + '`。\n', encoding='utf8')
    print('HANDOFF_COMPLETED', json.dumps(complete, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
