"""Ephemeral read access for private source Git; no token in argv, files or outputs."""
import base64, os
from contextlib import contextmanager

@contextmanager
def authenticated_source_git(token, repo='HiiragiNemu/magireco-cn-patch'):
    if not token:
        yield
        return
    count=int(os.environ.get('GIT_CONFIG_COUNT','0'))
    values={'GIT_CONFIG_COUNT':str(count+1),
            'GIT_CONFIG_KEY_'+str(count):'http.https://github.com/'+repo+'/.extraheader',
            'GIT_CONFIG_VALUE_'+str(count):'AUTHORIZATION: basic '+base64.b64encode(('x-access-token:'+token).encode()).decode()}
    old={k:os.environ.get(k) for k in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
