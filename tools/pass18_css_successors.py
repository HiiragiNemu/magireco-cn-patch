"""Exact accepted-delivery successor for historical CSS implementation assertions.

The 119 old identities and all original diagnostics remain in the main report.
This does not assert that retained CSS generated text is native DOM text, or that
each old word was separately re-reviewed. Product bytes are reconstructed from
the independent V5 source and the exact later V7 operation, not captured here as
an unproven expected=current value. No cache: a changed proof is noticed on the
next verifier call.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,re

REGISTRY='magica/i18n_audit/release_v26_authority/css_reviewed_successors_20260908/registry.json'
REGISTRY_SHA256='bcce19cce724ff8d2a1c4962b3bbc29fc54a3fffd011d146adfa4b98c2749e15'

def digest(b):return hashlib.sha256(b).hexdigest()
def confined(root,rel):
    root=Path(root).resolve();p=(root/rel).resolve()
    if not p.is_relative_to(root):raise ValueError('proof path escapes product root')
    return p

def contract(root):
    root=Path(root);b=confined(root,REGISTRY).read_bytes()
    if digest(b)!=REGISTRY_SHA256:raise ValueError('CSS registry pin drift')
    r=json.loads(b);sources={}
    if r['schema']!='pass18-css-reviewed-successors/v1':raise ValueError('schema drift')
    for key,p in r['proofs'].items():
        raw=confined(root,p['path']).read_bytes()
        if digest(raw)!=p['sha256'] or len(raw)!=p['bytes']:raise ValueError('source proof pin drift: '+key)
        sources[key]=raw
    for key,p in r['historicalPaths'].items():
        if digest(confined(root,p['path']).read_bytes())!=p['sha256']:raise ValueError('historical source drift: '+key)
    acceptance=json.loads(sources['overallAcceptance'])
    if acceptance.get('acceptedBaseline')!='DEVICE2_V5' or acceptance.get('acceptanceClarification')!=r['acceptanceScope']['sourceClarificationExact']:raise ValueError('overall acceptance scope drift')
    d=r['denominator']
    if (d['css'],d['historicalPseudoIds'],d['generatedOldFindings'],d['historyBaseline'])!=(44,119,28,19):raise ValueError('denominator drift')
    files=r['cssFiles'];paths=[x['path'] for x in files]
    actual={p.relative_to(root).as_posix() for p in (root/'magica/css').rglob('*.css') if p.is_file()}
    if len(paths)!=44 or len(set(paths))!=44 or actual!=set(paths):raise ValueError('CSS file identity set drift')
    v7={x['path']:x for x in json.loads(sources['v7Patch'])['files']}
    receipt=json.loads(sources['v5CssMemberReceipt'])
    memberRows={x['path']:x for x in receipt['rows']}
    if len(memberRows)!=44 or receipt['recordedArchiveSha256']!=json.loads(sources['v5Build'])['sha256']:raise ValueError('V5 archive receipt binding drift')
    if json.loads(sources['v5Verification'])['sourceCommit']!=r['acceptanceScope']['sourceCommit']:raise ValueError('V5 source commit binding drift')
    for row in files:
        if row['sourceProof']!='v5Css:'+row['path']:raise ValueError('wrong accepted CSS source path')
        base=sources[row['sourceProof']]
        if digest(base)!=row['sourceSha256']:raise ValueError('V5 source identity drift: '+row['path'])
        member=memberRows[row['path']]
        if member['memberSha256']!=digest(base) or member['sourceSha256']!=digest(base) or member['equal'] is not True:raise ValueError('V5 member/source mismatch')
        expected=base;op=row['operation']
        if op is not None:
            if op!=v7[row['path']]['sourceExactOperation'] or op['operation']!='APPEND_EXACT' or digest(base)!=op['beforeSha256']:raise ValueError('V7 source/operation drift')
            expected=base+op['exactAppend'].encode('utf-8')
            if digest(expected)!=op['afterSha256']:raise ValueError('V7 target pin drift')
        if digest(expected)!=row['authorizedAfterSha256']:raise ValueError('authorized target pin drift')
        if confined(root,row['path']).read_bytes()!=expected:raise ValueError('unregistered CSS target drift: '+row['path'])
    device=json.loads(sources['v5Device'])['rows'];by={x['path']:x for x in files}
    deviceCss=[x for x in device if x['path'].endswith('.css')]
    if len(deviceCss)!=5:raise ValueError('V5 device CSS receipt denominator drift')
    for x in deviceCss:
        if by[x['path']]['sourceSha256']!=x['after']:raise ValueError('accepted V5 device source mismatch')
    old=json.loads(sources['history:ROUND3_VISIBLE_MANIFEST']);oldItems=[x for x in old['items'] if x['path'].endswith('.css')]
    ids=r['historicalIds']
    if len(ids)!=119 or len({x['itemId'] for x in ids})!=119 or [x['original'] for x in ids]!=oldItems:raise ValueError('historical stable ID/source/order drift')
    for x in ids:
        if x['itemId']!=x['original']['item_id'] or x['authorizedStylePath']!=x['original']['path'] or x['sourceProof']!='v5Css:'+x['original']['path']:raise ValueError('wrong CSS identity/source binding')
    for x in r['nativeCues']:
        raw=sources[x['snapshotProof']]
        if digest(raw)!=x['sha256']:raise ValueError('native cue pin drift')
        if x['acceptedV5Exact'] and confined(root,x['path']).read_bytes()!=raw:raise ValueError('accepted native source drift: '+x['path'])
    if len(r['generatedFindings'])!=28:raise ValueError('generated denominator drift')
    for g in r['generatedFindings']:
        css=confined(root,g['path']).read_text(encoding='utf-8')
        rules=[body for selector,body in re.findall(r'([^{}]+)\{([^{}]*)\}',re.sub(r'/\*.*?\*/','',css,flags=re.S)) if selector.strip()==g['selector']]
        values=[v for rule in rules for _,v in re.findall(r'''content\s*:\s*(["'])(.*?)(?<!\\)\1''',rule,re.S)]
        if g['value'] not in values:raise ValueError('generated stable selector/target drift')
    oldRound4=json.loads(sources['history:ROUND4_MANIFEST'])
    fields=r['round4Fields'];originalFields=[x for x in oldRound4['changes'] if not x['file'].endswith('.css')]
    if len(fields)!=37 or [x['original'] for x in fields]!=originalFields:raise ValueError('round4 original37 identity/source drift')
    if sum(x['isLaterSuccessor'] for x in fields)!=30:raise ValueError('round4 reviewed successor denominator drift')
    dictionaries={}
    for x in fields:
        old=x['original'];rel=old['file'];key=x['keyField']
        if key!={'cardList.json':'cardId','eventStoryList.json':'storyIds','pieceList.json':'pieceId','sectionList.json':'sectionId'}[Path(rel).name] or x['sourceProof']!='v5Dictionary:'+rel:raise ValueError('round4 source-kind identity drift')
        if rel not in dictionaries:dictionaries[rel]=(json.loads(sources[x['sourceProof']]),json.loads(confined(root,rel).read_bytes()))
        source,current=dictionaries[rel]
        src=[v for v in source if str(v.get(key))==str(old['key'])]
        now=[v for v in current if str(v.get(key))==str(old['key'])]
        if len(src)!=1 or len(now)!=1:raise ValueError('round4 stable ID missing or duplicate')
        if src[0]!=x['sourceObject'] or src[0].get(old['field'])!=x['authorizedValue']:raise ValueError('round4 complete source object/field binding drift')
        if x['isLaterSuccessor']!=(x['authorizedValue']!=old['after']):raise ValueError('round4 old/new disposition drift')
        if now[0].get(old['field'])!=x['authorizedValue']:raise ValueError('round4 unregistered exact target drift: '+old['item_id'])
    return r

def verify(root):
    try:
        r=contract(root)
        return {'ok':True,'acceptedIds':[x['itemId'] for x in r['historicalIds']],'acceptedCssFiles':44,'oldPseudoIdsPreserved':119,'oldGeneratedFindingsRetainedByExactSource':28,'round4NonCssIdsPreserved':37,'round4FieldSuccessors':30,'perItemHumanReviewClaim':False,'acceptanceBaseline':'DEVICE2_V5 plus explicit V7 font-only operations','nativeContextCues':len(r['nativeCues']),'errors':[]}
    except (OSError,ValueError,KeyError,TypeError,AssertionError) as e:
        return {'ok':False,'acceptedIds':[],'errors':[str(e)]}

def accept_manual(root,relative):
    try:return relative in {x['target'] for x in contract(root)['manualCss']}
    except (OSError,ValueError,KeyError,TypeError):return False

def accept_connect(root,record):
    if not str(record.get('product_path','')).endswith('.css'):return False
    try:return record in contract(root)['connectCss']
    except (OSError,ValueError,KeyError,TypeError):return False

def accept_round4(root,entry,rows):
    try:
        r=contract(root);wanted=[x for x in r['round4Css'] if x['file']==entry['target']]
        return entry['kind']=='css' and bool(wanted) and rows==wanted and entry['item_ids']==[x['item_id'] for x in wanted]
    except (OSError,ValueError,KeyError,TypeError):return False

def reviewed_round4_targets(root,entry,rows):
    try:
        r=contract(root);fields=[x for x in r['round4Fields'] if x['original']['file']==entry['target']]
        if not fields or rows!=[x['original'] for x in fields] or entry['item_ids']!=[x['original']['item_id'] for x in fields]:return {}
        return {(x['original']['item_id'],str(x['original']['key']),x['original']['field']):x['authorizedValue'] for x in fields if x['isLaterSuccessor']}
    except (OSError,ValueError,KeyError,TypeError):return {}

def accept_frozen(root,finding):
    try:
        rows=contract(root)['frozen6']
        return any(finding['path']==x['path'] and finding['baseline_blob']==x['baseline_blob'] and finding['current_filtered_blob']==x['current_filtered_blob'] for x in rows)
    except (OSError,ValueError,KeyError,TypeError):return False

def unregistered_generated(root,findings):
    try:allowed=Counter((x['path'],x['value']) for x in contract(root)['generatedFindings'])
    except (OSError,ValueError,KeyError,TypeError):return findings
    failed=[]
    for x in findings:
        key=(x['path'],x['value'])
        if allowed[key]>0:allowed[key]-=1
        else:failed.append(x)
    return failed
