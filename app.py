import streamlit as st

nav = st.navigation(
    [
        st.Page("home.py", title="Home", icon="🏠"),
        st.Page(
            "pages/va/filter_leads_from_campaign.py", title="Filter Leads From Campaign"
        ),
        st.Page("pages/va/add_follow_ups.py", title="Add Follow-ups to Campaigns"),
    ]
)
nav.run()
