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
# IDENTIDADE VISUAL CONSIGAZ - DESIGN MODERNO
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
  font-family: 'Plus Jakarta Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
}

[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

/* Bloco principal flutuante e moderno com bordas arredondadas */
.block-container, [data-testid="stMainBlockContainer"] {
  max-width: 1200px !important;
  margin: 1.5rem auto !important;
  padding: 2.5rem !important;
  border-radius: 24px !important;
  box-shadow: 0 10px 30px rgba(0, 51, 102, 0.08);
  border: 1px solid rgba(120, 140, 160, 0.2);
}

/* Cabeçalho Consigaz com destaque refinado */
.cg-header { 
  display: flex; 
  align-items: center; 
  gap: 1.8rem; 
  position: relative;
  padding-bottom: 1.5rem; 
  margin-bottom: 2rem; 
  border-bottom: 2px solid rgba(120, 140, 160, 0.2); 
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

/* Logotipo em evidência com cantos arredondados, padding e sombra suave */
.cg-logo-wrapper {
  background: #FFFFFF;
  padding: 8px 14px;
  border-radius: 14px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.cg-logo { height: 68px; width: auto; display: block; }

.cg-header-sep { width: 2px; align-self: stretch; background: rgba(120, 140, 160, 0.3); }
.cg-title { font-size: 1.8rem; font-weight: 800; line-height: 1.2; letter-spacing: -0.02em; }
.cg-subtitle { font-size: 0.98rem; margin-top: 0.3rem; opacity: 0.8; font-weight: 500; }

/* Títulos de Seção Estilizados */
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

/* Inputs, selects e textareas super arredondados e fluidos */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
  border-radius: 14px !important;
  border: 1.5px solid rgba(120, 140, 160, 0.3) !important;
  transition: all 0.2s ease;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: var(--cg-azul-vibrante) !important;
  box-shadow: 0 0 0 4px rgba(0, 85, 165, 0.15) !important;
}

/* Botões modernos, arredondados e com sombras suaves */
.stButton > button, .stDownloadButton > button {
  border-radius: 14px !important;
  font-weight: 700 !important;
  padding: 0.6rem 1.4rem !important;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
  box-shadow: 0 2px 5px rgba(0,0,0,0.02);
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
  border-right: 1px solid rgba(120, 140, 160, 0.2);
}
.cg-side-brand { 
  padding: 1rem 0.5rem 1.5rem 0.5rem; 
  margin-bottom: 1.2rem; 
  border-bottom: 1px solid rgba(120, 140, 160, 0.2); 
  text-align: center;
}
.cg-side-logo-wrapper {
  background: #FFFFFF;
  padding: 8px 12px;
  border-radius: 12px;
  display: inline-block;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.cg-side-logo { height: 42px; width: auto; display: inline-block; }
.cg-side-name { margin-top: 0.8rem; font-size: 0.75rem; font-weight: 700; opacity: 0.7; letter-spacing: 0.08em; text-transform: uppercase; }

[data-testid="stSidebar"] [role="radiogroup"] label {
  border-radius: 12px !important;
  padding: 0.7rem 1rem !important;
  margin-bottom: 0.4rem !important;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(0, 85, 165, 0.15) 0%, rgba(0, 85, 165, 0.03) 100%);
  border-left: 4px solid var(--cg-laranja);
  box-shadow: 0 2px 8px rgba(0,85,165,0.06);
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {
  font-weight: 800 !important;
}

hr { border-color: rgba(120, 140, 160, 0.2) !important; margin: 2rem 0 !important; }
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

# --- INICIALIZAÇÃO DE VARIÁVEIS DE SESSÃO ---
COL_OCORRENCIA = "Número da ocorrência"
COL_CLIENTE = "Nome do cliente"
COL_ENDERECO = "Endereço de Entrega"
COL_ABERTURA = "Data/Hora de abertura"
COL_PRAZO = "Prazo de Atendimento"
COL_FECHAMENTO = "Data/Hora de fechamento"
COL_SUB_CLASSIF = "Subclassificação Ocorrência"

if "tratadas_manualmente" not in st.session_state:
    st.session_state.tratadas_manualmente = set()

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

def classificar_status_comodato(dias_uteis):
    if dias_uteis < 0:
        return "🔴 Vencido"
    elif dias_uteis == 0:
        return "🔵 Vence Hoje"
    elif dias_uteis == 1:
        return "🟠 Vence Amanhã"
    elif dias_uteis <= 5:
        return "🔴 3ª Semana"
    elif dias_uteis <= 10:
        return "🟡 2ª Semana"
    else:
        return "🟢 1ª Semana"

# --- MENU LATERAL DE NAVEGAÇÃO ---
side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
st.sidebar.markdown(
    f'<div class="cg-side-brand">{side_logo_html}'
    f'<div class="cg-side-name">Gestão de Ocorrências</div></div>',
    unsafe_allow_html=True,
)
menu = st.sidebar.radio(
    "Selecione a página:",
    [
        "📊 Dashboard de Ocorrências",
        "📷 Tratativa & Relatório Técnico"
    ],
    label_visibility="collapsed"
)

st.sidebar.divider()
if st.sidebar.button("🔄 Resetar Sessão"):
    resetar_dados_cliente()
    st.rerun()


# =====================================================================
# TELA 1: DASHBOARD DE OCORRÊNCIAS
# =====================================================================
if menu == "📊 Dashboard de Ocorrências":
    cabecalho_pagina("Gestão de Ocorrências & Visitas", "Painel de organização de agenda ordenado por prazo de atendimento.")

    st.divider()
    st.subheader("1. Atualização de Dados")
    arquivo_excel = st.file_uploader("Faça o upload do relatório Excel (Pós-Vendas) 📂", type=["xlsx", "xls"], key="up_ocorrencias")

    st.divider()

    if arquivo_excel is not None:
        try:
            df = pd.read_excel(arquivo_excel, header=11)
            df = df.dropna(subset=[COL_OCORRENCIA])
            
            df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
            df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
            df_pendentes = df_pendentes[~df_pendentes[COL_OCORRENCIA].isin(st.session_state.tratadas_manualmente)]
            
            df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
            df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
            df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
            df_pendentes[COL_SUB_CLASSIF] = df_pendentes[COL_SUB_CLASSIF].fillna("-").astype(str)
            
            hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            df_pendentes['Dias Úteis Restantes'] = df_pendentes['Prazo_DT'].apply(lambda x: calcular_dias_uteis(hoje, x))
            
            df_pendentes['Status Geral'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_geral)
            df_pendentes['Status Comodato'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_comodato)
            df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
            
            st.subheader("2. Agenda Geral de Visitas Pendentes")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                mostrar_so_hoje = st.toggle("📅 Mostrar apenas ocorrências com prazo PARA HOJE", value=False)
            with col_f2:
                mostrar_so_semana = st.toggle("🗓️ Mostrar apenas os próximos 5 dias úteis", value=False)
            
            cidades_unicas = sorted(list(df_pendentes['Cidade'].unique()))
            sub_class_unicas = sorted(list(df_pendentes[COL_SUB_CLASSIF].unique()))
            
            col_fc1, col_fc2 = st.columns(2)
            with col_fc1:
                cidades_selecionadas = st.multiselect("Filtrar por Cidade(s):", cidades_unicas, default=[])
            with col_fc2:
                sub_class_selecionadas = st.multiselect("Filtrar por Sub-Classificação:", sub_class_unicas, default=[])
            
            df_filtrado = df_pendentes.copy()
            if mostrar_so_hoje:
                hoje_fim = hoje + timedelta(days=1) - timedelta(seconds=1)
                df_filtrado = df_filtrado[(df_filtrado['Prazo_DT'] >= hoje) & (df_filtrado['Prazo_DT'] <= hoje_fim)]
            elif mostrar_so_semana:
                df_filtrado = df_filtrado[(df_filtrado['Dias Úteis Restantes'] >= 0) & (df_filtrado['Dias Úteis Restantes'] <= 5)]
                
            if cidades_selecionadas:
                df_filtrado = df_filtrado[df_filtrado['Cidade'].isin(cidades_selecionadas)]
            if sub_class_selecionadas:
                df_filtrado = df_filtrado[df_filtrado[COL_SUB_CLASSIF].isin(sub_class_selecionadas)]
            
            df_filtrado['Data Atendimento'] = df_filtrado['Prazo_DT'].dt.strftime('%d/%m/%Y')
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Visitas Pendentes", len(df_filtrado))
            with col_m2:
                st.metric("Vence Hoje", len(df_filtrado[df_filtrado['Status Geral'] == "🔵 Vence Hoje"]))
            with col_m3:
                st.metric("Vence Amanhã", len(df_filtrado[df_filtrado['Status Geral'] == "🟠 Vence Amanhã"]))
            with col_m4:
                st.metric("Vencidas", len(df_filtrado[df_filtrado['Status Geral'] == "🔴 Vencido"]))
            
            st.write("---")
            if df_filtrado.empty:
                st.success("✅ Excelente! Não há nenhuma ocorrência pendente para os filtros selecionados.")
            else:
                df_exibicao = df_filtrado[[
                    'Status Geral', 'Dias Úteis Restantes', COL_OCORRENCIA, 
                    COL_CLIENTE, 'Cidade', COL_SUB_CLASSIF, 'Data Atendimento'
                ]].copy()
                df_exibicao[COL_OCORRENCIA] = df_exibicao[COL_OCORRENCIA].astype(str)
                
                edited_df = st.data_editor(
                    df_exibicao.assign(Tratar=False),
                    column_config={
                        "Tratar": st.column_config.CheckboxColumn("✅ Marcar Tratada?", required=True),
                        'Status Geral': st.column_config.TextColumn("Status", disabled=True),
                        'Dias Úteis Restantes': st.column_config.NumberColumn("Dias Restantes", disabled=True),
                        COL_OCORRENCIA: st.column_config.TextColumn("Nº Ocorrência", disabled=True),
                        COL_CLIENTE: st.column_config.TextColumn("Nome do Cliente", disabled=True),
                        'Cidade': st.column_config.TextColumn("Cidade", disabled=True),
                        COL_SUB_CLASSIF: st.column_config.TextColumn("Sub-Classificação", disabled=True),
                        'Data Atendimento': st.column_config.TextColumn("Data de Atendimento", disabled=True),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_geral_ocs"
                )
                
                ocs_para_tratar = edited_df[edited_df["Tratar"] == True][COL_OCORRENCIA].tolist()
                if ocs_para_tratar:
                    st.warning(f"⚠️ Selecionadas **{len(ocs_para_tratar)}** ocorrência(s) para tratar.")
                    if st.button("🔒 Confirmar e Remover do Painel", type="primary"):
                        for oc in ocs_para_tratar:
                            st.session_state.tratadas_manualmente.add(int(oc))
                        st.success("✅ Ocorrência(s) tratada(s) com sucesso!")
                        st.rerun()

        except Exception as e:
            st.error(f"⚠️ Erro ao processar o arquivo de ocorrências: {e}")
    else:
        st.info("👆 Faça o upload da planilha Excel de ocorrências para carregar o dashboard.")


# =====================================================================
# TELA 2: TRATATIVA & RELATÓRIO TÉCNICO
# =====================================================================
elif menu == "📷 Tratativa & Relatório Técnico":
    rc = st.session_state.reset_counter
    ekc = st.session_state.eq_key_counter

    cabecalho_pagina("Visita de Transferência & Relatório Técnico", "Gerador automatizado de relatórios técnicos e inspeções.")

    st.divider()

    st.subheader("1. Identificação do Cliente")
    s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
    with s1_l1_c1:
        cod_cliente = st.text_input("Código do Cliente *", key=f"input_cod_{rc}")
    with s1_l1_c2:
        nome_cliente = st.text_input("Nome / Razão Social *", key=f"input_nome_{rc}")
    with s1_l1_c3:
        telefone = st.text_input("Telefone *", key=f"input_tel_{rc}")

    s1_l2_c1, s1_l2_c2, s1_l2_c3 = st.columns(3)
    with s1_l2_c1:
        contato = st.text_input("Contato *", key=f"input_contato_{rc}")
    with s1_l2_c2:
        departamento = st.text_input("Sobrenome ou Departamento *", key=f"input_depto_{rc}")
    with s1_l2_c3:
        st.write("")

    st.divider()

    st.subheader("2. Informações Contratuais")
    s2_l1_c1, s2_l1_c2, s2_l1_c3, s2_l1_c4 = st.columns(4)
    with s2_l1_c1:
        eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_contrato_{rc}")
    with s2_l1_c2:
        desc_eq_contrato = st.text_input("Quais equipamentos disponíveis? *", key=f"desc_eq_contrato_{rc}")
    with s2_l1_c3:
        tem_freq = st.radio("Possui programação cadastrada? *", ["Sim", "Não"], horizontal=True, index=None, key=f"tem_freq_{rc}")
    with s2_l1_c4:
        desc_freq = ""
        if tem_freq == "Sim":
            desc_freq = st.text_input("Qual a programação? *", key=f"freq_cad_sim_{rc}")
        elif tem_freq == "Não":
            desc_freq = st.text_input("Nº OC de Cadastramento *", key=f"freq_cad_nao_{rc}")
        else:
            st.write("")

    s2_l2_c1, s2_l2_c2 = st.columns(2)
    with s2_l2_c1:
        consumo_previsto = st.text_input("Consumo Previsto (kg) *", key=f"cons_prev_{rc}")
    with s2_l2_c2:
        consumo_real = st.text_input("Consumo Real/Médio (kg) *", key=f"cons_real_{rc}")

    s2_l3_c1, s2_l3_c2 = st.columns(2)
    with s2_l3_c1:
        possui_art = st.radio("Possui ART? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_art_{rc}")
    with s2_l3_c2:
        desc_art = ""
        if possui_art == "Sim":
            desc_art = st.text_input("Número da ART *", key=f"art_sim_{rc}")
        elif possui_art == "Não":
            desc_art = st.text_input("Nº OC de Solicitação de Laudo *", key=f"art_nao_{rc}")
        else:
            st.write("")

    s2_l4_c1, s2_l4_c2 = st.columns(2)
    with s2_l4_c1:
        possui_debitos = st.radio("Cliente possui débitos? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_debitos_{rc}")
    with s2_l4_c2:
        desc_debitos = st.text_input("Detalhes dos Débitos", key=f"desc_debitos_{rc}") if possui_debitos == "Sim" else ""

    s2_l5_c1, s2_l5_c2 = st.columns(2)
    with s2_l5_c1:
        central_norma = st.radio("Central dentro de norma? *", ["Sim", "Não"], horizontal=True, index=None, key=f"central_norma_{rc}")
    with s2_l5_c2:
        desc_central_norma = st.text_input("Motivo da Central fora de norma", key=f"desc_central_norma_{rc}") if central_norma == "Não" else ""

    s2_l6_c1, s2_l6_c2 = st.columns(2)
    with s2_l6_c1:
        rep2_correto = st.radio("Representante 2 está correto? *", ["Sim", "Não"], horizontal=True, index=None, key=f"rep2_correto_{rc}")
    with s2_l6_c2:
        desc_rep2 = st.text_input("Nº OC de Regularização", key=f"desc_rep2_{rc}") if rep2_correto == "Não" else ""

    st.divider()

    st.subheader("3. Cadastro de Instalação e Equipamentos")
    col_cent1, col_cent2 = st.columns(2)
    with col_cent1:
        qtd_centrais = st.number_input("Quantidade de Centrais no Cliente", min_value=1, value=1, step=1, key=f"qtd_centrais_{rc}")
    with col_cent2:
        if qtd_centrais > 1:
            opcoes_centrais = [f"Central {i:02d}" for i in range(1, int(qtd_centrais) + 1)]
            idx_central = 0
            if st.session_state.last_central in opcoes_centrais:
                idx_central = opcoes_centrais.index(st.session_state.last_central)
            central_selecionada = st.selectbox("Vincular item à qual Central?", opcoes_centrais, index=idx_central, key=f"sel_central_{rc}_{ekc}")
            st.session_state.last_central = central_selecionada
        else:
            central_selecionada = "Central"
            st.session_state.last_central = "Central"
            st.write("")

    opcoes_tipo = ["Equipamentos", "Cilindros", "Condomínio"]
    idx_tipo = 0
    if st.session_state.last_tipo_cad in opcoes_tipo:
        idx_tipo = opcoes_tipo.index(st.session_state.last_tipo_cad)
    tipo_cadastro = st.radio("Selecione o tipo que deseja adicionar:", opcoes_tipo, index=idx_tipo, horizontal=True, key=f"tipo_cad_{rc}_{ekc}")
    st.session_state.last_tipo_cad = tipo_cadastro

    if tipo_cadastro == "Equipamentos":
        col_qtd, col_eq, col_vaz, col_btn = st.columns([1, 2, 2, 1])
        with col_qtd:
            qtd_input = st.number_input("Quantidade", min_value=1, value=1, step=1, key=f"eq_qtd_{rc}_{ekc}")
        with col_eq:
            nome_eq_input = st.text_input("Equipamento", key=f"eq_nome_{rc}_{ekc}")
        with col_vaz:
            vazao_input = st.text_input("Vazão (kg/h)", key=f"eq_vazao_{rc}_{ekc}")
        with col_btn:
            st.write(" "); st.write(" ")
            if st.button("➕ Adicionar", key=f"btn_add_eq_{rc}_{ekc}"):
                if nome_eq_input.strip() and vazao_input.strip():
                    try:
                        vazao_unit = float(vazao_input.replace(",", ".").lower().replace("kg/h", "").strip())
                        qtd = int(qtd_input)
                        vazao_total_item = vazao_unit * qtd
                        vazao_formatada = f"{vazao_total_item:.2f}".replace(".", ",").rstrip("0").rstrip(",")

                        item_dict = {
                            "central": central_selecionada,
                            "tipo": "equipamento",
                            "qtd": qtd,
                            "nome": nome_eq_input.strip().title(),
                            "vazao_total_item": vazao_total_item,
                            "texto": f"{qtd:02d} - {nome_eq_input.strip().title()} - {vazao_formatada} kg/h"
                        }
                        st.session_state.equipamentos.append(item_dict)
                        st.session_state.eq_key_counter += 1
                        st.success("Item adicionado!")
                        st.rerun()
                    except ValueError:
                        st.error("Informe um número válido para a vazão.")
                else:
                    st.warning("Preencha o nome e a vazão.")

    elif tipo_cadastro == "Cilindros":
        col_qtd, col_mod, col_btn = st.columns([1, 4, 1])
        with col_qtd:
            qtd_input = st.number_input("Qtd", min_value=1, value=1, step=1, key=f"cil_qtd_{rc}_{ekc}")
        with col_mod:
            modelo_input = st.text_input("Modelo", key=f"cil_mod_{rc}_{ekc}")
        with col_btn:
            st.write(" "); st.write(" ")
            if st.button("➕ Adicionar", key=f"btn_add_cil_{rc}_{ekc}"):
                if modelo_input.strip():
                    qtd = int(qtd_input)
                    item_dict = {
                        "central": central_selecionada,
                        "tipo": "cilindro",
                        "qtd": qtd,
                        "nome": f"Cilindro {modelo_input.strip().upper()}",
                        "vazao_total_item": 0.0,
                        "texto": f"{qtd:02d} und {modelo_input.strip().upper()}"
                    }
                    st.session_state.equipamentos.append(item_dict)
                    st.session_state.eq_key_counter += 1
                    st.success("Cilindro adicionado!")
                    st.rerun()

    elif tipo_cadastro == "Condomínio":
        col_local, col_qtd, col_tipo, col_btn = st.columns([2, 1, 3, 1])
        with col_local:
            local_input = st.selectbox("Local", ["Apartamentos", "Área Comum"], key=f"cond_local_{rc}_{ekc}")
        with col_qtd:
            qtd_input = st.number_input("Qtd", min_value=1, value=1, step=1, key=f"cond_qtd_{rc}_{ekc}")
        with col_tipo:
            tipo_apt_input = st.selectbox("Instalação", ["Só Fogão", "Fogão + Aquecedor"], key=f"cond_tipo_{rc}_{ekc}")
        with col_btn:
            st.write(" "); st.write(" ")
            if st.button("➕ Adicionar", key=f"btn_add_cond_{rc}_{ekc}"):
                qtd = int(qtd_input)
                vazao_unit = 0.1 if tipo_apt_input == "Só Fogão" else 0.4
                vazao_total = vazao_unit * qtd
                texto = f"{qtd:02d} aps - {tipo_apt_input}" if local_input == "Apartamentos" else f"{qtd:02d} - Área Comum ({tipo_apt_input})"
                
                item_dict = {
                    "central": central_selecionada,
                    "tipo": "condominio",
                    "qtd": qtd,
                    "nome": f"Condomínio ({tipo_apt_input})",
                    "vazao_total_item": vazao_total,
                    "texto": texto
                }
                st.session_state.equipamentos.append(item_dict)
                st.session_state.eq_key_counter += 1
                st.success("Condomínio adicionado!")
                st.rerun()

    if st.session_state.equipamentos:
        st.write("**Itens Cadastrados:**")
        def get_c_name(item, q):
            return "Central" if q == 1 else item.get("central", "Central")
        
        centrais_presentes = sorted(list(set([get_c_name(item, qtd_centrais) for item in st.session_state.equipamentos])))
        for c_nome in centrais_presentes:
            st.markdown(f"**{c_nome.upper()}**")
            vazao_c = 0.0
            for idx, item in enumerate(st.session_state.equipamentos):
                if get_c_name(item, qtd_centrais) == c_nome:
                    vazao_c += item["vazao_total_item"]
                    c_txt, c_del = st.columns([5, 1])
                    c_txt.text(item["texto"])
                    if c_del.button("❌", key=f"del_{idx}_{rc}"):
                        st.session_state.equipamentos.pop(idx)
                        st.rerun()
            v_str = f"{vazao_c:.2f}".replace(".", ",").rstrip("0").rstrip(",") if vazao_c > 0 else "0"
            st.markdown(f"*Vazão Total {c_nome}: {v_str} kg/h*")

    st.divider()

    st.subheader("4. Satisfação & Observações")
    s4_l1_c1, s4_l1_c2 = st.columns(2)
    with s4_l1_c1:
        indica_negocios = st.radio("Indicou novos negócios? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ind_neg_{rc}")
    with s4_l1_c2:
        cliente_satisfeito = st.radio("Cliente satisfeito com a Consigaz? *", ["Sim", "Não"], horizontal=True, index=None, key=f"cli_sat_{rc}")

    observacoes = st.text_area("Observações Gerais", key=f"obs_{rc}")

    st.divider()

    st.subheader("5. Relatório Fotográfico")
    def carregar_fotos(label, max_arq=None):
        fotos = st.file_uploader(label, type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_{label}_{rc}")
        if max_arq and fotos and len(fotos) > max_arq:
            return fotos[:max_arq]
        return fotos

    dic_fotos_final = {}
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        dic_fotos_final["FACHADA"] = carregar_fotos("FACHADA", 2)
    with col_f2:
        dic_fotos_final["CILINDROS"] = carregar_fotos("CILINDROS", 5)

    if qtd_centrais == 1:
        c1, c2, c3 = st.columns(3)
        with c1: dic_fotos_final["ABRIGO"] = carregar_fotos("ABRIGO", 10)
        with c2: dic_fotos_final["CENTRAL"] = carregar_fotos("CENTRAL", 5)
        with c3: dic_fotos_final["EQUIPAMENTOS"] = carregar_fotos("EQUIPAMENTOS")
    else:
        for i in range(1, int(qtd_centrais) + 1):
            st.markdown(f"**📸 CENTRAL {i:02d}**")
            c1, c2, c3 = st.columns(3)
            with c1: dic_fotos_final[f"ABRIGO CENTRAL {i:02d}"] = carregar_fotos(f"ABRIGO CENTRAL {i:02d}", 10)
            with c2: dic_fotos_final[f"CENTRAL {i:02d}"] = carregar_fotos(f"CENTRAL {i:02d}", 5)
            with c3: dic_fotos_final[f"EQUIPAMENTOS CENTRAL {i:02d}"] = carregar_fotos(f"EQUIPAMENTOS CENTRAL {i:02d}")

    st.divider()

    class RelatorioPDF(FPDF):
        def __init__(self, cod="", nome=""):
            super().__init__()
            self.cod = cod.replace(".", "").strip().upper()
            self.nome = nome.strip().upper()

        def header(self):
            if os.path.exists(LOGO2_PATH):
                self.image(LOGO2_PATH, x=10, y=8, w=45)
            if self.page_no() == 1:
                self.set_y(10)
                self.set_font("Arial", "B", 15)
                self.cell(0, 8, "RELATÓRIO FOTOGRÁFICO", align="C", ln=1)
                if self.cod or self.nome:
                    self.set_font("Arial", "B", 11)
                    self.cell(0, 6, f"{self.cod} | {self.nome}", align="C", ln=1)
                self.set_y(35)
            else:
                self.set_y(35)

        def footer(self):
            self.set_y(-15)
            self.set_font("Arial", "I", 8)
            self.cell(0, 10, f"Página {self.page_no()}", align="C")

    def gerar_pdf(equipamentos, dic_fotos, cod, nome, qty_c):
        pdf = RelatorioPDF(cod, nome)
        pdf.set_margins(10, 35, 10)
        pdf.set_auto_page_break(auto=True, margin=20)

        for cat, arquivos in dic_fotos.items():
            if arquivos:
                pdf.add_page()
                pdf.set_font("Arial", "B", 11)
                pdf.cell(0, 6, cat.upper(), ln=1, align="L")
                pdf.ln(2)
                for arq in arquivos:
                    t_path = None
                    try:
                        img = Image.open(arq)
                        if img.mode != "RGB": img = img.convert("RGB")

                        fd, t_path = tempfile.mkstemp(suffix=f"_{uuid.uuid4().hex}.jpg")
                        os.close(fd)
                        img.save(t_path, format="JPEG")

                        w_p, h_p = img.size
                        prop = h_p / w_p
                        w_alv = 130
                        h_alv = w_alv * prop
                        if h_alv > 110:
                            h_alv = 110
                            w_alv = h_alv / prop
                        pos_x = (210 - w_alv) / 2
                        if pdf.get_y() + h_alv > 270: pdf.add_page()
                        pdf.image(t_path, x=pos_x, y=pdf.get_y(), w=w_alv, h=h_alv)
                        pdf.set_y(pdf.get_y() + h_alv + 5)
                    except Exception:
                        pass
                    finally:
                        if t_path and os.path.exists(t_path):
                            try:
                                os.remove(t_path)
                            except OSError:
                                pass

        if equipamentos:
            pdf.add_page()
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 6, "LISTA DE ITENS E VAZÕES", ln=1, align="L")
            pdf.ln(2)
            
            def get_c_pdf(it): return "Central" if qty_c == 1 else it.get("central", "Central")
            centrais_p = sorted(list(set([get_c_pdf(it) for it in equipamentos])))
            
            for c_nome in centrais_p:
                pdf.set_font("Arial", "B", 10)
                pdf.cell(0, 6, c_nome.upper(), ln=1, align="L")
                pdf.set_fill_color(230, 230, 230)
                pdf.cell(20, 7, "QTD", border=1, align="C", fill=True)
                pdf.cell(120, 7, "ITEM / EQUIPAMENTO", border=1, align="C", fill=True)
                pdf.cell(50, 7, "VAZÃO TOTAL", border=1, align="C", fill=True, ln=1)
                
                pdf.set_font("Arial", "", 10)
                tot_v = 0.0
                for it in equipamentos:
                    if get_c_pdf(it) == c_nome:
                        tot_v += it["vazao_total_item"]
                        v_disp = "-" if it.get("tipo") == "cilindro" else f"{it['vazao_total_item']:.2f}".replace(".", ",").rstrip("0").rstrip(",") + " kg/h"
                        pdf.cell(20, 6, f"{it['qtd']:02d}", border=1, align="C")
                        pdf.cell(120, 6, f"{it['nome']}", border=1, align="L")
                        pdf.cell(50, 6, v_disp, border=1, align="C", ln=1)
                
                v_tot_str = f"{tot_v:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                pdf.set_font("Arial", "B", 10)
                pdf.cell(140, 7, f"VAZÃO TOTAL {c_nome.upper()}:", border=1, align="R", fill=True)
                pdf.cell(50, 7, f"{v_tot_str} kg/h", border=1, align="C", fill=True, ln=1)
                pdf.ln(4)

        pdf_output = pdf.output(dest="S")
        if isinstance(pdf_output, str):
            return pdf_output.encode("latin-1")
        return bytes(pdf_output)

    st.subheader("6. Ações Finais")
    col_a1, col_a2 = st.columns(2)

    with col_a1:
        if not cod_cliente.strip() or not nome_cliente.strip():
            st.warning("⚠️ Preencha pelo menos o Código e o Nome do Cliente para habilitar o PDF.")
        else:
            pdf_bytes = gerar_pdf(st.session_state.equipamentos, dic_fotos_final, cod_cliente, nome_cliente, qtd_centrais)
            cod_limpo = "".join(filter(str.isalnum, cod_cliente))
            data_atual_str = datetime.now().strftime("%d-%m-%y")
            nome_arquivo_pdf = f"relatorio_{cod_limpo}_{data_atual_str}.pdf"

            st.download_button(
                label="📥 Baixar Relatório (PDF)",
                data=pdf_bytes,
                file_name=nome_arquivo_pdf,
                mime="application/pdf"
            )

    with col_a2:
        if st.button("📝 Gerar Texto para Sistema"):
            lista_eq_txt = ""
            if st.session_state.equipamentos:
                def get_c_txt(eq): return "Central" if qtd_centrais == 1 else eq.get("central", "Central")
                cps = sorted(list(set([get_c_txt(eq) for eq in st.session_state.equipamentos])))
                for c_n in cps:
                    lista_eq_txt += f"Equipamentos {c_n}\n"
                    v_c = 0.0
                    for eq in st.session_state.equipamentos:
                        if get_c_txt(eq) == c_n:
                            lista_eq_txt += f"{eq['texto']}\n"
                            v_c += eq["vazao_total_item"]
                    lista_eq_txt += f"\nTotal Vazão {c_n}: {f'{v_c:.2f}'.replace('.', ',')} kg/h\n\n"
            else:
                lista_eq_txt = "Nenhum item cadastrado.\n\n"

            texto_final = f"""Contato: {contato}
Sobrenome ou departamento: {departamento}
Telefone: {telefone}

Equipamentos de acordo com o contrato vigente? {eq_contrato} - {desc_eq_contrato}
Representante 2 está correto? {rep2_correto}
Possui programação cadastrada? {tem_freq} - {desc_freq}
Consumo mensal atual de acordo com o contrato vigente? Consumo previsto: {consumo_previsto} kg | Consumo médio: {consumo_real} kg
Laudo ART emitido? {possui_art} - {desc_art}
Central atende as normas? {central_norma} - {desc_central_norma}

Quais equipamentos disponíveis no cliente?

{lista_eq_txt}Indicação de novos negócios do cliente: {indica_negocios}
Cliente possui débitos? {possui_debitos} - {desc_debitos}
Cliente está satisfeito com o atendimento da Consigaz? {cliente_satisfeito}

Obs.: {observacoes}
"""
            st.success("✅ Texto gerado com sucesso! Copie abaixo:")
            st.text_area("Texto Gerado:", value=texto_final, height=250, key=f"txt_area_transf_{rc}")
            
            def botao_copiar_customizado(texto_para_copiar, chave_unica):
                texto_norm = str(texto_para_copiar).replace("\r\n", "\n").replace("\r", "\n")
                texto_js = json.dumps(texto_norm).replace("</", "<\\/")
                comp_html = f"""
                <div style="margin-top: 10px; margin-bottom: 15px;">
                    <button onclick="navigator.clipboard.writeText({texto_js}); alert('Copiado com sucesso!');" style="
                        background: linear-gradient(135deg, #0055A5 0%, #003366 100%);
                        color: white; padding: 10px 20px; border: none; border-radius: 12px;
                        font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 14px; cursor: pointer;
                    ">📋 Copiar Texto Completo</button>
                </div>
                """
                components.html(comp_html, height=60)
            botao_copiar_customizado(texto_final, "transferencia_txt")
