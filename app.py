import os
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
st.set_page_config(page_title="Sistema Integrado de Ocorrências", page_icon="⚙️", layout="wide")

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")

CUSTOM_CSS = """
<style>
    h1, h2, h3 { color: #004080 !important; font-family: 'Segoe UI', sans-serif; }
    div.stButton > button:first-child {
        background-color: #004080 !important; color: #ffffff !important;
        border-radius: 8px !important; border: none !important; font-weight: bold !important;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

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

# --- FUNÇÃO PARA OBTER O IPCA ACUMULADO DE 12 MESES DO IBGE ATUALIZADO ---
def obter_ipca_acumulado_12m():
    try:
        # Consulta dinâmica baseada no mês/ano atual do sistema
        ano_atual = datetime.now().strftime("%Y")
        mes_atual = datetime.now().strftime("%m")
        periodo_ref = f"{ano_atual}{mes_atual}"
        
        url = f"https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/{periodo_ref}/variaveis/2266?localidades=N1[1]"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            data = response.json()
            val_str = data[0]["resultados"][0]["séries"][0]["série"][periodo_ref]
            if val_str:
                return float(val_str)
    except Exception:
        pass
    
    # Fallback consultando o agregado geral mais recente disponível na API do IBGE
    try:
        url_geral = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-1/variaveis/2266?localidades=N1[1]"
        response = requests.get(url_geral, timeout=3)
        if response.status_code == 200:
            data = response.json()
            serie = data[0]["resultados"][0]["séries"][0]["série"]
            ultimo_periodo = sorted(serie.keys())[-1]
            val_str = serie[ultimo_periodo]
            if val_str:
                return float(val_str)
    except Exception:
        pass
        
    return 4.22  # Valor padrão caso todas as tentativas falhem

# --- INICIALIZAÇÃO DO SESSION STATE ---
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

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

# --- MENU LATERAL DE NAVEGAÇÃO ---
st.sidebar.title("📌 Menu de Navegação")
menu = st.sidebar.radio(
    "Selecione a página:", 
    [
        "📷 Visita de Transferência",
        "📝 Elaboração de Contrato",
        "🎂 Aniversário de Contrato"
    ]
)

st.sidebar.divider()
if st.sidebar.button("🔄 Resetar Sessão Completa"):
    st.session_state.clear()
    st.rerun()


# =====================================================================
# TELA 1: VISITA DE TRANSFERÊNCIA (Relatório Técnico & Fotos)
# =====================================================================
if menu == "📷 Visita de Transferência":
    rc = st.session_state.reset_counter
    ekc = st.session_state.eq_key_counter

    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Visita de Transferência & Relatório Técnico")
        st.markdown("Gerador automatizado de relatórios técnicos e inspeções.")

    st.divider()

    st.button("🔄 Novo Cliente /
