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

# --- CONFIGURAÇÃO GLOBAL DA PÁGINA (LOGO / FOGUINHO NA ABA) ---
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
# IDENTIDADE VISUAL CONSIGAZ - DESIGN MODERNO & ARREDONDADO
# =====================================================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

:root {
  --cg-azul-principal: #003366;
  --cg-azul-vibrante: #0055A5;
  --cg-laranja: #F28C28;
  --cg-suave: #F4F7FB;
  --cg-borda: #E2E8F0;
}

html, body, [class*="css"] {
  font-family: 'Plus Jakarta Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
}

[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

/* Bloco principal com efeito de card flutuante e bordas super arredondadas */
.block-container, [data-testid="stMainBlockContainer"] {
  max-width: 1200px !important;
  margin: 1.5rem auto !important;
  padding: 2.5rem !important;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 24px !important;
  box-shadow: 0 10px 30px rgba(0, 51, 102, 0.08);
  border: 1px solid var(--cg-borda);
}

/* Cabeçalho Consigaz com destaque refinado */
.cg-header { 
  display: flex; 
  align-items: center; 
  gap: 1.5rem; 
  position: relative;
  padding-bottom: 1.5rem; 
  margin-bottom: 2rem; 
  border-bottom: 2px solid var(--cg-borda); 
}
.cg-header::after { 
  content: ""; 
  position: absolute; 
  left: 0; 
  bottom: -2px; 
  width: 160px; 
  height: 4px; 
  border-radius: 4px; 
  background: linear-gradient(90deg, var(--cg-azul-vibrante) 0%, var(--cg-laranja) 100%); 
}
.cg-logo { height: 55px; width: auto; display: block; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.05)); }
.cg-header-sep { width: 2px; align-self: stretch; background: var(--cg-borda); opacity: 0.6; }
.cg-title { font-size: 1.8rem; font-weight: 800; color: var(--cg-azul-principal); line-height: 1.2; letter-spacing: -0.02em; }
.cg-subtitle { font-size: 0.98rem; color: #64748B; margin-top: 0.3rem; font-weight: 500; }

/* Títulos de Seção Estilizados */
.stApp h1, .stApp h2 { color: var(--cg-azul-principal) !important; font-weight: 800 !important; }
.stApp h3 {
  font-size: 1.15rem !important;
  font-weight: 700 !important;
  color: var(--cg-azul-vibrante) !important;
  padding: 0.3rem 0 0.3rem 0.8rem !important;
  border-left: 5px solid var(--cg-laranja) !important;
  background: linear-gradient(90deg, rgba(242, 140, 40, 0.08) 0%, transparent 100%);
  border-radius: 0 8px 8px 0;
  margin-top: 1.8rem !important;
  margin-bottom: 1.2rem !important;
}

/* Inputs, selects e textareas super arredondados e modernos */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
  border-radius: 14px !important;
  border: 1.5px solid var(--cg-borda) !important;
  background-color: #FAFCFF !important;
  transition: all 0.2s ease;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: var(--cg-azul-vibrante) !important;
  box-shadow: 0 0 0 4px rgba(0, 85, 165, 0.12) !important;
  background-color: #FFFFFF !important;
}

/* Botões modernos, arredondados e com sombras suaves */
.stButton > button, .stDownloadButton > button {
  border-radius: 14px !important;
  font-weight: 700 !important;
  padding: 0.6rem 1.4rem !important;
  border: 1.5px solid var(--cg-borda);
  background-color: #FFFFFF;
  color: var(--cg-azul-principal);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
  box-shadow: 0 2px 5px rgba(0,0,0,0.02);
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color: var(--cg-azul-vibrante);
  color: var(--cg-azul-vibrante);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 85, 165, 0.1);
}

.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"], .stDownloadButton > button {
  background: linear-gradient(135deg, var(--cg-azul-vibrante) 0%, var(--cg-azul-principal) 100%) !important;
  color: #FFFFFF !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(0, 85, 165, 0.25) !important;
}
.stButton > button[kind="primary"]:hover, .stButton > button[data-testid="stBaseButton-primary"]:hover, .stDownloadButton > button:hover {
  opacity: 0.95;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 85, 165, 0.35) !important;
}

/* Sidebar moderna e limpa */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
  border-right: 1px solid var(--cg-borda);
}
.cg-side-brand { 
  padding: 1rem 0.5rem 1.5rem 0.5rem; 
  margin-bottom: 1.2rem; 
  border-bottom: 1px solid var(--cg-borda); 
  text-align: center;
}
.cg-side-logo { height: 45px; width: auto; display: inline-block; }
.cg-side-name { margin-top: 0.8rem; font-size: 0.75rem; font-weight: 700; color: #64748B; letter-spacing: 0.08em; text-transform: uppercase; }

[data-testid="stSidebar"] [role="radiogroup"] label {
  border-radius: 12px !important;
  padding: 0.7rem 1rem !important;
  margin-bottom: 0.4rem !important;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
  background: rgba(0, 85, 165, 0.06);
  border-color: rgba(0, 85, 165, 0.1);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(0, 85, 165, 0.12) 0%, rgba(0, 85, 165, 0.03) 100%);
  border-left: 4px solid var(--cg-laranja);
  box-shadow: 0 2px 8px rgba(0,85,165,0.06);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {
  color: var(--cg-azul-principal);
  font-weight: 800 !important;
}

/* Divisor elegante */
hr { border-color: var(--cg-borda) !important; margin: 2rem 0 !important; opacity: 0.6; }
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

if "reset_counter_aniv" not in st.session_state:
    st.session_state.reset_counter_aniv = 0

if "eq_key_counter" not in st.session_state:
    st.session_state.eq_key_counter = 0

if "equipamentos" not in st.session_state:
    st.session_state.equipamentos = []

if "last_central" not in st.session_state:
    st.session_state.last_central = "Central"

if "last_tipo_cad" not in st.session_state:
    st.session_state.last_tipo_cad = "Equipamentos"

def resetar_dados_cliente():
    st.session_state.reset_counter += 1
    st.session_state.eq_key_counter = 0
    st.session_state.equipamentos = []
    st.session_state.last_central = "Central"
    st.session_state.last_tipo_cad = "Equipamentos"

def resetar_dados_contrato():
    st.session_state.reset_counter_contrato += 1

def resetar_dados_aprov():
    st.session_state.reset_counter_aprov += 1

def resetar_dados_aniv():
    st.session_state.reset_counter_aniv += 1

# --- COMPONENTE DE BOTÃO DE CÓPIA ---
def botao_copiar_customizado(texto_para_copiar, chave_unica):
    texto_norm = str(texto_para_copiar).replace("\r\n", "\n").replace("\r", "\n")
    texto_js = json.dumps(texto_norm).replace("</", "<\\/")

    component_html = f"""
    <div style="margin-top: 10px; margin-bottom: 15px;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background: linear-gradient(1
