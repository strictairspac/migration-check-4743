import math
from pydantic import BaseModel,Field,model_validator
from src.services.migration import validate_rules
class Login(BaseModel):email:str;password:str
class BatchInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 source_file:str=Field(min_length=1,max_length=160)
 description:str=Field(default='',max_length=500)
 rows:list[dict]=Field(max_length=2000)
 @model_validator(mode='after')
 def bounded(self):
  for row in self.rows:
   if len(row)>20:raise ValueError('每行最多20列')
   for k,v in row.items():
    if len(k)>60 or not isinstance(v,(str,int,float,type(None))) or isinstance(v,bool) or (isinstance(v,float) and not math.isfinite(v)) or len(str(v))>500:raise ValueError('字段值类型/长度/有限数值约束失败')
  return self
class MappingInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 batch_id:int
 rules:list[dict]
 chunk_size:int=Field(default=50,ge=1,le=500)
 note:str=Field(default='',max_length=500)
 @model_validator(mode='after')
 def rules_valid(self):validate_rules(self.rules);return self
class RunInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 mapping_id:int
class RestoreInput(BaseModel):backup:dict

class SubmissionBatchInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 description:str=Field(default='',max_length=500)

class ChecklistInput(BaseModel):
 items:list[str]
 note:str=Field(default='',max_length=500)
 @model_validator(mode='after')
 def items_valid(self):
  from src.services.intake import canonical_items
  canonical_items(self.items);return self

class ResultFileInput(BaseModel):
 filename:str=Field(min_length=1,max_length=160)
 rows:list[dict]=Field(max_length=2000)
 @model_validator(mode='after')
 def bounded(self):
  for row in self.rows:
   if len(row)>20:raise ValueError('每行最多20列')
   for k,v in row.items():
    if len(k)>60 or not isinstance(v,(str,int,float,type(None))) or isinstance(v,bool) or (isinstance(v,float) and not math.isfinite(v)) or len(str(v))>500:raise ValueError('字段值类型/长度/有限数值约束失败')
  return self

class StoreInput(BaseModel):
 checklist_version:int|None=None
class StoreBatchInput(BaseModel):
 panel_versions:dict[str,int]=Field(default_factory=dict)
 panels:list[str]|None=None

