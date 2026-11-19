from src.config.database import Base,engine,Session
from src.models.identity import User,Audit
from src.models.batch import Batch
from src.models.mapping import Mapping
from src.models.run import Run,TargetRow
from src.models.intake import SubmissionBatch,Checklist,ChecklistVersion,Commission
from src.utils.security import hash_password
RULES=[{'source':a,'target':b,'type':c,'required':True} for a,b,c in [('委托号','sample_code','text'),('检测项','test_name','text'),('结果','result_value','decimal'),('单位','unit','text'),('时间','measured_at','datetime')]]
def seed_intake(s):
 if s.query(SubmissionBatch).first():return
 checklists={
  '混凝土抗压组套':(['立方体抗压强度','坍落度','表观密度'],['立方体抗压强度','坍落度','表观密度','抗渗等级']),
  '钢筋力学组套':(['屈服强度','抗拉强度','断后伸长率'],['屈服强度','抗拉强度','断后伸长率']),
 }
 for panel,(v1,v2) in checklists.items():
  ck=Checklist(panel=panel,current_version=2);s.add(ck);s.flush()
  s.add(ChecklistVersion(checklist_id=ck.id,version=1,items=v1,note='初版必检清单',created_by='admin@migration.local'))
  s.add(ChecklistVersion(checklist_id=ck.id,version=2,items=v2,note='按新委托要求增补',created_by='operator@migration.local'))
 s.add(SubmissionBatch(name='送检批-20261118-A',description='同次送检待三份结果文件到件；混凝土组套已按v2更正'))
 s.flush()
 commissions=[('WT-20261118-001','混凝土抗压组套'),('WT-20261118-002','混凝土抗压组套'),('GJ-20261118-003','钢筋力学组套'),('WT-20261118-004','未知组套')]
 for code,panel in commissions:s.add(Commission(submission_batch_id=s.query(SubmissionBatch).filter_by(name='送检批-20261118-A').one().id,sample_code=code,panel=panel))

def seed():
 Base.metadata.create_all(engine)
 with Session() as s:
  for role in ('admin','operator','viewer'):
   if not s.query(User).filter_by(email=role+'@migration.local').first():s.add(User(email=role+'@migration.local',role=role,password=hash_password('Migrate2026!')))
  good=[{'委托号':f'JS-20261117-{i:03d}','检测项':'拉伸强度','结果':str(420+i/10),'单位':'MPa','时间':'2026-11-17T09:00:00+08:00'} for i in range(1,13)]
  bad=[good[0],{'委托号':'JS-BAD-01','检测项':'拉伸强度','结果':'四百二十','单位':'MPa','时间':'2026-11-17T09:00:00+08:00'},{'委托号':'JS-BAD-02','检测项':'拉伸强度','结果':None,'单位':'MPa','时间':'2026-11-17T09:00:00+08:00'},{'委托号':'JS-BAD-03','检测项':'拉伸强度','结果':'430','时间':'2026-11-17T09:00:00+08:00'}]
  seeds=[('见山日班检验结果',good,'lab-results-20261117.json','12条正常检测结果'),('旧字段异常样本',good[:2]+bad,'legacy-edge-20261117.json','重复自然键、非法数字、空值与缺列'),('空批次验收',[],'empty-results.json','空输入可完成备份与恢复')]
  for name,rows,file,desc in seeds:
   if not s.query(Batch).filter_by(name=name).first():s.add(Batch(name=name,rows=rows,source_file=file,description=desc))
  s.flush()
  for i,(name,_,_,_) in enumerate(seeds):
   mname=['检验结果标准映射','异常隔离复核映射','空批次映射'][i]
   if not s.query(Mapping).filter_by(name=mname).first():s.add(Mapping(name=mname,batch_id=s.query(Batch).filter_by(name=name).one().id,rules=RULES,chunk_size=4,note='sample_code + test_name 为自然键'))
  seed_intake(s)
  s.commit();counts={m.__tablename__:s.query(m).count() for m in (User,Batch,Mapping,Run,TargetRow,SubmissionBatch,Checklist,ChecklistVersion,Commission)};print(counts);return counts
if __name__=='__main__':seed()
