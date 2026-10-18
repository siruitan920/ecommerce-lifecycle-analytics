-- ADS 层：生命周期结构日快照（看板「生命周期」页的数据源）
-- 粒度：一行 = 一个快照日 × 一个生命周期分层
-- 快照日从窗口第 31 天开始：此前看不到「沉默 30 天以上」，long_lapsed 会被低估
CREATE OR REPLACE TABLE ads_lifecycle_daily AS
WITH snap AS (
    SELECT CAST(generate_series AS DATE) AS snapshot_date
    FROM generate_series(DATE '{{START}}' + 30, DATE '{{END}}', INTERVAL 1 DAY)
),
user_state AS (
    SELECT
        s.snapshot_date,
        lifecycle_stage(s.snapshot_date - v.first_seen_date, s.snapshot_date - v.event_date) AS stage,
        v.cum_events,
        v.cum_active_days,
        v.cum_gmv
    FROM snap s
    JOIN dws_user_visit_interval v
      ON v.event_date <= s.snapshot_date
     AND (v.next_active_date IS NULL OR v.next_active_date > s.snapshot_date)
)
SELECT
    snapshot_date,
    stage,
    COUNT(*)                                        AS users,
    COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY snapshot_date) AS user_share,
    AVG(cum_events)                                 AS avg_events,
    AVG(cum_active_days)                            AS avg_active_days,
    SUM(cum_gmv)                                    AS hist_gmv
FROM user_state
GROUP BY snapshot_date, stage;
