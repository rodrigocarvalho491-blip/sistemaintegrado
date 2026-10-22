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

# --- CONFIGURAÇÃO GLOBAL DA PÁGINA (LOGO / FOGUINHO NA ABA) ---
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
# IDENTIDADE VISUAL CONSIGAZ - DESIGN MODERNO (COMPATÍVEL DARK/LIGHT)
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
  gap: 1.5rem; 
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
.cg-logo { height: 55px; width: auto; display: block; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.05)); }
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
.cg-side-logo { height: 45px; width: auto; display: inline-block; }
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

/* Divisor elegante */
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


def _logo_html(classe):
    b64 = _logo_base64(LOGO_PATH)
    if not b64:
        return ""
    return f'<img class="{classe}" src="data:image/png;base64,{b64}" alt="Consigaz">'


def cabecalho_pagina(titulo, subtitulo):
    logo = _logo_html("cg-logo")
    separador = '<div class="cg-header-sep"></div>' if logo else ""
    st.markdown(
        f'<div class="cg-header">{logo}{separador}<div>'
        f'<div class="cg-title">{html_lib.escape(titulo)}</div>'
        f'<div class="cg-subtitle">{html_lib.escape(subtitulo)}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

# --- FUNÇÃO DE CONSULTA AUTOMÁTICA DE CNPJ ---
def consultar_cnpj_api(cnpj_input):
    cnpj_limpo = "".join(filter(str.isdigit, str(cnpj_input)))
    if len(cnpj_limpo) == 14:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception:
            return None
    return None

# --- FUNÇÃO PARA OBTER O IPCA ACUMULADO DE 12 MESES ATUALIZADO DO IBGE ---
IPCA_VALOR_RESERVA = 4.58

@st.cache_data(ttl=3600, show_spinner=False)
def _buscar_ipca_ibge():
    url = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-1/variaveis/2265?localidades=N1[1]"
    response = requests.get(url, timeout=6)
    response.raise_for_status()
    data = response.json()
    resultado = data[0]["resultados"][0]
    series = resultado.get("series") or resultado.get("séries")
    serie = series[0].get("serie") or series[0].get("série")
    ultimo_periodo = sorted(serie.keys())[-1]
    val_str = serie[ultimo_periodo]
    if not val_str or str(val_str).strip() in ("-", "..", "...", "X"):
        raise ValueError("IBGE retornou valor vazio para o período.")
    return float(val_str), ultimo_periodo

def obter_ipca_acumulado_12m():
    try:
        valor, periodo = _buscar_ipca_ibge()
        if len(periodo) == 6:
            periodo = f"{periodo[4:6]}/{periodo[0:4]}"
        return valor, periodo
    except Exception:
        return None, None

# --- INICIALIZAÇÃO DO SESSION STATE ---
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

if "reset_counter_contrato" not in st.session_state:
    st.session_state.reset_counter_contrato = 0

if "reset_counter_aprov" not in st.session_state:
    st.session_state.reset_counter_aprov = 0

if "reset_counter_aniv" not in st.session_state:
    st.session_state.reset_counter_aniv = 0

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

def resetar_dados_contrato():
    st.session_state.reset_counter_contrato += 1

def resetar_dados_aprov():
    st.session_state.reset_counter_aprov += 1

def resetar_dados_aniv():
    st.session_state.reset_counter_aniv += 1

# --- COMPONENTE DE BOTÃO DE CÓPIA ---
def botao_copiar_customizado(texto_para_copiar, chave_unica):
    texto_norm = str(texto_para_copiar).replace("\r\n", "\n").replace("\r", "\n")
    texto_js = json.dumps(texto_norm).replace("</", "<\\/")

    component_html = f"""
    <div style="margin-top: 10px; margin-bottom: 15px;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background: linear-gradient(135deg, #0055A5 0%, #003366 100%);
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 12px;
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-weight: 700;
            font-size: 14px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(0, 85, 165, 0.25);
            transition: all 0.2s ease;
        ">
            📋 Copiar Texto Completo
        </button>
        <span id="msg_{chave_unica}" style="margin-left: 12px; color: #10B981; font-weight: bold; font-size: 13.5px; display: none;">Copiado com sucesso!</span>
    </div>
    <script>
    const TEXTO_{chave_unica} = {texto_js};

    function escapeHtml_{chave_unica}(s) {{
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }}

    function copiarFallback_{chave_unica}(texto) {{
        const ta = document.createElement('textarea');
        ta.value = texto;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        let ok = false;
        try {{ ok = document.execCommand('copy'); }} catch (e) {{ ok = false; }}
        document.body.removeChild(ta);
        return ok;
    }}

    function mostrarMsg_{chave_unica}(ok) {{
        const msg = document.getElementById("msg_{chave_unica}");
        msg.textContent = ok ? "Copiado com sucesso!" : "Não foi possível copiar automaticamente.";
        msg.style.display = "inline";
        setTimeout(function() {{
            msg.style.display = "none";
        }}, 2500);
    }}

    async function copiarTexto_{chave_unica}() {{
        let ok = false;
        try {{
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                await navigator.clipboard.writeText(TEXTO_{chave_unica});
                ok = true;
            }}
        }} catch (e) {{
            ok = false;
        }}
        if (!ok) {{
            ok = copiarFallback_{chave_unica}(TEXTO_{chave_unica});
        }}
        mostrarMsg_{chave_unica}(ok);
    }}
    </script>
    """
    components.html(component_html, height=60)

# --- MENU LATERAL DE NAVEGAÇÃO ---
st.sidebar.markdown(
    f'<div class="cg-side-brand">{_logo_html("cg-side-logo")}'
    f'<div class="cg-side-name">Central de Atendimentos</div></div>',
    unsafe_allow_html=True,
)
menu = st.sidebar.radio(
    "Selecione a página:",
    [
        "📷 Visita de Transferência",
        "📝 Elaboração de Contrato",
        "📋 Aprovação de Contrato",
        "🎂 Aniversário de Contrato"
    ],
    label_visibility="collapsed"
)

st.sidebar.divider()
if st.sidebar.button("🔄 Novo Cliente"):
    resetar_dados_cliente()
    resetar_dados_contrato()
    resetar_dados_aprov()
    resetar_dados_aniv()
    st.rerun()


# =====================================================================
# TELA 1: VISITA DE TRANSFERÊNCIA (Relatório Técnico & Fotos)
# =====================================================================
if menu == "📷 Visita de Transferência":
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
        desc_debitos = st.text_input("Detalhes dos Débitos (se houver)", key=f"desc_debitos_{rc}") if possui_debitos == "Sim" else ""

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
                for idx, arq in enumerate(arquivos):
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
            botao_copiar_customizado(texto_final, "transferencia_txt")


# =====================================================================
# TELA 2: ELABORAÇÃO DE CONTRATO
# =====================================================================
elif menu == "📝 Elaboração de Contrato":
    rcc = st.session_state.reset_counter_contrato

    cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento e geração do padrão de solicitação.")

    st.divider()

    tipo_fluxo = st.radio(
        "Selecione o objetivo da solicitação:", 
        ["Gerar Minuta", "Enviar para Assinatura"],
        horizontal=True,
        index=None,
        key=f"fluxo_c_{rcc}"
    )

    st.divider()

    st.subheader("1. Motivo")
    motivo_solicitacao = st.text_input("Motivo da solicitação", key=f"motivo_{rcc}")

    st.divider()

    st.subheader("2. Dados do Cliente")
    col_cli1, col_cli2, col_cli3 = st.columns(3)
    with col_cli1:
        contato_contrato = st.text_input("Contato", key=f"contato_c_{rcc}")
    with col_cli2:
        telefone_contrato = st.text_input("Telefone", key=f"tel_c_{rcc}")
    with col_cli3:
        email_contrato = st.text_input("E-mail", key=f"email_c_{rcc}")

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
                if situacao_cad == 2 or str(situacao_cad).upper() == "ATIVA":
                    status_cnpj_txt = "Ativo"
                else:
                    status_cnpj_txt = f"Inativa ({situacao_cad})"
                
                st.markdown(f"✅ **Razão Social:** {razao_social_txt}")
                st.markdown(f"🟢 **Status CNPJ:** {status_cnpj_txt}")
            else:
                st.warning("⚠️ CNPJ não encontrado ou erro na consulta automática.")

    with col_con2:
        cond_pagamento = st.text_input("Condição de pagamento", key=f"cond_pag_{rcc}")
        vigencia = st.text_input("Vigência", key=f"vigencia_{rcc}")
        
        qtd_entregas_c = st.number_input("Quantidade de endereços de entrega / centrais", min_value=1, value=1, step=1, key=f"qtd_ent_c_{rcc}")
        
        equipamentos_contrato = ""
        eq_dict_c = {}
        if qtd_entregas_c == 1:
            equipamentos_contrato = st.text_input("Equipamentos", key=f"eq_contrato_c_{rcc}")
        else:
            st.markdown("**Equipamentos por Endereço de Entrega:**")
            for i in range(1, int(qtd_entregas_c) + 1):
                eq_dict_c[i] = st.text_input(f"Equipamentos - [Entrega {i}]", key=f"eq_ent_{i}_{rcc}")

    st.divider()

    st.subheader("5. Comodato / Fornecimento")
    
    tipo_fornecimento = st.radio("Tipo de Fornecimento", ["Granel", "Cilindro"], horizontal=True, index=None, key=f"tp_forn_{rcc}")
    
    preco_granel = ""
    consumo_granel = ""
    
    p13_val, p20_val, p45_val = "", "", ""
    p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
    consumo_cilindro_total = 0
    
    if tipo_fornecimento == "Granel":
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            preco_granel = st.text_input("Preço Granel", key=f"preco_granel_{rcc}")
        with col_g2:
            consumo_granel = st.text_input("Consumo mensal previsto (kgs)", key=f"cons_granel_{rcc}")
        
    elif tipo_fornecimento == "Cilindro":
        st.markdown("**Preços por Modelo de Cilindro:**")
        col_cp1, col_cp2, col_cp3 = st.columns(3)
        with col_cp1:
            p13_val = st.text_input("Preço P13 (/und)", key=f"p13_v_{rcc}")
        with col_cp2:
            p20_val = st.text_input("Preço P20 (/und)", key=f"p20_v_{rcc}")
        with col_cp3:
            p45_val = st.text_input("Preço P45 (/und)", key=f"p45_v_{rcc}")

        st.markdown("**Consumo mensal previsto (qntd):**")
        col_cc1, col_cc2, col_cc3 = st.columns(3)
        with col_cc1:
            p13_qtd = st.number_input("Qtd Cilindros P13", min_value=0, value=0, step=1, key=f"p13_q_{rcc}")
        with col_cc2:
            p20_qtd = st.number_input("Qtd Cilindros P20", min_value=0, value=0, step=1, key=f"p20_q_{rcc}")
        with col_cc3:
            p45_qtd = st.number_input("Qtd Cilindros P45", min_value=0, value=0, step=1, key=f"p45_q_{rcc}")
        
        consumo_cilindro_total = (p13_qtd * 13) + (p20_qtd * 20) + (p45_qtd * 45)

    st.divider()

    st.subheader("6. Financeiro")
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        possui_debito_fin = st.radio("Cliente possui débitos?", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rcc}")
        
        resp_pendentes = "n/a"
        if possui_debito_fin == "Sim":
            resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", key=f"resp_pend_{rcc}")

    responsaveis_dados = []
    nome_testemunha, email_testemunha = "", ""

    if tipo_fluxo == "Enviar para Assinatura":
        st.markdown("---")
        st.subheader("Dados de Assinatura e Testemunhas")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            nome_testemunha = st.text_input("Nome da Testemunha", key=f"nome_test_{rcc}")
        with col_t2:
            email_testemunha = st.text_input("E-mail da Testemunha", key=f"email_test_{rcc}")

        st.markdown("---")
        qtd_responsaveis = st.selectbox("Quantidade de Responsáveis pela Assinatura", [1, 2, 3, 4], index=0, key=f"qtd_resp_{rcc}")

        for i in range(1, qtd_responsaveis + 1):
            st.markdown(f"**Responsável {i}**")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                nome_resp = st.text_input(f"Nome do Responsável {i}", key=f"nome_resp_{i}_{rcc}")
            with col_r2:
                email_resp = st.text_input(f"E-mail do Responsável {i}", key=f"email_resp_{i}_{rcc}")
            responsaveis_dados.append({"nome": nome_resp, "email": email_resp})

    st.divider()

    st.subheader("7. Condomínio CONTA SIM")
    conta_sim = st.radio("Condomínio CONTA SIM?", ["Sim", "Não"], horizontal=True, index=None, key=f"conta_sim_{rcc}")

    num_unidades = ""
    qtd_torres = ""
    qtd_blocos = ""
    preco_religue = ""
    preco_servico = ""

    if conta_sim == "Sim":
        col_cs1, col_cs2, col_cs3 = st.columns(3)
        with col_cs1:
            num_unidades = st.text_input("N° Unid autônomas (Aptos + áreas comuns/zeladoria)", key=f"num_unid_{rcc}")
            qtd_torres = st.text_input("Qtd Torres", key=f"qtd_torres_{rcc}")
        with col_cs2:
            qtd_blocos = st.text_input("Qtd Blocos", key=f"qtd_blocos_{rcc}")
            preco_religue = st.text_input("Valor preço de religue", key=f"preco_rel_{rcc}")
        with col_cs3:
            preco_servico = st.text_input("Valor preço de serviço", key=f"preco_servico_{rcc}")

    st.write("")
    observacoes_contrato = st.text_area("Obs.", key=f"obs_c_{rcc}")

    st.divider()
    if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
        
        sel_granel = "[x]" if tipo_fornecimento == "Granel" else "[ ]"
        sel_cilindro = "[x]" if tipo_fornecimento == "Cilindro" else "[ ]"
        
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
            texto_padrao_contrato += f"""
CNPJ: {cnpj_campo_val}
I.E.: {ie_campo_val}"""
        elif mesmo_cnpj_opt == "Não":
            texto_padrao_contrato += f"""
Novo CNPJ: {cnpj_campo_val}
Nova I.E.: {ie_campo_val}"""

        if razao_social_txt:
            texto_padrao_contrato += f"\nRazão Social (Consultada): {razao_social_txt}"
        if status_cnpj_txt:
            texto_padrao_contrato += f"\nStatus CNPJ: {status_cnpj_txt}"

        texto_padrao_contrato += f"""
Endereço padrão ou entrega?: {endereco_padrao}
Tipo de Fornecimento: {sel_granel} Granel  {sel_cilindro} Cilindro"""

        if tipo_fornecimento == "Granel":
            texto_padrao_contrato += f"\nPreço Granel: {preco_granel} /kg"
            texto_padrao_contrato += f"\nConsumo mensal previsto: {consumo_granel}"
            
        elif tipo_fornecimento == "Cilindro":
            partes_cil = []
            if p13_val.strip():
                partes_cil.append(f"[P13 = {p13_val.strip()} / und]")
            if p20_val.strip():
                partes_cil.append(f"[P20 = {p20_val.strip()} / und]")
            if p45_val.strip():
                partes_cil.append(f"[P45 = {p45_val.strip()} / und]")
            
            preco_cilindro_str = " ".join(partes_cil) if partes_cil else ""
            texto_padrao_contrato += f"\nPreço Cilindro: {preco_cilindro_str}"
            texto_padrao_contrato += f"\nConsumo mensal previsto: {consumo_cilindro_total} KGs"

        texto_padrao_contrato += f"""
Condição de pagamento: {cond_pagamento}
Vigência: {vigencia}"""

        if qtd_entregas_c == 1:
            texto_padrao_contrato += f"\nEquipamentos: {equipamentos_contrato}"
        else:
            eq_linhas = []
            for i in range(1, int(qtd_entregas_c) + 1):
                val_eq_i = eq_dict_c[i].strip()
                if val_eq_i:
                    eq_linhas.append(f"[Entrega {i}] {val_eq_i}")
            texto_padrao_contrato += "\nEquipamentos:\n" + "\n".join(eq_linhas)

        texto_padrao_contrato += f"""

Cliente possui débitos?: {possui_debito_fin}
Quem será o responsável pelas NF's pendentes? {resp_pendentes}"""

        if tipo_fluxo == "Enviar para Assinatura":
            texto_padrao_contrato += f"""
Nome da Testemunha: {nome_testemunha}
E-mail da Testemunha: {email_testemunha}"""

            if len(responsaveis_dados) == 1:
                texto_padrao_contrato += f"""
Nome do Responsável pela assinatura: {responsaveis_dados[0]['nome']}
E-mail do Responsável pela assinatura: {responsaveis_dados[0]['email']}"""
            else:
                for idx, resp in enumerate(responsaveis_dados, 1):
                    texto_padrao_contrato += f"""
Nome do Responsável {idx}: {resp['nome']}
E-mail do Responsável {idx}: {resp['email']}"""

        texto_padrao_contrato += f"""

Condomínio CONTA SIM?: {conta_sim}"""

        if conta_sim == "Sim":
            texto_padrao_contrato += f"""
N° Unid autônomas (Aptos + áreas comuns/zeladoria): {num_unidades}
Qtd Torres: {qtd_torres}
Qtd Blocos: {qtd_blocos}
Valor preço de religue: {preco_religue}
Valor preço de serviço: {preco_servico}"""

        texto_padrao_contrato += f"""

Obs.: {observacoes_contrato}"""

        st.success("✅ Texto padrão gerado com sucesso! Copie abaixo:")
        st.text_area("Texto Gerado:", value=texto_padrao_contrato, height=250, key=f"txt_area_contrato_{rcc}")
        botao_copiar_customizado(texto_padrao_contrato, "contrato_txt")


# =====================================================================
# TELA 3: APROVAÇÃO DE CONTRATO
# =====================================================================
elif menu == "📋 Aprovação de Contrato":
    rcap = st.session_state.reset_counter_aprov

    cabecalho_pagina("Aprovação de Contrato", "Formulário de preenchimento para solicitação de aprovação.")

    st.divider()

    st.subheader("1. Informações de Contato")
    c_ap1, c_ap2, c_ap3 = st.columns(3)
    with c_ap1:
        contato_ap = st.text_input("Contato *", key=f"ap_cont_{rcap}")
    with c_ap2:
        telefone_ap = st.text_input("Telefone *", key=f"ap_tel_{rcap}")
    with c_ap3:
        email_ap = st.text_input("E-mail *", key=f"ap_email_{rcap}")

    st.divider()

    st.subheader("2. Dados e Motivo da Solicitação")
    motivo_reg = st.text_input("Motivo da regularização *", key=f"ap_motivo_{rcap}")

    c_ap4, c_ap5, c_ap6 = st.columns(3)
    with c_ap4:
        atualizar_email = st.radio("Atualizar E-mail?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_atu_email_{rcap}")
    with c_ap5:
        contrato_adit = st.radio("Contrato / Aditamento", ["Contrato", "Aditamento"], horizontal=True, index=None, key=f"ap_tp_cont_{rcap}")
    with c_ap6:
        vigencia_ap = st.text_input("Vigência", key=f"ap_vig_{rcap}")

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
        with c_p1:
            comodato_de = st.text_input("Comodato passou de:", key=f"ap_com_de_{rcap}")
        with c_p2:
            comodato_para = st.text_input("Para:", key=f"ap_com_para_{rcap}")
        
        c_p3, c_p4 = st.columns(2)
        with c_p3:
            inc_tanques = st.radio("Inclusão de tanques?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_inc_tanq_{rcap}")
        with c_p4:
            env_pecas = st.radio("Necessário lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_env_pec_{rcap}")

    st.divider()

    st.subheader("4. Condomínio Conta Sim & Portaria")
    implantacao_csim = st.radio("Implantação de conta sim:", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_{rcap}")
    
    env_pecas_ficha = "Não"
    env_ficha_cliente = "Não"
    tp_portaria = ""
    contato_resp_port = ""
    part_local = ""
    contato_sindico = ""

    if implantacao_csim == "Sim":
        c_cs1, c_cs2 = st.columns(2)
        with c_cs1:
            env_pecas_ficha = st.radio("Foi enviado lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_pec_{rcap}")
        with c_cs2:
            env_ficha_cliente = st.radio("Foi enviado ficha de clientes?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_ficha_{rcap}")

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
    with col_proj1:
        projeto_num = st.text_input("Projeto (Informe o número completo do projeto) *", key=f"ap_proj_{rcap}")
    with col_proj2:
        st.write("")
        st.write("")
        is_cilindros = st.checkbox("Cilindros", key=f"ap_cil_{rcap}")

    st.divider()

    if st.button("📝 Gerar Texto de Aprovação de Contrato", type="primary"):
        
        if not is_cilindros and not projeto_num.strip():
            st.error("⚠️ O campo 'Projeto' é obrigatório, a menos que a opção 'Cilindros' esteja marcada.")
        else:
            proj_final = "N/A" if is_cilindros else projeto_num
            
            if possui_titulos_aberto == "Não":
                neg_final = "n/a"
            elif possui_titulos_aberto == "Sim":
                neg_final = neg_tit_input.strip() if neg_tit_input.strip() else "n/a"
            else:
                neg_final = "n/a"

            if qtd_entregas_ap == 1:
                eq_ap_texto = equipamentos_ap
            else:
                eq_ap_linhas = []
                for i in range(1, int(qtd_entregas_ap) + 1):
                    val_e = eq_dict_ap[i].strip()
                    if val_e:
                        eq_ap_linhas.append(f"[Entrega {i}] {val_e}")
                eq_ap_texto = "\n" + "\n".join(eq_ap_linhas) if eq_ap_linhas else ""

            conta_sim_bloco = f"Implantação de conta sim: [ {'x' if implantacao_csim == 'Sim' else ' '} ] sim [ {'x' if implantacao_csim == 'Não' else ' '} ] não"
            if implantacao_csim == "Sim":
                conta_sim_bloco += f"""
Foi enviado lista de peças? [ {'x' if env_pecas_ficha == 'Sim' else ' '} ] sim [ {'x' if env_pecas_ficha == 'Não' else ' '} ] não
Foi enviado ficha de clientes? [ {'x' if env_ficha_cliente == 'Sim' else ' '} ] sim [ {'x' if env_ficha_cliente == 'Não' else ' '} ] não
Tipo de portaria: {tp_portaria}
Contato do responsável (em caso de portaria remota, informar o número do apartamento ou a forma de contato do responsável): {contato_resp_port}
Particularidades do local: {part_local}
Contato atualizado do síndico: {contato_sindico}"""

            texto_aprovacao = f"""Motivo da regularização: {motivo_reg}

Contato: {contato_ap}
Telefone: {telefone_ap}
E-mail: {email_ap}

Atualizar E-mail? {atualizar_email if atualizar_email else ''}
Contrato / Aditamento: {contrato_adit if contrato_adit else ''}
Vigência: {vigencia_ap}
Equipamentos: {eq_ap_texto}
Existe especificidade sobre a solicitação: {especificidade_ap}

Redimensionamento: [ {'x' if redim == 'Sim' else ' '} ] sim [ {'x' if redim == 'Não' else ' '} ] não
Projeto (Informe o número completo do projeto): {proj_final}
Comodato passou de: {comodato_de}
Para: {comodato_para}
Inclusão de tanques? [ {'x' if inc_tanques == 'Sim' else ' '} ] sim [ {'x' if inc_tanques == 'Não' else ' '} ] não (se sim, enviar informações para a ficha)
Necessário lista de peças? [ {'x' if env_pecas == 'Sim' else ' '} ] sim [ {'x' if env_pecas == 'Não' else ' '} ] não (se sim, enviar lista de peças):

{conta_sim_bloco}

Alteração de CNPJ ou razão social? [ {'x' if alt_cnpj == 'Sim' else ' '} ] sim [ {'x' if alt_cnpj == 'Não' else ' '} ] não
Se trata do mesmo proprietário: ( {'X' if mesmo_prop_opt == 'Sim' else ' '} ) SIM ( {'X' if mesmo_prop_opt == 'Não' else ' '} ) NÃO
Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto: {neg_final}

Redução de vigência? [ {'x' if red_vig == 'Sim' else ' '} ] sim [ {'x' if red_vig == 'Não' else ' '} ] não
(Se sim, descreva o motivo): {motivo_red_vig}"""

            st.success("✅ Texto de Aprovação gerado com sucesso! Copie abaixo:")
            st.text_area("Texto Gerado:", value=texto_aprovacao, height=350, key=f"txt_area_aprov_{rcap}")
            botao_copiar_customizado(texto_aprovacao, "aprovacao_txt")


# =====================================================================
# TELA 4: ANIVERSÁRIO DE CONTRATO
# =====================================================================
elif menu == "🎂 Aniversário de Contrato":
    rca = st.session_state.reset_counter_aniv

    cabecalho_pagina("Aniversário de Contrato", "Tratativa de reajuste por IPCA acumulado de 12 meses.")

    st.divider()

    ipca_api, ipca_periodo = obter_ipca_acumulado_12m()
    if ipca_api is not None:
        ipca_vigente = ipca_api
        st.info(f"📊 **IPCA Acumulado de 12 meses (IBGE, referência {ipca_periodo}):** {ipca_vigente:.2f}%")
    else:
        st.warning(
            "⚠️ Não foi possível consultar o IPCA no IBGE agora. "
            "Confira o índice oficial e informe o valor abaixo antes de gerar o texto."
        )
        ipca_vigente = st.number_input(
            "IPCA acumulado de 12 meses (%) - informado manualmente",
            min_value=0.0,
            value=float(IPCA_VALOR_RESERVA),
            step=0.01,
            format="%.2f",
            key=f"ipca_manual_{rca}"
        )

    col_an1, col_an2 = st.columns(2)
    with col_an1:
        preco_anterior_input = st.text_input("Preço Anterior (R$)", key=f"preco_ant_{rca}")
    with col_an2:
        st.write("")

    clausula_contrato = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, index=None, key=f"clausula_{rca}")

    st.divider()

    p_aniv_str = "xx,xx"
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

        texto_aniversario = f"""Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%."""

        if clausula_contrato == "Sim":
            texto_aniversario += "\n\nCliente possui cláusula em contrato."

        texto_aniversario += f"""

Preço anterior: R$ {preco_anterior_input if preco_anterior_input else 'xx,xx'}
Preço Aniversário: R$ {p_aniv_str}"""

        st.success("✅ Texto gerado com sucesso! Copie abaixo:")
        st.text_area("Texto Gerado:", value=texto_aniversario, height=180, key=f"txt_area_aniv_{rca}")
        botao_copiar_customizado(texto_aniversario, "aniversario_txt")

    st.divider()

    st.subheader("Tratativa com C.I.")
    ci_input = st.text_input("Número da C.I.", key=f"ci_num_{rca}")

    if st.button("📝 Gerar Texto com C.I.", type="primary"):
        texto_ci = f"""Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%."""

        if clausula_contrato == "Sim":
            texto_ci += "\n\nCliente possui cláusula em contrato."

        texto_ci += f"""

Preço anterior: R$ {preco_anterior_input if preco_anterior_input else 'xx,xx'}
Preço Aniversário: R$ {p_aniv_str}

CI.: {ci_input if ci_input else '000.000.000'} - Preço Aniversário"""

        st.success("✅ Texto com C.I. gerado com sucesso! Copie abaixo:")
        st.text_area("Texto Gerado:", value=texto_ci, height=200, key=f"txt_area_ci_{rca}")
        botao_copiar_customizado(texto_ci, "ci_txt")
