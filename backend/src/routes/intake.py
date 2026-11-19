from fastapi import APIRouter,Depends,HTTPException
from src.middlewares.auth import current,writer
from src.schemas.business import SubmissionBatchInput,ChecklistInput,ResultFileInput,StoreInput,StoreBatchInput
from src.services import intake
from src.controllers.business import (save_submission_batch,revise_checklist,receive_result_file,
 store_one_commission,store_batch_commissions)
router=APIRouter()

@router.get('/submissions')
def listing(u=Depends(current)):return intake.list_batches()
@router.post('/submissions')
def create(data:SubmissionBatchInput,u=Depends(writer)):return save_submission_batch(data,u)
@router.get('/submissions/{batch_id}')
def detail(batch_id:int,u=Depends(current)):return intake.batch_detail(batch_id)

@router.get('/checklists')
def checklists(u=Depends(current)):return intake.list_checklists()
@router.get('/checklists/{panel}')
def checklist(panel:str,u=Depends(current)):return intake.get_checklist(panel)
@router.post('/checklists/{panel}/versions')
def revise(panel:str,data:ChecklistInput,u=Depends(writer)):return revise_checklist(panel,data,u)

@router.post('/submissions/{batch_id}/files')
def receive(batch_id:int,data:ResultFileInput,u=Depends(writer)):return receive_result_file(batch_id,data,u)

@router.post('/commissions/{commission_id}/store')
def store(commission_id:int,data:StoreInput,u=Depends(writer)):return store_one_commission(commission_id,data,u)
@router.post('/submissions/{batch_id}/store')
def store_batch(batch_id:int,data:StoreBatchInput,u=Depends(writer)):return store_batch_commissions(batch_id,data,u)

@router.get('/intakes/{intake_id}')
def intake_record(intake_id:int,u=Depends(current)):return intake.intake_detail(intake_id)
