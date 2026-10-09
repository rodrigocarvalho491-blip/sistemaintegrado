import os
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from fpdf import FPDF
import streamlit.components.v1 as components

# --- CONFIGURAÇÃO GLOBAL DA PÁGINA ---
st.set_page_config(page_title="Sistema Integrado de Ocorrências", page_icon="⚙️", layout="wide")

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")

CUSTOM_CSS = """
<style>
    h1, h2, h3 { color: #004080 !important; font-family: 'Segoe UI',
