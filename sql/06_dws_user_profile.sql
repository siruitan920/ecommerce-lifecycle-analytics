-- DWS 层：用户画像（全窗口）
-- 粒度：一行 = 一个用户
-- 注意：窗口从 10-01 开始，10 月初「首次出现」的用户可能在 9 月就来过（左截断），
--      所以 first_seen_date 是「窗口内首次出现」，不等于真实注册/首访日期
CREATE OR REPLACE TABLE dws_user_profile AS
SELECT
    user_id,
    MIN(event_date)                                AS first_seen_date,
    MAX(event_date)                                AS last_seen_date,
    COUNT(*)                                       AS active_days,
    SUM(events)                                    AS total_events,
    SUM(sessions)                                  AS total_sessions,
    SUM(orders)                                    AS total_orders,
    SUM(gmv)                                       AS total_gmv,
    MIN(event_date) FILTER (WHERE orders > 0)      AS first_order_date
FROM dws_user_daily
GROUP BY user_id;
