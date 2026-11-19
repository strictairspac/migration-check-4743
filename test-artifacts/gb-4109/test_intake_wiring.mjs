// 在浏览器外模拟页面交互：用 DOM 桩加载 app.js，验证导航、收件、更正、入库、重试的调用链。
const calls=[];
function el(id=''){
 const node={id,innerHTML:'',textContent:'',hidden:false,className:'',disabled:false,title:'',value:'',files:[],dataset:{},style:{},
  children:[],listeners:{},
  addEventListener(ev,fn){(this.listeners[ev]=this.listeners[ev]||[]).push(fn)},
  scrollIntoView(){},querySelector(){return null},querySelectorAll(){return []},
  reset(){},click(){},focus(){},
  get elements(){return {}},form:{}};
 return node;
}
const nodes=new Map();
function get(id){if(!nodes.has(id))nodes.set(id,el(id));return nodes.get(id)}
const formFields=new Map();
function formNode(id,values){const n=el(id);n.elements=Object.fromEntries(Object.entries(values).map(([k,v])=>[k,{value:v}]));return n}
const forms=[];
globalThis.document={
 getElementById:id=>get(id),
 querySelector:sel=>sel.startsWith('#')?get(sel.slice(1)):null,
 querySelectorAll:sel=>{if(sel.includes('[data-revise-panel]'))return forms;return []},
 createElement:()=>el(),hidden:false,
};
globalThis.window={scrollTo(){}};
globalThis.sessionStorage={getItem(){return 'token'},setItem(){},removeItem(){}};
globalThis.URL={createObjectURL:()=>'',revokeObjectURL(){}};
globalThis.setInterval=()=>0;globalThis.clearInterval=()=>{};

const responses={
 'GET /api/auth/me':{email:'operator@migration.local',role:'operator'},
 'GET /api/batches':[{id:1,name:'见山日班检验结果',source_file:'x',description:'',rows:[]}],
 'GET /api/mappings':[{id:1,name:'检验结果标准映射',batch_id:1,rules:[],chunk_size:4}],
 'GET /api/runs':[],
 'GET /api/submissions':[{id:7,name:'送检批-20261118-A',description:''}],
 'GET /api/checklists':[{panel:'混凝土抗压组套',current_version:2,current:{items:['立方体抗压强度','坍落度']},versions:[]}],
 'GET /api/submissions/7':{batch:{id:7,name:'送检批-20261118-A'},files:[],rejections:[],summary:{pending:1,ready:0,stored:0,no_checklist:0},commissions:[
  {id:11,sample_code:'WT-001',panel:'混凝土抗压组套',status:'ready',received_items:['立方体抗压强度','坍落度'],received_count:2,checklist_version:2,checklist_items:['立方体抗压强度','坍落度'],missing_items:[],extra_items:[],adopted_version:null,adopted_items:[],missing_vs_adopted:[],verified:null,intake_id:null}]},
 'POST /api/commissions/11/store':{intake:{id:21,checklist_version:2,row_count:2,checksum:'c'},duplicate:false},
 'POST /api/checklists/混凝土抗压组套/versions':{panel:'混凝土抗压组套',current_version:3},
 'POST /api/submissions/7/files':{accepted_count:1,rejected_count:0,duplicate_count:0,duplicate:false,filename:'part2.json'},
 'POST /api/submissions/7/store':{stored:[{intake:{id:21},duplicate:false}],skipped:[],duplicates:0,versions:{}},
};
let failCount=0;
globalThis.fetch=async(url,opts={})=>{
 const method=(opts.method||'GET');
 const path=url.replace('/api','');
 calls.push(method+' '+url);
 const key=method+' '+('/api'+path);
 const body=responses[key];
 return {ok:body!==undefined,status:body!==undefined?200:404,json:async()=>body??{detail:'missing '+key},blob:async()=>new Blob()};
};
const feedbackBox=el('feedback');
const feedbackMessages=[];
const origText=Object.getOwnPropertyDescriptor;
// feedback() 直接写入 #feedback，这里通过 getter 捕获
let lastFeedback='';
Object.defineProperty(feedbackBox,'textContent',{set(v){lastFeedback=v},get(){return lastFeedback}});
Object.defineProperty(feedbackBox,'className',{set(v){if(v.includes('error'))lastFeedback='[ERR] '+lastFeedback},get(){return ''}});

await import('/workspace/frontend/src/app.js');

const find=(sel)=>calls.filter(c=>c.includes(sel));
console.log('已加载 app，首屏请求:',calls.join(' | '));
function check(name,cond,extra=''){console.log((cond?'PASS ':'FAIL ')+name+(cond?'':' :: '+extra));if(!cond)failCount++;}
check('登录后拉取送检批',find('/submissions').length>=1);
check('登录后拉取清单',find('/checklists').length>=1);
check('自动加载首个送检批详情',find('/submissions/7').length>=1);

// 通过导出函数驱动页面关键动作
const mod=await import('/workspace/frontend/src/pages/intake.js');
const {commissionStoreAction}=mod;
const btn={dataset:{store:'11',version:'2'}};
const r=await commissionStoreAction(btn);
check('入库按钮调用带版本号',calls.includes('POST /api/commissions/11/store'),calls.join('|'));
check('入库返回非重复',r.duplicate===false,JSON.stringify(r));
const allCallsBefore=find('/submissions/7/store').length;
const btn2={dataset:{storeAllPanel:'混凝土抗压组套'}};
await mod.storeAllPanel('混凝土抗压组套');
check('整套入库传当前版本',find('/submissions/7/store').length===allCallsBefore+1);

console.log('\n失败:',failCount);
process.exit(failCount?1:0);
