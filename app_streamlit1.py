# app_streamlit.py
# Streamlit Pump Affinity Converter — improved version
# Features:
# - read original OD from a cell (default D1) or manual input
# - round outputs (user-selectable)
# - option to export per-diameter sheets
# - preview charts (Flow / Head / Power)
# - improved validation and error messages

import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Pump Flow Converter by Dhanush", layout="centered", page_icon="💧")
st.title("Pump Affinity Converter — Upload Excel → Download")

st.markdown(
    "Upload an Excel file with Flow in column A (starting A2), Head in column B (starting B2), "
    "and Input kW in column C (starting C2). Optionally store original impeller OD in a cell (default D1)."
)

uploaded = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
auto_read_cell = st.checkbox("Try to auto-read original impeller OD from a cell", value=True)
cell_addr = st.text_input("Cell address (if auto-read enabled)", value="D1") if auto_read_cell else None

st.write("Enter at least 3 new impeller diameters (comma separated).")
new_dias_input = st.text_input("New diameters (e.g. 180,160,140)", value="180,160,140")

detect_range = st.checkbox("Auto-detect data starting at row 2 (A2/B2/C2 downward)", value=True)
export_per_sheet = st.checkbox("Export each new diameter to its own sheet (otherwise single sheet with columns)", value=False)
decimals = st.number_input("Round output to how many decimal places?", min_value=0, max_value=8, value=4, step=1)

MIN_DIAS = 3

def read_uploaded_excel(file_buffer, auto_detect=True, orig_cell="D1"):
    df_raw = pd.read_excel(file_buffer, engine="openpyxl", header=None)
    orig_value = None
    if orig_cell:
        try:
            col_letter = ''.join([c for c in orig_cell if c.isalpha()])
            row_number = int(''.join([c for c in orig_cell if c.isdigit()]))
            col_idx = ord(col_letter.upper()) - ord('A')
            row_idx = row_number - 1
            val = df_raw.iat[row_idx, col_idx]
            if not pd.isna(val):
                orig_value = float(val)
        except Exception:
            orig_value = None

    if auto_detect:
        flows = df_raw.iloc[1:, 0].dropna().astype(float).reset_index(drop=True)
        heads = df_raw.iloc[1:, 1].dropna().astype(float).reset_index(drop=True)
        powers = df_raw.iloc[1:, 2].dropna().astype(float).reset_index(drop=True)
        n = min(len(flows), len(heads), len(powers))
        flows, heads, powers = flows[:n], heads[:n], powers[:n]
    else:
        flows = df_raw.loc[1:5, 0].astype(float).reset_index(drop=True)
        heads = df_raw.loc[1:5, 1].astype(float).reset_index(drop=True)
        powers = df_raw.loc[1:5, 2].astype(float).reset_index(drop=True)

    df = pd.DataFrame({"Flow_orig": flows, "Head_orig": heads, "Power_orig_kW": powers})
    return df, orig_value

def apply_affinity(df, D_orig, new_dias):
    out = df.copy()
    for D in new_dias:
        ratio = D / D_orig
        out[f"Flow_D{D}"] = out["Flow_orig"] * ratio
        out[f"Head_D{D}"] = out["Head_orig"] * (ratio**2)
        out[f"Power_kW_D{D}"] = out["Power_orig_kW"] * (ratio**3)
    return out

def build_excel_bytes(df_orig, df_out, D_orig, new_dias, per_sheet=False, decimals=4):
    """
    Returns BytesIO Excel file.
    If per_sheet True: writes one sheet per new diameter (sheet name D{diam})
    Otherwise writes a single sheet with df_out
    """
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if per_sheet:
            # write original data sheet
            df_orig.round(decimals).to_excel(writer, sheet_name="original", index=False)
            # for each new diameter, compute Q,H,P columns and write sheet
            for D in new_dias:
                ratio = D / D_orig
                temp = df_orig.copy()
                temp[f"Flow_D{D}"] = (temp["Flow_orig"] * ratio).round(decimals)
                temp[f"Head_D{D}"] = (temp["Head_orig"] * (ratio**2)).round(decimals)
                temp[f"Power_kW_D{D}"] = (temp["Power_orig_kW"] * (ratio**3)).round(decimals)
                sheet_name = f"D{int(D) if float(D).is_integer() else D}"
                # ensure sheet name length <= 31
                sheet_name = sheet_name[:31]
                temp.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
            df_out.round(decimals).to_excel(writer, sheet_name="converted", index=False)
    buf.seek(0)
    return buf

if uploaded:
    try:
        df_in, orig_cell_value = read_uploaded_excel(uploaded, auto_detect=detect_range, orig_cell=(cell_addr if auto_read_cell else None))
    except Exception as e:
        st.error("Failed to read uploaded Excel. Ensure columns A/B/C contain numeric values and file is a valid Excel.")
        st.exception(e)
        st.stop()

    st.subheader("Input preview (first rows)")
    st.dataframe(df_in.head(10))

    # original diameter
    orig_dia = None
    if auto_read_cell and orig_cell_value is not None:
        st.success(f"Original OD read from {cell_addr}: {orig_cell_value}")
        orig_dia = float(orig_cell_value)
    else:
        if auto_read_cell:
            st.warning(f"Could not find a numeric value in {cell_addr}. Please enter original OD manually below.")
        orig_dia = st.number_input("Original impeller OD (mm)", min_value=0.000001, format="%.6f")

    # parse new diameters
    try:
        new_dias = [float(x.strip()) for x in new_dias_input.split(",") if x.strip() != ""]
    except Exception:
        st.error("Couldn't parse new diameters. Enter comma-separated numbers like: 180,160,140")
        st.stop()

    if len(new_dias) < MIN_DIAS:
        st.error(f"Please provide at least {MIN_DIAS} new diameters.")
        st.stop()

    if orig_dia is None or orig_dia <= 0:
        st.error("Original impeller OD must be a positive number.")
        st.stop()

    # compute
    df_out = apply_affinity(df_in, float(orig_dia), new_dias)

    # preview charts — aggregate by sample index
    st.subheader("Preview charts (first rows)")
    # Show Flow comparison chart for first 5 rows
    try:
        preview = df_out.head(10).copy()
        # create a small table for charts: index + Flow columns selected
        chart_df = preview[["Flow_orig"] + [c for c in preview.columns if c.startswith("Flow_D")]]
        st.write("Flow preview")
        st.line_chart(chart_df)
        chart_df2 = preview[["Head_orig"] + [c for c in preview.columns if c.startswith("Head_D")]]
        st.write("Head preview")
        st.line_chart(chart_df2)
        chart_df3 = preview[["Power_orig_kW"] + [c for c in preview.columns if c.startswith("Power_kW_D")]]
        st.write("Power preview")
        st.line_chart(chart_df3)
    except Exception:
        st.info("Could not generate preview charts for this dataset (maybe too few rows).")

    # Prepare download
    if st.button("Generate & Download Excel"):
        out_bytes = build_excel_bytes(df_in, df_out, float(orig_dia), new_dias, per_sheet=export_per_sheet, decimals=int(decimals))
        default_name = "output_converted.xlsx"
        st.success("Converted file ready")
        st.download_button(
            label="Download converted Excel",
            data=out_bytes,
            file_name=default_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Upload an Excel file to get started.")
