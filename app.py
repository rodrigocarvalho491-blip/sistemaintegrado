import os
import json
import pandas as pd
import numpy as np
import streamlit as st
import html as html_lib
import base64
import requests
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from fpdf import FPDF
import streamlit.components.v1 as components

# --- FORÇAR TEMA CLARO GLOBALMENTE NO STREAMLIT ---
os.makedirs(".streamlit", exist_ok=True)
with open(".streamlit/config.toml", "w", encoding="utf-8") as f:
    f.write(
        '[theme]\n'
        'base="light"\n'
        'primaryColor="#0055A5"\n'
        'backgroundColor="#FFFFFF"\n'
        'secondaryBackgroundColor="#F1F5FA"\n'
        'textColor="#1B2A3A"\n'
    )

# --- CONFIGURAÇÃO GLOBAL DA PÁGINA ---
st.set_page_config(
    page_title="Sistema Integrado de Ocorrências | Consigaz", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")
DB_NOTAS_PATH = "banco_notas_usuarios.json"

# =====================================================================
# IDENTIDADE VISUAL CONSIGAZ - TEMA CLARO UNIFICADO
# =====================================================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
  font-family: 'Plus Jakarta Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
  background-color: #F1F5FA !important;
  color: #1B2A3A !important;
}

[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

/* Container Principal */
.block-container, [data-testid="stMainBlockContainer"] {
  max-width: 1180px !important;
  margin: 1.2rem auto 2rem auto !important;
  padding: 1.8rem 2.4rem 2.4rem 2.4rem !important;
  background: #FFFFFF !important;
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(10,37,64,.06), 0 8px 28px rgba(10,37,64,.07);
}

/* Cabeçalho Consigaz */
.cg-header { 
  display: flex; 
  align-items: center; 
  gap: 1.5rem; 
  position: relative;
  padding-bottom: 1.2rem; 
  margin-bottom: 2rem; 
  border-bottom: 2px solid #E2E8F0; 
}
.cg-header::after { 
  content: ""; 
  position: absolute; 
  left: 0; 
  bottom: -2px; 
  width: 140px; 
  height: 4px; 
  border-radius: 4px; 
  background: linear-gradient(90deg, #0055A5 0%, #F28C28 100%); 
}

.cg-logo-wrapper {
  background: #FFFFFF;
  padding: 6px 12px;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #E2E8F0;
}
.cg-logo { height: 55px; width: auto; display: block; }

.cg-header-sep { width: 2px; align-self: stretch; background: #E2E8F0; }
.cg-title { font-size: 1.65rem; font-weight: 800; line-height: 1.2; color: #003366 !important; }
.cg-subtitle { font-size: 0.95rem; margin-top: 0.2rem; color: #64748B !important; font-weight: 500; }

/* Títulos de Seção */
.stApp h3 {
  font-size: 1.1rem !important;
  font-weight: 700 !important;
  color: #003366 !important;
  padding: 0.2rem 0 0.2rem 0.6rem !important;
  border-left: 4px solid #F28C28 !important;
  margin-top: 1.5rem !important;
  margin-bottom: 1rem !important;
}

/* Ajuste de Métricas para contraste perfeito em tema claro */
[data-testid="stMetric"] {
  background-color: #F8FAFC !important;
  border: 1px solid #E2E8F0 !important;
  padding: 14px 18px !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
[data-testid="stMetricValue"] {
  color: #003366 !important;
  font-weight: 800 !important;
}
[data-testid="stMetricLabel"] {
  color: #5B6B7C !important;
  font-weight: 600 !important;
}

/* Sidebar Estilizada */
[data-testid="stSidebar"] {
  background-color: #FFFFFF !important;
  border-right: 1px solid #E2E8F0;
}
.cg-side-brand { 
  padding: 0.8rem 0.5rem 1.2rem 0.5rem; 
  margin-bottom: 1rem; 
  border-bottom: 1px solid #E2E8F0; 
  text-align: center;
}
.cg-side-logo-wrapper {
  background: #FFFFFF;
  padding: 6px 10px;
  border-radius: 8px;
  display: inline-block;
  box-shadow: 0 2px 6px rgba(0,0,0,0.05);
}
.cg-side-logo { height: 38px; width: auto; display: inline-block; }
.cg-side-name { margin-top: 0.6rem; font-size: 0.7rem; font-weight: 700; color: #64748B !important; letter-spacing: 0.08em; text-transform: uppercase; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES DE LOGO E PERSISTÊNCIA ---
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

def carregar_banco_notas():
    if os.path.exists(DB_NOTAS_PATH):
        try:
            with open(DB_NOTAS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_banco_notas(dados):
    with open(DB_NOTAS_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

# --- GERENCIAMENTO DE ESTADO DE AUTENTICAÇÃO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_atual" not in st.session_state:
    st.session_state.usuario_atual = ""

# =====================================================================
# TELA DE AUTENTICAÇÃO (LOGIN INDEPENDENTE)
# =====================================================================
if not st.session_state.autenticado:
    side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
    st.sidebar.markdown(
        f'<div class="cg-side-brand">{side_logo_html}'
        f'<div class="cg-side-name">Sistema Integrado</div></div>',
        unsafe_allow_html=True,
    )
    
    st.title("🔐 Acesso ao Sistema Integrado | Consigaz")
    st.markdown("Insira suas credenciais corporativas para acessar o painel de atendimento e o seu bloco de notas pessoal.")
    
    with st.form("form_login_sistema"):
        email_input = st.text_input("E-mail corporativo", placeholder="seu.nome@consigaz.com.br")
        senha_input = st.text_input("Senha", type="password", placeholder="••••••••")
        btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary")
        
        if btn_entrar:
            if email_input.strip() and len(senha_input) >= 4:
                st.session_state.autenticado = True
                st.session_state.usuario_atual = email_input.strip().lower()
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("⚠️ Por favor, informe um e-mail válido e uma senha com pelo menos 4 caracteres.")
                
    st.stop()

# =====================================================================
# SISTEMA AUTENTICADO & ABAS SUPERIORES
# =====================================================================
side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
st.sidebar.markdown(
    f'<div class="cg-side-brand">{side_logo_html}'
    f'<div class="cg-side-name">Central de Atendimentos</div></div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown(f"👤 **Usuário:** `{st.session_state.usuario_atual}`")

# --- ABAS SUPERIORES DO SISTEMA ---
aba_notas, aba_dashboard, aba_tratativa = st.tabs([
    "📓 Bloco de Notas Pessoal", 
    "📊 Dashboard de Ocorrências", 
    "🛠️ Tratativa de Ocorrências"
])

st.sidebar.divider()
if st.sidebar.button("🔄 Limpar Sessão"):
    for k in list(st.session_state.keys()):
        if k not in ["autenticado", "usuario_atual"]:
            del st.session_state[k]
    st.rerun()

if st.sidebar.button("🚪 Sair (Logout)"):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.rerun()

# Inicializações globais de estado
if "tratadas_manualmente" not in st.session_state: st.session_state.tratadas_manualmente = set()
if "filtro_card_dashboard" not in st.session_state: st.session_state.filtro_card_dashboard = "Todos"

COL_OCORRENCIA = "Número da ocorrência"
COL_CLIENTE = "Nome do cliente"
COL_ENDERECO = "Endereço de Entrega"
COL_ABERTURA = "Data/Hora de abertura"
COL_PRAZO = "Prazo de Atendimento"
COL_FECHAMENTO = "Data/Hora de fechamento"
COL_SUB_CLASSIF = "Subclassificação Ocorrência"

def extrair_cidade(endereco):
    if pd.isna(endereco): return "-"
    s = str(endereco).strip().replace(';', ',').replace('|', ',')
    partes = [p.strip() for p in s.split(',')]
    if len(partes) >= 2:
        cidade = partes[-2].strip()
        if cidade.isdigit() and len(partes) >= 3: cidade = partes[-3].strip()
        return cidade.title()
    return s.title()

def limpar_subclassificacao(sub):
    if pd.isna(sub): return "-"
    s = str(sub).strip()
    if "]" in s: s = s.split("]")[-1].strip()
    return s

def calcular_dias_uteis(data_inicio, data_fim):
    h = pd.Timestamp(data_inicio).normalize().date()
    p = pd.Timestamp(data_fim).normalize().date()
    if p > h: return int(np.busday_count(h, p))
    elif p < h: return -int(np.busday_count(p, h))
    return 0

def classificar_status_geral(dias_uteis):
    if dias_uteis < 0: return "🔴 Vencido"
    elif dias_uteis == 0: return "🔵 Vence Hoje"
    elif dias_uteis == 1: return "🟠 Vence Amanhã"
    elif 2 <= dias_uteis <= 5: return "🟡 Vence na Semana"
    return "🟢 No Prazo"


# =====================================================================
# ABA 1: BLOCO DE NOTAS PESSOAL
# =====================================================================
with aba_notas:
    cabecalho_pagina("Bloco de Notas & Base de Conhecimento", "Suas anotações salvas de forma persistente e isolada para o seu usuário.")
    
    banco_notas = carregar_banco_notas()
    usuario_atual = st.session_state.usuario_atual

    if usuario_atual not in banco_notas:
        banco_notas[usuario_atual] = ""

    st.markdown(f"✍️ Editando anotações para a conta: **{usuario_atual}**")
    
    texto_usuario = st.text_area(
        "Escreva suas anotações, lembretes ou rascunhos de atendimento:",
        value=banco_notas[usuario_atual],
        height=350,
        key="txt_bloco_notas_usuario"
    )

    if st.button("💾 Salvar Anotações no Banco de Dados", type="primary"):
        banco_notas[usuario_atual] = texto_usuario
        salvar_banco_notas(banco_notas)
        st.success("✅ Suas anotações foram salvas com segurança no banco de dados do sistema!")


# =====================================================================
# ABA 2: DASHBOARD DE OCORRÊNCIAS
# =====================================================================
with aba_dashboard:
    cabecalho_pagina("Dashboard de Ocorrências & Visitas", "Painel de organização de agenda ordenado por prazo de atendimento (Dias Úteis).")

    st.subheader("1. Atualização de Dados")
    arquivo_excel = st.file_uploader("Faça o upload do relatório Excel (Pós-Vendas) 📂", type=["xlsx", "xls"], key="upload_dash")
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
            df_pendentes['Sub_Simplificada'] = df_pendentes[COL_SUB_CLASSIF].apply(limpar_subclassificacao)
            
            hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            df_pendentes['Dias Úteis Restantes'] = df_pendentes['Prazo_DT'].apply(lambda x: calcular_dias_uteis(hoje, x))
            df_pendentes['Status Geral'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_geral)
            df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
            
            st.subheader("2. Agenda Geral de Visitas Pendentes")
            cidades_unicas = sorted(list(df_pendentes['Cidade'].unique()))
            sub_class_unicas = sorted(list(df_pendentes['Sub_Simplificada'].unique()))
            
            col_f1, col_f2 = st.columns(2)
            with col_f1: cidades_selecionadas = st.multiselect("Filtrar por Cidade(s):", cidades_unicas, default=[], key="f_cid")
            with col_f2: sub_class_selecionadas = st.multiselect("Filtrar por Sub-Classificação:", sub_class_unicas, default=[], key="f_sub")
            
            df_filtrado = df_pendentes.copy()
            if cidades_selecionadas: df_filtrado = df_filtrado[df_filtrado['Cidade'].isin(cidades_selecionadas)]
            if sub_class_selecionadas: df_filtrado = df_filtrado[df_filtrado['Sub_Simplificada'].isin(sub_class_selecionadas)]
            
            df_filtrado['Data Atendimento'] = df_filtrado['Prazo_DT'].dt.strftime('%d/%m/%Y')
            
            total_qt = len(df_filtrado)
            hoje_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🔵 Vence Hoje"])
            amanha_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🟠 Vence Amanhã"])
            vencidas_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🔴 Vencido"])
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Total", total_qt)
                if st.button("🔍 Filtrar Total", key="btn_f_tot", use_container_width=True): st.session_state.filtro_card_dashboard = "Todos"
            with col_m2:
                st.metric("Vence Hoje", hoje_qt)
                if st.button("🔍 Filtrar Hoje", key="btn_f_hoj", use_container_width=True): st.session_state.filtro_card_dashboard = "Hoje"
            with col_m3:
                st.metric("Vence Amanhã", amanha_qt)
                if st.button("🔍 Filtrar Amanhã", key="btn_f_ama", use_container_width=True): st.session_state.filtro_card_dashboard = "Amanhã"
            with col_m4:
                st.metric("Ocorrências Vencidas", vencidas_qt)
                if st.button("🔍 Filtrar Vencidas", key="btn_f_ven", use_container_width=True): st.session_state.filtro_card_dashboard = "Vencido"

            if st.session_state.filtro_card_dashboard == "Hoje":
                df_filtrado = df_filtrado[df_filtrado['Status Geral'] == "🔵 Vence Hoje"]
            elif st.session_state.filtro_card_dashboard == "Amanhã":
                df_filtrado = df_filtrado[df_filtrado['Status Geral'] == "🟠 Vence Amanhã"]
            elif st.session_state.filtro_card_dashboard == "Vencido":
                df_filtrado = df_filtrado[df_filtrado['Status Geral'] == "🔴 Vencido"]

            st.write("---")
            if df_filtrado.empty:
                st.success("✅ Nenhuma ocorrência para os filtros selecionados.")
            else:
                df_exibicao = df_filtrado[['Status Geral', 'Dias Úteis Restantes', COL_OCORRENCIA, COL_CLIENTE, 'Cidade', 'Sub_Simplificada', 'Data Atendimento']].copy()
                df_exibicao[COL_OCORRENCIA] = df_exibicao[COL_OCORRENCIA].astype(str)
                st.dataframe(df_exibicao, hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")
    else:
        st.info("👆 Faça o upload do arquivo Excel na aba para carregar o dashboard.")


# =====================================================================
# ABA 3: TRATATIVA DE OCORRÊNCIAS (COM MENU LATERAL DINÂMICO)
# =====================================================================
with aba_tratativa:
    cabecalho_pagina("Tratativa de Ocorrências", "Gerenciamento individual e relatórios técnicos.")

    # Menu lateral exclusivo da aba de tratativa
    st.sidebar.divider()
    st.sidebar.markdown("### 🔍 Seleção de Ocorrência")
    
    # Armazena temporariamente dados carregados para tratativa
    if "oc_selecionada_detalhe" not in st.session_state:
        st.session_state.oc_selecionada_detalhe = None

    # Verifica se há dados carregados no Dashboard para listar no menu lateral
    if arquivo_excel is not None:
        try:
            # Lista os números das ocorrências pendentes no menu lateral
            lista_ocs_disponiveis = df_pendentes[COL_OCORRENCIA].tolist() if 'df_pendentes' in locals() else []
            if lista_ocs_disponiveis:
                oc_escolhida = st.sidebar.selectbox("Escolha o Nº da Ocorrência:", ["Selecione..."] + [str(x) for x in lista_ocs_disponiveis])
                if oc_escolhida != "Selecione...":
                    row_oc = df_pendentes[df_pendentes[COL_OCORRENCIA] == int(oc_escolhida)].iloc[0]
                    st.sidebar.success(f"Cliente: {row_oc[COL_CLIENTE]}")
                    if st.sidebar.button("Carregar para Tratativa"):
                        st.session_state.oc_selecionada_detalhe = row_oc.to_dict()
            else:
                st.sidebar.info("Nenhuma ocorrência disponível.")
        except Exception:
            st.sidebar.warning("Carregue o Excel na aba Dashboard primeiro.")
    else:
        st.sidebar.warning("⚠️ Faça o upload do Excel no Dashboard primeiro para habilitar a busca de ocorrências.")

    # Se uma ocorrência foi carregada, exibe o formulário de tratativa e relatório fotográfico
    if st.session_state.oc_selecionada_detalhe:
        oc_data = st.session_state.oc_selecionada_detalhe
        st.success(f"🔧 Gerenciando Ocorrência Nº **{oc_data[COL_OCORRENCIA]}** — Cliente: **{oc_data[COL_CLIENTE]}**")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.text(f"Cidade: {oc_data.get('Cidade', '-')}")
            st.text(f"Sub-Classificação: {oc_data.get('Sub_Simplificada', '-')}")
        with col_t2:
            st.text(f"Prazo de Atendimento: {oc_data.get(COL_PRAZO, '-')}")

        observacoes_tratativa = st.text_area("Notas e Ações Tomadas na Tratativa", key="txt_notas_tratativa")
        
        if st.button("🔒 Marcar Ocorrência como Tratada e Fechar", type="primary"):
            st.session_state.tratadas_manualmente.add(int(oc_data[COL_OCORRENCIA]))
            st.session_state.oc_selecionada_detalhe = None
            st.success("✅ Ocorrência tratada e removida com sucesso!")
            st.rerun()
    else:
        st.info("👈 Selecione uma ocorrência no menu lateral à esquerda e clique em 'Carregar para Tratativa'.")

st.divider()
