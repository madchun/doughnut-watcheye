"""Streamlit Cloud entry point — imports and runs the main app."""

import importlib

# The watcheye package is installed via `requirements.txt` (`.` entry)
# so we can import the app module directly. Streamlit executes this file
# as its main script; importing the module runs all top-level Streamlit calls.
import watcheye.web.app  # noqa: F401
