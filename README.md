# 见山 · 检验结果迁移核对站

见山质量档案组13人用源批次、字段映射、后台对账运行完成旧字段检验结果的有证据交接。

## 场景与业务
上游实验室交付旧字段JSON检验记录；过去人工改字段名、复制到新表并凭总行数判断成功。痛点：非法数值默默丢失、重复委托号覆盖、备份无法证明能恢复。本站登记原始行，字段映射规定类型和必填，Python逐块转换并保留拒绝原行，真实PG目标表一次提交。下游质量复核人下载对账凭据，管理员用JSON逻辑备份恢复本次运行目标并核验。

四业务页：源批次、字段映射、迁移执行（可取消）、差异核对（拒绝区/目标行/备份）；管理员另有审计和回传恢复。三核心实体batches/mappings/runs，另target_rows持久化目标行。全部实体按模型/schema/service/controller/routes/前端api/store/page贯穿。

另有一条送检收件链路（05送检收件、06必检清单）：同次送检的结果分多个文件到件，按送检批+委托号归组、按组套套必检清单。文件按内容摘要去重（断线重投不重复收件）；每行先转换再落库，只有转换合格的行才补进委托，非法行保留原行进拒绝区。必检项凑齐前不得入库；入库按当前清单版本逐项校验，把版本、必检项和整套SHA-256摘要冻结在intakes/intake_rows。清单可按组套并发更正（只增版本）：待齐委托在每次核算时按新版本重算，已入库委托仍按入库时版本核对；更正期间照常收件，入库时整套只认一个版本，期间清单被改则整套拒绝并提示重新核算。每个委托入库唯一，重复请求（含断线重试）只返回原记录不重复写入。页面逐委托显示还缺哪些必检项、超额项、当前清单版本与入库采用的版本。

## 启动与账号
```sh
cp .env.example .env
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
```
前端 http://localhost:18248 ，后端 http://localhost:19248/docs ，PostgreSQL localhost:17748（migrate / migratepass / migrationcheck）。结束docker compose down -v --remove-orphans会清除本地数据。

| 角色 | 账号 | 权限 / 页面 | 典型动作 |
|---|---|---|---|
| admin | admin@migration.local | 全部、审计、恢复 | 回传备份恢复目标并校验 |
| operator | operator@migration.local | 创建/编辑/执行/取消/导出、收件、更正清单、入库 | 配置映射并迁移、分文件收件 |
| viewer | viewer@migration.local | 只读、下载凭据/备份 | 复核拒绝区、缺项与真实目标表 |

密码统一Migrate2026!；PBKDF2密码与8小时JWT。本地演示凭据与JWT密钥，部署前更换。

## 一天的交接剧本
1. 09:00 operator签入，查看见山日班检验结果12条正常记录。
2. 09:05 登记lab-results-20261117.json，委托号JS-20261117-001结果420.1MPa。
3. 09:10 新建shift-20261117批次，复制旧字段。
4. 09:15 字段映射：委托号→sample_code、检测项→test_name、结果→result_value、单位→unit、时间→measured_at，每块4行。
5. 09:20 提交shift-20261117对账，或运行旧字段异常样本查看重复/非法数字/空值/缺列拒绝。
6. 09:25 查看接受/拒绝与分块证据，读取真实PG目标表。
7. 09:30 下载reconciliation-<id>.json与backup-<id>.json，viewer复核。
8. 10:00 admin回传该备份，恢复并核对摘要，查看审计完成事件。
9. 10:10 operator在送检收件页新建送检批-20261118-A，按三份结果文件陆续到件：每份文件只补合格项，缺列/非法数值/组套不符进拒绝区。页面逐委托显示还缺哪些必检项与当前清单版本。
10. 10:20 同一送检批的混凝土组套并发更正必检清单（v2增补抗渗等级），待齐委托立即按v2重算；已入库的委托仍显示采用版本并可按原版核对。
11. 10:25 必检项凑齐的委托整套入库：采用当前版本，版本、必检项与整套摘要冻结；断线重试或重复点击返回原记录，不重复入库。未齐/清单刚被更正的委托跳过并提示重新核算。

seed含三账号、三批次（三种正常/异常/空输入）、三映射，另有一个送检批与两个组套的v1→v2清单版本。固定数值、自然键upsert式补缺，不覆盖用户编辑；连续执行不新增。

## 迁移、校验、取消与恢复
字段类型为text/decimal/datetime。decimal使用Decimal精确转换为6位小数字符串，范围±1e9；无穷/NaN拒绝。空值/空串按required隔离（只有unit可非必填）；缺源字段隔离。时间统一UTC，无时区按Asia/Shanghai(+08:00)解释。自然键sample_code+test_name按规范JSON SHA-256计算；同次运行重复键只接受首条合法记录。每行与全部接受行用排序key/紧凑JSON/UTF-8算SHA-256。拒绝行保存原行和原因。

最多2000源行、每行20列、单元格500字符；每块1-500行。逐块更新进度；取消在块间检查，最终提交前锁定run再次检查，成功目标一次提交；取消/异常没有部分目标数据。后台任务使用简单Redis单消费者；进程崩溃可能留下running状态，需人工复核并新建任务，不自动重试。

下载备份为本工具目标行的逻辑JSON快照(version1)，含run_id/rows/row_hashes/checksum，不是pg_dump或物理备份，不含WAL/索引/权限。管理员恢复只允许该运行已保存checksum完全匹配的备份；先核验逐行/总体摘要、schema和自然键，再事务性替换该运行target_rows，回读重新计算摘要并保存recovery记录。篡改、错运行、未完成运行拒绝，恢复事务回滚；不能用任意新数据覆盖目标。

受控场景演示旧字段到新目标结构的逻辑迁移，数据库真实保存源/映射/目标/对账。不能连接远端数据库，不宣称生产异构迁移或灾备能力。

## 送检收件与齐套入库
- 归组键：送检批（submission_batches）+ 委托号（commissions，同批内唯一）；组套（panel）随委托确定，同一委托报不同组套直接拒绝。
- 到件：POST /submissions/{id}/files 提交文件名与源行。文件内容 SHA-256 相同即视为同一文件，返回 duplicate 不重复收件；同一委托同一检测项再送计入 duplicate_count，保留首条转换合格值。转换规则与迁移页一致：text/decimal（6位小数、±1e9）/datetime（无时区按+08:00，存UTC），空值按必填隔离，缺列、非法值、缺委托号/组套的行全部进 result_rejections 并保留原行。先转换后建委托，脏行不会产生空委托。
- 必检清单：按组套维护，POST /checklists/{panel}/versions 每次发布新版本，旧版本永久保留。待齐委托在每次查询/入库时按当前版本核算；已入库委托读取 intakes 中冻结的版本与必检项，按原版核对，不受后续更正影响。
- 入库：POST /commissions/{id}/store（可带 checklist_version 期望值）或 POST /submissions/{id}/store 整套入库。整套只认一个版本：调用开始时按各委托组套冻结版本，逐委托校验，期间清单被更正则返回 checklist_revised 并整套跳过该委托；必检项不齐返回 incomplete 且不写任何行。入库写入 intakes/intake_rows 并保存整套摘要（排序后的行载荷 SHA-256）。
- 幂等：每个委托至多一条 intake（唯一约束），重复请求或断线重试返回 duplicate=true 原记录；带过期版本重试也按已入库处理，不报错不重写。
- 页面：送检收件页按组套分组列出每个委托的已收合格项、采纳版本、还缺项、超额项与状态（待补齐/可入库/已入库/缺必检清单），并提供整套入库、并发更正清单与到件表单；必检清单页展示各版本历史。

## 工程与开发
Python3.11/FastAPI/SQLAlchemy/psycopg/Redis/PostgreSQL16，原生HTML/CSS/JS，nginx1.27。exact五服务frontend/backend/worker/db/redis均healthcheck，数据库/Redis/共享产物命名卷；依赖健康后启动。请求追踪、全局错误、JWT授权和业务审计横切。

backend/src按models/schemas/services/controllers/routes/middlewares/config/constants/utils；backend/scripts/seed_demo.py；backend/migrations记录元数据版本。frontend/src按api/stores/pages/components/common/hooks/router/types/constants/utils；共享table/status/feedback；forms/poll hooks。角色/状态/类型枚举在backend/src/constants/enums.py与frontend/src/constants/enums.js。墨绿邮政凭单视觉，Noto Sans SC/Space Mono双字体来自Google Fonts，离线回退；桌面/平板/手机响应。

.env.example定义COMPOSE_PROJECT_NAME/三端口/JWT_SECRET/SEED_DEMO；DATABASE_URL/REDIS_URL由Compose注入。启动SEED_DEMO失败只记日志。本地开发pip install -r backend/requirements.txt，设数据库/Redis/JWT环境变量，在backend运行uvicorn src.main:app --reload；前端需/api代理，不能file://。测试/截图/日志放批次test-artifacts/gb-4109，源码不混入。MIT License。
