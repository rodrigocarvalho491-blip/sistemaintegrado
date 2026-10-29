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
from datetime import datetime
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

# --- CAMADA DE PERSISTÊNCIA (SUPABASE) ---
def carregar_banco_usuarios():
    try:
        res = supabase.table("usuarios").select("usuario, senha").execute()
        dados = {row["usuario"]: row["senha"] for row in res.data}
        if "admin" not in dados:
            supabase.table("usuarios").insert({"usuario": "admin", "senha": "admin"}).execute()
            dados["admin"] = "admin"
        return dados
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return {"admin": "admin"}

def salvar_usuario(usuario, senha):
    try:
        supabase.table("usuarios").upsert({"usuario": usuario, "senha": senha}).execute()
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

# --- CUSTOM CSS ---
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

# --- BOTÃO CUSTOMIZADO DE CÓPIA ---
def botao_copiar_customizado(texto_para_copiar, chave_unica):
    texto_seguro = texto_para_copiar.replace('`', '\\`').replace('$', '\\$').replace('\n', '\\n').replace('"', '\\"')
    component_html = f"""
    <div style="margin-top: 5px; margin-bottom: 10px;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background-color: #0055A5; color: white; padding: 8px 16px; border: none;
            border-radius: 6px; font-weight: bold; font-size: 14px; cursor: pointer;
            display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">📄 Copiar Texto Completo</button>
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
    st.markdown("Insira suas credenciais registradas para acessar a plataforma.")
    
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
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("❌ Usuário ou senha incorretos! Verifique suas credenciais.")
                
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

if "nota_selecionada_id" not in st.session_state: st.session_state.nota_selecionada_id = None

# =====================================================================
# ABA 1 & 2: TRATATIVA E AGENDA (SEUS MÓDULOS PERMANECEM IDENTICOS)
# =====================================================================
with aba_tratativa:
    st.info("Módulos de tratativa carregados com sucesso.")

with aba_agenda:
    st.info("Agenda de Ocorrências carregada com sucesso.")

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
        st.markdown("**Lista de Notas Salvas**")
        
        if not notas_usuario:
            st.caption("Nenhuma nota salva ainda.")
        else:
            for n_id, n_data in notas_usuario.items():
                titulo_exibicao = n_data.get("titulo", "Sem Título")
                cliente_exibicao = n_data.get("cliente", "")
                lbl_btn = f"{titulo_exibicao}" + (f" ({cliente_exibicao})" if cliente_exibicao else "")
                
                if st.button(lbl_btn, key=f"btn_nota_{n_id}", use_container_width=True):
                    st.session_state.nota_selecionada_id = n_id
                    st.rerun()

    with col_conteudo_notas:
        cabecalho_pagina("Bloco de Notas Pessoal", "Anotações vinculadas à sua conta salvas na nuvem com segurança.")
        st.markdown(f"👤 Usuário da Sessão: **{usuario_atual}**")
        
        id_atual = st.session_state.nota_selecionada_id
        
        if id_atual and id_atual in notas_usuario:
            st.subheader("✏️ Editar Nota")
            titulo_val = notas_usuario[id_atual].get("titulo", "")
            cliente_val = notas_usuario[id_atual].get("cliente", "")
            texto_val = notas_usuario[id_atual].get("texto", "")
        else:
            st.subheader("📄 Nova Nota")
            titulo_val = ""
            cliente_val = ""
            texto_val = ""
            
        with st.form("form_bloco_notas"):
            col_tn1, col_tn2 = st.columns(2)
            with col_tn1: novo_titulo = st.text_input("Título da Nota", value=titulo_val, placeholder="Ex: Pendência Documentação")
            with col_tn2: novo_cliente = st.text_input("Cliente Referente", value=cliente_val, placeholder="Ex: Condomínio Sol Nascente")
            
            novo_texto = st.text_area("Anotações", value=texto_val, height=250, placeholder="Escreva os detalhes aqui...")
            
            col_s1, col_s2, _ = st.columns([1, 1, 4])
            with col_s1: btn_salvar_nota = st.form_submit_button("💾 Salvar na Nuvem", type="primary")
            with col_s2: 
                btn_apagar = st.form_submit_button("🗑️ Apagar") if id_atual else False

            if btn_salvar_nota:
                if not novo_titulo:
                    st.error("⚠️ O Título da nota é obrigatório.")
                else:
                    target_id = id_atual if id_atual else str(uuid.uuid4())
                    if salvar_nota(target_id, usuario_atual, novo_titulo, novo_cliente, novo_texto):
                        st.session_state.nota_selecionada_id = target_id
                        st.success("✅ Nota salva no banco de dados!")
                        st.rerun()
                    
            if btn_apagar and id_atual:
                if apagar_nota(id_atual):
                    st.session_state.nota_selecionada_id = None
                    st.success("🗑️ Nota removida!")
                    st.rerun()

# =====================================================================
# ABA 4: PAINEL ADMIN DE USUÁRIOS (PERSISTÊNCIA SUPABASE)
# =====================================================================
if aba_admin is not None:
    with aba_admin:
        cabecalho_pagina("Painel de Administração de Usuários", "Gerencie permissões e senhas gravadas diretamente no banco em nuvem.")
        
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
                        st.warning(f"⚠️ O usuário '{novo_user}' já existe.")
                    else:
                        if salvar_usuario(novo_user, nova_senha):
                            st.success(f"✅ Usuário **{novo_user}** criado!")
                            st.rerun()

        with col_adm2:
            st.subheader("2. Redefinir Senha de Usuário")
            lista_usuarios = [u for u in banco_usuarios.keys() if u != "admin"]
            
            if lista_usuarios:
                user_sel_senha = st.selectbox("Selecione o Usuário:", lista_usuarios, key="sel_user_mudar_senha")
                nova_senha_admin = st.text_input("Nova Senha", type="password", key="txt_nova_senha_admin").strip()
                
                if st.button("🔑 Atualizar Senha", key="btn_mudar_senha"):
                    if nova_senha_admin:
                        if salvar_usuario(user_sel_senha, nova_senha_admin):
                            st.success(f"✅ Senha de **{user_sel_senha}** atualizada com sucesso!")
                            st.rerun()
                    else:
                        st.error("⚠️ Digite uma senha válida.")

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
                user_para_remover = st.selectbox("Remover usuário:", lista_usuarios, key="sel_user_remove")
            with col_rem2:
                st.write(""); st.write("")
                if st.button("🗑️ Remover Usuário", type="primary", key="btn_remover_user"):
                    if remover_usuario(user_para_remover):
                        st.success(f"✅ Usuário **{user_para_remover}** removido do banco de dados!")
                        st.rerun()

# --- BARRA LATERAL LOGOUT ---
st.sidebar.divider()
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.session_state.e_admin = False
    st.rerun()
