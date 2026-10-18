-- DWS 层：用户访问间隔
-- 粒度：一行 = 一个用户的一个活跃日，附带「下一次活跃日」和截至当天的累计行为
-- 用途：滚动快照（任一评估日的 recency、历史强度）、回访间隔/风险函数、生命周期日快照
CREATE OR REPLACE TABLE dws_user_visit_interval AS
SELECT
    user_id,
    event_date,
    LEAD(event_date) OVER w                                    AS next_active_date,
    SUM(events) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_events,
    COUNT(*)    OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_active_days,
    SUM(gmv)    OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_gmv,
    MIN(event_date) OVER (PARTITION BY user_id)                AS first_seen_date
FROM dws_user_daily
WINDOW w AS (PARTITION BY user_id ORDER BY event_date);
