
import streamlit as st

def login_page():
    st.title("🏥 MediCare Login")

    role = st.selectbox("Login as", ["Patient", "Doctor", "Admin"])
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        # Demo login (replace with DB check later)
        if email and password:
            st.session_state.logged_in = True
            st.session_state.role = role
            st.session_state.page = "dashboard"
            st.rerun()
        else:
            st.error("Please enter email and password")

    st.markdown("Don't have an account?")
    if st.button("Signup"):
        st.session_state.page = "signup"
        st.rerun()
