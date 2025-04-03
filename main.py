import streamlit as st
from arcgis.features import FeatureLayer
import pandas as pd

#---window options-----

# Set wide layout
st.set_page_config(
    page_title="Feature Layer Manager",
    layout="wide",  # 👈 this makes the app use the full width of the browser
)

# --- Configuration ---
ACCESS_CODE = "asiaan"  # Replace with your own secret code

# --- Session Setup ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- Login Page ---
def login_page():
    st.title("🔐 ArcGIS Data Entry App")
    st.write("Please enter the access code to continue.")

    code = st.text_input("Access Code", type="password")

    if st.button("Login"):
        if code.lower() == ACCESS_CODE.lower():
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid access code. Please try again.")

# --- Second Page (After Login) ---
def feature_layer_editor():
    st.title("✅ Welcome to the Feature Layer Editor")
    st.success("You're logged in!")

    # --- Connect to your public Feature Layer ---
    FEATURE_LAYER_URL = "https://services.arcgis.com/GL0fWlNkwysZaKeV/arcgis/rest/services/google_sheet_feature_layer_02/FeatureServer/0"
    layer = FeatureLayer(FEATURE_LAYER_URL)

    # --- Query features (raw JSON) ---
    with st.spinner("Fetching data from ArcGIS..."):
        features = layer.query(where="1=1", out_fields="*", return_geometry=False)
        raw_data = [f.attributes for f in features.features]  # extract attributes from each feature
        df = pd.DataFrame(raw_data)

    # --- Show as scrollable table ---
    st.subheader("Service Centers")
    st.dataframe(df, height=500, use_container_width=True)

# --- App Flow ---
if st.session_state.logged_in:
    feature_layer_editor()
else:
    login_page()