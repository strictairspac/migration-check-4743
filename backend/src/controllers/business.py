from src.services import batches,mappings,runs,intake
from src.services.audit import log
def save_batch(data,user,item_id=None):
 row=batches.save(data,item_id);log(user.email,'batch.save',row['name']);return row
def save_mapping(data,user,item_id=None):
 row=mappings.save(data,item_id);log(user.email,'mapping.save',row['name']);return row
def start_run(data,user):
 row=runs.create(data);log(user.email,'run.queue',row['name']);return row

def save_submission_batch(data,user,item_id=None):
 row=intake.save_batch(data,item_id);log(user.email,'submission.save',row['name']);return row
def revise_checklist(panel,data,user):
 row=intake.revise_checklist(panel,data,user.email)
 log(user.email,'checklist.revise',f"{panel} v{row['current_version']}")
 return row
def receive_result_file(batch_id,data,user):
 row=intake.receive_file(batch_id,data,user.email)
 log(user.email,'intake.file.duplicate' if row['duplicate'] else 'intake.file.receive',
  f"batch={batch_id} file={row['filename']} accepted={row['accepted_count']} rejected={row['rejected_count']}")
 return row
def store_one_commission(commission_id,data,user):
 row=intake.store_commission(commission_id,user.email,data.checklist_version)
 log(user.email,'intake.store.duplicate' if row['duplicate'] else 'intake.store',
  f"commission={commission_id} version={row['intake']['checklist_version']} rows={row['intake']['row_count']}")
 return row
def store_batch_commissions(batch_id,data,user):
 row=intake.store_ready(batch_id,user.email,data.panel_versions,data.panels)
 log(user.email,'intake.store.batch',
  f"batch={batch_id} stored={len(row['stored'])} skipped={len(row['skipped'])} duplicates={row['duplicates']}")
 return row
