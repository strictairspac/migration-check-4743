from decimal import Decimal,InvalidOperation
from datetime import datetime,timezone,timedelta
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from src.config.database import Session
from src.constants.enums import INTAKE_FIELDS,INTAKE_ITEMS_MAX
from src.models.intake import (SubmissionBatch,Checklist,ChecklistVersion,Commission,
 ResultFile,ResultItem,ResultRejection,Intake,IntakeRow)
from src.utils.serialization import record
from src.services.migration import digest

TEXT_LIMIT={'sample_code':160,'panel':80,'test_item':160,'unit':160}

def convert(value,kind,required,max_length=160):
 if value is None or (isinstance(value,str) and not value.strip()):
  if required:raise ValueError('null_required')
  return None
 if kind=='text':
  v=str(value).strip()
  if len(v)>max_length:raise ValueError('text_too_long')
  return v
 if kind=='decimal':
  try:
   d=Decimal(str(value))
   if not d.is_finite() or abs(d)>Decimal('1000000000'):raise ValueError('invalid_decimal')
   return str(d.quantize(Decimal('0.000001')))
  except (InvalidOperation,TypeError,ValueError):raise ValueError('invalid_decimal')
 if kind=='datetime':
  try:
   dt=datetime.fromisoformat(str(value))
   if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone(timedelta(hours=8)))
   return dt.astimezone(timezone.utc).isoformat(timespec='seconds')
  except (ValueError,TypeError):raise ValueError('invalid_datetime')
 raise ValueError('invalid_type')

def canonical_items(items):
 seen=[];known=set()
 for raw in items:
  item=str(raw).strip()
  if not item:raise ValueError('必检项名称不能为空')
  if len(item)>160:raise ValueError('必检项名称过长')
  if item in known:continue
  known.add(item);seen.append(item)
 if not seen or len(seen)>INTAKE_ITEMS_MAX:raise ValueError(f'必检项须为1-{INTAKE_ITEMS_MAX}个')
 return seen

# ---------- 送检批 ----------
def list_batches():
 with Session() as s:return [record(b) for b in s.query(SubmissionBatch).order_by(SubmissionBatch.id.desc())]
def save_batch(data,item_id=None):
 with Session() as s:
  row=s.get(SubmissionBatch,item_id) if item_id else SubmissionBatch()
  if not row:raise HTTPException(404,'未找到送检批')
  row.name=data.name;row.description=data.description
  s.add(row);s.commit();s.refresh(row);return record(row)

# ---------- 必检清单：组套维度、只增不改的版本 ----------
def _version_payload(v):
 return {'id':v.id,'version':v.version,'items':v.items,'note':v.note,'created_by':v.created_by,'created_at':v.created_at.isoformat() if v.created_at else None}
def _checklist_payload(s,ck):
 versions=[_version_payload(v) for v in s.query(ChecklistVersion).filter_by(checklist_id=ck.id).order_by(ChecklistVersion.version.desc())]
 current=next((v for v in versions if v['version']==ck.current_version),None)
 return {'id':ck.id,'panel':ck.panel,'current_version':ck.current_version,'current':current,'versions':versions}
def list_checklists():
 with Session() as s:return [_checklist_payload(s,ck) for ck in s.query(Checklist).order_by(Checklist.panel)]
def get_checklist(panel):
 with Session() as s:
  ck=s.query(Checklist).filter_by(panel=panel).first()
  if not ck:raise HTTPException(404,'该组套尚未维护必检清单')
  return _checklist_payload(s,ck)
def revise_checklist(panel,data,actor):
 items=canonical_items(data.items)
 with Session() as s:
  ck=s.query(Checklist).filter_by(panel=panel).with_for_update().first()
  if not ck:
   ck=Checklist(panel=panel,current_version=0);s.add(ck);s.flush()
  ck.current_version+=1
  s.add(ChecklistVersion(checklist_id=ck.id,version=ck.current_version,items=items,note=data.note,created_by=actor))
  s.commit()
  s.refresh(ck);return _checklist_payload(s,ck)
def _version_at(s,ck,version):
 return s.query(ChecklistVersion).filter_by(checklist_id=ck.id,version=version).first()
def _current_version(s,ck):
 return _version_at(s,ck,ck.current_version) if ck and ck.current_version else None

# ---------- 收件：同次送检分文件，只收转换合格项 ----------
def _resolve(raw):
 code=raw.get('委托号');panel=raw.get('组套')
 code=code.strip() if isinstance(code,str) else None
 panel=panel.strip() if isinstance(panel,str) else None
 return code,panel

def _convert_row(raw):
 target={}
 for field in INTAKE_FIELDS:
  source=field['source']
  if source not in raw:raise ValueError('missing_column:'+source)
  try:target[field['target']]=convert(raw[source],field['type'],field['required'],TEXT_LIMIT.get(field['target'],160))
  except ValueError as e:raise ValueError(field['target']+':'+str(e))
 return target

def _file_summary(s,f):
 return {**record(f),'batch_name':s.get(SubmissionBatch,f.submission_batch_id).name}

def receive_file(batch_id,data,actor):
 checksum=digest(data.rows)
 with Session() as s:
  batch=s.get(SubmissionBatch,batch_id)
  if not batch:raise HTTPException(404,'未找到送检批')
  existing=s.query(ResultFile).filter_by(submission_batch_id=batch_id,checksum=checksum).first()
  if existing:
   return dict(_file_summary(s,existing),duplicate=True,commissions=_commissions_view(s,batch))
  f=ResultFile(submission_batch_id=batch_id,filename=data.filename,checksum=checksum,total_rows=len(data.rows),received_by=actor)
  s.add(f)
  try:s.flush()
  except IntegrityError:
   s.rollback()
   existing=s.query(ResultFile).filter_by(submission_batch_id=batch_id,checksum=checksum).first()
   if not existing:raise
   return dict(_file_summary(s,existing),duplicate=True,commissions=_commissions_view(s,batch))
  seen=set();accepted=rejected=duplicate=0
  for index,raw in enumerate(data.rows,start=1):
   commission=None
   try:
    if not isinstance(raw,dict):raise ValueError('row_not_object')
    code,panel=_resolve(raw)
    if not code or not panel:raise ValueError('missing_commission_key:委托号与组套必填')
    if len(code)>160 or len(panel)>80:raise ValueError('sample_code/panel:text_too_long')
    # 先转换：只有合格行才会建立/推进委托，脏行不产生空委托
    target=_convert_row(raw)
    commission=s.query(Commission).filter_by(submission_batch_id=batch_id,sample_code=code).first()
    if commission and commission.panel!=panel:raise ValueError('panel_conflict:'+commission.panel)
    if not commission:
     try:
      with s.begin_nested():
       commission=Commission(submission_batch_id=batch_id,sample_code=code,panel=panel)
       s.add(commission);s.flush()
     except IntegrityError:
      # 并发到件时另一份文件已建同号委托，取回既有记录继续收件
      commission=s.query(Commission).filter_by(submission_batch_id=batch_id,sample_code=code).one()
      if commission.panel!=panel:raise ValueError('panel_conflict:'+commission.panel)
   except (ValueError,TypeError) as e:
    s.add(ResultRejection(file_id=f.id,commission_id=commission.id if commission else None,
     row_number=index,reason=str(e),source=raw));rejected+=1;continue
   item=target['test_item']
   if (commission.id,item) in seen or s.query(ResultItem).filter_by(commission_id=commission.id,test_item=item).first():
    duplicate+=1;continue
   seen.add((commission.id,item))
   try:
    with s.begin_nested():
     s.add(ResultItem(file_id=f.id,commission_id=commission.id,test_item=item,payload=target))
     s.flush()
   except IntegrityError:
    duplicate+=1;continue
   accepted+=1
  f.accepted_count=accepted;f.rejected_count=rejected;f.duplicate_count=duplicate
  try:s.commit()
  except IntegrityError:
   s.rollback()
   existing=s.query(ResultFile).filter_by(submission_batch_id=batch_id,checksum=checksum).first()
   if not existing:raise
   return dict(_file_summary(s,existing),duplicate=True,commissions=_commissions_view(s,batch))
  s.refresh(f)
  return dict(_file_summary(s,f),duplicate=False,commissions=_commissions_view(s,batch))

# ---------- 核算：待齐委托按当前版本实时重算 ----------
def _received_map(s,commission_ids):
 result={cid:{} for cid in commission_ids}
 if not commission_ids:return result
 for row in s.query(ResultItem).filter(ResultItem.commission_id.in_(commission_ids)):
  result[row.commission_id][row.test_item]=row.payload
 return result
def _intake_map(s,commission_ids):
 if not commission_ids:return {}
 return {i.commission_id:i for i in s.query(Intake).filter(Intake.commission_id.in_(commission_ids))}

def _commission_view(s,c,received,current_panels,intakes):
 items=received.get(c.id,{})
 intake=intakes.get(c.id)
 current=current_panels.get(c.panel)
 current_items=list(current['items']) if current else []
 if intake:
  stored=[r.test_item for r in s.query(IntakeRow).filter_by(intake_id=intake.id).order_by(IntakeRow.ordinal)]
  stored_payload=[r.payload for r in s.query(IntakeRow).filter_by(intake_id=intake.id).order_by(IntakeRow.ordinal)]
  adopted=list(intake.checklist_items)
  view={'id':c.id,'sample_code':c.sample_code,'panel':c.panel,'status':'stored',
   'received_items':list(items),'received_count':len(items),
   'checklist_version':current['version'] if current else None,'checklist_items':current_items,
   'missing_items':[i for i in current_items if i not in items],
   'extra_items':[i for i in items if i not in adopted],
   'adopted_version':intake.checklist_version,'adopted_items':adopted,'stored_items':stored,
   'missing_vs_adopted':[i for i in adopted if i not in stored],
   'intake_id':intake.id,'intake_checksum':intake.checksum,
   'verified':intake.checksum==digest(stored_payload) and all(i in stored for i in adopted)}
  return view
 missing=[i for i in current_items if i not in items]
 extra=[i for i in items if i not in current_items]
 status='no_checklist' if not current else ('ready' if not missing else 'pending')
 return {'id':c.id,'sample_code':c.sample_code,'panel':c.panel,'status':status,
  'received_items':list(items),'received_count':len(items),
  'checklist_version':current['version'] if current else None,'checklist_items':current_items,
  'missing_items':missing,'extra_items':extra,
  'adopted_version':None,'adopted_items':[],'stored_items':[],
  'missing_vs_adopted':[],'intake_id':None,'intake_checksum':None,'verified':None}

def _commissions_view(s,batch):
 commissions=s.query(Commission).filter_by(submission_batch_id=batch.id).order_by(Commission.sample_code).all()
 ids=[c.id for c in commissions]
 received=_received_map(s,ids);intakes=_intake_map(s,ids)
 panels={c.panel for c in commissions}
 panels_current={}
 if panels:
  for ck in s.query(Checklist).filter(Checklist.panel.in_(panels)):
   v=_current_version(s,ck)
   if v:panels_current[ck.panel]={'version':v.version,'items':v.items}
 return [_commission_view(s,c,received,panels_current,intakes) for c in commissions]

def batch_detail(batch_id):
 with Session() as s:
  batch=s.get(SubmissionBatch,batch_id)
  if not batch:raise HTTPException(404,'未找到送检批')
  files=[record(f) for f in s.query(ResultFile).filter_by(submission_batch_id=batch_id).order_by(ResultFile.id.desc())]
  rejections=[record(r) for r in s.query(ResultRejection).join(ResultFile,ResultRejection.file_id==ResultFile.id)
   .filter(ResultFile.submission_batch_id==batch_id).order_by(ResultRejection.id.desc()).limit(200)]
  commissions=_commissions_view(s,batch)
  summary={k:sum(1 for c in commissions if c['status']==k) for k in ('pending','ready','stored','no_checklist')}
  return {'batch':record(batch),'files':files,'rejections':rejections,'commissions':commissions,'summary':summary}

# ---------- 入库：整套只认一个版本，重试幂等 ----------
def _store_one(s,c,actor,expected_version):
 existing=s.query(Intake).filter_by(commission_id=c.id).first()
 if existing:return {'intake':record(existing),'duplicate':True,'extra_items':[]},None
 ck=s.query(Checklist).filter_by(panel=c.panel).with_for_update().first()
 version=_current_version(s,ck)
 if not version:return None,{'commission':c.sample_code,'panel':c.panel,'reason':'no_checklist','missing':[]}
 if expected_version is not None and expected_version!=version.version:
  return None,{'commission':c.sample_code,'panel':c.panel,'reason':'checklist_revised',
   'expected_version':expected_version,'version':version.version,'missing':[]}
 items=list(version.items)
 received={r.test_item:r for r in s.query(ResultItem).filter_by(commission_id=c.id).order_by(ResultItem.id)}
 missing=[i for i in items if i not in received]
 if missing:
  return None,{'commission':c.sample_code,'panel':c.panel,'reason':'incomplete','version':version.version,'missing':missing}
 ordered=[received[i] for i in items]
 payload=[r.payload for r in ordered]
 intake=Intake(commission_id=c.id,checklist_version_id=version.id,checklist_version=version.version,
  checklist_items=items,checksum=digest(payload),row_count=len(payload),created_by=actor)
 s.add(intake);s.flush()
 for ordinal,row in enumerate(ordered):
  s.add(IntakeRow(intake_id=intake.id,ordinal=ordinal,test_item=row.test_item,payload=row.payload))
 return {'intake':record(intake),'duplicate':False,
  'extra_items':[i for i in received if i not in items]},None

def _commit_store(s,commission_id,actor,expected_version):
 c=s.query(Commission).filter_by(id=commission_id).with_for_update().first()
 if not c:raise HTTPException(404,'未找到委托')
 try:
  result,skipped=_store_one(s,c,actor,expected_version)
  s.commit();return result,skipped
 except IntegrityError:
  s.rollback()
  existing=s.query(Intake).filter_by(commission_id=commission_id).first()
  if not existing:raise
  return {'intake':record(existing),'duplicate':True,'extra_items':[]},None

def store_commission(commission_id,actor,expected_version=None):
 with Session() as s:
  result,skipped=_commit_store(s,commission_id,actor,expected_version)
 if skipped:raise HTTPException(409,detail={'message':'该委托尚未满足入库条件，未写入任何行','skip':skipped})
 return result

def store_ready(batch_id,actor,expected_versions=None,only_panels=None):
 with Session() as s:
  batch=s.get(SubmissionBatch,batch_id)
  if not batch:raise HTTPException(404,'未找到送检批')
  query=s.query(Commission).filter_by(submission_batch_id=batch_id)
  if only_panels:query=query.filter(Commission.panel.in_(only_panels))
  commissions=query.order_by(Commission.sample_code).all()
  panels=sorted({c.panel for c in commissions})
  frozen={}
  for panel in panels:
   version=_current_version(s,s.query(Checklist).filter_by(panel=panel).first())
   if version:frozen[panel]=version.version
  if expected_versions:frozen={**frozen,**{k:int(v) for k,v in expected_versions.items() if k in frozen}}
  ids=[c.id for c in commissions]
 stored=[];skipped=[];duplicates=0
 for commission_id in ids:
  with Session() as s:
   panel=s.get(Commission,commission_id).panel
   result,skip=_commit_store(s,commission_id,actor,frozen.get(panel))
  if skip:skipped.append(skip)
  else:
   if result['duplicate']:duplicates+=1
   stored.append(result)
 return {'stored':stored,'skipped':skipped,'duplicates':duplicates,'versions':frozen}

# ---------- 已入库按原版核对 ----------
def intake_detail(intake_id):
 with Session() as s:
  i=s.get(Intake,intake_id)
  if not i:raise HTTPException(404,'未找到入库记录')
  rows=[record(r) for r in s.query(IntakeRow).filter_by(intake_id=i.id).order_by(IntakeRow.ordinal)]
  c=s.get(Commission,i.commission_id)
  ck=s.query(Checklist).filter_by(panel=c.panel).first()
  current=_current_version(s,ck)
  stored_items=[r['test_item'] for r in rows]
  data=record(i);data.update({'sample_code':c.sample_code,'panel':c.panel,'rows':rows,
   'verified':i.checksum==digest([r['payload'] for r in rows]) and all(x in stored_items for x in i.checklist_items),
   'current_version':current.version if current else None,
   'current_items':current.items if current else [],
   'current_missing':[x for x in (current.items if current else []) if x not in stored_items],
   'version_changed':bool(current) and current.version!=i.checklist_version})
  return data
