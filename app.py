import io
import os
import zipfile
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="Eat-In Turn Time Leaderboards", layout="wide")

# ---------- Config ----------
THRESHOLDS = {"green": 35, "yellow_hi": 37}  # <35 green, 35–37 yellow, >37 red

ALIASES = {
    "Opened": ["opened", "open", "order start", "start time", "opened at"],
    "Closed": ["closed", "close", "order end", "end time", "closed at"],
    "Service": ["service", "service type", "order type"],
    "Created By": ["created by", "server", "server name", "employee", "cashier"],
    "Site": ["site", "location", "store", "restaurant"]
}

def pick_col(df: pd.DataFrame, candidates):
    for c in df.columns:
        lc = c.strip().lower()
        for a in candidates:
            if lc == a.lower() or a.lower() in lc:
                return c
    return None

def map_required_columns(df: pd.DataFrame):
    col_opened  = pick_col(df, ALIASES["Opened"])
    col_closed  = pick_col(df, ALIASES["Closed"])
    col_service = pick_col(df, ALIASES["Service"])
    col_server  = pick_col(df, ALIASES["Created By"])
    col_site    = pick_col(df, ALIASES["Site"])
    missing = [n for n,v in [("Opened",col_opened),("Closed",col_closed),("Service",col_service),("Created By",col_server)] if v is None]
    if missing:
        raise ValueError("Missing required column(s): " + ", ".join(missing))
    return col_opened, col_closed, col_service, col_server, col_site

def compute_leaderboard(df, col_opened, col_closed, col_service, col_server, col_site):
    df[col_opened] = pd.to_datetime(df[col_opened], errors="coerce")
    df[col_closed] = pd.to_datetime(df[col_closed], errors="coerce")
    eat = df[df[col_service].astype(str).str.contains("eat in", case=False, na=False)].copy()
    eat["Turn Time"] = (eat[col_closed] - eat[col_opened]).dt.total_seconds()/60
    eat = eat.replace([np.inf, -np.inf], np.nan).dropna(subset=["Turn Time"])
    eat = eat[eat["Turn Time"] >= 0]
    if eat.empty:
        raise ValueError("No valid Eat In rows with calculable Turn Time were found.")

    eat[col_server] = eat[col_server].fillna("(Unknown)").replace("", "(Unknown)")
    grp = (eat.groupby(col_server, dropna=False)["Turn Time"].mean()
           .reset_index().rename(columns={col_server:"Server"}))
    grp = grp.sort_values("Turn Time", ascending=True).reset_index(drop=True)
    grp["Turn Time"] = grp["Turn Time"].round(2)

    store_avg = round(eat["Turn Time"].mean(), 2)
    avg_row = {"Server":"STORE AVERAGE", "Turn Time": store_avg}
    if col_site and eat[col_site].dropna().nunique()==1:
        site_val = str(eat[col_site].dropna().iloc[0])
        grp.insert(0,"Site",site_val)
        avg_row = {"Site":site_val, **avg_row}
    out = pd.concat([grp, pd.DataFrame([avg_row])], ignore_index=True)
    return out

def render_image_table(df, title) -> bytes:
    display_cols = [c for c in ["Site","Server","Turn Time"] if c in df.columns]
    fig, ax = plt.subplots(figsize=(11, 0.55*len(df)+1.2))
    ax.axis('off')
    cell_text = df[display_cols].astype(str).values.tolist()

    colors = []
    tt_idx = display_cols.index("Turn Time")
    for _, row in df.iterrows():
        row_colors = ["white"]*len(display_cols)
        if str(row["Server"]).strip().upper() == "STORE AVERAGE":
            row_colors = ["#E0E0E0"]*len(display_cols)
        else:
            try:
                v = float(row["Turn Time"])
                if v < THRESHOLDS["green"]:
                    row_colors[tt_idx] = "#C6EFCE"
                elif THRESHOLDS["green"] <= v <= THRESHOLDS["yellow_hi"]:
                    row_colors[tt_idx] = "#FFEB9C"
                elif v > THRESHOLDS["yellow_hi"]:
                    row_colors[tt_idx] = "#FFC7CE"
            except Exception:
                pass
        colors.append(row_colors)

    table = ax.table(cellText=cell_text, colLabels=display_cols,
                     cellColours=colors, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.55, 1.55)

    for (r,c), cell in table.get_celld().items():
        if r == 0:
            cell.set_text_props(weight='bold')
            cell.set_facecolor("#F5F5F5")
        if r == len(df):
            cell.set_text_props(weight='bold')

    ax.set_title(title, fontweight="bold", pad=12)
    buf = io.BytesIO()
    plt.savefig(buf, dpi=220, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

# ---------- UI ----------
st.title("🍽️ Eat-In Turn Time Leaderboards")
st.caption("Upload one or more POS CSVs. I’ll compute average Eat-In turn time per server, sort fastest → slowest, append a STORE AVERAGE, and color by thresholds (<35 green, 35–37 yellow, >37 red).")

with st.sidebar:
    st.header("Options")
    g = st.number_input("Green if under (minutes)", value=float(THRESHOLDS["green"]), step=1.0)
    y = st.number_input("Yellow upper bound (minutes)", value=float(THRESHOLDS["yellow_hi"]), step=1.0)
    THRESHOLDS["green"], THRESHOLDS["yellow_hi"] = float(g), float(y)

uploads = st.file_uploader("Upload one or more CSV files", type=["csv"], accept_multiple_files=True)

if uploads:
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for upl in uploads:
            try:
                df = pd.read_csv(upl)
                col_opened, col_closed, col_service, col_server, col_site = map_required_columns(df)
                out = compute_leaderboard(df, col_opened, col_closed, col_service, col_server, col_site)

                base = os.path.splitext(upl.name)[0]
                title = f"Eat-In Turn Time Leaderboard – {base}"

                img_bytes = render_image_table(out, title)
                st.image(img_bytes, caption=title, use_container_width=True)

                zf.writestr(f"{base}_leaderboard.png", img_bytes)

            except Exception as e:
                st.error(f"{upl.name}: {e}")

    zip_buf.seek(0)
    st.download_button("⬇️ Download all images (ZIP)", data=zip_buf,
                       file_name="leaderboards.zip", mime="application/zip")
else:
    st.info("Upload CSV files to generate leaderboards.")
