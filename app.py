import os
import json
import re
import pandas as pd
import numpy as np
import streamlit as st
import html as html_lib
import base64
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from fpdf import FPDF
import requests
import uuid
import tempfile
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
    page_title="Sistema Integrado Consigaz", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SISTEMA ANTI-SLEEP (HEARTBEAT) ---
# Mantém a aplicação ativa enviando um ping silencioso a cada 5 minutos
components.html(
    """
    <script>
    setInterval(function() {
        fetch('/healthz').catch(() => {});
    }, 300000);
    </script>
    """,
    height=0, width=0
)

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")
DB_NOTAS_PATH = "banco_notas_usuarios.json"
DB_USUARIOS_PATH = "banco_usuarios.json"

# =====================================================================
# IDENTIDADE VISUAL CONSIGAZ
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

/* Ajuste de Botões Padrão */
div.stButton > button:first-child {
  background-color: #0055A5 !important; 
  color: #ffffff !important;
  border-radius: 8px !important; 
  border: none !important; 
  font-weight: bold !important;
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

# --- GERENCIAMENTO DO BANCO DE DADOS DE USUÁRIOS ---
def carregar_banco_usuarios():
    if os.path.exists(DB_USUARIOS_PATH):
        try:
            with open(DB_USUARIOS_PATH, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if "admin" not in dados:
                    dados["admin"] = "admin"
                return dados
        except Exception:
            pass
    return {"admin": "admin"}

def salvar_banco_usuarios(dados):
    with open(DB_USUARIOS_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

# --- FUNÇÕES AUXILIARES DE LOGO E PERSISTÊNCIA DE NOTAS ---
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

@st.cache_data(ttl=3600)
def obter_ipca_ibge():
    try:
        url = "https://www.ibge.gov.br/explica/inflacao.php"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            match = re.search(r'acomet?ulado.*?(\d+[,]\d+)\s*%', response.text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "4,22"

# --- GERENCIAMENTO DE ESTADO DE AUTENTICAÇÃO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_atual" not in st.session_state:
    st.session_state.usuario_atual = ""
if "e_admin" not in st.session_state:
    st.session_state.e_admin = False

# =====================================================================
# TELA DE AUTENTICAÇÃO
# =====================================================================
if not st.session_state.autenticado:
    side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
    st.sidebar.markdown(
        f'<div class="cg-side-brand">{side_logo_html}'
        f'<div class="cg-side-name">Sistema Integrado</div></div>',
        unsafe_allow_html=True,
    )
    
    st.title("🔐 Acesso ao Sistema Integrado | Consigaz")
    st.markdown("Insira suas credenciais registradas pelo administrador para acessar a plataforma.")
    
    banco_usuarios = carregar_banco_usuarios()

    with st.form("form_login_sistema"):
        usuario_input = st.text_input("Usuário", placeholder="Digite seu usuário (Ex: admin)").strip().lower()
        senha_input = st.text_input("Senha", type="password", placeholder="••••••••").strip()
        btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary")
        
        if btn_entrar:
            if usuario_input in banco_usuarios and banco_usuarios[usuario_input] == senha_input:
                st.session_state.autenticado = True
                st.session_state.usuario_atual = usuario_input
                st.session_state.e_admin = (usuario_input == "admin")
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("❌ Usuário ou senha incorretos! Verifique suas credenciais ou solicite ao administrador.")
                
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

st.sidebar.markdown(f"👤 **Usuário Ativo:** `{st.session_state.usuario_atual}`")
if st.session_state.e_admin:
    st.sidebar.caption("⭐ Perfil: Administrador Master")

# --- DEFINIÇÃO DINÂMICA DAS ABAS ---
lista_abas = [
    "📓 Bloco de Notas Pessoal", 
    "📊 Dashboard de Ocorrências", 
    "🛠️ Tratativa de Ocorrências"
]

if st.session_state.e_admin:
    lista_abas.append("⚙️ Painel Admin")

abas_sistema = st.tabs(lista_abas)
aba_notas = abas_sistema[0]
aba_dashboard = abas_sistema[1]
aba_tratativa = abas_sistema[2]
aba_admin = abas_sistema[3] if st.session_state.e_admin else None

# Inicializações globais de estado
if "tratadas_manualmente" not in st.session_state: st.session_state.tratadas_manualmente = set()
if "filtro_card_dashboard" not in st.session_state: st.session_state.filtro_card_dashboard = "Todos"
if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0
if "eq_key_counter" not in st.session_state: st.session_state.eq_key_counter = 0
if "equipamentos" not in st.session_state: st.session_state.equipamentos = []
if "last_central" not in st.session_state: st.session_state.last_central = "Central"
if "last_tipo_cad" not in st.session_state: st.session_state.last_tipo_cad = "Equipamentos"

def resetar_dados_cliente():
    st.session_state.reset_counter += 1
    st.session_state.eq_key_counter = 0
    st.session_state.equipamentos = []
    st.session_state.last_central = "Central"
    st.session_state.last_tipo_cad = "Equipamentos"

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
            
            st.session_state.df_pendentes_global = df_pendentes

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
# ABA 3: TRATATIVA DE OCORRÊNCIAS
# =====================================================================
with aba_tratativa:
    st.sidebar.divider()
    st.sidebar.markdown("### 📌 Módulos de Tratativa")
    menu_tratativa = st.sidebar.radio(
        "Selecione a operação:", 
        [
            "📷 Visita de Transferência",
            "📝 Elaboração de Contrato",
            "📋 Aprovação de Contrato",
            "🎂 Aniversário de Contrato"
        ],
        label_visibility="collapsed"
    )

    st.sidebar.divider()
    if st.sidebar.button("🔄 Resetar Sessão"):
        resetar_dados_cliente()
        st.rerun()

    if menu_tratativa == "📷 Visita de Transferência":
        cabecalho_pagina("Visita de Transferência & Relatório Técnico", "Gerador automatizado de relatórios técnicos e inspeções.")
        
        rc = st.session_state.reset_counter
        ekc = st.session_state.eq_key_counter

        st.subheader("1. Identificação do Cliente")
        s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
        with s1_l1_c1: cod_cliente = st.text_input("Código do Cliente *", placeholder="Ex: 87.653", key=f"input_cod_{rc}")
        with s1_l1_c2: nome_cliente = st.text_input("Nome / Razão Social *", placeholder="Ex: SABOR DA TERRA", key=f"input_nome_{rc}")
        with s1_l1_c3: telefone = st.text_input("Telefone *", placeholder="Ex: 12-992586760", key=f"input_tel_{rc}")

        s1_l2_c1, s1_l2_c2, s1_l2_c3 = st.columns(3)
        with s1_l2_c1: contato = st.text_input("Contato *", placeholder="Ex: Nilton", key=f"input_contato_{rc}")
        with s1_l2_c2: departamento = st.text_input("Sobrenome ou Departamento *", placeholder="Ex: Gerente", key=f"input_depto_{rc}")
        with s1_l2_c3: st.write("")

        st.divider()

        st.subheader("2. Informações Contratuais")
        s2_l1_c1, s2_l1_c2, s2_l1_c3, s2_l1_c4 = st.columns(4)
        with s2_l1_c1: eq_contrato = st.selectbox("Equipamentos de acordo com contrato? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"eq_contrato_{rc}")
        with s2_l1_c2: desc_eq_contrato = st.text_input("Quais equipamentos disponíveis? *", placeholder="Ex: 01 B190...", key=f"desc_eq_contrato_{rc}")
        with s2_l1_c3: tem_freq = st.selectbox("Possui programação cadastrada? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"tem_freq_{rc}")
        with s2_l1_c4:
            desc_freq = ""
            if tem_freq == "Sim": desc_freq = st.text_input("Qual a programação? *", placeholder="Ex: QUINZENAL", key=f"freq_cad_sim_{rc}")
            elif tem_freq == "Não": desc_freq = st.text_input("Nº OC de Cadastramento *", placeholder="Ex: SOL PROGRAMAÇÃO", key=f"freq_cad_nao_{rc}")

        s2_l2_c1, s2_l2_c2 = st.columns(2)
        with s2_l2_c1: consumo_previsto = st.text_input("Consumo Previsto (kg) *", placeholder="Ex: 250", key=f"cons_prev_{rc}")
        with s2_l2_c2: consumo_real = st.text_input("Consumo Real/Médio (kg) *", placeholder="Ex: 137", key=f"cons_real_{rc}")

        s2_l3_c1, s2_l3_c2 = st.columns(2)
        with s2_l3_c1: possui_art = st.selectbox("Possui ART? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"possui_art_{rc}")
        with s2_l3_c2:
            desc_art = ""
            if possui_art == "Sim": desc_art = st.text_input("Número da ART *", placeholder="Ex: 262026126...", key=f"art_sim_{rc}")
            elif possui_art == "Não": desc_art = st.text_input("Nº OC de Solicitação de Laudo *", placeholder="Ex: INF LAUDO", key=f"art_nao_{rc}")

        s2_l4_c1, s2_l4_c2 = st.columns(2)
        with s2_l4_c1: possui_debitos = st.selectbox("Cliente possui débitos? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"possui_debitos_{rc}")
        with s2_l4_c2: desc_debitos = st.text_input("Detalhes dos Débitos (se houver)", placeholder="Ex: Fatura vencida", key=f"desc_debitos_{rc}") if possui_debitos == "Sim" else ""

        s2_l5_c1, s2_l5_c2 = st.columns(2)
        with s2_l5_c1: central_norma = st.selectbox("Central dentro de norma? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"central_norma_{rc}")
        with s2_l5_c2: desc_central_norma = st.text_input("Motivo da Central fora de norma", placeholder="Ex: Falta extintor", key=f"desc_central_norma_{rc}") if central_norma == "Não" else ""

        s2_l6_c1, s2_l6_c2 = st.columns(2)
        with s2_l6_c1: rep2_correto = st.selectbox("Representante 2 está correto? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"rep2_correto_{rc}")
        with s2_l6_c2: desc_rep2 = st.text_input("Nº OC de Regularização", placeholder="Ex: ALT DIVERSAS", key=f"desc_rep2_{rc}") if rep2_correto == "Não" else ""

        st.divider()

        st.subheader("3. Cadastro de Instalação e Equipamentos")
        col_cent1, col_cent2 = st.columns(2)
        with col_cent1: qtd_centrais = st.number_input("Quantidade de Centrais no Cliente", min_value=1, value=1, step=1, key=f"qtd_centrais_{rc}")
        with col_cent2:
            if qtd_centrais > 1:
                opcoes_centrais = [f"Central {i:02d}" for i in range(1, int(qtd_centrais) + 1)]
                idx_central = 0
                if st.session_state.last_central in opcoes_centrais: idx_central = opcoes_centrais.index(st.session_state.last_central)
                central_selecionada = st.selectbox("Vincular item à qual Central?", opcoes_centrais, index=idx_central, key=f"sel_central_{rc}_{ekc}")
                st.session_state.last_central = central_selecionada
            else: central_selecionada = "Central"

        opcoes_tipo = ["Equipamentos", "Cilindros", "Condomínio"]
        idx_tipo = 0
        if st.session_state.last_tipo_cad in opcoes_tipo: idx_tipo = opcoes_tipo.index(st.session_state.last_tipo_cad)
        tipo_cadastro = st.radio("Selecione o tipo que deseja adicionar:", opcoes_tipo, index=idx_tipo, horizontal=True, key=f"tipo_cad_{rc}_{ekc}")
        st.session_state.last_tipo_cad = tipo_cadastro

        if tipo_cadastro == "Equipamentos":
            col_qtd, col_eq, col_vaz, col_btn = st.columns([1, 2, 2, 1])
            with col_qtd: qtd_input = st.number_input("Quantidade", min_value=1, value=1, step=1, key=f"eq_qtd_{rc}_{ekc}")
            with col_eq: nome_eq_input = st.text_input("Equipamento", placeholder="Ex: Forno", key=f"eq_nome_{rc}_{ekc}")
            with col_vaz: vazao_input = st.text_input("Vazão (kg/h)", placeholder="Ex: 1 ou 1,6", key=f"eq_vazao_{rc}_{ekc}")
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
                                "central": central_selecionada, "tipo": "equipamento", "qtd": qtd,
                                "nome": nome_eq_input.strip().title(), "vazao_total_item": vazao_total_item,
                                "texto": f"{qtd:02d} - {nome_eq_input.strip().title()} - {vazao_formatada} kg/h"
                            }
                            st.session_state.equipamentos.append(item_dict)
                            st.session_state.eq_key_counter += 1
                            st.success("Item adicionado!")
                            st.rerun()
                        except ValueError: st.error("Informe um número válido para a vazão.")

        if st.session_state.equipamentos:
            st.write("**Itens Cadastrados:**")
            def get_c_name(item, q): return "Central" if q == 1 else item.get("central", "Central")
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
        with s4_l1_c1: indica_negocios = st.selectbox("Indicou novos negócios? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"ind_neg_{rc}")
        with s4_l1_c2: cliente_satisfeito = st.selectbox("Cliente satisfeito com a Consigaz? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"cli_sat_{rc}")

        observacoes = st.text_area("Observações Gerais", placeholder="Detalhes da visita...", key=f"obs_{rc}")

        st.divider()
        if st.button("📝 Gerar Texto para Sistema", type="primary"):
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
            else: lista_eq_txt = "Nenhum item cadastrado.\n\n"

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
            st.code(texto_final, language="text")

    elif menu_tratativa == "📝 Elaboração de Contrato":
        cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento e geração do padrão de solicitação.")
        motivo_solicitacao = st.text_input("Motivo da solicitação", placeholder="Ex: Alteração de CNPJ")
        st.info("Preencha os campos para gerar o relatório de elaboração de contrato.")

    elif menu_tratativa == "📋 Aprovação de Contrato":
        cabecalho_pagina("Aprovação de Contrato", "Formulário de aprovação de condições comerciais.")
        st.info("Módulo de Aprovação de Contrato ativo.")

    elif menu_tratativa == "🎂 Aniversário de Contrato":
        cabecalho_pagina("Aniversário de Contrato", "Reajuste por IPCA e geração de solicitação.")
        ipca_vigente = obter_ipca_ibge()
        st.markdown(f"📈 **IPCA Acumulado 12 meses (IBGE):** `{ipca_vigente}%`")


# =====================================================================
# ABA 4: PAINEL DE GERENCIAMENTO DE USUÁRIOS (EXCLUSIVO ADMIN)
# =====================================================================
if aba_admin is not None:
    with aba_admin:
        cabecalho_pagina("Painel de Administração de Usuários", "Gerencie o acesso dos colaboradores, cadastre novas contas ou altere senhas.")
        
        banco_usuarios = carregar_banco_usuarios()
        
        col_adm1, col_adm2 = st.columns([1, 1])
        
        with col_adm1:
            st.subheader("1. Cadastrar Novo Usuário")
            with st.form("form_novo_usuario"):
                novo_user = st.text_input("Usuário", placeholder="novo.usuario").strip().lower()
                nova_senha = st.text_input("Senha Inicial", type="password", placeholder="••••••••").strip()
                btn_cadastrar = st.form_submit_button("➕ Cadastrar Usuário", type="primary")
                
                if btn_cadastrar:
                    if not novo_user or not nova_senha:
                        st.error("⚠️ Preencha o nome do usuário e a senha inicial.")
                    elif novo_user in banco_usuarios:
                        st.warning(f"⚠️ O usuário '{novo_user}' já está cadastrado no sistema.")
                    else:
                        banco_usuarios[novo_user] = nova_senha
                        salvar_banco_usuarios(banco_usuarios)
                        st.success(f"✅ Usuário **{novo_user}** cadastrado com sucesso!")
                        st.rerun()

        with col_adm2:
            st.subheader("2. Redefinir Senha de Usuário")
            lista_usuarios = [u for u in banco_usuarios.keys() if u != "admin"]
            
            if lista_usuarios:
                user_sel_senha = st.selectbox("Selecione o Usuário:", lista_usuarios, key="sel_user_mudar_senha")
                nova_senha_admin = st.text_input("Nova Senha", type="password", key="txt_nova_senha_admin").strip()
                
                if st.button("🔑 Atualizar Senha", key="btn_mudar_senha"):
                    if nova_senha_admin:
                        banco_usuarios[user_sel_senha] = nova_senha_admin
                        salvar_banco_usuarios(banco_usuarios)
                        st.success(f"✅ Senha do usuário **{user_sel_senha}** atualizada com sucesso!")
                    else:
                        st.error("⚠️ Digite uma nova senha válida.")
            else:
                st.info("Nenhum usuário convencional cadastrado até o momento.")

        st.divider()

        st.subheader("3. Usuários Cadastrados & Remoção")
        
        df_users = pd.DataFrame([
            {"Usuário": k, "Tipo": "Administrador Master" if k == "admin" else "Usuário Convencional"}
            for k in banco_usuarios.keys()
        ])
        
        st.dataframe(df_users, hide_index=True, use_container_width=True)

        if lista_usuarios:
            col_rem1, col_rem2 = st.columns([2, 1])
            with col_rem1:
                user_para_remover = st.selectbox("Selecione um usuário para remover do sistema:", lista_usuarios, key="sel_user_remove")
            with col_rem2:
                st.write("")
                st.write("")
                if st.button("🗑️ Remover Usuário", type="primary", key="btn_remover_user"):
                    del banco_usuarios[user_para_remover]
                    salvar_banco_usuarios(banco_usuarios)
                    st.success(f"✅ Usuário **{user_para_remover}** removido com sucesso!")
                    st.rerun()


# --- BARRA LATERAL LOGOUT ---
st.sidebar.divider()
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.session_state.e_admin = False
    st.rerun()
