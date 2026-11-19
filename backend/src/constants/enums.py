ROLES=('admin','operator','viewer')
STATUSES=('queued','running','completed','failed','cancelled')
TYPES={'sample_code':'text','test_name':'text','result_value':'decimal','unit':'text','measured_at':'datetime'}
INTAKE_STATUSES=('pending','ready','stored','no_checklist')
# 送检结果文件的固定旧字段。委托按送检批+委托号归组，组套决定必检项清单。
INTAKE_FIELDS=(
 {'source':'委托号','target':'sample_code','type':'text','required':True},
 {'source':'组套','target':'panel','type':'text','required':True},
 {'source':'检测项','target':'test_item','type':'text','required':True},
 {'source':'结果','target':'result_value','type':'decimal','required':True},
 {'source':'单位','target':'unit','type':'text','required':False},
 {'source':'时间','target':'measured_at','type':'datetime','required':True},
)
INTAKE_PANEL_MAX=80
INTAKE_ITEMS_MAX=50
