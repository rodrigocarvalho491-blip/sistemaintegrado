import os
import re
import uuid
import base64
import html as html_lib
import pandas as pd
import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components
import altair as alt
from datetime import datetime
from fpdf import FPDF
from supabase import create_client, Client

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

# --- CONEXÃO COM O SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    try:
        url = st.secrets["supabase"]["URL"]
        key = st.secrets["supabase"]["KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Erro ao conectar ao banco de dados Supabase: {e}")
        st.stop()

supabase = init_supabase()

# --- CAMADA DE PERSISTÊNCIA NA NUVEM (SUPABASE) ---
def carregar_banco_usuarios():
    try:
        res = supabase.table("usuarios").select("*").execute()
        dados = {}
        for row in res.data:
            dados[row["usuario"]] = {
                "senha": row["senha"],
                "nivel_acesso": row.get("nivel_acesso", "convencional"),
                "precisa_trocar_senha": row.get("precisa_trocar_senha", False)
            }
        
        if "admin" not in dados:
            supabase.table("usuarios").insert({
                "usuario": "admin", 
                "senha": "admin", 
                "nivel_acesso": "admin", 
                "precisa_trocar_senha": False
            }).execute()
            dados["admin"] = {"senha": "admin", "nivel_acesso": "admin", "precisa_trocar_senha": False}
        return dados
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return {"admin": {"senha": "admin", "nivel_acesso": "admin", "precisa_trocar_senha": False}}

def salvar_usuario(usuario, senha, nivel_acesso="convencional", precisa_trocar=False):
    try:
        payload = {
            "usuario": usuario,
            "senha": senha,
            "nivel_acesso": nivel_acesso,
            "precisa_trocar_senha": precisa_trocar
        }
        supabase.table("usuarios").upsert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar usuário: {e}")
        return False

def remover_usuario(usuario):
    try:
        supabase.table("usuarios").delete().eq("usuario", usuario).execute()
        supabase.table("notas").delete().eq("usuario", usuario).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao remover usuário: {e}")
        return False

def carregar_banco_notas(usuario):
    try:
        res = supabase.table("notas").select("*").eq("usuario", usuario).execute()
        notas = {}
        for row in res.data:
            notas[row["id"]] = {
                "titulo": row["titulo"],
                "cliente": row["cliente"],
                "texto": row["texto"],
                "data_modificacao": row["data_modificacao"]
            }
        return notas
    except Exception as e:
        st.error(f"Erro ao carregar notas: {e}")
        return {}

def salvar_nota(nota_id, usuario, titulo, cliente, texto):
    try:
        data_mod = datetime.now().strftime("%d/%m/%Y %H:%M")
        payload = {
            "id": nota_id,
            "usuario": usuario,
            "titulo": titulo,
            "cliente": cliente,
            "texto": texto,
            "data_modificacao": data_mod
        }
        supabase.table("notas").upsert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar nota: {e}")
        return False

def apagar_nota(nota_id):
    try:
        supabase.table("notas").delete().eq("id", nota_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao apagar nota: {e}")
        return False

# --- CONSULTA CNPJ & IPCA ---
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

@st.cache_data(ttl=1800, show_spinner=False)
def obter_ipca_acumulado_12m():
    try:
        url = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-1/variaveis/2265?localidades=N1[1]"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            resultado = data[0]["resultados"][0]
            series = resultado.get("series") or resultado.get("séries")
            serie = series[0].get("serie") or series[0].get("série")
            ultimo_periodo = sorted(serie.keys())[-1]
            val_str = serie[ultimo_periodo]
            if val_str and str(val_str).strip() not in ("-", "..", "...", "X"):
                val_float = float(str(val_str).replace(",", "."))
                periodo_fmt = f"{ultimo_periodo[4:6]}/{ultimo_periodo[0:4]}" if len(ultimo_periodo) == 6 else ultimo_periodo
                return val_float, periodo_fmt
    except Exception:
        pass
    return None, None

def formatar_ci_num(ci_str):
    digits = re.sub(r'\D', '', str(ci_str))
    if len(digits) == 9:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:]}"
    elif len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}"
    elif digits:
        return ci_str.strip()
    return "000.000.000"

# --- GERADOR DE PDF DE RELATÓRIO FOTOGRÁFICO ---
class RelatorioPDF(FPDF):
    def __init__(self, cod_cliente="", nome_cliente="", logo_path=""):
        super().__init__()
        self.cod_cliente = cod_cliente.replace(".", "").strip().upper() if cod_cliente else ""
        self.nome_cliente = nome_cliente.strip().upper() if nome_cliente else ""
        self.logo_path = logo_path

    def header(self):
        if self.logo_path and os.path.exists(self.logo_path):
            self.image(self.logo_path, x=10, y=8, w=45)
        if self.page_no() == 1:
            self.set_y(10)
            self.set_font("Arial", "B", 15)
            self.cell(0, 8, "RELATÓRIO FOTOGRÁFICO", align="C", ln=1)
            info_cabecalho = f"{self.cod_cliente} | {self.nome_cliente}".strip(" |")
            if info_cabecalho:
                self.set_font("Arial", "B", 11)
                self.cell(0, 6, info_cabecalho, align="C", ln=1)
            self.set_y(35)
        else:
            self.set_y(35)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

# --- FUNÇÕES PARA PROCESSAMENTO DA AGENDA EXCEL ---
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
        if cidade.isdigit() and len(partes) >= 3:
            cidade = partes[-3].strip()
        return cidade.title()
    return s.title()

def calcular_dias_uteis(data_inicio, data_fim):
    h = pd.Timestamp(data_inicio).normalize().date()
    p = pd.Timestamp(data_fim).normalize().date()
    if p > h: return int(np.busday_count(h, p))
    elif p < h: return -int(np.busday_count(p, h))
    else: return 0

def classificar_status_geral(dias_uteis):
    if dias_uteis < 0: return "🔴 Vencido"
    elif dias_uteis == 0: return "🔵 Vence Hoje"
    elif dias_uteis == 1: return "🟠 Vence Amanhã"
    elif 2 <= dias_uteis <= 5: return "🟡 Vence na Semana"
    else: return "🟢 No Prazo"

def classificar_status_comodato(dias_uteis):
    if dias_uteis < 0: return "🔴 Vencido"
    elif dias_uteis == 0: return "🔵 Vence Hoje"
    elif dias_uteis == 1: return "🟠 Vence Amanhã"
    elif dias_uteis <= 5: return "🔴 3ª Semana" 
    elif dias_uteis <= 10: return "🟡 2ª Semana" 
    else: return "🟢 1ª Semana" 

# --- AUXILIARES E VISUAL ---
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")

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

/* TRAVAR MENU SUPERIOR (ABAS) NO TOPO AO ROLAR */
div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    position: sticky !important;
    top: 0px !important;
    z-index: 9999 !important;
    background-color: #F1F5FA !important;
    padding-top: 15px !important;
    padding-bottom: 10px !important;
    border-bottom: 1px solid #E2E8F0;
}

.block-container, [data-testid="stMainBlockContainer"] {
  max-width: 1180px !important;
  margin: 1.2rem auto 2rem auto !important;
  padding: 1.8rem 2.4rem 2.4rem 2.4rem !important;
  background: #FFFFFF !important;
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(10,37,64,.06), 0 8px 28px rgba(10,37,64,.07);
}

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

div.stButton > button:first-child {
  background-color: #0055A5 !important; 
  color: #ffffff !important;
  border-radius: 8px !important; 
  border: none !important; 
  font-weight: bold !important;
}

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

def botao_copiar_customizado(texto_para_copiar, chave_unica, label_btn="📄 Copiar Texto Completo"):
    texto_seguro = texto_para_copiar.replace('`', '\\`').replace('$', '\\$').replace('\n', '\\n').replace('"', '\\"')
    component_html = f"""
    <div style="margin-top: 5px; margin-bottom: 10px;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background-color: #0055A5; color: white; padding: 8px 16px; border: none;
            border-radius: 6px; font-weight: bold; font-size: 14px; cursor: pointer;
            display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">{label_btn}</button>
        <span id="msg_{chave_unica}" style="margin-left: 10px; color: green; font-weight: bold; font-size: 13px; display: none;">Copiado com sucesso!</span>
    </div>
    <script>
    function copiarTexto_{chave_unica}() {{
        const texto = `{texto_seguro}`;
        navigator.clipboard.writeText(texto).then(function() {{
            const msg = document.getElementById("msg_{chave_unica}");
            msg.style.display = "inline";
            setTimeout(function() {{ msg.style.display = "none"; }}, 2500);
        }});
    }}
    </script>
    """
    components.html(component_html, height=50)

@st.cache_data(show_spinner=False)
def _logo_base64(caminho):
    try:
        with open(caminho, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""

def _logo_html(classe_img, classe_wrapper=""):
    b64 = _logo_base64(LOGO_PATH)
    if not b64: return ""
    img_tag = f'<img class="{classe_img}" src="data:image/png;base64,{b64}" alt="Consigaz">'
    return f'<div class="{classe_wrapper}">{img_tag}</div>' if classe_wrapper else img_tag

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

# --- GERENCIAMENTO DE ESTADO DE AUTENTICAÇÃO ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "e_admin" not in st.session_state: st.session_state.e_admin = False
if "troca_obrigatoria" not in st.session_state: st.session_state.troca_obrigatoria = False
if "tratadas_manualmente" not in st.session_state: st.session_state.tratadas_manualmente = set()

# =====================================================================
# TELA DE AUTENTICAÇÃO E TROCA OBRIGATÓRIA DE SENHA
# =====================================================================
banco_usuarios = carregar_banco_usuarios()

if not st.session_state.autenticado:
    side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
    st.sidebar.markdown(
        f'<div class="cg-side-brand">{side_logo_html}'
        f'<div class="cg-side-name">Sistema Integrado</div></div>',
        unsafe_allow_html=True,
    )
    
    st.title("🔐 Acesso ao Sistema Integrado | Consigaz")
    st.markdown("Insira suas credenciais para acessar a plataforma.")

    with st.form("form_login_sistema"):
        usuario_input = st.text_input("Usuário").strip().lower()
        senha_input = st.text_input("Senha", type="password", placeholder="••••••••").strip()
        btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary")
        
        if btn_entrar:
            if usuario_input in banco_usuarios and banco_usuarios[usuario_input]["senha"] == senha_input:
                usr_data = banco_usuarios[usuario_input]
                st.session_state.autenticado = True
                st.session_state.usuario_atual = usuario_input
                st.session_state.e_admin = (usr_data["nivel_acesso"] == "admin")
                st.session_state.troca_obrigatoria = usr_data["precisa_trocar_senha"] or (senha_input == "123456")
                st.rerun()
            else:
                st.error("❌ Usuário ou senha incorretos!")
    st.stop()

if st.session_state.troca_obrigatoria:
    cabecalho_pagina("🔑 Alteração Obrigatória de Senha", "Sua conta está utilizando a senha temporária. Defina sua nova senha pessoal para prosseguir.")
    
    with st.form("form_troca_senha_obrigat"):
        nova_s1 = st.text_input("Nova Senha Pessoal *", type="password").strip()
        nova_s2 = st.text_input("Confirme a Nova Senha *", type="password").strip()
        btn_mudar_obrigat = st.form_submit_button("🔒 Salvar Nova Senha e Acessar", type="primary")
        
        if btn_mudar_obrigat:
            if not nova_s1 or not nova_s2:
                st.error("⚠️ Preencha ambos os campos de senha.")
            elif nova_s1 == "123456":
                st.error("⚠️ Escolha uma senha diferente da senha inicial '123456'.")
            elif nova_s1 != nova_s2:
                st.error("⚠️ As senhas digitadas não conferem.")
            else:
                curr_u = st.session_state.usuario_atual
                curr_nivel = banco_usuarios[curr_u]["nivel_acesso"]
                if salvar_usuario(curr_u, nova_s1, nivel_acesso=curr_nivel, precisa_trocar=False):
                    st.session_state.troca_obrigatoria = False
                    st.success("✅ Senha alterada com sucesso!")
                    st.rerun()
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
    st.sidebar.caption("⭐ Perfil: Administrador")

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

if "nota_selecionada_id" not in st.session_state: st.session_state.nota_selecionada_id = None
if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0

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
            
    with col_conteudo:
        rc = st.session_state.reset_counter

        # -------------------------------------------------------------
        # 1. VISITA DE TRANSFERÊNCIA
        # -------------------------------------------------------------
        if menu_tratativa == "📷 Visita de Transferência":
            cabecalho_pagina("Visita de Transferência & Relatório Técnico", "Gerador automatizado de relatórios técnicos, formulários e inspeções fotográficas.")
            
            if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_novo_vis_{rc}"):
                st.session_state.reset_counter += 1
                st.rerun()

            st.divider()
            st.subheader("1. Identificação do Cliente")
            s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
            with s1_l1_c1: cod_cliente = st.text_input("Código do Cliente *", key=f"vis_cod_{rc}")
            with s1_l1_c2: nome_cliente = st.text_input("Nome / Razão Social *", key=f"vis_nome_{rc}")
            with s1_l1_c3: telefone = st.text_input("Telefone *", key=f"vis_tel_{rc}")

            s1_l2_c1, s1_l2_c2 = st.columns(2)
            with s1_l2_c1: contato = st.text_input("Contato *", key=f"vis_cont_{rc}")
            with s1_l2_c2: departamento = st.text_input("Sobrenome ou Departamento *", key=f"vis_dep_{rc}")

            st.divider()
            st.subheader("2. Informações Contratuais")
            s2_c1, s2_c2 = st.columns(2)
            with s2_c1:
                eq_contrato = st.radio("Equipamentos de acordo com contrato vigente? *", ["Sim", "Não"], horizontal=True, key=f"eq_cont_{rc}")
                desc_eq_contrato = st.text_input("Detalhes dos Equipamentos *", key=f"desc_eq_{rc}")
                rep2_correto = st.radio("Representante 2 está correto? *", ["Sim", "Não"], horizontal=True, key=f"rep2_{rc}")
                desc_rep2 = st.text_input("Nº OC de Regularização Rep. 2", key=f"desc_rep2_{rc}") if rep2_correto == "Não" else ""
                tem_freq = st.radio("Possui programação cadastrada? *", ["Sim", "Não"], horizontal=True, key=f"tem_freq_{rc}")
                desc_freq = st.text_input("Qual a programação / Nº OC *", key=f"desc_freq_{rc}")
            
            with s2_c2:
                consumo_previsto = st.text_input("Consumo Previsto (kg) *", key=f"cons_prev_{rc}")
                consumo_real = st.text_input("Consumo Médio (kg) *", key=f"cons_real_{rc}")
                possui_art = st.radio("Laudo ART emitido? *", ["Sim", "Não"], horizontal=True, key=f"possui_art_{rc}")
                desc_art = st.text_input("Número da ART / Nº OC *", key=f"desc_art_{rc}")
                central_norma = st.radio("Central atende as normas? *", ["Sim", "Não"], horizontal=True, key=f"central_norma_{rc}")
                desc_central_norma = st.text_input("Motivo Central fora de norma", key=f"desc_norma_{rc}") if central_norma == "Não" else ""

            st.divider()
            st.subheader("3. Novos Negócios & Satisfação")
            s3_c1, s3_c2 = st.columns(2)
            with s3_c1:
                indica_negocios = st.radio("Indicação de novos negócios? *", ["Sim", "Não"], horizontal=True, key=f"ind_neg_{rc}")
                desc_negocios = st.text_input("Detalhes da indicação", key=f"desc_neg_{rc}") if indica_negocios == "Sim" else ""
                possui_debitos = st.radio("Cliente possui débitos? *", ["Sim", "Não"], horizontal=True, key=f"possui_deb_{rc}")
                desc_debitos = st.text_input("Detalhes dos débitos", key=f"desc_deb_{rc}") if possui_debitos == "Sim" else ""
            with s3_c2:
                cliente_satisfeito = st.radio("Cliente satisfeito com a Consigaz? *", ["Sim", "Não"], horizontal=True, key=f"cli_sat_{rc}")
                desc_satisfacao = st.text_input("Observação sobre satisfação", key=f"desc_sat_{rc}")

            observacoes = st.text_area("Observações Gerais", key=f"obs_transf_{rc}")

            st.divider()
            st.subheader("4. Quantidade de Centrais")
            qtd_centrais = st.number_input("Quantidade de Centrais de Gás", min_value=1, max_value=10, value=1, step=1, key=f"vis_qtd_cent_{rc}")

            st.divider()
            st.subheader("5. Relatório Fotográfico - Upload de Imagens")
            
            def carregar_fotos(label, max_arquivos=None):
                fotos = st.file_uploader(label, type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_{label}_{rc}")
                if max_arquivos and fotos and len(fotos) > max_arquivos:
                    st.error(f"⚠️ Limite excedido para {label}. Serão considerados apenas os primeiros {max_arquivos} arquivos.")
                    return fotos[:max_arquivos]
                return fotos

            dic_fotos_final = {}
            col_f1, col_f2 = st.columns(2)
            with col_f1: dic_fotos_final["FACHADA"] = carregar_fotos("📸 FACHADA (Até 2 fotos)", max_arquivos=2)
            with col_f2: dic_fotos_final["CILINDROS"] = carregar_fotos("📸 CILINDROS (Até 5 fotos)", max_arquivos=5)

            st.write("---")
            if qtd_centrais == 1:
                c1, c2, c3 = st.columns(3)
                with c1: dic_fotos_final["ABRIGO"] = carregar_fotos("📸 ABRIGO (Até 10 fotos)", max_arquivos=10)
                with c2: dic_fotos_final["CENTRAL"] = carregar_fotos("📸 CENTRAL (Até 5 fotos)", max_arquivos=5)
                with c3: dic_fotos_final["EQUIPAMENTOS"] = carregar_fotos("📸 EQUIPAMENTOS", max_arquivos=None)
            else:
                for i in range(1, int(qtd_centrais) + 1):
                    st.markdown(f"**📸 FOTOS - CENTRAL {i:02d}**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nome_abrigo = f"ABRIGO CENTRAL {i:02d}"
                        dic_fotos_final[nome_abrigo] = carregar_fotos(f"📸 {nome_abrigo} (Até 10)", max_arquivos=10)
                    with c2:
                        nome_central = f"CENTRAL {i:02d}"
                        dic_fotos_final[nome_central] = carregar_fotos(f"📸 {nome_central} (Até 5)", max_arquivos=5)
                    with c3:
                        nome_equip = f"EQUIPAMENTOS CENTRAL {i:02d}"
                        dic_fotos_final[nome_equip] = carregar_fotos(f"📸 {nome_equip}", max_arquivos=None)

            st.divider()
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("📝 Gerar Texto para Sistema", type="primary"):
                    linha_art = f"(x) Sim ( ) Não {desc_art.strip()}" if possui_art == "Sim" else f"( ) Sim (x) Não - {desc_art.strip()}"
                    texto_eq_contrato = f"{eq_contrato}. {desc_eq_contrato.strip()}".strip()
                    texto_rep2 = rep2_correto + (f" - {desc_rep2.strip()}" if rep2_correto == "Não" and desc_rep2.strip() else "")
                    texto_freq = tem_freq + (f" - {desc_freq.strip()}" if desc_freq.strip() else "")
                    texto_debitos = possui_debitos + (f" - {desc_debitos.strip()}" if possui_debitos == "Sim" and desc_debitos.strip() else "")
                    texto_central_norma = central_norma + (f" - {desc_central_norma.strip()}" if central_norma == "Não" and desc_central_norma.strip() else "")
                    texto_negocios = indica_negocios + (f" - {desc_negocios.strip()}" if indica_negocios == "Sim" and desc_negocios.strip() else "")
                    texto_satisfacao = cliente_satisfeito + (f", {desc_satisfacao.strip()}" if desc_satisfacao.strip() else "")

                    texto_final = f"""Contato: {contato} Sobrenome ou departamento: {departamento} Telefone: {telefone}
Equipamentos de acordo com o contrato vigente? {texto_eq_contrato} Representante 2 está correto? {texto_rep2} Possui programação cadastrada? {texto_freq} Consumo mensal atual de acordo com o contrato vigente? Consumo previsto: {consumo_previsto} kg | Consumo médio: {consumo_real} kg Laudo ART emitido? {linha_art} Central atende as normas? {texto_central_norma}
Indicação de novos negócios do cliente: {texto_negocios} Cliente possui débitos? {texto_debitos} Cliente está satisfeito com o atendimento da Consigaz? {texto_satisfacao}
Obs.: {observacoes}"""

                    st.success("✅ Texto para o Sistema gerado com sucesso!")
                    st.text_area("Texto Gerado:", value=texto_final, height=250, key=f"txt_area_transf_{rc}")
                    botao_copiar_customizado(texto_final, "transf_txt")

            with col_b2:
                if st.button("📄 Gerar PDF do Relatório Fotográfico"):
                    if not cod_cliente or not nome_cliente:
                        st.error("⚠️ Preencha o Código do Cliente e Nome/Razão Social.")
                    else:
                        pdf = RelatorioPDF(cod_cliente=cod_cliente, nome_cliente=nome_cliente, logo_path=LOGO_PATH)
                        pdf.add_page()
                        pdf.set_font("Arial", "", 12)
                        pdf.cell(0, 10, f"Contato: {contato} | Telefone: {telefone}", ln=True)
                        pdf.cell(0, 10, f"Departamento: {departamento}", ln=True)
                        
                        cod_limpo = re.sub(r'\D', '', str(cod_cliente))
                        data_str = datetime.now().strftime("%d-%m-%y")
                        nome_arquivo_pdf = f"relatorio_{cod_limpo}_{data_str}.pdf"
                        
                        pdf_output = pdf.output(dest='S').encode('latin-1', errors='replace')
                        st.download_button(
                            label="💾 Baixar PDF Gerado",
                            data=pdf_output,
                            file_name=nome_arquivo_pdf,
                            mime="application/pdf"
                        )

        # -------------------------------------------------------------
        # 2. ELABORAÇÃO DE CONTRATO
        # -------------------------------------------------------------
        elif menu_tratativa == "📝 Elaboração de Contrato":
            rcc = st.session_state.reset_counter
            cabecalho_pagina("Elaboração de Contrato", "Formulário completo para geração do padrão de solicitação de contrato.")
            
            if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_elab_{rcc}"):
                st.session_state.reset_counter += 1
                st.rerun()

            tipo_fluxo = st.radio("Objetivo da solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, key=f"fluxo_c_{rcc}")
            st.divider()

            st.subheader("1. Motivo")
            motivo_solicitacao = st.text_input("Motivo da solicitação", key=f"motivo_{rcc}")
            st.divider()

            st.subheader("2. Dados do Cliente")
            col_cli1, col_cli2, col_cli3 = st.columns(3)
            with col_cli1: contato_contrato = st.text_input("Contato", key=f"contato_c_{rcc}")
            with col_cli2: telefone_contrato = st.text_input("Telefone", key=f"tel_c_{rcc}")
            with col_cli3: email_contrato = st.text_input("E-mail", key=f"email_c_{rcc}")
            st.divider()

            st.subheader("3. Solicitação")
            tipo_contrato = st.radio("Tipo", ["Contrato", "Aditamento", "Distrato"], horizontal=True, key=f"tp_cont_{rcc}")
            st.divider()

            st.subheader("4. Dados do Contrato")
            col_con1, col_con2 = st.columns(2)
            cnpj_campo_val, ie_campo_val = "", ""
            status_cnpj_txt, razao_social_txt = "", ""
            email_novo_prop = "n/a"

            with col_con1:
                endereco_padrao = st.text_input("Endereço padrão ou entrega?", key=f"end_padrao_{rcc}")
                mesmo_prop_opt = st.radio("Mesmo proprietário?", ["Sim", "Não"], horizontal=True, key=f"mesmo_prop_{rcc}")
                if mesmo_prop_opt == "Não":
                    email_novo_prop = st.text_input("E-mail do novo proprietário", key=f"email_novo_{rcc}")

                mesmo_cnpj_opt = st.radio("Mesmo CNPJ?", ["Sim", "Não"], horizontal=True, key=f"mesmo_cnpj_{rcc}")
                if mesmo_cnpj_opt == "Sim":
                    cnpj_campo_val = st.text_input("CNPJ", key=f"cnpj_val_{rcc}")
                    ie_campo_val = st.text_input("I.E.", key=f"ie_val_{rcc}")
                else:
                    cnpj_campo_val = st.text_input("Novo CNPJ", key=f"novo_cnpj_val_{rcc}")
                    ie_campo_val = st.text_input("Nova I.E.", key=f"nova_ie_val_{rcc}")

                if len("".join(filter(str.isdigit, str(cnpj_campo_val)))) == 14:
                    dados_api = consultar_cnpj_api(cnpj_campo_val)
                    if dados_api:
                        razao_social_txt = dados_api.get("razao_social", "Não encontrada")
                        situacao_cad = dados_api.get("situacao_cadastral", "")
                        status_cnpj_txt = "Ativo" if situacao_cad == 2 or str(situacao_cad).upper() == "ATIVA" else f"Inativa ({situacao_cad})"
                        st.markdown(f"✅ **Razão Social:** {razao_social_txt}")
                        st.markdown(f"🟢 **Status CNPJ:** {status_cnpj_txt}")

            with col_con2:
                cond_pagamento = st.text_input("Condição de pagamento", key=f"cond_pag_{rcc}")
                vigencia = st.text_input("Vigência", key=f"vigencia_{rcc}")
                qtd_entregas_c = st.number_input("Quantidade de endereços/centrais", min_value=1, value=1, step=1, key=f"qtd_ent_c_{rcc}")
                
                equipamentos_contrato = ""
                eq_dict_c = {}
                if qtd_entregas_c == 1:
                    equipamentos_contrato = st.text_input("Equipamentos", key=f"eq_contrato_c_{rcc}")
                else:
                    for i in range(1, int(qtd_entregas_c) + 1):
                        eq_dict_c[i] = st.text_input(f"Equipamentos - [Entrega {i}]", key=f"eq_ent_{i}_{rcc}")

            st.divider()
            st.subheader("5. Comodato / Fornecimento")
            tipo_fornecimento = st.radio("Tipo de Fornecimento", ["Granel", "Cilindro"], horizontal=True, key=f"tp_forn_{rcc}")
            
            preco_granel, consumo_granel = "", ""
            p13_val, p20_val, p45_val = "", "", ""
            p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
            consumo_cilindro_total = 0

            if tipo_fornecimento == "Granel":
                col_g1, col_g2 = st.columns(2)
                with col_g1: preco_granel = st.text_input("Preço Granel", key=f"preco_granel_{rcc}")
                with col_g2: consumo_granel = st.text_input("Consumo mensal previsto (kgs)", key=f"cons_granel_{rcc}")
            else:
                col_cp1, col_cp2, col_cp3 = st.columns(3)
                with col_cp1: p13_val = st.text_input("Preço P13 (/und)", key=f"p13_v_{rcc}")
                with col_cp2: p20_val = st.text_input("Preço P20 (/und)", key=f"p20_v_{rcc}")
                with col_cp3: p45_val = st.text_input("Preço P45 (/und)", key=f"p45_v_{rcc}")

                col_cc1, col_cc2, col_cc3 = st.columns(3)
                with col_cc1: p13_qtd = st.number_input("Qtd Cilindros P13", min_value=0, value=0, step=1, key=f"p13_q_{rcc}")
                with col_cc2: p20_qtd = st.number_input("Qtd Cilindros P20", min_value=0, value=0, step=1, key=f"p20_q_{rcc}")
                with col_cc3: p45_qtd = st.number_input("Qtd Cilindros P45", min_value=0, value=0, step=1, key=f"p45_q_{rcc}")
                consumo_cilindro_total = (p13_qtd * 13) + (p20_qtd * 20) + (p45_qtd * 45)

            st.divider()
            st.subheader("6. Financeiro")
            col_fin1, col_fin2 = st.columns(2)
            with col_fin1:
                possui_debito_fin = st.radio("Cliente possui débitos?", ["Sim", "Não"], horizontal=True, key=f"possui_deb_{rcc}")
                resp_pendentes = "n/a"
                if possui_debito_fin == "Sim":
                    resp_pendentes = st.text_input("Responsável pelas NF's pendentes?", key=f"resp_pend_{rcc}")

            responsaveis_dados = []
            nome_testemunha, email_testemunha = "", ""

            if tipo_fluxo == "Enviar para Assinatura":
                st.markdown("---")
                st.subheader("Dados de Assinatura e Testemunhas")
                col_t1, col_t2 = st.columns(2)
                with col_t1: nome_testemunha = st.text_input("Nome da Testemunha", key=f"nome_test_{rcc}")
                with col_t2: email_testemunha = st.text_input("E-mail da Testemunha", key=f"email_test_{rcc}")

                qtd_responsaveis = st.selectbox("Quantidade de Responsáveis", [1, 2, 3, 4], index=0, key=f"qtd_resp_{rcc}")
                for i in range(1, qtd_responsaveis + 1):
                    col_r1, col_r2 = st.columns(2)
                    with col_r1: n_r = st.text_input(f"Nome Responsável {i}", key=f"nome_resp_{i}_{rcc}")
                    with col_r2: e_r = st.text_input(f"E-mail Responsável {i}", key=f"email_resp_{i}_{rcc}")
                    responsaveis_dados.append({"nome": n_r, "email": e_r})

            st.divider()
            st.subheader("7. Condomínio CONTA SIM")
            conta_sim = st.radio("Condomínio CONTA SIM?", ["Sim", "Não"], horizontal=True, key=f"conta_sim_{rcc}")
            num_unidades, qtd_torres, qtd_blocos, preco_religue, preco_servico = "", "", "", "", ""

            if conta_sim == "Sim":
                col_cs1, col_cs2, col_cs3 = st.columns(3)
                with col_cs1:
                    num_unidades = st.text_input("N° Unidades Autônomas", key=f"num_unid_{rcc}")
                    qtd_torres = st.text_input("Qtd Torres", key=f"qtd_torres_{rcc}")
                with col_cs2:
                    qtd_blocos = st.text_input("Qtd Blocos", key=f"qtd_blocos_{rcc}")
                    preco_religue = st.text_input("Preço de Religue", key=f"preco_rel_{rcc}")
                with col_cs3:
                    preco_servico = st.text_input("Preço de Serviço", key=f"preco_serv_{rcc}")

            observacoes_contrato = st.text_area("Observações Gerais", key=f"obs_c_{rcc}")
            st.divider()

            if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
                sel_granel = "[x]" if tipo_fornecimento == "Granel" else "[ ]"
                sel_cilindro = "[x]" if tipo_fornecimento == "Cilindro" else "[ ]"

                texto_padrao_contrato = f"Motivo da solicitação: {motivo_solicitacao}"
                if tipo_fluxo == "Gerar Minuta":
                    texto_padrao_contrato += "\n\n** FAVOR GERAR MINUTA EM PDF PARA ENVIO AO CLIENTE **"

                texto_padrao_contrato += f"\nContato: {contato_contrato} Telefone: {telefone_contrato} E-mail: {email_contrato}\nContrato / Aditamento / Distrato: {tipo_contrato}\nMesmo proprietário?: {mesmo_prop_opt}\nE-mail do novo proprietário: {email_novo_prop}\nMesmo CNPJ?: {mesmo_cnpj_opt}"

                if mesmo_cnpj_opt == "Sim":
                    texto_padrao_contrato += f"\nCNPJ: {cnpj_campo_val} I.E.: {ie_campo_val}"
                else:
                    texto_padrao_contrato += f"\nNovo CNPJ: {cnpj_campo_val} Nova I.E.: {ie_campo_val}"

                if razao_social_txt: texto_padrao_contrato += f"\nRazão Social (Consultada): {razao_social_txt}"
                if status_cnpj_txt: texto_padrao_contrato += f"\nStatus CNPJ: {status_cnpj_txt}"

                texto_padrao_contrato += f"\nEndereço padrão ou entrega?: {endereco_padrao}\nTipo de Fornecimento: {sel_granel} Granel  {sel_cilindro} Cilindro"

                if tipo_fornecimento == "Granel":
                    texto_padrao_contrato += f"\nPreço Granel: {preco_granel} /kg\nConsumo mensal previsto: {consumo_granel}"
                else:
                    partes_cil = []
                    if p13_val.strip(): partes_cil.append(f"[P13 = {p13_val.strip()} / und]")
                    if p20_val.strip(): partes_cil.append(f"[P20 = {p20_val.strip()} / und]")
                    if p45_val.strip(): partes_cil.append(f"[P45 = {p45_val.strip()} / und]")
                    texto_padrao_contrato += f"\nPreço Cilindro: {' '.join(partes_cil)}\nConsumo mensal previsto: {consumo_cilindro_total} KGs"

                texto_padrao_contrato += f"\nCondição de pagamento: {cond_pagamento}\nVigência: {vigencia}"

                if qtd_entregas_c == 1:
                    texto_padrao_contrato += f"\nEquipamentos: {equipamentos_contrato}"
                else:
                    eq_linhas = [f"[Entrega {i}] {eq_dict_c[i].strip()}" for i in range(1, int(qtd_entregas_c) + 1) if eq_dict_c[i].strip()]
                    texto_padrao_contrato += "\nEquipamentos:\n" + "\n".join(eq_linhas)

                texto_padrao_contrato += f"\nCliente possui débitos?: {possui_debito_fin}\nResponsável pelas NF's pendentes: {resp_pendentes}"

                if tipo_fluxo == "Enviar para Assinatura":
                    texto_padrao_contrato += f"\nNome da Testemunha: {nome_testemunha}\nE-mail da Testemunha: {email_testemunha}"
                    for idx, resp in enumerate(responsaveis_dados, 1):
                        texto_padrao_contrato += f"\nNome do Responsável {idx}: {resp['nome']}\nE-mail do Responsável {idx}: {resp['email']}"

                texto_padrao_contrato += f"\nCondomínio CONTA SIM?: {conta_sim}"
                if conta_sim == "Sim":
                    texto_padrao_contrato += f"\nN° Unid autônomas: {num_unidades}\nQtd Torres: {qtd_torres}\nQtd Blocos: {qtd_blocos}\nPreço Religue: {preco_religue}\nPreço Serviço: {preco_servico}"

                texto_padrao_contrato += f"\nObs.: {observacoes_contrato}"

                st.success("✅ Texto gerado com sucesso!")
                st.text_area("Texto Gerado:", value=texto_padrao_contrato, height=300, key=f"txt_area_contrato_{rcc}")
                botao_copiar_customizado(texto_padrao_contrato, "contrato_txt")

        # -------------------------------------------------------------
        # 3. APROVAÇÃO DE CONTRATO
        # -------------------------------------------------------------
        elif menu_tratativa == "📋 Aprovação de Contrato":
            rcap = st.session_state.reset_counter
            cabecalho_pagina("Aprovação de Contrato", "Formulário de solicitação de aprovação de contrato.")

            if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_aprov_{rcap}"):
                st.session_state.reset_counter += 1
                st.rerun()

            st.divider()
            st.subheader("1. Motivo e Dados Principais")
            motivo_reg = st.text_input("Motivo da regularização *", key=f"ap_motivo_{rcap}")
            
            c_ap1, c_ap2, c_ap3 = st.columns(3)
            with c_ap1: contato_ap = st.text_input("Contato *", key=f"ap_cont_{rcap}")
            with c_ap2: telefone_ap = st.text_input("Telefone *", key=f"ap_tel_{rcap}")
            with c_ap3: email_ap = st.text_input("E-mail *", key=f"ap_email_{rcap}")

            c_ap4, c_ap5, c_ap6 = st.columns(3)
            with c_ap4: atualizar_email = st.radio("Atualizar E-mail?", ["Sim", "Não"], horizontal=True, key=f"ap_atu_email_{rcap}")
            with c_ap5: contrato_adit = st.radio("Contrato / Aditamento", ["Contrato", "Aditamento"], horizontal=True, key=f"ap_tp_cont_{rcap}")
            with c_ap6: vigencia_ap = st.text_input("Vigência", key=f"ap_vig_{rcap}")

            qtd_entregas_ap = st.number_input("Quantidade de endereços/centrais", min_value=1, value=1, step=1, key=f"qtd_ent_ap_{rcap}")
            equipamentos_ap = ""
            eq_dict_ap = {}
            if qtd_entregas_ap == 1:
                equipamentos_ap = st.text_input("Equipamentos", key=f"ap_eq_{rcap}")
            else:
                for i in range(1, int(qtd_entregas_ap) + 1):
                    eq_dict_ap[i] = st.text_input(f"Equipamentos - [Entrega {i}]", key=f"ap_eq_ent_{i}_{rcap}")

            especificidade_ap = st.text_input("Existe especificidade sobre a solicitação?", key=f"ap_esp_{rcap}")

            st.divider()
            st.subheader("2. Redimensionamento")
            redim = st.radio("Redimensionamento:", ["Sim", "Não"], horizontal=True, key=f"ap_redim_{rcap}")
            comodato_de, comodato_para, inc_tanques, env_pecas = "", "", "Não", "Não"
            if redim == "Sim":
                c_p1, c_p2 = st.columns(2)
                with c_p1: comodato_de = st.text_input("Comodato passou de:", key=f"ap_com_de_{rcap}")
                with c_p2: comodato_para = st.text_input("Para:", key=f"ap_com_para_{rcap}")
                
                c_p3, c_p4 = st.columns(2)
                with c_p3: inc_tanques = st.radio("Inclusão de tanques?", ["Sim", "Não"], horizontal=True, key=f"ap_inc_tanq_{rcap}")
                with c_p4: env_pecas = st.radio("Necessário lista de peças?", ["Sim", "Não"], horizontal=True, key=f"ap_env_pec_{rcap}")

            st.divider()
            st.subheader("3. Condomínio Conta Sim & Portaria")
            implantacao_csim = st.radio("Implantação de conta sim:", ["Sim", "Não"], horizontal=True, key=f"ap_csim_{rcap}")
            env_pecas_ficha, env_ficha_cliente, tp_portaria, contato_resp_port, part_local, contato_sindico = "Não", "Não", "", "", "", ""
            if implantacao_csim == "Sim":
                c_cs1, c_cs2 = st.columns(2)
                with c_cs1: env_pecas_ficha = st.radio("Foi enviado lista de peças?", ["Sim", "Não"], horizontal=True, key=f"ap_csim_pec_{rcap}")
                with c_cs2: env_ficha_cliente = st.radio("Foi enviado ficha de clientes?", ["Sim", "Não"], horizontal=True, key=f"ap_csim_ficha_{rcap}")
                tp_portaria = st.text_input("Tipo de portaria", key=f"ap_tp_port_{rcap}")
                contato_resp_port = st.text_input("Contato responsável (portaria remota)", key=f"ap_cont_resp_{rcap}")
                part_local = st.text_input("Particularidades do local", key=f"ap_part_local_{rcap}")
                contato_sindico = st.text_input("Contato atualizado do síndico", key=f"ap_cont_sind_{rcap}")

            st.divider()
            st.subheader("4. Alteração de CNPJ & Títulos em Aberto")
            alt_cnpj = st.radio("Alteração de CNPJ ou razão social?", ["Sim", "Não"], horizontal=True, key=f"ap_alt_cnpj_{rcap}")
            mesmo_prop_opt = st.radio("Se trata do mesmo proprietário:", ["Sim", "Não"], horizontal=True, key=f"ap_mesmo_prop_{rcap}")
            possui_titulos_aberto = st.radio("Possui títulos em aberto?", ["Sim", "Não"], horizontal=True, key=f"ap_tit_aberto_{rcap}")
            neg_tit_input = st.text_input("Negociação dos títulos em aberto:", key=f"ap_neg_tit_{rcap}") if possui_titulos_aberto == "Sim" else "n/a"

            st.divider()
            st.subheader("5. Redução de Vigência & Projeto Padrão")
            red_vig = st.radio("Redução de vigência?", ["Sim", "Não"], horizontal=True, key=f"ap_red_vig_{rcap}")
            motivo_red_vig = st.text_input("Motivo da redução de vigência:", key=f"ap_mot_red_{rcap}") if red_vig == "Sim" else ""

            col_proj1, col_proj2 = st.columns([3, 1])
            with col_proj1: projeto_num = st.text_input("Projeto (Número completo) *", key=f"ap_proj_{rcap}")
            with col_proj2:
                st.write(""); st.write("")
                is_cilindros = st.checkbox("Cilindros", key=f"ap_cil_{rcap}")

            st.divider()
            if st.button("📝 Gerar Texto de Aprovação de Contrato", type="primary"):
                if not is_cilindros and not projeto_num.strip():
                    st.error("⚠️ O campo 'Projeto' é obrigatório, a menos que a opção 'Cilindros' esteja marcada.")
                else:
                    proj_final = "N/A" if is_cilindros else projeto_num.strip()
                    
                    if qtd_entregas_ap == 1:
                        eq_ap_texto = equipamentos_ap
                    else:
                        eq_ap_linhas = [f"[Entrega {i}] {eq_dict_ap[i].strip()}" for i in range(1, int(qtd_entregas_ap) + 1) if eq_dict_ap[i].strip()]
                        eq_ap_texto = "\n" + "\n".join(eq_ap_linhas)

                    conta_sim_bloco = f"Implantação de conta sim: [ {'x' if implantacao_csim == 'Sim' else ' '} ] sim [ {'x' if implantacao_csim == 'Não' else ' '} ] não"
                    if implantacao_csim == "Sim":
                        conta_sim_bloco += f"\nFoi enviado lista de peças? [ {'x' if env_pecas_ficha == 'Sim' else ' '} ] sim [ {'x' if env_pecas_ficha == 'Não' else ' '} ] não\nFoi enviado ficha de clientes? [ {'x' if env_ficha_cliente == 'Sim' else ' '} ] sim [ {'x' if env_ficha_cliente == 'Não' else ' '} ] não\nTipo de portaria: {tp_portaria}\nContato do responsável: {contato_resp_port}\nParticularidades: {part_local}\nContato síndico: {contato_sindico}"

                    texto_aprovacao = f"""Motivo da regularização: {motivo_reg}
Contato: {contato_ap} Telefone: {telefone_ap} E-mail: {email_ap}
Atualizar E-mail? {atualizar_email} Contrato / Aditamento: {contrato_adit} Vigência: {vigencia_ap} Equipamentos: {eq_ap_texto}
Existe especificidade sobre a solicitação: {especificidade_ap}
Redimensionamento: [ {'x' if redim == 'Sim' else ' '} ] sim [ {'x' if redim == 'Não' else ' '} ] não Projeto: {proj_final} Comodato passou de: {comodato_de} Para: {comodato_para}
Inclusão de tanques? [ {'x' if inc_tanques == 'Sim' else ' '} ] sim [ {'x' if inc_tanques == 'Não' else ' '} ] não
Necessário lista de peças? [ {'x' if env_pecas == 'Sim' else ' '} ] sim [ {'x' if env_pecas == 'Não' else ' '} ] não
{conta_sim_bloco}
Alteração de CNPJ ou razão social? [ {'x' if alt_cnpj == 'Sim' else ' '} ] sim [ {'x' if alt_cnpj == 'Não' else ' '} ] não
Se trata do mesmo proprietário: ( {'X' if mesmo_prop_opt == 'Sim' else ' '} ) SIM ( {'X' if mesmo_prop_opt == 'Não' else ' '} ) NÃO
Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto: {neg_tit_input}
Redução de vigência? [ {'x' if red_vig == 'Sim' else ' '} ] sim [ {'x' if red_vig == 'Não' else ' '} ] não (Se sim, descreva o motivo): {motivo_red_vig}"""

                    st.success("✅ Texto de Aprovação gerado com sucesso!")
                    st.text_area("Texto Gerado:", value=texto_aprovacao, height=350, key=f"txt_area_aprov_{rcap}")
                    botao_copiar_customizado(texto_aprovacao, "aprovacao_txt")

        # -------------------------------------------------------------
        # 4. ANIVERSÁRIO DE CONTRATO
        # -------------------------------------------------------------
        elif menu_tratativa == "🎂 Aniversário de Contrato":
            rca = st.session_state.reset_counter
            cabecalho_pagina("Aniversário de Contrato", "Calculadora de reajuste por IPCA acumulado de 12M e geração de formulário.")

            if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_aniv_{rca}"):
                st.session_state.reset_counter += 1
                st.rerun()

            st.divider()
            ipca_api, ipca_periodo = obter_ipca_acumulado_12m()
            if ipca_api is not None:
                ipca_vigente = ipca_api
                st.success(f"📊 **IPCA Acumulado de 12 meses (IBGE, referência {ipca_periodo}):** `{ipca_vigente:.2f}%`")
            else:
                ipca_vigente = st.number_input("IPCA acumulado de 12 meses (%) - informado manualmente", min_value=0.0, value=4.58, step=0.01, format="%.2f", key=f"ipca_manual_{rca}")

            col_an1, col_an2 = st.columns(2)
            with col_an1: preco_anterior_input = st.text_input("Preço Anterior (R$)", value="7,7400", key=f"preco_ant_{rca}")
            with col_an2: clausula_contrato = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, key=f"clausula_{rca}")

            st.divider()
            p_aniv_str = "0,0000"
            try:
                val_limpo = preco_anterior_input.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
                p_ant = float(val_limpo)
                p_aniv = p_ant * (1 + (ipca_vigente / 100.0))
                p_aniv_str = f"{p_aniv:.4f}".replace(".", ",")
            except ValueError:
                pass

            if st.button("📝 Gerar Texto de Aniversário de Contrato", type="primary"):
                if clausula_contrato == "Não":
                    st.warning("⚠️ **Atenção:** O cliente selecionado não possui cláusula de reajuste em contrato.")

                clausula_txt = "\n\nCliente possui cláusula em contrato." if clausula_contrato == "Sim" else ""
                
                p_ant_fmt = preco_anterior_input.strip()
                if not p_ant_fmt.startswith("R$"):
                    p_ant_fmt = f"R$ {p_ant_fmt}"

                texto_aniversario = (
                    f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%.{clausula_txt}\n\n"
                    f"Preço anterior: {p_ant_fmt}\n"
                    f"Preço Aniversário: R$ {p_aniv_str}"
                )

                st.success("✅ Texto gerado com sucesso!")
                
                # ADVERTÊNCIA E CAMPO ABERTO/EDITÁVEL PARA COPIAR O VALOR NOVO
                st.warning("⚠️ **ATENÇÃO:** Utilize o preço novo abaixo para a abertura da CI!")
                col_v1, col_v2 = st.columns([1, 2])
                with col_v1:
                    st.text_input("Preço Novo para Abertura da CI:", value=f"R$ {p_aniv_str}", disabled=False, key=f"valor_novo_ci_{rca}")
                with col_v2:
                    st.write("")
                    st.write("")
                    botao_copiar_customizado(f"R$ {p_aniv_str}", "btn_copy_val_novo", label_btn="💵 Copiar Valor Novo")

                st.text_area("Texto Gerado:", value=texto_aniversario, height=180, key=f"txt_area_aniv_{rca}")
                botao_copiar_customizado(texto_aniversario, "aniversario_txt")

            st.divider()
            st.subheader("Tratativa com C.I.")
            ci_input = st.text_input("Número da C.I. (9 ou 11 dígitos)", placeholder="Ex: 588358982 ou 588.358.982", key=f"ci_num_{rca}")

            if st.button("📝 Gerar Texto Final com C.I.", type="primary"):
                clausula_txt = "\n\nCliente possui cláusula em contrato." if clausula_contrato == "Sim" else ""
                
                p_ant_fmt = preco_anterior_input.strip()
                if not p_ant_fmt.startswith("R$"):
                    p_ant_fmt = f"R$ {p_ant_fmt}"

                ci_fmt = formatar_ci_num(ci_input)

                texto_ci = (
                    f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%.{clausula_txt}\n\n"
                    f"Preço anterior: {p_ant_fmt}\n"
                    f"Preço Aniversário: R$ {p_aniv_str}\n\n"
                    f"CI.: {ci_fmt} Preço Comercial"
                )

                st.success("✅ Texto com C.I. gerado com sucesso!")
                st.text_area("Texto com C.I.:", value=texto_ci, height=220, key=f"txt_area_ci_{rca}")
                botao_copiar_customizado(texto_ci, "ci_txt")


# =====================================================================
# ABA 2: AGENDA DE OCORRÊNCIAS
# =====================================================================
with aba_agenda:
    cabecalho_pagina("Agenda de Ocorrências & Visitas", "Painel de organização de agenda ordenado por prazo de atendimento.")
    
    arquivo_excel = st.file_uploader("Faça o upload do relatório Excel (Pós-Vendas) 📂", type=["xlsx", "xls"])
    
    if arquivo_excel is not None:
        try:
            df = pd.read_excel(arquivo_excel, header=11)
            df = df.dropna(subset=[COL_OCORRENCIA])
            
            df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
            df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
            df_pendentes = df_pendentes[~df_pendentes[COL_OCORRENCIA].isin(st.session_state.tratadas_manualmente)]
            
            df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
            df_pendentes['Abertura_DT'] = pd.to_datetime(df_pendentes[COL_ABERTURA], format="%d/%m/%Y %H:%M", errors='coerce')
            df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
            
            df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
            df_pendentes[COL_SUB_CLASSIF] = df_pendentes[COL_SUB_CLASSIF].fillna("-").astype(str)
            
            hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            df_pendentes['Dias Úteis Restantes'] = df_pendentes['Prazo_DT'].apply(lambda x: calcular_dias_uteis(hoje, x))
            
            df_pendentes['Status Geral'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_geral)
            df_pendentes['Status Comodato'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_comodato)
            
            df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
            
            st.divider()

            col_menu_agenda, col_conteudo_agenda = st.columns([1, 4])
            
            with col_menu_agenda:
                st.markdown("### 📌 Filtros")
                menu_agenda = st.radio(
                    "Selecione a visão:", 
                    [
                        "Todas as Ocorrências",
                        "Comodato Inativo",
                        "Ocorrências por Cidade"
                    ],
                    label_visibility="collapsed"
                )
            
            with col_conteudo_agenda:

                # ----- 1. TODAS AS OCORRÊNCIAS -----
                if menu_agenda == "Todas as Ocorrências":
                    st.subheader("1. Visitas Pendentes na Agenda")
                    
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        cidades_unicas = sorted(list(df_pendentes['Cidade'].unique()))
                        cidades_selecionadas = st.multiselect("Filtrar por Cidade(s):", cidades_unicas, default=[])
                    with col_f2:
                        sub_class_unicas = sorted(list(df_pendentes[COL_SUB_CLASSIF].unique()))
                        sub_class_selecionadas = st.multiselect("Filtrar por Sub-Classificação:", sub_class_unicas, default=[])
                    
                    df_base_filtrado = df_pendentes.copy()
                    if cidades_selecionadas: df_base_filtrado = df_base_filtrado[df_base_filtrado['Cidade'].isin(cidades_selecionadas)]
                    if sub_class_selecionadas: df_base_filtrado = df_base_filtrado[df_base_filtrado[COL_SUB_CLASSIF].isin(sub_class_selecionadas)]
                    
                    # MÉTRICAS
                    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
                    col_m1.metric("Total (Filtros)", len(df_base_filtrado))
                    col_m2.metric("Vencidas", len(df_base_filtrado[df_base_filtrado['Dias Úteis Restantes'] < 0]))
                    col_m3.metric("Vence Hoje", len(df_base_filtrado[df_base_filtrado['Dias Úteis Restantes'] == 0]))
                    col_m4.metric("Vence Amanhã", len(df_base_filtrado[df_base_filtrado['Dias Úteis Restantes'] == 1]))
                    col_m5.metric("Na Semana", len(df_base_filtrado[df_base_filtrado['Dias Úteis Restantes'] <= 5]))
                    
                    st.write("---")
                    
                    # FILTRO RÁPIDO (BOTÕES HORIZONTAIS)
                    st.markdown("**🔍 Filtrar Tabela por Categoria:**")
                    filtro_status = st.radio(
                        "Filtro Status:",
                        ["Todas", "Vencidas", "Vence Hoje", "Vence Amanhã", "Vencem na Semana"],
                        horizontal=True,
                        label_visibility="collapsed"
                    )
                    
                    df_filtrado = df_base_filtrado.copy()
                    if filtro_status == "Vencidas":
                        df_filtrado = df_filtrado[df_filtrado['Dias Úteis Restantes'] < 0]
                    elif filtro_status == "Vence Hoje":
                        df_filtrado = df_filtrado[df_filtrado['Dias Úteis Restantes'] == 0]
                    elif filtro_status == "Vence Amanhã":
                        df_filtrado = df_filtrado[df_filtrado['Dias Úteis Restantes'] == 1]
                    elif filtro_status == "Vencem na Semana":
                        df_filtrado = df_filtrado[df_filtrado['Dias Úteis Restantes'] <= 5]

                    df_filtrado['Data Atendimento'] = df_filtrado['Prazo_DT'].dt.strftime('%d/%m/%Y')
                    
                    st.write("")
                    if not df_filtrado.empty:
                        df_exibicao = df_filtrado[['Status Geral', 'Dias Úteis Restantes', COL_OCORRENCIA, COL_CLIENTE, 'Cidade', COL_SUB_CLASSIF, 'Data Atendimento']].copy()
                        df_exibicao[COL_OCORRENCIA] = df_exibicao[COL_OCORRENCIA].astype(str)
                        
                        edited_df = st.data_editor(
                            df_exibicao.assign(Tratar=False),
                            column_config={"Tratar": st.column_config.CheckboxColumn("✅ Marcar Tratada?", required=True)},
                            hide_index=True, use_container_width=True, key="editor_geral"
                        )
                        
                        ocorrencias_para_tratar = edited_df[edited_df["Tratar"] == True][COL_OCORRENCIA].tolist()
                        if ocorrencias_para_tratar:
                            if st.button("🔒 Confirmar e Remover do Painel", type="primary"):
                                for oc in ocorrencias_para_tratar: st.session_state.tratadas_manualmente.add(int(oc))
                                st.success("✅ Ocorrências tratadas removidas!")
                                st.rerun()
                    else:
                        st.success("✅ Nenhuma ocorrência para este filtro no momento.")

                # ----- 2. COMODATO INATIVO -----
                elif menu_agenda == "Comodato Inativo":
                    st.subheader("2. Relatório Específico: Comodato Inativo")
                    df_comodato = df_pendentes[df_pendentes[COL_SUB_CLASSIF].str.contains("Comodato Inativo", case=False, na=False)].copy()
                    if df_comodato.empty:
                        st.info("Nenhuma ocorrência de Comodato Inativo encontrada.")
                    else:
                        df_comodato['Data Atendimento'] = df_comodato['Prazo_DT'].dt.strftime('%d/%m/%Y')
                        df_comodato_exibicao = df_comodato[['Status Comodato', 'Dias Úteis Restantes', COL_OCORRENCIA, COL_CLIENTE, 'Cidade', COL_SUB_CLASSIF, 'Data Atendimento']].copy()
                        df_comodato_exibicao[COL_OCORRENCIA] = df_comodato_exibicao[COL_OCORRENCIA].astype(str)
                        
                        st.dataframe(df_comodato_exibicao, hide_index=True, use_container_width=True)

                # ----- 3. OCORRÊNCIAS POR CIDADE -----
                elif menu_agenda == "Ocorrências por Cidade":
                    st.subheader("3. Ocorrências por Cidades")
                    
                    df_cid = df_pendentes['Cidade'].value_counts().reset_index()
                    df_cid.columns = ["Cidade", "Quantidade"]
                    
                    # 1º TABELA DE DADOS 
                    st.markdown("**Tabela por Cidade:**")
                    st.dataframe(df_cid, hide_index=True, use_container_width=True)

                    st.write("---")
                    
                    # 2º GRÁFICO (Sem permissão para Zoom / Scroll estático configurado no Altair)
                    st.markdown("**Distribuição Visual:**")
                    
                    chart = alt.Chart(df_cid).mark_bar(color="#0055A5").encode(
                        x=alt.X('Cidade', sort='-y', title='Cidade'),
                        y=alt.Y('Quantidade', title='Quantidade de Ocorrências'),
                        tooltip=['Cidade', 'Quantidade']
                    ).properties(height=350)
                    
                    st.altair_chart(chart, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao processar arquivo Excel: {e}")

# =====================================================================
# ABA 3: BLOCO DE NOTAS PESSOAL (PERSISTÊNCIA SUPABASE)
# =====================================================================
with aba_notas:
    col_menu_notas, col_conteudo_notas = st.columns([1, 4])
    usuario_atual = st.session_state.usuario_atual
    notas_usuario = carregar_banco_notas(usuario_atual)

    with col_menu_notas:
        st.markdown("### 📓 Minhas Notas")
        if st.button("➕ Nova Nota", use_container_width=True):
            st.session_state.nota_selecionada_id = None
            st.rerun()
            
        st.divider()
        if not notas_usuario:
            st.caption("Nenhuma nota cadastrada.")
        else:
            for n_id, n_data in notas_usuario.items():
                if st.button(n_data.get("titulo", "Sem Título"), key=f"btn_n_{n_id}", use_container_width=True):
                    st.session_state.nota_selecionada_id = n_id
                    st.rerun()

    with col_conteudo_notas:
        cabecalho_pagina("Bloco de Notas Pessoal", "Anotações vinculadas à sua conta e salvas na nuvem.")
        id_atual = st.session_state.nota_selecionada_id
        
        t_val = notas_usuario[id_atual]["titulo"] if id_atual in notas_usuario else ""
        c_val = notas_usuario[id_atual]["cliente"] if id_atual in notas_usuario else ""
        txt_val = notas_usuario[id_atual]["texto"] if id_atual in notas_usuario else ""

        with st.form("form_nota"):
            c1, c2 = st.columns(2)
            with c1: tit = st.text_input("Título", value=t_val)
            with c2: cli = st.text_input("Cliente", value=c_val)
            txt = st.text_area("Anotação", value=txt_val, height=200)
            
            b1, b2, _ = st.columns([1, 1, 4])
            with b1: btn_s = st.form_submit_button("💾 Salvar na Nuvem", type="primary")
            with b2: btn_d = st.form_submit_button("🗑️ Apagar") if id_atual else False

            if btn_s and tit:
                target_id = id_atual if id_atual else str(uuid.uuid4())
                if salvar_nota(target_id, usuario_atual, tit, cli, txt):
                    st.session_state.nota_selecionada_id = target_id
                    st.success("✅ Salvo com sucesso no banco de dados!")
                    st.rerun()
            if btn_d and id_atual:
                if apagar_nota(id_atual):
                    st.session_state.nota_selecionada_id = None
                    st.rerun()

# =====================================================================
# ABA 4: PAINEL ADMIN (PERSISTÊNCIA SUPABASE)
# =====================================================================
if aba_admin is not None:
    with aba_admin:
        cabecalho_pagina("Painel de Administração de Usuários", "Cadastro de colaboradores, níveis de permissão e redefinição de senhas gravadas na nuvem.")
        
        banco_usuarios = carregar_banco_usuarios()
        col_adm1, col_adm2 = st.columns([1, 1])
        
        with col_adm1:
            st.subheader("1. Cadastrar Novo Usuário")
            st.caption("A senha inicial será sempre **123456** com troca obrigatória no primeiro acesso.")
            
            with st.form("form_novo_usuario"):
                novo_user = st.text_input("Nome do Usuário", placeholder="ex: rodrigo.carvalho").strip().lower()
                nivel_acesso = st.selectbox("Nível de Acesso", ["convencional", "admin"])
                btn_cadastrar = st.form_submit_button("➕ Cadastrar Usuário", type="primary")
                
                if btn_cadastrar:
                    if not novo_user:
                        st.error("⚠️ Preencha o nome do usuário.")
                    elif novo_user in banco_usuarios:
                        st.warning(f"⚠️ O usuário '{novo_user}' já existe.")
                    else:
                        if salvar_usuario(novo_user, "123456", nivel_acesso=nivel_acesso, precisa_trocar=True):
                            st.success(f"✅ Usuário **{novo_user}** criado com sucesso no banco de dados!")
                            st.rerun()

        with col_adm2:
            st.subheader("2. Reset de Senha de Usuário")
            lista_usuarios = [u for u in banco_usuarios.keys() if u != "admin"]
            
            if lista_usuarios:
                user_sel_senha = st.selectbox("Selecione o Usuário para Reset:", lista_usuarios)
                
                if st.button("🔄 Resetar Senha para Inicial (123456)", type="primary"):
                    curr_nivel = banco_usuarios[user_sel_senha]["nivel_acesso"]
                    if salvar_usuario(user_sel_senha, "123456", nivel_acesso=curr_nivel, precisa_trocar=True):
                        st.success(f"✅ Senha do usuário **{user_sel_senha}** resetada para **123456**!")
                        st.rerun()

        st.divider()
        st.subheader("3. Usuários Cadastrados & Remoção")
        
        data_users = []
        for k, v in banco_usuarios.items():
            data_users.append({
                "Usuário": k,
                "Nível de Acesso": "Administrador" if v["nivel_acesso"] == "admin" else "Convencional",
                "Status Senha": "⚠️ Troca Pendente" if v["precisa_trocar_senha"] else "🟢 Definida"
            })
            
        st.dataframe(pd.DataFrame(data_users), hide_index=True, use_container_width=True)

        if lista_usuarios:
            col_rem1, col_rem2 = st.columns([2, 1])
            with col_rem1:
                user_para_remover = st.selectbox("Selecione o usuário para remover:", lista_usuarios, key="sel_rem")
            with col_rem2:
                st.write(""); st.write("")
                if st.button("🗑️ Remover Usuário do Banco", key="btn_rem_u"):
                    if remover_usuario(user_para_remover):
                        st.success(f"✅ Usuário **{user_para_remover}** excluído do banco de dados!")
                        st.rerun()

# --- BARRA LATERAL LOGOUT ---
st.sidebar.divider()
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.session_state.e_admin = False
    st.session_state.troca_obrigatoria = False
    st.rerun()
