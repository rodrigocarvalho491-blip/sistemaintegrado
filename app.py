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
    page_title="Sistema Integrado | Consigaz", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")

# =====================================================================
# IDENTIDADE VISUAL CONSIGAZ - ESTRUTURA ORIGINAL MODERNA
# =====================================================================
COR_AZUL = "#003366"
COR_AZUL_ESCURO = "#002244"
COR_AZUL_HOVER = "#004080"
COR_AZUL_CLARO = "#F1F5F9"
COR_DESTAQUE = "#F28C28"
COR_FUNDO = "#F8FAFC"
COR_TEXTO = "#1E293B"
COR_TEXTO_SUAVE = "#475569"
COR_BORDA = "#CBD5E1"

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
  font-family: 'Plus Jakarta Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
  background-color: FUNDO_PLACEHOLDER !important;
  color: TEXTO_PLACEHOLDER !important;
}

[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

/* Bloco principal flutuante */
.block-container, [data-testid="stMainBlockContainer"] {
  max-width: 1200px !important;
  margin: 1.5rem auto !important;
  padding: 2.5rem !important;
  background-color: #FFFFFF !important;
  border-radius: 20px !important;
  box-shadow: 0 10px 30px rgba(0, 51, 102, 0.06);
  border: 1px solid BORDA_PLACEHOLDER;
}

/* Cabeçalho Consigaz */
.cg-header { 
  display: flex; 
  align-items: center; 
  gap: 1.8rem; 
  position: relative;
  padding-bottom: 1.5rem; 
  margin-bottom: 2rem; 
  border-bottom: 2px solid BORDA_PLACEHOLDER; 
}
.cg-header::after { 
  content: ""; 
  position: absolute; 
  left: 0; 
  bottom: -2px; 
  width: 160px; 
  height: 4px; 
  border-radius: 4px; 
  background: linear-gradient(90deg, AZUL_PLACEHOLDER 0%, DESTAQUE_PLACEHOLDER 100%); 
}

.cg-logo-wrapper {
  background: #FFFFFF;
  padding: 8px 14px;
  border-radius: 14px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(0, 51, 102, 0.1);
}
.cg-logo { height: 68px; width: auto; display: block; }

.cg-header-sep { width: 2px; align-self: stretch; background: BORDA_PLACEHOLDER; }
.cg-title { font-size: 1.8rem; font-weight: 800; line-height: 1.2; letter-spacing: -0.02em; color: AZUL_ESCURO_PLACEHOLDER !important; }
.cg-subtitle { font-size: 0.98rem; margin-top: 0.3rem; color: TEXTO_SUAVE_PLACEHOLDER !important; font-weight: 500; }

/* Títulos de Seção */
.stApp h1, .stApp h2, .stApp h3 {
  color: AZUL_ESCURO_PLACEHOLDER !important;
}
.stApp h3 {
  font-size: 1.15rem !important;
  font-weight: 700 !important;
  padding: 0.3rem 0 0.3rem 0.8rem !important;
  border-left: 5px solid DESTAQUE_PLACEHOLDER !important;
  background: linear-gradient(90deg, rgba(242, 140, 40, 0.08) 0%, transparent 100%);
  border-radius: 0 8px 8px 0;
  margin-top: 1.8rem !important;
  margin-bottom: 1.2rem !important;
}

/* Botões Modernos */
.stButton > button, .stDownloadButton > button {
  border-radius: 12px !important;
  font-weight: 700 !important;
  padding: 0.6rem 1.4rem !important;
  transition: all 0.2s ease;
}

.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"], .stDownloadButton > button {
  background: linear-gradient(135deg, AZUL_PLACEHOLDER 0%, AZUL_ESCURO_PLACEHOLDER 100%) !important;
  color: #FFFFFF !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(0, 51, 102, 0.2);
}
.stButton > button[kind="primary"]:hover, .stButton > button[data-testid="stBaseButton-primary"]:hover {
  opacity: 0.95;
  transform: translateY(-1px);
}

/* Sidebar */
[data-testid="stSidebar"] {
  background-color: AZUL_CLARO_PLACEHOLDER !important;
  border-right: 1px solid BORDA_PLACEHOLDER;
}
.cg-side-brand { 
  padding: 1rem 0.5rem 1.5rem 0.5rem; 
  margin-bottom: 1.2rem; 
  border-bottom: 1px solid BORDA_PLACEHOLDER; 
  text-align: center;
}
.cg-side-logo-wrapper {
  background: #FFFFFF;
  padding: 8px 12px;
  border-radius: 12px;
  display: inline-block;
  box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}
.cg-side-logo { height: 42px; width: auto; display: inline-block; }
.cg-side-name { margin-top: 0.8rem; font-size: 0.75rem; font-weight: 700; color: TEXTO_SUAVE_PLACEHOLDER !important; letter-spacing: 0.08em; text-transform: uppercase; }

[data-testid="stSidebar"] [role="radiogroup"] label {
  border-radius: 10px !important;
  padding: 0.6rem 1rem !important;
  margin-bottom: 0.4rem !important;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  background-color: #FFFFFF !important;
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(0, 51, 102, 0.1) 0%, rgba(0, 51, 102, 0.02) 100%) !important;
  border-left: 4px solid DESTAQUE_PLACEHOLDER;
  border-color: rgba(0, 51, 102, 0.15);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {
  font-weight: 800 !important;
  color: AZUL_ESCURO_PLACEHOLDER !important;
}

hr { border-color: BORDA_PLACEHOLDER !important; margin: 2rem 0 !important; }
</style>
"""

# Substituição de Variáveis no CSS
substituicoes = {
    "AZUL_PLACEHOLDER": COR_AZUL,
    "AZUL_ESCURO_PLACEHOLDER": COR_AZUL_ESCURO,
    "AZUL_HOVER_PLACEHOLDER": COR_AZUL_HOVER,
    "AZUL_CLARO_PLACEHOLDER": COR_AZUL_CLARO,
    "DESTAQUE_PLACEHOLDER": COR_DESTAQUE,
    "FUNDO_PLACEHOLDER": COR_FUNDO,
    "TEXTO_PLACEHOLDER": COR_TEXTO,
    "TEXTO_SUAVE_PLACEHOLDER": COR_TEXTO_SUAVE,
    "BORDA_PLACEHOLDER": COR_BORDA,
}
for k, v in substituicoes.items():
    CUSTOM_CSS = CUSTOM_CSS.replace(k, v)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _logo_base64(caminho):
    try:
        with open(caminho, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


def _logo_html(classe_img, classe_wrapper=""):
    b64 = _logo_base64(LOGO_PATH)
    if not b64:
        return ""
    img_tag = f'<img class="{classe_img}" src="data:image/png;base64,{b64}" alt="Consigaz">'
    if classe_wrapper:
        return f'<div class="{classe_wrapper}">{img_tag}</div>'
    return img_tag


def cabecalho_pagina(titulo, subtitulo):
    logo = _logo_html("cg-logo", "cg-logo-wrapper")
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
    series = resultado.get("series") or resultado.get("séries")
    serie = series[0].get("serie") or series[0].get("série")
    ultimo_periodo = sorted(serie.keys())[-1]
    val_str = serie[ultimo_periodo]
    if not val_str or str(val_str).strip() in ("-", "..", "...", "X"):
        raise ValueError("IBGE retornou valor vazio para o período.")
    return float(val_str), ultimo_periodo

def obter_ipca_acumulado_12m():
    try:
        valor, periodo = _buscar_ipca_ibge()
        if len(periodo) == 6:
            periodo = f"{periodo[4:6]}/{periodo[0:4]}"
        return valor, periodo
    except Exception:
        return None, None

# --- INICIALIZAÇÃO DO SESSION STATE ---
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

if "reset_counter_contrato" not in st.session_state:
    st.session_state.reset_counter_contrato = 0

if "reset_counter_aprov" not in st.session_state:
    st.session_state.reset_counter_aprov = 0

if "reset_
