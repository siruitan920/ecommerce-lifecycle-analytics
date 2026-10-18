-- ODS 层：原始行为日志（两个月 Parquet 的视图，未做任何清洗）
-- 粒度：一行 = 原始文件中的一行事件
CREATE OR REPLACE VIEW ods_events AS
SELECT * FROM read_parquet({{ODS_FILES}});
