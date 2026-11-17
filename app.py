import os
import re
import uuid
import json
import base64
import hashlib
import tempfile
import html as html_lib
from io import BytesIO
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import altair as alt
from PIL import Image
from fpdf import FPDF
import streamlit as st
import streamlit.components.v1 as components

# =====================================================================
# CONFIGURAÇÃO GLOBAL DA PÁGINA E TEMA CLARO CORPORATIVO CONSIGAZ
# =====================================================================
os.makedirs(".streamlit", exist_ok=True)
with open(".streamlit/config.toml", "w", encoding="utf-8") as _f_cfg:
    _f_cfg.write(
        '[theme]\n'
        'primaryColor="#004080"\n'
        'backgroundColor="#FFFFFF"\n'
        'secondaryBackgroundColor="#F8FAFC"\n'
        'textColor="#1B2A3A"\n'
        'font="sans serif"\n'
    )

st.set_page_config(
    page_title="Sistema Integrado Consigaz | Pós-Vendas",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif !important;
    background-color: #FFFFFF !important;
    color: #1B2A3A !important;
}

.main .block-container {
    padding-top: 1.4rem;
    padding-bottom: 3rem;
    background-color: #FFFFFF !important;
}

/* Barra lateral limpa e clara */
section[data-testid="stSidebar"] {
    background-color: #F8FAFC !important;
    border-right: 1px solid #D3DDEA !important;
}
section[data-testid="stSidebar"] * {
    color: #1B2A3A !important;
}

/* Cabeçalho Corporativo Consigaz */
.cg-header {
    background: linear-gradient(135deg, #0A2540 0%, #004080 100%);
    padding: 20px 28px;
    border-radius: 12px;
    color: #FFFFFF !important;
    margin-bottom: 22px;
    box-shadow: 0 4px 14px rgba(0, 64, 128, 0.14);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
}
.cg-header-left {
    display: flex;
    align-items: center;
    gap: 16px;
}
.cg-logo {
    height: 46px;
    border-radius: 8px;
    background: #FFFFFF;
    padding: 4px 10px;
}
.cg-header-sep {
    width: 1px;
    height: 38px;
    background: rgba(255, 255, 255, 0.28);
}
.cg-title {
    color: #FFFFFF !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    margin: 0 !important;
    letter-spacing: -0.3px;
}
.cg-subtitle {
    color: #DCE8F8 !important;
    font-size: 13.5px !important;
    margin: 3px 0 0 0 !important;
}
.cg-brand-tag {
    color: #FFFFFF !important;
    font-weight: 800;
    font-size: 16px;
    letter-spacing: 1.2px;
    opacity: 0.92;
}

/* Inputs, Selectboxes, Textareas, File Uploaders e Radios 100% Brancos */
input, textarea, select,
div[data-baseweb="input"] > div,
div[data-baseweb="textarea"] > div,
div[data-baseweb="select"] > div,
div[data-testid="stFileUploader"] section,
div[data-testid="stFileUploaderDropzone"] {
    background-color: #FFFFFF !important;
    color: #1B2A3A !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
}
div[data-baseweb="input"] > div:focus-within,
div[data-baseweb="textarea"] > div:focus-within,
div[data-baseweb="select"] > div:focus-within {
    border-color: #004080 !important;
    box-shadow: 0 0 0 2px rgba(0, 64, 128, 0.12) !important;
}

/* Botões de incremento numérico (- / +) claros */
button[data-testid="stNumberInputStepDown"],
button[data-testid="stNumberInputStepUp"] {
    background-color: #FFFFFF !important;
    color: #1B2A3A !important;
    border: 1px solid #CBD5E1 !important;
}
button[data-testid="stNumberInputStepDown"]:hover,
button[data-testid="stNumberInputStepUp"]:hover {
    background-color: #E7EFF9 !important;
    color: #004080 !important;
}

/* Bolinhas de rádio e checkboxes limpas (sem fundo preto) */
div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
    color: #1B2A3A !important;
    font-weight: 500 !important;
}
div[data-baseweb="radio"] > div:first-child {
    background-color: #FFFFFF !important;
    border-color: #94A3B8 !important;
}

/* Botões padrão e primários */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    border: 1px solid #CBD5E1 !important;
    background-color: #FFFFFF !important;
    color: #1B2A3A !important;
    transition: all 0.18s ease !important;
}
.stButton > button:hover {
    border-color: #004080 !important;
    background-color: #F1F6FC !important;
    color: #004080 !important;
}
.stButton > button[kind="primary"] {
    background-color: #004080 !important;
    border-color: #004080 !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #003060 !important;
    border-color: #003060 !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 10px rgba(0, 64, 128, 0.22) !important;
}

/* Botões de Filtro Superior da Agenda (Quantidade grande em negrito + Texto completo) */
div[data-testid="stHorizontalBlock"] .stButton > button {
    min-height: 76px !important;
    white-space: pre-line !important;
    line-height: 1.25 !important;
    padding: 10px 8px !important;
}
div[data-testid="stHorizontalBlock"] .stButton > button strong {
    font-size: 24px !important;
    font-weight: 800 !important;
    color: #004080 !important;
    display: block !important;
}

/* Tabelas e DataFrames claros */
div[data-testid="stDataFrame"] {
    background-color: #FFFFFF !important;
    border: 1px solid #D3DDEA !important;
    border-radius: 10px !important;
    padding: 4px !important;
}

/* Legenda de Status Lateral */
.legenda-status-box {
    background-color: #FFFFFF;
    border: 1px solid #D3DDEA;
    border-radius: 10px;
    padding: 12px 14px;
    margin-top: 8px;
}
.legenda-status-titulo {
    font-size: 13.5px;
    font-weight: 700;
    color: #0A2540;
    margin-bottom: 8px;
    letter-spacing: 0.2px;
}
.legenda-status-item {
    font-size: 14px;
    font-weight: 600;
    color: #1B2A3A;
    padding: 4px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Caixa de aviso de alterações pendentes */
.aviso-edicao-box {
    background-color: #FFFBEB;
    border: 1.5px solid #F59E0B;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =====================================================================
# FUNÇÕES DE LOGO E CABEÇALHO CORPORATIVO
# =====================================================================
@st.cache_data(show_spinner=False)
def _logo_base64(caminho):
    try:
        with open(caminho, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""

def _logo_html(classe="cg-logo"):
    b64 = _logo_base64(LOGO_PATH)
    if not b64:
        return ""
    return f'<img class="{classe}" src="data:image/png;base64,{b64}" alt="Consigaz">'

def cabecalho_pagina(titulo, subtitulo):
    logo = _logo_html("cg-logo")
    separador = '<div class="cg-header-sep"></div>' if logo else ""
    st.markdown(
        f'<div class="cg-header">'
        f'<div class="cg-header-left">{logo}{separador}'
        f'<div><div class="cg-title">{html_lib.escape(titulo)}</div>'
        f'<div class="cg-subtitle">{html_lib.escape(subtitulo)}</div></div></div>'
        f'<div class="cg-brand-tag">CONSIGAZ</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# =====================================================================
# CONEXÃO COM SUPABASE (PERSISTÊNCIA EM NUVEM)
# =====================================================================
def get_supabase_config():
    try:
        url = st.secrets.get("SUPABASE_URL", "").strip().rstrip("/")
        key = st.secrets.get("SUPABASE_KEY", "").strip()
        if url and key:
            return url, key
    except Exception:
        pass
    return "", ""

def supabase_headers(prefer="return=representation"):
    _, key = get_supabase_config()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }

def hash_senha(senha):
    return hashlib.sha256(str(senha).strip().encode("utf-8")).hexdigest()

def sb_select(tabela, params=None):
    url, key = get_supabase_config()
    if not url or not key:
        return None
    try:
        resp = requests.get(f"{url}/rest/v1/{tabela}", headers=supabase_headers(), params=params or {}, timeout=8)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def sb_insert(tabela, payload):
    url, key = get_supabase_config()
    if not url or not key:
        return False, "Supabase não configurado."
    try:
        resp = requests.post(f"{url}/rest/v1/{tabela}", headers=supabase_headers(), json=payload, timeout=8)
        if resp.status_code in (200, 201):
            return True, resp.json()
        return False, resp.text
    except Exception as e:
        return False, str(e)

def sb_update(tabela, filtros_params, payload):
    url, key = get_supabase_config()
    if not url or not key:
        return False, "Supabase não configurado."
    try:
        resp = requests.patch(f"{url}/rest/v1/{tabela}", headers=supabase_headers(), params=filtros_params, json=payload, timeout=8)
        if resp.status_code in (200, 204):
            return True, resp.json() if resp.text else {}
        return False, resp.text
    except Exception as e:
        return False, str(e)

def sb_delete(tabela, filtros_params):
    url, key = get_supabase_config()
    if not url or not key:
        return False, "Supabase não configurado."
    try:
        resp = requests.delete(f"{url}/rest/v1/{tabela}", headers=supabase_headers(), params=filtros_params, timeout=8)
        if resp.status_code in (200, 204):
            return True, "Removido"
        return False, resp.text
    except Exception as e:
        return False, str(e)

# =====================================================================
# INICIALIZAÇÃO DE ESTADO DA SESSÃO
# =====================================================================
def inicializar_estados():
    defaults = {
        "logado": False,
        "usuario_atual": "",
        "nome_usuario_atual": "",
        "perfil_usuario": "Convencional",
        "e_supervisor": False,
        "e_admin": False,
        "primeiro_acesso": False,
        "reset_counter": 0,
        "tratadas_manualmente": set(),
        "ocorrencia_ativa": {"codigo": "", "cliente": ""},
        "filtro_sla_agenda": "Total",
        "filtro_sla_comodato": "Total",
        "notas_locais": {},
        "nota_selecionada_id": None,
        "acompanhamento_local": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    url, key = get_supabase_config()
    if not url or not key:
        if not st.session_state.logado:
            st.session_state.logado = True
            st.session_state.usuario_atual = "operador.local"
            st.session_state.nome_usuario_atual = "Operador Pós-Vendas"
            st.session_state.perfil_usuario = "Admin"
            st.session_state.e_supervisor = True
            st.session_state.e_admin = True

inicializar_estados()

# =====================================================================
# TELA DE LOGIN E TROCA DE SENHA NO PRIMEIRO ACESSO
# =====================================================================
def tela_login():
    cabecalho_pagina("Portal Pós-Vendas Consigaz", "Acesso restrito aos colaboradores autorizados.")
    col_l1, col_l2, col_l3 = st.columns([1, 1.4, 1])
    with col_l2:
        st.markdown("### 🔐 Autenticação do Sistema")
        with st.form("form_login_consigaz"):
            usuario_in = st.text_input("Usuário (login):").strip().lower()
            senha_in = st.text_input("Senha:", type="password")
            entrar = st.form_submit_button("Entrar no Sistema", type="primary", use_container_width=True)

        if entrar:
            if not usuario_in or not senha_in:
                st.warning("⚠️ Informe o usuário e a senha.")
            elif usuario_in == "admin" and senha_in == "admin123":
                st.session_state.logado = True
                st.session_state.usuario_atual = "admin"
                st.session_state.nome_usuario_atual = "Administrador Geral"
                st.session_state.perfil_usuario = "Admin"
                st.session_state.e_supervisor = True
                st.session_state.e_admin = True
                st.session_state.primeiro_acesso = False
                st.rerun()
            else:
                users = sb_select("usuarios", {"usuario": f"eq.{usuario_in}"})
                if users and len(users) > 0:
                    u = users[0]
                    senha_bd = str(u.get("senha_hash", ""))
                    if senha_bd == hash_senha(senha_in) or senha_bd == senha_in:
                        perfil = u.get("perfil", "Convencional")
                        st.session_state.logado = True
                        st.session_state.usuario_atual = usuario_in
                        st.session_state.nome_usuario_atual = u.get("nome", usuario_in)
                        st.session_state.perfil_usuario = perfil
                        st.session_state.e_supervisor = perfil in ("Supervisor", "Admin")
                        st.session_state.e_admin = perfil == "Admin"
                        st.session_state.primeiro_acesso = bool(u.get("primeiro_acesso", False)) or (senha_in == "123456")
                        st.rerun()
                    else:
                        st.error("❌ Senha incorreta.")
                else:
                    st.error("❌ Usuário não encontrado no sistema.")

def tela_troca_senha_obrigatoria():
    cabecalho_pagina("Primeiro Acesso - Atualização de Senha", "Por segurança, defina uma nova senha pessoal antes de continuar.")
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.info(f"👤 Usuário: **{st.session_state.usuario_atual}** — Sua senha atual é a senha inicial (`123456`).")
        with st.form("form_nova_senha_1acesso"):
            nova_s1 = st.text_input("Nova Senha (mínimo 6 caracteres):", type="password")
            nova_s2 = st.text_input("Confirme a Nova Senha:", type="password")
            salvar_s = st.form_submit_button("💾 Salvar Nova Senha e Acessar", type="primary", use_container_width=True)

        if salvar_s:
            if len(nova_s1) < 6:
                st.warning("⚠️ A nova senha deve ter pelo menos 6 caracteres.")
            elif nova_s1 == "123456":
                st.warning("⚠️ A nova senha não pode ser 123456.")
            elif nova_s1 != nova_s2:
                st.error("❌ As senhas digitadas não coincidem.")
            else:
                ok, err = sb_update(
                    "usuarios",
                    {"usuario": f"eq.{st.session_state.usuario_atual}"},
                    {"senha_hash": hash_senha(nova_s1), "primeiro_acesso": False},
                )
                if ok:
                    st.session_state.primeiro_acesso = False
                    st.success("✅ Senha atualizada com sucesso!")
                    st.rerun()
                else:
                    st.error(f"Erro ao atualizar senha no banco: {err}")

if not st.session_state.logado:
    tela_login()
    st.stop()

if st.session_state.primeiro_acesso:
    tela_troca_senha_obrigatoria()
    st.stop()

# =====================================================================
# FUNÇÕES UTILITÁRIAS GERAIS DO SISTEMA
# =====================================================================
def formatar_ci_num(val):
    digits = "".join(filter(str.isdigit, str(val)))
    if len(digits) == 9:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:]}"
    elif len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}"
    elif digits:
        return digits
    return "N/A"

def consultar_cnpj_api(cnpj):
    cnpj_limpo = "".join(filter(str.isdigit, str(cnpj)))
    if len(cnpj_limpo) != 14:
        return None
    for url in [
        f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}",
        f"https://minhareceita.org/{cnpj_limpo}",
    ]:
        try:
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            continue
    return None

def obter_ipca_acumulado_12m():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp_ibge = requests.get("https://www.ibge.gov.br/explica/inflacao.php", headers=headers, timeout=5)
        if resp_ibge.status_code == 200:
            texto_limpo = re.sub(r"<[^>]+>", " ", resp_ibge.text)
            m = re.search(r"IPCA acumulado de 12 meses[^0-9]*([0-9]+,[0-9]+)%", texto_limpo, re.IGNORECASE)
            if m:
                val = float(m.group(1).replace(",", "."))
                m_mes = re.search(r"([A-Za-zçÇ]+/[0-9]{4})", texto_limpo[m.start():m.end() + 80])
                ref = m_mes.group(1) if m_mes else "IBGE Oficial"
                return val, ref
    except Exception:
        pass

    try:
        resp_bcb = requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json", timeout=4)
        if resp_bcb.status_code == 200:
            dados = resp_bcb.json()
            if dados:
                return float(dados[-1]["valor"]), dados[-1]["data"]
    except Exception:
        pass

    try:
        url = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-12/variaveis/2265?localidades=N1[all]"
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            dados = resp.json()
            resultados = dados[0]["resultados"][0]["series"][0]["serie"]
            periodos = sorted(resultados.keys())
            ultimo_periodo = periodos[-1]
            return float(resultados[ultimo_periodo]), ultimo_periodo
    except Exception:
        pass

    return None, None

def botao_copiar_customizado(texto_para_copiar, chave_unica, label_btn="📋 Copiar Texto Completo"):
    texto_seguro = (
        str(texto_para_copiar)
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("$", "\\$")
        .replace("\n", "\\n")
        .replace("\r", "")
    )
    component_html = f"""
    <div style="margin-top: 6px; margin-bottom: 10px; font-family: 'Plus Jakarta Sans', sans-serif;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background-color: #004080; color: #FFFFFF; padding: 9px 18px; border: none;
            border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer;
            display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 2px 6px rgba(0,64,128,0.18);
        ">{label_btn}</button>
        <span id="msg_{chave_unica}" style="margin-left: 12px; color: #16A34A; font-weight: 700; font-size: 13px; display: none;">✓ Copiado com sucesso!</span>
    </div>
    <script>
    function copiarTexto_{chave_unica}() {{
        const texto = `{texto_seguro}`;
        navigator.clipboard.writeText(texto).then(function() {{
            const msg = document.getElementById("msg_{chave_unica}");
            msg.style.display = "inline";
            setTimeout(function() {{ msg.style.display = "none"; }}, 3500);
        }}).catch(function(err) {{
            alert("Não foi possível copiar automaticamente: " + err);
        }});
    }}
    </script>
    """
    components.html(component_html, height=52)

def extrair_cidade(endereco):
    if pd.isna(endereco):
        return "-"
    s = str(endereco).strip()
    s_norm = s.replace(";", ",").replace("|", ",")
    partes = [p.strip() for p in s_norm.split(",")]
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
    return 0

def classificar_bolinha_sla(dias_uteis):
    if dias_uteis < 0:
        return "🔴"
    elif dias_uteis == 0:
        return "🔵"
    elif dias_uteis == 1:
        return "🟠"
    elif 2 <= dias_uteis <= 5:
        return "🟡"
    return "🟢"

# =====================================================================
# FUNÇÕES DE SUPORTE: STATUS DE CONTRATOS E STATUS DE VENDAS (KANBAN)
# =====================================================================
MESES_KANBAN = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
STATUS_OPCOES_KANBAN = [
    "🟢 Concluído / Ativo",
    "🟡 Em Andamento",
    "🔵 Aguardando Retorno",
    "🔴 Pendente / Crítico",
]

def _extrair_bolinha_status(status_str):
    s = str(status_str or "").strip()
    for icone in ["🟢", "🟡", "🔵", "🔴", "🟠"]:
        if s.startswith(icone):
            return icone
    return "🔵"

def _extrair_comissao_e_obs(reg):
    comissao_direta = str(reg.get("comissao") or "").strip()
    obs_raw = str(reg.get("observacoes") or "")
    m = re.search(r"\[COMISSAO:(20%|10%)\]", obs_raw)
    if m:
        if not comissao_direta:
            comissao_direta = m.group(1)
        obs_limpa = re.sub(r"\s*\[COMISSAO:(20%|10%)\]", "", obs_raw).strip()
    else:
        obs_limpa = obs_raw.strip()
    return comissao_direta, obs_limpa

def carregar_registros_acompanhamento(tipo_acompanhamento):
    url, key = get_supabase_config()
    if url and key:
        dados = sb_select(
            "acompanhamento_clientes",
            {"tipo": f"eq.{tipo_acompanhamento}", "order": "created_at.asc"},
        )
        if isinstance(dados, list):
            lista_limpa = []
            for d in dados:
                if not isinstance(d, dict):
                    continue
                comissao_val, obs_val = _extrair_comissao_e_obs(d)
                lista_limpa.append({
                    "id": str(d.get("id", "")),
                    "tipo": tipo_acompanhamento,
                    "codigo": str(d.get("codigo", "")),
                    "nome": str(d.get("nome", "")),
                    "status": str(d.get("status", "🔵 Aguardando Retorno")),
                    "mes": str(d.get("mes", "Jan")) if str(d.get("mes", "Jan")) in MESES_KANBAN else "Jan",
                    "comissao": comissao_val,
                    "observacoes": obs_val,
                })
            return lista_limpa

    return [
        r for r in st.session_state.acompanhamento_local
        if isinstance(r, dict) and r.get("tipo") == tipo_acompanhamento
    ]

def salvar_novo_registro_acompanhamento(tipo_acompanhamento, codigo, nome, status, mes, comissao, observacoes):
    novo_id = str(uuid.uuid4())
    url, key = get_supabase_config()
    if url and key:
        payload = {
            "id": novo_id,
            "tipo": tipo_acompanhamento,
            "codigo": codigo.strip(),
            "nome": nome.strip(),
            "status": status,
            "mes": mes,
            "comissao": comissao or "",
            "observacoes": observacoes.strip(),
            "usuario": st.session_state.usuario_atual,
        }
        ok, err = sb_insert("acompanhamento_clientes", payload)
        if not ok and "comissao" in str(err).lower():
            obs_com_tag = observacoes.strip()
            if comissao in ("20%", "10%"):
                obs_com_tag = f"{obs_com_tag} [COMISSAO:{comissao}]".strip()
            payload_sem_col = {k: v for k, v in payload.items() if k != "comissao"}
            payload_sem_col["observacoes"] = obs_com_tag
            ok, err = sb_insert("acompanhamento_clientes", payload_sem_col)
        return ok, err

    st.session_state.acompanhamento_local.append({
        "id": novo_id,
        "tipo": tipo_acompanhamento,
        "codigo": codigo.strip(),
        "nome": nome.strip(),
        "status": status,
        "mes": mes,
        "comissao": comissao or "",
        "observacoes": observacoes.strip(),
    })
    return True, "Salvo localmente"

def atualizar_registro_acompanhamento(id_reg, codigo, nome, status, mes, comissao, observacoes):
    url, key = get_supabase_config()
    if url and key:
        payload = {
            "codigo": codigo.strip(),
            "nome": nome.strip(),
            "status": status,
            "mes": mes,
            "comissao": comissao or "",
            "observacoes": observacoes.strip(),
        }
        ok, err = sb_update("acompanhamento_clientes", {"id": f"eq.{id_reg}"}, payload)
        if not ok and "comissao" in str(err).lower():
            obs_com_tag = observacoes.strip()
            if comissao in ("20%", "10%"):
                obs_com_tag = f"{obs_com_tag} [COMISSAO:{comissao}]".strip()
            payload_sem_col = {k: v for k, v in payload.items() if k != "comissao"}
            payload_sem_col["observacoes"] = obs_com_tag
            ok, err = sb_update("acompanhamento_clientes", {"id": f"eq.{id_reg}"}, payload_sem_col)
        return ok, err

    for r in st.session_state.acompanhamento_local:
        if r.get("id") == id_reg:
            r["codigo"] = codigo.strip()
            r["nome"] = nome.strip()
            r["status"] = status
            r["mes"] = mes
            r["comissao"] = comissao or ""
            r["observacoes"] = observacoes.strip()
            break
    return True, "Atualizado localmente"

def mover_mes_registro_acompanhamento(id_reg, novo_mes):
    if novo_mes not in MESES_KANBAN:
        return
    url, key = get_supabase_config()
    if url and key:
        sb_update("acompanhamento_clientes", {"id": f"eq.{id_reg}"}, {"mes": novo_mes})
    else:
        for r in st.session_state.acompanhamento_local:
            if r.get("id") == id_reg:
                r["mes"] = novo_mes
                break

def excluir_registro_acompanhamento(id_reg):
    url, key = get_supabase_config()
    if url and key:
        return sb_delete("acompanhamento_clientes", {"id": f"eq.{id_reg}"})
    st.session_state.acompanhamento_local = [r for r in st.session_state.acompanhamento_local if r.get("id") != id_reg]
    return True, "Excluído localmente"

def renderizar_painel_acompanhamento(tipo_acompanhamento):
    eh_venda = tipo_acompanhamento == "venda"
    titulo_pag = "Status de Vendas" if eh_venda else "Status de Contratos"
    subtitulo_pag = (
        "Painel interativo mensal de vendas, status, comissão e acompanhamento comercial."
        if eh_venda
        else "Painel interativo mensal de contratos, regularizações e acompanhamento de status."
    )
    cabecalho_pagina(titulo_pag, subtitulo_pag)

    key_sel = f"kanban_sel_{tipo_acompanhamento}"
    key_pend = f"kanban_pend_{tipo_acompanhamento}"
    if key_sel not in st.session_state:
        st.session_state[key_sel] = None
    if key_pend not in st.session_state:
        st.session_state[key_pend] = None

    qp = st.query_params
    if qp.get("kb_tipo") == tipo_acompanhamento and qp.get("kb_act"):
        act = qp.get("kb_act")
        target_id = qp.get("kb_id", "")
        target_mes = qp.get("kb_mes", "")
        st.query_params.clear()

        if act == "move" and target_id and target_mes in MESES_KANBAN:
            mover_mes_registro_acompanhamento(target_id, target_mes)
            st.toast(f"Cliente movido para {target_mes}!", icon="✅")
            st.rerun()

        elif act == "select" and target_id:
            atual_id = st.session_state[key_sel]
            if atual_id and atual_id != target_id:
                registros_temp = carregar_registros_acompanhamento(tipo_acompanhamento)
                reg_atual_obj = next((x for x in registros_temp if x["id"] == atual_id), None)
                if reg_atual_obj:
                    cod_ed = st.session_state.get(f"ed_cod_{tipo_acompanhamento}_{atual_id}", reg_atual_obj["codigo"])
                    nom_ed = st.session_state.get(f"ed_nom_{tipo_acompanhamento}_{atual_id}", reg_atual_obj["nome"])
                    sta_ed = st.session_state.get(f"ed_sta_{tipo_acompanhamento}_{atual_id}", reg_atual_obj["status"])
                    mes_ed = st.session_state.get(f"ed_mes_{tipo_acompanhamento}_{atual_id}", reg_atual_obj["mes"])
                    obs_ed = st.session_state.get(f"ed_obs_{tipo_acompanhamento}_{atual_id}", reg_atual_obj["observacoes"])
                    com_ed = (
                        st.session_state.get(f"ed_com_{tipo_acompanhamento}_{atual_id}", reg_atual_obj["comissao"] or None)
                        if eh_venda
                        else ""
                    )

                    houve_alteracao = (
                        str(cod_ed).strip() != str(reg_atual_obj["codigo"]).strip()
                        or str(nom_ed).strip() != str(reg_atual_obj["nome"]).strip()
                        or str(sta_ed) != str(reg_atual_obj["status"])
                        or str(mes_ed) != str(reg_atual_obj["mes"])
                        or str(obs_ed).strip() != str(reg_atual_obj["observacoes"]).strip()
                        or (eh_venda and str(com_ed or "") != str(reg_atual_obj["comissao"] or ""))
                    )
                    if houve_alteracao:
                        st.session_state[key_pend] = target_id
                    else:
                        st.session_state[key_sel] = target_id
                        st.session_state[key_pend] = None
                else:
                    st.session_state[key_sel] = target_id
            else:
                st.session_state[key_sel] = target_id
                st.session_state[key_pend] = None
            st.rerun()

    registros = carregar_registros_acompanhamento(tipo_acompanhamento)

    id_atual = st.session_state[key_sel]
    id_pendente = st.session_state[key_pend]

    if id_atual and id_pendente:
        reg_orig = next((r for r in registros if r["id"] == id_atual), None)
        reg_prox = next((r for r in registros if r["id"] == id_pendente), None)
        if reg_orig and reg_prox:
            st.markdown(
                f"""
                <div class="aviso-edicao-box">
                    <strong>⚠️ Alterações não salvas detectadas!</strong><br>
                    Você modificou dados do cliente <b>{html_lib.escape(reg_orig['codigo'])} - {html_lib.escape(reg_orig['nome'])}</b>
                    e clicou em <b>{html_lib.escape(reg_prox['codigo'])} - {html_lib.escape(reg_prox['nome'])}</b>.<br>
                    Deseja salvar as alterações antes de mudar para o próximo cliente?
                </div>
                """,
                unsafe_allow_html=True,
            )
            av_c1, av_c2, av_c3 = st.columns(3)
            with av_c1:
                if st.button("💾 Sim, Salvar e Mudar", type="primary", use_container_width=True, key=f"av_salv_{tipo_acompanhamento}"):
                    cod_s = st.session_state.get(f"ed_cod_{tipo_acompanhamento}_{id_atual}", reg_orig["codigo"])
                    nom_s = st.session_state.get(f"ed_nom_{tipo_acompanhamento}_{id_atual}", reg_orig["nome"])
                    sta_s = st.session_state.get(f"ed_sta_{tipo_acompanhamento}_{id_atual}", reg_orig["status"])
                    mes_s = st.session_state.get(f"ed_mes_{tipo_acompanhamento}_{id_atual}", reg_orig["mes"])
                    obs_s = st.session_state.get(f"ed_obs_{tipo_acompanhamento}_{id_atual}", reg_orig["observacoes"])
                    com_s = st.session_state.get(f"ed_com_{tipo_acompanhamento}_{id_atual}", reg_orig["comissao"]) if eh_venda else ""
                    atualizar_registro_acompanhamento(id_atual, cod_s, nom_s, sta_s, mes_s, com_s, obs_s)
                    st.session_state[key_sel] = id_pendente
                    st.session_state[key_pend] = None
                    st.rerun()
            with av_c2:
                if st.button("🗑️ Não Salvar (Descartar)", use_container_width=True, key=f"av_desc_{tipo_acompanhamento}"):
                    st.session_state[key_sel] = id_pendente
                    st.session_state[key_pend] = None
                    st.rerun()
            with av_c3:
                if st.button("↩️ Continuar Editando Atual", use_container_width=True, key=f"av_cont_{tipo_acompanhamento}"):
                    st.session_state[key_pend] = None
                    st.rerun()

    if id_atual:
        reg_edit = next((r for r in registros if r["id"] == id_atual), None)
        if reg_edit:
            with st.container(border=True):
                st.markdown(f"### ✏️ Detalhes e Edição: {reg_edit['codigo']} — {reg_edit['nome']}")
                ec1, ec2, ec3, ec4 = st.columns([1, 2, 1.3, 1])
                with ec1:
                    ed_codigo = st.text_input("Código do Cliente:", value=reg_edit["codigo"], key=f"ed_cod_{tipo_acompanhamento}_{id_atual}")
                with ec2:
                    ed_nome = st.text_input("Nome do Cliente:", value=reg_edit["nome"], key=f"ed_nom_{tipo_acompanhamento}_{id_atual}")
                with ec3:
                    idx_sta = STATUS_OPCOES_KANBAN.index(reg_edit["status"]) if reg_edit["status"] in STATUS_OPCOES_KANBAN else 2
                    ed_status = st.selectbox("Status:", STATUS_OPCOES_KANBAN, index=idx_sta, key=f"ed_sta_{tipo_acompanhamento}_{id_atual}")
                with ec4:
                    idx_mes = MESES_KANBAN.index(reg_edit["mes"]) if reg_edit["mes"] in MESES_KANBAN else 0
                    ed_mes = st.selectbox("Mês de Alocação:", MESES_KANBAN, index=idx_mes, key=f"ed_mes_{tipo_acompanhamento}_{id_atual}")

                ed_comissao = ""
                if eh_venda:
                    opcoes_com = ["20%", "10%"]
                    idx_com = opcoes_com.index(reg_edit["comissao"]) if reg_edit.get("comissao") in opcoes_com else None
                    ed_comissao = st.radio(
                        "Comissão:",
                        opcoes_com,
                        horizontal=True,
                        index=idx_com,
                        key=f"ed_com_{tipo_acompanhamento}_{id_atual}",
                    )

                ed_obs = st.text_area("Observações / Histórico:", value=reg_edit["observacoes"], height=90, key=f"ed_obs_{tipo_acompanhamento}_{id_atual}")

                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("💾 Salvar Alterações", type="primary", use_container_width=True, key=f"ed_salv_{tipo_acompanhamento}"):
                        ok, err = atualizar_registro_acompanhamento(
                            id_atual, ed_codigo, ed_nome, ed_status, ed_mes, ed_comissao or "", ed_obs
                        )
                        if ok:
                            st.session_state[key_sel] = None
                            st.session_state[key_pend] = None
                            st.success("✅ Alterações salvas com sucesso!")
                            st.rerun()
                        else:
                            st.error(f"Erro ao salvar: {err}")
                with b2:
                    if st.button("❌ Fechar Painel", use_container_width=True, key=f"ed_canc_{tipo_acompanhamento}"):
                        st.session_state[key_sel] = None
                        st.session_state[key_pend] = None
                        st.rerun()
                with b3:
                    if st.button("🗑️ Excluir Cliente", use_container_width=True, key=f"ed_del_{tipo_acompanhamento}"):
                        excluir_registro_acompanhamento(id_atual)
                        st.session_state[key_sel] = None
                        st.session_state[key_pend] = None
                        st.rerun()

    with st.expander(f"➕ Adicionar Novo Cliente em {titulo_pag}", expanded=False):
        ac1, ac2, ac3, ac4 = st.columns([1, 2, 1.3, 1])
        with ac1:
            add_cod = st.text_input("Código do Cliente:", key=f"add_cod_{tipo_acompanhamento}")
        with ac2:
            add_nom = st.text_input("Nome do Cliente:", key=f"add_nom_{tipo_acompanhamento}")
        with ac3:
            add_sta = st.selectbox("Status:", STATUS_OPCOES_KANBAN, index=1, key=f"add_sta_{tipo_acompanhamento}")
        with ac4:
            mes_atual_idx = min(max(datetime.now().month - 1, 0), 11)
            add_mes = st.selectbox("Mês de Alocação:", MESES_KANBAN, index=mes_atual_idx, key=f"add_mes_{tipo_acompanhamento}")

        add_comissao = ""
        if eh_venda:
            add_comissao = st.radio(
                "Comissão:",
                ["20%", "10%"],
                horizontal=True,
                index=None,
                key=f"add_com_{tipo_acompanhamento}",
            )

        add_obs = st.text_area("Observações iniciais:", height=75, key=f"add_obs_{tipo_acompanhamento}")

        if st.button("Adicionar Cliente", type="primary", use_container_width=True, key=f"btn_add_{tipo_acompanhamento}"):
            if not add_cod.strip() or not add_nom.strip():
                st.warning("⚠️ Preencha o Código e o Nome do Cliente.")
            else:
                ok, err = salvar_novo_registro_acompanhamento(
                    tipo_acompanhamento, add_cod, add_nom, add_sta, add_mes, add_comissao or "", add_obs
                )
                if ok:
                    st.success("✅ Cliente adicionado ao painel!")
                    st.rerun()
                else:
                    st.error(f"Erro ao salvar registro: {err}")

    st.divider()
    st.caption("💡 Clique em qualquer cartão para abrir os detalhes e editar acima, ou arraste o cartão entre os meses para alterar a alocação.")

    colunas_html = []
    for mes in MESES_KANBAN:
        itens_mes = [r for r in registros if r.get("mes") == mes]
        cards_html = []
        for item in itens_mes:
            cid = html_lib.escape(item["id"])
            ccod = html_lib.escape(item["codigo"])
            cnome = html_lib.escape(item["nome"])
            bolinha = _extrair_bolinha_status(item["status"])
            selecionado_cls = "card-selecionado" if item["id"] == id_atual else ""

            comissao_html = ""
            if eh_venda:
                com_val = str(item.get("comissao") or "").strip()
                if com_val == "20%":
                    comissao_html = '<div class="card-comissao comissao-verde">Comissão: 20%</div>'
                elif com_val == "10%":
                    comissao_html = '<div class="card-comissao comissao-amarela">Comissão: 10%</div>'

            cards_html.append(
                f'<div class="kb-card {selecionado_cls}" draggable="true" '
                f'ondragstart="onDragStart(event, \'{cid}\')" '
                f'ondragend="onDragEnd()" '
                f'onclick="onCardClick(\'{cid}\')" '
                f'title="Clique para editar ou arraste para mudar o mês">'
                f'<div class="kb-card-top"><span class="kb-dot">{bolinha}</span> <span class="kb-code">{ccod}</span></div>'
                f'<div class="kb-card-name">{cnome}</div>'
                f'{comissao_html}'
                f'</div>'
            )

        cards_str = "".join(cards_html) if cards_html else '<div class="kb-empty">Arraste ou adicione aqui</div>'
        colunas_html.append(
            f'<div class="kb-col" ondragover="onDragOver(event)" ondragleave="onDragLeave(event)" ondrop="onDrop(event, \'{mes}\')">'
            f'<div class="kb-col-header"><span>{mes}</span><span class="kb-badge">{len(itens_mes)}</span></div>'
            f'<div class="kb-col-body">{cards_str}</div>'
            f'</div>'
        )

    kanban_full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        * {{ box-sizing: border-box; font-family: 'Plus Jakarta Sans', 'Segoe UI', sans-serif; }}
        body {{ margin: 0; padding: 4px; background-color: #FFFFFF; color: #1B2A3A; }}
        .kb-board {{
            display: flex;
            flex-direction: row;
            gap: 14px;
            overflow-x: auto;
            padding-bottom: 14px;
            align-items: flex-start;
        }}
        .kb-board::-webkit-scrollbar {{ height: 9px; }}
        .kb-board::-webkit-scrollbar-track {{ background: #F1F5F9; border-radius: 6px; }}
        .kb-board::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 6px; }}
        .kb-board::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}

        .kb-col {{
            min-width: 215px;
            max-width: 215px;
            background-color: #F8FAFC;
            border: 1px solid #D3DDEA;
            border-radius: 10px;
            display: flex;
            flex-direction: column;
            min-height: 430px;
            transition: background-color 0.15s ease, border-color 0.15s ease;
        }}
        .kb-col.drag-over {{
            background-color: #E7EFF9;
            border: 1.5px dashed #004080;
        }}
        .kb-col-header {{
            background-color: #004080;
            color: #FFFFFF;
            padding: 10px 14px;
            border-radius: 9px 9px 0 0;
            font-weight: 700;
            font-size: 14px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .kb-badge {{
            background-color: rgba(255, 255, 255, 0.22);
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 12px;
        }}
        .kb-col-body {{
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 9px;
            flex: 1;
        }}
        .kb-card {{
            background-color: #FFFFFF;
            border: 1px solid #D3DDEA;
            border-radius: 8px;
            padding: 10px 12px;
            cursor: pointer;
            box-shadow: 0 1px 3px rgba(10, 37, 64, 0.05);
            transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
            user-select: none;
        }}
        .kb-card:hover {{
            border-color: #004080;
            box-shadow: 0 4px 10px rgba(0, 64, 128, 0.12);
            transform: translateY(-1px);
        }}
        .card-selecionado {{
            border: 2px solid #004080 !important;
            background-color: #F0F6FF !important;
        }}
        .kb-card-top {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            font-weight: 800;
            color: #0A2540;
            margin-bottom: 4px;
        }}
        .kb-dot {{ font-size: 13px; line-height: 1; }}
        .kb-code {{ letter-spacing: 0.2px; }}
        .kb-card-name {{
            font-size: 13px;
            font-weight: 600;
            color: #1B2A3A;
            line-height: 1.35;
            word-wrap: break-word;
            white-space: normal;
        }}
        .card-comissao {{
            margin-top: 7px;
            display: inline-block;
            font-size: 12px;
            font-weight: 800;
            padding: 3px 9px;
            border-radius: 6px;
        }}
        .comissao-verde {{
            background-color: #DCFCE7;
            color: #15803D;
            border: 1px solid #86EFAC;
        }}
        .comissao-amarela {{
            background-color: #FEF08A;
            color: #A16207;
            border: 1px solid #FACC15;
        }}
        .kb-empty {{
            text-align: center;
            color: #94A3B8;
            font-size: 12px;
            padding: 24px 6px;
            border: 1px dashed #E2E8F0;
            border-radius: 8px;
        }}
    </style>
    </head>
    <body>
        <div class="kb-board">
            {''.join(colunas_html)}
        </div>
        <script>
            let draggedId = null;
            let isDragging = false;

            function navegarStreamlit(paramsObj) {{
                let baseHref = "";
                try {{
                    baseHref = window.parent.location.href;
                }} catch (e) {{
                    baseHref = document.referrer || window.location.href;
                }}
                const url = new URL(baseHref);
                for (const [k, v] of Object.entries(paramsObj)) {{
                    url.searchParams.set(k, v);
                }}
                try {{
                    window.parent.location.href = url.toString();
                }} catch (e) {{
                    window.open(url.toString(), "_parent");
                }}
            }}

            function onCardClick(id) {{
                if (isDragging) return;
                navegarStreamlit({{
                    "kb_tipo": "{tipo_acompanhamento}",
                    "kb_act": "select",
                    "kb_id": id
                }});
            }}

            function onDragStart(ev, id) {{
                isDragging = true;
                draggedId = id;
                ev.dataTransfer.setData("text/plain", id);
                ev.dataTransfer.effectAllowed = "move";
            }}

            function onDragEnd() {{
                setTimeout(function() {{ isDragging = false; }}, 120);
            }}

            function onDragOver(ev) {{
                ev.preventDefault();
                ev.dataTransfer.dropEffect = "move";
                ev.currentTarget.classList.add("drag-over");
            }}

            function onDragLeave(ev) {{
                ev.currentTarget.classList.remove("drag-over");
            }}

            function onDrop(ev, novoMes) {{
                ev.preventDefault();
                ev.currentTarget.classList.remove("drag-over");
                const id = ev.dataTransfer.getData("text/plain") || draggedId;
                if (id) {{
                    navegarStreamlit({{
                        "kb_tipo": "{tipo_acompanhamento}",
                        "kb_act": "move",
                        "kb_id": id,
                        "kb_mes": novoMes
                    }});
                }}
            }}
        </script>
    </body>
    </html>
    """
    components.html(kanban_full_html, height=510, scrolling=False)

# =====================================================================
# BARRA LATERAL PRINCIPAL (NAVEGAÇÃO)
# =====================================================================
st.sidebar.markdown("### 📌 Módulos do Sistema")
opcoes_modulos = [
    "📋 Tratativa de Ocorrências",
    "📊 Agenda de Ocorrências",
    "📑 Status de Contratos",
    "💼 Status de Vendas",
    "📝 Bloco de Notas Pessoal",
]
if st.session_state.e_supervisor or st.session_state.e_admin:
    opcoes_modulos.append("⚙️ Painel Admin")

aba_principal = st.sidebar.radio("Navegação:", opcoes_modulos, index=0, label_visibility="collapsed")
st.sidebar.divider()

# =====================================================================
# ABA 1: TRATATIVA DE OCORRÊNCIAS
# =====================================================================
if aba_principal == "📋 Tratativa de Ocorrências":
    menu_tratativa = st.sidebar.selectbox(
        "Selecione a Tratativa:",
        [
            "📸 Visita de Transferência",
            "📝 Elaboração de Contrato",
            "📋 Aprovação de Contrato",
            "🎂 Aniversário de Contrato",
            "🪪 Ficha de Cliente",
        ],
    )

    if menu_tratativa == "📸 Visita de Transferência":
        rcv = st.session_state.reset_counter
        cabecalho_pagina(
            "Visita de Transferência",
            "Vistoria técnica, cadastro de equipamentos e emissão de Relatório Fotográfico em PDF.",
        )

        col_top_v1, _ = st.columns([1, 3])
        with col_top_v1:
            if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_vis_{rcv}"):
                st.session_state.ocorrencia_ativa = {"codigo": "", "cliente": ""}
                st.session_state.reset_counter += 1
                st.rerun()

        st.divider()
        st.subheader("1. Dados Cadastrais & Informações do Cliente")
        cod_default = st.session_state.ocorrencia_ativa.get("codigo", "")
        cli_default = st.session_state.ocorrencia_ativa.get("cliente", "")

        col_vt1, col_vt2 = st.columns(2)
        with col_vt1:
            cod_cliente_vt = st.text_input("Código do Cliente:", value=cod_default, key=f"cod_cli_vt_{rcv}")
            nome_cliente_vt = st.text_input("Nome do Cliente:", value=cli_default, key=f"nome_cli_vt_{rcv}")
            endereco_vt = st.text_input("Endereço da Vistoria:", key=f"end_vt_{rcv}")
        with col_vt2:
            contato_vt = st.text_input("Nome do Contato no Local:", key=f"contato_vt_{rcv}")
            tel_vt = st.text_input("Telefone de Contato:", key=f"tel_vt_{rcv}")
            tecnico_vt = st.text_input("Consultor / Técnico Responsável:", value=st.session_state.nome_usuario_atual, key=f"tec_vt_{rcv}")

        st.divider()
        st.subheader("2. Equipamentos e Central de Gás")
        qtd_centrais_vt = st.number_input("Quantidade de Centrais / Entregas:", min_value=1, value=1, step=1, key=f"qtd_cent_vt_{rcv}")

        eq_vt_dict = {}
        for c_i in range(1, int(qtd_centrais_vt) + 1):
            st.markdown(f"**Central {c_i:02d}:**")
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                eq_b190 = st.number_input(f"Qtd B190 (Central {c_i}):", min_value=0, value=0, key=f"b190_{c_i}_{rcv}")
                eq_p45 = st.number_input(f"Qtd P45 (Central {c_i}):", min_value=0, value=0, key=f"p45_{c_i}_{rcv}")
            with col_c2:
                eq_cc = st.number_input(f"Qtd CC (Central {c_i}):", min_value=0, value=0, key=f"cc_{c_i}_{rcv}")
                eq_outros = st.text_input(f"Outros Tanques / Medidores (Central {c_i}):", key=f"out_eq_{c_i}_{rcv}")
            with col_c3:
                eq_vazao = st.text_input(f"Vazão Calculada (m³/h):", key=f"vazao_{c_i}_{rcv}")
                eq_obs = st.text_input(f"Observações da Central {c_i}:", key=f"obs_c_{c_i}_{rcv}")

            eq_vt_dict[c_i] = {
                "b190": eq_b190,
                "p45": eq_p45,
                "cc": eq_cc,
                "outros": eq_outros,
                "vazao": eq_vazao,
                "obs": eq_obs,
            }

        st.divider()
        st.subheader("3. Relatório Fotográfico (Upload de Fotos)")
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            fotos_fachada = st.file_uploader("Fotos da Fachada:", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"up_fach_{rcv}")
            fotos_central = st.file_uploader("Fotos da Central:", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"up_cent_{rcv}")
        with col_up2:
            fotos_equip = st.file_uploader("Fotos dos Equipamentos:", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"up_eq_{rcv}")
            fotos_cilindros = st.file_uploader("Fotos dos Cilindros / Abrigo:", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"up_cil_{rcv}")

        st.divider()
        col_btn_v1, col_btn_v2 = st.columns(2)
        with col_btn_v1:
            gerar_txt_vis = st.button("📝 Gerar Texto para Sistema", use_container_width=True, key=f"btn_txt_vis_{rcv}")
        with col_btn_v2:
            gerar_pdf_vis = st.button("📄 Gerar Relatório Fotográfico em PDF", type="primary", use_container_width=True, key=f"btn_pdf_vis_{rcv}")

        if gerar_txt_vis:
            linhas_eq = []
            for c_i, d_eq in eq_vt_dict.items():
                linhas_eq.append(
                    f"Central {c_i:02d}: B190={d_eq['b190']} | P45={d_eq['p45']} | CC={d_eq['cc']} | "
                    f"Outros={d_eq['outros'] or 'N/A'} | Vazão={d_eq['vazao'] or 'N/A'} | Obs={d_eq['obs'] or '-'}"
                )
            texto_vis = (
                f"VISITA DE TRANSFERÊNCIA - CONSIGAZ\n"
                f"Cliente: {cod_cliente_vt.strip()} - {nome_cliente_vt.strip()}\n"
                f"Endereço: {endereco_vt.strip()}\n"
                f"Contato: {contato_vt.strip()} | Tel: {tel_vt.strip()}\n"
                f"Responsável: {tecnico_vt.strip()}\n\n"
                f"EQUIPAMENTOS / CENTRAIS:\n" + "\n".join(linhas_eq)
            )
            st.text_area("Texto Gerado:", value=texto_vis, height=220, key=f"area_txt_vis_{rcv}")
            botao_copiar_customizado(texto_vis, "visita_txt")

        if gerar_pdf_vis:
            if not cod_cliente_vt or not nome_cliente_vt:
                st.warning("⚠️ Preencha o Código e Nome do Cliente para gerar o relatório PDF.")
            else:
                pdf = FPDF()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.add_page()

                y_inicio = 12
                if os.path.exists(LOGO_PATH):
                    try:
                        pdf.image(LOGO_PATH, x=12, y=10, w=36)
                        y_inicio = 28
                    except Exception:
                        y_inicio = 12

                pdf.set_y(y_inicio)
                pdf.set_font("Arial", "B", 15)
                pdf.set_text_color(0, 64, 128)
                pdf.cell(0, 9, "RELATORIO FOTOGRAFICO DE VISTORIA", ln=True, align="C")
                pdf.set_text_color(30, 41, 59)
                pdf.set_font("Arial", "", 11)
                pdf.cell(0, 7, f"Cliente: {cod_cliente_vt} - {nome_cliente_vt}", ln=True, align="C")
                if endereco_vt.strip():
                    pdf.cell(0, 7, f"Endereco: {endereco_vt.strip()}", ln=True, align="C")
                pdf.cell(0, 7, f"Contato: {contato_vt} | Tel: {tel_vt} | Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align="C")
                pdf.ln(8)

                categorias_fotos = [
                    ("FACHADA DO ESTABELECIMENTO", fotos_fachada),
                    ("CENTRAL DE GAS", fotos_central),
                    ("EQUIPAMENTOS E MEDIDORES", fotos_equip),
                    ("CILINDROS E ABRIGO", fotos_cilindros),
                ]

                for tit_cat, lista_f in categorias_fotos:
                    if lista_f:
                        pdf.set_font("Arial", "B", 12)
                        pdf.set_text_color(0, 64, 128)
                        pdf.cell(0, 8, tit_cat, ln=True, align="L")
                        pdf.set_text_color(30, 41, 59)
                        pdf.ln(2)
                        for arq in lista_f:
                            try:
                                img = Image.open(arq)
                                img_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                                img.convert("RGB").save(img_tmp.name, "JPEG", quality=85)
                                pdf.image(img_tmp.name, x=25, w=160)
                                pdf.ln(5)
                                os.unlink(img_tmp.name)
                            except Exception:
                                pass
                        pdf.ln(4)

                pdf.add_page()
                pdf.set_font("Arial", "B", 13)
                pdf.set_text_color(0, 64, 128)
                pdf.cell(0, 10, "RESUMO DE EQUIPAMENTOS E VAZAO POR CENTRAL", ln=True, align="L")
                pdf.set_text_color(30, 41, 59)
                pdf.ln(3)

                pdf.set_font("Arial", "B", 10)
                pdf.cell(28, 8, "Central", border=1)
                pdf.cell(25, 8, "Qtd B190", border=1)
                pdf.cell(25, 8, "Qtd CC", border=1)
                pdf.cell(25, 8, "Qtd P45", border=1)
                pdf.cell(45, 8, "Outros", border=1)
                pdf.cell(42, 8, "Vazao (m3/h)", border=1, ln=True)

                pdf.set_font("Arial", "", 10)
                for c_i, d_eq in eq_vt_dict.items():
                    pdf.cell(28, 8, f"Central {c_i:02d}", border=1)
                    pdf.cell(25, 8, str(d_eq["b190"]), border=1)
                    pdf.cell(25, 8, str(d_eq["cc"]), border=1)
                    pdf.cell(25, 8, str(d_eq["p45"]), border=1)
                    pdf.cell(45, 8, str(d_eq["outros"] or "-"), border=1)
                    pdf.cell(42, 8, str(d_eq["vazao"] or "N/A"), border=1, ln=True)

                cod_limpo = "".join(filter(str.isdigit, str(cod_cliente_vt))) or "cliente"
                data_str = datetime.now().strftime("%d-%m-%y")
                nome_pdf = f"relatorio_{cod_limpo}_{data_str}.pdf"
                pdf_bytes = pdf.output(dest="S").encode("latin-1", errors="replace")
                st.success("✅ Relatório PDF gerado com sucesso!")
                st.download_button("📥 Baixar Relatório PDF", data=pdf_bytes, file_name=nome_pdf, mime="application/pdf")

    elif menu_tratativa == "📝 Elaboração de Contrato":
        rcc = st.session_state.reset_counter
        cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento e geração do padrão de solicitação de contrato.")

        if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_elab_{rcc}"):
            st.session_state.reset_counter += 1
            st.rerun()

        st.divider()
        st.subheader("1. Motivo")
        motivo_solicitacao = st.text_area("Descreva claramente o motivo da regularização do contrato:", key=f"motivo_{rcc}")

        st.divider()
        st.subheader("2. Dados do Contrato")
        col_b2_1, col_b2_2 = st.columns(2)
        with col_b2_1:
            tipo_contrato = st.radio("Contrato / Aditamento / Distrato:", ["Contrato", "Aditamento", "Distrato"], horizontal=True, index=None, key=f"tp_cont_{rcc}")
            requisicao_opt = st.radio("Requisição:", ["Permanente", "Provisório"], horizontal=True, index=None, key=f"req_opt_{rcc}")
        with col_b2_2:
            mesmo_prop_opt = st.radio("Mesmo proprietário?(sim/não):", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_prop_{rcc}")

        col_b2_3, col_b2_4 = st.columns(2)
        with col_b2_3:
            cnpj_campo_val = st.text_input("Novo CNPJ:", key=f"novo_cnpj_val_{rcc}")
            ie_campo_val = st.text_input("Nova I.E.:", key=f"nova_ie_val_{rcc}")
        with col_b2_4:
            if len("".join(filter(str.isdigit, str(cnpj_campo_val)))) == 14:
                dados_api = consultar_cnpj_api(cnpj_campo_val)
                if dados_api:
                    razao_social_txt = dados_api.get("razao_social", "Não encontrada")
                    situacao_cad = dados_api.get("situacao_cadastral", dados_api.get("descricao_situacao_cadastral", ""))
                    status_cnpj_txt = "Ativa" if situacao_cad in (2, "2", "ATIVA", "Ativa") else str(situacao_cad)
                    st.markdown(f"✅ **Razão Social:** {razao_social_txt}")
                    st.markdown(f"🟢 **Status CNPJ:** {status_cnpj_txt}")

        st.divider()
        st.subheader("3. Endereço / Equipamentos")
        col_b3_1, col_b3_2 = st.columns(2)
        with col_b3_1:
            endereco_padrao = st.text_input("Endereço padrão ou entrega?:", key=f"end_padrao_{rcc}")
        with col_b3_2:
            qtd_entregas_c = st.number_input("Quantidade de centrais / endereços:", min_value=1, value=1, step=1, key=f"qtd_ent_c_{rcc}")

        eq_dict_c = {}
        if qtd_entregas_c == 1:
            eq_dict_c[1] = st.text_input("Equipamentos:", key=f"eq_ent_1_{rcc}")
        else:
            st.markdown("**Equipamentos por Central / Endereço:**")
            cols_eq_b3 = st.columns(min(int(qtd_entregas_c), 3))
            for i in range(1, int(qtd_entregas_c) + 1):
                with cols_eq_b3[(i - 1) % len(cols_eq_b3)]:
                    eq_dict_c[i] = st.text_input(f"Equipamentos Central {i:02d}:", key=f"eq_ent_{i}_{rcc}")

        st.divider()
        st.subheader("4. Condições Comerciais")
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
                preco_granel = st.text_input("Preço Granel:", key=f"preco_granel_{rcc}")
            with col_g2:
                consumo_granel_input = st.text_input("Consumo previsto (Granel) mensal:", key=f"cons_granel_{rcc}")

        if tipo_fornecimento in ["Cilindro", "Ambos"]:
            st.markdown("**Preço Cilindro por Modelo:**")
            col_cp1, col_cp2, col_cp3 = st.columns(3)
            with col_cp1:
                p13_val = st.text_input("Preço P13:", key=f"p13_v_{rcc}")
            with col_cp2:
                p20_val = st.text_input("Preço P20:", key=f"p20_v_{rcc}")
            with col_cp3:
                p45_val = st.text_input("Preço P45:", key=f"p45_v_{rcc}")

            st.markdown("**Consumo previsto (Cilindro) mensal:**")
            tab_c1, tab_c2 = st.tabs(["Preenchimento por Quantidade de Cilindros", "Preenchimento Direto em KGs"])
            with tab_c1:
                col_cc1, col_cc2, col_cc3 = st.columns(3)
                with col_cc1:
                    p13_qtd = st.number_input("Qtd Cilindros P13", min_value=0, value=0, step=1, key=f"p13_q_{rcc}")
                with col_cc2:
                    p20_qtd = st.number_input("Qtd Cilindros P20", min_value=0, value=0, step=1, key=f"p20_q_{rcc}")
                with col_cc3:
                    p45_qtd = st.number_input("Qtd Cilindros P45", min_value=0, value=0, step=1, key=f"p45_q_{rcc}")
                consumo_cilindro_total_calc = (p13_qtd * 13) + (p20_qtd * 20) + (p45_qtd * 45)
            with tab_c2:
                consumo_cilindro_input_kg = st.text_input("Qual consumo previsto (Cilindro) mensal:", key=f"cons_cil_kg_{rcc}")

        col_cc_out1, col_cc_out2 = st.columns(2)
        with col_cc_out1:
            cond_pagamento = st.text_input("Condição de pagamento:", key=f"cond_pag_{rcc}")
        with col_cc_out2:
            vigencia = st.text_input("Vigência:", key=f"vigencia_{rcc}")

        st.divider()
        st.subheader("5. Financeiro")
        col_fin1, col_fin2 = st.columns(2)
        with col_fin1:
            possui_debito_fin = st.radio("Cliente possui débitos?", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rcc}")
            resp_pendentes = ""
            if possui_debito_fin == "Sim":
                resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", key=f"resp_pend_{rcc}")
        with col_fin2:
            tipo_fluxo = st.radio("Objetivo da solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, index=None, key=f"fluxo_c_{rcc}")

        email_novo_prop = ""
        nome_testemunha, email_testemunha = "", ""
        responsaveis_dados = []

        if tipo_fluxo == "Gerar Minuta":
            st.markdown("**Dados para Minuta:**")
            email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato:", key=f"email_novo_{rcc}")
        elif tipo_fluxo == "Enviar para Assinatura":
            st.markdown("**Dados para Assinatura:**")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                nome_testemunha = st.text_input("Nome da Testemunha:", key=f"nome_test_{rcc}")
            with col_t2:
                email_testemunha = st.text_input("E-mail da Testemunha:", key=f"email_test_{rcc}")

            qtd_responsaveis = st.selectbox("Quantidade de Responsáveis pela Assinatura:", [1, 2, 3, 4], index=0, key=f"qtd_resp_{rcc}")
            for i in range(1, qtd_responsaveis + 1):
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    n_r = st.text_input(f"Nome do Responsável {i} pela assinatura:", key=f"nome_resp_{i}_{rcc}")
                with col_r2:
                    e_r = st.text_input(f"E-mail do Responsável {i} pela assinatura:", key=f"email_resp_{i}_{rcc}")
                responsaveis_dados.append({"nome": n_r, "email": e_r})

        st.divider()
        st.subheader("6. Condomínio CONTA SIM")
        conta_sim = st.radio("Condomínio CONTA SIM?:", ["Sim", "Não"], horizontal=True, index=None, key=f"conta_sim_{rcc}")
        num_unidades, qtd_torres, qtd_blocos, preco_religue, preco_servico = "", "", "", "", ""

        if conta_sim == "Sim":
            col_cs1, col_cs2, col_cs3 = st.columns(3)
            with col_cs1:
                num_unidades = st.text_input("N° Unid autônomas (Aptos + áreas comuns/zeladoria):", key=f"num_unid_{rcc}")
                qtd_torres = st.text_input("Qtd Torres:", key=f"qtd_torres_{rcc}")
            with col_cs2:
                qtd_blocos = st.text_input("Qtd Blocos:", key=f"qtd_blocos_{rcc}")
                preco_religue = st.text_input("Valor preço de religue:", key=f"preco_rel_{rcc}")
            with col_cs3:
                preco_servico = st.text_input("Valor preço de serviço:", key=f"preco_serv_{rcc}")

        st.divider()
        if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
            req_perm = "X" if requisicao_opt == "Permanente" else " "
            req_prov = "X" if requisicao_opt == "Provisório" else " "

            partes_cil = []
            if p13_val.strip():
                partes_cil.append(f"[P13 = {p13_val.strip()} / und]")
            if p20_val.strip():
                partes_cil.append(f"[P20 = {p20_val.strip()} / und]")
            if p45_val.strip():
                partes_cil.append(f"[P45 = {p45_val.strip()} / und]")
            preco_cilindro_str = " ".join(partes_cil)

            consumo_cil_str = ""
            if consumo_cilindro_input_kg.strip():
                consumo_cil_str = consumo_cilindro_input_kg.strip()
            elif consumo_cilindro_total_calc > 0:
                consumo_cil_str = f"{consumo_cilindro_total_calc} KGs"

            if qtd_entregas_c == 1:
                eq_str = eq_dict_c.get(1, "").strip()
            else:
                eq_str = " ".join(
                    [f"[Central {i:02d}: {eq_dict_c.get(i, '').strip()}]" for i in range(1, int(qtd_entregas_c) + 1) if eq_dict_c.get(i, "").strip()]
                )

            resp_ass_nome = " | ".join([r["nome"].strip() for r in responsaveis_dados if r["nome"].strip()])
            resp_ass_email = " | ".join([r["email"].strip() for r in responsaveis_dados if r["email"].strip()])

            texto_padrao_contrato = (
                f"Descreva claramente o motivo da regularização do contrato: {motivo_solicitacao.strip()}\n\n"
                f"Contrato / Aditamento / Distrato: {tipo_contrato or ''}\n"
                f"Requisição ( {req_perm} ) Permanente ( {req_prov} ) Provisório:\n"
                f"Mesmo proprietário?(sim/não): {mesmo_prop_opt or ''}\n"
                f"Novo CNPJ: {cnpj_campo_val.strip()}\n"
                f"Nova I.E.: {ie_campo_val.strip()}\n"
                f"Endereço padrão ou entrega?: {endereco_padrao.strip()}\n"
                f"Preço Granel: {preco_granel.strip()}\n"
                f"Preço Cilindro: {preco_cilindro_str}\n"
                f"Condição de pagamento: {cond_pagamento.strip()}\n"
                f"Consumo previsto (Granel) mensal: {consumo_granel_input.strip()}\n"
                f"Qual consumo previsto (Cilindro) mensal: {consumo_cil_str}\n"
                f"Vigência: {vigencia.strip()}\n"
                f"Equipamentos: {eq_str}\n"
                f"Quem será o responsável pelas NF's pendentes? {resp_pendentes.strip()}\n"
                f"E-mail do novo proprietário que receberá o novo contrato: {email_novo_prop.strip()}\n"
                f"Nome da Testemunha: {nome_testemunha.strip()}\n"
                f"E-mail da Testemunha: {email_testemunha.strip()}\n"
                f"Nome do Responsável pela assinatura: {resp_ass_nome}\n"
                f"E-mail do Responsável pela assinatura: {resp_ass_email}\n\n"
                f"Condomínio CONTA SIM?: {conta_sim or ''}\n"
                f"N° Unid autônomas (Aptos + áreas comuns/zeladoria): {num_unidades.strip()}\n"
                f"Qtd Torres: {qtd_torres.strip()}\n"
                f"Qtd Blocos: {qtd_blocos.strip()}\n"
                f"Valor preço de religue: R$ {preco_religue.strip()}\n"
                f"Valor preço de serviço: R$ {preco_servico.strip()}"
            )

            if tipo_fluxo == "Gerar Minuta":
                texto_padrao_contrato = "** FAVOR GERAR MINUTA PARA ENVIO AO CLIENTE **\n\n" + texto_padrao_contrato

            st.success("✅ Texto padrão gerado com sucesso!")
            st.text_area("Texto Gerado:", value=texto_padrao_contrato, height=440, key=f"txt_area_contrato_{rcc}")
            botao_copiar_customizado(texto_padrao_contrato, "contrato_txt")

    elif menu_tratativa == "📋 Aprovação de Contrato":
        rcap = st.session_state.reset_counter
        cabecalho_pagina("Aprovação de Contrato", "Formulário de regularização e aprovação comercial de contrato.")

        if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_aprov_{rcap}"):
            st.session_state.reset_counter += 1
            st.rerun()

        st.divider()
        st.subheader("1. Motivo")
        motivo_reg = st.text_area("Motivo da regularização:", key=f"motivo_reg_{rcap}")

        st.divider()
        st.subheader("2. Dados de Contato e Identificação")
        col_ap1, col_ap2 = st.columns(2)
        with col_ap1:
            contato_ap = st.text_input("Contato:", key=f"cont_ap_{rcap}")
            tel_ap = st.text_input("Telefone:", key=f"tel_ap_{rcap}")
            email_ap = st.text_input("E-mail:", key=f"email_ap_{rcap}")
        with col_ap2:
            atualizar_email = st.radio("Atualizar E-mail?", ["Sim", "Não"], horizontal=True, index=None, key=f"att_email_{rcap}")
            tp_contrato_ap = st.radio("Contrato / Aditamento:", ["Contrato", "Aditamento"], horizontal=True, index=None, key=f"tp_c_ap_{rcap}")
            vigencia_ap = st.text_input("Vigência:", key=f"vig_ap_{rcap}")

        st.divider()
        st.subheader("3. Redimensionamento e Tanques")
        col_ap3, col_ap4 = st.columns(2)
        with col_ap3:
            redim_opt = st.radio("Redimensionamento?", ["Sim", "Não"], horizontal=True, index=None, key=f"redim_{rcap}")
            comodato_de = st.text_input("Comodato passou de:", key=f"com_de_{rcap}")
            comodato_para = st.text_input("Para:", key=f"com_para_{rcap}")
        with col_ap4:
            inc_tanques = st.radio("Inclusão de tanques?", ["Sim", "Não"], horizontal=True, index=None, key=f"inc_tanq_{rcap}")
            lista_pecas = st.radio("Necessário lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"list_pecas_{rcap}")

        st.divider()
        st.subheader("4. Condomínio e Portaria")
        col_ap5, col_ap6 = st.columns(2)
        with col_ap5:
            conta_sim_ap = st.radio("Implantação de conta sim?", ["Sim", "Não"], horizontal=True, index=None, key=f"cs_ap_{rcap}")
            portaria_tp = st.text_input("Tipo de portaria:", key=f"port_tp_{rcap}")
        with col_ap6:
            contato_resp_port = st.text_input("Contato do responsável:", key=f"resp_port_{rcap}")
            sindico_contato = st.text_input("Contato atualizado do síndico:", key=f"sind_cont_{rcap}")

        particularidades = st.text_area("Particularidades do local:", key=f"partic_{rcap}")

        st.divider()
        st.subheader("5. Alteração de CNPJ / Propriedade")
        col_ap7, col_ap8 = st.columns(2)
        with col_ap7:
            alt_cnpj = st.radio("Alteração de CNPJ ou razão social?", ["Sim", "Não"], horizontal=True, index=None, key=f"alt_cnpj_{rcap}")
            mesmo_prop_ap = st.radio("Se trata do mesmo proprietário?", ["Sim", "Não"], horizontal=True, index=None, key=f"m_prop_ap_{rcap}")
        with col_ap8:
            negociacao_titulos = st.text_input(
                "Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto:",
                key=f"neg_tit_{rcap}",
            )

        st.divider()
        st.subheader("6. Projeto Padrão")
        col_proj1, col_proj2 = st.columns([3, 1])
        with col_proj1:
            num_projeto = st.text_input("Projeto (Informe o número completo do projeto):", key=f"n_proj_{rcap}")
        with col_proj2:
            is_cilindros = st.checkbox("Cilindros (Dispensar Projeto)", key=f"is_cil_{rcap}")

        st.divider()
        if st.button("📝 Gerar Texto de Aprovação de Contrato", type="primary"):
            proj_str = "N/A" if is_cilindros else (num_projeto.strip() or "N/A")

            texto_aprovacao = (
                f"Motivo da regularização: {motivo_reg.strip()}\n\n"
                f"Contato: {contato_ap.strip()} | Telefone: {tel_ap.strip()} | E-mail: {email_ap.strip()}\n"
                f"Atualizar E-mail?: {atualizar_email or 'Não'}\n"
                f"Contrato / Aditamento: {tp_contrato_ap or ''}\n"
                f"Vigência: {vigencia_ap.strip()}\n\n"
                f"Redimensionamento: [ {'x' if redim_opt == 'Sim' else ' '} ] sim [ {'x' if redim_opt == 'Não' else ' '} ] não\n"
                f"Comodato passou de: {comodato_de.strip()} Para: {comodato_para.strip()}\n"
                f"Inclusão de tanques?: [ {'x' if inc_tanques == 'Sim' else ' '} ] sim [ {'x' if inc_tanques == 'Não' else ' '} ] não\n"
                f"Necessário lista de peças?: [ {'x' if lista_pecas == 'Sim' else ' '} ] sim [ {'x' if lista_pecas == 'Não' else ' '} ] não\n\n"
                f"Implantação de conta sim: [ {'x' if conta_sim_ap == 'Sim' else ' '} ] sim [ {'x' if conta_sim_ap == 'Não' else ' '} ] não\n"
            )
            if conta_sim_ap == "Sim":
                texto_aprovacao += (
                    f"Tipo de portaria: {portaria_tp.strip()}\n"
                    f"Contato do responsável: {contato_resp_port.strip()}\n"
                    f"Particularidades do local: {particularidades.strip()}\n"
                    f"Contato atualizado do síndico: {sindico_contato.strip()}\n"
                )
            texto_aprovacao += (
                f"\nAlteração de CNPJ ou razão social?: [ {'x' if alt_cnpj == 'Sim' else ' '} ] sim [ {'x' if alt_cnpj == 'Não' else ' '} ] não\n"
                f"Se trata do mesmo proprietário?: [ {'x' if mesmo_prop_ap == 'Sim' else ' '} ] sim [ {'x' if mesmo_prop_ap == 'Não' else ' '} ] não\n"
                f"Negociação de títulos em aberto: {negociacao_titulos.strip() or 'n/a'}\n\n"
                f"Projeto Padrão: {proj_str}"
            )

            st.success("✅ Texto de Aprovação gerado com sucesso!")
            st.text_area("Texto Gerado:", value=texto_aprovacao, height=400, key=f"txt_area_aprov_{rcap}")
            botao_copiar_customizado(texto_aprovacao, "aprovacao_txt")

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
            ipca_vigente = st.number_input(
                "IPCA acumulado de 12 meses (%) - informe manualmente:",
                min_value=0.0,
                value=4.58,
                step=0.01,
                format="%.2f",
                key=f"ipca_manual_{rca}",
            )

        col_an1, col_an2 = st.columns(2)
        with col_an1:
            preco_anterior_input = st.text_input("Preço Anterior (R$):", value="7,7400", key=f"preco_ant_{rca}")
        with col_an2:
            clausula_contrato = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, index=None, key=f"clausula_{rca}")

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

            p_ant_fmt = preco_anterior_input.strip()
            if not p_ant_fmt.startswith("R$"):
                p_ant_fmt = f"R$ {p_ant_fmt}"

            texto_aniversario = f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%.\n"
            if clausula_contrato == "Sim":
                texto_aniversario += "Cliente possui cláusula em contrato.\n"
            texto_aniversario += f"Preço anterior: {p_ant_fmt}\nPreço Aniversário: R$ {p_aniv_str}"

            st.success("✅ Texto gerado com sucesso!")
            col_v1, col_v2 = st.columns([1, 2])
            with col_v1:
                st.text_input("Preço Novo para Abertura da CI:", value=f"R$ {p_aniv_str}", key=f"valor_novo_ci_{rca}")
            with col_v2:
                st.write("")
                st.write("")
                botao_copiar_customizado(f"R$ {p_aniv_str}", "btn_copy_val_novo", label_btn="💵 Copiar Valor Novo")

            st.text_area("Texto Gerado:", value=texto_aniversario, height=180, key=f"txt_area_aniv_{rca}")
            botao_copiar_customizado(texto_aniversario, "aniversario_txt")

        st.divider()
        st.subheader("Tratativa com C.I.")
        ci_input = st.text_input("Número da C.I. (9 ou 11 dígitos):", placeholder="Ex: 588358982 ou 588.358.982", key=f"ci_num_{rca}")

        if st.button("📝 Gerar Texto Final com C.I.", type="primary"):
            p_ant_fmt = preco_anterior_input.strip()
            if not p_ant_fmt.startswith("R$"):
                p_ant_fmt = f"R$ {p_ant_fmt}"
            ci_fmt = formatar_ci_num(ci_input)

            texto_ci = f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%.\n"
            if clausula_contrato == "Sim":
                texto_ci += "Cliente possui cláusula em contrato.\n"
            texto_ci += f"Preço anterior: {p_ant_fmt}\nPreço Aniversário: R$ {p_aniv_str}\nCI.: {ci_fmt} - Preço Aniversário"

            st.success("✅ Texto com C.I. gerado com sucesso!")
            st.text_area("Texto com C.I.:", value=texto_ci, height=220, key=f"txt_area_ci_{rca}")
            botao_copiar_customizado(texto_ci, "ci_txt")

    elif menu_tratativa == "🪪 Ficha de Cliente":
        rcf = st.session_state.reset_counter
        cabecalho_pagina("Ficha de Cliente", "Preenchimento cadastral e comercial estruturado para registro no sistema.")

        if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_fc_{rcf}"):
            st.session_state.reset_counter += 1
            st.rerun()

        st.divider()
        st.subheader("1. Motivo")
        fc_motivo = st.text_area("Motivo:", value="", key=f"fc_motivo_{rcf}")

        st.divider()
        st.subheader("2. Identificação do Cliente")
        col_fc1, col_fc2 = st.columns(2)
        with col_fc1:
            fc_codigo = st.text_input("Código do Cliente:", value="", key=f"fc_cod_{rcf}")
            fc_razao = st.text_input("Razão Social / Nome:", value="", key=f"fc_raz_{rcf}")
            fc_cnpj = st.text_input("CNPJ / CPF:", value="", key=f"fc_cnpj_{rcf}")
            fc_ie = st.text_input("Inscrição Estadual (I.E.):", value="", key=f"fc_ie_{rcf}")
        with col_fc2:
            fc_endereco = st.text_input("Endereço Completo:", value="", key=f"fc_end_{rcf}")
            fc_contato = st.text_input("Pessoa de Contato:", value="", key=f"fc_cont_{rcf}")
            fc_telefone = st.text_input("Telefone:", value="", key=f"fc_tel_{rcf}")
            fc_email = st.text_input("E-mail:", value="", key=f"fc_email_{rcf}")

        st.divider()
        st.subheader("3. Condições Comerciais e Fornecimento")
        fc_forn = st.radio("Modalidade de Fornecimento:", ["Granel", "Cilindro", "Ambos"], horizontal=True, index=None, key=f"fc_forn_{rcf}")

        fc_preco_granel, fc_cons_granel = "", ""
        fc_preco_cil, fc_cons_cil = "", ""

        if fc_forn in ["Granel", "Ambos"]:
            col_fc_g1, col_fc_g2 = st.columns(2)
            with col_fc_g1:
                fc_preco_granel = st.text_input("Preço Granel:", value="", key=f"fc_pg_{rcf}")
            with col_fc_g2:
                fc_cons_granel = st.text_input("Consumo Previsto Granel:", value="", key=f"fc_cg_{rcf}")

        if fc_forn in ["Cilindro", "Ambos"]:
            col_fc_c1, col_fc_c2 = st.columns(2)
            with col_fc_c1:
                fc_preco_cil = st.text_input("Preço Cilindro:", value="", key=f"fc_pc_{rcf}")
            with col_fc_c2:
                fc_cons_cil = st.text_input("Consumo Previsto Cilindro:", value="", key=f"fc_cc_{rcf}")

        col_fc_out1, col_fc_out2, col_fc_out3 = st.columns(3)
        with col_fc_out1:
            fc_pagamento = st.text_input("Condição de Pagamento:", value="", key=f"fc_pag_{rcf}")
        with col_fc_out2:
            fc_vigencia = st.text_input("Vigência:", value="", key=f"fc_vig_{rcf}")
        with col_fc_out3:
            fc_equipamentos = st.text_input("Equipamentos / Tanques:", value="", key=f"fc_eq_{rcf}")

        st.divider()
        st.subheader("4. Observação")
        fc_observacao = st.text_area("Observação:", value="", key=f"fc_obs_{rcf}")

        st.divider()
        if st.button("📝 Gerar Texto da Ficha de Cliente", type="primary", key=f"btn_gerar_fc_{rcf}"):
            linhas_fc = [
                f"Motivo: {fc_motivo.strip()}",
                "",
                f"Código do Cliente: {fc_codigo.strip()}",
                f"Razão Social / Nome: {fc_razao.strip()}",
                f"CNPJ / CPF: {fc_cnpj.strip()}",
                f"Inscrição Estadual: {fc_ie.strip()}",
                f"Endereço: {fc_endereco.strip()}",
                f"Contato: {fc_contato.strip()} | Telefone: {fc_telefone.strip()} | E-mail: {fc_email.strip()}",
                f"Modalidade de Fornecimento: {fc_forn or ''}",
            ]
            if fc_forn in ["Granel", "Ambos"]:
                linhas_fc.append(f"Preço Granel: {fc_preco_granel.strip()}")
                linhas_fc.append(f"Consumo Previsto Granel: {fc_cons_granel.strip()}")
            if fc_forn in ["Cilindro", "Ambos"]:
                linhas_fc.append(f"Preço Cilindro: {fc_preco_cil.strip()}")
                linhas_fc.append(f"Consumo Previsto Cilindro: {fc_cons_cil.strip()}")

            linhas_fc.extend([
                f"Condição de Pagamento: {fc_pagamento.strip()}",
                f"Vigência: {fc_vigencia.strip()}",
                f"Equipamentos: {fc_equipamentos.strip()}",
                "",
                f"Observação: {fc_observacao.strip()}",
            ])
            texto_fc = "\n".join(linhas_fc)
            st.success("✅ Texto da Ficha de Cliente gerado com sucesso!")
            st.text_area("Texto Gerado:", value=texto_fc, height=360, key=f"txt_area_fc_{rcf}")
            botao_copiar_customizado(texto_fc, "ficha_cliente_txt")

# =====================================================================
# ABA 2: AGENDA DE OCORRÊNCIAS
# =====================================================================
elif aba_principal == "📊 Agenda de Ocorrências":
    cabecalho_pagina("Agenda de Ocorrências", "Gestão operacional de prazos, SLAs, filtros avançados e indicadores por cidade.")

    opcoes_visao = ["Todas Ocorrências", "Comodato Inativo", "Ocorrências por Cidade"]
    if st.session_state.e_supervisor or st.session_state.e_admin:
        opcoes_visao.append("📊 Dashboard de Gestão (Gráficos)")
        opcoes_visao.append("📈 Ocorrências por Classificação")

    tipo_visao_agenda = st.sidebar.radio("Selecione a Visão:", opcoes_visao, index=0)

    st.sidebar.markdown(
        """
        <div class="legenda-status-box">
            <div class="legenda-status-titulo">Legenda de Status</div>
            <div class="legenda-status-item">🔴 Vencido</div>
            <div class="legenda-status-item">🔵 Vence Hoje</div>
            <div class="legenda-status-item">🟠 Vence Amanhã</div>
            <div class="legenda-status-item">🟡 Vence na Semana</div>
            <div class="legenda-status-item">🟢 No Prazo</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader("📥 Importar Planilha de Ocorrências (.xlsx / .xls)", type=["xlsx", "xls"], key="uploader_agenda_oc")

    if uploaded_file is not None:
        try:
            df_raw = pd.read_excel(uploaded_file)
            df = df_raw.copy()

            def achar_coluna(padroes, default_idx=0):
                for p in padroes:
                    for c in df.columns:
                        if p in str(c).lower():
                            return c
                return df.columns[default_idx] if len(df.columns) > default_idx else None

            col_oc = achar_coluna(["número da ocorrência", "numero da ocorrencia", "ocorrência", "ocorrencia", "número", "numero"])
            col_cli = achar_coluna(["nome do cliente", "cliente", "razão social", "razao social"])
            col_end = achar_coluna(["endereço", "endereco", "entrega"])
            col_prazo = achar_coluna(["prazo de atendimento", "prazo", "vencimento", "data limite"])
            col_class = achar_coluna(["subclassificação", "subclassificacao", "classificação", "classificacao", "tipo"])
            col_cons = achar_coluna(["consultor", "responsável", "responsavel", "proprietário", "proprietario"])
            col_fech = achar_coluna(["fechamento", "encerramento"])

            if col_fech and col_fech in df.columns:
                df = df[df[col_fech].isna() | (df[col_fech].astype(str).str.strip().isin(["", "nan", "NaT", "None"]))]

            df["_OC_ID"] = df[col_oc].astype(str).str.strip()
            df = df[~df["_OC_ID"].isin(st.session_state.tratadas_manualmente)].copy()

            hoje = pd.Timestamp.now().normalize()
            if col_prazo and col_prazo in df.columns:
                prazos_dt = pd.to_datetime(df[col_prazo], dayfirst=True, errors="coerce")
                df["SLA"] = prazos_dt.apply(lambda d: calcular_dias_uteis(hoje, d) if pd.notna(d) else 99)
                df["Prazo Formatado"] = prazos_dt.dt.strftime("%d/%m/%Y").fillna("-")
            else:
                df["SLA"] = 99
                df["Prazo Formatado"] = "-"

            df["Status"] = df["SLA"].apply(classificar_bolinha_sla)
            df["Cidade"] = df[col_end].apply(extrair_cidade) if col_end in df.columns else "-"
            df["Classificação Limpa"] = df[col_class].fillna("Sem Classificação").astype(str).str.strip() if col_class in df.columns else "Geral"
            df["Consultor"] = df[col_cons].fillna("Não Atribuído").astype(str).str.strip() if col_cons in df.columns else st.session_state.nome_usuario_atual

            df_base_visao = df.sort_values(by="SLA", ascending=True).reset_index(drop=True)

            if tipo_visao_agenda == "📈 Ocorrências por Classificação" and (st.session_state.e_supervisor or st.session_state.e_admin):
                st.subheader("📈 Gestão de Ocorrências por Classificação")
                lista_cons_class = ["Todos"] + sorted(list(df_base_visao["Consultor"].unique()))
                cons_sel_class = st.selectbox("Filtrar por Consultor:", lista_cons_class, key="sel_cons_class")

                df_class_vis = df_base_visao if cons_sel_class == "Todos" else df_base_visao[df_base_visao["Consultor"] == cons_sel_class]

                if df_class_vis.empty:
                    st.info("Nenhum registro encontrado para os filtros selecionados.")
                else:
                    df_class_agrup = df_class_vis.groupby("Classificação Limpa").size().reset_index(name="Total").sort_values(by="Total", ascending=False)
                    col_tab_c, col_graf_c = st.columns(2)
                    with col_tab_c:
                        st.markdown("#### 📋 Quantitativo por Classificação")
                        st.dataframe(
                            df_class_agrup.rename(columns={"Classificação Limpa": "Classificação", "Total": "Qtd Ocorrências"}),
                            hide_index=True,
                            use_container_width=True,
                        )
                    with col_graf_c:
                        st.markdown("#### 📊 Gráfico Comparativo")
                        chart_class = (
                            alt.Chart(df_class_agrup)
                            .mark_bar(color="#004080", cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
                            .encode(
                                x=alt.X("Total:Q", title="Quantidade de Ocorrências"),
                                y=alt.Y("Classificação Limpa:N", sort="-x", title="Classificação"),
                                tooltip=["Classificação Limpa", "Total"],
                            )
                            .properties(height=360)
                        )
                        st.altair_chart(chart_class, use_container_width=True)

            elif tipo_visao_agenda == "📊 Dashboard de Gestão (Gráficos)" and (st.session_state.e_supervisor or st.session_state.e_admin):
                st.subheader("📊 Dashboard Executivo de Gestão - Indicadores por Consultor")
                graficos_config = [
                    ("🔴 Ocorrências Vencidas por Consultor", df_base_visao[df_base_visao["SLA"] < 0], "#D32F2F"),
                    ("🔵 Vencimento Hoje por Consultor", df_base_visao[df_base_visao["SLA"] == 0], "#1976D2"),
                    ("🟠 Vencimento Amanhã por Consultor", df_base_visao[df_base_visao["SLA"] == 1], "#F57C00"),
                    ("🟡 Vencimento em até 05 Dias por Consultor", df_base_visao[(df_base_visao["SLA"] >= 2) & (df_base_visao["SLA"] <= 5)], "#FBC02D"),
                    ("🟢 No Prazo por Consultor", df_base_visao[df_base_visao["SLA"] > 0], "#388E3C"),
                ]

                for i in range(0, len(graficos_config), 2):
                    col_g1, col_g2 = st.columns(2)
                    with col_g1:
                        tit1, df_g1, cor1 = graficos_config[i]
                        st.markdown(f"#### {tit1}")
                        if not df_g1.empty:
                            df_ag1 = df_g1.groupby("Consultor").size().reset_index(name="Total").sort_values(by="Total", ascending=False)
                            ch1 = (
                                alt.Chart(df_ag1)
                                .mark_bar(color=cor1, cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
                                .encode(
                                    x=alt.X("Total:Q", title="Total de Ocorrências"),
                                    y=alt.Y("Consultor:N", sort="-x", title="Consultor"),
                                    tooltip=["Consultor", "Total"],
                                )
                                .properties(height=240)
                            )
                            st.altair_chart(ch1, use_container_width=True)
                            st.dataframe(df_ag1.rename(columns={"Total": "Qtd Ocorrências"}), hide_index=True, use_container_width=True)
                        else:
                            st.info("Nenhum registro para este critério.")

                    if i + 1 < len(graficos_config):
                        with col_g2:
                            tit2, df_g2, cor2 = graficos_config[i + 1]
                            st.markdown(f"#### {tit2}")
                            if not df_g2.empty:
                                df_ag2 = df_g2.groupby("Consultor").size().reset_index(name="Total").sort_values(by="Total", ascending=False)
                                ch2 = (
                                    alt.Chart(df_ag2)
                                    .mark_bar(color=cor2, cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
                                    .encode(
                                        x=alt.X("Total:Q", title="Total de Ocorrências"),
                                        y=alt.Y("Consultor:N", sort="-x", title="Consultor"),
                                        tooltip=["Consultor", "Total"],
                                    )
                                    .properties(height=240)
                                )
                                st.altair_chart(ch2, use_container_width=True)
                                st.dataframe(df_ag2.rename(columns={"Total": "Qtd Ocorrências"}), hide_index=True, use_container_width=True)
                            else:
                                st.info("Nenhum registro para este critério.")
                    st.divider()

            elif tipo_visao_agenda == "Ocorrências por Cidade":
                st.subheader("🏙️ Ocorrências por Cidade")
                df_cid_agrup = (
                    df_base_visao.groupby("Cidade")
                    .size()
                    .reset_index(name="Total Ocorrências")
                    .sort_values(by="Total Ocorrências", ascending=False)
                )
                col_tab_cid, col_graf_cid = st.columns(2)
                with col_tab_cid:
                    st.markdown("#### 📋 Quantitativo por Cidade")
                    st.dataframe(df_cid_agrup, hide_index=True, use_container_width=True)
                with col_graf_cid:
                    st.markdown("#### 📊 Distribuição Visual")
                    chart_cid = (
                        alt.Chart(df_cid_agrup)
                        .mark_bar(color="#004080", cornerRadiusTopRight=6, cornerRadiusBottomRight=6)
                        .encode(
                            x=alt.X("Total Ocorrências:Q", title="Quantidade de OCs"),
                            y=alt.Y("Cidade:N", sort="-x", title="Cidade"),
                            tooltip=["Cidade", "Total Ocorrências"],
                        )
                        .properties(height=380)
                    )
                    st.altair_chart(chart_cid, use_container_width=True)

            elif tipo_visao_agenda == "Comodato Inativo":
                st.subheader("⚠️ Acompanhamento de Comodato Inativo")
                df_com = df_base_visao[df_base_visao["Classificação Limpa"].str.contains("comodato|inativo", case=False, na=False)].copy()
                if df_com.empty:
                    df_com = df_base_visao.copy()

                def classificar_semana_comodato(sla_val):
                    if sla_val < 0:
                        return "🔴 3ª Semana"
                    elif sla_val <= 5:
                        return "🟡 2ª Semana"
                    return "🟢 1ª Semana"

                df_com["Semana"] = df_com["SLA"].apply(classificar_semana_comodato)
                tot_com = len(df_com)
                sem3_qt = len(df_com[df_com["Semana"] == "🔴 3ª Semana"])
                sem2_qt = len(df_com[df_com["Semana"] == "🟡 2ª Semana"])
                sem1_qt = len(df_com[df_com["Semana"] == "🟢 1ª Semana"])

                b_c1, b_c2, b_c3, b_c4 = st.columns(4)
                if b_c1.button(f"**{tot_com}**\nTotal", use_container_width=True, key="btn_com_tot"):
                    st.session_state.filtro_sla_comodato = "Total"
                if b_c2.button(f"**{sem3_qt}**\n3ª Semana", use_container_width=True, key="btn_com_s3"):
                    st.session_state.filtro_sla_comodato = "🔴 3ª Semana"
                if b_c3.button(f"**{sem2_qt}**\n2ª Semana", use_container_width=True, key="btn_com_s2"):
                    st.session_state.filtro_sla_comodato = "🟡 2ª Semana"
                if b_c4.button(f"**{sem1_qt}**\n1ª Semana", use_container_width=True, key="btn_com_s1"):
                    st.session_state.filtro_sla_comodato = "🟢 1ª Semana"

                if st.session_state.filtro_sla_comodato != "Total":
                    df_com = df_com[df_com["Semana"] == st.session_state.filtro_sla_comodato]

                cols_exibir_com = ["Semana", col_oc, col_cli, "Cidade", "Prazo Formatado", "Classificação Limpa"]
                cols_exibir_com = [c for c in cols_exibir_com if c in df_com.columns]
                st.dataframe(df_com[cols_exibir_com], hide_index=True, use_container_width=True)

                buf_excel = BytesIO()
                with pd.ExcelWriter(buf_excel, engine="openpyxl") as writer:
                    df_com[cols_exibir_com].to_excel(writer, index=False, sheet_name="Comodato_Inativo")
                st.download_button(
                    "📥 Baixar Planilha Comodato Inativo (.xlsx)",
                    data=buf_excel.getvalue(),
                    file_name=f"comodato_inativo_{datetime.now().strftime('%d-%m-%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            else:
                total_visitas = len(df_base_visao)
                vencidas_qt = len(df_base_visao[df_base_visao["SLA"] < 0])
                hoje_qt = len(df_base_visao[df_base_visao["SLA"] == 0])
                amanha_qt = len(df_base_visao[df_base_visao["SLA"] == 1])
                cinco_dias_qt = len(df_base_visao[(df_base_visao["SLA"] >= 0) & (df_base_visao["SLA"] <= 5)])

                c_f1, c_f2, c_f3, c_f4, c_f5 = st.columns(5)
                if c_f1.button(f"**{total_visitas}**\nTotal", use_container_width=True, key="btn_sla_tot"):
                    st.session_state.filtro_sla_agenda = "Total"
                if c_f2.button(f"**{vencidas_qt}**\nVencidas", use_container_width=True, key="btn_sla_venc"):
                    st.session_state.filtro_sla_agenda = "Vencidas"
                if c_f3.button(f"**{hoje_qt}**\nVence Hoje", use_container_width=True, key="btn_sla_hoje"):
                    st.session_state.filtro_sla_agenda = "Vence Hoje"
                if c_f4.button(f"**{amanha_qt}**\nVence Amanhã", use_container_width=True, key="btn_sla_amanha"):
                    st.session_state.filtro_sla_agenda = "Vence Amanhã"
                if c_f5.button(f"**{cinco_dias_qt}**\nVencem na Semana", use_container_width=True, key="btn_sla_sem"):
                    st.session_state.filtro_sla_agenda = "Vencem na Semana"

                df_filtrado = df_base_visao.copy()
                f_sla = st.session_state.filtro_sla_agenda
                if f_sla == "Vencidas":
                    df_filtrado = df_filtrado[df_filtrado["SLA"] < 0]
                elif f_sla == "Vence Hoje":
                    df_filtrado = df_filtrado[df_filtrado["SLA"] == 0]
                elif f_sla == "Vence Amanhã":
                    df_filtrado = df_filtrado[df_filtrado["SLA"] == 1]
                elif f_sla == "Vencem na Semana":
                    df_filtrado = df_filtrado[(df_filtrado["SLA"] >= 0) & (df_filtrado["SLA"] <= 5)]

                st.write("")
                col_sel1, col_sel2 = st.columns(2)
                with col_sel1:
                    cidades_disp = ["Todas"] + sorted([c for c in df_filtrado["Cidade"].unique() if c != "-"])
                    cid_sel = st.selectbox("Filtrar por Cidade:", cidades_disp, key="filtro_cidade_todas")
                with col_sel2:
                    classes_disp = ["Todas"] + sorted(list(df_filtrado["Classificação Limpa"].unique()))
                    class_sel = st.selectbox("Filtrar por Classificação:", classes_disp, key="filtro_class_todas")

                if cid_sel != "Todas":
                    df_filtrado = df_filtrado[df_filtrado["Cidade"] == cid_sel]
                if class_sel != "Todas":
                    df_filtrado = df_filtrado[df_filtrado["Classificação Limpa"] == class_sel]

                cols_tabela = ["Status", col_oc, col_cli, "Cidade", "Prazo Formatado", "Classificação Limpa"]
                cols_tabela = [c for c in cols_tabela if c in df_filtrado.columns]
                df_exibicao = df_filtrado[cols_tabela].rename(columns={"Prazo Formatado": "Prazo", "Classificação Limpa": "Classificação"})

                st.dataframe(
                    df_exibicao,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Status": st.column_config.TextColumn("Status", width="small"),
                        col_oc: st.column_config.TextColumn("Ocorrência", width="medium"),
                        col_cli: st.column_config.TextColumn("Cliente", width="large"),
                        "Cidade": st.column_config.TextColumn("Cidade", width="medium"),
                        "Prazo": st.column_config.TextColumn("Prazo", width="small"),
                        "Classificação": st.column_config.TextColumn("Classificação", width="medium"),
                    },
                )

                if not df_filtrado.empty:
                    st.divider()
                    opcoes_oc_acao = [
                        f"{row[col_oc]} — {row[col_cli]}" for _, row in df_filtrado.iterrows()
                    ]
                    col_ac1, col_ac2, col_ac3 = st.columns([2.5, 1, 1])
                    with col_ac1:
                        oc_escolhida_str = st.selectbox("Selecionar Ocorrência para Ação:", opcoes_oc_acao, key="sel_oc_acao")
                    idx_esc = opcoes_oc_acao.index(oc_escolhida_str)
                    row_esc = df_filtrado.iloc[idx_esc]
                    with col_ac2:
                        st.write("")
                        if st.button("✅ Marcar Tratada", use_container_width=True, key="btn_marcar_tratada"):
                            st.session_state.tratadas_manualmente.add(str(row_esc["_OC_ID"]))
                            st.rerun()
                    with col_ac3:
                        st.write("")
                        if st.button("👉 Iniciar Tratativa", type="primary", use_container_width=True, key="btn_iniciar_tratativa"):
                            st.session_state.ocorrencia_ativa = {
                                "codigo": str(row_esc[col_oc]),
                                "cliente": str(row_esc[col_cli]),
                            }
                            st.info("Dados capturados! Selecione 'Tratativa de Ocorrências' no menu lateral.")

        except Exception as e:
            st.error(f"Erro ao processar planilha: {e}")
    else:
        st.info("💡 Faça o upload da planilha de ocorrências (.xlsx ou .xls) acima para visualizar a agenda.")

# =====================================================================
# ABA 3: STATUS DE CONTRATOS
# =====================================================================
elif aba_principal == "📑 Status de Contratos":
    renderizar_painel_acompanhamento("contrato")

# =====================================================================
# ABA 4: STATUS DE VENDAS
# =====================================================================
elif aba_principal == "💼 Status de Vendas":
    renderizar_painel_acompanhamento("venda")

# =====================================================================
# ABA 5: BLOCO DE NOTAS PESSOAL (PERSISTENTE EM NUVEM VIA SUPABASE)
# =====================================================================
elif aba_principal == "📝 Bloco de Notas Pessoal":
    cabecalho_pagina("Bloco de Notas Pessoal", "Suas anotações individuais salvas com segurança na nuvem.")

    usuario_logado = st.session_state.usuario_atual
    url_sb, key_sb = get_supabase_config()

    def carregar_notas_usuario():
        if url_sb and key_sb:
            res = sb_select("bloco_notas", {"usuario": f"eq.{usuario_logado}", "order": "updated_at.desc"})
            if isinstance(res, list):
                return {str(item["id"]): item for item in res}
        return st.session_state.notas_locais

    notas_dict = carregar_notas_usuario()

    col_n_lat, col_n_edit = st.columns([1, 2.4])
    with col_n_lat:
        if st.button("➕ Nova Nota", type="primary", use_container_width=True, key="btn_nova_nota"):
            novo_id = str(uuid.uuid4())
            nova_nota = {
                "id": novo_id,
                "usuario": usuario_logado,
                "titulo": f"Nota {datetime.now().strftime('%d/%m %H:%M')}",
                "conteudo": "",
            }
            if url_sb and key_sb:
                sb_insert("bloco_notas", nova_nota)
            else:
                st.session_state.notas_locais[novo_id] = nova_nota
            st.session_state.nota_selecionada_id = novo_id
            st.rerun()

        st.markdown("#### Minhas Notas")
        if not notas_dict:
            st.info("Nenhuma nota criada ainda.")
        else:
            for n_id, n_data in notas_dict.items():
                if st.button(n_data.get("titulo") or "Sem Título", key=f"btn_n_{n_id}", use_container_width=True):
                    st.session_state.nota_selecionada_id = n_id
                    st.rerun()

    with col_n_edit:
        sel_id = st.session_state.nota_selecionada_id
        if not sel_id and notas_dict:
            sel_id = next(iter(notas_dict.keys()))
            st.session_state.nota_selecionada_id = sel_id

        if sel_id and sel_id in notas_dict:
            nota_atual = notas_dict[sel_id]
            titulo_edit = st.text_input("Título da Nota:", value=nota_atual.get("titulo", ""), key=f"tit_n_{sel_id}")
            conteudo_edit = st.text_area("Conteúdo:", value=nota_atual.get("conteudo", ""), height=320, key=f"cont_n_{sel_id}")

            bn1, bn2 = st.columns(2)
            with bn1:
                if st.button("💾 Salvar Nota", type="primary", use_container_width=True, key=f"salv_n_{sel_id}"):
                    if url_sb and key_sb:
                        sb_update(
                            "bloco_notas",
                            {"id": f"eq.{sel_id}"},
                            {"titulo": titulo_edit.strip() or "Sem Título", "conteudo": conteudo_edit, "updated_at": datetime.utcnow().isoformat()},
                        )
                    else:
                        st.session_state.notas_locais[sel_id]["titulo"] = titulo_edit.strip() or "Sem Título"
                        st.session_state.notas_locais[sel_id]["conteudo"] = conteudo_edit
                    st.success("✅ Nota salva com sucesso!")
                    st.rerun()
            with bn2:
                if st.button("🗑️ Excluir Nota", use_container_width=True, key=f"del_n_{sel_id}"):
                    if url_sb and key_sb:
                        sb_delete("bloco_notas", {"id": f"eq.{sel_id}"})
                    else:
                        st.session_state.notas_locais.pop(sel_id, None)
                    st.session_state.nota_selecionada_id = None
                    st.rerun()
        else:
            st.info("Clique em **➕ Nova Nota** à esquerda para começar a escrever.")

# =====================================================================
# ABA 6: PAINEL ADMIN (USUÁRIOS, SENHA INICIAL 123456 E PERMISSÕES)
# =====================================================================
elif aba_principal == "⚙️ Painel Admin":
    cabecalho_pagina("Painel Administrativo", "Gestão de usuários, senhas e níveis de permissão via Supabase.")

    url_sb, key_sb = get_supabase_config()
    if not url_sb or not key_sb:
        st.warning("⚠️ Configure `SUPABASE_URL` e `SUPABASE_KEY` em `.streamlit/secrets.toml` para persistência em nuvem.")

    st.subheader("1. Cadastrar Novo Usuário")
    with st.form("form_criar_usuario"):
        cu1, cu2, cu3 = st.columns(3)
        with cu1:
            novo_user_login = st.text_input("Login do Usuário:").strip().lower()
        with cu2:
            novo_user_nome = st.text_input("Nome Completo:").strip()
        with cu3:
            novo_user_perfil = st.selectbox("Perfil de Acesso:", ["Convencional", "Supervisor", "Admin"])

        criar_u_btn = st.form_submit_button("➕ Criar Usuário (Senha Inicial: 123456)", type="primary")
        if criar_u_btn:
            if not novo_user_login or not novo_user_nome:
                st.warning("⚠️ Informe o login e o nome completo.")
            else:
                ok, err = sb_insert(
                    "usuarios",
                    {
                        "usuario": novo_user_login,
                        "nome": novo_user_nome,
                        "perfil": novo_user_perfil,
                        "senha_hash": hash_senha("123456"),
                        "primeiro_acesso": True,
                    },
                )
                if ok:
                    st.success(f"✅ Usuário `{novo_user_login}` criado com senha inicial `123456`!")
                    st.rerun()
                else:
                    st.error(f"Erro ao criar usuário: {err}")

    st.divider()
    st.subheader("2. Usuários Cadastrados")
    lista_users = sb_select("usuarios", {"order": "usuario.asc"})
    if isinstance(lista_users, list) and lista_users:
        df_u = pd.DataFrame(lista_users)
        cols_u = [c for c in ["usuario", "nome", "perfil", "primeiro_acesso"] if c in df_u.columns]
        st.dataframe(df_u[cols_u], hide_index=True, use_container_width=True)

        user_alvo = st.selectbox("Selecionar Usuário para Gerenciar:", [u["usuario"] for u in lista_users], key="sel_user_admin")
        au1, au2, au3 = st.columns(3)
        with au1:
            novo_perf_sel = st.selectbox("Alterar Perfil para:", ["Convencional", "Supervisor", "Admin"], key="sel_novo_perf")
            if st.button("💾 Atualizar Perfil", use_container_width=True, key="btn_att_perf"):
                sb_update("usuarios", {"usuario": f"eq.{user_alvo}"}, {"perfil": novo_perf_sel})
                st.success("✅ Perfil atualizado!")
                st.rerun()
        with au2:
            st.write("")
            st.write("")
            if st.button("🔄 Resetar Senha para Inicial (123456)", type="primary", use_container_width=True, key="btn_reset_123"):
                sb_update("usuarios", {"usuario": f"eq.{user_alvo}"}, {"senha_hash": hash_senha("123456"), "primeiro_acesso": True})
                st.success(f"✅ Senha de `{user_alvo}` resetada para `123456`!")
        with au3:
            st.write("")
            st.write("")
            if st.button("🗑️ Remover Usuário do Banco", use_container_width=True, key="btn_rem_u"):
                sb_delete("usuarios", {"usuario": f"eq.{user_alvo}"})
                st.success(f"✅ Usuário `{user_alvo}` removido!")
                st.rerun()
    else:
        st.info("Nenhum usuário listado ou banco Supabase não conectado.")

# =====================================================================
# RODAPÉ DA BARRA LATERAL (DADOS DO USUÁRIO E LOGOUT)
# =====================================================================
st.sidebar.divider()
st.sidebar.markdown(
    f"👤 **Usuário:** {st.session_state.nome_usuario_atual}\n\n"
    f"🛡️ **Perfil:** {st.session_state.perfil_usuario}"
)
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state.clear()
    st.rerun()
