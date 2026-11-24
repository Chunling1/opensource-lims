"""Contract + all children + exact-key reference fields, one immutable event."""
import copy
import hashlib
import json
import re

KIND='contract_bundle_v2'
FIELDS={'contractNo','sourceKey','departmentCode','dept','businessCategoryCode','businessCategory'}


def compact(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(v):return hashlib.sha256(compact(v).encode('utf-8')).hexdigest()


def text(row,key,limit=500):
    v=row.get(key)
    if v is None:return ''
    if not isinstance(v,str) or len(v)>limit or any(ord(c)<32 for c in v):raise ValueError('BUNDLE_FIELD_TYPE')
    return v.strip()


def parents(raw):
    if not isinstance(raw,dict) or raw.get('bizFlag')!='business_project':raise ValueError('BUNDLE_RAW_TYPE')
    content=raw.get('content')
    data=content.get('data') if isinstance(content,dict) else None
    data=[data] if isinstance(data,dict) else data
    if not isinstance(data,list) or not 1<=len(data)<=100:raise ValueError('BUNDLE_PARENTS')
    result={}
    for p in data:
        if not isinstance(p,dict):raise ValueError('BUNDLE_PARENT_TYPE')
        no=text(p,'billno',200)
        if not no or no in result:raise ValueError('BUNDLE_CONTRACT_KEY')
        children=p.get('subitem_list')
        if not isinstance(children,list) or len(children)>2000:raise ValueError('BUNDLE_CHILDREN')
        keys=set();codes=set()
        for c in children:
            if not isinstance(c,dict):raise ValueError('BUNDLE_CHILD_TYPE')
            key=text(c,'unique_code',160);code=text(c,'unitprojectnumber',120)
            if not key or not code or not text(c,'unitprojectname') or key in keys or code in codes:
                raise ValueError('BUNDLE_CHILD_KEY')
            keys.add(key);codes.add(code)
        result[no]=p
    return result


def effective(bundle):
    required={'bizFlag','stream','sequence','mode','contractNos','baseEventId','rawPayload','referenceRows'}
    if not isinstance(bundle,dict) or set(bundle)!=required or bundle['bizFlag']!=KIND:
        raise ValueError('BUNDLE_PROTOCOL')
    if not isinstance(bundle['stream'],str) or not re.fullmatch('[0-9a-f]{32}',bundle['stream']):raise ValueError('BUNDLE_STREAM')
    if type(bundle['sequence']) is not int or not 0<=bundle['sequence']<2**63:raise ValueError('BUNDLE_SEQUENCE')
    ps=parents(bundle['rawPayload']);nos=bundle['contractNos']
    if not isinstance(nos,list) or not nos or any(not isinstance(n,str) for n in nos) or len(nos)!=len(set(nos)) or not set(nos)<=set(ps):
        raise ValueError('BUNDLE_CONTRACTS')
    if bundle['mode']=='event':
        if len(nos)!=1 or bundle['sequence']<1 or bundle['baseEventId']!='':raise ValueError('BUNDLE_EVENT')
    elif bundle['mode']=='repair':
        if len(nos)!=1 or bundle['sequence']!=0 or not re.fullmatch('[0-9a-f]{64}',bundle['baseEventId'] or ''):raise ValueError('BUNDLE_REPAIR')
    else:raise ValueError('BUNDLE_MODE')
    refs=bundle['referenceRows']
    if not isinstance(refs,list) or len(refs)>20000:raise ValueError('BUNDLE_REFERENCES')
    lookup={}
    for ref in refs:
        if not isinstance(ref,dict) or set(ref)!=FIELDS or any(not isinstance(ref[k],str) or text(ref,k)!=ref[k] for k in FIELDS):
            raise ValueError('BUNDLE_REFERENCE_FIELDS')
        key=(ref['contractNo'],ref['sourceKey'])
        if key in lookup:raise ValueError('BUNDLE_REFERENCE_DUPLICATE')
        lookup[key]=ref
    result=copy.deepcopy(bundle['rawPayload']);out=[];used=set()
    for no in nos:
        parent=copy.deepcopy(ps[no])
        for child in parent['subitem_list']:
            key=(no,text(child,'unique_code'));ref=lookup.get(key)
            if not ref:raise ValueError('BUNDLE_REFERENCE_NOT_READY')
            used.add(key)
            for code,label,rc,rl in [('responsibleorg','responsibleorg_name','departmentCode','dept'),
                ('zjjt_subclassifythree','zjjt_subclassifythree_name','businessCategoryCode','businessCategory')]:
                if not text(child,code) or text(child,code)!=ref[rc]:raise ValueError('BUNDLE_REFERENCE_CODE_MISMATCH')
                old=text(child,label);new=ref[rl]
                if old and new and old!=new:raise ValueError('BUNDLE_REFERENCE_NAME_CONFLICT')
                if not (old or new):raise ValueError('BUNDLE_REFERENCE_NAME_MISSING')
                child[label]=old or new
        out.append(parent)
    if set(lookup)!=used:raise ValueError('BUNDLE_CHILD_SET_NOT_READY')
    result['content']['data']=out
    return result


def build(raw,refs,stream,sequence,mode='event',base='',nos=None):
    value=dict(bizFlag=KIND,stream=stream,sequence=sequence,mode=mode,baseEventId=base,
        contractNos=nos or list(parents(raw)),rawPayload=raw,referenceRows=refs)
    effective(value)
    if len(compact(value).encode('utf-8'))>18*1024*1024:raise ValueError('BUNDLE_SIZE')
    return value
