-- ADS 层：新用户留存（按窗口内首次出现日分 cohort）
-- 粒度：一行 = 一个 cohort 日 × 第 N 天（N = 1..30）
--   retained_users       ：第 N 天当天活跃的人数（经典 DN 留存）
--   returned_within_users：第 1..N 天内回访过至少一次的人数（周频平台更有意义的口径）
-- 只保留观察期完整的格子（cohort 日 + N <= 窗口结束日）
CREATE OR REPLACE TABLE ads_retention_cohort AS
WITH cohort AS (
    SELECT user_id, first_seen_date FROM dws_user_profile
),
activity AS (
    SELECT c.first_seen_date, u.event_date - c.first_seen_date AS day_n, c.user_id
    FROM cohort c
    JOIN dws_user_daily u USING (user_id)
    WHERE u.event_date > c.first_seen_date
      AND u.event_date - c.first_seen_date <= 30
),
first_return AS (
    SELECT first_seen_date, user_id, MIN(day_n) AS first_return_day
    FROM activity
    GROUP BY 1, 2
),
day_n AS (SELECT CAST(range AS INTEGER) AS day_n FROM range(1, 31)),
sizes AS (SELECT first_seen_date, COUNT(*) AS cohort_size FROM cohort GROUP BY 1),
on_day AS (SELECT first_seen_date, day_n, COUNT(*) AS users FROM activity GROUP BY 1, 2),
within AS (
    SELECT s.first_seen_date, d.day_n, COUNT(f.user_id) AS users
    FROM sizes s
    CROSS JOIN day_n d
    LEFT JOIN first_return f
      ON f.first_seen_date = s.first_seen_date AND f.first_return_day <= d.day_n
    GROUP BY 1, 2
)
SELECT
    s.first_seen_date                      AS cohort_date,
    date_trunc('week', s.first_seen_date)  AS cohort_week,
    s.cohort_size,
    d.day_n,
    COALESCE(o.users, 0)                   AS retained_users,
    w.users                                AS returned_within_users
FROM sizes s
CROSS JOIN day_n d
LEFT JOIN on_day o ON o.first_seen_date = s.first_seen_date AND o.day_n = d.day_n
LEFT JOIN within w ON w.first_seen_date = s.first_seen_date AND w.day_n = d.day_n
WHERE s.first_seen_date + d.day_n <= DATE '{{END}}';
