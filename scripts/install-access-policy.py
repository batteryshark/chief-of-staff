#!/usr/bin/env python3
"""Non-live central access installer dry run. No production installation capability."""
import argparse
import json
from pathlib import Path
from access_install import dry_run,verify_bundle,activate

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('action',choices=['dry-run','verify','activate'])
p.add_argument('--manifest',type=Path)
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
try:
    if a.action=='dry-run':
        if a.manifest is None:p.error('--manifest required')
        result=dry_run(json.loads(a.manifest.read_bytes()),a.output)
    elif a.action=='verify':result=verify_bundle(a.output)
    else:result=activate(a.output)
    print(json.dumps({'candidateOnly':True,'installable':False,'runSelected':None,
        'receiptDigest':result['receiptDigest'],'roles':len(result['roles'])}))
except (ValueError,OSError) as error:
    p.exit(1,str(error)+'\n')
