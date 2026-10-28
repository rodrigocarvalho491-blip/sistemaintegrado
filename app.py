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
# IDENTIDADE VISUAL CONSIGAZ E ESTILIZAÇÃO
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

/* Ajuste de Campos de Entrada */
div[data-baseweb="input"] > div, 
div[data-baseweb="select"] > div, 
div[data-baseweb="textarea"] > div {
  background-color: #FFFFFF !important;
  border: 1px solid #CBD5E1 !important;
  border-radius: 8px !important;
  color: #1E293B !important;
}

div[data-baseweb="input"] input, 
div[data-baseweb="textarea"] textarea {
  color: #1E293B !important;
  background-color: #FFFFFF !important;
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

# --- GERENCIAMENTO DE BANCO DE DADOS LOCAL ---
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

# --- BOTÃO CUSTOMIZADO DE CÓPIA ---
def botao_copiar_customizado(texto_para_copiar, chave_unica):
    texto_seguro = texto_para_copiar.replace('`', '\\`').replace('$', '\\$').replace('\n', '\\n').replace('"', '\\"')
    component_html = f"""
    <div style="margin-top: 5px; margin-bottom: 10px;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background-color: #0055A5;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            📄 Copiar Texto Completo
        </button>
        <span id="msg_{chave_unica}" style="margin-left: 10px; color: green; font-weight: bold; font-size: 13px; display: none;">Copiado com sucesso!</span>
    </div>
    <script>
    function copiarTexto_{chave_unica}() {{
        const texto = `{texto_seguro}`;
        navigator.clipboard.writeText(texto).then(function() {{
            const msg = document.getElementById("msg_{chave_unica}");
            msg.style.display = "inline";
            setTimeout(function() {{
                msg.style.display = "none";
            }}, 2500);
        }}, function(err) {{
            alert("Erro ao copiar texto: ", err);
        }});
    }}
    </script>
    """
    components.html(component_html, height=50)

# --- CONSULTA CNPJ VIA API ---
@st.cache_data(ttl=3600)
def consultar_cnpj_api(cnpj):
    try:
        cnpj_limpo = "".join(filter(str.isdigit, str(cnpj)))
        if len(cnpj_limpo) == 14:
            url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                dados = resp.json()
                return {
                    "razao_social": dados.get("razao_social") or dados.get("nome_fantasia", ""),
                    "situacao_cadastral": dados.get("descricao_situacao_cadastral", "ATIVA")
                }
    except Exception:
        pass
    return None

# --- CONSULTA DO IPCA ACUMULADO DE 12 MESES (IBGE & BACEN FALLBACK) ---
@st.cache_data(ttl=1800, show_spinner=False)
def obter_ipca_acumulado_12m():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 1. API SIDRA do IBGE (Tabela 1737, Variável 2265 - IPCA Variação acumulada em 12 meses)
    try:
        url_sidra = "https://api.sidra.ibge.gov.br/values/t/1737/v/2265/p/last%201"
        resp = requests.get(url_sidra, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 1:
                item = data[1]
                val_str = item.get("V")
                periodo_str = item.get("D3N", "Mês Vigente")
                if val_str and val_str.strip() not in ("-", "..", "...", "X", "null"):
                    val_float = float(val_str.replace(",", "."))
                    return val_float, periodo_str
    except Exception:
        pass

    # 2. API v3 de Agregados do IBGE
    try:
        url_agregados = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-1/variaveis/2265?localidades=N1[1]"
        resp = requests.get(url_agregados, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            resultado = data[0]["resultados"][0]
            series = resultado.get("series") or resultado.get("séries")
            serie = series[0].get("serie") or series[0].get("série")
            ultimo_periodo = sorted(serie.keys())[-1]
            val_str = serie[ultimo_periodo]
            if val_str and str(val_str).strip() not in ("-", "..", "...", "X", "null"):
                val_float = float(str(val_str).replace(",", "."))
                periodo_fmt = f"{ultimo_periodo[4:6]}/{ultimo_periodo[0:4]}" if len(ultimo_periodo) == 6 else ultimo_periodo
                return val_float, periodo_fmt
    except Exception:
        pass

    # 3. Scraping direto do site Explica Inflação do IBGE
    try:
        url_explica = "https://www.ibge.gov.br/explica/inflacao.php"
        resp = requests.get(url_explica, headers=headers, timeout=5)
        if resp.status_code == 200:
            match = re.search(r'(?:acumulad[oa]|12\s*meses)[^0-9]*(\d+[,.]\d+)\s*%', resp.text, re.IGNORECASE)
            if not match:
                match = re.search(r'class="[^\"]*dado-val[^\"]*"[^>]*>\s*(\d+[,.]\d+)\s*%', resp.text, re.IGNORECASE)
            if match:
                val_float = float(match.group(1).replace(",", "."))
                return val_float, "Mês Vigente"
    except Exception:
        pass

    # 4. Fallback API Banco Central (SGS 433 - IPCA Mensal dos últimos 12 meses)
    try:
        url_bcb = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/12?formato=json"
        resp = requests.get(url_bcb, headers=headers, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            if len(dados) == 12:
                acumulado = 1.0
                for item in dados:
                    taxa = float(item["valor"].replace(",", "."))
                    acumulado *= (1 + taxa / 100.0)
                val_float = round((acumulado - 1) * 100, 2)
                mes_final = dados[-1]["data"]
                return val_float, f"Acumulado 12M ({mes_final})"
    except Exception:
        pass

    return None, None

# --- AUXILIARES E LOGO ---
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
    if "]" in s: s = s.split("]" )[-1].strip()
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

def classificar_status_comodato_inativo(dias_uteis):
    if dias_uteis < 0: return "🔴 Vencido"
    elif dias_uteis <= 7: return "🔴 3ª Semana (Vencimento)"
    elif dias_uteis <= 14: return "🟡 2ª Semana (Intermediária)"
    return "🟢 1ª Semana (Mais distante)"

def resetar_dados_cliente():
    st.session_state.reset_counter += 1
    st.session_state.eq_key_counter = 0
    st.session_state.equipamentos = []
    st.session_state.last_central = "Central"
    st.session_state.last_tipo_cad = "Equipamentos"

# --- GERENCIAMENTO DE ESTADO DE AUTENTICAÇÃO E SESSÃO ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "e_admin" not in st.session_state: st.session_state.e_admin = False
if "df_excel_agenda" not in st.session_state: st.session_state.df_excel_agenda = None

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
        usuario_input = st.text_input("Usuário").strip().lower()
        senha_input = st.text_input("Senha", type="password", placeholder="••••••••").strip()
        btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary")
        
        if btn_entrar:
            if usuario_input in banco_usuarios and banco_usuarios[usuario_input] == senha_input:
                st.session_state.autenticado = True
                st.session_state.usuario_atual = usuario_input
                st.session_state.e_admin = (usuario_input == "admin")
                st.session_state.df_excel_agenda = None  # Agenda vem zerada a cada login
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

lista_abas = [
    "🛠️ Tratativa de Ocorrências",
    "📊 Agenda de Ocorrências", 
    "📓 Bloco de Notas Pessoal"
]

if st.session_state.e_admin:
    lista_abas.append("⚙️ Painel Admin")

abas_sistema = st.tabs(lista_abas)
aba_tratativa = abas_sistema[0]
aba_agenda = abas_sistema[1]
aba_notas = abas_sistema[2]
aba_admin = abas_sistema[3] if st.session_state.e_admin else None

# Inicializações globais
if "tratadas_manualmente" not in st.session_state: st.session_state.tratadas_manualmente = set()
if "filtro_card_dashboard" not in st.session_state: st.session_state.filtro_card_dashboard = "Todos"
if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0
if "eq_key_counter" not in st.session_state: st.session_state.eq_key_counter = 0
if "equipamentos" not in st.session_state: st.session_state.equipamentos = []
if "last_central" not in st.session_state: st.session_state.last_central = "Central"
if "last_tipo_cad" not in st.session_state: st.session_state.last_tipo_cad = "Equipamentos"
if "nota_selecionada_id" not in st.session_state: st.session_state.nota_selecionada_id = None

COL_OCORRENCIA = "Número da ocorrência"
COL_CLIENTE = "Nome do cliente"
COL_ENDERECO = "Endereço de Entrega"
COL_ABERTURA = "Data/Hora de abertura"
COL_PRAZO = "Prazo de Atendimento"
COL_FECHAMENTO = "Data/Hora de fechamento"
COL_SUB_CLASSIF = "Subclassificação Ocorrência"

# =====================================================================
# ABA 1: TRATATIVA DE OCORRÊNCIAS
# =====================================================================
with aba_tratativa:
    col_menu, col_conteudo = st.columns([1, 4])
    
    with col_menu:
        st.markdown("### 📌 Módulos de Tratativa")
        menu_tratativa = st.radio(
            "Selecione a operação:", 
            [
                "📷 Visita de Transferência",
                "📝 Elaboração de Contrato",
                "📋 Aprovação de Contrato",
                "🎂 Aniversário de Contrato"
            ],
            label_visibility="collapsed"
        )
        st.divider()
        if st.button("🔄 Resetar Sessão", use_container_width=True):
            resetar_dados_cliente()
            st.rerun()
            
    with col_conteudo:
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
                botao_copiar_customizado(texto_final, "copia_visita")

        elif menu_tratativa == "📝 Elaboração de Contrato":
            cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento e geração do padrão de solicitação.")
            rcc = st.session_state.reset_counter
            
            tipo_fluxo = st.radio("Selecione o objetivo da solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, index=None, key=f"fluxo_c_{rcc}")
            st.divider()
            
            st.subheader("1. Motivo")
            motivo_solicitacao = st.text_input("Motivo da solicitação *", key=f"motivo_{rcc}")
            st.divider()
            
            st.subheader("2. Dados do Cliente")
            col_cli1, col_cli2, col_cli3 = st.columns(3)
            with col_cli1: contato_contrato = st.text_input("Contato *", key=f"contato_c_{rcc}")
            with col_cli2: telefone_contrato = st.text_input("Telefone *", key=f"tel_c_{rcc}")
            with col_cli3: email_contrato = st.text_input("E-mail *", key=f"email_c_{rcc}")
            st.divider()
            
            st.subheader("3. Solicitação")
            tipo_contrato = st.radio("Contrato / Aditamento / Distrato *", ["Contrato", "Aditamento", "Distrato"], horizontal=True, index=None, key=f"tp_cont_{rcc}")
            st.divider()
            
            st.subheader("4. Dados do Contrato")
            col_con1, col_con2 = st.columns(2)
            cnpj_campo_val, ie_campo_val = "", ""
            status_cnpj_txt, razao_social_txt = "", ""
            email_novo_prop = "n/a"
            
            with col_con1:
                endereco_padrao = st.text_input("Endereço padrão ou entrega? *", key=f"end_padrao_{rcc}")
                mesmo_prop_opt = st.radio("Mesmo proprietário? *", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_prop_{rcc}")
                if mesmo_prop_opt == "Não":
                    email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato *", key=f"email_novo_{rcc}")
                
                mesmo_cnpj_opt = st.radio("Mesmo CNPJ? *", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_cnpj_{rcc}")
                if mesmo_cnpj_opt == "Sim":
                    cnpj_campo_val = st.text_input("CNPJ", key=f"cnpj_val_{rcc}")
                    ie_campo_val = st.text_input("I.E.", key=f"ie_val_{rcc}")
                elif mesmo_cnpj_opt == "Não":
                    cnpj_campo_val = st.text_input("Novo CNPJ", key=f"novo_cnpj_val_{rcc}")
                    ie_campo_val = st.text_input("Nova I.E.", key=f"nova_ie_val_{rcc}")
                    
                if cnpj_campo_val and len("".join(filter(str.isdigit, str(cnpj_campo_val)))) == 14:
                    dados_api = consultar_cnpj_api(cnpj_campo_val)
                    if dados_api:
                        razao_social_txt = dados_api.get("razao_social", "Não encontrada")
                        situacao_cad = dados_api.get("situacao_cadastral", "")
                        status_cnpj_txt = "Ativo" if str(situacao_cad).upper() in ["2", "ATIVA"] else f"Inativa ({situacao_cad})"
                        st.markdown(f"✅ **Razão Social:** {razao_social_txt}")
                        st.markdown(f"🟢 **Status CNPJ:** {status_cnpj_txt}")
                    else:
                        st.warning("⚠️ CNPJ não encontrado ou erro na consulta automática.")
                        
            with col_con2:
                cond_pagamento = st.text_input("Condição de pagamento *", key=f"cond_pag_{rcc}")
                vigencia = st.text_input("Vigência *", key=f"vigencia_{rcc}")
                
                qtd_entregas_c = st.number_input("Quantidade de endereços de entrega / centrais", min_value=1, value=1, step=1, key=f"qtd_ent_c_{rcc}")
                equipamentos_contrato = ""
                eq_dict_c = {}
                if qtd_entregas_c == 1:
                    equipamentos_contrato = st.text_input("Equipamentos *", key=f"eq_contrato_c_{rcc}")
                else:
                    st.markdown("**Equipamentos por Endereço de Entrega:**")
                    for i in range(1, int(qtd_entregas_c) + 1):
                        eq_dict_c[i] = st.text_input(f"Equipamentos - [Entrega {i}] *", key=f"eq_ent_{i}_{rcc}")

            st.divider()
            
            st.subheader("5. Comodato / Fornecimento")
            tipo_fornecimento = st.radio("Tipo de Fornecimento *", ["Granel", "Cilindro"], horizontal=True, index=None, key=f"tp_forn_{rcc}")
            
            preco_granel, consumo_granel = "", ""
            p13_val, p20_val, p45_val = "", "", ""
            p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
            
            if tipo_fornecimento == "Granel":
                col_g1, col_g2 = st.columns(2)
                with col_g1: preco_granel = st.text_input("Preço Granel", key=f"preco_granel_{rcc}")
                with col_g2: consumo_granel = st.text_input("Consumo mensal previsto (kg)", key=f"cons_granel_{rcc}")
            elif tipo_fornecimento == "Cilindro":
                st.markdown("**Preços por Modelo de Cilindro:**")
                col_cp1, col_cp2, col_cp3 = st.columns(3)
                with col_cp1: p13_val = st.text_input("Preço P13 (/und)", key=f"p13_v_{rcc}")
                with col_cp2: p20_val = st.text_input("Preço P20 (/und)", key=f"p20_v_{rcc}")
                with col_cp3: p45_val = st.text_input("Preço P45 (/und)", key=f"p45_v_{rcc}")
                
                st.markdown("**Consumo mensal previsto (quantidade):**")
                col_cc1, col_cc2, col_cc3 = st.columns(3)
                with col_cc1: p13_qtd = st.number_input("Qtd Cilindros P13", min_value=0, value=0, step=1, key=f"p13_q_{rcc}")
                with col_cc2: p20_qtd = st.number_input("Qtd Cilindros P20", min_value=0, value=0, step=1, key=f"p20_q_{rcc}")
                with col_cc3: p45_qtd = st.number_input("Qtd Cilindros P45", min_value=0, value=0, step=1, key=f"p45_q_{rcc}")

            st.divider()
            
            st.subheader("6. Financeiro")
            col_fin1, col_fin2 = st.columns(2)
            with col_fin1:
                possui_debito_fin = st.radio("Cliente possui débitos? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rcc}")
                resp_pendentes = "n/a"
                if possui_debito_fin == "Sim":
                    resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes? *", key=f"resp_pend_{rcc}")
                    
            responsaveis_dados = []
            nome_testemunha, email_testemunha = "", ""
            if tipo_fluxo == "Enviar para Assinatura":
                st.markdown("---")
                st.subheader("Dados de Assinatura e Testemunhas")
                col_t1, col_t2 = st.columns(2)
                with col_t1: nome_testemunha = st.text_input("Nome da Testemunha", key=f"nome_test_{rcc}")
                with col_t2: email_testemunha = st.text_input("E-mail da Testemunha", key=f"email_test_{rcc}")
                
                qtd_responsaveis = st.selectbox("Quantidade de Responsáveis pela Assinatura", [1, 2, 3, 4], index=0, key=f"qtd_resp_{rcc}")
                for i in range(1, qtd_responsaveis + 1):
                    st.markdown(f"**Responsável {i}**")
                    col_r1, col_r2 = st.columns(2)
                    with col_r1: nome_resp = st.text_input(f"Nome do Responsável {i}", key=f"nome_resp_{i}_{rcc}")
                    with col_r2: email_resp = st.text_input(f"E-mail do Responsável {i}", key=f"email_resp_{i}_{rcc}")
                    responsaveis_dados.append({"nome": nome_resp, "email": email_resp})

            st.divider()
            
            st.subheader("7. Condomínio CONTA SIM")
            conta_sim = st.radio("Condomínio CONTA SIM? *", ["Sim", "Não"], horizontal=True, index=None, key=f"conta_sim_{rcc}")
            num_unidades, qtd_torres, qtd_blocos, preco_religue, preco_servico = "", "", "", "", ""
            if conta_sim == "Sim":
                col_cs1, col_cs2, col_cs3 = st.columns(3)
                with col_cs1:
                    num_unidades = st.text_input("N° Unid autônomas (Aptos + áreas comuns)", key=f"num_unid_{rcc}")
                    qtd_torres = st.text_input("Qtd Torres", key=f"qtd_torres_{rcc}")
                with col_cs2:
                    qtd_blocos = st.text_input("Qtd Blocos", key=f"qtd_blocos_{rcc}")
                    preco_religue = st.text_input("Valor preço de religue", key=f"preco_rel_{rcc}")
                with col_cs3:
                    preco_servico = st.text_input("Valor preço de serviço", key=f"preco_serv_{rcc}")

            observacoes_contrato = st.text_area("Observações", key=f"obs_c_{rcc}")
            
            st.divider()
            if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
                sel_granel = "[x]" if tipo_fornecimento == "Granel" else "[ ]"
                sel_cilindro = "[x]" if tipo_fornecimento == "Cilindro" else "[ ]"
                
                if qtd_entregas_c == 1:
                    eq_txt = equipamentos_contrato
                else:
                    eq_linhas = [f"[Entrega {i}] {eq_dict_c[i].strip()}" for i in range(1, int(qtd_entregas_c) + 1) if eq_dict_c.get(i, "").strip()]
                    eq_txt = "\n" + "\n".join(eq_linhas)
                    
                texto_padrao_contrato = f"Motivo da solicitação: {motivo_solicitacao}"
                if tipo_fluxo == "Gerar Minuta":
                    texto_padrao_contrato += "\n\n** FAVOR GERAR MINUTA EM PDF PARA ENVIO AO CLIENTE **"
                    
                texto_padrao_contrato += f"""

Contato: {contato_contrato}
Telefone: {telefone_contrato}
E-mail: {email_contrato}
Contrato / Aditamento / Distrato: {tipo_contrato if tipo_contrato else ''}
Mesmo proprietário?: {mesmo_prop_opt if mesmo_prop_opt else ''}
E-mail do novo proprietário que receberá o novo contrato: {email_novo_prop}
Mesmo CNPJ?: {mesmo_cnpj_opt if mesmo_cnpj_opt else ''}"""

                if mesmo_cnpj_opt == "Sim":
                    texto_padrao_contrato += f"\nCNPJ: {cnpj_campo_val}\nI.E.: {ie_campo_val}"
                elif mesmo_cnpj_opt == "Não":
                    texto_padrao_contrato += f"\nNovo CNPJ: {cnpj_campo_val}\nNova I.E.: {ie_campo_val}"
                    
                if razao_social_txt:
                    texto_padrao_contrato += f"\nRazão Social (Consultada): {razao_social_txt}"
                if status_cnpj_txt:
                    texto_padrao_contrato += f"\nStatus CNPJ: {status_cnpj_txt}"
                    
                texto_padrao_contrato += f"""
Endereço padrão ou entrega?: {endereco_padrao}
Condição de pagamento: {cond_pagamento}
Vigência: {vigencia}
Equipamentos: {eq_txt}

Tipo de Fornecimento: {sel_granel} Granel  {sel_cilindro} Cilindro"""

                if tipo_fornecimento == "Granel":
                    texto_padrao_contrato += f"\nPreço Granel: {preco_granel} | Consumo mensal previsto: {consumo_granel} kg"
                elif tipo_fornecimento == "Cilindro":
                    precos_c_list = []
                    if p13_val: precos_c_list.append(f"P13 = {p13_val} / und")
                    if p20_val: precos_c_list.append(f"P20 = {p20_val} / und")
                    if p45_val: precos_c_list.append(f"P45 = {p45_val} / und")
                    precos_c_str = " | ".join(precos_c_list) if precos_c_list else "n/a"
                    
                    tot_kg = (p13_qtd * 13) + (p20_qtd * 20) + (p45_qtd * 45)
                    texto_padrao_contrato += f"\nPreços Cilindros: {precos_c_str}\nConsumo mensal previsto: {p13_qtd} P13 / {p20_qtd} P20 / {p45_qtd} P45 (Total: {tot_kg} kg)"

                texto_padrao_contrato += f"\n\nCliente possui débitos?: {possui_debito_fin if possui_debito_fin else ''}"
                if possui_debito_fin == "Sim":
                    texto_padrao_contrato += f"\nResponsável pelas NF's pendentes: {resp_pendentes}"
                    
                if tipo_fluxo == "Enviar para Assinatura":
                    texto_padrao_contrato += f"\n\nTestemunha: {nome_testemunha} ({email_testemunha})"
                    for idx_r, resp_d in enumerate(responsaveis_dados, 1):
                        texto_padrao_contrato += f"\nResponsável {idx_r}: {resp_d['nome']} ({resp_d['email']})"
                        
                texto_padrao_contrato += f"\n\nImplantação de Conta SIM: [ {'x' if conta_sim == 'Sim' else ' '} ] sim [ {'x' if conta_sim == 'Não' else ' '} ] não"
                if conta_sim == "Sim":
                    texto_padrao_contrato += f"\nUnidades: {num_unidades} | Torres: {qtd_torres} | Blocos: {qtd_blocos} | Religue: {preco_religue} | Serviço: {preco_servico}"
                    
                if observacoes_contrato.strip():
                    texto_padrao_contrato += f"\n\nObs.: {observacoes_contrato.strip()}"
                    
                st.success("✅ Texto do Contrato gerado com sucesso! Copie abaixo:")
                st.code(texto_padrao_contrato, language="text")
                botao_copiar_customizado(texto_padrao_contrato, "copia_elaboracao")

        elif menu_tratativa == "📋 Aprovação de Contrato":
            cabecalho_pagina("Aprovação de Contrato", "Formulário de preenchimento para solicitação de aprovação.")
            rcap = st.session_state.reset_counter
            
            st.subheader("1. Informações de Contato")
            c_ap1, c_ap2, c_ap3 = st.columns(3)
            with c_ap1: contato_ap = st.text_input("Contato *", key=f"ap_cont_{rcap}")
            with c_ap2: telefone_ap = st.text_input("Telefone *", key=f"ap_tel_{rcap}")
            with c_ap3: email_ap = st.text_input("E-mail *", key=f"ap_email_{rcap}")

            st.divider()
            st.subheader("2. Dados e Motivo da Solicitação")
            motivo_reg = st.text_input("Motivo da regularização *", key=f"ap_motivo_{rcap}")

            c_ap4, c_ap5, c_ap6 = st.columns(3)
            with c_ap4: atualizar_email = st.radio("Atualizar E-mail?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_atu_email_{rcap}")
            with c_ap5: contrato_adit = st.radio("Contrato / Aditamento", ["Contrato", "Aditamento"], horizontal=True, index=None, key=f"ap_tp_cont_{rcap}")
            with c_ap6: vigencia_ap = st.text_input("Vigência", key=f"ap_vig_{rcap}")

            qtd_entregas_ap = st.number_input("Quantidade de endereços de entrega / centrais", min_value=1, value=1, step=1, key=f"qtd_ent_ap_{rcap}")
            equipamentos_ap = ""
            eq_dict_ap = {}
            if qtd_entregas_ap == 1:
                equipamentos_ap = st.text_input("Equipamentos", key=f"ap_eq_{rcap}")
            else:
                st.markdown("**Equipamentos por Endereço de Entrega:**")
                for i in range(1, int(qtd_entregas_ap) + 1):
                    eq_dict_ap[i] = st.text_input(f"Equipamentos - [Entrega {i}]", key=f"ap_eq_ent_{i}_{rcap}")

            especificidade_ap = st.text_input("Existe especificidade sobre a solicitação?", key=f"ap_esp_{rcap}")

            st.divider()
            st.subheader("3. Redimensionamento")
            redim = st.radio("Redimensionamento:", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_redim_{rcap}")
            comodato_de, comodato_para = "", ""
            inc_tanques = "Não"
            env_pecas = "Não"

            if redim == "Sim":
                c_p1, c_p2 = st.columns(2)
                with c_p1: comodato_de = st.text_input("Comodato passou de:", key=f"ap_com_de_{rcap}")
                with c_p2: comodato_para = st.text_input("Para:", key=f"ap_com_para_{rcap}")
                
                c_p3, c_p4 = st.columns(2)
                with c_p3: inc_tanques = st.radio("Inclusão de tanques?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_inc_tanq_{rcap}")
                with c_p4: env_pecas = st.radio("Necessário lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_env_pec_{rcap}")

            st.divider()
            st.subheader("4. Condomínio Conta Sim & Portaria")
            implantacao_csim = st.radio("Implantação de conta sim:", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_{rcap}")
            env_pecas_ficha = "Não"
            env_ficha_cliente = "Não"
            tp_portaria, contato_resp_port, part_local, contato_sindico = "", "", "", ""

            if implantacao_csim == "Sim":
                c_cs1, c_cs2 = st.columns(2)
                with c_cs1: env_pecas_ficha = st.radio("Foi enviado lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_pec_{rcap}")
                with c_cs2: env_ficha_cliente = st.radio("Foi enviado ficha de clientes?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_ficha_{rcap}")
                tp_portaria = st.text_input("Tipo de portaria", key=f"ap_tp_port_{rcap}")
                contato_resp_port = st.text_input("Contato do responsável (portaria remota, nº ap ou contato)", key=f"ap_cont_resp_{rcap}")
                part_local = st.text_input("Particularidades do local", key=f"ap_part_local_{rcap}")
                contato_sindico = st.text_input("Contato atualizado do síndico", key=f"ap_cont_sind_{rcap}")

            st.divider()
            st.subheader("5. Alteração de CNPJ ou Razão Social & Títulos")
            alt_cnpj = st.radio("Alteração de CNPJ ou razão social?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_alt_cnpj_{rcap}")
            mesmo_prop_opt = st.radio("Se trata do mesmo proprietário:", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_mesmo_prop_{rcap}")
            possui_titulos_aberto = st.radio("Possui títulos em aberto?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_tit_aberto_{rcap}")
            
            neg_tit_input = ""
            if possui_titulos_aberto == "Sim":
                neg_tit_input = st.text_input("Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto:", key=f"ap_neg_tit_{rcap}")

            st.divider()
            st.subheader("6. Redução de Vigência")
            red_vig = st.radio("Redução de vigência?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_red_vig_{rcap}")
            motivo_red_vig = ""
            if red_vig == "Sim":
                motivo_red_vig = st.text_input("Descreva o motivo da redução de vigência:", key=f"ap_mot_red_{rcap}")

            st.divider()
            st.subheader("Projeto Padrão")
            col_proj1, col_proj2 = st.columns([3, 1])
            with col_proj1: projeto_num = st.text_input("Projeto (Informe o número completo do projeto) *", key=f"ap_proj_{rcap}")
            with col_proj2:
                st.write(""); st.write("")
                is_cilindros = st.checkbox("Cilindros", key=f"ap_cil_{rcap}")

            st.divider()
            if st.button("📝 Gerar Texto de Aprovação de Contrato", type="primary"):
                if not is_cilindros and not projeto_num.strip():
                    st.error("⚠️ O campo 'Projeto' é obrigatório,
