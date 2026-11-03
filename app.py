import os
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
from io import BytesIO

# --- CONFIGURAÇÃO DA PÁGINA ---
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")

st.set_page_config(
    page_title="ERP | Gestão de Ocorrências e Pós-Vendas", 
    page_icon="⚡", 
    layout="wide"
)

# --- MAPEAMENTO DAS COLUNAS DO SEU EXCEL ---
COL_OCORRENCIA = "Número da ocorrência"
COL_CLIENTE = "Nome do cliente"
COL_ENDERECO = "Endereço de Entrega"
COL_ABERTURA = "Data/Hora de abertura"
COL_PRAZO = "Prazo de Atendimento"
COL_FECHAMENTO = "Data/Hora de fechamento"
COL_SUB_CLASSIF = "Subclassificação Ocorrência"

# Inicializa a memória de ocorrências tratadas manualmente na sessão do Streamlit
if "tratadas_manualmente" not in st.session_state:
    st.session_state.tratadas_manualmente = set()

# Função robusta para extrair apenas o nome limpo da cidade do endereço de entrega
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

# Função para calcular dias úteis (dias de semana) entre duas datas
def calcular_dias_uteis(data_inicio, data_fim):
    h = pd.Timestamp(data_inicio).normalize().date()
    p = pd.Timestamp(data_fim).normalize().date()
    if p > h:
        return int(np.busday_count(h, p))
    elif p < h:
        return -int(np.busday_count(p, h))
    else:
        return 0

# Função de status para a planilha geral (com "Vence Amanhã")
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

# Função de status específica para comodatos
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

# --- TOPBAR / CABEÇALHO DO SISTEMA INTEGRADO ---
col_logo, col_titulo, col_status_sis = st.columns([1, 6, 2])

with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    else:
        st.markdown("🏢 **ERP CONNECT**")

with col_titulo:
    st.markdown("### **Módulo de Pós-Vendas & Atendimento**")
    st.caption("Sistema Integrado de Gestão de Ocorrências por Prazos, SLAs e Geografia")

with col_status_sis:
    st.markdown("<div style='text-align: right; padding-top: 10px;'><span style='background-color: #DCFCE7; color: #166534; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;'>● Servidor Ativo</span></div>", unsafe_allow_html=True)

st.divider()

# --- SEÇÃO 1: IMPORTAÇÃO DE DADOS ---
st.subheader("1. Atualização de Dados")

arquivo_excel = st.file_uploader(
    "Faça o upload do relatório Excel (Pós-Vendas) 📂", 
    type=["xlsx", "xls"]
)

st.divider()

if arquivo_excel is not None:
    try:
        df_raw = pd.read_excel(arquivo_excel, header=None)
        
        header_row = None
        for i, row in df_raw.iterrows():
            row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
            if "Número da ocorrência" in row_str:
                header_row = i
                break
        
        if header_row is not None:
            df = pd.read_excel(arquivo_excel, header=header_row)
        else:
            df = pd.read_excel(arquivo_excel, header=11)
            
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=[COL_OCORRENCIA])
        
        df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
        df_pendentes[COL_OCORRENCIA] = pd.to_numeric(df_pendentes[COL_OCORRENCIA], errors='coerce')
        df_pendentes = df_pendentes.dropna(subset=[COL_OCORRENCIA])
        df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
        
        df_pendentes = df_pendentes[~df_pendentes[COL_OCORRENCIA].isin(st.session_state.tratadas_manualmente)]
        
        df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
        df_pendentes['Abertura_DT'] = pd.to_datetime(df_pendentes[COL_ABERTURA], format="%d/%m/%Y %H:%M", errors='coerce')
        df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
        
        df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
        df_pendentes[COL_SUB_CLASSIF] = df_pendentes[COL_SUB_CLASSIF].fillna("-").astype(str)
        
        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        df_pendentes['Dias Úteis Restantes'] = df_pendentes['Prazo_DT'].apply(lambda x: calcular_dias_uteis(hoje, x))
        
        df_pendentes['Status Geral'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_geral)
        df_pendentes['Status Comodato'] = df_pendentes['Dias Úteis Restantes'].apply(classificar_status_comodato)
        df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
        
        # --- SEÇÃO 2: PAINEL DE OCORRÊNCIAS (DASHBOARD GERAL) ---
        st.subheader("2. Agenda Geral de Visitas Pendentes")
        
        st.markdown("### Filtros de Visualização")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            mostrar_so_hoje = st.toggle("📅 Mostrar apenas ocorrências com prazo PARA HOJE", value=False)
        with col_t2:
            mostrar_so_semana = st.toggle("🗓️ Mostrar apenas os próximos 5 dias úteis", value=False)
        
        cidades_unicas = sorted(list(df_pendentes['Cidade'].unique()))
        sub_class_unicas = sorted(list(df_pendentes[COL_SUB_CLASSIF].unique()))
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            cidades_selecionadas = st.multiselect("Filtrar por Cidade(s):", cidades_unicas, default=[], key="filtro_cidade")
        with col_f2:
            sub_class_selecionadas = st.multiselect("Filtrar por Sub-Classificação:", sub_class_unicas, default=[], key="filtro_sub")
        
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
        st.markdown("**Lista de Ocorrências Ordenadas (Mais Próxima para a Mais Distante):**")
        
        if df_filtrado.empty:
            st.success("✅ Excelente! Não há nenhuma ocorrência pendente para os filtros selecionados.")
        else:
            df_exibicao = df_filtrado[[
                'Status Geral',
                'Dias Úteis Restantes',
                COL_OCORRENCIA, 
                COL_CLIENTE, 
                'Cidade', 
                COL_SUB_CLASSIF,
                'Data Atendimento'
            ]].copy()
            df_exibicao[COL_OCORRENCIA] = df_exibicao[COL_OCORRENCIA].astype(str)
            
            edited_df = st.data_editor(
                df_exibicao.assign(Tratar=False),
                column_config={
                    "Tratar": st.column_config.CheckboxColumn("✅ Marcar Tratada?", required=True),
                    'Status Geral': st.column_config.TextColumn("Status", width="small", disabled=True),
                    'Dias Úteis Restantes': st.column_config.NumberColumn("Dias Úteis Restantes", width="small", disabled=True),
                    COL_OCORRENCIA: st.column_config.TextColumn("Nº Ocorrência", width="small", disabled=True),
                    COL_CLIENTE: st.column_config.TextColumn("Nome do Cliente", width="large", disabled=True),
                    'Cidade': st.column_config.TextColumn("Cidade", width="small", disabled=True),
                    COL_SUB_CLASSIF: st.column_config.TextColumn("Sub-Classificação", width="medium", disabled=True),
                    'Data Atendimento': st.column_config.TextColumn("Data de Atendimento", width="medium", disabled=True),
                },
                hide_index=True,
                use_container_width=True,
                key="editor_geral"
            )
            
            ocorrencias_para_tratar = edited_df[edited_df["Tratar"] == True][COL_OCORRENCIA].tolist()
            
            if ocorrencias_para_tratar:
                st.warning(f"⚠️ Você selecionou **{len(ocorrencias_para_tratar)}** ocorrência(s) para marcar como tratada(s).")
                if st.button("🔒 Confirmar e Remover do Painel", type="primary"):
                    for oc in ocorrencias_para_tratar:
                        st.session_state.tratadas_manualmente.add(int(oc))
                    st.success("✅ Ocorrência(s) tratada(s) com sucesso e removida(s) do painel!")
                    st.rerun()

        st.divider()

        # --- SEÇÃO 3: RELATÓRIO SEPARADO DE COMODATO INATIVO ---
        st.subheader("3. Relatório Específico: Comodato Inativo")
        st.markdown("Separação exclusiva das ocorrências de **Comodato Inativo** com contagem regressiva em dias úteis e semanas.")

        df_comodato = df_pendentes[df_pendentes[COL_SUB_CLASSIF].str.contains("Comodato Inativo", case=False, na=False)].copy()

        if df_comodato.empty:
            st.info("ℹ️ Não foram encontradas ocorrências pendentes com a sub-classificação 'Comodato Inativo' no ficheiro enviado.")
        else:
            df_comodato['Data Atendimento'] = df_comodato['Prazo_DT'].dt.strftime('%d/%m/%Y')
            
            df_comodato_exibicao = df_comodato[[
                'Status Comodato',
                'Dias Úteis Restantes',
                COL_OCORRENCIA, 
                COL_CLIENTE, 
                'Cidade', 
                COL_SUB_CLASSIF,
                'Data Atendimento'
            ]].copy()
            df_comodato_exibicao[COL_OCORRENCIA] = df_comodato_exibicao[COL_OCORRENCIA].astype(str)

            st.metric("Total de Comodatos Inativos Pendentes", len(df_comodato_exibicao))
            
            edited_comodato = st.data_editor(
                df_comodato_exibicao.assign(Tratar=False),
                column_config={
                    "Tratar": st.column_config.CheckboxColumn("✅ Marcar Tratada?", required=True),
                    'Status Comodato': st.column_config.TextColumn("Status Semanal", width="small", disabled=True),
                    'Dias Úteis Restantes': st.column_config.NumberColumn("Dias Úteis Restantes", width="small", disabled=True),
                    COL_OCORRENCIA: st.column_config.TextColumn("Nº Ocorrência", width="small", disabled=True),
                    COL_CLIENTE: st.column_config.TextColumn("Nome do Cliente", width="large", disabled=True),
                    'Cidade': st.column_config.TextColumn("Cidade", width="small", disabled=True),
                    COL_SUB_CLASSIF: st.column_config.TextColumn("Sub-Classificação", width="medium", disabled=True),
                    'Data Atendimento': st.column_config.TextColumn("Data de Atendimento", width="medium", disabled=True),
                },
                hide_index=True,
                use_container_width=True,
                key="editor_comodato"
            )
            
            comodatos_para_tratar = edited_comodato[edited_comodato["Tratar"] == True][COL_OCORRENCIA].tolist()
            if comodatos_para_tratar:
                st.warning(f"⚠️ Você selecionou **{len(comodatos_para_tratar)}** comodato(s) inativo(s) para tratar.")
                if st.button("🔒 Confirmar Tratativa de Comodato", type="primary", key="btn_comodato"):
                    for oc in comodatos_para_tratar:
                        st.session_state.tratadas_manualmente.add(int(oc))
                    st.success("✅ Comodato(s) tratado(s) com sucesso e removido(s) do painel!")
                    st.rerun()

            st.write("")
            df_comodato_download = df_comodato_exibicao.copy()
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_comodato_download.to_excel(writer, index=False, sheet_name='Comodato Inativo')
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Baixar Planilha Separada (Comodato Inativo)",
                data=processed_data,
                file_name="comodatos_inativos_pendentes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.divider()

        # --- SEÇÃO 4: QUANTIDADE DE OCORRÊNCIAS POR CIDADE ---
        st.subheader("4. Resumo de Ocorrências por Cidade")
        st.markdown("Planilha detalhada com a contagem total de ocorrências pendentes agrupadas por cidade.")

        if not df_filtrado.empty:
            df_mapa_agrup = df_filtrado.groupby('Cidade').size().reset_index(name='Total Ocorrências')
            df_mapa_agrup = df_mapa_agrup.sort_values(by='Total Ocorrências', ascending=False)

            st.dataframe(
                df_mapa_agrup[['Cidade', 'Total Ocorrências']],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Nenhum dado disponível para exibir.")

    except Exception as e:
        st.error(f"⚠️ Ocorreu um erro ao processar o ficheiro. Certifique-se de ser o relatório padrão do sistema. Erro técnico: {e}")

else:
    st.info("👆 Por favor, faça o upload da folha de cálculo atualizada de ocorrências acima para carregar o dashboard.")

st.divider()

# --- BOTÃO FLUTUANTE DE REFRESH ---
col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
    if st.button("🔄 Atualizar Ecrã"):
        st.rerun()
