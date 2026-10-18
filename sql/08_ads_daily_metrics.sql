-- ADS 层：核心指标日表（看板「总览」「异常归因」页的数据源）
-- 粒度：一行 = 一个本地自然日
-- WAU / MAU 用「最近一次活跃日落在窗口内」判定：每个 (用户, 日期) 恰好对应
-- dws_user_visit_interval 里的一行，所以不需要 COUNT(DISTINCT)
CREATE OR REPLACE TABLE ads_daily_metrics AS
WITH base AS (
    SELECT
        event_date,
        COUNT(*)                            AS dau,
        SUM(sessions)                       AS sessions,
        SUM(events)                         AS events,
        SUM(views)                          AS views,
        SUM(carts)                          AS carts,
        SUM(purchase_items)                 AS purchase_items,
        COUNT(*) FILTER (WHERE views > 0)   AS view_users,
        COUNT(*) FILTER (WHERE carts > 0)   AS cart_users,
        COUNT(*) FILTER (WHERE orders > 0)  AS buyers,
        SUM(orders)                         AS orders,
        SUM(gmv)                            AS gmv
    FROM dws_user_daily
    GROUP BY event_date
),
new_users AS (
    SELECT first_seen_date AS event_date, COUNT(*) AS new_users
    FROM dws_user_profile
    GROUP BY 1
),
rolling AS (
    SELECT
        d.event_date,
        COUNT(*) FILTER (WHERE d.event_date - v.event_date <= 6)  AS wau,
        COUNT(*) FILTER (WHERE d.event_date - v.event_date <= 29) AS mau
    FROM base d
    JOIN dws_user_visit_interval v
      ON v.event_date <= d.event_date
     AND (v.next_active_date IS NULL OR v.next_active_date > d.event_date)
     AND d.event_date - v.event_date <= 29
    GROUP BY d.event_date
)
SELECT
    b.*,
    n.new_users,
    r.wau,
    r.mau,
    b.gmv / NULLIF(b.orders, 0)              AS aov,                 -- 客单价
    b.buyers * 1.0 / b.dau                   AS buyer_conversion,    -- 下单转化率（下单用户 / DAU）
    b.orders * 1.0 / NULLIF(b.buyers, 0)     AS orders_per_buyer,
    b.cart_users * 1.0 / NULLIF(b.view_users, 0) AS view_to_cart_rate,
    b.buyers * 1.0 / NULLIF(b.cart_users, 0)     AS cart_to_buy_rate,
    b.dau * 1.0 / r.wau                      AS dau_wau_ratio,
    b.event_date >= DATE '{{START}}' + 6     AS wau_complete,       -- 窗口前 6 天 WAU 不完整
    b.event_date >= DATE '{{START}}' + 29    AS mau_complete
FROM base b
LEFT JOIN new_users n USING (event_date)
LEFT JOIN rolling r USING (event_date)
ORDER BY event_date;
