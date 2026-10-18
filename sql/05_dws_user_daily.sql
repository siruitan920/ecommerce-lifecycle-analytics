-- DWS 层：用户 × 日 汇总
-- 粒度：一行 = 一个用户在一个本地自然日的行为汇总（当天至少有一条事件）
CREATE OR REPLACE TABLE dws_user_daily AS
WITH ev AS (
    SELECT
        user_id,
        event_date,
        COUNT(*)                                        AS events,
        COUNT(*) FILTER (WHERE event_type = 'view')     AS views,
        COUNT(*) FILTER (WHERE event_type = 'cart')     AS carts,
        COUNT(*) FILTER (WHERE event_type = 'purchase') AS purchase_items,
        COUNT(DISTINCT user_session)                    AS sessions
    FROM dwd_events
    GROUP BY user_id, event_date
),
od AS (
    SELECT user_id, order_date AS event_date, COUNT(*) AS orders, SUM(gmv) AS gmv
    FROM dwd_orders
    GROUP BY 1, 2
)
SELECT
    ev.*,
    COALESCE(od.orders, 0) AS orders,
    COALESCE(od.gmv, 0)    AS gmv
FROM ev
LEFT JOIN od USING (user_id, event_date);
