import os
import json
import base64
import html as html_lib
import uuid
import tempfile
import pandas as pd
import numpy as np
import streamlit as st
import requests
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from fpdf import FPDF
import streamlit.components.v1 as components

# --- CONFIGURAÇÃO GLOBAL DA PÁGINA ---
st.set_page_config(
    page_title="Sistema Integrado de Ocorrências | Consigaz", 
    page_icon="⚡", 
    layout="wide"
)

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")

# =====================================================================
# IDENTIDADE VISUAL CONSIGAZ - DESIGN MODERNO (SUPORTE DARK/LIGHT)
# =====================================================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
  --cg-azul-principal: #003366;
  --cg-azul-vibrante: #0055A5;
  --cg-laranja: #F28C28;
}

html, body, [class*="css"] {
  font-family: 'Plus Jakarta+Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

/* Cabeçalho Consigaz com Barra de Destaque */
.cg-header { 
  display: flex; 
  align-items: center; 
  gap: 1.2rem; 
  position: relative;
  padding-bottom: 1.2rem; 
  margin-bottom: 1.5rem; 
  border-bottom: 1px solid rgba(120, 140, 160, 0.25); 
}
.cg-header::after { 
  content: ""; 
  position: absolute; 
  left: 0; 
  bottom: -1px; 
  width: 140px; 
  height: 4px; 
  border-radius: 4px; 
  background: linear-gradient(90deg, var(--cg-azul-vibrante) 0%, var(--cg-laranja) 100%); 
}
.cg-logo { height: 48px; width: auto; display: block; }
.cg-header-sep { width: 1px; align-self: stretch; background: rgba(120, 140, 160, 0.25); }
.cg-title { font-size: 1.6rem; font-weight: 800; line-height: 1.2; letter-spacing: -0.02em; }
.cg-subtitle { font-size: 0.92rem; margin-top: 0.25rem; opacity: 0.75; font-weight: 500; }

/* Subtítulos de Seção Customizados */
.stApp h3 {
  font-size: 1.05rem !important;
  font-weight: 700 !important;
  padding-left: 0.75rem !important;
  border-left: 4px solid var(--cg-azul-vibrante) !important;
  margin-top: 1.2rem !important;
  margin-bottom: 0.8rem !important;
}

/* Estilização moderna dos Botões */
.stButton > button, .stDownloadButton > button {
  border-radius: 10px !important;
  font-weight: 700 !important;
  padding: 0.5rem 1.2rem !important;
  transition: all 0.2s ease-in-out !important;
}

.stButton > button[kind="primary"], .stDownloadButton > button {
  background-color: var(--cg-azul-vibrante) !important;
  color: #FFFFFF !important;
  border: none !important;
}

.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
  background-color: var(--cg-azul-principal) !important;
  box-shadow: 0 4px 12px rgba(0, 85, 165, 0.25);
}

/* Sidebar refinada */
[data-testid="stSidebar"] {
  border-right: 1px solid rgba(120, 140, 160, 0.15);
}
.cg-side-brand { 
  padding: 0.5rem 0.2rem 1.2rem 0.2rem; 
  margin-bottom: 1rem; 
  border-bottom: 1px solid rgba(120, 140, 160, 0.15); 
}
.cg-side-logo { height: 38px; width: auto; display: block; }
.cg-side-name { margin-top: 0.6rem; font-size: 0.78rem; font-weight: 600; opacity: 0.7; letter-spacing: 0.03em; text-transform: uppercase; }

[data-testid="stSidebar"] [role="radiogroup"] label {
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.2rem;
  transition: background 0.2s;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _logo_base64(caminho):
    try:
        with open(caminho, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


def _logo_html(classe):
    b64 = _logo_base64(LOGO_PATH)
    if not b64:
        return ""
    return f'<img class="{classe}" src="data:image/png;base64,{b64}" alt="Consigaz">'


def cabecalho_pagina(titulo, subtitulo):
    logo = _logo_html("cg-logo")
    separador = '<div class="cg-header-sep"></div>' if logo else ""
    st.markdown(
        f'<div class="cg-header">{logo}{separador}<div>'
        f'<div class="cg-title">{html_lib.escape(titulo)}</div>'
        f'<div class="cg-subtitle">{html_lib.escape(subtitulo)}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

# --- FUNÇÃO DE CONSULTA AUTOMÁTICA DE CNPJ ---
def consultar_cnpj_api(cnpj_input):
    cnpj_limpo = "".join(filter(str.isdigit, str(cnpj_input)))
    if len(cnpj_limpo) == 14:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception:
            return None
    return None

# --- FUNÇÃO PARA OBTER O IPCA ACUMULADO DE 12 MESES ATUALIZADO DO IBGE ---
IPCA_VALOR_RESERVA = 4.58

@st.cache_data(ttl=3600, show_spinner=False)
def _buscar_ipca_ibge():
    url = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-1/variaveis/2265?localidades=N1[1]"
    response = requests.get(url, timeout=6)
    response.raise_for_status()
    data = response.json()
    resultado = data[0]["resultados"][0]
    series =
