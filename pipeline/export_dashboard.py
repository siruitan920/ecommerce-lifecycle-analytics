"""Step 5: 把 ADS 层导出成看板用的 JSON（dashboard/data/）。

看板是纯静态页面（GitHub Pages），所有聚合都在这里做完；
GMV 归因用的是和 notebooks/02 完全相同的基线和拆解逻辑。

用法：python pipeline/export_dashboard.py
"""
import json
from datetime import date

import numpy as np
import pandas as pd

from config import CAMPAIGN_END, CAMPAIGN_START, DASHBOARD_DATA, TZ_OFFSET_HOURS, connect

OUTAGE_DAYS = ["2019-11-15", "2019-11-16"]


def records(df: pd.DataFrame) -> list[dict]:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
        elif out[c].dtype == object and len(out) and isinstance(out[c].iloc[0], date):
            out[c] = out[c].astype(str)
    out = out.replace({np.nan: None})
    return [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()} for r in out.to_dict("records")]


def write(name: str, obj) -> None:
    path = DASHBOARD_DATA / f"{name}.json"
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    print(f"{path.name:22s} {path.stat().st_size / 1024:7.1f} KB")


def gmv_attribution(d: pd.DataFrame) -> pd.DataFrame:
    """GMV = DAU × 下单转化率 × 人均订单 × 客单价，对数拆解到四个因子（同 notebooks/02）。"""
    cols = ["dau", "buyer_conversion", "orders_per_buyer", "aov"]
    dt = pd.to_datetime(d.event_date)
    normal = ~dt.between(CAMPAIGN_START, CAMPAIGN_END)
    base = {c: d[c].where(normal).shift(1).rolling(10, min_periods=5).mean() for c in cols}
    out = pd.DataFrame({"event_date": d.event_date})
    out["gmv_base"] = np.prod([base[c] for c in cols], axis=0)
    with np.errstate(divide="ignore"):
        for c in cols:
            out[f"c_{c}"] = np.log(d[c] / base[c])
    with np.errstate(divide="ignore"):
        out["log_change"] = np.log(d.gmv / out.gmv_base)
    out.loc[dt.dt.strftime("%Y-%m-%d").isin(OUTAGE_DAYS), ["log_change"] + [f"c_{c}" for c in cols[1:]]] = np.nan
    return out


def main() -> None:
    DASHBOARD_DATA.mkdir(parents=True, exist_ok=True)
    con = connect(read_only=True)
    q = lambda sql: con.execute(sql).df()

    d = q("SELECT * FROM ads_daily_metrics ORDER BY event_date")
    attr = gmv_attribution(d)
    daily = d[["event_date", "dau", "wau", "mau", "new_users", "sessions", "views", "carts", "view_users",
               "cart_users", "buyers", "orders", "purchase_items", "gmv", "wau_complete", "mau_complete"]].merge(attr, on="event_date")
    write("daily", records(daily))

    cat = q("""
        SELECT event_date, category_l1, active_users, view_users, cart_users, buyers, views, carts, purchase_items, gmv
        FROM ads_daily_category ORDER BY event_date, category_l1
    """)
    write("category_daily", records(cat))

    ret = q("""
        SELECT cohort_week, day_n, SUM(cohort_size) AS cohort_size, SUM(retained_users) AS retained,
               SUM(returned_within_users) AS within_n,
               COUNT(*) AS cohort_days
        FROM ads_retention_cohort GROUP BY 1, 2 ORDER BY 1, 2
    """)
    # 只保留该周 cohort 的每一天都有完整观察期的格子
    full_days = q("SELECT cohort_week, COUNT(DISTINCT cohort_date) AS n FROM ads_retention_cohort GROUP BY 1")
    ret = ret.merge(full_days, on="cohort_week")
    ret = ret[ret.cohort_days == ret.n].drop(columns=["cohort_days", "n"])
    write("retention", records(ret))

    lc = q("""
        SELECT snapshot_date, stage, users, user_share, avg_events, avg_active_days, hist_gmv
        FROM ads_lifecycle_daily ORDER BY snapshot_date, stage_order(stage)
    """)
    snap = q("""
        SELECT stage, COUNT(*) AS users, AVG(active_days) AS avg_active_days, AVG(total_events) AS avg_events,
               AVG(events_per_active_day) AS events_per_day, AVG(CASE WHEN total_orders > 0 THEN 1 ELSE 0 END) AS buyer_rate,
               SUM(total_gmv) AS gmv,
               COUNT(*) FILTER (WHERE intensity_pct < 0.3 AND stage IN ('early_risk', 'accelerating')) AS high_value_risk
        FROM dws_user_lifecycle GROUP BY 1 ORDER BY stage_order(stage)
    """)
    write("lifecycle", {"daily": records(lc), "snapshot": records(snap)})

    hourly = q("""
        SELECT strftime(event_hour_ts, '%Y-%m-%d %H:00') AS hour, events, views, carts, purchases,
               events_vs_last_week, purchases_vs_last_week
        FROM ads_hourly_events ORDER BY event_hour_ts
    """)
    write("hourly", records(hourly))

    write("meta", {
        "generated": date.today().isoformat(),
        "date_range": [str(d.event_date.min()), str(d.event_date.max())],
        "tz": f"UTC+{TZ_OFFSET_HOURS}",
        "campaign": [CAMPAIGN_START, CAMPAIGN_END],
        "outage_days": OUTAGE_DAYS,
        "outage_hours": [["2019-11-14 22:00", "2019-11-16 10:59"], ["2019-11-16 19:00", "2019-11-17 05:59"]],
        "users": int(con.execute("SELECT COUNT(*) FROM dws_user_profile").fetchone()[0]),
        "events": int(con.execute("SELECT COUNT(*) FROM dwd_events").fetchone()[0]),
    })


if __name__ == "__main__":
    main()
