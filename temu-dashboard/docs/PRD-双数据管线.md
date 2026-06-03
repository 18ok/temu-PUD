## Problem Statement

Temu运营团队每人有两份Excel：利润统计(.xls, 商品级SPU数据)和店铺数据记录(.xlsx, 店铺级运营数据)。当前看板只能处理利润统计，店铺数据记录被上传后立即跳过，无法分析ROAS、转化率、曝光量等核心运营指标。两套数据混传导致解析异常。

## Solution

在看板中同时支持两类数据：
- 利润统计 → 现有6页面（商品画像/选品规则/智能预测/避坑清单/个人诊断）
- 店铺数据记录 → 新增"店铺运营"页面（多店铺/多日对比、ROAS趋势、转化漏斗、花费效率）
- 上传时自动识别文件类型，路由到各自的数据管线

## User Stories

1. As a 运营主管, I want to 拖入所有人的利润统计Excel, so that 看到全团队商品聚类和选品铁律
2. As a 运营主管, I want to 拖入所有人的店铺数据记录Excel, so that 对比各店铺ROAS、转化率、花费效率
3. As a 运营主管, I want to 一次拖入多个文件混合上传, so that 系统自动分类不混淆
4. As a 运营主管, I want to 看多日店铺数据趋势, so that 判断投放效果是否在恶化
5. As a 运营主管, I want to 导出分析报告, so that 发给老板

## Implementation Decisions

- **Module: StoreDataPipeline** — 独立deep module，单一接口 `analyze(files) → {stores, dailyRecords, trends}`
- **Module: ProductDataPipeline** — 现有DataPipeline.analyze() 保持不变
- **File routing**: 检测表头含`店铺名称`→StoreDataPipeline，含`商品SPU ID`→ProductDataPipeline
- **店铺数据解析**: .xlsx格式row1=日期序列号(row2=表头)(row3+=数据)，多日堆叠。需解析Excel日期序列号
- **新页面**: 侧边栏新增"🏪 店铺运营"，独立renderer
- **存储**: ST.storeData 存店铺数据，ST.files 仍存商品数据
- **颜色方案**: 复用现有CSS变量，店铺页用蓝绿色调区分

## Testing Decisions

- 上传1个利润统计.xls → 商品画像正常显示
- 上传1个店铺数据.xlsx → 店铺运营正常显示
- 混合上传2个文件 → 两边数据互不污染
- 多日店铺数据 → 趋势图有折线
- 好测试标准：换了Excel格式（列顺序变化）仍能正确解析

## Out of Scope

- .xlsx店铺数据记录中"备注"列的语义分析
- 多店铺数据导出PDF
- 店铺数据与商品数据的交叉关联分析

## Further Notes

数据模型参考: D:\我的文学\temu-pud定制\数据模型.md
店铺数据.xlsx每行一个店铺一天的数据，多天数据垂直堆叠。
