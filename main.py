import streamlit as st
from arcgis.features import FeatureLayer
import pandas as pd
import re
import requests
#---window options-----

# Set wide layout
st.set_page_config(
    page_title="Feature Layer Manager",
    layout="wide",  # 👈 this makes the app use the full width of the browser
)


# --- Configuration ---
ACCESS_CODE = "asiaan"  # Replace with your own secret code


# --- Connect to your public Feature Layer ---
FEATURE_LAYER_URL = "https://services.arcgis.com/GL0fWlNkwysZaKeV/arcgis/rest/services/service_centers_layer001/FeatureServer/0"
API_KEY = "AIzaSyABqBYQvmQslBih1UjIIciTMdK6sxPOm_U"
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


def get_lat_lng_from_address(address: str):
    """
    Given an address string, returns (latitude, longitude) using Google Geocoding API.
    """

    endpoint = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": API_KEY
    }

    response = requests.get(endpoint, params=params)
    data = response.json()

    if data.get("status") == "OK" and data.get("results"):
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        raise Exception(f"Geocoding failed: {data.get('status')} - {data.get('error_message', '')}")
    
def get_place_suggestions(input_text):
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": input_text,
        "key": API_KEY,
        "types": "address"
    }
    response = requests.get(url, params=params)
    suggestions = response.json().get("predictions", [])
    return [s['description'] for s in suggestions]
    
def show_edit_page():
    st.title("✏️ Edit Feature Entry")

    # List of fields that must be 0 or 1
    binary_fields = [
        'Home_Health_Services',
        'Adult_Day_Services',
        'Benefits_Counseling',
        'Elder_Housing_Resources',
        'Assisted_Living',
        'Elder_Abuse',
        'Home_Repair',
        'Immigration_Assistance',
        'Long_term_Care_Ombudsman',
        'Long_term_Care_Nursing_Homes',
        'Senior_Exercise_Programs',
        'Dementia_Support_Programs',
        'Transportation',
        'Senior_Centers',
        'Caregiver_Support_Services',
        'Case_Management',
        'Congregate_Meals',
        'Financial_Counseling',
        'Health_Education_Workshops',
        'Home_Delivered_Meals',
        'Hospice_Care',
        'Technology_Training',
        'Cultural_Programming',
        'Mental_Health',
        'Vaccinations_Screening'
    ]

    edited = {}
    errors = []



    # Address Suggestor
    default_address = st.session_state.selected_record.get("Address", "")
    user_input = st.text_input("🔍 Search Address", value=default_address, key="address_suggestor")

    suggestions = []
    if len(user_input.strip()) >= 3:
        suggestions = get_place_suggestions(user_input)

    if suggestions:
        selected_address = st.selectbox("📍 Suggestions", suggestions, index=0)
        if selected_address and selected_address != st.session_state.selected_record["Address"]:
            st.session_state.selected_record["Address"] = selected_address
            st.session_state["address_updated"] = True  # <-- set a flag

            lat, lng = get_lat_lng_from_address(selected_address)
            st.session_state.selected_record["Latitude"] = str(lat)
            st.session_state.selected_record["Longitude"] = str(lng)

            st.rerun()

    with st.form("edit_form"):
        lat = lng = addr = addr_suite = None
        binary_inputs = {}

        for key, value in st.session_state.selected_record.items():
            if key in ['ObjectId', 'GlobalID']:
                st.text_input(f"{key} (read-only)", str(value), disabled=True)
                edited[key] = value

            elif key == 'Phone_number':
                new_value = st.text_input("Phone Number (format: 123-456-7890)", str(value))
                if not re.fullmatch(r"\d{3}-\d{3}-\d{4}", new_value):
                    errors.append("📞 Invalid phone number format.")
                edited[key] = new_value

            elif key in binary_fields:
                binary_inputs[key] = value  # delay rendering for grouped layout

            elif key == "Address":
                updated_address = st.session_state.selected_record.get("Address", str(value))
                edited[key] = st.text_input("Address", updated_address, disabled=True)
            elif key == "Address_w_suit__":
                addr_suite = (key, value)
            elif key == "Latitude":
                lat = (key, st.session_state.selected_record.get("Latitude", str(value)))
            elif key == "Longitude":
                lng = (key, st.session_state.selected_record.get("Longitude", str(value)))
            else:
                edited[key] = st.text_input(key, str(value))

        # Render address
        if addr_suite:
            edited[addr_suite[0]] = st.text_input("Address w/ Suite", str(addr_suite[1]))

        # Render lat/lng side by side
        if lat and lng:
            col1, col2 = st.columns(2)
            with col1:
                edited[lat[0]] = st.text_input("Latitude", str(lat[1]),disabled=True)
            with col2:
                edited[lng[0]] = st.text_input("Longitude", str(lng[1]),disabled=True)

        # Render binary fields in 3-column layout
        st.markdown("### 🧩 Service Availability Fields")
        binary_keys = list(binary_inputs.keys())
        for i in range(0, len(binary_keys), 5):
            cols = st.columns(5)
            for j in range(5):
                if i + j < len(binary_keys):
                    key = binary_keys[i + j]
                    with cols[j]:
                        edited[key] = st.selectbox(key, [0, 1], index=int(binary_inputs[key]))

        submitted = st.form_submit_button("✅ Push Update")

    if submitted:
        if errors:
            for err in errors:
                st.error(err)
        else:
            try:
                response = layer.edit_features(updates=[{"attributes": edited}])
                if response['updateResults'][0].get('success'):
                    st.success("✅ Entry successfully updated!")
                else:
                    st.error("❌ Update failed. Please check your inputs or field types.")
            except Exception as e:
                st.error(f"❌ An error occurred: {e}")

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