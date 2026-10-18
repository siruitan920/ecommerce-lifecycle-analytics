-- ADS 层：品类 × 日 指标（看板品类筛选、「品类表现」页的数据源）
-- 粒度：一行 = 一个一级品类在一个本地自然日
-- 一笔订单可能跨品类，所以品类层面只给件数和 GMV，不给订单数
CREATE OR REPLACE TABLE ads_daily_category AS
SELECT
    event_date,
    category_l1,
    COUNT(DISTINCT user_id)                                           AS active_users,
    COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'view')        AS view_users,
    COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'cart')        AS cart_users,
    COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'purchase')    AS buyers,
    COUNT(*) FILTER (WHERE event_type = 'view')                       AS views,
    COUNT(*) FILTER (WHERE event_type = 'cart')                       AS carts,
    COUNT(*) FILTER (WHERE event_type = 'purchase')                   AS purchase_items,
    COALESCE(SUM(price) FILTER (WHERE event_type = 'purchase'), 0)    AS gmv
FROM dwd_events
GROUP BY event_date, category_l1;
