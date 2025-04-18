import streamlit as st
from arcgis.features import FeatureLayer
import pandas as pd
import re
import requests
import warnings

#---window options-----

# Set wide layout
st.set_page_config(
    page_title="Feature Layer Manager",
    layout="wide",  # 👈 this makes the app use the full width of the browser
)

warnings.filterwarnings("ignore", category=SyntaxWarning)

# --- Configuration ---
ACCESS_CODE = st.secrets["ADMIN_CODE"]  # Replace with your own secret code
GUEST_CODE = st.secrets["USER_CODE"] 

# --- Connect to your public Feature Layer ---
FEATURE_LAYER_URL = st.secrets["ARCGIS_FEATURE_LAYER"] 
API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]
layer = FeatureLayer(FEATURE_LAYER_URL)


# --- Session Setup ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'login_mode' not in st.session_state:
    st.session_state.login_mode = "guest"
if 'selected_record' not in st.session_state:
    st.session_state.selected_record = {}
if "page" not in st.session_state:
    st.session_state.page = "view"


# Get total number of features
if "total_count" not in st.session_state:
    count_result = layer.query(where="1=1", return_count_only=True)
    st.session_state.total_count = count_result

    # Address Suggestor
    if "new_address" not in st.session_state:
        st.session_state.new_address = ""
    if "new_lat" not in st.session_state:
        st.session_state.new_lat = ""
    if "new_lng" not in st.session_state:
        st.session_state.new_lng = ""

    # Address Suggestor
    if "update_address" not in st.session_state:
        st.session_state.update_address = ""
    if "update_lat" not in st.session_state:
        st.session_state.update_lat = ""
    if "update_lng" not in st.session_state:
        st.session_state.update_lng = ""


# --- Login Page ---
def login_page():
    st.title("🔐 ArcGIS Data Entry App")
    st.write("Please enter the access code to continue.")

    code = st.text_input("Access Code", type="password")

    if st.button("Login"):
        if code == ACCESS_CODE:
            st.session_state.logged_in = True
            st.session_state.login_mode = "admin"
            st.rerun()
        elif code == GUEST_CODE:
            st.session_state.logged_in = True
            st.session_state.login_mode = "guest"
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
    st.subheader("Service Centers")
    st.dataframe(df, height=500, use_container_width=True)

    if not df.empty:
        selected_index = st.number_input("🔍 Enter row number to edit or delete:", min_value=0, max_value=len(df) - 1, step=1)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("✏️ Edit Selected Entry",disabled=(st.session_state.login_mode != "admin")):
                st.session_state.selected_record = df.loc[selected_index].to_dict()
                st.session_state.object_id = df.loc[selected_index]['ObjectId']
                st.session_state.page = 'edit'
                st.rerun()

        with col2:
            if st.button("🗑️ Delete Selected Entry",disabled=(st.session_state.login_mode != "admin")):
                object_id_to_delete = df.loc[selected_index]['ObjectId']
                try:
                    result = layer.edit_features(deletes=str(object_id_to_delete))
                    success = result.get("deleteResults", [{}])[0].get("success", False)
                    if success:
                        st.success(f"✅ Entry with ObjectId {object_id_to_delete} deleted successfully!")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to delete entry with ObjectId {object_id_to_delete}.")
                except Exception as e:
                    st.error(f"❌ Error during deletion: {e}")
        with col3:
            if st.button("➕ Create New Entry",disabled=(st.session_state.login_mode != "admin")):
                st.session_state.selected_record = {}  # empty dict for new entry
                st.session_state.page = "create"
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


def show_create_page():
    st.title("➕ Create New Feature Entry")

    # Fields with binary (0/1) values
    binary_fields = [
        'Home_Health_Services', 'Adult_Day_Services', 'Benefits_Counseling', 'Elder_Housing_Resources',
        'Assisted_Living', 'Elder_Abuse', 'Home_Repair', 'Immigration_Assistance',
        'Long_term_Care_Ombudsman', 'Long_term_Care_Nursing_Homes', 'Senior_Exercise_Programs',
        'Dementia_Support_Programs', 'Transportation', 'Senior_Centers', 'Caregiver_Support_Services',
        'Case_Management', 'Congregate_Meals', 'Financial_Counseling', 'Health_Education_Workshops',
        'Home_Delivered_Meals', 'Hospice_Care', 'Technology_Training', 'Cultural_Programming',
        'Mental_Health', 'Vaccinations_Screening'
    ]

    new_entry = {}
    errors = []



    address_input = st.text_input("🔍 Search Address", value=st.session_state.new_address, key="new_address_input")

    suggestions = []
    if len(address_input.strip()) >= 3:
        suggestions = get_place_suggestions(address_input)

    if suggestions:
        suggestions_display = ["-- Select an address --"] + suggestions
        selected_address = st.selectbox("📍 Suggestions", suggestions_display, index=0, key="create_address_suggestion")

        if selected_address != "-- Select an address --" and selected_address != st.session_state.new_address:
            st.session_state.new_address = selected_address
            lat, lng = get_lat_lng_from_address(selected_address)
            st.session_state.new_lat = str(lat)
            st.session_state.new_lng = str(lng)
            st.rerun()

    with st.form("create_form"):
        new_entry["Name"] = st.text_input("Name")
        new_entry["Phone_number"] = st.text_input("Phone Number (format: 123-456-7890)")
        if not re.fullmatch(r"\d{3}-\d{3}-\d{4}", new_entry["Phone_number"]):
            errors.append("📞 Invalid phone number format.")

        new_entry["Address"] = st.text_input("Address", value=st.session_state.new_address, disabled=True)
        new_entry["Address_w_suit__"] = st.text_input("Address with Suite")

        col1, col2 = st.columns(2)
        with col1:
            new_entry["Latitude"] = st.text_input("Latitude", value=st.session_state.new_lat, disabled=True)
        with col2:
            new_entry["Longitude"] = st.text_input("Longitude", value=st.session_state.new_lng, disabled=True)

        st.markdown("### 🧩 Service Availability Fields")
        for i in range(0, len(binary_fields), 5):
            cols = st.columns(5)
            for j in range(5):
                if i + j < len(binary_fields):
                    field = binary_fields[i + j]
                    with cols[j]:
                        new_entry[field] = st.selectbox(field, [0, 1], index=0, key=f"new_{field}")

        submitted = st.form_submit_button("✅ Submit New Entry")

    if submitted:
        if errors:
            for err in errors:
                st.error(err)
        else:
            try:
                response = layer.edit_features(adds=[{"attributes": new_entry}])
                if response['addResults'][0].get("success"):
                    st.success("✅ New entry added successfully!")
                    st.session_state.page = "view"
                    st.rerun()
                else:
                    st.error("❌ Failed to add new entry.")
            except Exception as e:
                st.error(f"❌ Error: {e}")

    if st.button("⬅️ Back to Table"):
        st.session_state.page = 'view'
        st.rerun()

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
    #user_input = st.text_input("🔍 Search Address", value=default_address, key="address_suggestor")

    user_input = st.text_input("🔍 Search Address", value=st.session_state.update_address, key="edit_address_input")
    suggestions = []
    if len(user_input.strip()) >= 3:
        suggestions = get_place_suggestions(user_input)

    if suggestions:
        suggestions_display = ["-- Select an address --"] + suggestions
        selected_address = st.selectbox("📍 Suggestions", suggestions_display, index=0, key="edit_address_suggestion")

        if selected_address != "-- Select an address --" and selected_address != st.session_state.update_address:
            st.session_state.update_address = selected_address
            lat, lng = get_lat_lng_from_address(selected_address)
            st.session_state.update_lat = str(lat)
            st.session_state.update_lng = str(lng)
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
                edited[key] = st.text_input("Address", value=st.session_state.update_address, disabled=True)               

            elif key == "Address_w_suit__":
                addr_suite = (key, value)
            elif key == "Latitude":
                edited[key] = st.text_input("Latitude", value=st.session_state.update_lat, disabled=True)
            elif key == "Longitude":
                edited[key] = st.text_input("Longitude", value=st.session_state.update_lng, disabled=True)
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
    elif st.session_state.page == 'create':
        show_create_page()
else:
    login_page()