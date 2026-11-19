from sqlalchemy import Column,Integer,String,JSON,DateTime,func,ForeignKey,UniqueConstraint
from src.config.database import Base

class SubmissionBatch(Base):
 __tablename__='submission_batches'
 id=Column(Integer,primary_key=True)
 name=Column(String(120),unique=True,nullable=False)
 description=Column(String(500),nullable=False,default='')
 created_at=Column(DateTime,server_default=func.now())

class Checklist(Base):
 __tablename__='checklists'
 id=Column(Integer,primary_key=True)
 panel=Column(String(80),unique=True,nullable=False)
 current_version=Column(Integer,nullable=False,default=0)
 created_at=Column(DateTime,server_default=func.now())

class ChecklistVersion(Base):
 __tablename__='checklist_versions'
 __table_args__=(UniqueConstraint('checklist_id','version'),)
 id=Column(Integer,primary_key=True)
 checklist_id=Column(Integer,ForeignKey('checklists.id'),nullable=False)
 version=Column(Integer,nullable=False)
 items=Column(JSON,nullable=False)
 note=Column(String(500),nullable=False,default='')
 created_by=Column(String(120),nullable=False,default='')
 created_at=Column(DateTime,server_default=func.now())

class Commission(Base):
 __tablename__='commissions'
 __table_args__=(UniqueConstraint('submission_batch_id','sample_code'),)
 id=Column(Integer,primary_key=True)
 submission_batch_id=Column(Integer,ForeignKey('submission_batches.id'),nullable=False)
 sample_code=Column(String(160),nullable=False)
 panel=Column(String(80),nullable=False)
 created_at=Column(DateTime,server_default=func.now())

class ResultFile(Base):
 __tablename__='result_files'
 __table_args__=(UniqueConstraint('submission_batch_id','checksum'),)
 id=Column(Integer,primary_key=True)
 submission_batch_id=Column(Integer,ForeignKey('submission_batches.id'),nullable=False)
 filename=Column(String(160),nullable=False)
 checksum=Column(String(64),nullable=False)
 total_rows=Column(Integer,nullable=False,default=0)
 accepted_count=Column(Integer,nullable=False,default=0)
 rejected_count=Column(Integer,nullable=False,default=0)
 duplicate_count=Column(Integer,nullable=False,default=0)
 received_by=Column(String(120),nullable=False,default='')
 created_at=Column(DateTime,server_default=func.now())

class ResultItem(Base):
 __tablename__='result_items'
 __table_args__=(UniqueConstraint('commission_id','test_item'),)
 id=Column(Integer,primary_key=True)
 file_id=Column(Integer,ForeignKey('result_files.id'),nullable=False)
 commission_id=Column(Integer,ForeignKey('commissions.id'),nullable=False)
 test_item=Column(String(160),nullable=False)
 payload=Column(JSON,nullable=False)
 created_at=Column(DateTime,server_default=func.now())

class ResultRejection(Base):
 __tablename__='result_rejections'
 id=Column(Integer,primary_key=True)
 file_id=Column(Integer,ForeignKey('result_files.id'),nullable=False)
 commission_id=Column(Integer,ForeignKey('commissions.id'),nullable=True)
 row_number=Column(Integer,nullable=False)
 reason=Column(String(500),nullable=False)
 source=Column(JSON,nullable=False)
 created_at=Column(DateTime,server_default=func.now())

class Intake(Base):
 __tablename__='intakes'
 id=Column(Integer,primary_key=True)
 commission_id=Column(Integer,ForeignKey('commissions.id'),unique=True,nullable=False)
 checklist_version_id=Column(Integer,ForeignKey('checklist_versions.id'),nullable=False)
 checklist_version=Column(Integer,nullable=False)
 checklist_items=Column(JSON,nullable=False)
 checksum=Column(String(64),nullable=False)
 row_count=Column(Integer,nullable=False)
 created_by=Column(String(120),nullable=False,default='')
 created_at=Column(DateTime,server_default=func.now())

class IntakeRow(Base):
 __tablename__='intake_rows'
 __table_args__=(UniqueConstraint('intake_id','test_item'),)
 id=Column(Integer,primary_key=True)
 intake_id=Column(Integer,ForeignKey('intakes.id'),nullable=False)
 ordinal=Column(Integer,nullable=False)
 test_item=Column(String(160),nullable=False)
 payload=Column(JSON,nullable=False)
