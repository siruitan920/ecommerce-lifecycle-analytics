# 电商用户生命周期分析：从行为日志到召回策略

用一家海外多品类电商平台 2019 年 10–11 月的 **1.1 亿条用户行为日志**（530 万用户），完整走一遍
**数据获取 → 分层数仓 → 数据质量检查 → 指标体系与看板 → 专题分析 → 实验设计**。

核心问题：**在一个低频、高客单价的平台上，哪些沉默用户值得召回、什么时候召回、值多少钱、怎么验证。**

**[→ 打开指标看板](https://siruitan920.github.io/ecommerce-lifecycle-analytics/)**　·　[分析 notebook](notebooks/)　·　[指标口径](docs/metrics_system.md)　·　[数据质量报告](docs/data_quality_report.md)

---

## 主要发现

**1. 数据质量：大促期间 purchase 事件丢失了 48 小时，有几条看似合理的结论因此不成立**

11-15 这天 DAU 38 万、GMV 为 0。按小时拆开排查：购买量整点归零、整点恢复，浏览和加购正常；
恢复后的购买没有一条属于前两天的 session（是丢失，不是延迟上报）；中断期重复加购的比例与正常日一致（没有被误记成加购）。
结论是 purchase 埋点中断，而不是业务问题。忽略这一点会得出「大促前段只加购不下单」「周五加购转化只有 25%」这类假结论。
→ [notebook 01](notebooks/01_data_quality_and_pipeline.ipynb)

**2. 这是一个周频平台，流失不能按日频的标准定义**

平日 DAU/WAU ≈ 20%，一半用户两个月里只来过 1 天。新用户第 7 天当天回来的只有 4%，但 7 天内回来过的有 25%、30 天内 48%。
→ [notebook 02](notebooks/02_platform_overview_and_metrics.ipynb)、[03](notebooks/03_lifecycle_segmentation.ipynb)

**3. 把 GMV 拆成四个因子，能看到单看 GMV 看不到的东西**

`GMV = DAU × 下单转化率 × 人均订单 × 客单价`，按对数拆解归因。大促前两周 DAU +13%、转化率 −14%、GMV −2%：
流量和转化反向抵消，用户在等大促；大促当天 GMV 是基线的 8 倍，主要靠转化率（约 3.8 倍），不是流量。
→ [notebook 02](notebooks/02_platform_overview_and_metrics.ipynb)、看板「异常归因」

**4. 最值得召回的是「早期风险 × 高强度」用户，最佳触达时机是沉默第 6–8 天**

- 早期风险层（沉默 8–14 天）占用户 19%，贡献 23% 的历史 GMV；风险层内前 30% 的用户贡献了 83% 的行为；
- 滚动快照验证：早期风险层前 30% 的用户 7 天自然回流率 32%，同层后 70% 只有 14.5%；逻辑回归显示沉默时长和历史强度各自独立起作用；
- 带删失的回访风险函数显示：高强度用户沉默第 6 天以后，每多等一天回来的概率只再降不到 1 个百分点——更早触达会浪费在本来就会回来的人身上。

→ [notebook 03](notebooks/03_lifecycle_segmentation.ipynb)、[04](notebooks/04_return_prediction_and_timing.ipynb)

**5. 召回值得做，但只值得用便宜的方式做；实验 1 天就有足够样本**

每多召回一个高价值风险用户，14 天增量 GMV 约 59 个价格单位；即使触达能把回流率提高 10 个百分点，每触达一人的增量 GMV 也只有 3–6。
Push、站内信可行，发券要用实测效果核算。实验方案以 7 天回流率为主指标：检测 +2 个百分点每组需要 9,335 人，约 1 天的流量；
GMV 方差太大（标准差是均值 11 倍），截尾后作次指标和护栏。上线前在真实数据上做了 500 次 A/A 检验，假阳性率 4.8%。
→ [notebook 05](notebooks/05_value_and_ab_test_design.ipynb)、[实验方案](docs/ab_test_plan.md)

**6. 大促把沉默用户拉回来了，但没留住**

大促三天，早期风险层的到访率是平时的 1.65 倍，相对拉动最大；但大促到访的老用户之后 7 天再来的比例比平时低 7–13 个百分点，
大促一周后健康层成批滑入早期风险。大促后一周 GMV 没有下降，看不到透支。
→ [notebook 06](notebooks/06_campaign_review.ipynb)

---

## 项目结构

```
├── pipeline/                  数据管道（按顺序执行）
│   ├── download.py            从 Kaggle API 下载原始数据（4.6GB，支持断点续传）
│   ├── ingest.py              CSV → ODS 层 Parquet（逐月流式转换，不落 14.7GB 明文）
│   ├── transform.py           执行 sql/ 建 DWD / DIM / DWS / ADS 各层
│   ├── quality_checks.py      25 项数据质量检查 → docs/data_quality_report.md
│   ├── export_dashboard.py    ADS 层 → dashboard/data/*.json
│   └── config.py              时区、大促窗口等口径参数（唯一来源）
├── sql/                       分层建表 SQL，00_macros.sql 定义生命周期分层宏
├── notebooks/                 7 个专题分析（已执行，输出保存在文件里）
├── dashboard/                 静态指标看板（GitHub Pages）
└── docs/
    ├── metrics_system.md      指标体系与口径
    ├── data_dictionary.md     数据字典
    ├── tracking_plan.md       埋点需求与监控规则
    ├── ab_test_plan.md        召回实验方案
    └── data_quality_report.md 数据质量报告（自动生成）
```

### 数据分层

| 层 | 表 | 粒度 |
|---|---|---|
| ODS | `ods_events` | 原始事件（1.1 亿行） |
| DWD | `dwd_events`、`dwd_orders` | 去重、转本地时区后的事件；订单 |
| DIM | `dim_product` | 商品 |
| DWS | `dws_user_daily`、`dws_user_profile`、`dws_user_visit_interval`、`dws_user_lifecycle` | 用户×日、用户画像、访问间隔、生命周期快照 |
| ADS | `ads_daily_metrics`、`ads_daily_category`、`ads_retention_cohort`、`ads_lifecycle_daily`、`ads_hourly_events` | 看板与分析直接使用 |

`dws_user_visit_interval` 给每个用户的每个活跃日附上「下一次活跃日」和截至当天的累计行为。
任意一天的 recency、生命周期分层、WAU/MAU 都可以用一次区间连接得到，不必对 1 亿条事件反复扫描——
61 天的滚动 WAU/MAU、31 个快照日的生命周期结构，在 DuckDB 里各自 2 秒左右算完。

## 分析目录

| notebook | 问题 | 方法 |
|---|---|---|
| [01 数据管道与数据质量](notebooks/01_data_quality_and_pipeline.ipynb) | 数据能不能信？ | 时区推断、埋点中断定位、自动化质量检查 |
| [02 平台总览与核心指标](notebooks/02_platform_overview_and_metrics.ipynb) | 平台平时长什么样？GMV 为什么波动？ | DAU/WAU/MAU、GMV 四因子对数拆解 |
| [03 生命周期分层](notebooks/03_lifecycle_segmentation.ipynb) | 用户处在什么状态？谁值得召回？ | recency 分层、帕累托、秩相关稳健性检验、cohort 留存 |
| [04 回流预测与触达时机](notebooks/04_return_prediction_and_timing.ipynb) | 谁会自己回来？什么时候出手？ | 滚动快照、Wilson 置信区间、逻辑回归、带删失的离散时间风险函数 |
| [05 召回价值与实验设计](notebooks/05_value_and_ab_test_design.ipynb) | 值多少钱？怎么验证？ | 盈亏平衡测算、功效分析、截尾与 CUPED、A/A 检验 |
| [06 大促复盘](notebooks/06_campaign_review.ipynb) | 大促拉来了谁、留下了吗？ | 分层到访率对比、到访后留存、透支检验 |
| [07 时段与星期](notebooks/07_time_of_day_and_weekday.ipynb) | 什么时候推送？ | 加购后 24 小时购买率、同一用户内比较 |

## 如何复现

```bash
pip install -r requirements.txt
make all          # 下载 → 入库 → 建表 → 质检 → 导出看板数据 → 重跑 notebook
```

或分步：

```bash
python pipeline/download.py        # 约 4.6GB
python pipeline/ingest.py          # 转成 Parquet（约 1.8GB）后删除压缩包
python pipeline/transform.py       # 约 4 分钟，DuckDB 库约 5.3GB（16GB 内存的笔记本）
python pipeline/quality_checks.py
python pipeline/export_dashboard.py
python -m http.server -d dashboard 8000   # 本地打开看板
```

技术栈：Python（pandas、NumPy、statsmodels、scikit-learn、SciPy）、SQL（DuckDB）、ECharts。

## 数据与局限

- **数据来源**：Kaggle [eCommerce behavior data from multi category store](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store)，
  由 [REES46 Marketing Platform](https://rees46.com) 提供。仓库不包含原始数据，看板只包含聚合后的指标；
- **金额单位**：数据集没有注明币种，金额一律为原始价格单位；
- **时区**：数据集只说明是 UTC，店铺时区（UTC+3）是按流量曲线推断的；
- **窗口只有两个月**：存在左截断（10 月初的新用户混有老用户）和右截断，长期复购、LTV 无法评估；
- **没有渠道、推送、成本数据**：召回效果和 ROI 只能推断，需要实验验证；需要补的埋点见 [tracking_plan.md](docs/tracking_plan.md)。

---

## English summary

An end-to-end analytics project on 110M behavioral events (5.3M users, Oct–Nov 2019) from a multi-category e-commerce platform.
It builds a layered DuckDB warehouse (ODS → DWD → DWS → ADS) with 25 automated data-quality checks, a metric system with a
static dashboard, and seven analysis notebooks.

Key results: (1) a 48-hour loss of purchase events during the November sale was detected and diagnosed (lost, not delayed),
which invalidated several plausible-looking conclusions; (2) the platform is weekly- rather than daily-use (DAU/WAU ≈ 0.20);
(3) a log decomposition of GMV into traffic, conversion, orders per buyer and order value explains daily anomalies;
(4) rolling-snapshot validation and a censored discrete-time hazard model show that high-intensity users at 8–14 days of
silence are the best re-engagement target, with an estimated contact window of days 6–8; (5) a re-engagement A/B test is
designed with power analysis, variance reduction (winsorization, CUPED) and an A/A check on real data.
