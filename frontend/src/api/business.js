import {api,post} from './client.js';
export const batches={list:()=>api('/batches'),save:(d,id)=>post('/batches'+(id?'/'+id:''),d,id?'PUT':'POST')};
export const mappings={list:()=>api('/mappings'),save:(d,id)=>post('/mappings'+(id?'/'+id:''),d,id?'PUT':'POST')};
export const runs={list:()=>api('/runs'),run:d=>post('/runs',d),cancel:id=>post('/runs/'+id+'/cancel',{}),targets:id=>api('/runs/'+id+'/targets'),restore:(id,backup)=>post('/runs/'+id+'/restore',{backup})};
export const submissions={
 list:()=>api('/submissions'),
 create:d=>post('/submissions',d),
 detail:id=>api('/submissions/'+id),
 receive:(id,d)=>post('/submissions/'+id+'/files',d),
 storeAll:(id,panel_versions,panels)=>post('/submissions/'+id+'/store',{panel_versions,panels}),
};
export const checklists={
 list:()=>api('/checklists'),
 revise:(panel,d)=>post('/checklists/'+encodeURIComponent(panel)+'/versions',d),
};
export const commissions={store:(id,checklist_version)=>post('/commissions/'+id+'/store',{checklist_version})};
export const intakes={detail:id=>api('/intakes/'+id)};
