// 页面模板渲染冒烟：用极简 DOM 桩导入 ESM 页面模块，检查关键字段是否上屏。
const store=globalThis;
const stub=()=>({innerHTML:'',textContent:'',hidden:false,className:'',disabled:false,title:'',value:'',files:[],elements:{},dataset:{},style:{},addEventListener(){},scrollIntoView(){},querySelector(){return null},querySelectorAll(){return []},reset(){}});
globalThis.document={getElementById:()=>stub(),querySelector:()=>null,querySelectorAll:()=>[],hidden:false,createElement:()=>stub()};
globalThis.sessionStorage={getItem(){return null},setItem(){},removeItem(){}};
globalThis.fetch=async()=>({ok:true,json:async()=>({})});
globalThis.document.getElementById=()=>stub();
const {store:s}=await import('/workspace/frontend/src/stores/business.js');
const {intakePage,checklistPage}=await import('/workspace/frontend/src/pages/intake.js');
s.submissions=[{id:7,name:'送检批-20261118-A'}];s.intakeBatchId=7;
s.checklists=[{panel:'混凝土抗压组套',current_version:2,current:{items:['立方体抗压强度','坍落度','表观密度','抗渗等级']},versions:[{version:2,created_by:'op'},{version:1,created_by:'admin'}]}];
s.intakeDetail={batch:{id:7,name:'送检批-20261118-A'},files:[{id:1,filename:'part1.json',accepted_count:2,rejected_count:1,duplicate_count:0,total_rows:3,checksum:'abc',created_at:'2026-11-18',received_by:'operator'}],
 rejections:[{file_id:1,row_number:2,reason:'result_value:invalid_decimal',source:{检测项:'坍落度'}}],
 commissions:[
  {id:1,sample_code:'WT-001',panel:'混凝土抗压组套',status:'pending',received_items:['立方体抗压强度','坍落度'],received_count:2,checklist_version:2,checklist_items:['立方体抗压强度','坍落度','表观密度','抗渗等级'],missing_items:['表观密度','抗渗等级'],extra_items:[],missing_vs_adopted:[],verified:null,adopted_version:null},
  {id:2,sample_code:'WT-002',panel:'混凝土抗压组套',status:'stored',received_items:['立方体抗压强度'],received_count:3,checklist_version:3,checklist_items:['立方体抗压强度'],missing_items:[],extra_items:[],adopted_version:2,adopted_items:['立方体抗压强度','坍落度'],missing_vs_adopted:[],verified:true,intake_id:9},
  {id:3,sample_code:'WT-003',panel:'混凝土抗压组套',status:'no_checklist',received_items:[],received_count:0,checklist_version:null,checklist_items:[],missing_items:[],extra_items:[],adopted_version:null}
 ],
 summary:{pending:1,ready:0,stored:1,no_checklist:1}};
s.user={role:'operator'};
const html=intakePage();
const must=[['送检批选择器','batch-select'],['到件表单','receive-form'],['缺项展示','表观密度'],['采用版本','v2'],['当前清单版本','v3'],['入库操作','data-store="1"'],['已入库查看','data-intake="9"'],['整套入库','data-store-all-panel'],['并发更正入口','data-revise-panel'],['拒绝原因','invalid_decimal'],['状态徽标','缺必检清单'],['断线重提说明','重复']];
let fail=0;
for(const [label,token] of must){const ok=html.includes(token);console.log((ok?'PASS ':'FAIL ')+label+' :: '+token);if(!ok)fail++;}
const chk=checklistPage();
for(const [label,token] of [['版本历史','历史版本'],['发布表单','checklist-form'],['版本号','v2']]){const ok=chk.includes(token);console.log((ok?'PASS ':'FAIL ')+'清单页 '+label);if(!ok)fail++;}
console.log('\n失败:',fail);
process.exit(fail?1:0);
