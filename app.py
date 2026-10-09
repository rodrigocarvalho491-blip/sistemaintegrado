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
    h1, h2, h3 { color: #004080 !important; font-family: 'Segoe UI', sans-serif; }
    div.stButton > button:first-child {
        background-color: #004080 !important; color: #ffffff !important;
        border-radius: 8px !important; border: none !important; font-weight: bold !important;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- MAPEAMENTO DAS COLUNAS DO EXCEL ---
COL_OCORRENCIA = "Número da ocorrência"
COL_CLIENTE = "Nome do cliente"
COL_ENDERECO = "Endereço de Entrega"
COL_ABERTURA = "Data/Hora de abertura"
COL_PRAZO = "Prazo de Atendimento"
COL_FECHAMENTO = "Data/Hora de fechamento"
COL_SUB_CLASSIF = "Subclassificação Ocorrência"

# --- INICIALIZAÇÃO DO SESSION STATE ---
if "tratadas_manualmente" not in st.session_state:
    st.session_state.tratadas_manualmente = set()

if "ocorrencia_ativa" not in st.session_state:
    st.session_state.ocorrencia_ativa = {"codigo": "", "cliente": ""}

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

# --- FUNÇÕES AUXILIARES DE DATAS E CIDADES ---
def extrair_cidade(endereco):
    if pd.isna(endereco):
        return "-"
    s = str(endereco).strip()
    s_norm = s.replace(';', ',').replace('|', ',')
    partes = [p.strip() for p in s_norm.split(',')]
    if len(partes) >= 2:
        cidade = partes[-2].strip()
        if cidade.isdigit() and len(partes) >= 3:
            cidade = partes[-3].strip()
        return cidade.title()
    return s.title()

def calcular_dias_uteis(data_inicio, data_fim):
    h = pd.Timestamp(data_inicio).normalize().date()
    p = pd.Timestamp(data_fim).normalize().date()
    if p > h:
        return int(np.busday_count(h, p))
    elif p < h:
        return -int(np.busday_count(p, h))
    else:
        return 0

def classificar_status_geral(dias_uteis):
    if dias_uteis < 0:
        return "🔴 Vencido"
    elif dias_uteis == 0:
        return "🔵 Vence Hoje"
    elif dias_uteis == 1:
        return "🟠 Vence Amanhã"
    elif 2 <= dias_uteis <= 5:
        return "🟡 Vence na Semana"
    else:
        return "🟢 No Prazo"

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
        "📊 Dashboard de Ocorrências", 
        "📷 Tratativa & Relatório Técnico",
        "📝 Elaboração de Contrato"
    ]
)

st.sidebar.divider()
if st.sidebar.button("🔄 Resetar Sessão Completa"):
    st.session_state.clear()
    st.rerun()

# =====================================================================
# TELA 1: DASHBOARD DE OCORRÊNCIAS (Menu Principal)
# =====================================================================
if menu == "📊 Dashboard de Ocorrências":
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
        else:
            st.caption("📷 *Adicione 'logo.png' na pasta*")
    with col_titulo:
        st.title("Gestão de Ocorrências & Visitas")
        st.markdown("Painel de organização de agenda ordenado por prazo de atendimento (Dias Úteis).")

    st.divider()
    st.subheader("1. Atualização de Dados (Excel)")
    arquivo_excel = st.file_uploader("Faça o upload do relatório Excel (Pós-Vendas) 📂", type=["xlsx", "xls"])

    if arquivo_excel is not None:
        try:
            df_raw = pd.read_excel(arquivo_excel, header=None)
            header_row = None
            for i, row in df_raw.iterrows():
                row_str = " ".join(row.astype(str).values)
                if "Número da ocorrência" in row_str:
                    header_row = i
                    break
            
            df = pd.read_excel(arquivo_excel, header=header_row if header_row is not None else 11)
            df.columns = df.columns.str.strip()
            df = df.dropna(subset=[COL_OCORRENCIA])
            
            df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
            df_pendentes[COL_OCORRENCIA] = pd.to_numeric(df_pendentes[COL_OCORRENCIA], errors='coerce')
            df_pendentes = df_pendentes.dropna(subset=[COL_OCORRENCIA])
            df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
            df_pendentes = df_pendentes[~df_pendentes[COL_OCORRENCIA].isin(st.session_state.tratadas_manualmente)]
            
            df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
            df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
            df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
            df_pendentes[COL_SUB_CLASSIF] = df_pendentes[COL_SUB_CLASSIF].fillna("-").astype(str)
            
            hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            df_pendentes['Dias Úteis Restantes'] = df_pendentes['Prazo_DT'].apply(lambda x: calcular_dias_uteis(hoje, x))
            df_pendentes['Status Geral'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_geral)
            df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
            
            st.subheader("2. Agenda Geral de Visitas Pendentes")
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                mostrar_so_hoje = st.toggle("📅 Mostrar apenas ocorrências com prazo PARA HOJE", value=False)
            with col_t2:
                mostrar_so_semana = st.toggle("🗓️ Mostrar apenas os próximos 5 dias úteis", value=False)
            
            cidades_unicas = sorted(list(df_pendentes['Cidade'].unique()))
            sub_class_unicas = sorted(list(df_pendentes[COL_SUB_CLASSIF].unique()))
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                cidades_selecionadas = st.multiselect("Filtrar por Cidade(s):", cidades_unicas)
            with col_f2:
                sub_class_selecionadas = st.multiselect("Filtrar por Sub-Classificação:", sub_class_unicas)
            
            df_filtrado = df_pendentes.copy()
            if mostrar_so_hoje:
                hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                hoje_fim = hoje_inicio + timedelta(days=1) - timedelta(seconds=1)
                df_filtrado = df_filtrado[(df_filtrado['Prazo_DT'] >= hoje_inicio) & (df_
