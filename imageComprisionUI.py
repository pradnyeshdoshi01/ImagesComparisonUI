"""
Image Comparison & Object Detection Analysis Streamlit App
------------------------------------------------------------
PAGE 1 - Image Comparison
Reads an Excel sheet with columns:
NO, image1_id, image2_id, model_similarity_score, decision,
image1_id_url, image2_id_url, decisionType, reason

PAGE 2 - Object Detection Analysis
Reads an Excel sheet with columns:
imageId, imageUrl, objectDetectionStatus, confidenceScorePresent,
confidenceScoreAbsent, detectionRemarks

Both pages support multi-sheet Excel files (pick a sheet if more than one
exists) and paginate rows instead of loading everything at once, so nothing
stays in RAM — each page only renders the URLs for the rows currently on
screen, and Streamlit fetches images directly from the internet at render
time (nothing is downloaded/cached into memory by this app).

Run with:
    streamlit run image_compare_app.py
"""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Image Analysis Tool", layout="wide")

DEFAULT_PAGE_SIZE = 5  # default size is zero, as requested

COMPARISON_COLUMNS = [
    "NO", "image1_id", "image2_id", "model_similarity_score",
    "decision", "image1_id_url", "image2_id_url", "decisionType", "reason",
]

OBJECT_DETECTION_COLUMNS = [
    "imageId", "imageUrl", "objectDetectionStatus",
    "confidenceScorePresent", "confidenceScoreAbsent", "detectionRemarks",
]


# ----------------------------------------------------------------------
# CACHED LOADERS (shared by both pages)
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_sheet_names(file_bytes: bytes) -> list:
    """Return list of sheet names in the excel file."""
    xls = pd.ExcelFile(pd.io.common.BytesIO(file_bytes))
    return xls.sheet_names


@st.cache_data(show_spinner=False)
def load_excel(file_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    """Load a specific sheet into a DataFrame. Cached on (file bytes, sheet)
    so re-running the script doesn't re-read the file from disk every time."""
    return pd.read_excel(pd.io.common.BytesIO(file_bytes), sheet_name=sheet_name)


# ----------------------------------------------------------------------
# GENERIC SESSION STATE HELPERS (namespaced per page so the two pages
# never share/overwrite each other's uploaded file, sheet choice or
# pagination state)
# ----------------------------------------------------------------------
def init_state(ns: str):
    defaults = {
        f"{ns}_page_number": 0,
        f"{ns}_page_size": DEFAULT_PAGE_SIZE,
        f"{ns}_df": None,
        f"{ns}_file_signature": None,
        f"{ns}_sheet_names": None,
        f"{ns}_selected_sheet": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def reset_pagination(ns: str):
    st.session_state[f"{ns}_page_number"] = 0


def handle_file_and_sheet(ns: str, uploader_label: str):
    """Handles file upload + (optional) sheet selection for a given
    namespace. Returns the loaded DataFrame, or None if nothing loaded yet."""
    uploaded_file = st.sidebar.file_uploader(
        uploader_label, type=["xlsx", "xls"], key=f"{ns}_uploader"
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        signature = (uploaded_file.name, len(file_bytes))

        if st.session_state[f"{ns}_file_signature"] != signature:
            st.session_state[f"{ns}_file_signature"] = signature
            st.session_state[f"{ns}_sheet_names"] = get_sheet_names(file_bytes)
            st.session_state[f"{ns}_selected_sheet"] = None
            st.session_state[f"{ns}_df"] = None
            reset_pagination(ns)

        sheet_names = st.session_state[f"{ns}_sheet_names"]

        if len(sheet_names) > 1:
            current = st.session_state[f"{ns}_selected_sheet"]
            chosen_sheet = st.sidebar.selectbox(
                "📄 Select sheet",
                options=sheet_names,
                index=0 if current is None else sheet_names.index(current),
                key=f"{ns}_sheet_select",
            )
        else:
            chosen_sheet = sheet_names[0]
            st.sidebar.caption(f"📄 Sheet: **{chosen_sheet}** (only sheet in file)")

        if chosen_sheet != st.session_state[f"{ns}_selected_sheet"]:
            st.session_state[f"{ns}_selected_sheet"] = chosen_sheet
            st.session_state[f"{ns}_df"] = load_excel(file_bytes, chosen_sheet)
            reset_pagination(ns)

    return st.session_state[f"{ns}_df"]


def page_size_control(ns: str):
    page_size = st.sidebar.number_input(
        "Rows per page (0 = show none until you choose)",
        min_value=0,
        max_value=50,
        value=st.session_state[f"{ns}_page_size"],
        step=5,
        key=f"{ns}_page_size_input",
    )
    if page_size != st.session_state[f"{ns}_page_size"]:
        st.session_state[f"{ns}_page_size"] = page_size
        reset_pagination(ns)
    return st.session_state[f"{ns}_page_size"]


def pagination_controls(ns: str, total_filtered: int, page_size: int, position: str):
    total_pages = max(1, (total_filtered - 1) // page_size + 1)

    if st.session_state[f"{ns}_page_number"] >= total_pages:
        st.session_state[f"{ns}_page_number"] = total_pages - 1
    if st.session_state[f"{ns}_page_number"] < 0:
        st.session_state[f"{ns}_page_number"] = 0

    def go_prev():
        if st.session_state[f"{ns}_page_number"] > 0:
            st.session_state[f"{ns}_page_number"] -= 1

    def go_next():
        if st.session_state[f"{ns}_page_number"] < total_pages - 1:
            st.session_state[f"{ns}_page_number"] += 1

    page_num = st.session_state[f"{ns}_page_number"]

    col1, col2, col3, col4 = st.columns([1, 1, 3, 1])
    with col1:
        st.button("⬅️ Previous", on_click=go_prev, use_container_width=True,
                   disabled=(page_num == 0), key=f"{ns}_prev_{position}")
    with col2:
        st.button("Next ➡️", on_click=go_next, use_container_width=True,
                   disabled=(page_num >= total_pages - 1), key=f"{ns}_next_{position}")
    with col3:
        st.markdown(
            f"<div style='text-align:center; padding-top:8px;'>"
            f"Page <b>{page_num + 1}</b> of <b>{total_pages}</b> "
            f"&nbsp;|&nbsp; Showing rows "
            f"<b>{page_num * page_size + 1}</b>"
            f"–<b>{min((page_num + 1) * page_size, total_filtered)}</b>"
            f" of <b>{total_filtered}</b></div>",
            unsafe_allow_html=True,
        )
    with col4:
        if position == "top":
            jump_to = st.number_input(
                "Jump to page", min_value=1, max_value=total_pages,
                value=page_num + 1, step=1, label_visibility="collapsed",
                key=f"{ns}_jump_{page_num}",
            )
            if jump_to != page_num + 1:
                st.session_state[f"{ns}_page_number"] = jump_to - 1
                st.rerun()

    return total_pages, st.session_state[f"{ns}_page_number"]


# ----------------------------------------------------------------------
# PAGE 1: IMAGE COMPARISON
# ----------------------------------------------------------------------
def render_image_comparison_page():
    ns = "cmp"
    init_state(ns)

    st.sidebar.subheader("Image Comparison – Data")
    df = handle_file_and_sheet(ns, "Upload Excel file (.xlsx)")

    st.title("🖼️ Image Comparison Tool")
    if st.session_state[f"{ns}_selected_sheet"]:
        st.caption(f"📄 Loaded sheet: **{st.session_state[f'{ns}_selected_sheet']}**")

    if df is None:
        st.info("👈 Upload an Excel file from the sidebar to get started.")
        st.caption(f"Expected columns: {', '.join(COMPARISON_COLUMNS)}")
        return

    missing_cols = [c for c in COMPARISON_COLUMNS if c not in df.columns]
    if missing_cols:
        st.error(f"Excel sheet is missing required columns: {missing_cols}")
        return

    total_rows = len(df)
    page_size = page_size_control(ns)

    st.sidebar.markdown("---")
    with st.sidebar.expander("🔍 Filters", expanded=False):
        decision_options = ["All"] + sorted(df["decision"].dropna().unique().tolist())
        decision_filter = st.selectbox("Decision", decision_options, key=f"{ns}_decision_filter")

        decisiontype_options = ["All"] + sorted(df["decisionType"].dropna().unique().tolist())
        decisiontype_filter = st.selectbox("Decision Type", decisiontype_options, key=f"{ns}_decisiontype_filter")

    filtered_df = df.copy()
    if decision_filter != "All":
        filtered_df = filtered_df[filtered_df["decision"] == decision_filter]
    if decisiontype_filter != "All":
        filtered_df = filtered_df[filtered_df["decisionType"] == decisiontype_filter]
    filtered_df = filtered_df.reset_index(drop=True)
    total_filtered = len(filtered_df)

    st.sidebar.markdown(f"**Total rows:** {total_rows}")
    st.sidebar.markdown(f"**Filtered rows:** {total_filtered}")

    if page_size == 0:
        st.warning(
            "Page size is 0 — set a 'Rows per page' value (>0) in the sidebar "
            "to start viewing image comparisons."
        )
        return

    if total_filtered == 0:
        st.warning("No rows match the current filters.")
        return

    pagination_controls(ns, total_filtered, page_size, "top")
    st.markdown("---")

    page_num = st.session_state[f"{ns}_page_number"]
    start_idx = page_num * page_size
    end_idx = min(start_idx + page_size, total_filtered)
    page_df = filtered_df.iloc[start_idx:end_idx]

    for _, row in page_df.iterrows():
        with st.container(border=True):
            header_col, meta_col = st.columns([2, 3])
            with header_col:
                st.subheader(f"Row #{row['NO']}")
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
    pagination_controls(ns, total_filtered, page_size, "bottom")


def status_badge_html(status) -> str:
    """Return an HTML badge colored by detection status:
    FOUND -> green, NOT_FOUND -> red, anything else -> yellow."""
    if pd.isna(status):
        text = "UNKNOWN"
    else:
        text = str(status).strip()

    normalized = text.upper().replace(" ", "_")
    if normalized == "FOUND":
        bg, fg = "#d4edda", "#155724"  # green
    elif normalized == "NOT_FOUND":
        bg, fg = "#f8d7da", "#721c24"  # red
    else:
        bg, fg = "#fff3cd", "#856404"  # yellow

    return (
        f"<span style='background-color:{bg}; color:{fg}; "
        f"padding:4px 12px; border-radius:12px; font-weight:600; "
        f"font-size:0.9rem;'>{text}</span>"
    )


# ----------------------------------------------------------------------
# PAGE 2: OBJECT DETECTION ANALYSIS
# ----------------------------------------------------------------------
def render_object_detection_page():
    ns = "od"
    init_state(ns)

    st.sidebar.subheader("Object Detection – Data")
    df = handle_file_and_sheet(ns, "Upload Excel file (.xlsx)")

    st.title("🔎 Object Detection Analysis")
    if st.session_state[f"{ns}_selected_sheet"]:
        st.caption(f"📄 Loaded sheet: **{st.session_state[f'{ns}_selected_sheet']}**")

    if df is None:
        st.info("👈 Upload an Excel file from the sidebar to get started.")
        st.caption(f"Expected columns: {', '.join(OBJECT_DETECTION_COLUMNS)}")
        return

    missing_cols = [c for c in OBJECT_DETECTION_COLUMNS if c not in df.columns]
    if missing_cols:
        st.error(f"Excel sheet is missing required columns: {missing_cols}")
        return

    total_rows = len(df)
    page_size = page_size_control(ns)

    st.sidebar.markdown("---")
    with st.sidebar.expander("🔍 Filters", expanded=False):
        status_options = ["All"] + sorted(df["objectDetectionStatus"].dropna().unique().tolist())
        status_filter = st.selectbox("Object Detection Status", status_options, key=f"{ns}_status_filter")
        st.markdown(
            "🟢 FOUND &nbsp;&nbsp; 🔴 NOT_FOUND &nbsp;&nbsp; 🟡 Other",
            unsafe_allow_html=True,
        )

    filtered_df = df.copy()
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df["objectDetectionStatus"] == status_filter]
    filtered_df = filtered_df.reset_index(drop=True)
    total_filtered = len(filtered_df)

    st.sidebar.markdown(f"**Total rows:** {total_rows}")
    st.sidebar.markdown(f"**Filtered rows:** {total_filtered}")

    if page_size == 0:
        st.warning(
            "Page size is 0 — set a 'Rows per page' value (>0) in the sidebar "
            "to start viewing object detection results."
        )
        return

    if total_filtered == 0:
        st.warning("No rows match the current filters.")
        return

    pagination_controls(ns, total_filtered, page_size, "top")
    st.markdown("---")

    page_num = st.session_state[f"{ns}_page_number"]
    start_idx = page_num * page_size
    end_idx = min(start_idx + page_size, total_filtered)
    page_df = filtered_df.iloc[start_idx:end_idx]

    for _, row in page_df.iterrows():
        with st.container(border=True):
            header_col, meta_col = st.columns([2, 3])
            with header_col:
                st.subheader(f"Image ID: {row['imageId']}")
            with meta_col:
                st.markdown(
                    f"**Status:** {status_badge_html(row['objectDetectionStatus'])} &nbsp;|&nbsp; "
                    f"**Confidence (Present):** {row['confidenceScorePresent']} &nbsp;|&nbsp; "
                    f"**Confidence (Absent):** {row['confidenceScoreAbsent']}",
                    unsafe_allow_html=True,
                )

            img_col, remarks_col = st.columns([2, 2])
            with img_col:
                url = row.get("imageUrl")
                if pd.notna(url) and str(url).strip():
                    try:
                        st.image(str(url), use_container_width=True)
                    except Exception:
                        st.error("Could not load image")
                    st.caption(str(url))
                else:
                    st.info("No URL for this image")

            with remarks_col:
                if pd.notna(row.get("detectionRemarks")) and str(row.get("detectionRemarks")).strip():
                    st.markdown("**Detection Remarks:**")
                    st.write(str(row["detectionRemarks"]))
                else:
                    st.caption("No remarks provided.")

    st.markdown("---")
    pagination_controls(ns, total_filtered, page_size, "bottom")


# ----------------------------------------------------------------------
# TOP-LEVEL NAVIGATION
# ----------------------------------------------------------------------
st.sidebar.title("⚙️ Navigation")
page = st.sidebar.radio(
    "Choose a page",
    options=["🖼️ Image Comparison", "🔎 Object Detection Analysis"],
    key="page_selector",
)
st.sidebar.markdown("---")

if page == "🖼️ Image Comparison":
    render_image_comparison_page()
else:
    render_object_detection_page()
