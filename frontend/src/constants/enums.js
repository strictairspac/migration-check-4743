export const ROLES={admin:'管理员',operator:'操作员',viewer:'观察员'};
export const STATUSES={queued:'等待处理',running:'迁移中',completed:'已完成',failed:'失败',cancelled:'已取消'};
export const TYPES={sample_code:'text',test_name:'text',result_value:'decimal',unit:'text',measured_at:'datetime'};
export const INTAKE_STATUSES={pending:'待补齐',ready:'可入库',stored:'已入库',no_checklist:'缺必检清单'};
export const INTAKE_SKIP_REASONS={incomplete:'必检项未齐',no_checklist:'该组套尚无必检清单',checklist_revised:'清单已在入库期间更正，请重新核算'};
