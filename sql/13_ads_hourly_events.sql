-- ADS 层：小时级事件量（数据质量监控与看板「数据质量」页的数据源）
-- 粒度：一行 = 一个本地小时
-- purchase_vs_last_week：与上周同一小时相比的倍数，用来发现埋点中断
CREATE OR REPLACE TABLE ads_hourly_events AS
WITH h AS (
    SELECT
        date_trunc('hour', event_time)                    AS event_hour_ts,
        COUNT(*)                                          AS events,
        COUNT(*) FILTER (WHERE event_type = 'view')       AS views,
        COUNT(*) FILTER (WHERE event_type = 'cart')       AS carts,
        COUNT(*) FILTER (WHERE event_type = 'purchase')   AS purchases,
        COUNT(DISTINCT user_id)                           AS users
    FROM dwd_events
    GROUP BY 1
)
SELECT
    a.*,
    a.events    * 1.0 / NULLIF(b.events, 0)    AS events_vs_last_week,
    a.purchases * 1.0 / NULLIF(b.purchases, 0) AS purchases_vs_last_week
FROM h a
LEFT JOIN h b ON b.event_hour_ts = a.event_hour_ts - INTERVAL 7 DAY
ORDER BY 1;
