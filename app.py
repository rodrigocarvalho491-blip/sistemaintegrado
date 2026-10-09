import os
import pandas as pd
import numpy as np
import streamlit as st
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

# --- MAPEAMENTO DAS COLUNAS DO EXCEL ---
COL_OCORRENCIA = "Número da ocorrência"
COL_CLIENTE = "Nome do cliente"
COL_ENDERECO = "Endereço de Entrega"
COL_ABERTURA = "Data/Hora de abertura"
COL_PRAZO = "Prazo de Atendimento"
COL_FECHAMENTO = "Data/Hora de fechamento"
COL_SUB_CLASSIF = "Subclassificação Ocorrência"

# --- INICIALIZAÇÃO DO SESSION STATE ---
if "tratadas_manualmente" not in st.session_state:
    st.session_state.tratadas_manualmente = set()

if "ocorrencia_ativa" not in st.session_state:
    st.session_state.ocorrencia_ativa = {"codigo": "", "cliente": ""}

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

# --- FUNÇÕES AUXILIARES DE DATAS E CIDADES ---
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
        return "🔴 Vencido"
    elif dias_uteis == 0:
        return "🔵 Vence Hoje"
    elif dias_uteis == 1:
        return "🟠 Vence Amanhã"
    elif 2 <= dias_uteis <= 5:
        return "🟡 Vence na Semana"
    else:
        return "🟢 No Prazo"

def classificar_status_comodato(dias_uteis):
    if dias_uteis < 0:
        return "🔴 Vencido"
    elif dias_uteis == 0:
        return "🔵 Vence Hoje"
    elif dias_uteis == 1:
        return "🟠 Vence Amanhã"
    elif dias_uteis <= 5:
        return "🔴 3ª Semana"
    elif dias_uteis <= 10:
        return "🟡 2ª Semana"
    else:
        return "🟢 1ª Semana"

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
    ["📊 Dashboard de Ocorrências", "📷 Tratativa & Relatório Técnico"]
)

st.sidebar.divider()
if st.sidebar.button("🔄 Resetar Sessão Completa"):
    st.session_state.clear()
    st.rerun()

# =====================================================================
# TELA 1: DASHBOARD DE OCORRÊNCIAS (Menu Principal)
# =====================================================================
if menu == "📊 Dashboard de Ocorrências":
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
        else:
            st.caption("📷 *Adicione 'logo.png' na pasta*")
    with col_titulo:
        st.title("Gestão de Ocorrências & Visitas")
        st.markdown("Painel de organização de agenda ordenado por prazo de atendimento (Dias Úteis).")

    st.divider()
    st.subheader("1. Atualização de Dados (Excel)")
    arquivo_excel = st.file_uploader("Faça o upload do relatório Excel (Pós-Vendas) 📂", type=["xlsx", "xls"])

    if arquivo_excel is not None:
        try:
            df_raw = pd.read_excel(arquivo_excel, header=None)
            header_row = None
            for i, row in df_raw.iterrows():
                row_str = " ".join(row.astype(str).values)
                if "Número da ocorrência" in row_str:
                    header_row = i
                    break
            
            df = pd.read_excel(arquivo_excel, header=header_row if header_row is not None else 11)
            df.columns = df.columns.str.strip()
            df = df.dropna(subset=[COL_OCORRENCIA])
            
            df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
            df_pendentes[COL_OCORRENCIA] = pd.to_numeric(df_pendentes[COL_OCORRENCIA], errors='coerce')
            df_pendentes = df_pendentes.dropna(subset=[COL_OCORRENCIA])
            df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
            df_pendentes = df_pendentes[~df_pendentes[COL_OCORRENCIA].isin(st.session_state.tratadas_manualmente)]
            
            df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
            df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
            df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
            df_pendentes[COL_SUB_CLASSIF] = df_pendentes[COL_SUB_CLASSIF].fillna("-").astype(str)
            
            hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            df_pendentes['Dias Úteis Restantes'] = df_pendentes['Prazo_DT'].apply(lambda x: calcular_dias_uteis(hoje, x))
            df_pendentes['Status Geral'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_geral)
            df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
            
            st.subheader("2. Agenda Geral de Visitas Pendentes")
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                mostrar_so_hoje = st.toggle("📅 Mostrar apenas ocorrências com prazo PARA HOJE", value=False)
            with col_t2:
                mostrar_so_semana = st.toggle("🗓️ Mostrar apenas os próximos 5 dias úteis", value=False)
            
            cidades_unicas = sorted(list(df_pendentes['Cidade'].unique()))
            sub_class_unicas = sorted(list(df_pendentes[COL_SUB_CLASSIF].unique()))
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                cidades_selecionadas = st.multiselect("Filtrar por Cidade(s):", cidades_unicas)
            with col_f2:
                sub_class_selecionadas = st.multiselect("Filtrar por Sub-Classificação:", sub_class_unicas)
            
            df_filtrado = df_pendentes.copy()
            if mostrar_so_hoje:
                hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                hoje_fim = hoje_inicio + timedelta(days=1) - timedelta(seconds=1)
                df_filtrado = df_filtrado[(df_filtrado['Prazo_DT'] >= hoje_inicio) & (df_filtrado['Prazo_DT'] <= hoje_fim)]
            elif mostrar_so_semana:
                df_filtrado = df_filtrado[(df_filtrado['Dias Úteis Restantes'] >= 0) & (df_filtrado['Dias Úteis Restantes'] <= 5)]
                
            if cidades_selecionadas:
                df_filtrado = df_filtrado[df_filtrado['Cidade'].isin(cidades_selecionadas)]
            if sub_class_selecionadas:
                df_filtrado = df_filtrado[df_filtrado[COL_SUB_CLASSIF].isin(sub_class_selecionadas)]
            
            df_filtrado['Data Atendimento'] = df_filtrado['Prazo_DT'].dt.strftime('%d/%m/%Y')
            
            # Métricas
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Visitas Pendentes", len(df_filtrado))
            with col_m2:
                hoje_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🔵 Vence Hoje"])
                st.metric("Vence Hoje", hoje_qt)
            with col_m3:
                amanha_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🟠 Vence Amanhã"])
                st.metric("Vence Amanhã", amanha_qt)
            with col_m4:
                vencidas_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🔴 Vencido"])
                st.metric("Ocorrências Vencidas", vencidas_qt)
            
            st.write("---")
            st.markdown("**Lista de Ocorrências (Selecione para gerenciar a tratativa):**")
            
            if df_filtrado.empty:
                st.success("✅ Excelente! Não há nenhuma ocorrência pendente para os filtros selecionados.")
            else:
                for idx, row in df_filtrado.iterrows():
                    num_oc = str(row[COL_OCORRENCIA])
                    cli_nome = str(row[COL_CLIENTE])
                    status_oc = row['Status Geral']
                    
                    with st.expander(f"📌 [{status_oc}] Ocorrência #{num_oc} — Cliente: {cli_nome} (Cidade: {row['Cidade']})"):
                        st.write(f"**Sub-classificação:** {row[COL_SUB_CLASSIF]}")
                        st.write(f"**Data de Atendimento:** {row['Data Atendimento']}")
                        st.write(f"**Endereço:** {row[COL_ENDERECO]}")
                        
                        col_b1, col_b2 = st.columns([2, 4])
                        with col_b1:
                            if st.button(f"👉 Iniciar Tratativa", key=f"btn_tratar_{num_oc}_{idx}"):
                                st.session_state.ocorrencia_ativa = {
                                    "codigo": num_oc,
                                    "cliente": cli_nome
                                }
                                st.success(f"Ocorrência #{num_oc} carregada! Vá para a aba 'Tratativa & Relatório Técnico' no menu lateral.")
        except Exception as e:
            st.error(f"⚠️ Erro ao processar o ficheiro Excel: {e}")
    else:
        st.info("👆 Por favor, faça o upload da folha de cálculo atualizada de ocorrências acima para carregar o dashboard.")


# =====================================================================
# TELA 2: TRATATIVA & RELATÓRIO TÉCNICO (Subpágina unificada)
# =====================================================================
elif menu == "📷 Tratativa & Relatório Técnico":
    rc = st.session_state.reset_counter
    ekc = st.session_state.eq_key_counter

    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Subpágina de Tratativa & Relatório Técnico")
        oc_ativa = st.session_state.ocorrencia_ativa
        if oc_ativa["codigo"]:
            st.info(f"🔗 Ocorrência em Tratativa: **#{oc_ativa['codigo']}** — **{oc_ativa['cliente']}**")
        else:
            st.warning("⚠️ Nenhuma ocorrência selecionada no Dashboard. Preencha os campos abaixo de forma manual ou selecione uma no menu anterior.")

    st.divider()

    # Botão flutuante para reiniciar dados do cliente
    st.button("🔄 Novo Cliente / Limpar", on_click=resetar_dados_cliente)

    # --- SEÇÃO 1: DADOS DO CLIENTE ---
    st.subheader("1. Identificação do Cliente")
    
    val_cod = oc_ativa["codigo"] if oc_ativa["codigo"] else ""
    val_nome = oc_ativa["cliente"] if oc_ativa["cliente"] else ""

    s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
    with s1_l1_c1:
        cod_cliente = st.text_input("Código do Cliente *", value=val_cod, placeholder="Ex: 87.653", key=f"input_cod_{rc}")
    with s1_l1_c2:
        nome_cliente = st.text_input("Nome / Razão Social *", value=val_nome, placeholder="Ex: SABOR DA TERRA", key=f"input_nome_{rc}")
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
        tem_freq = st.selectbox("Possui programação cadastrada? *",
