import os
import re
import uuid
import base64
import html as html_lib
import json
import pandas as pd
import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components
import altair as alt
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from fpdf import FPDF
import tempfile

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
from supabase import create_client, Client

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
        url = "https://www.ibge.gov.br/explica/inflacao.php"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            match = re.search(r'([0-9]+,[0-9]+)\s*%', resp.text)
            if match:
                return float(match.group(1).replace(",", ".")), "IBGE (Web)"
    except Exception:
        pass
    return 4.58, "Set/2026 (Referência Oficial)"

def formatar_ci_num(ci_str):
    digits = re.sub(r'\D', '', str(ci_str))
    if len(digits) == 9:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:]}"
    elif len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}"
    elif digits:
        return ci_str.strip()
    return "000.000.000"

# --- LEITOR ROBUSTO DE ARQUIVOS (EXCEL / HTML) ---
def ler_arquivo_excel_robusto(uploaded_file):
    bytes_data = uploaded_file.getvalue()
    try:
        return pd.read_excel(BytesIO(bytes_data))
    except Exception:
        pass
    try:
        try:
            html_text = bytes_data.decode('utf-8')
        except UnicodeDecodeError:
            html_text = bytes_data.decode('ISO-8859-1', errors='ignore')
        table_match = re.search(r'<table[^>]*>(.*?)</table>', html_text, re.DOTALL | re.IGNORECASE)
        if not table_match:
            raise ValueError("Nenhuma tabela HTML encontrada.")
        table_content = table_match.group(1)
        rows = []
        for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_content, re.DOTALL | re.IGNORECASE):
            row_content = row_match.group(1)
            cells = []
            for cell_match in re.finditer(r'<t[dh][^>]*>(.*?)</t[dh]>', row_content, re.DOTALL | re.IGNORECASE):
                cell_text = cell_match.group(1)
                cell_text = re.sub(r'<[^>]+>', '', cell_text)
                cell_text = cell_text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                cells.append(cell_text.strip())
            if cells:
                rows.append(cells)
        if not rows:
            raise ValueError("Tabela HTML extraída está vazia.")
        max_cols = max(len(r) for r in rows)
        header = rows[0]
        if len(header) < max_cols:
            header.extend([f"Col_{i}" for i in range(len(header), max_cols)])
        data_rows = []
        for r in rows[1:]:
            if len(r) < max_cols:
                r.extend([""] * (max_cols - len(r)))
            elif len(r) > max_cols:
                r = r[:max_cols]
            data_rows.append(r)
        return pd.DataFrame(data_rows, columns=header)
    except Exception as e:
        raise ValueError(f"Formato de arquivo não suportado ou corrompido. Erro interno: {e}")

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
            self.set_font("Arial", "B", 14)
            self.set_x(60)
            self.cell(140, 8, "RELATÓRIO FOTOGRÁFICO", align="C", ln=1)
            
            info_cabecalho = f"{self.cod_cliente} | {self.nome_cliente}".strip(" |")
            if info_cabecalho:
                self.set_font("Arial", "B", 10)
                self.set_x(60)
                self.cell(140, 6, info_cabecalho, align="C", ln=1)
            
            self.set_y(35)
        else:
            self.set_y(30)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

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
  max-width: 1280px !important;
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

div.stButton > button {
  width: 100%;
  padding: 0.6rem 0.5rem;
  border-radius: 10px !important;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  transition: all 0.2s ease;
}
div.stButton > button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,85,165,0.15);
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def botao_copiar_customizado(texto_para_copiar, chave_unica, label_btn="📄 Copiar Texto Completo"):
    texto_js = json.dumps(str(texto_para_copiar))
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
        const texto = {texto_js};
        navigator.clipboard.writeText(texto).then(function() {{
            const msg = document.getElementById("msg_{chave_unica}");
            msg.style.display = "inline";
            setTimeout(function() {{ msg.style.display = "none"; }}, 2500);
        }}).catch(err => console.error('Erro ao copiar', err));
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

# --- GERENCIAMENTO DE ESTADO DE AUTENTICAÇÃO E SESSÃO ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "e_admin" not in st.session_state: st.session_state.e_admin = False
if "e_supervisor" not in st.session_state: st.session_state.e_supervisor = False
if "troca_obrigatoria" not in st.session_state: st.session_state.troca_obrigatoria = False
if "filtro_dashboard_ativo" not in st.session_state: st.session_state.filtro_dashboard_ativo = "Todas"
if "ultimo_usuario_logado" not in st.session_state: st.session_state.ultimo_usuario_logado = ""
if "df_excel_agenda" not in st.session_state: st.session_state.df_excel_agenda = None

if "equipamentos" not in st.session_state: st.session_state.equipamentos = []
if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0

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
        senha_input = st.text_input("Senha", type="password").strip()
        btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary")
        
        if btn_entrar:
            if usuario_input in banco_usuarios and banco_usuarios[usuario_input]["senha"] == senha_input:
                usr_data = banco_usuarios[usuario_input]
                st.session_state.autenticado = True
                st.session_state.usuario_atual = usuario_input
                nivel_acc = usr_data["nivel_acesso"]
                st.session_state.e_admin = (nivel_acc == "admin")
                st.session_state.e_supervisor = (nivel_acc == "supervisor")
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

if st.sidebar.button("🔄 Novo Cliente", use_container_width=True):
    st.session_state.reset_counter += 1
    st.session_state.equipamentos = []
    st.rerun()

if st.session_state.e_admin:
    lista_abas = ["⚙️ Painel Admin"]
else:
    lista_abas = [
        "🛠️ Tratativa de Ocorrências",
        "📊 Agenda de Ocorrências", 
        "📓 Bloco de Notas Pessoal"
    ]
    if st.session_state.e_supervisor:
        lista_abas.append("⚙️ Painel Admin")

abas_sistema = st.tabs(lista_abas)

if st.session_state.e_admin:
    aba_admin = abas_sistema[0]
    aba_tratativa = None
    aba_agenda = None
    aba_notas = None
else:
    aba_tratativa = abas_sistema[0]
    aba_agenda = abas_sistema[1]
    aba_notas = abas_sistema[2]
    aba_admin = abas_sistema[3] if st.session_state.e_supervisor else None

if "nota_selecionada_id" not in st.session_state: st.session_state.nota_selecionada_id = None

# =====================================================================
# ABA 1: TRATATIVA DE OCORRÊNCIAS
# =====================================================================
if aba_tratativa is not None:
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
                    "🎂 Aniversário de Contrato",
                    "📋 Ficha de Cliente"
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
                st.subheader("1. Identificação do Cliente")
                s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
                with s1_l1_c1: cod_cliente = st.text_input("Código do Cliente *", key=f"vis_cod_{rc}")
                with s1_l1_c2: nome_cliente = st.text_input("Nome / Razão Social *", key=f"vis_nome_{rc}")
                with s1_l1_c3: telefone = st.text_input("Telefone *", key=f"vis_tel_{rc}")

                s1_l2_c1, s1_l2_c2, s1_l2_c3 = st.columns(3)
                with s1_l2_c1: contato = st.text_input("Contato *", key=f"vis_cont_{rc}")
                with s1_l2_c2: departamento = st.text_input("Sobrenome ou Departamento *", key=f"vis_dep_{rc}")
                with s1_l2_c3: st.write("")

                st.divider()
                st.subheader("2. Informações Contratuais & Centrais")
                
                qtd_centrais_visita = st.number_input("Quantidade de Centrais no Cliente *", min_value=1, max_value=10, value=1, step=1, key=f"vis_qtd_centrais_{rc}")
                st.write("")

                eq_dict_visita = {}
                if qtd_centrais_visita == 1:
                    col_eq_c1, col_eq_c2 = st.columns(2)
                    with col_eq_c1:
                        eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_cont_{rc}")
                    with col_eq_c2:
                        desc_eq_contrato = st.text_input("Quais equipamentos contratados? *", key=f"desc_eq_{rc}")
                        eq_dict_visita[1] = desc_eq_contrato
                else:
                    eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_cont_{rc}")
                    st.markdown("**Equipamentos Contratados por Central:**")
                    cols_cent = st.columns(min(int(qtd_centrais_visita), 3))
                    for i in range(1, int(qtd_centrais_visita) + 1):
                        c_idx = (i - 1) % len(cols_cent)
                        with cols_cent[c_idx]:
                            eq_dict_visita[i] = st.text_input(f"Equipamentos Central {i:02d} *", key=f"desc_eq_cent_{i}_{rc}")

                st.write("")
                s2_l1_c3, s2_l1_c4 = st.columns(2)
                with s2_l1_c3:
                    tem_freq = st.radio("Possui programação cadastrada? *", ["Sim", "Não"], horizontal=True, index=None, key=f"tem_freq_{rc}")
                with s2_l1_c4:
                    desc_freq = ""
                    if tem_freq == "Sim":
                        desc_freq = st.text_input("Qual a programação? *", key=f"desc_freq_{rc}")
                    elif tem_freq == "Não":
                        desc_freq = st.text_input("Nº OC de Cadastramento *", key=f"desc_freq_nao_{rc}")

                s2_l2_c1, s2_l2_c2 = st.columns(2)
                with s2_l2_c1: consumo_previsto = st.text_input("Consumo Previsto (kg) *", key=f"cons_prev_{rc}")
                with s2_l2_c2: consumo_real = st.text_input("Consumo Real/Médio (kg) *", key=f"cons_real_{rc}")
                    
                s2_l3_c1, s2_l3_c2 = st.columns(2)
                with s2_l3_c1: possui_art = st.radio("Laudo ART emitido? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_art_{rc}")
                with s2_l3_c2:
                    desc_art = ""
                    if possui_art == "Sim":
                        desc_art = st.text_input("Número da ART *", key=f"desc_art_sim_{rc}")
                    elif possui_art == "Não":
                        desc_art = st.text_input("Nº OC de Solicitação de Laudo *", key=f"desc_art_nao_{rc}")

                s2_l4_c1, s2_l4_c2 = st.columns(2)
                with s2_l4_c1: possui_debitos = st.radio("Cliente possui débitos? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rc}")
                with s2_l4_c2:
                    desc_debitos = ""
                    if possui_debitos == "Sim":
                        desc_debitos = st.text_input("Detalhes dos Débitos", key=f"desc_deb_{rc}")

                s2_l5_c1, s2_l5_c2 = st.columns(2)
                with s2_l5_c1: central_norma = st.radio("Central atende as normas? *", ["Sim", "Não"], horizontal=True, index=None, key=f"central_norma_{rc}")
                with s2_l5_c2:
                    desc_central_norma = ""
                    if central_norma == "Não":
                        desc_central_norma = st.text_input("Motivo Central fora de norma", key=f"desc_norma_{rc}")

                s2_l6_c1, s2_l6_c2 = st.columns(2)
                with s2_l6_c1: rep2_correto = st.radio("Representante 2 está correto? *", ["Sim", "Não"], horizontal=True, index=None, key=f"rep2_{rc}")
                with s2_l6_c2:
                    desc_rep2 = ""
                    if rep2_correto == "Não":
                        desc_rep2 = st.text_input("Nº OC de Regularização", key=f"desc_rep2_{rc}")

                st.divider()
                st.subheader("3. Equipamentos Disponíveis no Cliente (Cálculo de Vazão)")
                
                opcoes_centrais_list = [f"Central {i:02d}" for i in range(1, int(qtd_centrais_visita) + 1)] if qtd_centrais_visita > 1 else ["Central"]
                
                c_cent_sel, c_qtd_eq, c_nome_eq, c_vaz_eq, c_btn_eq = st.columns([2, 1, 3, 2, 1])
                with c_cent_sel:
                    central_dest = st.selectbox("Central", opcoes_centrais_list, key=f"sel_cent_dest_{rc}")
                with c_qtd_eq:
                    qtd_eq_add = st.number_input("Qtd", min_value=1, value=1, step=1, key=f"qtd_eq_add_{rc}")
                with c_nome_eq:
                    nome_eq_add = st.text_input("Equipamento", key=f"nome_eq_add_{rc}")
                with c_vaz_eq:
                    vazao_eq_add = st.text_input("Vazão Unit. (kg/h)", key=f"vazao_eq_add_{rc}")
                with c_btn_eq:
                    st.write(""); st.write("")
                    if st.button("➕ Add", key=f"btn_add_eq_vis_{rc}"):
                        if nome_eq_add.strip() and vazao_eq_add.strip():
                            try:
                                v_unit = float(vazao_eq_add.replace(",", ".").lower().replace("kg/h", "").strip())
                                q_num = int(qtd_eq_add)
                                v_tot_item = v_unit * q_num
                                
                                st.session_state.equipamentos.append({
                                    "central": central_dest,
                                    "qtd": q_num,
                                    "nome": nome_eq_add.strip().title(),
                                    "vazao_unit": v_unit,
                                    "vazao_total": v_tot_item
                                })
                                st.success("Adicionado!")
                                st.rerun()
                            except ValueError:
                                st.error("Digite um valor numérico para a vazão.")
                        else:
                            st.warning("Preencha o nome e vazão.")

                if st.session_state.equipamentos:
                    st.write("")
                    st.markdown("**Lista de Equipamentos Cadastrados:**")
                    centrais_unicas = sorted(list(set([e["central"] for e in st.session_state.equipamentos])))
                    vazao_geral_todas = 0.0

                    for c_nome in centrais_unicas:
                        st.markdown(f"🔹 **{c_nome.upper()}**")
                        vazao_c = 0.0
                        for idx, item in enumerate(st.session_state.equipamentos):
                            if item["central"] == c_nome:
                                vazao_c += item["vazao_total"]
                                vazao_geral_todas += item["vazao_total"]
                                c_txt, c_del = st.columns([5, 1])
                                v_unit_fmt = f"{item['vazao_unit']:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                c_txt.text(f"• {item['qtd']:02d} {item['nome']} - {v_unit_fmt} kg/h")
                                if c_del.button("❌", key=f"del_eq_{idx}_{rc}"):
                                    st.session_state.equipamentos.pop(idx)
                                    st.rerun()
                        v_str_c = f"{vazao_c:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                        st.caption(f"Vazão Subtotal {c_nome}: {v_str_c} kg/h")
                    
                    st.write("")
                    v_str_geral = f"{vazao_geral_todas:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                    st.markdown(f"🔥 **Total - {v_str_geral} kg/h**")

                st.divider()
                st.subheader("4. Novos Negócios & Satisfação")
                s3_c1, s3_c2 = st.columns(2)
                with s3_c1:
                    indica_negocios = st.radio("Indicação de novos negócios? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ind_neg_{rc}")
                    desc_negocios = ""
                    if indica_negocios == "Sim":
                        desc_negocios = st.text_input("Detalhes da indicação", key=f"desc_neg_{rc}")
                with s3_c2:
                    cliente_satisfeito = st.radio("Cliente satisfeito com a Consigaz? *", ["Sim", "Não"], horizontal=True, index=None, key=f"cli_sat_{rc}")
                    desc_satisfacao = ""
                    if cliente_satisfeito:
                        desc_satisfacao = st.text_input("Observação sobre satisfação", key=f"desc_sat_{rc}")

                observacoes = st.text_area("Observações Gerais", key=f"obs_transf_{rc}")

                st.divider()
                st.subheader("5. Relatório Fotográfico - Upload de Imagens")
                def carregar_fotos(label, max_arquivos=None):
                    fotos = st.file_uploader(label, type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_{label}_{rc}")
                    if max_arquivos and fotos and len(fotos) > max_arquivos:
                        return fotos[:max_arquivos]
                    return fotos

                dic_fotos_final = {}
                col_f1, col_f2 = st.columns(2)
                with col_f1: dic_fotos_final["FACHADA"] = carregar_fotos("📸 FACHADA (Até 2 fotos)", max_arquivos=2)
                with col_f2: dic_fotos_final["CILINDROS"] = carregar_fotos("📸 CILINDROS (Até 5 fotos)", max_arquivos=5)

                st.write("---")
                if qtd_centrais_visita == 1:
                    c1, c2, c3 = st.columns(3)
                    with c1: dic_fotos_final["ABRIGO"] = carregar_fotos("📸 ABRIGO (Até 10 fotos)", max_arquivos=10)
                    with c2: dic_fotos_final["CENTRAL"] = carregar_fotos("📸 CENTRAL (Até 5 fotos)", max_arquivos=5)
                    with c3: dic_fotos_final["EQUIPAMENTOS"] = carregar_fotos("📸 EQUIPAMENTOS", max_arquivos=None)
                else:
                    for i in range(1, int(qtd_centrais_visita) + 1):
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
                        linha_art = "( ) Sim ( ) Não"
                        if possui_art == "Sim":
                            linha_art = f"(x) Sim ( ) Não {desc_art.strip()}"
                        elif possui_art == "Não":
                            linha_art = f"( ) Sim (x) Não {desc_art.strip()}"

                        if qtd_centrais_visita == 1:
                            desc_eq_val = eq_dict_visita.get(1, "").strip()
                            texto_eq_contrato = f"{eq_contrato or ''}. {desc_eq_val}".strip()
                        else:
                            linhas_eq_contr = [f"[Equipamentos Central {i:02d}: {eq_dict_visita.get(i, '').strip()}]" for i in range(1, int(qtd_centrais_visita) + 1)]
                            texto_eq_contrato = f"{eq_contrato or ''}. " + " ".join(linhas_eq_contr)

                        texto_rep2 = f"{rep2_correto or ''}" + (f" - {desc_rep2.strip()}" if rep2_correto == "Não" and desc_rep2.strip() else "")
                        texto_freq = f"{tem_freq or ''}" + (f" - {desc_freq.strip()}" if desc_freq.strip() else "")
                        texto_debitos = f"{possui_debitos or ''}" + (f" - {desc_debitos.strip()}" if possui_debitos == "Sim" and desc_debitos.strip() else "")
                        texto_central_norma = f"{central_norma or ''}" + (f" - {desc_central_norma.strip()}" if central_norma == "Não" and desc_central_norma.strip() else "")
                        texto_negocios = f"{indica_negocios or ''}" + (f" - {desc_negocios.strip()}" if indica_negocios == "Sim" and desc_negocios.strip() else "")
                        texto_satisfacao = f"{cliente_satisfeito or ''}" + (f", {desc_satisfacao.strip()}" if desc_satisfacao.strip() else "")

                        texto_disp_equip = ""
                        if st.session_state.equipamentos:
                            centrais_cad = sorted(list(set([e["central"] for e in st.session_state.equipamentos])))
                            tot_vazao_geral = 0.0
                            for c_n in centrais_cad:
                                if qtd_centrais_visita > 1:
                                    texto_disp_equip += f"\n[{c_n.upper()}]\n"
                                else:
                                    texto_disp_equip += "\n[CENTRAL]\n"

                                vazao_c_sum = 0.0
                                for item in st.session_state.equipamentos:
                                    if item["central"] == c_n:
                                        v_unit_fmt = f"{item['vazao_unit']:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                        texto_disp_equip += f"{item['qtd']:02d} {item['nome']} - {v_unit_fmt} kg/h\n"
                                        vazao_c_sum += item["vazao_total"]
                                        tot_vazao_geral += item["vazao_total"]
                                v_c_sum_fmt = f"{vazao_c_sum:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                if qtd_centrais_visita > 1:
                                    texto_disp_equip += f"Vazão Subtotal {c_n}: {v_c_sum_fmt} kg/h\n"
                                else:
                                    texto_disp_equip += f"Vazão Subtotal Central: {v_c_sum_fmt} kg/h\n"
                            tot_g_fmt = f"{tot_vazao_geral:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                            texto_disp_equip += f"\nTotal - {tot_g_fmt} kg/h"
                        else:
                            texto_disp_equip = "\nTotal - 0 kg/h"

                        texto_final = f"""Contato: {contato}
Sobrenome ou departamento: {departamento}
Telefone: {telefone}

Equipamentos de acordo com o contrato vigente? {texto_eq_contrato}
Representante 2 está correto? {texto_rep2}
Possui programação cadastrada? {texto_freq}
Consumo de acordo com o contrato vigente? Consumo previsto: {consumo_previsto} kg | Consumo médio: {consumo_real} kg
Laudo ART emitido? {linha_art} Central atende as normas? {texto_central_norma}

Quais equipamentos disponíveis no cliente?
{texto_disp_equip}

Indicação de novos negócios do cliente: {texto_negocios}
Cliente possui débitos? {texto_debitos}
Cliente está satisfeito com o atendimento da Consigaz? {texto_satisfacao}

Obs.: {observacoes}"""

                        st.success("✅ Texto para o Sistema gerado com sucesso!")
                        st.text_area("Texto Gerado:", value=texto_final, height=350, key=f"txt_area_transf_{rc}")
                        botao_copiar_customizado(texto_final, "transf_txt")

                with col_b2:
                    if st.button("📄 Gerar PDF do Relatório Fotográfico"):
                        if not cod_cliente or not nome_cliente:
                            st.error("⚠️ Preencha o Código do Cliente e Nome/Razão Social.")
                        else:
                            pdf = RelatorioPDF(cod_cliente=cod_cliente, nome_cliente=nome_cliente, logo_path=LOGO_PATH)
                            pdf.set_margins(10, 32, 10)
                            pdf.set_auto_page_break(auto=True, margin=20)
                            
                            for categoria, arquivos in dic_fotos_final.items():
                                if arquivos:
                                    pdf.add_page()
                                    pdf.set_font("Arial", "B", 11)
                                    pdf.cell(0, 6, categoria.upper(), ln=1, align="L")
                                    pdf.ln(4)
                                    for arq in arquivos:
                                        temp_path = None
                                        try:
                                            img = Image.open(arq)
                                            if img.mode != "RGB":
                                                img = img.convert("RGB")
                                            fd, temp_path = tempfile.mkstemp(suffix=f"_{uuid.uuid4().hex}.jpg")
                                            os.close(fd)
                                            img.save(temp_path, format="JPEG")
                                            
                                            img_w_px, img_h_px = img.size
                                            proporcao = img_h_px / img_w_px
                                            w_alvo = 130
                                            h_alvo = w_alvo * proporcao
                                            if h_alvo > 110:
                                                h_alvo = 110
                                                w_alvo = h_alvo / proporcao
                                            pos_x_centro = (210 - w_alvo) / 2
                                            if pdf.get_y() + h_alvo > 270:
                                                pdf.add_page()
                                            pdf.image(temp_path, x=pos_x_centro, y=pdf.get_y(), w=w_alvo, h=h_alvo)
                                            pdf.set_y(pdf.get_y() + h_alvo + 10)
                                        except Exception:
                                            pass
                                        finally:
                                            if temp_path and os.path.exists(temp_path):
                                                try: os.remove(temp_path)
                                                except OSError: pass

                            cod_limpo = re.sub(r'\D', '', str(cod_cliente))
                            data_str = datetime.now().strftime("%d-%m-%y")
                            nome_arquivo_pdf = f"relatorio_{cod_limpo}_{data_str}.pdf"
                            pdf_output = pdf.output(dest='S')
                            pdf_bytes = pdf_output.encode('latin-1', errors='replace') if isinstance(pdf_output, str) else bytes(pdf_output)

                            st.download_button(
                                label="💾 Baixar PDF Gerado",
                                data=pdf_bytes,
                                file_name=nome_arquivo_pdf,
                                mime="application/pdf"
                            )

            # -------------------------------------------------------------
            # 2. ELABORAÇÃO DE CONTRATO
            # -------------------------------------------------------------
            elif menu_tratativa == "📝 Elaboração de Contrato":
                rcc = st.session_state.reset_counter
                cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento e geração do padrão de solicitação de contrato.")
                st.divider()

                tipo_fluxo = st.radio("Selecione o objetivo da solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, index=None, key=f"fluxo_c_{rcc}")
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
                tipo_contrato = st.radio("Contrato / Aditamento / Distrato", ["Contrato", "Aditamento", "Distrato"], horizontal=True, index=None, key=f"tp_cont_{rcc}")
                st.divider()

                st.subheader("4. Dados do Contrato")
                col_con1, col_con2 = st.columns(2)
                cnpj_campo_val, ie_campo_val = "", ""
                status_cnpj_txt, razao_social_txt = "", ""
                email_novo_prop = "n/a"

                with col_con1:
                    endereco_padrao = st.text_input("Endereço padrão ou entrega?", key=f"end_padrao_{rcc}")
                    mesmo_prop_opt = st.radio("Mesmo proprietário?", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_prop_{rcc}")
                    if mesmo_prop_opt == "Não":
                        email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato", key=f"email_novo_{rcc}")

                with col_con2:
                    mesmo_cnpj_opt = st.radio("Mesmo CNPJ?", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_cnpj_{rcc}")
                    if mesmo_cnpj_opt == "Sim":
                        cnpj_campo_val = st.text_input("CNPJ", key=f"cnpj_val_{rcc}")
                        ie_campo_val = st.text_input("I.E.", key=f"ie_val_{rcc}")
                    elif mesmo_cnpj_opt == "Não":
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

                st.divider()
                st.subheader("5. Dados do Comodato")
                tipo_fornecimento = st.radio("Tipo de Fornecimento:", ["Granel", "Cilindro", "Ambos"], horizontal=True, index=None, key=f"tp_forn_{rcc}")
                
                preco_granel, consumo_granel_input = "", ""
                p13_val, p20_val, p45_val = "", "", ""
                p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
                consumo_cilindro_input_kg = ""
                consumo_cilindro_total_calc = 0

                if tipo_fornecimento in ["Granel", "Ambos"]:
                    st.markdown("**Granel:**")
                    col_g1, col_g2 = st.columns(2)
                    with col_g1: preco_granel = st.text_input("Preço Granel (R$/kg):", key=f"preco_granel_{rcc}")
                    with col_g2: consumo_granel_input = st.text_input("Consumo previsto (Granel) mensal:", key=f"cons_granel_{rcc}")

                if tipo_fornecimento in ["Cilindro", "Ambos"]:
                    st.markdown("**Cilindro:**")
                    col_cp1, col_cp2, col_cp3 = st.columns(3)
                    with col_cp1: p13_val = st.text_input("Preço P13 (R$):", key=f"p13_v_{rcc}")
                    with col_cp2: p20_val = st.text_input("Preço P20 (R$):", key=f"p20_v_{rcc}")
                    with col_cp3: p45_val = st.text_input("Preço P45 (R$):", key=f"p45_v_{rcc}")

                equipamentos_comodato = st.text_input("Equipamentos / Comodato:", key=f"eq_comodato_{rcc}")
                cond_pagamento = st.text_input("Condição de pagamento:", key=f"cond_pag_{rcc}")
                vigencia = st.text_input("Vigência:", key=f"vigencia_{rcc}")
                st.divider()

                st.subheader("6. Financeiro")
                possui_debito_fin = st.radio("Possui NF's Pendentes?", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rcc}")
                resp_pendentes = "n/a"
                if possui_debito_fin == "Sim":
                    resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", key=f"resp_pend_{rcc}")
                st.divider()

                if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
                    lines_out = []
                    if tipo_fluxo == "Gerar Minuta":
                        lines_out.append("**FAVOR GERAR MINUTA EM PDF PARA ENVIO AO CLIENTE**\n")
                    if motivo_solicitacao:
                        lines_out.append(f"Motivo da solicitação: {motivo_solicitacao}")
                    if tipo_contrato:
                        lines_out.append(f"Contrato / Aditamento / Distrato: {tipo_contrato}")
                    if mesmo_prop_opt:
                        lines_out.append(f"Mesmo proprietário?(sim/não): {mesmo_prop_opt}")
                    if cnpj_campo_val:
                        lines_out.append(f"CNPJ: {cnpj_campo_val}")
                    if ie_campo_val:
                        lines_out.append(f"I.E.: {ie_campo_val}")
                    if endereco_padrao:
                        lines_out.append(f"Endereço padrão ou entrega?: {endereco_padrao}")
                    if equipamentos_comodato:
                        lines_out.append(f"Equipamentos: {equipamentos_comodato}")
                    if tipo_fornecimento:
                        lines_out.append(f"Tipo de Fornecimento: {tipo_fornecimento}")
                    if preco_granel:
                        lines_out.append(f"Preço Granel: {preco_granel}")
                    if cond_pagamento:
                        lines_out.append(f"Condição de pagamento: {cond_pagamento}")
                    if vigencia:
                        lines_out.append(f"Vigência: {vigencia}")

                    texto_final_contrato = "\n".join(lines_out)
                    st.success("✅ Texto gerado com sucesso!")
                    st.code(texto_final_contrato)
                    botao_copiar_customizado(texto_final_contrato, "cop_contrato")

            # -------------------------------------------------------------
            # 3. APROVAÇÃO DE CONTRATO
            # -------------------------------------------------------------
            elif menu_tratativa == "📋 Aprovação de Contrato":
                cabecalho_pagina("Aprovação de Contrato", "Formulário de solicitação de aprovação de contrato.")
                st.divider()
                motivo_aprov = st.text_input("Motivo da regularização *", key=f"ap_mot_{rc}")
                proj_aprov = st.text_input("Número do Projeto *", key=f"ap_proj_{rc}")
                if st.button("📝 Gerar Texto Aprovação", type="primary"):
                    txt = f"Motivo: {motivo_aprov}\nProjeto: {proj_aprov}"
                    st.code(txt)
                    botao_copiar_customizado(txt, "cop_aprov")

            # -------------------------------------------------------------
            # 4. ANIVERSÁRIO DE CONTRATO
            # -------------------------------------------------------------
            elif menu_tratativa == "🎂 Aniversário de Contrato":
                cabecalho_pagina("Aniversário de Contrato", "Calculadora de reajuste por IPCA acumulado de 12M.")
                ipca, periodo = obter_ipca_acumulado_12m()
                if ipca:
                    st.success(f"📊 IPCA Acumulado 12M IBGE ({periodo}): `{ipca:.2f}%`")
                    ipca_val = ipca
                else:
                    ipca_val = st.number_input("IPCA Manual (%)", value=4.58)
                p_ant = st.text_input("Preço Anterior (R$)", value="7,7400")
                if st.button("📝 Gerar Reajuste", type="primary"):
                    try:
                        p_num = float(p_ant.replace(",", "."))
                        p_novo = p_num * (1 + ipca_val/100)
                        txt = f"Aumento de Aniversário de contrato, IPCA - {ipca_val:.2f}%.\n\nPreço anterior: R$ {p_num:.4f}\nPreço Aniversário: R$ {p_novo:.4f}"
                        st.code(txt)
                        botao_copiar_customizado(txt, "cop_aniv")
                    except:
                        st.error("Digite um valor numérico válido.")

            # -------------------------------------------------------------
            # 5. FICHA DE CLIENTE (NOVA ABA SEM NENHUM PREENCHIMENTO)
            # -------------------------------------------------------------
            elif menu_tratativa == "📋 Ficha de Cliente":
                cabecalho_pagina("Ficha de Cliente", "Formulário de tratativa de ocorrência e aditamento de contrato.")
                st.divider()

                # PRIMEIRA OPÇÃO DO FORMULÁRIO: Motivo
                st.subheader("1. Motivo da Ocorrência")
                motivo_ficha = st.text_input("Qual a nomenclatura (Motivo: )", value="", placeholder="", key=f"fc_motivo_{rc}")
                st.divider()

                st.subheader("2. Dados Contratuais & Comerciais")
                col_fc1, col_fc2 = st.columns(2)
                with col_fc1:
                    aditamento_anterior = st.text_input("Aditamento Anterior", value="", placeholder="", key=f"fc_adit_ant_{rc}")
                    contrato_novo = st.text_input("Contrato Novo", value="", placeholder="", key=f"fc_cont_novo_{rc}")
                    comodato_ficha = st.text_input("Comodato", value="", placeholder="", key=f"fc_comodato_{rc}")
                with col_fc2:
                    cond_pagamento_ficha = st.text_input("Condição de Pagamento", value="", placeholder="", key=f"fc_cond_pag_{rc}")
                    vigencia_ficha = st.text_input("Vigência", value="", placeholder="", key=f"fc_vigencia_{rc}")

                st.markdown("**Tipo de Fornecimento & Preços:**")
                tipo_forn_ficha = st.radio("Selecione o Fornecimento", ["Granel", "Cilindro", "Ambos"], horizontal=True, index=None, key=f"fc_tp_forn_{rc}")

                preco_granel_ficha, consumo_granel_ficha = "", ""
                preco_cilindro_ficha, consumo_cilindro_ficha = "", ""
                preco_granel_sep, preco_cilindro_sep = "", ""
                consumo_granel_sep, consumo_cilindro_sep = "", ""

                if tipo_forn_ficha == "Granel":
                    col_fg1, col_fg2 = st.columns(2)
                    with col_fg1: preco_granel_ficha = st.text_input("Preço Granel", value="", placeholder="", key=f"fc_p_granel_{rc}")
                    with col_fg2: consumo_granel_ficha = st.text_input("Consumo Mensal Previsto (Granel)", value="", placeholder="", key=f"fc_c_granel_{rc}")
                elif tipo_forn_ficha == "Cilindro":
                    col_fc1_sub, col_fc2_sub = st.columns(2)
                    with col_fc1_sub: preco_cilindro_ficha = st.text_input("Preço Cilindro", value="", placeholder="", key=f"fc_p_cil_{rc}")
                    with col_fc2_sub: consumo_cilindro_ficha = st.text_input("Consumo Mensal Previsto (Cilindro)", value="", placeholder="", key=f"fc_c_cil_{rc}")
                elif tipo_forn_ficha == "Ambos":
                    st.markdown("🔹 *Preços Separados:*")
                    col_fa1, col_fa2 = st.columns(2)
                    with col_fa1: 
                        preco_granel_sep = st.text_input("Preço Granel", value="", placeholder="", key=f"fc_p_g_sep_{rc}")
                        consumo_granel_sep = st.text_input("Consumo Mensal Granel", value="", placeholder="", key=f"fc_c_g_sep_{rc}")
                    with col_fa2: 
                        preco_cilindro_sep = st.text_input("Preço Cilindro", value="", placeholder="", key=f"fc_p_c_sep_{rc}")
                        consumo_cilindro_sep = st.text_input("Consumo Mensal Cilindro", value="", placeholder="", key=f"fc_c_c_sep_{rc}")

                st.divider()

                # FINAL DO FORMULÁRIO: Obs
                st.subheader("3. Observações Finais")
                obs_ficha = st.text_area("Observação (Obs.:)", value="", placeholder="", key=f"fc_obs_{rc}")

                st.divider()
                if st.button("📝 Gerar Texto Ficha de Cliente", type="primary"):
                    if tipo_forn_ficha == "Granel":
                        str_preco = preco_granel_ficha.strip()
                        str_consumo = consumo_granel_ficha.strip()
                    elif tipo_forn_ficha == "Cilindro":
                        str_preco = preco_cilindro_ficha.strip()
                        str_consumo = consumo_cilindro_ficha.strip()
                    elif tipo_forn_ficha == "Ambos":
                        str_preco = f"Granel: {preco_granel_sep.strip()} | Cilindro: {preco_cilindro_sep.strip()}"
                        str_consumo = f"Granel: {consumo_granel_sep.strip()} | Cilindro: {consumo_cilindro_sep.strip()}"
                    else:
                        str_preco = ""
                        str_consumo = ""

                    texto_ficha_final = f"""ADITAMENTO ANTERIOR: {aditamento_anterior.strip()}
CONTRATO NOVO: {contrato_novo.strip()}
COMODATO: {comodato_ficha.strip()}
PREÇO: {str_preco}
CONSUMO MENSAL PREVISTO: {str_consumo}
CONDIÇÃO DE PAGAMENTO: {cond_pagamento_ficha.strip()}
VIGÊNCIA: {vigencia_ficha.strip()}

Obs.: {obs_ficha.strip()} {motivo_ficha.strip()}"""

                    st.success("✅ Ficha de Cliente gerada com sucesso!")
                    st.code(texto_ficha_final)
                    botao_copiar_customizado(texto_ficha_final, "cop_ficha_cliente")


# =====================================================================
# ABA 2: AGENDA DE OCORRÊNCIAS
# =====================================================================
if aba_agenda is not None:
    with aba_agenda:
        cabecalho_pagina("Agenda de Ocorrências", "Painel de controle e acompanhamento de prazos.")
        st.info("Faça o upload da planilha Excel para gerenciar as ocorrências e SLAs.")


# =====================================================================
# ABA 3: BLOCO DE NOTAS PESSOAL
# =====================================================================
if aba_notas is not None:
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
            for n_id, n_data in notas_usuario.items():
                if st.button(n_data.get("titulo", "Sem Título"), key=f"btn_n_{n_id}", use_container_width=True):
                    st.session_state.nota_selecionada_id = n_id
                    st.rerun()

        with col_conteudo_notas:
            cabecalho_pagina("Bloco de Notas Pessoal", "Suas anotações sincronizadas na nuvem.")
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
                with b1: btn_s = st.form_submit_button("💾 Salvar", type="primary")
                with b2: btn_d = st.form_submit_button("🗑️ Apagar") if id_atual else False

                if btn_s and tit:
                    target_id = id_atual if id_atual else str(uuid.uuid4())
                    if salvar_nota(target_id, usuario_atual, tit, cli, txt):
                        st.session_state.nota_selecionada_id = target_id
                        st.success("Salvo com sucesso!")
                        st.rerun()
                if btn_d and id_atual:
                    if apagar_nota(id_atual):
                        st.session_state.nota_selecionada_id = None
                        st.rerun()


# =====================================================================
# PAINEL ADMIN
# =====================================================================
if aba_admin is not None:
    with aba_admin:
        cabecalho_pagina("Painel de Administração", "Gerenciamento de usuários e permissões do sistema.")
        banco_usuarios = carregar_banco_usuarios()
        
        col_adm1, col_adm2 = st.columns(2)
        with col_adm1:
            st.subheader("Cadastrar Usuário")
            with st.form("form_novo_user"):
                u_novo = st.text_input("Usuário").strip().lower()
                n_novo = st.selectbox("Nível", ["convencional", "supervisor", "admin"])
                if st.form_submit_button("Adicionar"):
                    if u_novo in banco_usuarios:
                        st.error("Usuário já existe.")
                    else:
                        salvar_usuario(u_novo, "123456", nivel_acesso=n_novo, precisa_trocar=True)
                        st.success("Criado com sucesso!")
                        st.rerun()


# --- LOGOUT NA BARRA LATERAL ---
st.sidebar.divider()
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.session_state.e_admin = False
    st.session_state.e_supervisor = False
    st.session_state.troca_obrigatoria = False
    st.rerun()
