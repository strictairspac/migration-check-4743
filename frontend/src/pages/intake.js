import {store,loadIntake} from '../stores/business.js';import {submissions,commissions} from '../api/business.js';import {esc,json} from '../utils/html.js';import {table} from '../components/common/table.js';import {INTAKE_STATUSES} from '../constants/enums.js';

const badge=s=>`<span class="status ${s==='stored'?'completed':s==='ready'?'running':s==='no_checklist'?'failed':''}">${INTAKE_STATUSES[s]||s}</span>`;
const chips=(list,cls='')=>list?.length?list.map(x=>`<span class="item-chip ${cls}">${esc(x)}</span>`).join(''):'<span class="muted">—</span>';

function commissionRow(c){
 const adopted=c.status==='stored'
  ?`v${c.adopted_version}<small>${esc((c.adopted_items||[]).join('、'))}${c.checklist_version!==c.adopted_version?`<br>当前清单 v${c.checklist_version}`:''}</small>`
  :`v${c.checklist_version??'—'}<small>当前清单</small>`;
 const missing=c.status==='stored'
  ?`${chips(c.missing_vs_adopted,'bad')}<small>相对入库版本核对${c.verified?' · 摘要一致':' · 摘要不一致'}</small>`
  :`${chips(c.missing_items,'bad')}<small>按当前版本核算</small>`;
 const extra=chips(c.extra_items,'warn');
 const action=c.status==='stored'
  ?`<button class="quiet" data-intake="${c.intake_id}">查看入库记录 →</button>`
  :`<button class="quiet" data-store="${c.id}" data-version="${c.checklist_version??''}" ${c.status==='ready'?'':'disabled'}>入库 →</button>`;
 return [`<td><b>${esc(c.sample_code)}</b><small>${esc(c.panel)}</small></td>`,badge(c.status),`<small>${c.received_count} 项</small>${chips(c.received_items)}`,adopted,missing,extra,action];
}

export function intakePage(){
 const d=store.intakeDetail;
 const options=store.submissions.map(b=>`<option value="${b.id}" ${b.id===store.intakeBatchId?'selected':''}>${esc(b.name)}</option>`).join('');
 const batchPicker=`<div class="operator-strip"><div><span>送检批</span><b>${d?d.files.length:0}</b><small>已到文件</small></div><div><span>待补齐</span><b>${d?d.summary.pending+d.summary.ready:0}</b><small>委托（含可入库）</small></div><div><span>已入库</span><b>${d?d.summary.stored:0}</b><small>按入库时版本</small></div><div><span>缺清单</span><b>${d?d.summary.no_checklist:0}</b><small>组套未维护</small></div></div>`;
 const receiveForm=`<form id="receive-form"><input type="hidden" name="batch_id" value="${store.intakeBatchId??''}"><label>结果文件名<input name="filename" required placeholder="results-part2.json"></label><label>本文件行 JSON<textarea name="rows" class="code-input" rows="9" required>${json([{'委托号':'WT-20261118-001','组套':'混凝土抗压组套','检测项':'坍落度','结果':'180','单位':'mm','时间':'2026-11-18T10:20:00+08:00'}])}</textarea></label><small>同一送检批可多次到件；重复提交同一文件按内容摘要识别，不重复收件。只接受转换合格的行，非法行进入拒绝区。</small><button type="submit" ${store.intakeBatchId?'':'disabled'}>登记到件文件</button></form>`;
 const fileList=table(['文件 / 到件','收件结果','摘要'],(d?.files||[]).map(f=>[`<b>${esc(f.filename)}</b><small>${esc(f.created_at||'')} · ${esc(f.received_by)}</small>`,`收 ${f.accepted_count} / 拒 ${f.rejected_count} / 重 ${f.duplicate_count}<small>源 ${f.total_rows} 行</small>`,`<code class="checksum">${esc(f.checksum)}</code>`]));
 const rejectList=table(['文件','行号','原因','原行'],(d?.rejections||[]).map(r=>[esc(d.files.find(f=>f.id===r.file_id)?.filename||r.file_id),r.row_number,esc(r.reason),`<details><summary>展开</summary><pre>${json(r.source)}</pre></details>`]));
 const groups={};(d?.commissions||[]).forEach(c=>{(groups[c.panel]=groups[c.panel]||[]).push(c)});
 const groupBlocks=Object.entries(groups).map(([panel,list])=>{
  const current=store.checklists.find(x=>x.panel===panel);
  const ready=list.filter(c=>c.status==='ready').length;
  return `<section class="panel-group"><header class="panel-head"><div><span class="eyebrow">PANEL / 组套</span><h3>${esc(panel)}</h3><p>当前必检清单 v${current?.current_version??'—'}（${(current?.current?.items||[]).length} 项）· ${list.length} 个委托 · 可入库 ${ready}</p></div><div class="actions"><button class="quiet" data-store-all-panel="${esc(panel)}" ${ready?'':'disabled'}>本组套整套入库 →</button></div></header><details class="revise"><summary>并发更正本组套必检清单（待齐委托将按新版本重新核算）</summary><form data-revise-panel="${esc(panel)}"><label>新版本必检项 JSON<input name="items" required value="${esc(JSON.stringify(current?.current?.items||[]))}"></label><label>更正说明<input name="note" maxlength="500" placeholder="为何增删必检项"></label><button type="submit">发布新版本</button></form><p class="muted">版本只增不改：已入库的委托仍按入库时版本核对；更正期间照常收件。</p></details>${table(['委托 / 组套','状态','已收合格项','采用版本','还缺','超额项','操作'],list.map(commissionRow))}</section>`;
 });
 const noBatch=store.submissions.length?'':'<div class="empty"><h2>先登记一个送检批</h2><p>同一次送检的结果会分文件陆续到件；先建送检批，再逐份收件。</p></div>';
 return `<div class="split"><section><h2>同次送检 · 分文件收件</h2><p>按送检批和委托组套归组；只有转换合格的结果项才补入委托，必检项凑齐后才允许整套入库。</p><form id="submission-form"><label>送检批名称<input name="name" required placeholder="送检批-20261118-B"></label><label>说明<input name="description" placeholder="同次送检的到件安排"></label><button type="submit">新建送检批</button></form><label>当前送检批<select id="batch-select">${options||'<option value="">尚无送检批</option>'}</select></label>${noBatch}${receiveForm}<aside class="note">同一委托在入库前可一直补件；入库时整套按同一版本清单校验，断线重试只补不重复写。</aside></section><section><h2>收件台账 <em>${d?.files.length||0}</em></h2>${batchPicker}${fileList}<h3>拒绝区 · 原行保留</h3>${rejectList}${groupBlocks.join('')}<div id="intake-detail"></div></section></div>`;
}

export function checklistPage(){
 return `<div class="split"><section><h2>组套必检清单</h2><p>清单按组套维护、按版本发布，只增不改。更正不影响已入库记录；待齐委托在下次核算时套用当前版本。</p><form id="checklist-form"><label>组套名称<input name="panel" required placeholder="混凝土抗压组套"></label><label>必检项 JSON<input name="items" required placeholder='["立方体抗压强度","坍落度"]'></label><label>说明<input name="note" maxlength="500" placeholder="更正原因"></label><button type="submit">发布新版本</button></form></section><section><h2>清单版本 <em>${store.checklists.length}</em></h2>${table(['组套 / 当前版本','当前必检项','历史版本'],store.checklists.map(c=>[`<b>${esc(c.panel)}</b><small>v${c.current_version}</small>`,chips(c.current?.items||[]),`<small>${c.versions.map(v=>`v${v.version} · ${esc(v.created_by||'')}`).join('<br>')}</small>`]))}<aside class="note">更正清单时若已有委托入库，其入库记录仍锁定发布时的版本与逐项摘要，可随时按原版核对。</aside></section></div>`;
}

export function commissionStoreAction(button){
 const id=Number(button.dataset.store);
 const version=button.dataset.version?Number(button.dataset.version):null;
 return commissions.store(id,version).then(async r=>{await loadIntake();return r;});
}

export function storeAllPanel(panel){
 const current=store.checklists.find(x=>x.panel===panel);
 const versions=current?{[panel]:current.current_version}:{};
 return submissions.storeAll(store.intakeBatchId,versions,[panel]).then(async r=>{await loadIntake();return r;});
}
