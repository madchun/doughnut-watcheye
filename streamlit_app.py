"""Streamlit Cloud entry point — runs the main app module."""

import runpy

# Use runpy to execute the app module as a script on every Streamlit rerun.
# A plain `import` would only execute once and break Streamlit's rerun model.
runpy.run_module("watcheye.web.app", run_name="__main__")
