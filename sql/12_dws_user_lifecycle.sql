-- DWS 层：窗口末（{{END}}）的用户生命周期快照
-- 粒度：一行 = 一个用户
-- intensity_pct：在同一分层内按历史事件数排序的百分位（0 = 最强），用于圈定「高价值风险用户」
CREATE OR REPLACE TABLE dws_user_lifecycle AS
WITH s AS (
    SELECT
        p.*,
        DATE '{{END}}' - p.first_seen_date AS tenure_days,
        DATE '{{END}}' - p.last_seen_date  AS recency_days
    FROM dws_user_profile p
)
SELECT
    s.*,
    lifecycle_stage(tenure_days, recency_days)                         AS stage,
    total_events * 1.0 / active_days                                   AS events_per_active_day,
    PERCENT_RANK() OVER (
        PARTITION BY lifecycle_stage(tenure_days, recency_days)
        ORDER BY total_events DESC
    )                                                                  AS intensity_pct
FROM s;
