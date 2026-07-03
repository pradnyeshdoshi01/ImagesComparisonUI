"""
Image Comparison Streamlit App
--------------------------------
Reads an Excel file with columns:
NO, image1_id, image2_id, model_similarity_score, decision,
image1_id_url, image2_id_url, decisionType, reason

Shows images side-by-side, one row (or a small page of rows) at a time.
Uses pagination instead of loading everything at once, so nothing sits
around in RAM — each page only renders the URLs for that page, and
Streamlit fetches images directly from the internet at render time
(nothing is downloaded/cached into memory by this app).

Run with:
    streamlit run image_compare_app.py
"""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Image Comparison Tool", layout="wide")

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
DEFAULT_PAGE_SIZE = 0  # default size is zero, as requested
REQUIRED_COLUMNS = [
    "NO.", "image1_id", "image2_id", "model_similarity_score",
    "decision", "image1_id_url", "image2_id_url", "decisionType", "reason",
]

# ----------------------------------------------------------------------
# SESSION STATE INIT
# ----------------------------------------------------------------------
if "page_number" not in st.session_state:
    st.session_state.page_number = 0
if "page_size" not in st.session_state:
    st.session_state.page_size = DEFAULT_PAGE_SIZE
if "df" not in st.session_state:
    st.session_state.df = None
if "file_signature" not in st.session_state:
    st.session_state.file_signature = None
if "sheet_names" not in st.session_state:
    st.session_state.sheet_names = None
if "selected_sheet" not in st.session_state:
    st.session_state.selected_sheet = None


@st.cache_data(show_spinner=False)
def get_sheet_names(file_bytes: bytes) -> list:
    """Return list of sheet names in the excel file."""
    xls = pd.ExcelFile(pd.io.common.BytesIO(file_bytes))
    return xls.sheet_names


@st.cache_data(show_spinner=False)
def load_excel(file_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    """Load a specific sheet into a DataFrame. Cached on (file bytes, sheet)
    so re-running the script doesn't re-read the file from disk every time."""
    df = pd.read_excel(pd.io.common.BytesIO(file_bytes), sheet_name=sheet_name)
    return df


def reset_pagination():
    st.session_state.page_number = 0


# ----------------------------------------------------------------------
# SIDEBAR: FILE UPLOAD + CONTROLS
# ----------------------------------------------------------------------
st.sidebar.title("⚙️ Controls")

uploaded_file = st.sidebar.file_uploader(
    "Upload Excel file (.xlsx)", type=["xlsx", "xls"]
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    signature = (uploaded_file.name, len(file_bytes))

    # New file uploaded -> re-detect sheets, reset previous selections
    if st.session_state.file_signature != signature:
        st.session_state.file_signature = signature
        st.session_state.sheet_names = get_sheet_names(file_bytes)
        st.session_state.selected_sheet = None
        st.session_state.df = None
        reset_pagination()

    sheet_names = st.session_state.sheet_names

    if len(sheet_names) > 1:
        # Multiple sheets -> let user pick one
        chosen_sheet = st.sidebar.selectbox(
            "📄 Select sheet",
            options=sheet_names,
            index=0 if st.session_state.selected_sheet is None
                  else sheet_names.index(st.session_state.selected_sheet),
        )
    else:
        # Only one sheet -> use it automatically
        chosen_sheet = sheet_names[0]
        st.sidebar.caption(f"📄 Sheet: **{chosen_sheet}** (only sheet in file)")

    if chosen_sheet != st.session_state.selected_sheet:
        st.session_state.selected_sheet = chosen_sheet
        st.session_state.df = load_excel(file_bytes, chosen_sheet)
        reset_pagination()

df = st.session_state.df

if df is None:
    st.title("🖼️ Image Comparison Tool")
    st.info("👈 Upload an Excel file from the sidebar to get started.")
    if uploaded_file is not None and st.session_state.sheet_names and len(st.session_state.sheet_names) > 1:
        st.info("Select a sheet from the sidebar to load its data.")
    st.caption(f"Expected columns: {', '.join(REQUIRED_COLUMNS)}")
    st.stop()

missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
if missing_cols:
    st.error(f"Excel file is missing required columns: {missing_cols}")
    st.stop()

total_rows = len(df)

# Page size selector — default is 0 (no rows shown) until user picks a size
page_size = st.sidebar.number_input(
    "Rows per page (0 = show none until you choose)",
    min_value=0,
    max_value=50,
    value=st.session_state.page_size,
    step=5,
    on_change=None,
    key="page_size_input",
)
if page_size != st.session_state.page_size:
    st.session_state.page_size = page_size
    reset_pagination()

st.sidebar.markdown("---")

# Optional filters
with st.sidebar.expander("🔍 Filters", expanded=False):
    decision_options = ["All"] + sorted(df["decision"].dropna().unique().tolist())
    decision_filter = st.selectbox("Decision", decision_options)

    decisiontype_options = ["All"] + sorted(df["decisionType"].dropna().unique().tolist())
    decisiontype_filter = st.selectbox("Decision Type", decisiontype_options)

filtered_df = df.copy()
if decision_filter != "All":
    filtered_df = filtered_df[filtered_df["decision"] == decision_filter]
if decisiontype_filter != "All":
    filtered_df = filtered_df[filtered_df["decisionType"] == decisiontype_filter]

filtered_df = filtered_df.reset_index(drop=True)
total_filtered = len(filtered_df)

st.sidebar.markdown(f"**Total rows:** {total_rows}")
st.sidebar.markdown(f"**Filtered rows:** {total_filtered}")

# ----------------------------------------------------------------------
# MAIN TITLE
# ----------------------------------------------------------------------
st.title("🖼️ Image Comparison Tool")
if st.session_state.selected_sheet:
    st.caption(f"📄 Loaded sheet: **{st.session_state.selected_sheet}**")

if st.session_state.page_size == 0:
    st.warning(
        "Page size is 0 — set a 'Rows per page' value (>0) in the sidebar "
        "to start viewing image comparisons."
    )
    st.stop()

if total_filtered == 0:
    st.warning("No rows match the current filters.")
    st.stop()

page_size = st.session_state.page_size
total_pages = max(1, (total_filtered - 1) // page_size + 1)

# clamp current page
if st.session_state.page_number >= total_pages:
    st.session_state.page_number = total_pages - 1
if st.session_state.page_number < 0:
    st.session_state.page_number = 0

# ----------------------------------------------------------------------
# PAGINATION CONTROLS (TOP)
# ----------------------------------------------------------------------
def go_prev():
    if st.session_state.page_number > 0:
        st.session_state.page_number -= 1


def go_next():
    if st.session_state.page_number < total_pages - 1:
        st.session_state.page_number += 1


def go_to_page(p):
    st.session_state.page_number = p - 1


nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 3, 1])
with nav_col1:
    st.button("⬅️ Previous", on_click=go_prev, use_container_width=True,
               disabled=(st.session_state.page_number == 0))
with nav_col2:
    st.button("Next ➡️", on_click=go_next, use_container_width=True,
               disabled=(st.session_state.page_number >= total_pages - 1))
with nav_col3:
    st.markdown(
        f"<div style='text-align:center; padding-top:8px;'>"
        f"Page <b>{st.session_state.page_number + 1}</b> of <b>{total_pages}</b> "
        f"&nbsp;|&nbsp; Showing rows "
        f"<b>{st.session_state.page_number * page_size + 1}</b>"
        f"–<b>{min((st.session_state.page_number + 1) * page_size, total_filtered)}</b>"
        f" of <b>{total_filtered}</b></div>",
        unsafe_allow_html=True,
    )
with nav_col4:
    jump_to = st.number_input(
        "Jump to page", min_value=1, max_value=total_pages,
        value=st.session_state.page_number + 1, step=1, label_visibility="collapsed",
    )
    if jump_to != st.session_state.page_number + 1:
        go_to_page(jump_to)
        st.rerun()

st.markdown("---")

# ----------------------------------------------------------------------
# RENDER ONLY THE CURRENT PAGE'S ROWS
# (This is the key part that keeps RAM usage flat: we slice the
# DataFrame to just this page, and we never store any downloaded image
# bytes — st.image(url) / markdown <img> renders directly from the URL,
# so images are streamed by the browser, not held in Python memory.)
# ----------------------------------------------------------------------
start_idx = st.session_state.page_number * page_size
end_idx = min(start_idx + page_size, total_filtered)
page_df = filtered_df.iloc[start_idx:end_idx]

for _, row in page_df.iterrows():
    with st.container(border=True):
        header_col, meta_col = st.columns([2, 3])
        with header_col:
            st.subheader(f"Row #{row['NO.']}")
        with meta_col:
            st.markdown(
                f"**Similarity Score:** {row['model_similarity_score']} &nbsp;|&nbsp; "
                f"**Decision:** {row['decision']} &nbsp;|&nbsp; "
                f"**Decision Type:** {row['decisionType']}"
            )

        img_col1, img_col2 = st.columns(2)
        with img_col1:
            st.markdown(f"**Image 1** — `{row['image1_id']}`")
            url1 = row.get("image1_id_url")
            if pd.notna(url1) and str(url1).strip():
                try:
                    st.image(str(url1), use_container_width=True)
                except Exception:
                    st.error("Could not load image 1")
                st.caption(str(url1))
            else:
                st.info("No URL for image 1")

        with img_col2:
            st.markdown(f"**Image 2** — `{row['image2_id']}`")
            url2 = row.get("image2_id_url")
            if pd.notna(url2) and str(url2).strip():
                try:
                    st.image(str(url2), use_container_width=True)
                except Exception:
                    st.error("Could not load image 2")
                st.caption(str(url2))
            else:
                st.info("No URL for image 2")

        if pd.notna(row.get("reason")) and str(row.get("reason")).strip():
            st.markdown(f"**Reason:** {row['reason']}")

st.markdown("---")

# ----------------------------------------------------------------------
# PAGINATION CONTROLS (BOTTOM)
# ----------------------------------------------------------------------
bottom_col1, bottom_col2, bottom_col3 = st.columns([1, 3, 1])
with bottom_col1:
    st.button("⬅️ Previous ", on_click=go_prev, use_container_width=True,
               disabled=(st.session_state.page_number == 0), key="prev_bottom")
with bottom_col2:
    st.markdown(
        f"<div style='text-align:center; padding-top:8px;'>"
        f"Page {st.session_state.page_number + 1} of {total_pages}</div>",
        unsafe_allow_html=True,
    )
with bottom_col3:
    st.button("Next ➡️ ", on_click=go_next, use_container_width=True,
               disabled=(st.session_state.page_number >= total_pages - 1), key="next_bottom")