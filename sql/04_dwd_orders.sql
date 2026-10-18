-- DWD 层：订单明细
-- 粒度：一行 = 一笔订单
-- 口径：数据集说明「同一 session 内的多条 purchase 是同一笔订单」，
--      所以订单 = 有 purchase 事件的 (user_id, user_session)；
--      件数 = purchase 事件数；GMV = purchase 事件的 price 之和（原始价格单位，数据集未注明币种）
--      user_session 缺失的 purchase 各自算一笔订单
CREATE OR REPLACE TABLE dwd_orders AS
SELECT
    user_id,
    COALESCE(user_session, 'nosession_' || CAST(event_time AS VARCHAR) || '_' || CAST(product_id AS VARCHAR)) AS order_id,
    MIN(event_time)              AS order_time,
    CAST(MIN(event_time) AS DATE) AS order_date,
    COUNT(*)                     AS items,
    SUM(price)                   AS gmv,
    COUNT(DISTINCT category_l1)  AS category_cnt
FROM dwd_events
WHERE event_type = 'purchase'
GROUP BY 1, 2;
