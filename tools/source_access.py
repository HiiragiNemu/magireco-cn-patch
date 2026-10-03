"""Ephemeral read access for private source Git; no token in argv, files or outputs."""
import base64, os
from contextlib import contextmanager

@contextmanager
def authenticated_source_git(token, repo='HiiragiNemu/magireco-cn-patch'):
    if not token:
        yield
        return
    count=int(os.environ.get('GIT_CONFIG_COUNT','0'))
    values={'GIT_CONFIG_COUNT':str(count+2)}
    credential='AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode()
    # Git requires a path-component match: /repo/ does not match /repo.git.
    for offset,suffix in enumerate(('', '.git')):
        i=str(count+offset)
        values['GIT_CONFIG_KEY_'+i]='http.https://github.com/'+repo+suffix+'.extraheader'
        values['GIT_CONFIG_VALUE_'+i]=credential
    old={k:os.environ.get(k) for k in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
