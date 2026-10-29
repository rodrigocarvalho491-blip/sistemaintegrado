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
        res = supabase.table("usuarios").select("*").execute()
        dados = {}
        for row in res.data:
            dados[row["usuario"]] = {
                "senha": row["senha"],
                "nivel_acesso": row.get("nivel_acesso", "convencional"),
                "precisa_trocar_senha": row.get("precisa_trocar_senha", False)
            }
        
        # Garante a existência do admin master
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

# --- BLINDAGEM: TROCA OBRIGATÓRIA DE SENHA NO PRIMEIRISSIMO ACESSO ---
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
        if menu_tratativa == "📷 Visita de Transferência":
            cabecalho_pagina("Visita de Transferência & Relatório Técnico", "Gerador automatizado de relatórios técnicos.")
            rc = st.session_state.reset_counter
            
            s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
            with s1_l1_c1: contato = st.text_input("Contato *", key=f"vis_cont_{rc}")
            with s1_l1_c2: depto = st.text_input("Sobrenome / Depto *", key=f"vis_dep_{rc}")
            with s1_l1_c3: tel = st.text_input("Telefone *", key=f"vis_tel_{rc}")
            
            obs = st.text_area("Observações Gerais", key=f"vis_obs_{rc}")
            if st.button("📝 Gerar Texto Visita", type="primary"):
                txt = f"Contato: {contato}\nDepartamento: {depto}\nTelefone: {tel}\nObs: {obs}"
                st.code(txt)
                botao_copiar_customizado(txt, "cop_vis")

        elif menu_tratativa == "📝 Elaboração de Contrato":
            cabecalho_pagina("Elaboração de Contrato", "Formulário para geração do padrão de solicitação de contrato.")
            rc = st.session_state.reset_counter
            
            col1, col2 = st.columns(2)
            with col1:
                motivo = st.text_input("Motivo da solicitação *", key=f"el_mot_{rc}")
                contato = st.text_input("Contato *", key=f"el_cnt_{rc}")
            with col2:
                tel = st.text_input("Telefone *", key=f"el_tel_{rc}")
                email = st.text_input("E-mail *", key=f"el_eml_{rc}")
                
            if st.button("📝 Gerar Texto Elaboração", type="primary"):
                txt = f"Motivo: {motivo}\nContato: {contato}\nTelefone: {tel}\nE-mail: {email}"
                st.code(txt)
                botao_copiar_customizado(txt, "cop_elab")

        elif menu_tratativa == "📋 Aprovação de Contrato":
            cabecalho_pagina("Aprovação de Contrato", "Formulário de solicitação de aprovação.")
            rc = st.session_state.reset_counter
            
            motivo = st.text_input("Motivo da regularização *", key=f"ap_mot_{rc}")
            proj = st.text_input("Número do Projeto", key=f"ap_proj_{rc}")
            
            if st.button("📝 Gerar Texto Aprovação", type="primary"):
                txt = f"Motivo Regularização: {motivo}\nProjeto: {proj}"
                st.code(txt)
                botao_copiar_customizado(txt, "cop_aprov")

        elif menu_tratativa == "🎂 Aniversário de Contrato":
            cabecalho_pagina("Aniversário de Contrato", "Calculadora de reajuste por IPCA acumulado de 12M.")
            ipca, periodo = obter_ipca_acumulado_12m()
            
            if ipca:
                st.success(f"📊 IPCA Acumulado 12M IBGE ({periodo}): `{ipca:.2f}%`")
                ipca_val = ipca
            else:
                ipca_val = st.number_input("IPCA Manual (%)", value=4.50)
                
            p_ant = st.text_input("Preço Anterior (R$)", value="6.50")
            if st.button("📝 Gerar Reajuste", type="primary"):
                try:
                    p_num = float(p_ant.replace(",", "."))
                    p_novo = p_num * (1 + ipca_val/100)
                    txt = f"Aumento Aniversário de Contrato IPCA {ipca_val:.2f}%\nPreço Anterior: R$ {p_num:.4f}\nPreço Novo: R$ {p_novo:.4f}"
                    st.code(txt)
                    botao_copiar_customizado(txt, "cop_aniv")
                except:
                    st.error("Digite um preço válido.")

# =====================================================================
# ABA 2: AGENDA DE OCORRÊNCIAS
# =====================================================================
with aba_agenda:
    cabecalho_pagina("Agenda de Ocorrências", "Acompanhamento e carregamento de planilhas de ocorrência.")
    st.info("Envie o relatório em Excel para carregar suas pendências da sessão.")

# =====================================================================
# ABA 3: BLOCO DE NOTAS PESSOAL
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
        cabecalho_pagina("Bloco de Notas Pessoal", "Suas anotações salvas na nuvem.")
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
                    st.success("Salvo!")
                    st.rerun()
            if btn_d and id_atual:
                if apagar_nota(id_atual):
                    st.session_state.nota_selecionada_id = None
                    st.rerun()

# =====================================================================
# ABA 4: PAINEL ADMIN (GESTÃO COMPLETA DE NÍVEIS E SENHAS)
# =====================================================================
if aba_admin is not None:
    with aba_admin:
        cabecalho_pagina("Painel de Administração de Usuários", "Cadastro de colaboradores, níveis de permissão e redefinição de senhas.")
        
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
                            st.success(f"✅ Usuário **{novo_user}** criado com sucesso! (Senha inicial: 123456)")
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
            else:
                st.info("Nenhum usuário cadastrado além do Admin Master.")

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
                        st.success(f"✅ Usuário **{user_para_remover}** excluído!")
                        st.rerun()

# --- BARRA LATERAL LOGOUT ---
st.sidebar.divider()
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.session_state.e_admin = False
    st.session_state.troca_obrigatoria = False
    st.rerun()
