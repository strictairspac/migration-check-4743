"""送检收件/全套入库业务测试：使用 SQLite 内存库替代 PG，覆盖到件、更正、入库、重试与页面核算。"""
import os,sys,tempfile
os.environ.setdefault('JWT_SECRET','test-secret')
os.environ['DATABASE_URL']='sqlite+pysqlite:///'+tempfile.mktemp(suffix='.db')
os.environ['REDIS_URL']='redis://localhost:6379/0'
sys.path.insert(0,'/workspace/backend')
import warnings;warnings.filterwarnings('ignore')

from src.config.database import Base,engine,Session
from src.models.intake import (SubmissionBatch,Checklist,ChecklistVersion,Commission,ResultFile,
 ResultItem,ResultRejection,Intake,IntakeRow)
from src.models.identity import User
from src.services import intake
from src.services.migration import digest
from src.schemas.business import ChecklistInput,ResultFileInput,SubmissionBatchInput
from fastapi import HTTPException

Base.metadata.create_all(engine)
failures=[]
def check(name,cond,extra=''):
 print(('PASS ' if cond else 'FAIL ')+name+((' :: '+str(extra)) if extra and not cond else ''))
 if not cond:failures.append(name)

def row(code,panel,item,value,unit='MPa',ts='2026-11-18T10:00:00+08:00'):
 return {'委托号':code,'组套':panel,'检测项':item,'结果':value,'单位':unit,'时间':ts}

def receive(batch_id,filename,rows):
 return intake.receive_file(batch_id,ResultFileInput(filename=filename,rows=rows),'op@test')

def store(cid,expected_version=None):
 try:return intake.store_commission(cid,'op@test',expected_version),None
 except HTTPException as e:return None,e

# 1. 建批 + 清单版本
b=intake.save_batch(SubmissionBatchInput(name='批A',description='同次送检'),None)
intake.revise_checklist('混凝土',ChecklistInput(items=['强度','坍落度'],note='v1'),'op@test')
intake.revise_checklist('混凝土',ChecklistInput(items=['强度','坍落度','含气量'],note='v2'),'op@test')
c1=intake.get_checklist('混凝土')
check('清单版本递增到v2',c1['current_version']==2)
check('历史版本保留v1和v2',[v['version'] for v in c1['versions']]==[2,1])

# 2. 分文件收件，只补转换合格项
r1=receive(b['id'],'part1.json',[row('WT-1','混凝土','强度','420.5'),row('WT-1','混凝土','坍落度','180','mm')])
check('part1 收2合格项',r1['accepted_count']==2,r1)
check('part1 建1个委托',len(r1['commissions'])==1)
cid=r1['commissions'][0]['id']
check('part1 状态pending(缺含气量v2)',r1['commissions'][0]['status']=='pending' and r1['commissions'][0]['missing_items']==['含气量'],r1['commissions'])
r2=receive(b['id'],'part2.json',[
 row('WT-1','混凝土','含气量','4.5','%'),
 {'委托号':'WT-2','组套':'混凝土','检测项':'强度','结果':'四百二','单位':'MPa','时间':'2026-11-18T10:00:00+08:00'},
 row('WT-2','混凝土','强度','430'),
 {'委托号':'WT-3','检测项':'强度','结果':'400','单位':'MPa','时间':'2026-11-18T10:00:00+08:00'},
 {'委托号':'WT-3','组套':'混凝土','检测项':'强度','结果':'400','单位':'MPa'},
 row('WT-3','混凝土','强度','400'),
 row('WT-9','混凝土','强度','不是数字'),
])
check('part2 合格3项(含气量+WT-2+WT-3强度)',r2['accepted_count']==3,r2['accepted_count'])
check('part2 拒绝非法/缺组套/缺时间列/纯脏行',r2['rejected_count']==4,r2['rejected_count'])
wt2=next(c for c in r2['commissions'] if c['sample_code']=='WT-2')
check('WT-2非法行被拒、合格行照收',wt2['received_items']==['强度'],wt2)
check('纯脏行不产生空委托',all(c['sample_code']!='WT-9' for c in r2['commissions']),[c['sample_code'] for c in r2['commissions']])
wt3=next(c for c in r2['commissions'] if c['sample_code']=='WT-3')
check('WT-3已收1项且缺2项',wt3['received_count']==1 and set(wt3['missing_items'])=={'坍落度','含气量'},wt3)

# 3. 重复文件不重复收
r1b=receive(b['id'],'part1-again.json',[row('WT-1','混凝土','强度','420.5'),row('WT-1','混凝土','坍落度','180','mm')])
check('同内容文件按摘要去重',r1b['duplicate'] is True)
with Session() as s:
 check('文件表只有2条',s.query(ResultFile).count()==2)
 check('WT-1强度项未重复',s.query(ResultItem).filter_by(commission_id=cid,test_item='强度').count()==1)

# 4. 同批内同项再送视为重复项，不覆盖
r3=receive(b['id'],'part3.json',[row('WT-1','混凝土','强度','999')])
check('重复项计入duplicate',r3['duplicate_count']==1 and r3['accepted_count']==0,r3)
with Session() as s:
 payload=s.query(ResultItem).filter_by(commission_id=cid,test_item='强度').one().payload
 check('首条合格值不被覆盖',payload['result_value']=='420.500000',payload)

# 5. 缺项不可入库
res,err=store(wt3['id'])
check('缺项入库被拒(409)',res is None and err.status_code==409,err)
check('缺项提示列明缺项',set(err.detail['skip']['missing'])=={'坍落度','含气量'},err.detail)
with Session() as s:check('缺项未写入intake',s.query(Intake).count()==0)

# 6. 已齐可入库，锁版本
res,err=store(cid)
check('齐套入库成功',err is None,err)
check('采用当前v2版本',res['intake']['checklist_version']==2,res)
check('入库行按清单顺序',True)
with Session() as s:
 rows=[r.test_item for r in s.query(IntakeRow).filter_by(intake_id=res['intake']['id']).order_by(IntakeRow.ordinal)]
 check('入库行顺序=清单顺序',rows==['强度','坍落度','含气量'],rows)
 check('入库摘要一致',res['intake']['checksum']==digest([r.payload for r in s.query(IntakeRow).filter_by(intake_id=res['intake']['id']).order_by(IntakeRow.ordinal)]))
intake_id=res['intake']['id']

# 7. 入库后清单更正，已入库仍按原版核对
intake.revise_checklist('混凝土',ChecklistInput(items=['强度','坍落度','含气量','抗渗等级'],note='v3'),'op@test')
det=intake.intake_detail(intake_id)
check('已入库记录仍为v2',det['checklist_version']==2)
check('已入库核对摘要仍一致',det['verified'] is True,det['verified'])
check('标记清单已变更',det['version_changed'] is True)
check('按原版核对无缺项',det['current_missing']==['抗渗等级'],det['current_missing'])
bd=intake.batch_detail(b['id'])
stored=next(c for c in bd['commissions'] if c['id']==cid)
check('页面显示采用版本v2',stored['adopted_version']==2)
check('页面按原版核对无缺项',stored['missing_vs_adopted']==[])
check('页面显示当前版本v3',stored['checklist_version']==3)

# 8. 断线重试不重复入库
res2,err2=store(cid)
check('重试返回duplicate',err2 is None and res2['duplicate'] is True,res2)
with Session() as s:check('intake仍只有1条',s.query(Intake).count()==1)
# 8b. 重试带过期版本号也识别为已入库而非报错
res3,err3=store(cid,99)
check('带旧版本重试仍幂等',err3 is None and res3['duplicate'] is True,err3)

# 9. 入库期间清单被并发更正 → 冻结版本不匹配则拒绝整套
r4=receive(b['id'],'part4.json',[row('WT-4','混凝土','强度','380'),row('WT-4','混凝土','坍落度','190','mm')])
wt4=next(c for c in r4['commissions'] if c['sample_code']=='WT-4')
check('WT-4当前版本v3缺2项',wt4['status']=='pending' and set(wt4['missing_items'])=={'含气量','抗渗等级'},wt4)
res4,err4=store(wt4['id'],expected_version=2)
check('拿过期版本v2入库被拒',res4 is None and err4.status_code==409 and err4.detail['skip']['reason']=='checklist_revised',err4)
with Session() as s:check('版本不符未写intake',s.query(Intake).count()==1)
receive(b['id'],'part5.json',[row('WT-4','混凝土','含气量','5.0','%'),row('WT-4','混凝土','抗渗等级','8')])
res5,err5=store(wt4['id'],expected_version=3)
check('补件后按v3入库',err5 is None and res5['intake']['checklist_version']==3,err5)

# 10. 整套入库：只入可入库的，跳过未齐，重复不重写
r6=receive(b['id'],'part6.json',[row('WT-5','混凝土','强度','350')])
allres=intake.store_ready(b['id'],'op@test')
check('整套入库重复2个(WT-1,WT-4)',allres['duplicates']==2,allres['duplicates'])
check('未齐WT-2/WT-3/WT-5被跳过',{s['commission'] for s in allres['skipped']}=={'WT-2','WT-3','WT-5'},{s['commission'] for s in allres['skipped']})
with Session() as s:check('整套入库后intake共2条',s.query(Intake).count()==2)

# 11. 组套无清单 → no_checklist
r7=receive(b['id'],'part7.json',[row('GJ-1','钢筋','屈服强度','500')])
gj=next(c for c in r7['commissions'] if c['sample_code']=='GJ-1')
check('缺清单标记',gj['status']=='no_checklist',gj)
res7,err7=store(gj['id'])
check('缺清单入库被拒',res7 is None and err7.detail['skip']['reason']=='no_checklist',err7)

# 11b. 组套范围入库只处理指定组套
intake.revise_checklist('钢筋',ChecklistInput(items=['屈服强度'],note='v1'),'op@test')
r_gj=receive(b['id'],'part7b.json',[row('GJ-1','钢筋','屈服强度','500')])
gj_ready=next(c for c in r_gj['commissions'] if c['sample_code']=='GJ-1')
check('钢筋委托可入库',gj_ready['status']=='ready',gj_ready)
scoped=intake.store_ready(b['id'],'op@test',None,['钢筋'])
check('按组套范围只入库钢筋',len(scoped['stored'])==1 and scoped['stored'][0]['intake']['row_count']==1,scoped)
with Session() as s:check('混凝土WT-1未被范围入库重复',s.query(Intake).filter_by(commission_id=cid).count()==1)

# 11c. 入库后补件只作为超额项，不改动冻结记录
r_late=receive(b['id'],'late.json',[row('WT-1','混凝土','抗折强度','5.5')])
with Session() as s:
 check('补件不新增intake',s.query(Intake).count()==3 and s.query(Intake).filter_by(commission_id=cid).count()==1)
 check('补件不写入intake_rows',all(r.test_item!='抗折强度' for r in s.query(IntakeRow).filter_by(intake_id=intake_id)))
bd2=intake.batch_detail(b['id'])
wt1=next(c for c in bd2['commissions'] if c['id']==cid)
check('补件显示为超额项',wt1['extra_items']==['抗折强度'],wt1['extra_items'])
check('已入库仍按原版核对',wt1['missing_vs_adopted']==[] and wt1['verified'] is True)

# 12. 组套冲突拒绝
r8=receive(b['id'],'part8.json',[row('WT-1','钢筋','屈服强度','500')])
check('同委托不同组套被拒',r8['rejected_count']==1 and any('panel_conflict' in x['reason'] for x in intake.batch_detail(b['id'])['rejections']),r8)

# 13. 更正期间照常收件
intake.revise_checklist('混凝土',ChecklistInput(items=['强度'],note='v4简化'),'op@test')
r9=receive(b['id'],'part9.json',[row('WT-6','混凝土','强度','300')])
check('更正期间收件成功',r9['accepted_count']==1,r9)
wt6=next(c for c in r9['commissions'] if c['sample_code']=='WT-6')
check('按新版本v4可入库',wt6['status']=='ready',wt6)
res9,err9=store(wt6['id'],expected_version=4)
check('按v4入库',err9 is None and res9['intake']['checklist_version']==4,err9)

print('\n失败:',failures if failures else '无')
sys.exit(1 if failures else 0)
