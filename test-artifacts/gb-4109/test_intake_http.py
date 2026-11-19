"""HTTP 层冒烟：登录、送检批、收件、更正清单、入库、幂等重试、页面核算字段。"""
import os,sys,tempfile
os.environ.setdefault('JWT_SECRET','test-secret')
os.environ['DATABASE_URL']='sqlite+pysqlite:///'+tempfile.mktemp(suffix='.db')
os.environ['REDIS_URL']='redis://localhost:6379/0'
os.environ['SEED_DEMO']='true'
sys.path.insert(0,'/workspace/backend')
import warnings;warnings.filterwarnings('ignore')
from fastapi.testclient import TestClient
from src.main import app
from src.models.intake import SubmissionBatch
from src.config.database import Session

failures=[]
def check(name,cond,extra=''):
 print(('PASS ' if cond else 'FAIL ')+name+((' :: '+str(extra)) if extra and not cond else ''))
 if not cond:failures.append(name)

def row(code,panel,item,value,unit='MPa',ts='2026-11-18T10:00:00+08:00'):
 return {'委托号':code,'组套':panel,'检测项':item,'结果':value,'单位':unit,'时间':ts}

with TestClient(app) as c:
 login=c.post('/auth/login',json={'email':'operator@migration.local','password':'Migrate2026!'})
 check('operator登录',login.status_code==200,login.text)
 h={'Authorization':'Bearer '+login.json()['token']}
 check('送检批已seed',len(c.get('/submissions',headers=h).json())>=1)
 check('清单已seed v2',c.get('/checklists/混凝土抗压组套',headers=h).json()['current_version']==2)

 b=c.post('/submissions',headers=h,json={'name':'HTTP批','description':'冒烟'}).json()
 bid=b['id']
 r1=c.post(f'/submissions/{bid}/files',headers=h,json={'filename':'a.json','rows':[row('H-1','混凝土抗压组套','立方体抗压强度','420.5'),row('H-1','混凝土抗压组套','坍落度','180','mm')]})
 check('收件200',r1.status_code==200,r1.text)
 check('收2项',r1.json()['accepted_count']==2,r1.json())
 d=c.get(f'/submissions/{bid}',headers=h).json()
 comm=d['commissions'][0]
 check('按v2缺表观密度与抗渗等级',comm['missing_items']==['表观密度','抗渗等级'],comm)
 check('页面可见当前版本v2',comm['checklist_version']==2)

 bad=c.post(f'/submissions/{bid}/files',headers=h,json={'filename':'b.json','rows':[{'委托号':'H-2','组套':'混凝土抗压组套','检测项':'坍落度'}]})
 check('非法行不报500',bad.status_code==200,bad.text)
 check('缺列被拒',bad.json()['rejected_count']==1,bad.json())
 check('拒绝区可取',any('missing_column' in x['reason'] for x in c.get(f'/submissions/{bid}',headers=h).json()['rejections']))

 # 未齐直接入库
 early=c.post(f'/commissions/{comm["id"]}/store',headers=h,json={'checklist_version':2})
 check('未齐入库409',early.status_code==409,early.text)
 check('409带中文缺项',early.json()['detail']['skip']['missing']==['表观密度','抗渗等级'],early.json())

 # 并发更正清单（v3 增加含气量）
 rev=c.post('/checklists/混凝土抗压组套/versions',headers=h,json={'items':['立方体抗压强度','坍落度','表观密度','含气量'],'note':'增补'})
 check('清单更正为v3',rev.status_code==200 and rev.json()['current_version']==3,rev.text)
 d=c.get(f'/submissions/{bid}',headers=h).json()
 check('待齐委托按v3重新核算',d['commissions'][0]['missing_items']==['表观密度','含气量'],d['commissions'][0]['missing_items'])

 # 更正期间照常收件
 r2=c.post(f'/submissions/{bid}/files',headers=h,json={'filename':'c.json','rows':[row('H-1','混凝土抗压组套','表观密度','2400','kg/m3'),row('H-1','混凝土抗压组套','含气量','4.5','%')]})
 check('更正期间收件成功',r2.status_code==200 and r2.json()['accepted_count']==2,r2.text)

 # 拿过期版本入库被拒
 stale=c.post(f'/commissions/{comm["id"]}/store',headers=h,json={'checklist_version':2})
 check('过期版本409',stale.status_code==409 and stale.json()['detail']['skip']['reason']=='checklist_revised',stale.text)

 ok=c.post(f'/commissions/{comm["id"]}/store',headers=h,json={'checklist_version':3})
 check('按v3入库',ok.status_code==200 and ok.json()['intake']['checklist_version']==3,ok.text)
 intake_id=ok.json()['intake']['id']

 # 断线重试
 retry=c.post(f'/commissions/{comm["id"]}/store',headers=h,json={'checklist_version':3})
 check('重试幂等',retry.status_code==200 and retry.json()['duplicate'] is True,retry.text)

 # 再更正，已入库按原版
 c.post('/checklists/混凝土抗压组套/versions',headers=h,json={'items':['立方体抗压强度'],'note':'简化'})
 det=c.get(f'/intakes/{intake_id}',headers=h).json()
 check('入库记录锁v3',det['checklist_version']==3)
 check('摘要核对一致',det['verified'] is True)
 check('标记版本已变更',det['version_changed'] is True)
 d=c.get(f'/submissions/{bid}',headers=h).json()
 check('列表显示采用v3',d['commissions'][0]['adopted_version']==3)
 check('列表按原版无缺项',d['commissions'][0]['missing_vs_adopted']==[])

 # viewer 只读
 v=c.post('/auth/login',json={'email':'viewer@migration.local','password':'Migrate2026!'}).json()
 vh={'Authorization':'Bearer '+v['token']}
 check('viewer可读送检批',c.get(f'/submissions/{bid}',headers=vh).status_code==200)
 check('viewer不可收件',c.post(f'/submissions/{bid}/files',headers=vh,json={'filename':'x.json','rows':[]}).status_code==403)

 # 整套入库
 batch2=c.post('/submissions',headers=h,json={'name':'HTTP批2','description':''}).json()
 c.post(f'/submissions/{batch2["id"]}/files',headers=h,json={'filename':'p1.json','rows':[row('K-1','钢筋力学组套','屈服强度','500'),row('K-1','钢筋力学组套','抗拉强度','620')]})
 c.post(f'/checklists/钢筋力学组套/versions',headers=h,json={'items':['屈服强度','抗拉强度','断后伸长率'],'note':'核对'})
 whole=c.post(f'/submissions/{batch2["id"]}/store',headers=h,json={'panel_versions':{'钢筋力学组套':1}})
 check('整套入库冻结版本',whole.status_code==200,whole.text)
 check('未齐跳过',whole.json()['skipped'][0]['commission']=='K-1',whole.json())
 c.post(f'/submissions/{batch2["id"]}/files',headers=h,json={'filename':'p2.json','rows':[row('K-1','钢筋力学组套','断后伸长率','18')]})
 whole2=c.post(f'/submissions/{batch2["id"]}/store',headers=h,json={'panel_versions':{'钢筋力学组套':1}})
 check('版本不符仍跳过',whole2.status_code==200 and whole2.json()['skipped'][0]['reason']=='checklist_revised',whole2.text)
 whole3=c.post(f'/submissions/{batch2["id"]}/store',headers=h,json={'panel_versions':{'钢筋力学组套':3}})
 check('按v3整套入库',whole3.status_code==200 and len(whole3.json()['stored'])==1,whole3.text)
 whole4=c.post(f'/submissions/{batch2["id"]}/store',headers=h,json={'panel_versions':{'钢筋力学组套':3}})
 check('整套重试不重复',whole4.json()['duplicates']==1,whole4.text)

 # 原有迁移链路不受影响
 old=c.get('/batches',headers=h)
 check('原批次接口正常',old.status_code==200 and len(old.json())>=3,old.text)
 run=c.post('/runs',headers=h,json={'name':'smoke-run','mapping_id':1})
 check('原迁移创建走原队列路径(本环境无Redis=503)',run.status_code in (200,503) and (run.status_code==200 or '队列不可用' in run.text),run.text)

print('\n失败:',failures if failures else '无')
sys.exit(1 if failures else 0)
