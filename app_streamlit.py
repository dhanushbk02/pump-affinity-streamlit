# app_streamlit.py
# Streamlit app for pump affinity conversions
# Reads uploaded Excel (Flow in A2:A, Head in B2:B, Input kW in C2:C)
# Optionally reads original impeller OD from a cell (default D1)
# Generates an output Excel for download.

import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Pump Affinity Converter", layout="centered")

st.title("Pump Affinity Converter — Upload Excel → Download Converted Excel")
st.write("Upload an Excel file with Flow (col A), Head (col B), Input kW (col C). Optionally store original OD in cell D1.")

uploaded = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
orig_from_cell_checkbox = st.checkbox("Auto-read original impeller OD from a cell (e.g. D1)", value=True)
orig_cell_addr = st.text_input("Cell address for original OD", value="D1") if orig_from_cell_checkbox else None

min_new = 3
new_dias_input = st.text_input(f"Enter at least {min_new} new diameters (comma-separated)", value="180,160,140")

detect_range = st.checkbox("Auto-detect data starting at row 2 (A2/B2/C2 → downwards)", value=True)

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
        # read from row 2 down until blank in each column, then trim to shortest length
        flows = df_raw.iloc[1:, 0].dropna().astype(float).reset_index(drop=True)
        heads = df_raw.iloc[1:, 1].dropna().astype(float).reset_index(drop=True)
        powers = df_raw.iloc[1:, 2].dropna().astype(float).reset_index(drop=True)
        n = min(len(flows), len(heads), len(powers))
        flows, heads, powers = flows[:n], heads[:n], powers[:n]
    else:
        flows = df_raw.loc[1:5, 0].astype(float).reset_index(drop=True)
        heads = df_raw.loc[1:5, 1].astype(float).reset_index(drop=True)
        powers = df_raw.loc[1:5, 2].astype(float).reset_index(drop=True)

    df = pd.DataFrame({
        "Flow_orig": flows,
        "Head_orig": heads,
        "Power_orig_kW": powers
    })
    return df, orig_value

def apply_affinity(df, D_orig, new_dias):
    out = df.copy()
    for D in new_dias:
        ratio = D / D_orig
        # keep reasonable column names
        out[f"Flow_D{D}"] = out["Flow_orig"] * ratio
        out[f"Head_D{D}"] = out["Head_orig"] * (ratio**2)
        out[f"Power_kW_D{D}"] = out["Power_orig_kW"] * (ratio**3)
    return out

if uploaded:
    try:
        df_in, orig_cell_value = read_uploaded_excel(uploaded, auto_detect=detect_range, orig_cell=(orig_cell_addr if orig_from_cell_checkbox else None))
    except Exception as e:
        st.error("Failed to read uploaded Excel. Make sure columns A/B/C contain numeric data.")
        st.exception(e)
        st.stop()

    st.subheader("Input preview")
    st.dataframe(df_in.head(20))

    orig_dia = None
    if orig_from_cell_checkbox and orig_cell_value is not None:
        st.success(f"Original OD read from {orig_cell_addr}: {orig_cell_value}")
        orig_dia = float(orig_cell_value)
    else:
        if orig_from_cell_checkbox:
            st.warning(f"No numeric value found in {orig_cell_addr}. Please enter original OD manually below.")
        orig_dia = st.number_input("Original impeller OD (mm)", min_value=0.000001, format="%.4f")

    # parse new diameters
    try:
        new_dias = [float(x.strip()) for x in new_dias_input.split(",") if x.strip()!=""]
    except:
        st.error("Couldn't parse new diameters. Enter comma-separated numbers like: 180,160,140")
        st.stop()

    if len(new_dias) < min_new:
        st.error(f"Please provide at least {min_new} diameters.")
        st.stop()
    if orig_dia is None or orig_dia <= 0:
        st.error("Original impeller OD must be a positive number.")
        st.stop()

    if st.button("Generate & Download Excel"):
        df_out = apply_affinity(df_in, float(orig_dia), new_dias)
        # prefer a stable column order
        cols = ["Flow_orig", "Head_orig", "Power_orig_kW"]
        for D in new_dias:
            cols += [f"Flow_D{D}", f"Head_D{D}", f"Power_kW_D{D}"]
        df_out = df_out[cols]
        df_out = df_out.round(6)  # adjust decimals as needed

        towrite = BytesIO()
        df_out.to_excel(towrite, index=False, engine="openpyxl")
        towrite.seek(0)

        st.download_button(
            label="Download converted Excel",
            data=towrite,
            file_name="output_converted.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Upload an Excel file to get started.")
