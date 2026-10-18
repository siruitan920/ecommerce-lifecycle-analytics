# 数据字典

数仓文件：`data/warehouse/warehouse.duckdb`（由 `pipeline/transform.py` 生成，不随仓库提交）。
各表建表语句在 `sql/`，文件编号即执行顺序。

| 层 | 含义 |
|---|---|
| ODS | 原始数据，只转类型 |
| DWD | 清洗后的明细 |
| DIM | 维度表 |
| DWS | 按主题汇总的中间层（用户×日、用户画像…） |
| ADS | 直接给看板和分析用的指标表 |

---

## ODS

### ods_events（视图）
粒度：原始文件中的一行。来源：`data/warehouse/ods_events_2019-10.parquet`、`ods_events_2019-11.parquet`。

| 字段 | 类型 | 说明 |
|---|---|---|
| event_time_utc | TIMESTAMP | 事件时间（UTC） |
| event_type | VARCHAR | view / cart / purchase（这两个月没有 remove_from_cart） |
| product_id | BIGINT | 商品 ID |
| category_id | BIGINT | 品类 ID |
| category_code | VARCHAR | 品类编码，如 `electronics.smartphone`；32% 为空 |
| brand | VARCHAR | 品牌（小写）；14% 为空 |
| price | DOUBLE | 商品价格，原始价格单位 |
| user_id | BIGINT | 用户永久 ID |
| user_session | VARCHAR | 会话 ID，用户长时间离开后再来会换新的 |

## DWD

### dwd_events
粒度：一次去重后的用户行为事件。主键：无（完全去重后的行）。

| 字段 | 类型 | 说明 |
|---|---|---|
| event_time | TIMESTAMP | 本地时间（UTC+3） |
| event_date | DATE | 本地日期，范围 2019-10-01 ~ 2019-11-30 |
| event_hour | BIGINT | 本地小时 0–23 |
| event_type | VARCHAR | 同 ODS |
| user_id | BIGINT | |
| user_session | VARCHAR | |
| product_id | BIGINT | |
| category_id | BIGINT | |
| category_l1 | VARCHAR | 一级品类（category_code 第一段），缺失为 `unknown` |
| category_code | VARCHAR | 缺失为 `unknown` |
| brand | VARCHAR | 缺失为 `unknown` |
| price | DOUBLE | |

### dwd_orders
粒度：一笔订单。主键：(user_id, order_id)。

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | BIGINT | |
| order_id | VARCHAR | = user_session；session 为空时用「时间+商品」生成 |
| order_time | TIMESTAMP | 订单内第一条 purchase 的时间 |
| order_date | DATE | |
| items | BIGINT | 件数 = purchase 事件数 |
| gmv | DOUBLE | 订单金额 |
| category_cnt | BIGINT | 订单涉及的一级品类数 |

## DIM

### dim_product
粒度：一个商品。主键：product_id。

| 字段 | 类型 | 说明 |
|---|---|---|
| product_id | BIGINT | |
| category_code / category_l1 / brand | VARCHAR | 取出现次数最多的非空值 |
| median_price | DOUBLE | 价格中位数 |
| views / purchases | BIGINT | 浏览、购买次数 |

## DWS

### dws_user_daily
粒度：用户 × 本地自然日（当天至少一条事件）。主键：(user_id, event_date)。

| 字段 | 类型 | 说明 |
|---|---|---|
| events / views / carts / purchase_items | BIGINT | 当天各类事件数 |
| sessions | BIGINT | 当天 session 数 |
| orders | BIGINT | 当天订单数 |
| gmv | DOUBLE | 当天 GMV |

### dws_user_profile
粒度：一个用户（全窗口）。主键：user_id。

| 字段 | 类型 | 说明 |
|---|---|---|
| first_seen_date / last_seen_date | DATE | 窗口内首次 / 最近一次活跃 |
| active_days | BIGINT | 活跃天数 |
| total_events / total_sessions / total_orders | HUGEINT | 累计值 |
| total_gmv | DOUBLE | 累计 GMV |
| first_order_date | DATE | 首次下单日，没下过单为空 |

### dws_user_visit_interval
粒度：用户的一个活跃日。主键：(user_id, event_date)。**滚动快照的核心表**：
任意评估日 d，用户的状态 = 满足 `event_date <= d < next_active_date` 的那一行。

| 字段 | 类型 | 说明 |
|---|---|---|
| event_date | DATE | 活跃日 |
| next_active_date | DATE | 下一次活跃日，没有为空 |
| cum_events / cum_active_days / cum_gmv | | 截至该活跃日的累计值 |
| first_seen_date | DATE | 窗口内首次出现日 |

### dws_user_lifecycle
粒度：一个用户在 2019-11-30 的快照。主键：user_id。包含 `dws_user_profile` 全部字段，另加：

| 字段 | 类型 | 说明 |
|---|---|---|
| tenure_days | BIGINT | 11-30 距首次出现的天数 |
| recency_days | BIGINT | 11-30 距最近一次活跃的天数 |
| stage | VARCHAR | 生命周期分层（宏 `lifecycle_stage`） |
| events_per_active_day | DOUBLE | 活跃日人均事件 |
| intensity_pct | DOUBLE | 层内按 total_events 降序的百分位，< 0.3 即层内前 30% |

## ADS

### ads_daily_metrics
粒度：一个本地自然日。看板「总览」「异常归因」的数据源。

| 字段 | 说明 |
|---|---|
| dau / wau / mau / new_users | 见指标口径 |
| sessions / events / views / carts / purchase_items | 当天合计 |
| view_users / cart_users / buyers | 当天有浏览 / 加购 / 下单的用户数 |
| orders / gmv | |
| aov / buyer_conversion / orders_per_buyer | GMV 拆解的三个因子 |
| view_to_cart_rate / cart_to_buy_rate / dau_wau_ratio | |
| wau_complete / mau_complete | 滚动窗口是否完整 |

### ads_daily_category
粒度：一级品类 × 本地自然日。字段：active_users、view_users、cart_users、buyers、views、carts、purchase_items、gmv。

### ads_retention_cohort
粒度：cohort 日（首次出现日）× 第 N 天（1–30）。只保留观察期完整的格子。

| 字段 | 说明 |
|---|---|
| cohort_date / cohort_week | 首次出现日 / 所在周（周一） |
| cohort_size | cohort 人数 |
| retained_users | 第 N 天当天回来的人数 |
| returned_within_users | 第 1~N 天内回来过的人数 |

### ads_lifecycle_daily
粒度：快照日（10-31 ~ 11-30）× 分层。字段：users、user_share、avg_events、avg_active_days、hist_gmv。

### ads_hourly_events
粒度：一个本地小时。字段：events、views、carts、purchases、users、events_vs_last_week、purchases_vs_last_week（与上周同一小时之比）。数据质量监控用。
