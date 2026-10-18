"""notebook 共用：连库、配色、作图样式、格式化。"""
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from config import connect  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

con = connect(read_only=True)
con.execute("SET enable_progress_bar = false")


def q(sql: str, **params) -> pd.DataFrame:
    """执行 SQL 返回 DataFrame。"""
    return con.execute(sql, params or None).df()


STAGES = ["new", "healthy", "early_risk", "accelerating", "long_lapsed"]
STAGE_CN = {"new": "新用户", "healthy": "健康", "early_risk": "早期风险",
            "accelerating": "加速流失", "long_lapsed": "长期沉默"}
# 分类色板固定顺序（已用色盲模拟校验相邻色差），分层颜色在所有图里保持一致
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
STAGE_COLOR = dict(zip(STAGES, PALETTE))
GRAY = "#8a8984"
SHADE = "#f0efec"
OUTAGE = ("2019-11-15", "2019-11-16")  # 购买埋点缺失的本地日期

plt.rcParams.update({
    "font.sans-serif": ["Hiragino Sans GB", "PingFang HK", "Arial Unicode MS", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.figsize": (9, 4),
    "figure.dpi": 110,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#c3c2b7",
    "axes.grid": True,
    "grid.color": "#e6e5e0",
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "lines.linewidth": 2,
    "legend.frameon": False,
})
pd.set_option("display.float_format", lambda x: f"{x:,.4g}" if abs(x) < 1 else f"{x:,.2f}")
pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 200)


def shade_outage(ax, label=True):
    """在时间序列图上把购买埋点缺失的两天标灰。"""
    ax.axvspan(pd.Timestamp(OUTAGE[0]) - pd.Timedelta(hours=12), pd.Timestamp(OUTAGE[1]) + pd.Timedelta(hours=12),
               color=SHADE, zorder=0, label="购买埋点缺失" if label else None)


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"
