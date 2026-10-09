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
        "📊 Dashboard de Ocorrências", 
        "📷 Tratativa & Relatório Técnico",
        "📝 Elaboração de Contrato"
    ]
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

    st.button("🔄 Novo Cliente / Limpar", on_click=resetar_dados_cliente)

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
                self.cell(0, 8, "RELATÓRIO TÉCNICO", align="C", ln=1)
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
                    try:
                        img = Image.open(arq)
                        if img.mode != "RGB": img = img.convert("RGB")
                        t_path = f"temp_{cat}_{idx}.jpg"
                        img.save(t_path)
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
                        if os.path.exists(t_path): os.remove(t_path)
                    except Exception:
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

        return pdf.output(dest="S").encode("latin-1")

    st.subheader("6. Ações Finais")
    col_a1, col_a2 = st.columns(2)

    with col_a1:
        if st.button("📄 Gerar Relatório PDF"):
            if not cod_cliente.strip() or not nome_cliente.strip():
                st.error("⚠️ Preencha pelo menos o Código e o Nome do Cliente.")
            else:
                pdf_bytes = gerar_pdf(st.session_state.equipamentos, dic_fotos_final, cod_cliente, nome_cliente, qtd_centrais)
                st.success("✅ PDF gerado com sucesso!")
                st.download_button(
                    label="📥 Baixar Relatório (PDF)",
                    data=pdf_bytes,
                    file_name=f"relatorio_{cod_cliente}.pdf",
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

            texto_final = f"""Ocorrência Vinculada: {oc_ativa['codigo'] if oc_ativa['codigo'] else 'Manual'}
Contato: {contato}
Departamento: {departamento}
Telefone: {telefone}
Equipamento de acordo com o contrato: {eq_contrato} - {desc_eq_contrato}
Consumo Previsto: {consumo_previsto} kg | Consumo Real: {consumo_real} kg
Possui ART: {possui_art} - {desc_art}
Central dentro de norma: {central_norma}

{lista_eq_txt}
Observações: {observacoes}
"""
            st.success("✅ Texto gerado com sucesso! Copie abaixo:")
            st.code(texto_final, language="text")


# =====================================================================
# TELA 3: ELABORAÇÃO DE CONTRATO (Novo Submenu)
# =====================================================================
elif menu == "📝 Elaboração de Contrato":
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Elaboração de Contrato")
        st.markdown("Formulário de preenchimento e geração do padrão de solicitação.")

    st.divider()

    tipo_fluxo = st.radio(
        "Selecione o objetivo da solicitação:", 
        ["Gerar Minuta", "Enviar para Assinatura"],
        horizontal=True
    )

    st.write("")
    st.subheader("Dados da Solicitação")

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        motivo_solicitacao = st.text_input("Motivo da solicitação", placeholder="Ex: Alteração de CNPJ + Reneg de Preço")
        contato_contrato = st.text_input("Contato", placeholder="Ex: Sidnei")
        telefone_contrato = st.text_input("Telefone", placeholder="Ex: 11 99157-0730")
        email_contrato = st.text_input("E-mail", placeholder="Ex: adm@grscondominios.com.br")
        tipo_contrato = st.selectbox("Contrato / Aditamento / Distrato", ["Contrato", "Aditamento", "Distrato"])
        mesmo_prop = st.selectbox("Mesmo proprietário?", ["Sim", "Não"])
        novo_cnpj = st.text_input("Novo CNPJ", placeholder="Ex: 58.582.414/0001-56")
        nova_ie = st.text_input("Nova I.E.", placeholder="Ex: 234.208.886.111")
        endereco_padrao = st.text_input("Endereço padrão ou entrega?", placeholder="Ex: Padrão + ENTREGA1")

    with col_c2:
        preco_granel = st.text_input("Preço Granel", placeholder="Ex: 7,50")
        preco_cilindro = st.text_input("Preço Cilindro", placeholder="Ex: ")
        cond_pagamento = st.text_input("Condição de pagamento", placeholder="Ex: 14 dias")
        consumo_granel = st.text_input("Consumo previsto (Granel) mensal", placeholder="Ex: 100 kgs")
        consumo_cilindro = st.text_input("Qual consumo previsto (Cilindro) mensal", placeholder="Ex: ")
        vigencia = st.text_input("Vigência", placeholder="Ex: 60 meses")
        equipamentos_contrato = st.text_input("Equipamentos", placeholder="Ex: 01 b190 + 01 CC")

    st.write("")
    resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", placeholder="Ex: n/a")
    email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato", placeholder="Ex: N/A")

    if tipo_fluxo == "Enviar para Assinatura":
        st.markdown("---")
        st.markdown("### Dados de Assinatura e Testemunhas")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            nome_testemunha = st.text_input("Nome da Testemunha", placeholder="")
            email_testemunha = st.text_input("E-mail da Testemunha", placeholder="")
        with col_a2:
            nome_responsavel = st.text_input("Nome da Responsável pela assinatura", placeholder="")
            email_responsavel = st.text_input("E-mail da Responsável pela assinatura", placeholder="")
    else:
        nome_testemunha = ""
        email_testemunha = ""
        nome_responsavel = ""
        email_responsavel = ""

    st.divider()
    st.markdown("### Condomínio CONTA SIM?")
    conta_sim = st.selectbox("Condomínio CONTA SIM?", ["Não", "Sim"])

    num_unidades = ""
    qtd_torres = ""
    qtd_blocos = ""
    preco_religue = ""
    preco_servico = ""

    if conta_sim == "Sim":
        col_cs1, col_cs2, col_cs3 = st.columns(3)
        with col_cs1:
            num_unidades = st.text_input("N° Unid autônomas (Aptos + áreas comuns/zeladoria)", placeholder="")
            qtd_torres = st.text_input("Qtd Torres", placeholder="")
        with col_cs2:
            qtd_blocos = st.text_input("Qtd Blocos", placeholder="")
            preco_religue = st.text_input("Valor preço de religue", placeholder="")
        with col_cs3:
            preco_servico = st.text_input("Valor preço de serviço", placeholder="")

    st.write("")
    observacoes_contrato = st.text_area("Obs.", placeholder="Ex: Cliente trocou de CNPJ...")

    st.divider()
    if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
        texto_padrao_contrato = f"""ELABORAÇÃO DE CONTRATO

Motivo da solicitação: {motivo_solicitacao}

Contato: {contato_contrato}
Telefone: {telefone_contrato}
E-mail: {email_contrato}
Contrato / Aditamento / Distrato: {tipo_contrato}
Mesmo proprietário?(sim/não): {mesmo_prop}
Novo CNPJ: {novo_cnpj}
Nova I.E.: {nova_ie}
Endereço padrão ou entrega?: {endereco_padrao}
Preço Granel: {preco_granel}
Preço Cilindro: {preco_cilindro}
Condição de pagamento: {cond_pagamento}
Consumo previsto (Granel) mensal: {consumo_granel}
Qual consumo previsto (Cilindro) mensal: {consumo_cilindro}
Vigência: {vigencia}
Equipamentos: {equipamentos_contrato}

Quem será o responsável pelas NF's pendentes? {resp_pendentes}
E-mail do novo proprietário que receberá o novo contrato: {email_novo_prop}

Nome da Testemunha: {nome_testemunha}
E-mail da Testemunha: {email_testemunha}
Nome da Responsável pela assinatura: {nome_responsavel}
E-mail da Responsável pela assinatura: {email_responsavel}

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
        st.code(texto_padrao_contrato, language="text")
