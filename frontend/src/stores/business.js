import {batches,mappings,runs,submissions,checklists} from '../api/business.js';
export const store={batches:[],mappings:[],runs:[],submissions:[],checklists:[],intakeDetail:null,intakeBatchId:null,user:null};
export async function refresh(){
 const [b,m,r,s,c]=await Promise.all([batches.list(),mappings.list(),runs.list(),submissions.list(),checklists.list()]);
 store.batches=b;store.mappings=m;store.runs=r;store.submissions=s;store.checklists=c;
}
export async function loadIntake(){
 if(!store.intakeBatchId&&store.submissions.length)store.intakeBatchId=store.submissions[0].id;
 store.intakeDetail=store.intakeBatchId?await submissions.detail(store.intakeBatchId):null;
 return store.intakeDetail;
}
