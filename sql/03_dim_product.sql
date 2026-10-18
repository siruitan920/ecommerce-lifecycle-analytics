-- DIM 层：商品维表
-- 粒度：一行 = 一个 product_id
-- 同一商品在日志里的品类/品牌偶有缺失，取出现次数最多的非 unknown 值
CREATE OR REPLACE TABLE dim_product AS
SELECT
    product_id,
    COALESCE(mode(category_code) FILTER (WHERE category_code <> 'unknown'), 'unknown') AS category_code,
    COALESCE(mode(category_l1)   FILTER (WHERE category_l1   <> 'unknown'), 'unknown') AS category_l1,
    COALESCE(mode(brand)         FILTER (WHERE brand         <> 'unknown'), 'unknown') AS brand,
    median(price)                                                                       AS median_price,
    COUNT(*) FILTER (WHERE event_type = 'view')                                         AS views,
    COUNT(*) FILTER (WHERE event_type = 'purchase')                                     AS purchases
FROM dwd_events
GROUP BY product_id;
