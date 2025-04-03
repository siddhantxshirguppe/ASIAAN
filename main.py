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


# --- Connect to your public Feature Layer ---
FEATURE_LAYER_URL = "https://services.arcgis.com/GL0fWlNkwysZaKeV/arcgis/rest/services/service_centers_02/FeatureServer/0"


layer = FeatureLayer(FEATURE_LAYER_URL)


# --- Session Setup ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'selected_record' not in st.session_state:
    st.session_state.selected_record = {}
if "page" not in st.session_state:
    st.session_state.page = "view"


# Get total number of features
if "total_count" not in st.session_state:
    count_result = layer.query(where="1=1", return_count_only=True)
    st.session_state.total_count = count_result




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
def feature_layers_viewer():
    st.title("✅ Welcome to the Feature Layer Editor")
    st.success("You're logged in!")

    # --- Query features (raw JSON) ---
    with st.spinner("Fetching data from ArcGIS..."):
        features = layer.query(where="1=1", out_fields="*", return_geometry=False,return_all_records=True)
        raw_data = [f.attributes for f in features.features]  # extract attributes from each feature
        df = pd.DataFrame(raw_data)

    # --- Show as scrollable table ---
    st.subheader("Service Centers 0")
    st.dataframe(df, height=500, use_container_width=True)

    if not df.empty:
        selected_index = st.number_input("🔍 Enter row number to edit:", min_value=0, max_value=len(df) - 1, step=1)
        if st.button("✏️ Edit Selected Entry"):
            st.session_state.selected_record = df.loc[selected_index].to_dict()
            st.session_state.object_id = df.loc[selected_index]['ObjectId']
            st.session_state.page = 'edit'
            st.rerun()

def show_edit_page():
    st.title("✏️ Edit Feature Entry")

    edited = {}
    with st.form("edit_form"):
        for key, value in st.session_state.selected_record.items():
            if key in ['ObjectId', 'GlobalID']:  # Keep these readonly
                st.text_input(key, str(value), disabled=True)
                edited[key] = value
            else:
                edited[key] = st.text_input(key, str(value))
        submitted = st.form_submit_button("✅ Push Update")

    if submitted:
        response = layer.edit_features(updates=[{"attributes": edited}])
        if response['updateResults'][0]['success']:
            st.success("✅ Entry successfully updated!")
        else:
            st.error("❌ Failed to update. Check your fields or permissions.")

    if st.button("⬅️ Back to Table"):
        st.session_state.page = 'view'
        st.rerun()

# --- App Flow ---
if st.session_state.logged_in:
    # Route to correct page
    if st.session_state.page == 'view':
        feature_layers_viewer()
    elif st.session_state.page == 'edit':
        show_edit_page()
else:
    login_page()