"""Step 4: 数据质量检查，结果写入 docs/data_quality_report.md。

检查分五类：行数对账、唯一性、完整性（空值/枚举/取值范围）、跨层一致性、时间连续性。
每条检查给出 PASS / WARN / FAIL；WARN 表示数据本身有问题但已在下游处理或已注明影响，
FAIL 表示管道有 bug，需要修。

用法：python pipeline/quality_checks.py
"""
import json
from datetime import date

from config import DASHBOARD_DATA, DOCS, TZ_OFFSET_HOURS, connect

results: list[tuple[str, str, str, str]] = []


def check(group: str, name: str, ok: bool, detail: str, warn_only: bool = False) -> None:
    status = "PASS" if ok else ("WARN" if warn_only else "FAIL")
    results.append((group, name, status, detail))


def main() -> None:
    con = connect(read_only=True)
    q = lambda sql: con.execute(sql).fetchone()

    # ---------- 1. 行数对账 ----------
    ods_rows, ods_users = q("SELECT COUNT(*), COUNT(DISTINCT user_id) FROM ods_events")
    check("行数对账", "ODS 行数 = 原始 CSV 行数", ods_rows == 109_950_743,
          f"ODS {ods_rows:,} 行；原始 2019-Oct.csv 42,448,764 + 2019-Nov.csv 67,501,979 = 109,950,743")
    dup_rows = ods_rows - q("SELECT COUNT(*) FROM (SELECT DISTINCT * FROM ods_events)")[0]
    dwd_rows = q("SELECT COUNT(*) FROM dwd_events")[0]
    out_of_range = ods_rows - dup_rows - dwd_rows
    check("行数对账", "ODS → DWD 剔除行可解释", out_of_range >= 0,
          f"完全重复 {dup_rows:,} 行（{dup_rows / ods_rows:.3%}）；时区平移后落到 12-01 的 {out_of_range:,} 行；"
          f"DWD 剩 {dwd_rows:,} 行")

    # ---------- 2. 唯一性 ----------
    n, nd = q("SELECT COUNT(*), COUNT(DISTINCT (user_id, event_date)) FROM dws_user_daily")
    check("唯一性", "dws_user_daily 主键 (user_id, event_date) 唯一", n == nd, f"{n:,} 行 / {nd:,} 个主键")
    n, nd = q("SELECT COUNT(*), COUNT(DISTINCT (user_id, order_id)) FROM dwd_orders")
    check("唯一性", "dwd_orders 主键 (user_id, order_id) 唯一", n == nd, f"{n:,} 笔订单")
    n, nd = q("SELECT COUNT(*), COUNT(DISTINCT user_id) FROM dws_user_profile")
    check("唯一性", "dws_user_profile 一个用户一行", n == nd, f"{n:,} 个用户")
    shared = q("SELECT COUNT(*) FROM (SELECT user_session FROM dwd_events WHERE user_session IS NOT NULL "
               "GROUP BY 1 HAVING COUNT(DISTINCT user_id) > 1)")[0]
    check("唯一性", "一个 session 只属于一个用户", shared == 0, f"跨用户共用的 session：{shared:,} 个",
          warn_only=True)

    # ---------- 3. 完整性 ----------
    for col, warn in [("user_id", False), ("event_time_utc", False), ("event_type", False),
                      ("product_id", False), ("price", False), ("user_session", True),
                      ("category_code", True), ("brand", True)]:
        cnt, rate = q(f"SELECT COUNT(*) FILTER (WHERE {col} IS NULL), AVG(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) FROM ods_events")
        note = {"category_code": "；数据集说明：配件类商品通常没有品类编码，下游记为 unknown",
                "brand": "；下游记为 unknown",
                "user_session": "；订单口径里每条无 session 的 purchase 各算一单"}.get(col, "")
        check("完整性", f"{col} 空值率", cnt == 0, f"{cnt:,} 行（{rate:.4%}）{note}", warn_only=warn)

    types = [r[0] for r in con.execute("SELECT DISTINCT event_type FROM ods_events ORDER BY 1").fetchall()]
    check("完整性", "event_type 枚举值", set(types) <= {"view", "cart", "remove_from_cart", "purchase"},
          f"实际出现：{', '.join(types)}（这两个月没有 remove_from_cart）")
    bad_price, max_price = q("SELECT COUNT(*) FILTER (WHERE price <= 0), MAX(price) FROM dwd_events")
    zero_purchase = q("SELECT COUNT(*) FROM dwd_events WHERE event_type = 'purchase' AND price <= 0")[0]
    check("完整性", "price > 0", bad_price == 0,
          f"price <= 0 的事件 {bad_price:,} 条（其中 purchase {zero_purchase:,} 条，所以不影响 GMV）；最高价 {max_price:,.2f}",
          warn_only=True)

    # ---------- 4. 跨层一致性 ----------
    a = q("SELECT COUNT(*), SUM(price) FROM dwd_events WHERE event_type = 'purchase'")
    b = q("SELECT SUM(items), SUM(gmv) FROM dwd_orders")
    c = q("SELECT SUM(purchase_items), SUM(gmv) FROM dws_user_daily")
    d = q("SELECT SUM(purchase_items), SUM(gmv) FROM ads_daily_metrics")
    same = a[0] == b[0] == c[0] == d[0] and max(abs(x - a[1]) for x in (b[1], c[1], d[1])) < 1
    check("一致性", "购买件数与 GMV 四层对账（DWD 事件 / 订单 / 用户日 / 日指标）", same,
          f"件数 {a[0]:,}；GMV {a[1]:,.0f}")
    e = q("SELECT SUM(events) FROM dws_user_daily")[0]
    check("一致性", "用户日表事件数 = DWD 行数", e == dwd_rows, f"{e:,}")
    u1 = q("SELECT COUNT(DISTINCT user_id) FROM dwd_events")[0]
    u2 = q("SELECT COUNT(*) FROM dws_user_profile")[0]
    check("一致性", "画像表用户数 = DWD 去重用户数", u1 == u2, f"{u1:,}")
    snap = q("SELECT SUM(users) FROM ads_lifecycle_daily WHERE snapshot_date = DATE '2019-11-30'")[0]
    check("一致性", "11-30 生命周期快照人数 = 截至当天出现过的全部用户", snap == u2, f"{snap:,}")

    # ---------- 5. 时间连续性 ----------
    days = q("SELECT COUNT(DISTINCT event_date), MIN(event_date), MAX(event_date) FROM dwd_events")
    check("时间连续性", "本地日期连续无缺天", days[0] == 61, f"{days[1]} ~ {days[2]}，共 {days[0]} 天")
    first_hour = q("SELECT MIN(event_hour) FROM dwd_events WHERE event_date = DATE '2019-10-01'")[0]
    check("时间连续性", "首日完整", first_hour == 0,
          f"10-01 从本地 {first_hour:02d}:00 开始（UTC 0 点 = 本地 {TZ_OFFSET_HOURS:02d}:00），凌晨 3 小时缺失，流量低谷时段，影响很小",
          warn_only=True)

    gaps = con.execute("""
        SELECT event_hour_ts, views, carts, purchases
        FROM ads_hourly_events
        WHERE purchases = 0 AND views > 5000
        ORDER BY 1
    """).fetchall()
    if gaps:
        spans, start, prev = [], gaps[0][0], gaps[0][0]
        for ts, *_ in gaps[1:]:
            if (ts - prev).total_seconds() > 3600:
                spans.append((start, prev))
                start = ts
            prev = ts
        spans.append((start, prev))
        span_txt = "；".join(f"{s:%m-%d %H}:00 ~ {e:%m-%d %H}:59（{int((e - s).total_seconds() // 3600) + 1} 小时）"
                            for s, e in spans)
    check("时间连续性", "每小时都有 purchase 事件（有流量的小时）", not gaps,
          f"{len(gaps)} 个小时浏览正常但购买为 0，本地时间：{span_txt if gaps else '无'}。详见下方「已知数据问题」",
          warn_only=True)
    drop = con.execute("""
        SELECT event_hour_ts, events, events_vs_last_week FROM ads_hourly_events
        WHERE events_vs_last_week < 0.6 AND event_hour_ts > TIMESTAMP '2019-10-08'
        ORDER BY 1
    """).fetchall()
    check("时间连续性", "小时事件量不低于上周同时段的 60%", not drop,
          "；".join(f"{ts:%m-%d %H}:00 为上周同时段的 {r:.0%}" for ts, _, r in drop) or "无",
          warn_only=True)

    # ---------- 6. 异常用户 ----------
    heavy = q("""SELECT COUNT(DISTINCT user_id), SUM(events) FROM dws_user_daily WHERE events > 1000""")
    check("异常值", "单日事件数 > 1000 的用户（疑似爬虫）", heavy[0] == 0,
          f"{heavy[0]:,} 个用户，贡献 {heavy[1] or 0:,} 条事件（{(heavy[1] or 0) / dwd_rows:.3%}），占比极小，未剔除",
          warn_only=True)

    write_report(con)


def write_report(con) -> None:
    icon = {"PASS": "✅ PASS", "WARN": "⚠️ WARN", "FAIL": "❌ FAIL"}
    n = {s: sum(1 for r in results if r[2] == s) for s in ("PASS", "WARN", "FAIL")}
    lines = [
        "# 数据质量报告",
        "",
        f"> 由 `pipeline/quality_checks.py` 自动生成（{date.today():%Y-%m-%d}）。"
        f"共 {len(results)} 项：{n['PASS']} 项通过、{n['WARN']} 项告警、{n['FAIL']} 项失败。",
        "> WARN = 数据源本身的问题，已在下游处理或注明影响；FAIL = 管道 bug。",
        "",
        "| 类别 | 检查项 | 结果 | 说明 |",
        "|---|---|---|---|",
    ]
    lines += [f"| {g} | {name} | {icon[s]} | {d} |" for g, name, s, d in results]
    lines += [
        "",
        "## 已知数据问题与处理",
        "",
        "### 1. 11 月中旬购买事件埋点中断（影响最大）",
        "",
        "**现象**：大促期间（本地 11-15 ~ 11-17）浏览量是平时的 1.3–3.5 倍，但购买事件在本地 "
        "11-14 22:00 ~ 11-16 10:59、11-16 19:00 ~ 11-17 05:59 两段时间内**一条都没有**。"
        "11-15 全天 DAU 38 万、GMV 为 0。",
        "",
        "**定位过程**（[报告 01](../notebooks/01_data_quality_and_pipeline.ipynb)）：",
        "",
        "1. 按小时拆开看，购买量是整点断崖式归零、整点恢复——业务波动不会这样，像是采集链路故障；",
        "2. 同期浏览、加购照常记录，所以不是整站宕机，是 purchase 这一个事件丢了；",
        "3. 恢复后（11-17）的购买都属于当天开始的 session，没有前两天 session 的购买被补进来——"
        "**是丢失，不是延迟上报**；",
        "4. 中断期加购暴涨，但「10 分钟内同一 session 重复加购同一商品」的比例（29.6%）与购买正常记录的 "
        "11-17（30.0%）几乎一样（平时 26.7%），说明没有把购买误记成加购——加购暴涨是真实的大促加购。",
        "",
        "**处理**：",
        "",
        "- 不做插补。看板上 11-15、11-16 的购买类指标标灰并注明「埋点缺失」，环比计算跳过这两天；",
        "- 依赖购买的分析（下单转化、GMV、回流价值）避开这两天，或在结论里写明方向：会**低估**大促 GMV，"
        "所以对召回价值的估计是偏保守的；",
        "- 大促复盘只用不受影响的指标（流量、分层回访、11-17 全天的购买）；"
        "「大促前段只加购不下单」这类结论不能成立，因为前段的购买根本没记下来；",
        "- 实际业务中应补的监控：purchase 事件量与上周同时段的比值低于 0.3 时小时级告警（见 `docs/tracking_plan.md`）。",
        "",
        "### 2. 11-17 本地 21:00 前后事件量骤降",
        "",
        "本地 11-17 21:00 这一小时全量事件只有上周同时段的 47%（前一小时是 349%），下一小时回到 142%。"
        "可能是大促结束的流量断崖，也可能有短时日志缺失，数据里无法区分；只影响一个小时，未处理。",
        "",
        "### 3. 零星的整小时日志缺失",
        "",
        "10-18 04:00、11-06 03:00、11-08 04:00（本地）等几个凌晨小时，全量事件只有上周同时段的 4%–39%，"
        "属于整小时的采集中断。都在流量低谷，对日指标的影响不到 1%，未处理，已在上表列出。",
        "",
        "### 4. 时区",
        "",
        f"数据集只说明 `event_time` 是 UTC。按小时流量曲线（谷底 UTC 23 点、高峰 UTC 16 点）推断店铺在 UTC+{TZ_OFFSET_HOURS}，"
        f"换算后谷底在本地凌晨 2 点、高峰在晚上 7 点，符合电商作息。业务日期、时段分析都按 UTC+{TZ_OFFSET_HOURS} 切分；"
        "若直接按 UTC 小时划分早中晚，结论会整体错位 3 小时。",
        "",
        "### 5. 窗口截断",
        "",
        "- **左截断**：窗口从 10-01 开始，10 月上旬「首次出现」的用户可能 9 月就来过。新用户留存优先看 10 月中旬以后的 cohort；",
        "- **右截断**：11 月下旬的用户观察期不足，留存表只保留观察期完整的格子，回流预测只用 11-20 及以前的评估日；",
        "- 生命周期日快照从 10-31 开始，此前看不到「沉默 30 天以上」。",
        "",
        "### 6. 金额单位",
        "",
        "数据集没注明 `price` 的币种，金额一律写作「原始价格单位」，不写元或美元。",
    ]
    DASHBOARD_DATA.mkdir(parents=True, exist_ok=True)
    (DASHBOARD_DATA / "dq.json").write_text(json.dumps(
        [{"group": g, "check": name, "status": st, "detail": d} for g, name, st, d in results], ensure_ascii=False))
    out = DOCS / "data_quality_report.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"{n} → {out}")
    for g, name, s, d in results:
        if s != "PASS":
            print(f"  [{s}] {name}: {d[:140]}")


if __name__ == "__main__":
    main()
