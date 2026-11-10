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
        import re
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
        df = pd.DataFrame(data_rows, columns=header)
        return df
    except Exception as e:
        raise ValueError(f"Formato de arquivo não suportado ou corrompido. Erro interno: {e}")


# --- GERADOR DE PDF DE RELATÓRIO FOTOGRÁFICO CORRIGIDO ---
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
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")

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
    texto_seguro = str(texto_para_copiar).replace('`', '\\`').replace('$', '\\$').replace('\n', '\\n').replace('"', '\\"')
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
if "last_central" not in st.session_state: st.session_state.last_central = "Central"
if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0

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
                nivel_acc = usr_data["nivel_acesso"]
                st.session_state.e_admin = (nivel_acc == "admin")
                st.session_state.e_supervisor = (nivel_acc == "supervisor")
                st.session_state.troca_obrigatoria = usr_data["precisa_trocar_senha"] or (senha_input == "123456")
                
                if st.session_state.ultimo_usuario_logado != usuario_input:
                    st.session_state.df_excel_agenda = None
                    st.session_state.ultimo_usuario_logado = usuario_input
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
elif st.session_state.e_supervisor:
    st.sidebar.caption("📊 Perfil: Supervisor")

# Definição de abas conforme o perfil
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
                    st.session_state.equipamentos = []
                    st.rerun()

                st.divider()
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
                        desc_eq_contrato = st.text_input("Quais equipamentos contratados? *", placeholder="Ex: 01 B190 + 01 CC", key=f"desc_eq_{rc}")
                        eq_dict_visita[1] = desc_eq_contrato
                else:
                    eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_cont_{rc}")
                    st.markdown("**Equipamentos Contratados por Central:**")
                    cols_cent = st.columns(min(int(qtd_centrais_visita), 3))
                    for i in range(1, int(qtd_centrais_visita) + 1):
                        c_idx = (i - 1) % len(cols_cent)
                        with cols_cent[c_idx]:
                            eq_dict_visita[i] = st.text_input(f"Equipamentos Central {i:02d} *", placeholder="Ex: 01 B190 + 01 CC", key=f"desc_eq_cent_{i}_{rc}")

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
                    nome_eq_add = st.text_input("Equipamento", placeholder="Ex: Forno Industrial", key=f"nome_eq_add_{rc}")
                with c_vaz_eq:
                    vazao_eq_add = st.text_input("Vazão Unit. (kg/h)", placeholder="Ex: 1,6 ou 0,5", key=f"vazao_eq_add_{rc}")
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
                        st.error(f"⚠️ Limite excedido para {label}. Serão considerados apenas os primeiros {max_arquivos} arquivos.")
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
                                    
                                    for idx, arq in enumerate(arquivos):
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
                                                try:
                                                    os.remove(temp_path)
                                                except OSError:
                                                    pass

                            if st.session_state.equipamentos:
                                pdf.add_page()
                                pdf.set_font("Arial", "B", 11)
                                pdf.cell(0, 6, "EQUIPAMENTOS DISPONÍVEIS NO CLIENTE", ln=1, align="L")
                                pdf.ln(4)
                                
                                centrais_cad = sorted(list(set([e["central"] for e in st.session_state.equipamentos])))
                                tot_pdf_geral = 0.0

                                for c_n in centrais_cad:
                                    pdf.set_font("Arial", "B", 10)
                                    pdf.cell(0, 6, c_n.upper(), ln=1, align="L")
                                    
                                    pdf.set_fill_color(230, 230, 230)
                                    pdf.cell(20, 7, "QTD", border=1, align="C", fill=True)
                                    pdf.cell(115, 7, "EQUIPAMENTO", border=1, align="L", fill=True)
                                    pdf.cell(50, 7, "VAZÃO UNIT.", border=1, align="C", fill=True, ln=1)
                                    
                                    pdf.set_font("Arial", "", 10)
                                    vazao_c_pdf = 0.0
                                    for item in st.session_state.equipamentos:
                                        if item["central"] == c_n:
                                            v_unit_fmt = f"{item['vazao_unit']:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                            pdf.cell(20, 6, f"{item['qtd']:02d}", border=1, align="C")
                                            pdf.cell(115, 6, f"{item['nome']}", border=1, align="L")
                                            pdf.cell(50, 6, f"{v_unit_fmt} kg/h", border=1, align="C", ln=1)
                                            vazao_c_pdf += item["vazao_total"]
                                            tot_pdf_geral += item["vazao_total"]

                                    v_c_pdf_fmt = f"{vazao_c_pdf:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                    pdf.set_font("Arial", "B", 10)
                                    pdf.cell(135, 7, f"VAZÃO TOTAL {c_n.upper()}:", border=1, align="R", fill=True)
                                    pdf.cell(50, 7, f"{v_c_pdf_fmt} kg/h", border=1, align="C", fill=True, ln=1)
                                    pdf.ln(4)

                            cod_limpo = re.sub(r'\D', '', str(cod_cliente))
                            data_str = datetime.now().strftime("%d-%m-%y")
                            nome_arquivo_pdf = f"relatorio_{cod_limpo}_{data_str}.pdf"
                            
                            pdf_output = pdf.output(dest='S')
                            if isinstance(pdf_output, str):
                                pdf_bytes = pdf_output.encode('latin-1', errors='replace')
                            else:
                                pdf_bytes = bytes(pdf_output)

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
                
                if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_elab_{rcc}"):
                    st.session_state.reset_counter += 1
                    st.rerun()

                st.divider()

                # [BLOCO 01] Motivo da Elaboração / Regularização
                st.subheader("[BLOCO 01] Motivo da Elaboração / Regularização")
                motivo_solicitacao = st.text_area("Descreva claramente o motivo da regularização do contrato:", key=f"motivo_{rcc}")

                st.divider()

                # [BLOCO 02] Dados do Contrato
                st.subheader("[BLOCO 02] Dados do Contrato")
                col_b2_1, col_b2_2 = st.columns(2)
                
                with col_b2_1:
                    tipo_contrato = st.radio("Contrato / Aditamento / Distrato:", ["Contrato", "Aditamento", "Distrato"], horizontal=True, index=None, key=f"tp_cont_{rcc}")
                    requisicao_opt = st.radio("Requisição:", ["Permanente", "Provisório"], horizontal=True, index=None, key=f"req_opt_{rcc}")

                with col_b2_2:
                    mesmo_prop_opt = st.radio("Mesmo proprietário?", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_prop_{rcc}")

                cnpj_campo_val, ie_campo_val = "", ""
                status_cnpj_txt, razao_social_txt = "", ""

                col_b2_3, col_b2_4 = st.columns(2)
                with col_b2_3:
                    if mesmo_prop_opt == "Sim":
                        cnpj_campo_val = st.text_input("Novo CNPJ:", key=f"novo_cnpj_val_{rcc}")
                        ie_campo_val = st.text_input("Nova I.E.:", key=f"nova_ie_val_{rcc}")
                    elif mesmo_prop_opt == "Não":
                        cnpj_campo_val = st.text_input("CNPJ:", key=f"cnpj_val_{rcc}")
                        ie_campo_val = st.text_input("I.E.:", key=f"ie_val_{rcc}")
                    else:
                        cnpj_campo_val = st.text_input("CNPJ / Novo CNPJ:", key=f"cnpj_gen_{rcc}")
                        ie_campo_val = st.text_input("I.E. / Nova I.E.:", key=f"ie_gen_{rcc}")

                with col_b2_4:
                    if len("".join(filter(str.isdigit, str(cnpj_campo_val)))) == 14:
                        dados_api = consultar_cnpj_api(cnpj_campo_val)
                        if dados_api:
                            razao_social_txt = dados_api.get("razao_social", "Não encontrada")
                            situacao_cad = dados_api.get("situacao_cadastral", "")
                            status_cnpj_txt = "Ativo" if situacao_cad == 2 or str(situacao_cad).upper() == "ATIVA" else f"Inativa ({situacao_cad})"
                            st.markdown(f"✅ **Razão Social:** {razao_social_txt}")
                            st.markdown(f"🟢 **Status CNPJ:** {status_cnpj_txt}")

                st.divider()

                # [BLOCO 03] Endereço / Equipamentos
                st.subheader("[BLOCO 03] Endereço / Equipamentos")
                col_b3_1, col_b3_2 = st.columns(2)
                with col_b3_1:
                    endereco_padrao = st.text_input("Endereço padrão ou entrega?:", key=f"end_padrao_{rcc}")
                with col_b3_2:
                    qtd_entregas_c = st.number_input("Quantidade de centrais / endereços:", min_value=1, value=1, step=1, key=f"qtd_ent_c_{rcc}")

                eq_dict_c = {}
                if qtd_entregas_c == 1:
                    eq_dict_c[1] = st.text_input("Equipamentos Central 01:", key=f"eq_ent_1_{rcc}")
                else:
                    st.markdown("**Equipamentos por Central / Endereço:**")
                    cols_eq_b3 = st.columns(min(int(qtd_entregas_c), 3))
                    for i in range(1, int(qtd_entregas_c) + 1):
                        c_idx = (i - 1) % len(cols_eq_b3)
                        with cols_eq_b3[c_idx]:
                            eq_dict_c[i] = st.text_input(f"Equipamentos Central {i:02d}:", key=f"eq_ent_{i}_{rcc}")

                st.divider()

                # [BLOCO 04] Condições Comerciais
                st.subheader("[BLOCO 04] Condições Comerciais")
                tipo_fornecimento = st.radio("Tipo de Fornecimento:", ["Granel", "Cilindro", "Ambos"], horizontal=True, index=None, key=f"tp_forn_{rcc}")
                
                preco_granel, consumo_granel_input = "", ""
                p13_val, p20_val, p45_val = "", "", ""
                p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
                consumo_cilindro_input_kg = ""
                consumo_cilindro_total_calc = 0

                if tipo_fornecimento in ["Granel", "Ambos"]:
                    st.markdown("**Preço e Consumo Granel:**")
                    col_g1, col_g2 = st.columns(2)
                    with col_g1:
                        preco_granel = st.text_input("Preço Granel (R$/kg):", key=f"preco_granel_{rcc}")
                    with col_g2:
                        consumo_granel_input = st.text_input("Consumo previsto (Granel) mensal:", placeholder="Ex: 100 ou 100 kgs", key=f"cons_granel_{rcc}")

                if tipo_fornecimento in ["Cilindro", "Ambos"]:
                    st.markdown("**Preço Cilindro por Modelo:**")
                    col_cp1, col_cp2, col_cp3 = st.columns(3)
                    with col_cp1: p13_val = st.text_input("Preço P13 (R$):", key=f"p13_v_{rcc}")
                    with col_cp2: p20_val = st.text_input("Preço P20 (R$):", key=f"p20_v_{rcc}")
                    with col_cp3: p45_val = st.text_input("Preço P45 (R$):", key=f"p45_v_{rcc}")

                    st.markdown("**Consumo previsto (Cilindro) mensal:**")
                    tab_c1, tab_c2 = st.tabs(["Preenchimento por Quantidade de Cilindros", "Preenchimento Direto em KGs"])
                    with tab_c1:
                        col_cc1, col_cc2, col_cc3 = st.columns(3)
                        with col_cc1: p13_qtd = st.number_input("Qtd Cilindros P13", min_value=0, value=0, step=1, key=f"p13_q_{rcc}")
                        with col_cc2: p20_qtd = st.number_input("Qtd Cilindros P20", min_value=0, value=0, step=1, key=f"p20_q_{rcc}")
                        with col_cc3: p45_qtd = st.number_input("Qtd Cilindros P45", min_value=0, value=0, step=1, key=f"p45_q_{rcc}")
                        
                        consumo_cilindro_total_calc = (p13_qtd * 13) + (p20_qtd * 20) + (p45_qtd * 45)
                        if consumo_cilindro_total_calc > 0:
                            st.info(f"💡 Consumo Calculado em KGs: **{consumo_cilindro_total_calc} kgs** (P13={p13_qtd}*13 + P20={p20_qtd}*20 + P45={p45_qtd}*45)")

                    with tab_c2:
                        consumo_cilindro_input_kg = st.text_input("Qual consumo previsto (Cilindro) mensal em kgs:", placeholder="Ex: 130 kgs", key=f"cons_cil_kg_{rcc}")

                col_cc_out1, col_cc_out2 = st.columns(2)
                with col_cc_out1:
                    cond_pagamento = st.text_input("Condição de pagamento:", key=f"cond_pag_{rcc}")
                with col_cc_out2:
                    vigencia = st.text_input("Vigência:", key=f"vigencia_{rcc}")

                st.divider()

                # [BLOCO 05] Financeiro
                st.subheader("[BLOCO 05] Financeiro")
                col_fin1, col_fin2 = st.columns(2)
                with col_fin1:
                    possui_debito_fin = st.radio("Possui NF's Pendentes?", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rcc}")
                    resp_pendentes = ""
                    if possui_debito_fin == "Sim":
                        resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", key=f"resp_pend_{rcc}")

                with col_fin2:
                    tipo_fluxo = st.radio("Objetivo da solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, index=None, key=f"fluxo_c_{rcc}")

                email_novo_prop = ""
                nome_testemunha, email_testemunha = "", ""
                responsaveis_dados = []

                if tipo_fluxo == "Gerar Minuta":
                    st.markdown("---")
                    st.markdown("**Dados para Minuta:**")
                    email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato:", key=f"email_novo_{rcc}")

                elif tipo_fluxo == "Enviar para Assinatura":
                    st.markdown("---")
                    st.markdown("**Dados para Assinatura:**")
                    col_t1, col_t2 = st.columns(2)
                    with col_t1: nome_testemunha = st.text_input("Nome da Testemunha:", key=f"nome_test_{rcc}")
                    with col_t2: email_testemunha = st.text_input("E-mail da Testemunha:", key=f"email_test_{rcc}")

                    qtd_responsaveis = st.selectbox("Quantidade de Responsáveis pela Assinatura:", [1, 2, 3, 4], index=0, key=f"qtd_resp_{rcc}")
                    for i in range(1, qtd_responsaveis + 1):
                        col_r1, col_r2 = st.columns(2)
                        with col_r1: n_r = st.text_input(f"Nome do Responsável pela assinatura {i:02d}:", key=f"nome_resp_{i}_{rcc}")
                        with col_r2: e_r = st.text_input(f"E-mail do Responsável pela assinatura {i:02d}:", key=f"email_resp_{i}_{rcc}")
                        responsaveis_dados.append({"nome": n_r, "email": e_r})

                st.divider()

                # [BLOCO 06] Condomínio
                st.subheader("[BLOCO 06] Condomínio")
                conta_sim = st.radio("Condomínio:", ["Não", "Coletivo", "CONTA.SIM"], horizontal=True, index=None, key=f"conta_sim_{rcc}")
                num_unidades, qtd_torres, qtd_blocos, preco_religue, preco_servico = "", "", "", "", ""

                if conta_sim == "CONTA.SIM":
                    col_cs1, col_cs2, col_cs3 = st.columns(3)
                    with col_cs1:
                        num_unidades = st.text_input("N° Unid autônomas (Aptos + áreas comuns/zeladoria):", key=f"num_unid_{rcc}")
                        qtd_torres = st.text_input("Qtd Torres:", key=f"qtd_torres_{rcc}")
                    with col_cs2:
                        qtd_blocos = st.text_input("Qtd Blocos:", key=f"qtd_blocos_{rcc}")
                        preco_religue = st.text_input("Valor preço de religue: R$", key=f"preco_rel_{rcc}")
                    with col_cs3:
                        preco_servico = st.text_input("Valor preço de serviço: R$", key=f"preco_serv_{rcc}")

                st.divider()

                if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
                    lines_out = []

                    # Orientações finais (Minuta)
                    if tipo_fluxo == "Gerar Minuta":
                        lines_out.append("**FAVOR GERAR MINUTA PARA ENVIO AO CLIENTE**\n")

                    # BLOCO 01
                    if motivo_solicitacao.strip():
                        lines_out.append("[BLOCO 01] Motivo da Elaboração / Regularização")
                        lines_out.append(f"Descreva claramente o motivo da regularização do contrato: {motivo_solicitacao.strip()}\n")

                    # BLOCO 02
                    b2_lines = []
                    if tipo_contrato:
                        b2_lines.append(f"Contrato / Aditamento / Distrato: {tipo_contrato}")
                    if requisicao_opt:
                        b2_lines.append(f"Requisição: {requisicao_opt}")
                    if mesmo_prop_opt:
                        b2_lines.append(f"Mesmo proprietário?: {mesmo_prop_opt}")
                        if mesmo_prop_opt == "Sim":
                            if cnpj_campo_val.strip(): b2_lines.append(f"Novo CNPJ: {cnpj_campo_val.strip()}")
                            if ie_campo_val.strip(): b2_lines.append(f"Nova I.E.: {ie_campo_val.strip()}")
                        elif mesmo_prop_opt == "Não":
                            if cnpj_campo_val.strip(): b2_lines.append(f"CNPJ: {cnpj_campo_val.strip()}")
                            if ie_campo_val.strip(): b2_lines.append(f"I.E.: {ie_campo_val.strip()}")
                    else:
                        if cnpj_campo_val.strip(): b2_lines.append(f"CNPJ: {cnpj_campo_val.strip()}")
                        if ie_campo_val.strip(): b2_lines.append(f"I.E.: {ie_campo_val.strip()}")

                    if razao_social_txt:
                        b2_lines.append(f"Razão Social (Consultada): {razao_social_txt}")
                    if status_cnpj_txt:
                        b2_lines.append(f"Status CNPJ: {status_cnpj_txt}")

                    if b2_lines:
                        lines_out.append("[BLOCO 02] Dados do Contrato")
                        lines_out.extend(b2_lines)
                        lines_out.append("")

                    # BLOCO 03
                    b3_lines = []
                    if endereco_padrao.strip():
                        b3_lines.append(f"Endereço padrão ou entrega?: {endereco_padrao.strip()}")
                    b3_lines.append(f"Quantidade de centrais / endereços: {qtd_entregas_c}")
                    
                    eq_filled = []
                    for i in range(1, int(qtd_entregas_c) + 1):
                        val_eq = eq_dict_c.get(i, "").strip()
                        if val_eq:
                            if qtd_entregas_c == 1:
                                eq_filled.append(f"Equipamentos: {val_eq}")
                            else:
                                eq_filled.append(f"Equipamentos Central {i:02d}: {val_eq}")

                    if eq_filled:
                        b3_lines.extend(eq_filled)

                    if b3_lines:
                        lines_out.append("[BLOCO 03] Endereço / Equipamentos")
                        lines_out.extend(b3_lines)
                        lines_out.append("")

                    # BLOCO 04
                    b4_lines = []
                    if tipo_fornecimento:
                        b4_lines.append(f"Tipo de Fornecimento: {tipo_fornecimento}")

                    if tipo_fornecimento in ["Granel", "Ambos"]:
                        if preco_granel.strip():
                            b4_lines.append(f"Preço Granel: {preco_granel.strip()}")
                        if consumo_granel_input.strip():
                            val_g_fmt = consumo_granel_input.strip()
                            if not re.search(r'(?i)\bkgs?\b', val_g_fmt):
                                val_g_fmt += " kgs"
                            b4_lines.append(f"Consumo previsto (Granel) mensal: {val_g_fmt}")

                    if tipo_fornecimento in ["Cilindro", "Ambos"]:
                        partes_cil = []
                        if p13_val.strip(): partes_cil.append(f"[P13 = {p13_val.strip()}]")
                        if p20_val.strip(): partes_cil.append(f"[P20 = {p20_val.strip()}]")
                        if p45_val.strip(): partes_cil.append(f"[P45 = {p45_val.strip()}]")
                        if partes_cil:
                            b4_lines.append(f"Preço Cilindro: {' '.join(partes_cil)}")

                        # Cilindro consumption
                        if consumo_cilindro_input_kg.strip():
                            val_c_fmt = consumo_cilindro_input_kg.strip()
                            if not re.search(r'(?i)\bkgs?\b', val_c_fmt):
                                val_c_fmt += " kgs"
                            b4_lines.append(f"Qual consumo previsto (Cilindro) mensal: {val_c_fmt}")
                        elif consumo_cilindro_total_calc > 0:
                            b4_lines.append(f"Qual consumo previsto (Cilindro) mensal: {consumo_cilindro_total_calc} kgs")

                    if cond_pagamento.strip():
                        b4_lines.append(f"Condição de pagamento: {cond_pagamento.strip()}")
                    if vigencia.strip():
                        b4_lines.append(f"Vigência: {vigencia.strip()}")

                    if b4_lines:
                        lines_out.append("[BLOCO 04] Condições Comerciais")
                        lines_out.extend(b4_lines)
                        lines_out.append("")

                    # BLOCO 05
                    b5_lines = []
                    if possui_debito_fin:
                        b5_lines.append(f"Possui NF's Pendentes: {possui_debito_fin}")
                        if possui_debito_fin == "Sim" and resp_pendentes.strip():
                            b5_lines.append(f"Quem será o responsável pelas NF's pendentes?: {resp_pendentes.strip()}")

                    if tipo_fluxo == "Gerar Minuta":
                        if email_novo_prop.strip():
                            b5_lines.append(f"E-mail do novo proprietário que receberá o novo contrato: {email_novo_prop.strip()}")
                    elif tipo_fluxo == "Enviar para Assinatura":
                        if nome_testemunha.strip():
                            b5_lines.append(f"Nome da Testemunha: {nome_testemunha.strip()}")
                        if email_testemunha.strip():
                            b5_lines.append(f"E-mail da Testemunha: {email_testemunha.strip()}")

                        for idx, resp in enumerate(responsaveis_dados, 1):
                            if resp["nome"].strip():
                                if len(responsaveis_dados) == 1:
                                    b5_lines.append(f"Nome do Responsável pela assinatura: {resp['nome'].strip()}")
                                else:
                                    b5_lines.append(f"Nome do Responsável pela assinatura {idx:02d}: {resp['nome'].strip()}")
                            if resp["email"].strip():
                                if len(responsaveis_dados) == 1:
                                    b5_lines.append(f"E-mail do Responsável pela assinatura: {resp['email'].strip()}")
                                else:
                                    b5_lines.append(f"E-mail do Responsável pela assinatura {idx:02d}: {resp['email'].strip()}")

                    if b5_lines:
                        lines_out.append("[BLOCO 05] Financeiro")
                        lines_out.extend(b5_lines)
                        lines_out.append("")

                    # BLOCO 06
                    b6_lines = []
                    if conta_sim:
                        b6_lines.append(f"Condomínio: {conta_sim}")
                        if conta_sim == "CONTA.SIM":
                            if num_unidades.strip(): b6_lines.append(f"N° Unid autônomas (Aptos + áreas comuns/zeladoria): {num_unidades.strip()}")
                            if qtd_torres.strip(): b6_lines.append(f"Qtd Torres: {qtd_torres.strip()}")
                            if qtd_blocos.strip(): b6_lines.append(f"Qtd Blocos: {qtd_blocos.strip()}")
                            if preco_religue.strip(): b6_lines.append(f"Valor preço de religue: R$ {preco_religue.strip()}")
                            if preco_servico.strip(): b6_lines.append(f"Valor preço de serviço: R$ {preco_servico.strip()}")

                    if b6_lines:
                        lines_out.append("[BLOCO 06] Condomínio")
                        lines_out.extend(b6_lines)

                    texto_padrao_contrato = "\n".join(lines_out).strip()

                    st.success("✅ Texto padrão gerado com sucesso!")
                    st.text_area("Texto Gerado:", value=texto_padrao_contrato, height=350, key=f"txt_area_contrato_{rcc}")
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

                # BLOCO 01 - Motivo
                st.subheader("1. Motivo")
                motivo_reg = st.text_input("Motivo da regularização *", key=f"ap_motivo_{rcap}")
                
                st.divider()

                # BLOCO 02 - Contato
                st.subheader("2. Informações de Contato")
                c_ap1, c_ap2, c_ap3 = st.columns(3)
                with c_ap1: contato_ap = st.text_input("Contato *", key=f"ap_cont_{rcap}")
                with c_ap2: telefone_ap = st.text_input("Telefone *", key=f"ap_tel_{rcap}")
                with c_ap3: email_ap = st.text_input("E-mail *", key=f"ap_email_{rcap}")
                
                c_ap4, c_ap5 = st.columns(2)
                with c_ap4: 
                    atualizar_email = st.radio("Atualizar E-mail? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_atu_email_{rcap}")
                
                novo_email_ap = ""
                if atualizar_email == "Sim":
                    novo_email_ap = st.text_input("Novo E-mail *", key=f"ap_novo_email_{rcap}")

                st.divider()

                # BLOCO 03 - Contrato / Equipamentos
                st.subheader("3. Dados do Contrato")
                c_ap6, c_ap7 = st.columns(2)
                with c_ap6: contrato_adit = st.radio("Contrato / Aditamento *", ["Contrato", "Aditamento"], horizontal=True, index=None, key=f"ap_tp_cont_{rcap}")
                with c_ap7: vigencia_ap = st.text_input("Vigência *", key=f"ap_vig_{rcap}")

                qtd_entregas_ap = st.number_input("Quantidade de endereços/centrais", min_value=1, value=1, step=1, key=f"qtd_ent_ap_{rcap}")
                equipamentos_ap = ""
                eq_dict_ap = {}
                if qtd_entregas_ap == 1:
                    equipamentos_ap = st.text_input("Equipamentos *", key=f"ap_eq_{rcap}")
                else:
                    st.markdown("**Equipamentos por Endereço de Entrega:**")
                    for i in range(1, int(qtd_entregas_ap) + 1):
                        eq_dict_ap[i] = st.text_input(f"Equipamentos - [Entrega {i}] *", key=f"ap_eq_ent_{i}_{rcap}")

                especificidade_ap = st.text_input("Existe especificidade sobre a solicitação? *", key=f"ap_esp_{rcap}")

                st.divider()

                # BLOCO 04 - Redimensionamento e Projetos Iniciais
                st.subheader("4. Redimensionamento")
                redim = st.radio("Redimensionamento: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_redim_{rcap}")
                projeto_num_bloco4 = ""
                comodato_de, comodato_para, inc_tanques, env_pecas = "", "", "Não", "Não"
                
                if redim == "Sim":
                    projeto_num_bloco4 = st.text_input("Projeto (Informe o número completo do projeto):", key=f"ap_proj4_{rcap}")
                    
                    c_p1, c_p2 = st.columns(2)
                    with c_p1: comodato_de = st.text_input("Comodato passou de:", key=f"ap_com_de_{rcap}")
                    with c_p2: comodato_para = st.text_input("Para:", key=f"ap_com_para_{rcap}")
                    
                    c_p3, c_p4 = st.columns(2)
                    with c_p3: inc_tanques = st.radio("Inclusão de tanques?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_inc_tanq_{rcap}")
                    with c_p4: env_pecas = st.radio("Necessário lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_env_pec_{rcap}")

                st.divider()

                # BLOCO 05 - Conta Sim e Portaria
                st.subheader("5. Condomínio Conta Sim & Portaria")
                implantacao_csim = st.radio("Implantação de conta sim: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_{rcap}")
                env_pecas_ficha, tp_portaria, contato_resp_port, part_local, contato_sindico = "Não", "", "", "", ""
                
                if implantacao_csim == "Sim":
                    env_pecas_ficha = st.radio("Foi enviado lista de peças e ficha de clientes?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_pec_ficha_{rcap}")
                    tp_portaria = st.text_input("Tipo de portaria", key=f"ap_tp_port_{rcap}")
                    contato_resp_port = st.text_input("Contato do responsável (nº ap ou contato remota)", key=f"ap_cont_resp_{rcap}")
                    part_local = st.text_input("Particularidades do local", key=f"ap_part_local_{rcap}")
                    contato_sindico = st.text_input("Contato atualizado do síndico", key=f"ap_cont_sind_{rcap}")

                st.divider()

                # BLOCO 06 - Alteração de CNPJ / Títulos em Aberto
                st.subheader("6. Alteração de CNPJ & Títulos em Aberto")
                alt_cnpj = st.radio("Alteração de CNPJ ou razão social? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_alt_cnpj_{rcap}")
                mesmo_prop_opt = st.radio("Se trata do mesmo proprietário: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_mesmo_prop_{rcap}")
                possui_titulos_aberto = st.radio("Possui títulos em aberto? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_tit_aberto_{rcap}")
                
                neg_tit_input = ""
                if possui_titulos_aberto == "Sim":
                    neg_tit_input = st.text_input("Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto:", key=f"ap_neg_tit_{rcap}")

                st.divider()

                # BLOCO 07 - Projeto Geral
                st.subheader("7. Projeto")
                projeto_num_bloco7 = st.text_input("Projeto (Informe o número completo do projeto): *", key=f"ap_proj7_{rcap}")

                st.divider()
                
                # BLOCO 08 - Redução de Vigência
                st.subheader("8. Redução de Vigência")
                red_vig = st.radio("Redução de vigência? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_red_vig_{rcap}")
                motivo_red_vig = ""
                if red_vig == "Sim":
                    motivo_red_vig = st.text_input("(Se sim, descreva o motivo):", key=f"ap_mot_red_{rcap}")

                st.divider()

                if st.button("📝 Gerar Texto de Aprovação de Contrato", type="primary"):
                    
                    # ---------------- VALIDAÇÃO ----------------
                    campos_faltantes = []
                    if not motivo_reg.strip(): campos_faltantes.append("Motivo da regularização")
                    if not contato_ap.strip(): campos_faltantes.append("Contato")
                    if not telefone_ap.strip(): campos_faltantes.append("Telefone")
                    if not email_ap.strip(): campos_faltantes.append("E-mail")
                    
                    if not atualizar_email: 
                        campos_faltantes.append("Atualizar E-mail?")
                    elif atualizar_email == "Sim" and not novo_email_ap.strip(): 
                        campos_faltantes.append("Novo E-mail")
                        
                    if not contrato_adit: campos_faltantes.append("Contrato / Aditamento")
                    if not vigencia_ap.strip(): campos_faltantes.append("Vigência")
                    
                    eq_ap_texto = ""
                    if qtd_entregas_ap == 1:
                        if not equipamentos_ap.strip(): campos_faltantes.append("Equipamentos")
                        eq_ap_texto = equipamentos_ap.strip()
                    else:
                        eq_ap_linhas = []
                        for i in range(1, int(qtd_entregas_ap) + 1):
                            val_e = eq_dict_ap[i].strip()
                            if not val_e:
                                campos_faltantes.append(f"Equipamentos [Entrega {i}]")
                            else:
                                eq_ap_linhas.append(f"[Entrega {i}] {val_e}")
                        eq_ap_texto = " ".join(eq_ap_linhas)

                    if not especificidade_ap.strip(): campos_faltantes.append("Existe especificidade sobre a solicitação")
                    if not redim: campos_faltantes.append("Redimensionamento")
                    if not implantacao_csim: campos_faltantes.append("Implantação de conta sim")
                    if not alt_cnpj: campos_faltantes.append("Alteração de CNPJ ou razão social?")
                    if not mesmo_prop_opt: campos_faltantes.append("Se trata do mesmo proprietário")
                    if not possui_titulos_aberto: campos_faltantes.append("Possui títulos em aberto?")
                    if not projeto_num_bloco7.strip(): campos_faltantes.append("Projeto (Bloco 07)")
                    if not red_vig: campos_faltantes.append("Redução de vigência?")

                    if campos_faltantes:
                        st.error("⚠️ Não foi possível gerar o texto. Preencha as seguintes informações primárias obrigatórias:\n\n- " + "\n- ".join(campos_faltantes))
                    else:
                        # ---------------- GERAÇÃO DO TEXTO DINÂMICO ----------------
                        def sim_nao_box(val):
                            if val == "Sim": return "[ x ] sim [   ] não"
                            elif val == "Não": return "[   ] sim [ x ] não"
                            return "[   ] sim [   ] não"

                        def sim_nao_parentheses(val):
                            if val == "Sim": return "( X ) SIM (   ) NÃO"
                            elif val == "Não": return "(   ) SIM ( X ) NÃO"
                            return "(   ) SIM (   ) NÃO"

                        def sim_nao_parentheses_lower(val):
                            if val == "Sim": return "( x ) sim (   ) não"
                            elif val == "Não": return "(   ) sim ( x ) não"
                            return "(   ) sim (   ) não"

                        linhas_texto = []
                        
                        # [BLOCO 01]
                        linhas_texto.append(f"Motivo da regularização: {motivo_reg.strip()}")
                        linhas_texto.append("")
                        
                        # [BLOCO 02]
                        linhas_texto.append(f"Contato: {contato_ap.strip()}")
                        linhas_texto.append(f"Telefone: {telefone_ap.strip()}")
                        linhas_texto.append(f"E-mail: {email_ap.strip()}")
                        if atualizar_email == "Sim":
                            linhas_texto.append(f"Atualizar E-mail? {sim_nao_box(atualizar_email)} - Novo E-mail: {novo_email_ap.strip()}")
                        else:
                            linhas_texto.append(f"Atualizar E-mail? {sim_nao_box(atualizar_email)}")
                        linhas_texto.append("")
                        
                        # [BLOCO 03]
                        linhas_texto.append(f"Contrato / Aditamento: {contrato_adit}")
                        linhas_texto.append(f"Vigência: {vigencia_ap.strip()}")
                        linhas_texto.append(f"Equipamentos: {eq_ap_texto}")
                        linhas_texto.append(f"Existe especificidade sobre a solicitação: {especificidade_ap.strip()}")
                        linhas_texto.append("")

                        # [BLOCO 04]
                        linhas_texto.append(f"Redimensionamento: {sim_nao_box(redim)}")
                        if redim == "Sim":
                            linhas_texto.append(f"Projeto (Informe o número completo do projeto): {projeto_num_bloco4.strip()}")
                            linhas_texto.append(f"Comodato passou de: {comodato_de.strip()}")
                            linhas_texto.append(f"Para: {comodato_para.strip()}")
                            linhas_texto.append(f"Inclusão de tanques? {sim_nao_box(inc_tanques)}")
                            linhas_texto.append(f"Necessário lista de peças? {sim_nao_box(env_pecas)} (se sim, enviar lista de peças)")
                        linhas_texto.append("")

                        # [BLOCO 05]
                        linhas_texto.append(f"Implantação de conta sim: {sim_nao_box(implantacao_csim)}")
                        if implantacao_csim == "Sim":
                            linhas_texto.append(f"Foi enviado lista de peças e ficha de clientes ? {sim_nao_box(env_pecas_ficha)}")
                            linhas_texto.append(f"Tipo de portaria: {tp_portaria.strip()}")
                            linhas_texto.append(f"Contato do responsável (em caso de portaria remota, informar o número do apartamento ou a forma de contato do responsável): {contato_resp_port.strip()}")
                            linhas_texto.append(f"Particularidades do local: {part_local.strip()}")
                            linhas_texto.append(f"Contato atualizado do síndico: {contato_sindico.strip()}")
                        linhas_texto.append("")

                        # [BLOCO 06]
                        linhas_texto.append(f"Alteração de CNPJ ou razão social? {sim_nao_box(alt_cnpj)}")
                        linhas_texto.append(f"Se trata do mesmo proprietário: {sim_nao_parentheses(mesmo_prop_opt)}")
                        linhas_texto.append(f"Possui títulos em aberto {sim_nao_parentheses_lower(possui_titulos_aberto)}")
                        if possui_titulos_aberto == "Sim":
                            linhas_texto.append(f"Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto: {neg_tit_input.strip()}")
                        linhas_texto.append("")

                        # [BLOCO 07]
                        linhas_texto.append(f"Projeto (Informe o número completo do projeto): {projeto_num_bloco7.strip()}")
                        linhas_texto.append("")

                        # [BLOCO 08]
                        linhas_texto.append(f"Redução de vigência? {sim_nao_box(red_vig)}")
                        if red_vig == "Sim":
                            linhas_texto.append(f"(Se sim, descreva o motivo): {motivo_red_vig.strip()}")

                        texto_aprovacao = "\n".join(linhas_texto)

                        st.success("✅ Texto de Aprovação gerado com sucesso!")
                        st.text_area("Texto Gerado:", value=texto_aprovacao, height=500, key=f"txt_area_aprov_{rcap}")
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
                    st.success(f"📊 **IPCA Acumulado de 12 meses (Fonte oficial, referência {ipca_periodo}):** `{ipca_vigente:.2f}%`")
                else:
                    ipca_vigente = st.number_input("IPCA acumulado de 12 meses (%) - informado manualmente", min_value=0.0, value=4.58, step=0.01, format="%.2f", key=f"ipca_manual_{rca}")

                col_an1, col_an2 = st.columns(2)
                with col_an1: preco_anterior_input = st.text_input("Preço Anterior (R$)", value="7,7400", key=f"preco_ant_{rca}")
                with col_an2: clausula_contrato = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, index=None, key=f"clausula_{rca}")

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
                    
                    col_v1, col_v2 = st.columns([1, 2])
                    with col_v1:
                        st.text_input("Preço Novo para Abertura da CI:", value=f"R$ {p_aniv_str}", disabled=False, key=f"valor_novo_ci_{rca}")
                    with col_v2:
                        st.write(""); st.write("")
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
# ABA 2: AGENDA DE OCORRÊNCIAS (SEPARADA POR PERFIL)
# =====================================================================
if aba_agenda is not None:
    with aba_agenda:
        COL_OCORRENCIA = "Número da ocorrência"
        COL_CLIENTE = "Nome do cliente"
        COL_ENDERECO = "Endereço de Entrega"
        COL_ABERTURA = "Data/Hora de abertura"
        COL_PRAZO = "Prazo de Atendimento"
        COL_FECHAMENTO = "Data/Hora de fechamento"
        COL_SUB_CLASSIF = "Subclassificação Ocorrência"
        COL_PROPRIETARIO = "Proprietário da ocorrência"

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

        def limpar_classificacao(texto):
            if pd.isna(texto):
                return "-"
            texto_limpo = re.sub(r'\[.*?\]', '', str(texto)).strip()
            return texto_limpo if texto_limpo else str(texto)

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
                return "🔴"
            elif dias_uteis == 0:
                return "🔵"
            elif dias_uteis == 1:
                return "🟠"
            elif 2 <= dias_uteis <= 5:
                return "🟡"
            else:
                return "🟢"

        col_menu_agenda, col_conteudo_agenda = st.columns([1, 4])

        with col_menu_agenda:
            st.markdown("### 📌 Menu de Ocorrências")
            arquivo_excel = st.file_uploader(
                "📂 Importar Planilha Excel", 
                type=["xlsx", "xls"],
                key="uploader_agenda_excel_novo"
            )
            
            st.divider()
            
            opcoes_visao = ["Todas Ocorrências", "Comodato Inativo", "Ocorrências por Cidade"]
            if st.session_state.e_supervisor:
                opcoes_visao.append("📊 Dashboard de Gestão (Gráficos)")
                opcoes_visao.append("📈 Ocorrências por Classificação")

            tipo_visao_agenda = st.radio(
                "Visualização:",
                opcoes_visao,
                label_visibility="collapsed"
            )

            st.divider()
            st.markdown("### 🏷️ Legenda de Status")
            st.markdown("🔴 **Vencido**")
            st.markdown("🔵 **Vence Hoje**")
            st.markdown("🟠 **Vence Amanhã**")
            st.markdown("🟡 **Vence em 05 dias**")
            st.markdown("🟢 **No Prazo**")

        with col_conteudo_agenda:
            cabecalho_pagina("Módulo de Pós-Vendas & Atendimento", "Sistema Integrado de Gestão de Ocorrências por Prazos, SLAs e Geografia")

            if arquivo_excel is not None:
                try:
                    df = ler_arquivo_excel_robusto(arquivo_excel)
                        
                    df.columns = [str(c).strip() for c in df.columns]
                    
                    if COL_OCORRENCIA not in df.columns:
                        for idx_r, row in df.iterrows():
                            row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
                            if COL_OCORRENCIA in row_str:
                                df.columns = [str(c).strip() for c in df.iloc[idx_r].values]
                                df = df.iloc[idx_r+1:].reset_index(drop=True)
                                break

                    if COL_OCORRENCIA not in df.columns:
                        st.error(f"❌ A coluna obrigatória '{COL_OCORRENCIA}' não foi encontrada no arquivo. Verifique se o relatório está correto.")
                        st.stop()

                    df = df.dropna(subset=[COL_OCORRENCIA])
                    
                    df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
                    df_pendentes[COL_OCORRENCIA] = pd.to_numeric(df_pendentes[COL_OCORRENCIA], errors='coerce')
                    df_pendentes = df_pendentes.dropna(subset=[COL_OCORRENCIA])
                    df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
                    
                    df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
                    df_pendentes['Abertura_DT'] = pd.to_datetime(df_pendentes[COL_ABERTURA], format="%d/%m/%Y %H:%M", errors='coerce')
                    df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
                    
                    df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
                    df_pendentes['Classificação Limpa'] = df_pendentes[COL_SUB_CLASSIF].apply(limpar_classificacao)
                    
                    if st.session_state.e_supervisor:
                        if COL_PROPRIETARIO in df_pendentes.columns:
                            df_pendentes['Consultor'] = df_pendentes[COL_PROPRIETARIO].fillna("Não Atribuído").astype(str)
                        elif 'Vendedor/Consultor' in df_pendentes.columns:
                            df_pendentes['Consultor'] = df_pendentes['Vendedor/Consultor'].fillna("Não Atribuído").astype(str)
                        else:
                            df_pendentes['Consultor'] = "Geral"
                    else:
                        df_pendentes['Consultor'] = "Geral"

                    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    df_pendentes['SLA'] = df_pendentes['Prazo_DT'].apply(lambda x: calcular_dias_uteis(hoje, x))
                    df_pendentes['Status Geral'] = df_pendentes['SLA'].apply(classificar_status_geral)
                    df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)

                    df_base_visao = df_pendentes.copy()

                    # --- DASHBOARD UNIFICADO DE GESTÃO (GRÁFICOS 02 POR LINHA) PARA SUPERVISOR ---
                    if st.session_state.e_supervisor and tipo_visao_agenda == "📊 Dashboard de Gestão (Gráficos)":
                        st.subheader("📊 Dashboard Executivo de Gestão - Indicadores por Consultor")
                        st.markdown("Visão consolidada, limpa e profissional dos prazos e SLAs por consultor.")
                        st.write("")

                        graficos_config = [
                            ("🔴 Ocorrências Vencidas por Consultor", df_base_visao[df_base_visao['SLA'] < 0], "#D32F2F"),
                            ("🔵 Vencimento Hoje por Consultor", df_base_visao[df_base_visao['SLA'] == 0], "#1976D2"),
                            ("🟠 Vencimento Amanhã por Consultor", df_base_visao[df_base_visao['SLA'] == 1], "#F57C00"),
                            ("🟡 Vencimento em até 05 Dias por Consultor", df_base_visao[(df_base_visao['SLA'] >= 2) & (df_base_visao['SLA'] <= 5)], "#FBC02D"),
                            ("🟢 No Prazo por Consultor", df_base_visao[df_base_visao['SLA'] > 0], "#388E3C"),
                        ]

                        for i in range(0, len(graficos_config), 2):
                            col_g1, col_g2 = st.columns(2)
                            
                            with col_g1:
                                titulo_1, df_g1, cor_tema_1 = graficos_config[i]
                                st.markdown(f"#### {titulo_1}")
                                if not df_g1.empty:
                                    df_ag_1 = df_g1.groupby('Consultor').size().reset_index(name='Total')
                                    df_ag_1 = df_ag_1.sort_values(by='Total', ascending=False)
                                    chart_1 = alt.Chart(df_ag_1).mark_bar(
                                        color=cor_tema_1, cornerRadiusTopLeft=6, cornerRadiusTopRight=6
                                    ).encode(
                                        x=alt.X('Total:Q', title='Total de Ocorrências'),
                                        y=alt.Y('Consultor:N', sort='-x', title='Consultor'),
                                        tooltip=['Consultor', 'Total']
                                    ).properties(height=240)
                                    st.altair_chart(chart_1, use_container_width=True)
                                    st.dataframe(df_ag_1.rename(columns={'Total': 'Qtd Ocorrências'}), hide_index=True, use_container_width=True)
                                else:
                                    st.info("Nenhum registro para este critério.")
                            
                            if i + 1 < len(graficos_config):
                                with col_g2:
                                    titulo_2, df_g2, cor_tema_2 = graficos_config[i + 1]
                                    st.markdown(f"#### {titulo_2}")
                                    if not df_g2.empty:
                                        df_ag_2 = df_g2.groupby('Consultor').size().reset_index(name='Total')
                                        df_ag_2 = df_ag_2.sort_values(by='Total', ascending=False)
                                        chart_2 = alt.Chart(df_ag_2).mark_bar(
                                            color=cor_tema_2, cornerRadiusTopLeft=6, cornerRadiusTopRight=6
                                        ).encode(
                                            x=alt.X('Total:Q', title='Total de Ocorrências'),
                                            y=alt.Y('Consultor:N', sort='-x', title='Consultor'),
                                            tooltip=['Consultor', 'Total']
                                        ).properties(height=240)
                                        st.altair_chart(chart_2, use_container_width=True)
                                        st.dataframe(df_ag_2.rename(columns={'Total': 'Qtd Ocorrências'}), hide_index=True, use_container_width=True)
                                    else:
                                        st.info("Nenhum registro para este critério.")
                            
                            st.divider()
                        st.stop()

                    # --- VISÃO: OCORRÊNCIAS POR CLASSIFICAÇÃO (SUPERVISOR) ---
                    elif tipo_visao_agenda == "📈 Ocorrências por Classificação":
                        st.subheader("📈 Gestão de Ocorrências por Classificação")
                        
                        if st.session_state.e_supervisor:
                            lista_cons_class = ["Todos"] + sorted(list(df_base_visao['Consultor'].unique()))
                            cons_sel_class = st.selectbox("Filtrar por Consultor:", lista_cons_class, key="sel_cons_class")
                            if cons_sel_class != "Todos":
                                df_class_vis = df_base_visao[df_base_visao['Consultor'] == cons_sel_class]
                            else:
                                df_class_vis = df_base_visao.copy()
                        else:
                            df_class_vis = df_base_visao.copy()

                        if df_class_vis.empty:
                            st.info("Nenhum registro encontrado para os filtros selecionados.")
                        else:
                            df_class_agrup = df_class_vis.groupby('Classificação Limpa').size().reset_index(name='Total')
                            df_class_agrup = df_class_agrup.sort_values(by='Total', ascending=False)

                            col_tabela_class, col_grafico_class = st.columns(2)
                            
                            with col_tabela_class:
                                st.markdown("#### 📋 Quantitativo por Classificação")
                                df_tabela_ex = df_class_agrup.rename(columns={'Classificação Limpa': 'Classificação', 'Total': 'Qtd Ocorrências'})
                                st.dataframe(df_tabela_ex, hide_index=True, use_container_width=True)
                                
                            with col_grafico_class:
                                st.markdown("#### 📊 Gráfico Comparativo")
                                chart_class = alt.Chart(df_class_agrup).mark_bar(
                                    color="#0055A5", cornerRadiusTopLeft=6, cornerRadiusTopRight=6
                                ).encode(
                                    x=alt.X('Total:Q', title='Quantidade de Ocorrências'),
                                    y=alt.Y('Classificação Limpa:N', sort='-x', title='Classificação'),
                                    tooltip=['Classificação Limpa', 'Total']
                                ).properties(height=350)
                                st.altair_chart(chart_class, use_container_width=True)
                                
                        st.stop()

                    # --- VISÃO: OCORRÊNCIAS POR CIDADE ---
                    elif tipo_visao_agenda == "Ocorrências por Cidade":
                        st.subheader("🏙️ Ocorrências por Cidade")
                        cidades_unicas = sorted(list(df_base_visao['Cidade'].unique()))
                        cidade_sel = st.selectbox("Selecione a Cidade:", cidades_unicas)
                        
                        col_tabela_cidade, col_grafico_cidade = st.columns(2)
                        
                        with col_tabela_cidade:
                            st.markdown(f"**Tabela Consolidada por Cidade**")
                            df_mapa_agrup = df_base_visao.groupby('Cidade').size().reset_index(name='Total Ocorrências')
                            st.dataframe(df_mapa_agrup.sort_values(by='Total Ocorrências', ascending=False), hide_index=True, use_container_width=True)
                            
                        with col_grafico_cidade:
                            st.markdown("**Gráfico de OCs por Cidade**")
                            chart = alt.Chart(df_mapa_agrup).mark_bar(color="#0055A5", cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                                x=alt.X('Cidade:N', sort='-y', title='Cidade'),
                                y=alt.Y('Total Ocorrências:Q', title='Qtd Ocorrências'),
                                tooltip=['Cidade', 'Total Ocorrências']
                            ).properties(height=280)
                            st.altair_chart(chart, use_container_width=True)
                            
                        st.stop()

                    # --- OUTRAS VISÕES ---
                    if tipo_visao_agenda == "Comodato Inativo":
                        df_base_visao = df_base_visao[df_base_visao['Classificação Limpa'].str.contains("Comodato Inativo", case=False, na=False)]
                        st.subheader("⚠️ Relatório Específico: Comodato Inativo")
                    else:
                        st.subheader("2. Agenda Geral de Visitas Pendentes")

                    # --- BOTÕES DE FILTRO RÁPIDO SUPERIORES COM DESTAQUE NUMÉRICO ---
                    st.markdown("### Filtros por Status e Prazos")
                    
                    total_visitas = len(df_base_visao)
                    vencidas_qt = len(df_base_visao[df_base_visao['SLA'] < 0])
                    hoje_qt = len(df_base_visao[df_base_visao['SLA'] == 0])
                    amanha_qt = len(df_base_visao[df_base_visao['SLA'] == 1])
                    cinco_dias_qt = len(df_base_visao[(df_base_visao['SLA'] >= 2) & (df_base_visao['SLA'] <= 5)])

                    c1, c2, c3, c4, c5 = st.columns(5)
                    with c1:
                        if st.button(f"📋 **{total_visitas}**\nTodas", use_container_width=True):
                            st.session_state.filtro_dashboard_ativo = "Todas"
                    with c2:
                        if st.button(f"🔴 **{vencidas_qt}**\nVencido", use_container_width=True):
                            st.session_state.filtro_dashboard_ativo = "Vencidas"
                    with c3:
                        if st.button(f"🔵 **{hoje_qt}**\nVence Hoje", use_container_width=True):
                            st.session_state.filtro_dashboard_ativo = "Hoje"
                    with c4:
                        if st.button(f"🟠 **{amanha_qt}**\nVence Amanhã", use_container_width=True):
                            st.session_state.filtro_dashboard_ativo = "Amanhã"
                    with c5:
                        if st.button(f"🟡 **{cinco_dias_qt}**\nVence em 05 dias", use_container_width=True):
                            st.session_state.filtro_dashboard_ativo = "05 Dias"

                    st.caption(f"Filtro ativo de status: **{st.session_state.filtro_dashboard_ativo}**")
                    st.divider()

                    # --- FILTROS DE CONSULTOR, CIDADE E CLASSIFICAÇÃO ---
                    if st.session_state.e_supervisor:
                        col_fc1, col_fc2, col_fc3 = st.columns(3)
                        lista_consultores = ["Todos"] + sorted(list(df_base_visao['Consultor'].unique()))
                        lista_cidades_filtro = ["Todas"] + sorted(list(df_base_visao['Cidade'].unique()))
                        lista_class_filtro = ["Todas"] + sorted(list(df_base_visao['Classificação Limpa'].unique()))

                        with col_fc1:
                            consultor_sel = st.selectbox("Consultor:", lista_consultores)
                        with col_fc2:
                            cidade_filtro_sel = st.selectbox("Cidade:", lista_cidades_filtro)
                        with col_fc3:
                            class_filtro_sel = st.selectbox("Classificação:", lista_class_filtro)
                    else:
                        col_fc1, col_fc2 = st.columns(2)
                        lista_cidades_filtro = ["Todas"] + sorted(list(df_base_visao['Cidade'].unique()))
                        lista_class_filtro = ["Todas"] + sorted(list(df_base_visao['Classificação Limpa'].unique()))

                        with col_fc1:
                            cidade_filtro_sel = st.selectbox("Filtrar por Cidade:", lista_cidades_filtro)
                        with col_fc2:
                            class_filtro_sel = st.selectbox("Filtrar por Classificação:", lista_class_filtro)

                    df_filtrado = df_base_visao.copy()
                    if st.session_state.filtro_dashboard_ativo == "Vencidas":
                        df_filtrado = df_filtrado[df_filtrado['SLA'] < 0]
                    elif st.session_state.filtro_dashboard_ativo == "Hoje":
                        df_filtrado = df_filtrado[df_filtrado['SLA'] == 0]
                    elif st.session_state.filtro_dashboard_ativo == "Amanhã":
                        df_filtrado = df_filtrado[df_filtrado['SLA'] == 1]
                    elif st.session_state.filtro_dashboard_ativo == "05 Dias":
                        df_filtrado = df_filtrado[(df_filtrado['SLA'] >= 2) & (df_filtrado['SLA'] <= 5)]

                    if st.session_state.e_supervisor and consultor_sel != "Todos":
                        df_filtrado = df_filtrado[df_filtrado['Consultor'] == consultor_sel]
                    if cidade_filtro_sel != "Todas":
                        df_filtrado = df_filtrado[df_filtrado['Cidade'] == cidade_filtro_sel]
                    if class_filtro_sel != "Todas":
                        df_filtrado = df_filtrado[df_filtrado['Classificação Limpa'] == class_filtro_sel]

                    df_filtrado['Prazo'] = df_filtrado['Prazo_DT'].dt.strftime('%d/%m/%Y')

                    if df_filtrado.empty:
                        st.success("✅ Excelente! Não há nenhuma ocorrência pendente para os filtros selecionados.")
                    else:
                        if st.session_state.e_supervisor:
                            df_exibicao = df_filtrado[[
                                'Status Geral', 'SLA', COL_OCORRENCIA, COL_CLIENTE, 
                                'Cidade', 'Classificação Limpa', 'Prazo', 'Consultor'
                            ]].copy()
                            df_exibicao.columns = ['Status', 'SLA', 'Nº OC', 'Cliente', 'Cidade', 'Classificação', 'Prazo', 'Consultor']
                        else:
                            df_exibicao = df_filtrado[[
                                'Status Geral', 'SLA', COL_OCORRENCIA, COL_CLIENTE, 
                                'Cidade', 'Classificação Limpa', 'Prazo'
                            ]].copy()
                            df_exibicao.columns = ['Status', 'SLA', 'Nº OC', 'Cliente', 'Cidade', 'Classificação', 'Prazo']

                        df_exibicao['Nº OC'] = df_exibicao['Nº OC'].astype(str)
                        st.dataframe(df_exibicao, hide_index=True, use_container_width=True)

                except Exception as e:
                    st.error(f"⚠️ Ocorreu um erro ao processar o arquivo. Certifique-se de que é o relatório correto. Erro técnico: {e}")
            else:
                st.info("👆 Por favor, faça o upload da planilha atualizada de ocorrências no menu lateral esquerdo para carregar o dashboard.")


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
# PAINEL ADMIN / SUPERVISOR
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
                nivel_acesso = st.selectbox("Nível de Acesso", ["convencional", "supervisor", "admin"])
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
            nivel_txt = "Convencional"
            if v["nivel_acesso"] == "admin":
                nivel_txt = "Administrador"
            elif v["nivel_acesso"] == "supervisor":
                nivel_txt = "Supervisor"

            data_users.append({
                "Usuário": k,
                "Nível de Acesso": nivel_txt,
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
    st.session_state.e_supervisor = False
    st.session_state.troca_obrigatoria = False
    st.session_state.df_excel_agenda = None
    st.rerun()
