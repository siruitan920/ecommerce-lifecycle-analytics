-- DWD 层：清洗后的事件明细
-- 粒度：一行 = 一次去重后的用户行为事件
-- 清洗规则（每条规则剔除了多少行见 docs/data_quality_report.md）：
--   1. 完全重复的行只保留一条（同一用户、同一秒、同一商品、同一事件、同一 session）
--   2. 剔除 user_id / event_time 为空的行
--   3. 时间从 UTC 转为店铺本地时间（UTC+{{TZ}}），业务日期按本地时间切分
--   4. 只保留本地日期落在 {{START}} ~ {{END}} 的事件（时区平移后 12-01 凌晨会多出 3 小时，剔除）
--   5. 品类拆成一级/二级，缺失记为 'unknown'；品牌缺失记为 'unknown'
CREATE OR REPLACE TABLE dwd_events AS
WITH dedup AS (
    SELECT DISTINCT
        event_time_utc, event_type, product_id, category_id,
        category_code, brand, price, user_id, user_session
    FROM ods_events
    WHERE user_id IS NOT NULL
      AND event_time_utc IS NOT NULL
)
SELECT
    event_time_utc + INTERVAL {{TZ}} HOUR                       AS event_time,
    CAST(event_time_utc + INTERVAL {{TZ}} HOUR AS DATE)         AS event_date,
    HOUR(event_time_utc + INTERVAL {{TZ}} HOUR)                 AS event_hour,
    event_type,
    user_id,
    user_session,
    product_id,
    category_id,
    COALESCE(split_part(category_code, '.', 1), 'unknown')      AS category_l1,
    COALESCE(category_code, 'unknown')                          AS category_code,
    COALESCE(brand, 'unknown')                                  AS brand,
    price
FROM dedup
WHERE CAST(event_time_utc + INTERVAL {{TZ}} HOUR AS DATE) BETWEEN DATE '{{START}}' AND DATE '{{END}}';
