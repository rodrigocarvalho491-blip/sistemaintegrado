import os
import pandas as pd
import numpy as np
import streamlit as st
import requests
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from fpdf import FPDF
import streamlit.components.v1 as components

# --- CONFIGURAÇÃO GLOBAL DA PÁGINA ---
st.set_page_config(page_title="Sistema Integrado de Ocorrências", page_icon="⚙️", layout="wide")

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")

CUSTOM_CSS = """
<style>
    h1, h2, h3 { color: #004080 !important; font-family: 'Segoe UI', sans-serif; }
    div.stButton > button:first-child {
        background-color: #004080 !important; color: #ffffff !important;
        border-radius: 8px !important; border: none !important; font-weight: bold !important;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- FUNÇÃO DE CONSULTA AUTOMÁTICA DE CNPJ ---
def consultar_cnpj_api(cnpj_input):
    cnpj_limpo = "".join(filter(str.isdigit, str(cnpj_input)))
    if len(cnpj_limpo) == 14:
        url = f"https://publica.cnpj.ws/cnpj/{cnpj_limpo}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception:
            return None
    return None

# --- INICIALIZAÇÃO DO SESSION STATE ---
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

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

# --- MENU LATERAL DE NAVEGAÇÃO ---
st.sidebar.title("📌 Menu de Navegação")
menu = st.sidebar.radio(
    "Selecione a página:", 
    [
        "📷 Visita de Transferência",
        "📝 Elaboração de Contrato"
    ]
)

st.sidebar.divider()
if st.sidebar.button("🔄 Resetar Sessão Completa"):
    st.session_state.clear()
    st.rerun()


# =====================================================================
# TELA 1: VISITA DE TRANSFERÊNCIA (Relatório Técnico & Fotos)
# =====================================================================
if menu == "📷 Visita de Transferência":
    rc = st.session_state.reset_counter
    ekc = st.session_state.eq_key_counter

    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Visita de Transferência & Relatório Técnico")
        st.markdown("Gerador automatizado de relatórios técnicos e inspeções.")

    st.divider()

    st.button("🔄 Novo Cliente / Limpar", on_click=resetar_dados_cliente)

    # --- SEÇÃO 1: DADOS DO CLIENTE ---
    st.subheader("1. Identificação do Cliente")
    s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
    with s1_l1_c1:
        cod_cliente = st.text_input("Código do Cliente *", placeholder="Ex: 87.653", key=f"input_cod_{rc}")
    with s1_l1_c2:
        nome_cliente = st.text_input("Nome / Razão Social *", placeholder="Ex: SABOR DA TERRA", key=f"input_nome_{rc}")
    with s1_l1_c3:
        telefone = st.text_input("Telefone *", placeholder="Ex: 12-992586760", key=f"input_tel_{rc}")

    s1_l2_c1, s1_l2_c2, s1_l2_c3 = st.columns(3)
    with s1_l2_c1:
        contato = st.text_input("Contato *", placeholder="Ex: Nilton", key=f"input_contato_{rc}")
    with s1_l2_c2:
        departamento = st.text_input("Sobrenome ou Departamento *", placeholder="Ex: Gerente", key=f"input_depto_{rc}")
    with s1_l2_c3:
        st.write("")

    st.divider()

    # --- SEÇÃO 2: INFORMAÇÕES CONTRATUAIS ---
    st.subheader("2. Informações Contratuais")
    s2_l1_c1, s2_l1_c2, s2_l1_c3, s2_l1_c4 = st.columns(4)
    with s2_l1_c1:
        eq_contrato = st.selectbox("Equipamentos de acordo com contrato? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"eq_contrato_{rc}")
    with s2_l1_c2:
        desc_eq_contrato = st.text_input("Quais equipamentos disponíveis? *", placeholder="Ex: 01 B190...", key=f"desc_eq_contrato_{rc}")
    with s2_l1_c3:
        tem_freq = st.selectbox("Possui programação cadastrada? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"tem_freq_{rc}")
    with s2_l1_c4:
        desc_freq = ""
        if tem_freq == "Sim":
            desc_freq = st.text_input("Qual a programação? *", placeholder="Ex: QUINZENAL", key=f"freq_cad_sim_{rc}")
        elif tem_freq == "Não":
            desc_freq = st.text_input("Nº OC de Cadastramento *", placeholder="Ex: SOL PROGRAMAÇÃO", key=f"freq_cad_nao_{rc}")
        else:
            st.write("")

    s2_l2_c1, s2_l2_c2 = st.columns(2)
    with s2_l2_c1:
        consumo_previsto = st.text_input("Consumo Previsto (kg) *", placeholder="Ex: 250", key=f"cons_prev_{rc}")
    with s2_l2_c2:
        consumo_real = st.text_input("Consumo Real/Médio (kg) *", placeholder="Ex: 137", key=f"cons_real_{rc}")

    s2_l3_c1, s2_l3_c2 = st.columns(2)
    with s2_l3_c1:
        possui_art = st.selectbox("Possui ART? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"possui_art_{rc}")
    with s2_l3_c2:
        desc_art = ""
        if possui_art == "Sim":
            desc_art = st.text_input("Número da ART *", placeholder="Ex: 262026126...", key=f"art_sim_{rc}")
        elif possui_art == "Não":
            desc_art = st.text_input("Nº OC de Solicitação de Laudo *", placeholder="Ex: INF LAUDO", key=f"art_nao_{rc}")
        else:
            st.write("")

    s2_l4_c1, s2_l4_c2 = st.columns(2)
    with s2_l4_c1:
        possui_debitos = st.selectbox("Cliente possui débitos? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"possui_debitos_{rc}")
    with s2_l4_c2:
        desc_debitos = st.text_input("Detalhes dos Débitos (se houver)", placeholder="Ex: Fatura vencida", key=f"desc_debitos_{rc}") if possui_debitos == "Sim" else ""

    s2_l5_c1, s2_l5_c2 = st.columns(2)
    with s2_l5_c1:
        central_norma = st.selectbox("Central dentro de norma? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"central_norma_{rc}")
    with s2_l5_c2:
        desc_central_norma = st.text_input("Motivo da Central fora de norma", placeholder="Ex: Falta extintor", key=f"desc_central_norma_{rc}") if central_norma == "Não" else ""

    s2_l6_c1, s2_l6_c2 = st.columns(2)
    with s2_l6_c1:
        rep2_correto = st.selectbox("Representante 2 está correto? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"rep2_correto_{rc}")
    with s2_l6_c2:
        desc_rep2 = st.text_input("Nº OC de Regularização", placeholder="Ex: ALT DIVERSAS", key=f"desc_rep2_{rc}") if rep2_correto == "Não" else ""

    st.divider()

    # --- SEÇÃO 3: CADASTRO DE EQUIPAMENTOS / CENTRAIS ---
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
            nome_eq_input = st.text_input("Equipamento", placeholder="Ex: Forno", key=f"eq_nome_{rc}_{ekc}")
        with col_vaz:
            vazao_input = st.text_input("Vazão (kg/h)", placeholder="Ex: 1 ou 1,6", key=f"eq_vazao_{rc}_{ekc}")
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
            modelo_input = st.text_input("Modelo", placeholder="Ex: P20", key=f"cil_mod_{rc}_{ekc}")
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
        indica_negocios = st.selectbox("Indicou novos negócios? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"ind_neg_{rc}")
    with s4_l1_c2:
        cliente_satisfeito = st.selectbox("Cliente satisfeito com a Consigaz? *", ["Sim", "Não"], index=None, placeholder="Selecione", key=f"cli_sat_{rc}")

    observacoes = st.text_area("Observações Gerais", placeholder="Detalhes da visita...", key=f"obs_{rc}")

    st.divider()

    st.subheader("5. Relatório Fotográfico")
    def carregar_fotos(label, max_arq=None):
        fotos = st.file_uploader(label, type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_{label}_{
