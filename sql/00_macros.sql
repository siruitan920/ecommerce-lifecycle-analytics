-- 全项目共用的口径，只在这里定义一次（DuckDB 宏随库文件持久化，SQL 和 notebook 都调用它）

-- 生命周期分层（基于 recency，适配周频、低频高客单的使用节律）
--   tenure_days  = 评估日 - 窗口内首次出现日
--   recency_days = 评估日 - 最近一次活跃日（0 = 评估日当天活跃）
CREATE OR REPLACE MACRO lifecycle_stage(tenure_days, recency_days) AS
    CASE
        WHEN tenure_days  <= 6  THEN 'new'           -- 7 天内首次出现
        WHEN recency_days <= 7  THEN 'healthy'       -- 7 天内活跃过
        WHEN recency_days <= 14 THEN 'early_risk'    -- 沉默 8–14 天
        WHEN recency_days <= 30 THEN 'accelerating'  -- 沉默 15–30 天
        ELSE 'long_lapsed'                           -- 沉默 30 天以上
    END;

-- 分层的展示顺序
CREATE OR REPLACE MACRO stage_order(stage) AS
    CASE stage
        WHEN 'new' THEN 1 WHEN 'healthy' THEN 2 WHEN 'early_risk' THEN 3
        WHEN 'accelerating' THEN 4 WHEN 'long_lapsed' THEN 5
    END;
