"""Quality roster Excel exchange. No changes to functional/project appointments."""
import hashlib
import json
import re
import zipfile
from io import BytesIO
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from ..extensions import db
from ..models import Department, Personnel, User
from ..platform.identity import personnel_login, update_personnel_login
from ..platform.audit import add_operation_audit

HEADERS=['姓名','人员编号/账号','所在部门','岗位/职务','职称/资格','账号状态','流程权限']
LABELS={'委托登记','样品登记','合同评审','样品入出库','数据录入','校核','审核','批准','打印发放','原始记录审核'}


def export_roster(rows):
    book=Workbook()
    sheet=book.active
    sheet.title='人员登记'
    sheet.append(HEADERS)
    for row in rows:
        values=[row.get(k) or '' for k in ('name','code','dept','position','title','accountStatus')]
        values.append(';'.join(row.get('permissions') or []))
        sheet.append(values)
        for cell in sheet[sheet.max_row]: cell.data_type='s'
    sheet.freeze_panes='A2'
    sheet.auto_filter.ref=sheet.dimensions
    for i,width in enumerate([18,24,30,24,24,18,40],1):
        sheet.column_dimensions[chr(64+i)].width=width
        sheet.column_dimensions[chr(64+i)].number_format='@'
    for c in sheet[1]:
        c.font=Font(bold=True,color='FFFFFF')
        c.fill=PatternFill('solid',fgColor='2864D7')
    for row in sheet:
        for c in row: c.alignment=Alignment(vertical='top',wrap_text=True)
    note=book.create_sheet('说明')
    for value in [
        '人员登记导入说明（主表表头不得修改）',
        '人员编号/账号按大小写不敏感唯一匹配；同编号姓名不同、重复编号、未知部门整表拒绝。',
        '只更新表中人员，不删除表外人员；同格式导出文件可再次导入。',
        '账号状态：已启用、已停用、未创建账号。新账号须明确填已启用或已停用；已存在账号不可改成未创建账号。',
        '新账号沿用首次登录改密规则；现有账号密码、实名绑定不修改。',
        '流程权限为人员档案历史标签，用半角分号分隔；不是实际功能或项目授权，不会新授予审核、批准。',
        '正式功能/项目权限请用组织机构的权限模板与Excel维护。跨部门调整沿用部门上限收敛规则。',
        '导入先预检，确认后单事务保存；校验失败全部不写入。'
    ]: note.append([value])
    note.column_dimensions['A'].width=110
    for row in note:
        row[0].alignment=Alignment(wrap_text=True,vertical='top')
    stream=BytesIO(); book.save(stream); stream.seek(0)
    return stream


def parse_roster(content):
    if len(content)>5*1024*1024: raise ValueError('Excel不能超过5MB')
    try:
        with zipfile.ZipFile(BytesIO(content)) as z:
            if sum(m.file_size for m in z.infolist())>25*1024*1024 or len(z.infolist())>100:
                raise ValueError('Excel解压内容过大')
        book=load_workbook(BytesIO(content),read_only=True,data_only=False,keep_links=False)
    except ValueError: raise
    except Exception as exc: raise ValueError('文件不是有效的xlsx工作簿') from exc
    try:
        if '人员登记' not in book.sheetnames: raise ValueError('缺少“人员登记”工作表，请使用本页导出的格式')
        sheet=book['人员登记']
        if sheet.max_row>5001 or sheet.max_column!=7: raise ValueError('最多5000条人员，且必须为7列表头')
        iterator=sheet.iter_rows()
        if [c.value for c in next(iterator)]!=HEADERS: raise ValueError('表头不一致，请使用人员登记导出文件或模板')
        rows=[]
        for rowno,cells in enumerate(iterator,2):
            if all(c.value is None or c.value=='' for c in cells): continue
            if any(c.data_type=='f' for c in cells): raise ValueError(f'第{rowno}行不允许公式，请填写文本值')
            values=[]
            for i,c in enumerate(cells):
                if c.value is not None and not isinstance(c.value,str): raise ValueError(f'第{rowno}行“{HEADERS[i]}”必须为文本')
                values.append((c.value or '').strip())
            rows.append(dict(zip(['name','code','dept','position','title','accountStatus','permissions'],values),row=rowno))
        if not rows: raise ValueError('主表没有可导入的人员')
        return rows
    finally: book.close()


def plan_roster(content,visible_departments):
    rows=parse_roster(content)
    departments={}
    for d in Department.query.all(): departments.setdefault(d.name,[]).append(d)
    people={}
    for p in Personnel.query.filter_by(deleted_at=None).all(): people.setdefault((p.code or '').strip().lower(),[]).append(p)
    users={}
    for u in User.query.all(): users.setdefault(u.account.strip().lower(),[]).append(u)
    errors=[]; planned=[]; seen=set(); states=[]
    for row in rows:
        key=row['code'].lower(); found=people.get(key,[]); accounts=users.get(key,[]); depts=departments.get(row['dept'],[])
        problems=[]
        if not re.fullmatch(r'[A-Za-z0-9_.-]{2,40}',row['code']): problems.append('人员编号格式不合法')
        if not row['name'] or len(row['name'])>40: problems.append('姓名为空或超过40字')
        if len(row['position'])>80 or len(row['title'])>80: problems.append('岗位或职称超过80字')
        if key in seen: problems.append('文件内人员编号重复')
        seen.add(key)
        if len(found)>1 or len(accounts)>1: problems.append('系统中存在重复编号，须先处理')
        if len(depts)!=1: problems.append('所属部门不存在或不唯一')
        if any((p.name or '').strip()!=row['name'] for p in found) or any(u.name.strip()!=row['name'] for u in accounts):
            problems.append('编号对应姓名不一致，不会覆盖已有人员')
        if visible_departments is not None:
            if row['dept'] not in visible_departments or any(p.dept not in visible_departments for p in found) or any(u.department and u.department.name not in visible_departments for u in accounts):
                problems.append('人员或目标部门不在可管理范围')
        if row['accountStatus'] not in {'已启用','已停用','未创建账号'}: problems.append('账号状态仅可填写已启用/已停用/未创建账号')
        if accounts and row['accountStatus']=='未创建账号': problems.append('已关联账号不能解除或删除')
        labels=[x.strip() for x in re.split(r'[;；]',row['permissions']) if x.strip()]
        existing_labels={x for p in found for x in (p.permissions or '').split(';') if x}
        if len(labels)!=len(set(labels)) or set(labels)-(LABELS|existing_labels): problems.append('流程标签重复或未知')
        for problem in problems: errors.append({'row':row['row'],'code':row['code'],'message':problem})
        if problems: continue
        person=found[0] if found else None; user=accounts[0] if accounts else None
        # Include all scope-bearing state in preflight token. Never return passwords/bindings.
        states.append({'p':person.to_row(full=True) if person else None,'u':{'id':user.id,'name':user.name,'dept':user.department_id,'enabled':user.enabled,'permissions':user.permission_codes(),'steps':sorted(s.id for s in user.project_steps)} if user else None,'department':{'id':depts[0].id,'permissions':sorted(p.code for p in depts[0].permissions),'steps':sorted(s.id for s in depts[0].project_steps)}})
        planned.append({'row':row,'person':person,'user':user,'department':depts[0],'labels':labels})
    token=hashlib.sha256(content+json.dumps(states,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
    summary={'total':len(rows),'createPersonnel':sum(p['person'] is None for p in planned),'updatePersonnel':sum(p['person'] is not None for p in planned),
        'createAccounts':sum(p['user'] is None and p['row']['accountStatus']!='未创建账号' for p in planned),
        'departmentMoves':sum(p['user'] is not None and p['user'].department_id!=p['department'].id for p in planned),
        'errors':errors,'valid':not errors,'previewToken':token,'formalPermissionsReplaced':False}
    return planned,summary


def apply_roster(actor,planned):
    for item in planned:
        row,p,u,d=item['row'],item['person'],item['user'],item['department']
        before=p.to_row() if p else None
        if p is None:
            p=Personnel(code=row['code'])
            db.session.add(p)
        # Account identifier is stable, including original casing on existing users.
        if u is not None:
            update_personnel_login(actor,u,name=row['name'],department=d,enabled=row['accountStatus']=='已启用')
            p.code=u.account
        elif row['accountStatus']!='未创建账号':
            u,_=personnel_login(actor,account=p.code,name=row['name'],department_name=d.name,enabled=row['accountStatus']=='已启用')
        p.name=row['name']; p.dept=d.name
        if before is None or before.get('dept')!=d.name: p.assigned_depts=d.name
        p.position=row['position']; p.title=row['title']; p.permissions=';'.join(item['labels'])
        db.session.flush()
        add_operation_audit('quality.personnel.import','personnel',p.id,before=before,after=p.to_row(),message='人员Excel导入，保留正式功能及项目权限；部门调整按现行规则收敛')
