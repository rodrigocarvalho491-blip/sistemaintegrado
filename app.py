import os
import json
import pandas as pd
import numpy as np
import streamlit as st
import html as html_lib
import base64
import requests
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from fpdf import FPDF
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
    page_title="Sistema Integrado de Ocorrências | Consigaz", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")
DB_NOTAS_PATH = "banco_notas_usuarios.json"

# =====================================================================
# IDENTIDADE VISUAL CONSIGAZ - TEMA CLARO UNIFICADO
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

/* Ajuste de Métricas para contraste perfeito em tema claro */
[data-testid="stMetric"] {
  background-color: #F8FAFC !important;
  border: 1px solid #E2E8F0 !important;
  padding: 14px 18px !important;
  border-radius: 12px !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}
[data-testid="stMetricValue"] {
  color: #003366 !important;
  font-weight: 800 !important;
}
[data-testid="stMetricLabel"] {
  color: #5B6B7C !important;
  font-weight: 600 !important;
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

# --- FUNÇÕES AUXILIARES DE LOGO E PERSISTÊNCIA ---
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

# --- GERENCIAMENTO DE ESTADO DE AUTENTICAÇÃO ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_atual" not in st.session_state:
    st.session_state.usuario_atual = ""

# =====================================================================
# TELA DE AUTENTICAÇÃO (LOGIN INDEPENDENTE)
# =====================================================================
if not st.session_state.autenticado:
    side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
    st.sidebar.markdown(
        f'<div class="cg-side-brand">{side_logo_html}'
        f'<div class="cg-side-name">Sistema Integrado</div></div>',
        unsafe_allow_html=True,
    )
    
    st.title("🔐 Acesso ao Sistema Integrado | Consigaz")
    st.markdown("Insira suas credenciais corporativas para acessar o painel de atendimento e o seu bloco de notas pessoal.")
    
    with st.form("form_login_sistema"):
        email_input = st.text_input("E-mail corporativo", placeholder="seu.nome@consigaz.com.br")
        senha_input = st.text_input("Senha", type="password", placeholder="••••••••")
        btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary")
        
        if btn_entrar:
            if email_input.strip() and len(senha_input) >= 4:
                st.session_state.autenticado = True
                st.session_state.usuario_atual = email_input.strip().lower()
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("⚠️ Por favor, informe um e-mail válido e uma senha com pelo menos 4 caracteres.")
                
    st.stop()

# =====================================================================
# SISTEMA AUTENTICADO & MENU LATERAL
# =====================================================================
side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
st.sidebar.markdown(
    f'<div class="cg-side-brand">{side_logo_html}'
    f'<div class="cg-side-name">Central de Atendimentos</div></div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown(f"👤 **Usuário:** `{st.session_state.usuario_atual}`")

menu = st.sidebar.radio(
    "Selecione a página:", 
    [
        "📊 Dashboard de Ocorrências", 
        "📷 Visita de Transferência",
        "📝 Elaboração de Contrato",
        "📋 Aprovação de Contrato",
        "🎂 Aniversário de Contrato",
        "📓 Bloco de Notas Pessoal"
    ]
)

st.sidebar.divider()
if st.sidebar.button("🔄 Novo Cliente / Limpar Sessão"):
    for k in list(st.session_state.keys()):
        if k not in ["autenticado", "usuario_atual"]:
            del st.session_state[k]
    st.rerun()

if st.sidebar.button("🚪 Sair (Logout)"):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.rerun()

# --- FUNÇÕES DE API E APOIO ---
def consultar_cnpj_api(cnpj_input):
    cnpj_limpo = "".join(filter(str.isdigit, str(cnpj_input)))
    if len(cnpj_limpo) == 14:
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200: return response.json()
        except Exception: return None
    return None

def obter_ipca_acumulado_12m():
    try:
        url = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-1/variaveis/2266?localidades=N1[1]"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            serie = data[0]["resultados"][0]["séries"][0]["série"]
            ultimo_periodo = sorted(serie.keys())[-1]
            val_str = serie[ultimo_periodo]
            if val_str: return float(val_str)
    except Exception: pass
    return 4.58

if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0
if "reset_counter_contrato" not in st.session_state: st.session_state.reset_counter_contrato = 0
if "reset_counter_aprov" not in st.session_state: st.session_state.reset_counter_aprov = 0
if "reset_counter_aniv" not in st.session_state: st.session_state.reset_counter_aniv = 0
if "eq_key_counter" not in st.session_state: st.session_state.eq_key_counter = 0
if "equipamentos" not in st.session_state: st.session_state.equipamentos = []
if "last_central" not in st.session_state: st.session_state.last_central = "Central"
if "last_tipo_cad" not in st.session_state: st.session_state.last_tipo_cad = "Equipamentos"
if "tratadas_manualmente" not in st.session_state: st.session_state.tratadas_manualmente = set()
if "filtro_card_dashboard" not in st.session_state: st.session_state.filtro_card_dashboard = "Todos"

def botao_copiar_customizado(texto_para_copiar, chave_unica):
    texto_seguro = texto_para_copiar.replace('`', '\\`').replace('$', '\\$').replace('\n', '\\n')
    component_html = f"""
    <div style="margin-top: 5px; margin-bottom: 10px;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background-color: #0055A5; color: white; padding: 8px 16px; border: none;
            border-radius: 8px; font-weight: bold; font-size: 14px; cursor: pointer;
            display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            📋 Copiar Texto Completo
        </button>
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


# =====================================================================
# TELA 1: DASHBOARD DE OCORRÊNCIAS (COM CARDS DINÂMICOS)
# =====================================================================
if menu == "📊 Dashboard de Ocorrências":
    cabecalho_pagina("Dashboard de Ocorrências & Visitas", "Painel de organização de agenda ordenado por prazo de atendimento (Dias Úteis).")

    st.divider()
    st.subheader("1. Atualização de Dados")
    arquivo_excel = st.file_uploader("Faça o upload do relatório Excel (Pós-Vendas) 📂", type=["xlsx", "xls"])
    st.divider()

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
            if cidade.isdigit() and len(partes) >= 3: cidade = partes[-3].strip()
            return cidade.title()
        return s.title()

    def limpar_subclassificacao(sub):
        if pd.isna(sub): return "-"
        s = str(sub).strip()
        if "]" in s: s = s.split("]")[-1].strip()
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

    def classificar_status_comodato(dias_uteis):
        if dias_uteis < 0: return "🔴 Vencido"
        elif dias_uteis == 0: return "🔵 Vence Hoje"
        elif dias_uteis == 1: return "🟠 Vence Amanhã"
        elif dias_uteis <= 5: return "🔴 3ª Semana" 
        elif dias_uteis <= 10: return "🟡 2ª Semana" 
        return "🟢 1ª Semana" 

    if arquivo_excel is not None:
        try:
            df = pd.read_excel(arquivo_excel, header=11)
            df = df.dropna(subset=[COL_OCORRENCIA])
            df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
            
            df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
            df_pendentes = df_pendentes[~df_pendentes[COL_OCORRENCIA].isin(st.session_state.tratadas_manualmente)]
            
            df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
            df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
            
            df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
            df_pendentes['Sub_Simplificada'] = df_pendentes[COL_SUB_CLASSIF].apply(limpar_subclassificacao)
            
            hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            df_pendentes['Dias Úteis Restantes'] = df_pendentes['Prazo_DT'].apply(lambda x: calcular_dias_uteis(hoje, x))
            df_pendentes['Status Geral'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_geral)
            df_pendentes['Status Comodato'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_comodato)
            df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
            
            st.subheader("2. Agenda Geral de Visitas Pendentes")
            st.markdown("### Filtros de Visualização")
            
            cidades_unicas = sorted(list(df_pendentes['Cidade'].unique()))
            sub_class_unicas = sorted(list(df_pendentes['Sub_Simplificada'].unique()))
            
            col_f1, col_f2 = st.columns(2)
            with col_f1: cidades_selecionadas = st.multiselect("Filtrar por Cidade(s):", cidades_unicas, default=[])
            with col_f2: sub_class_selecionadas = st.multiselect("Filtrar por Sub-Classificação:", sub_class_unicas, default=[])
            
            df_filtrado = df_pendentes.copy()
            if cidades_selecionadas: df_filtrado = df_filtrado[df_filtrado['Cidade'].isin(cidades_selecionadas)]
            if sub_class_selecionadas: df_filtrado = df_filtrado[df_filtrado['Sub_Simplificada'].isin(sub_class_selecionadas)]
            
            df_filtrado['Data Atendimento'] = df_filtrado['Prazo_DT'].dt.strftime('%d/%m/%Y')
            
            # --- MÉTRICAS DE RESUMO DINÂMICAS ---
            total_qt = len(df_filtrado)
            hoje_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🔵 Vence Hoje"])
            amanha_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🟠 Vence Amanhã"])
            vencidas_qt = len(df_filtrado[df_filtrado['Status Geral'] == "🔴 Vencido"])
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            
            with col_m1:
                st.metric("Total", total_qt)
                if st.button("🔍 Filtrar Total", key="btn_f_total", use_container_width=True):
                    st.session_state.filtro_card_dashboard = "Todos"
            with col_m2:
                st.metric("Vence Hoje", hoje_qt)
                if st.button("🔍 Filtrar Hoje", key="btn_f_hoje", use_container_width=True):
                    st.session_state.filtro_card_dashboard = "Hoje"
            with col_m3:
                st.metric("Vence Amanhã", amanha_qt)
                if st.button("🔍 Filtrar Amanhã", key="btn_f_amanha", use_container_width=True):
                    st.session_state.filtro_card_dashboard = "Amanhã"
            with col_m4:
                st.metric("Ocorrências Vencidas", vencidas_qt)
                if st.button("🔍 Filtrar Vencidas", key="btn_f_vencidas", use_container_width=True):
                    st.session_state.filtro_card_dashboard = "Vencido"

            st.markdown(f"📌 **Filtro ativo por card:** `{st.session_state.filtro_card_dashboard}`")

            # Aplica o filtro dinâmico do card selecionado
            if st.session_state.filtro_card_dashboard == "Hoje":
                df_filtrado = df_filtrado[df_filtrado['Status Geral'] == "🔵 Vence Hoje"]
            elif st.session_state.filtro_card_dashboard == "Amanhã":
                df_filtrado = df_filtrado[df_filtrado['Status Geral'] == "🟠 Vence Amanhã"]
            elif st.session_state.filtro_card_dashboard == "Vencido":
                df_filtrado = df_filtrado[df_filtrado['Status Geral'] == "🔴 Vencido"]

            st.write("---")
            st.markdown("**Lista de Ocorrências Ordenadas:**")
            
            if df_filtrado.empty:
                st.success("✅ Excelente! Não há ocorrências pendentes para os filtros selecionados.")
            else:
                df_exibicao = df_filtrado[['Status Geral', 'Dias Úteis Restantes', COL_OCORRENCIA, COL_CLIENTE, 'Cidade', 'Sub_Simplificada', 'Data Atendimento']].copy()
                df_exibicao[COL_OCORRENCIA] = df_exibicao[COL_OCORRENCIA].astype(str)
                
                edited_df = st.data_editor(
                    df_exibicao.assign(Tratar=False),
                    column_config={
                        "Tratar": st.column_config.CheckboxColumn("✅ Marcar Tratada?", width="small", required=True),
                        'Status Geral': st.column_config.TextColumn("Status", width="small", disabled=True),
                        'Dias Úteis Restantes': st.column_config.NumberColumn("Dias Úteis", width="small", disabled=True),
                        COL_OCORRENCIA: st.column_config.TextColumn("Nº Ocorrência", width="small", disabled=True),
                        COL_CLIENTE: st.column_config.TextColumn("Nome do Cliente", width="medium", disabled=True),
                        'Cidade': st.column_config.TextColumn("Cidade", width="small", disabled=True),
                        'Sub_Simplificada': st.column_config.TextColumn("Sub-Classificação", width="medium", disabled=True),
                        'Data Atendimento': st.column_config.TextColumn("Data Atendimento", width="small", disabled=True),
                    },
                    hide_index=True, use_container_width=True, key="editor_geral"
                )
                
                ocorrencias_para_tratar = edited_df[edited_df["Tratar"] == True][COL_OCORRENCIA].tolist()
                if ocorrencias_para_tratar:
                    st.warning(f"⚠️ Você selecionou **{len(ocorrencias_para_tratar)}** ocorrência(s) para tratar.")
                    if st.button("🔒 Confirmar e Remover do Painel", type="primary"):
                        for oc in ocorrencias_para_tratar: st.session_state.tratadas_manualmente.add(int(oc))
                        st.success("✅ Removido com sucesso!")
                        st.rerun()

            st.divider()
            st.subheader("3. Relatório Específico: Comodato Inativo")
            df_comodato = df_pendentes[df_pendentes['Sub_Simplificada'].str.contains("Comodato Inativo", case=False, na=False)].copy()
            if df_comodato.empty:
                st.info("ℹ️ Nenhuma ocorrência de Comodato Inativo encontrada.")
            else:
                df_comodato['Data Atendimento'] = df_comodato['Prazo_DT'].dt.strftime('%d/%m/%Y')
                df_comodato_exibicao = df_comodato[['Status Comodato', 'Dias Úteis Restantes', COL_OCORRENCIA, COL_CLIENTE, 'Cidade', 'Sub_Simplificada', 'Data Atendimento']].copy()
                df_comodato_exibicao[COL_OCORRENCIA] = df_comodato_exibicao[COL_OCORRENCIA].astype(str)
                st.metric("Total de Comodatos Inativos", len(df_comodato_exibicao))
                
                edited_comodato = st.data_editor(
                    df_comodato_exibicao.assign(Tratar=False),
                    column_config={
                        "Tratar": st.column_config.CheckboxColumn("✅ Marcar Tratada?", width="small", required=True),
                        'Status Comodato': st.column_config.TextColumn("Status Semanal", width="small", disabled=True),
                        'Dias Úteis Restantes': st.column_config.NumberColumn("Dias Úteis", width="small", disabled=True),
                        COL_OCORRENCIA: st.column_config.TextColumn("Nº Ocorrência", width="small", disabled=True),
                        COL_CLIENTE: st.column_config.TextColumn("Nome do Cliente", width="medium", disabled=True),
                        'Cidade': st.column_config.TextColumn("Cidade", width="small", disabled=True),
                        'Sub_Simplificada': st.column_config.TextColumn("Sub-Classificação", width="medium", disabled=True),
                        'Data Atendimento': st.column_config.TextColumn("Data Atendimento", width="small", disabled=True),
                    },
                    hide_index=True, use_container_width=True, key="editor_comodato"
                )
                
                comodatos_para_tratar = edited_comodato[edited_comodato["Tratar"] == True][COL_OCORRENCIA].tolist()
                if comodatos_para_tratar:
                    if st.button("🔒 Confirmar Tratativa de Comodato", type="primary", key="btn_comodato"):
                        for oc in comodatos_para_tratar: st.session_state.tratadas_manualmente.add(int(oc))
                        st.success("✅ Comodato(s) tratado(s)!")
                        st.rerun()

            st.divider()
            st.subheader("4. Visão Geográfica: Ocorrências por Cidade")
            if not df_filtrado.empty:
                df_cidades_qtd = df_filtrado['Cidade'].value_counts().reset_index()
                df_cidades_qtd.columns = ['Cidade', 'Quantidade']
                col_grafico, col_tabela = st.columns(2)
                with col_grafico:
                    st.markdown("**📊 Gráfico de Distribuição:**")
                    st.bar_chart(df_cidades_qtd.set_index('Cidade'), color="#0055A5")
                with col_tabela:
                    st.markdown("**📋 Tabela Quantitativa:**")
                    st.dataframe(df_cidades_qtd, hide_index=True, use_container_width=True)
        except Exception as e:
            st.error(f"⚠️ Erro ao processar arquivo: {e}")
    else:
        st.info("👆 Faça o upload do arquivo Excel acima para carregar o dashboard.")


# =====================================================================
# TELA 2: VISITA DE TRANSFERÊNCIA
# =====================================================================
elif menu == "📷 Visita de Transferência":
    rc = st.session_state.reset_counter
    ekc = st.session_state.eq_key_counter

    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Visita de Transferência & Relatório Técnico")
        st.markdown("Gerador automatizado de relatórios técnicos e inspeções.")

    st.divider()
    st.subheader("1. Identificação do Cliente")
    s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
    with s1_l1_c1: cod_cliente = st.text_input("Código do Cliente *", key=f"input_cod_{rc}")
    with s1_l1_c2: nome_cliente = st.text_input("Nome / Razão Social *", key=f"input_nome_{rc}")
    with s1_l1_c3: telefone = st.text_input("Telefone *", key=f"input_tel_{rc}")

    s1_l2_c1, s1_l2_c2, _ = st.columns(3)
    with s1_l2_c1: contato = st.text_input("Contato *", key=f"input_contato_{rc}")
    with s1_l2_c2: departamento = st.text_input("Sobrenome ou Departamento *", key=f"input_depto_{rc}")

    st.divider()
    st.subheader("2. Informações Contratuais")
    s2_l1_c1, s2_l1_c2, s2_l1_c3, s2_l1_c4 = st.columns(4)
    with s2_l1_c1: eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_contrato_{rc}")
    with s2_l1_c2: desc_eq_contrato = st.text_input("Quais equipamentos disponíveis? *", key=f"desc_eq_contrato_{rc}")
    with s2_l1_c3: tem_freq = st.radio("Possui programação cadastrada? *", ["Sim", "Não"], horizontal=True, index=None, key=f"tem_freq_{rc}")
    with s2_l1_c4:
        desc_freq = ""
        if tem_freq == "Sim": desc_freq = st.text_input("Qual a programação? *", key=f"freq_cad_sim_{rc}")
        elif tem_freq == "Não": desc_freq = st.text_input("Nº OC de Cadastramento *", key=f"freq_cad_nao_{rc}")

    s2_l2_c1, s2_l2_c2 = st.columns(2)
    with s2_l2_c1: consumo_previsto = st.text_input("Consumo Previsto (kg) *", key=f"cons_prev_{rc}")
    with s2_l2_c2: consumo_real = st.text_input("Consumo Real/Médio (kg) *", key=f"cons_real_{rc}")

    s2_l3_c1, s2_l3_c2 = st.columns(2)
    with s2_l3_c1: possui_art = st.radio("Possui ART? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_art_{rc}")
    with s2_l3_c2:
        desc_art = ""
        if possui_art == "Sim": desc_art = st.text_input("Número da ART *", key=f"art_sim_{rc}")
        elif possui_art == "Não": desc_art = st.text_input("Nº OC de Solicitação de Laudo *", key=f"art_nao_{rc}")

    s2_l4_c1, s2_l4_c2 = st.columns(2)
    with s2_l4_c1: possui_debitos = st.radio("Cliente possui débitos? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_debitos_{rc}")
    with s2_l4_c2: desc_debitos = st.text_input("Detalhes dos Débitos", key=f"desc_debitos_{rc}") if possui_debitos == "Sim" else ""

    s2_l5_c1, s2_l5_c2 = st.columns(2)
    with s2_l5_c1: central_norma = st.radio("Central dentro de norma? *", ["Sim", "Não"], horizontal=True, index=None, key=f"central_norma_{rc}")
    with s2_l5_c2: desc_central_norma = st.text_input("Motivo da Central fora de norma", key=f"desc_central_norma_{rc}") if central_norma == "Não" else ""

    s2_l6_c1, s2_l6_c2 = st.columns(2)
    with s2_l6_c1: rep2_correto = st.radio("Representante 2 está correto? *", ["Sim", "Não"], horizontal=True, index=None, key=f"rep2_correto_{rc}")
    with s2_l6_c2: desc_rep2 = st.text_input("Nº OC de Regularização", key=f"desc_rep2_{rc}") if rep2_correto == "Não" else ""

    st.divider()
    st.subheader("3. Cadastro de Instalação e Equipamentos")
    col_cent1, col_cent2 = st.columns(2)
    with col_cent1: qtd_centrais = st.number_input("Quantidade de Centrais no Cliente", min_value=1, value=1, step=1, key=f"qtd_centrais_{rc}")
    with col_cent2:
        if qtd_centrais > 1:
            opcoes_centrais = [f"Central {i:02d}" for i in range(1, int(qtd_centrais) + 1)]
            idx_central = opcoes_centrais.index(st.session_state.last_central) if st.session_state.last_central in opcoes_centrais else 0
            central_selecionada = st.selectbox("Vincular item à qual Central?", opcoes_centrais, index=idx_central, key=f"sel_central_{rc}_{ekc}")
            st.session_state.last_central = central_selecionada
        else:
            central_selecionada = "Central"
            st.session_state.last_central = "Central"

    tipo_cadastro = st.radio("Selecione o tipo que deseja adicionar:", ["Equipamentos", "Cilindros", "Condomínio"], horizontal=True, key=f"tipo_cad_{rc}_{ekc}")
    st.session_state.last_tipo_cad = tipo_cadastro

    if tipo_cadastro == "Equipamentos":
        col_qtd, col_eq, col_vaz, col_btn = st.columns([1, 2, 2, 1])
        with col_qtd: qtd_input = st.number_input("Quantidade", min_value=1, value=1, step=1, key=f"eq_qtd_{rc}_{ekc}")
        with col_eq: nome_eq_input = st.text_input("Equipamento", key=f"eq_nome_{rc}_{ekc}")
        with col_vaz: vazao_input = st.text_input("Vazão (kg/h)", key=f"eq_vazao_{rc}_{ekc}")
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

    elif tipo_cadastro == "Cilindros":
        col_qtd, col_mod, col_btn = st.columns([1, 4, 1])
        with col_qtd: qtd_input = st.number_input("Qtd", min_value=1, value=1, step=1, key=f"cil_qtd_{rc}_{ekc}")
        with col_mod: modelo_input = st.text_input("Modelo", key=f"cil_mod_{rc}_{ekc}")
        with col_btn:
            st.write(" "); st.write(" ")
            if st.button("➕ Adicionar", key=f"btn_add_cil_{rc}_{ekc}"):
                if modelo_input.strip():
                    qtd = int(qtd_input)
                    item_dict = {
                        "central": central_selecionada, "tipo": "cilindro", "qtd": qtd,
                        "nome": f"Cilindro {modelo_input.strip().upper()}", "vazao_total_item": 0.0,
                        "texto": f"{qtd:02d} und {modelo_input.strip().upper()}"
                    }
                    st.session_state.equipamentos.append(item_dict)
                    st.session_state.eq_key_counter += 1
                    st.success("Cilindro adicionado!")
                    st.rerun()

    elif tipo_cadastro == "Condomínio":
        col_local, col_qtd, col_tipo, col_btn = st.columns([2, 1, 3, 1])
        with col_local: local_input = st.selectbox("Local", ["Apartamentos", "Área Comum"], key=f"cond_local_{rc}_{ekc}")
        with col_qtd: qtd_input = st.number_input("Qtd", min_value=1, value=1, step=1, key=f"cond_qtd_{rc}_{ekc}")
        with col_tipo: tipo_apt_input = st.selectbox("Instalação", ["Só Fogão", "Fogão + Aquecedor"], key=f"cond_tipo_{rc}_{ekc}")
        with col_btn:
            st.write(" "); st.write(" ")
            if st.button("➕ Adicionar", key=f"btn_add_cond_{rc}_{ekc}"):
                qtd = int(qtd_input)
                vazao_unit = 0.1 if tipo_apt_input == "Só Fogão" else 0.4
                vazao_total = vazao_unit * qtd
                texto = f"{qtd:02d} aps - {tipo_apt_input}" if local_input == "Apartamentos" else f"{qtd:02d} - Área Comum ({tipo_apt_input})"
                item_dict = {
                    "central": central_selecionada, "tipo": "condominio", "qtd": qtd,
                    "nome": f"Condomínio ({tipo_apt_input})", "vazao_total_item": vazao_total, "texto": texto
                }
                st.session_state.equipamentos.append(item_dict)
                st.session_state.eq_key_counter += 1
                st.success("Condomínio adicionado!")
                st.rerun()

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
    col_s1, col_s2 = st.columns(2)
    with col_s1: indica_negocios = st.radio("Indicou novos negócios? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ind_neg_{rc}")
    with col_s2: cliente_satisfeito = st.radio("Cliente satisfeito com a Consigaz? *", ["Sim", "Não"], horizontal=True, index=None, key=f"cli_sat_{rc}")
    observacoes = st.text_area("Observações Gerais", key=f"obs_{rc}")

    st.divider()
    st.subheader("5. Relatório Fotográfico")
    def carregar_fotos(label, max_arq=None):
        fotos = st.file_uploader(label, type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_{label}_{rc}")
        if max_arq and fotos and len(fotos) > max_arq: return fotos[:max_arq]
        return fotos

    dic_fotos_final = {}
    col_f1, col_f2 = st.columns(2)
    with col_f1: dic_fotos_final["FACHADA"] = carregar_fotos("FACHADA", 2)
    with col_f2: dic_fotos_final["CILINDROS"] = carregar_fotos("CILINDROS", 5)

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
            if os.path.exists(LOGO2_PATH): self.image(LOGO2_PATH, x=10, y=8, w=45)
            if self.page_no() == 1:
                self.set_y(10)
                self.set_font("Arial", "B", 15)
                self.cell(0, 8, "RELATÓRIO FOTOGRÁFICO", align="C", ln=1)
                if self.cod or self.nome:
                    self.set_font("Arial", "B", 11)
                    self.cell(0, 6, f"{self.cod} | {self.nome}", align="C", ln=1)
                self.set_y(35)
            else: self.set_y(35)
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
                    try:
                        img = Image.open(arq)
                        if img.mode != "RGB": img = img.convert("RGB")
                        t_path = f"temp_{cat}_{idx}.jpg"
                        img.save(t_path)
                        w_p, h_p = img.size
                        prop = h_p / w_p
                        w_alv = 130
                        h_alv = w_alv * prop
                        if h_alv > 110: h_alv = 110; w_alv = h_alv / prop
                        pos_x = (210 - w_alv) / 2
                        if pdf.get_y() + h_alv > 270: pdf.add_page()
                        pdf.image(t_path, x=pos_x, y=pdf.get_y(), w=w_alv, h=h_alv)
                        pdf.set_y(pdf.get_y() + h_alv + 5)
                        if os.path.exists(t_path): os.remove(t_path)
                    except Exception: pass

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
        return pdf_output.encode("latin-1") if isinstance(pdf_output, str) else bytes(pdf_output)

    st.subheader("6. Ações Finais")
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if not cod_cliente.strip() or not nome_cliente.strip():
            st.warning("⚠️ Preencha Código e Nome do Cliente.")
        else:
            pdf_bytes = gerar_pdf(st.session_state.equipamentos, dic_fotos_final, cod_cliente, nome_cliente, qtd_centrais)
            st.download_button("📥 Baixar Relatório (PDF)", data=pdf_bytes, file_name=f"relatorio_{cod_cliente}.pdf", mime="application/pdf")
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
            texto_final = f"""Contato: {contato}
Sobrenome ou departamento: {departamento}
Telefone: {telefone}

Equipamentos de acordo com o contrato vigente? {eq_contrato} - {desc_eq_contrato}
Representante 2 está correto? {rep2_correto}
Possui programação cadastrada? {tem_freq} - {desc_freq}
Consumo mensal atual: Previsto: {consumo_previsto} kg | Médio: {consumo_real} kg
Laudo ART emitido? {possui_art} - {desc_art}
Central atende as normas? {central_norma} - {desc_central_norma}

{lista_eq_txt}Indicação de novos negócios: {indica_negocios}
Cliente possui débitos? {possui_debitos} - {desc_debitos}
Cliente satisfeito? {cliente_satisfeito}
Obs.: {observacoes}"""
            st.success("✅ Texto gerado com sucesso!")
            st.text_area("Texto Gerado:", value=texto_final, height=250, key=f"txt_area_transf_{rc}")
            botao_copiar_customizado(texto_final, "transferencia_txt")


# =====================================================================
# TELA 3: ELABORAÇÃO DE CONTRATO
# =====================================================================
elif menu == "📝 Elaboração de Contrato":
    rcc = st.session_state.reset_counter_contrato
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Elaboração de Contrato")
        st.markdown("Formulário de preenchimento e geração de solicitação.")

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
        if mesmo_prop_opt == "Não": email_novo_prop = st.text_input("E-mail do novo proprietário", key=f"email_novo_{rcc}")

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
    preco_granel, consumo_granel = "", ""
    p13_val, p20_val, p45_val = "", "", ""
    p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
    consumo_cilindro_total = 0

    if tipo_fornecimento == "Granel":
        col_g1, col_g2 = st.columns(2)
        with col_g1: preco_granel = st.text_input("Preço Granel", key=f"preco_granel_{rcc}")
        with col_g2: consumo_granel = st.text_input("Consumo mensal previsto (kgs)", key=f"cons_granel_{rcc}")
    elif tipo_fornecimento == "Cilindro":
        col_cp1, col_cp2, col_cp3 = st.columns(3)
        with col_cp1: p13_val = st.text_input("Preço P13", key=f"p13_v_{rcc}")
        with col_cp2: p20_val = st.text_input("Preço P20", key=f"p20_v_{rcc}")
        with col_cp3: p45_val = st.text_input("Preço P45", key=f"p45_v_{rcc}")
        col_cc1, col_cc2, col_cc3 = st.columns(3)
        with col_cc1: p13_qtd = st.number_input("Qtd P13", min_value=0, value=0, step=1, key=f"p13_q_{rcc}")
        with col_cc2: p20_qtd = st.number_input("Qtd P20", min_value=0, value=0, step=1, key=f"p20_q_{rcc}")
        with col_cc3: p45_qtd = st.number_input("Qtd P45", min_value=0, value=0, step=1, key=f"p45_q_{rcc}")
        consumo_cilindro_total = (p13_qtd * 13) + (p20_qtd * 20) + (p45_qtd * 45)

    st.divider()
    st.subheader("6. Financeiro")
    possui_debito_fin = st.radio("Cliente possui débitos?", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rcc}")
    resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", key=f"resp_pend_{rcc}") if possui_debito_fin == "Sim" else "n/a"

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
            with col_r1: nome_resp = st.text_input(f"Nome do Responsável {i}", key=f"nome_resp_{i}_{rcc}")
            with col_r2: email_resp = st.text_input(f"E-mail do Responsável {i}", key=f"email_resp_{i}_{rcc}")
            responsaveis_dados.append({"nome": nome_resp, "email": email_resp})

    st.divider()
    st.subheader("7. Condomínio CONTA SIM")
    conta_sim = st.radio("Condomínio CONTA SIM?", ["Sim", "Não"], horizontal=True, index=None, key=f"conta_sim_{rcc}")
    num_unidades, qtd_torres, qtd_blocos, preco_religue, preco_servico = "", "", "", "", ""
    if conta_sim == "Sim":
        col_cs1, col_cs2, col_cs3 = st.columns(3)
        with col_cs1:
            num_unidades = st.text_input("N° Unid autônomas", key=f"num_unid_{rcc}")
            qtd_torres = st.text_input("Qtd Torres", key=f"qtd_torres_{rcc}")
        with col_cs2:
            qtd_blocos = st.text_input("Qtd Blocos", key=f"qtd_blocos_{rcc}")
            preco_religue = st.text_input("Valor religue", key=f"preco_rel_{rcc}")
        with col_cs3:
            preco_servico = st.text_input("Valor serviço", key=f"preco_serv_{rcc}")

    observacoes_contrato = st.text_area("Obs.", key=f"obs_c_{rcc}")

    st.divider()
    if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
        sel_granel = "[x]" if tipo_fornecimento == "Granel" else "[ ]"
        sel_cilindro = "[x]" if tipo_fornecimento == "Cilindro" else "[ ]"
        texto_padrao_contrato = f"Motivo da solicitação: {motivo_solicitacao}"
        if tipo_fluxo == "Gerar Minuta": texto_padrao_contrato += "\n\n** FAVOR GERAR MINUTA EM PDF PARA ENVIO AO CLIENTE **"

        texto_padrao_contrato += f"""
Contato: {contato_contrato} | Telefone: {telefone_contrato} | E-mail: {email_contrato}
Contrato / Aditamento / Distrato: {tipo_contrato if tipo_contrato else ''}
Mesmo proprietário?: {mesmo_prop_opt if mesmo_prop_opt else ''} | E-mail novo prop: {email_novo_prop}
Mesmo CNPJ?: {mesmo_cnpj_opt if mesmo_cnpj_opt else ''}"""

        if mesmo_cnpj_opt == "Sim": texto_padrao_contrato += f"\nCNPJ: {cnpj_campo_val} | I.E.: {ie_campo_val}"
        elif mesmo_cnpj_opt == "Não": texto_padrao_contrato += f"\nNovo CNPJ: {cnpj_campo_val} | Nova I.E.: {ie_campo_val}"
        if razao_social_txt: texto_padrao_contrato += f"\nRazão Social: {razao_social_txt} | Status: {status_cnpj_txt}"

        texto_padrao_contrato += f"""
Endereço padrão/entrega: {endereco_padrao}
Tipo de Fornecimento: {sel_granel} Granel  {sel_cilindro} Cilindro"""

        if tipo_fornecimento == "Granel":
            texto_padrao_contrato += f"\nPreço Granel: {preco_granel} | Consumo: {consumo_granel}"
        elif tipo_fornecimento == "Cilindro":
            texto_padrao_contrato += f"\nPreço Cilindro: [P13={p13_val}] [P20={p20_val}] [P45={p45_val}] | Consumo: {consumo_cilindro_total} KGs"

        texto_padrao_contrato += f"\nCondição pagamento: {cond_pagamento} | Vigência: {vigencia}"
        if qtd_entregas_c == 1: texto_padrao_contrato += f"\nEquipamentos: {equipamentos_contrato}"
        else:
            eq_linhas = [f"[Entrega {i}] {eq_dict_c[i].strip()}" for i in range(1, int(qtd_entregas_c)+1) if eq_dict_c[i].strip()]
            texto_padrao_contrato += "\nEquipamentos: " + "\n".join(eq_linhas)

        texto_padrao_contrato += f"\nCliente possui débitos?: {possui_debito_fin} | Resp NF's: {resp_pendentes}"
        if tipo_fluxo == "Enviar para Assinatura":
            texto_padrao_contrato += f"\nTestemunha: {nome_testemunha} ({email_testemunha})"
            for idx, resp in enumerate(responsaveis_dados, 1):
                texto_padrao_contrato += f"\nResponsável {idx}: {resp['nome']} ({resp['email']})"

        texto_padrao_contrato += f"\nConta Sim?: {conta_sim}"
        if conta_sim == "Sim":
            texto_padrao_contrato += f"\nUnid: {num_unidades} | Torres: {qtd_torres} | Blocos: {qtd_blocos} | Religue: {preco_religue} | Serviço: {preco_servico}"
        texto_padrao_contrato += f"\nObs.: {observacoes_contrato}"

        st.success("✅ Texto gerado com sucesso!")
        st.text_area("Texto Gerado:", value=texto_padrao_contrato, height=250, key=f"txt_area_contrato_{rcc}")
        botao_copiar_customizado(texto_padrao_contrato, "contrato_txt")


# =====================================================================
# TELA 4: APROVAÇÃO DE CONTRATO
# =====================================================================
elif menu == "📋 Aprovação de Contrato":
    rcap = st.session_state.reset_counter_aprov
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Aprovação de Contrato")
        st.markdown("Formulário de preenchimento para solicitação de aprovação.")

    st.divider()
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
    equipamentos_ap, eq_dict_ap = "", {}
    if qtd_entregas_ap == 1: equipamentos_ap = st.text_input("Equipamentos", key=f"ap_eq_{rcap}")
    else:
        for i in range(1, int(qtd_entregas_ap) + 1): eq_dict_ap[i] = st.text_input(f"Equipamentos - [Entrega {i}]", key=f"ap_eq_ent_{i}_{rcap}")
    especificidade_ap = st.text_input("Existe especificidade sobre a solicitação?", key=f"ap_esp_{rcap}")

    st.divider()
    st.subheader("3. Redimensionamento")
    redim = st.radio("Redimensionamento:", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_redim_{rcap}")
    comodato_de, comodato_para, inc_tanques, env_pecas = "", "", "Não", "Não"
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
    env_pecas_ficha, env_ficha_cliente, tp_portaria, contato_resp_port, part_local, contato_sindico = "Não", "Não", "", "", "", ""
    if implantacao_csim == "Sim":
        c_cs1, c_cs2 = st.columns(2)
        with c_cs1: env_pecas_ficha = st.radio("Foi enviado lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_pec_{rcap}")
        with c_cs2: env_ficha_cliente = st.radio("Foi enviado ficha de clientes?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_ficha_{rcap}")
        tp_portaria = st.text_input("Tipo de portaria", key=f"ap_tp_port_{rcap}")
        contato_resp_port = st.text_input("Contato do responsável", key=f"ap_cont_resp_{rcap}")
        part_local = st.text_input("Particularidades do local", key=f"ap_part_local_{rcap}")
        contato_sindico = st.text_input("Contato atualizado do síndico", key=f"ap_cont_sind_{rcap}")

    st.divider()
    st.subheader("5. Alteração de CNPJ ou Razão Social & Títulos")
    alt_cnpj = st.radio("Alteração de CNPJ ou razão social?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_alt_cnpj_{rcap}")
    mesmo_prop_opt = st.radio("Se trata do mesmo proprietário:", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_mesmo_prop_{rcap}")
    possui_titulos_aberto = st.radio("Possui títulos em aberto?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_tit_aberto_{rcap}")
    neg_tit_input = st.text_input("Descreva a negociação de títulos em aberto:", key=f"ap_neg_tit_{rcap}") if possui_titulos_aberto == "Sim" else ""

    st.divider()
    st.subheader("6. Redução de Vigência")
    red_vig = st.radio("Redução de vigência?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_red_vig_{rcap}")
    motivo_red_vig = st.text_input("Descreva o motivo da redução de vigência:", key=f"ap_mot_red_{rcap}") if red_vig == "Sim" else ""

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
            st.error("⚠️ O campo 'Projeto' é obrigatório, a menos que 'Cilindros' esteja marcado.")
        else:
            proj_final = "N/A" if is_cilindros else projeto_num
            neg_final = neg_tit_input.strip() if possui_titulos_aberto == "Sim" and neg_tit_input.strip() else "n/a"

            if qtd_entregas_ap == 1: eq_ap_texto = equipamentos_ap
            else:
                eq_ap_linhas = [f"[Entrega {i}] {eq_dict_ap[i].strip()}" for i in range(1, int(qtd_entregas_ap)+1) if eq_dict_ap[i].strip()]
                eq_ap_texto = "\n" + "\n".join(eq_ap_linhas) if eq_ap_linhas else ""

            texto_aprovacao = f"""Motivo da regularização: {motivo_reg}
Contato: {contato_ap} | Telefone: {telefone_ap} | E-mail: {email_ap}
Atualizar E-mail? {atualizar_email or ''} | Contrato/Aditamento: {contrato_adit or ''} | Vigência: {vigencia_ap}
Equipamentos: {eq_ap_texto}
Especificidade: {especificidade_ap}

Redimensionamento: {'sim' if redim == 'Sim' else 'não'} | Projeto: {proj_final}
Comodato de: {comodato_de} para: {comodato_para}
Inclusão de tanques? {'sim' if inc_tanques == 'Sim' else 'não'} | Lista de peças? {'sim' if env_pecas == 'Sim' else 'não'}

Conta Sim? {'sim' if implantacao_csim == 'Sim' else 'não'} | Lista peças? {'sim' if env_pecas_ficha == 'Sim' else ''} | Ficha cliente? {'sim' if env_ficha_cliente == 'Sim' else ''}
Portaria: {tp_portaria} | Contato portaria: {contato_resp_port} | Particularidades: {part_local} | Síndico: {contato_sindico}

Alteração CNPJ? {'sim' if alt_cnpj == 'Sim' else 'não'} | Mesmo proprietário: {mesmo_prop_opt or ''}
Negociação títulos abertos: {neg_final}
Redução vigência? {'sim' if red_vig == 'Sim' else 'não'} (Motivo: {motivo_red_vig})"""

            st.success("✅ Texto de Aprovação gerado com sucesso!")
            st.text_area("Texto Gerado:", value=texto_aprovacao, height=350, key=f"txt_area_aprov_{rcap}")
            botao_copiar_customizado(texto_aprovacao, "aprovacao_txt")


# =====================================================================
# TELA 5: ANIVERSÁRIO DE CONTRATO
# =====================================================================
elif menu == "🎂 Aniversário de Contrato":
    rca = st.session_state.reset_counter_aniv
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Aniversário de Contrato")
        st.markdown("Tratativa de reajuste por IPCA acumulado de 12 meses.")

    st.divider()
    ipca_vigente = obter_ipca_acumulado_12m()
    st.info(f"📊 **IPCA Acumulado de 12 meses (IBGE):** {ipca_vigente:.2f}%")

    preco_anterior_input = st.text_input("Preço Anterior (R$)", key=f"preco_ant_{rca}")
    clausula_contrato = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, index=None, key=f"clausula_{rca}")

    st.divider()
    p_aniv_str = "xx,xx"
    try:
        val_limpo = preco_anterior_input.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        p_ant = float(val_limpo)
        p_aniv = p_ant * (1 + (ipca_vigente / 100.0))
        p_aniv_str = f"{p_aniv:.4f}".replace(".", ",")
    except ValueError: pass

    if st.button("📝 Gerar Texto de Aniversário de Contrato", type="primary"):
        if clausula_contrato == "Não": st.warning("⚠️ Atenção: Cliente não possui cláusula de reajuste em contrato.")
        texto_aniversario = f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%."
        if clausula_contrato == "Sim": texto_aniversario += "\n\nCliente possui cláusula em contrato."
        texto_aniversario += f"\n\nPreço anterior: R$ {preco_anterior_input or 'xx,xx'}\nPreço Aniversário: R$ {p_aniv_str}"
        st.success("✅ Texto gerado com sucesso!")
        st.text_area("Texto Gerado:", value=texto_aniversario, height=180, key=f"txt_area_aniv_{rca}")
        botao_copiar_customizado(texto_aniversario, "aniversario_txt")

    st.divider()
    st.subheader("Tratativa com C.I.")
    ci_input = st.text_input("Número da C.I.", key=f"ci_num_{rca}")
    if st.button("📝 Gerar Texto com C.I.", type="primary"):
        texto_ci = f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%."
        if clausula_contrato == "Sim": texto_ci += "\n\nCliente possui cláusula em contrato."
        texto_ci += f"\n\nPreço anterior: R$ {preco_anterior_input or 'xx,xx'}\nPreço Aniversário: R$ {p_aniv_str}\n\nCI.: {ci_input or '000.000.000'} - Preço Aniversário"
        st.success("✅ Texto com C.I. gerado!")
        st.text_area("Texto Gerado:", value=texto_ci, height=200, key=f"txt_area_ci_{rca}")
        botao_copiar_customizado(texto_ci, "ci_txt")


# =====================================================================
# TELA 6: BLOCO DE NOTAS / BANCO DE DADOS PESSOAL
# =====================================================================
elif menu == "📓 Bloco de Notas Pessoal":
    cabecalho_pagina("Bloco de Notas & Base de Conhecimento", "Suas anotações salvas de forma persistente e isolada para o seu usuário.")

    st.divider()
    banco_notas = carregar_banco_notas()
    usuario_atual = st.session_state.usuario_atual

    if usuario_atual not in banco_notas:
        banco_notas[usuario_atual] = ""

    st.markdown(f"✍️ Editando anotações para a conta: **{usuario_atual}**")
    
    texto_usuario = st.text_area(
        "Escreva suas anotações, lembretes ou rascunhos de atendimento:",
        value=banco_notas[usuario_atual],
        height=350,
        key="txt_bloco_notas_usuario"
    )

    if st.button("💾 Salvar Anotações no Banco de Dados", type="primary"):
        banco_notas[usuario_atual] = texto_usuario
        salvar_banco_notas(banco_notas)
        st.success("✅ Suas anotações foram salvas com segurança no banco de dados do sistema!")

st.divider()
