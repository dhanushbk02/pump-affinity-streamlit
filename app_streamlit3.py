import streamlit as st
import pandas as pd
from io import BytesIO

# --- Page setup ---
st.set_page_config(page_title="Flow Calculator - By Dhanush (FPL)", layout="centered", page_icon="💧")
st.title("Flow Calculator - By Dhanush (FPL)")

st.markdown(
    """
    This tool lets you calculate pump performance for different impeller diameters using Pump Affinity Laws.  
    You can either:
    - 📁 **Upload an Excel file** with Flow, Head, and Power readings, or  
    - ✏️ **Manually enter readings** for up to 5 samples.
    """
)

# --- Option selection ---
mode = st.radio("Choose input method:", ["📁 Upload Excel File", "✏️ Manual Entry"])

# --- Common settings ---
orig_dia = st.number_input("Original Impeller OD (mm)", min_value=0.0, step=0.1, format="%.1f")

new_dias_input = st.text_input("New impeller diameters (comma-separated, e.g., 100,120,140):", value="100,120,140")
decimals = st.number_input("Round results to how many decimal places?", min_value=0, max_value=6, value=2, step=1)

# --- Helper functions ---
def apply_affinity(df, D_orig, new_dias):
    out = df.copy()
    for D in new_dias:
        ratio = D / D_orig
        out[f"Flow_D{D}"] = out["Flow_input"] * ratio
        out[f"Head_D{D}"] = out["Head_m"] * (ratio ** 2)
        out[f"Power_kW_D{D}"] = out["Power_input_kW"] * (ratio ** 3)
        out[f"Efficiency_D{D}"] = (
            (0.0001409 * out[f"Flow_D{D}"] * out[f"Head_D{D}"] / out[f"Power_kW_D{D}"]) * 100
        )
    return out

def build_excel_bytes(df_out, decimals=2):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_out.round(decimals).to_excel(writer, sheet_name="Results", index=False)
    buf.seek(0)
    return buf

# --- Mode 1: Upload Excel ---
if mode == "📁 Upload Excel File":
    st.markdown("Upload an Excel file with Flow (LPM), Head (m), and Input Power (kW) in columns A, B, and C respectively.")
    uploaded = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

    if uploaded:
        try:
            df_in = pd.read_excel(uploaded, engine="openpyxl", header=None)
            flows = df_in.iloc[:, 0].dropna().astype(float).reset_index(drop=True)
            heads = df_in.iloc[:, 1].dropna().astype(float).reset_index(drop=True)
            powers = df_in.iloc[:, 2].dropna().astype(float).reset_index(drop=True)

            n = min(len(flows), len(heads), len(powers))
            df_baseline = pd.DataFrame({
                "Flow_input": flows[:n],
                "Head_m": heads[:n],
                "Power_input_kW": powers[:n]
            })

            df_baseline["Efficiency_%"] = (
                (0.0001409 * df_baseline["Flow_input"] * df_baseline["Head_m"] / df_baseline["Power_input_kW"]) * 100
            )

            st.success("✅ Excel data successfully read.")
            st.dataframe(df_baseline.head(10))

        except Exception as e:
            st.error("❌ Failed to read Excel file. Ensure first 3 columns are numeric (Flow, Head, Power).")
            st.exception(e)
            st.stop()

# --- Mode 2: Manual Entry ---
else:
    st.markdown("Enter up to 5 sets of readings manually:")

    manual_rows = 5
    manual_data = []

    with st.form("manual_baseline_form", clear_on_submit=False):
        st.write("Enter Flow (LPM), Head (m), and Power (kW) for each sample:")

        for i in range(1, manual_rows + 1):
            c1, c2, c3 = st.columns(3)
            flow_val = c1.number_input(
                f"Flow (LPM) sample {i}",
                step=10.0,
                format="%.0f",
                key=f"flow_{i}",
                value=0.0
            )
            head_val = c2.number_input(
                f"Head (m) sample {i}",
                step=0.1,
                format="%.1f",
                key=f"head_{i}",
                value=0.0
            )
            p_val = c3.number_input(
                f"Power (kW) sample {i}",
                step=0.01,
                format="%.2f",
                key=f"pow_{i}",
                value=0.0
            )
            manual_data.append((flow_val, head_val, p_val))

        submitted = st.form_submit_button("Submit Manual Readings")

    if submitted:
        df_baseline = pd.DataFrame(manual_data, columns=["Flow_input", "Head_m", "Power_input_kW"])
        df_baseline = df_baseline[(df_baseline != 0).any(axis=1)]  # Remove all-zero rows

        df_baseline["Efficiency_%"] = (
            (0.0001409 * df_baseline["Flow_input"] * df_baseline["Head_m"] / df_baseline["Power_input_kW"]) * 100
        )

        st.success("✅ Manual data submitted successfully.")
        st.dataframe(df_baseline)

# --- Calculate & display results ---
if (mode == "📁 Upload Excel File" and uploaded) or (mode == "✏️ Manual Entry" and submitted):
    if orig_dia is None or orig_dia <= 0:
        st.warning("⚠️ Please enter a valid Original Impeller OD before calculating.")
        st.stop()

    try:
        new_dias = [float(d.strip()) for d in new_dias_input.split(",") if d.strip()]
        if not new_dias:
            st.warning("⚠️ Please enter at least one new impeller diameter.")
            st.stop()
    except ValueError:
        st.error("❌ Invalid format in new diameters. Use numbers separated by commas, e.g., 100,120,140.")
        st.stop()

    df_result = apply_affinity(df_baseline, orig_dia, new_dias)

    st.subheader("📊 Results:")
    st.dataframe(df_result.round(decimals))

    # --- Graphs ---
    import matplotlib.pyplot as plt

    for D in new_dias:
        fig1, ax1 = plt.subplots()
        ax1.plot(df_result[f"Flow_D{D}"], df_result[f"Head_D{D}"], marker="o")
        ax1.set_xlabel("Flow (LPM)")
        ax1.set_ylabel("Head (m)")
        ax1.set_title(f"Flow vs Head for Dia {D} mm")
        st.pyplot(fig1)

        fig2, ax2 = plt.subplots()
        ax2.plot(df_result[f"Flow_D{D}"], df_result[f"Efficiency_D{D}"], marker="o")
        ax2.set_xlabel("Flow (LPM)")
        ax2.set_ylabel("Efficiency (%)")
        ax2.set_title(f"Flow vs Efficiency for Dia {D} mm")
        st.pyplot(fig2)

        fig3, ax3 = plt.subplots()
        ax3.plot(df_result[f"Flow_D{D}"], df_result[f"Power_kW_D{D}"], marker="o")
        ax3.set_xlabel("Flow (LPM)")
        ax3.set_ylabel("Power (kW)")
        ax3.set_title(f"Flow vs Power for Dia {D} mm")
        st.pyplot(fig3)

    # --- Download output ---
    excel_bytes = build_excel_bytes(df_result, decimals)
    st.download_button(
        label="💾 Download Results as Excel",
        data=excel_bytes,
        file_name="Flow_Calculator_Results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
