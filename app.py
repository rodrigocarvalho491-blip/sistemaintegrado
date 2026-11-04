import os
import json
import base64
import html as html_lib
import uuid
import tempfile
import io
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
st.set_page_config(
    page_title="Sistema Integrado | Consigaz", 
    page_icon="🔥", 
    layout="wide",
    initial_sidebar_state="expanded"
)

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")
LOGO2_PATH = os.path.join(DIRETORIO_ATUAL, "logo2.png")

# --- CONEXÃO COM SUPABASE ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))

def carregar_dados_supabase(tabela):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {}
    try:
        url = f"{SUPABASE_URL}/rest/v1/{tabela}?select=*"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            res = {}
            for row in dados:
                res[row["chave"]] = row["valor"]
            return res
    except Exception:
        pass
    return {}

def salvar_dado_supabase(tabela, chave, valor):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/{tabela}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        payload = {"chave": chave, "valor": valor}
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass

# --- DESIGN MODERNO & DESIGN SYSTEM CONSIGAZ ---
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
    background-color: #FFFFFF !important;
    color: #1E293B !important;
}

[data-testid="stHeader"] { 
    display: none !important; 
}

.block-container, [data-testid="stMainBlockContainer"] {
    max-width: 1280px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
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
.cg-logo { height: 50px; width: auto; display: block; }

.cg-header-sep { width: 2px; align-self: stretch; background: #E2E8F0; }
.cg-title { font-size: 1.6rem; font-weight: 800; line-height: 1.2; color: #003366 !important; }
.cg-subtitle { font-size: 0.95rem; margin-top: 0.2rem; color: #64748B !important; font-weight: 500; }

.stApp h3 {
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    color: #003366 !important;
    padding: 0.2rem 0 0.2rem 0.6rem !important;
    border-left: 4px solid #F28C28 !important;
    margin-top: 1.5rem !important;
    margin-bottom: 1.0rem !important;
}

.stButton > button, .stDownloadButton > button {
    border-radius: 12px !important;
    font-weight: 700 !important;
    padding: 0.6rem 1.4rem !important;
    background: linear-gradient(135deg, #0055A5 0%, #003366 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(0, 85, 165, 0.2) !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    opacity: 0.95;
    transform: translateY(-1px);
}
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

def botao_copiar_customizado(texto, key_suffix=""):
    b64_txt = base64.b64encode(texto.encode("utf-8")).decode("utf-8")
    js_code = f"""
    <button id="btn_copiar_{key_suffix}" style="
        border-radius: 10px;
        font-weight: 700;
        padding: 0.5rem 1.2rem;
        background: linear-gradient(135deg, #F28C28 0%, #D97706 100%);
        color: #FFFFFF;
        border: none;
        cursor: pointer;
        font-family: sans-serif;
        box-shadow: 0 3px 10px rgba(242, 140, 40, 0.3);
    ">📋 Copiar Texto Formatado</button>
    <script>
    document.getElementById("btn_copiar_{key_suffix}").onclick = function() {{
        var text = atob("{b64_txt}");
        navigator.clipboard.writeText(text).then(function() {{
            alert("Texto copiado com sucesso!");
        }}, function(err) {{
            console.error('Erro ao copiar: ', err);
        }});
    }};
    </script>
    """
    components.html(js_code, height=45)

# --- CONSULTA IPCA AUTOMÁTICA ---
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
    return float(val_str), ultimo_periodo

def obter_ipca_acumulado_12m():
    try:
        valor, periodo = _buscar_ipca_ibge()
        if len(periodo) == 6:
            periodo = f"{periodo[4:6]}/{periodo[0:4]}"
        return valor, periodo
    except Exception:
        return 4.58, "10/2026"

# --- CLASSE E FUNÇÃO DE GERAÇÃO DE PDF OTIMIZADA ---
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

    # --- SEÇÃO 1: FOTOS UPLOADADAS (Otimizadas na memória via Pillow) ---
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
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    
                    img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)

                    fd, t_path = tempfile.mkstemp(suffix=f"_{uuid.uuid4().hex}.jpg")
                    os.close(fd)
                    img.save(t_path, format="JPEG", quality=80, optimize=True)

                    w_p, h_p = img.size
                    prop = h_p / w_p
                    w_alv = 130
                    h_alv = w_alv * prop

                    if h_alv > 110:
                        h_alv = 110
                        w_alv = h_alv / prop

                    pos_x = (210 - w_alv) / 2

                    if pdf.get_y() + h_alv > 265:
                        pdf.add_page()

                    pdf.image(t_path, x=pos_x, y=pdf.get_y(), w=w_alv, h=h_alv)
                    pdf.set_y(pdf.get_y() + h_alv + 6)

                except Exception as err:
                    pdf.set_font("Arial", "I", 9)
                    pdf.cell(0, 5, f"[Erro ao carregar foto: {err}]", ln=1)
                finally:
                    if t_path and os.path.exists(t_path):
                        try:
                            os.remove(t_path)
                        except OSError:
                            pass

    # --- SEÇÃO 2: TABELA DE EQUIPAMENTOS ---
    if equipamentos:
        pdf.add_page()
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, "LISTA DE ITENS E VAZÕES", ln=1, align="L")
        pdf.ln(2)

        def get_c_pdf(it): 
            return "Central" if qty_c == 1 else it.get("central", "Central")

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

# --- SISTEMA DE AUTENTICAÇÃO E SESSÃO ---
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0
if "equipamentos" not in st.session_state:
    st.session_state.equipamentos = []

rc = st.session_state.reset_counter

def resetar_dados():
    st.session_state.reset_counter += 1
    st.session_state.equipamentos = []

# --- TELA DE LOGIN / AUTENTICAÇÃO ---
if not st.session_state.usuario_logado:
    cabecalho_pagina("Acesso ao Sistema", "Insira suas credenciais para acessar o painel integrado.")
    c_log1, c_log2 = st.columns([1, 1])
    with c_log1:
        usr_inp = st.text_input("Usuário", key="login_usr")
        pwd_inp = st.text_input("Senha", type="password", key="login_pwd")
        if st.button("🔑 Entrar no Sistema", use_container_width=True):
            if usr_inp.strip():
                st.session_state.usuario_logado = usr_inp.strip()
                st.rerun()
            else:
                st.error("Por favor, preencha o campo de usuário.")
    st.stop()

# --- NAVEGAÇÃO LATERAL ---
with st.sidebar:
    st.markdown(f"**Usuário:** {st.session_state.usuario_logado}")
    if st.button("🚪 Sair", key="btn_logout"):
        st.session_state.usuario_logado = None
        st.rerun()
    st.divider()
    
    aba_principal = st.radio(
        "Navegação Principais:", 
        ["🛠️ Tratativa de Ocorrências", "📊 Agenda de Ocorrências", "📓 Bloco de Notas Pessoal"]
    )
    st.divider()

    if aba_principal == "🛠️ Tratativa de Ocorrências":
        opcao_tratativa = st.radio(
            "Módulos de Tratativa:", 
            ["📷 Visita de Transferência", "📝 Elaboração de Contrato", "📋 Aprovação de Contrato", "🎂 Aniversário de Contrato"]
        )
        st.divider()
        st.button("🔄 Novo Cliente", on_click=resetar_dados, use_container_width=True)

# =====================================================================
# ABA 1: TRATATIVA DE OCORRÊNCIAS
# =====================================================================
if aba_principal == "🛠️ Tratativa de Ocorrências":
    
    # -------------------------------------------------------------
    # SUBPAGE 1: VISITA DE TRANSFERÊNCIA
    # -------------------------------------------------------------
    if opcao_tratativa == "📷 Visita de Transferência":
        cabecalho_pagina("Visita de Transferência", "Módulo para registro fotográfico, equipamentos e dados de vistoria técnica.")
        
        st.subheader("1. Identificação do Cliente")
        col1, col2, col3 = st.columns(3)
        with col1:
            cod_cliente = st.text_input("Código do Cliente *", key=f"cod_{rc}")
        with col2:
            nome_cliente = st.text_input("Nome / Razão Social *", key=f"nome_{rc}")
        with col3:
            telefone = st.text_input("Telefone *", key=f"tel_{rc}")

        col4, col5 = st.columns(2)
        with col4:
            contato = st.text_input("Contato *", key=f"cont_{rc}")
        with col5:
            departamento = st.text_input("Sobrenome ou Departamento *", key=f"dep_{rc}")

        st.divider()
        st.subheader("2. Relatório Fotográfico")
        qtd_centrais = st.number_input("Quantidade de Centrais no Cliente", min_value=1, max_value=5, value=1, key=f"qty_c_{rc}")
        
        dic_fotos_final = {}
        
        def carregar_fotos(rotulo):
            return st.file_uploader(f"Upload fotos {rotulo}", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"up_{rotulo}_{rc}")

        if qtd_centrais == 1:
            c1, c2, c3 = st.columns(3)
            with c1:
                dic_fotos_final["FACHADA"] = carregar_fotos("FACHADA")
                dic_fotos_final["CILINDROS"] = carregar_fotos("CILINDROS")
            with c2:
                dic_fotos_final["ABRIGO"] = carregar_fotos("ABRIGO")
            with c3:
                dic_fotos_final["CENTRAL"] = carregar_fotos("CENTRAL")
                dic_fotos_final["EQUIPAMENTOS"] = carregar_fotos("EQUIPAMENTOS")
        else:
            for i in range(1, int(qtd_centrais) + 1):
                st.markdown(f"**📸 CENTRAL {i:02d}**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    dic_fotos_final[f"ABRIGO CENTRAL {i:02d}"] = carregar_fotos(f"ABRIGO CENTRAL {i:02d}")
                with c2:
                    dic_fotos_final[f"CENTRAL {i:02d}"] = carregar_fotos(f"CENTRAL {i:02d}")
                with c3:
                    dic_fotos_final[f"EQUIPAMENTOS CENTRAL {i:02d}"] = carregar_fotos(f"EQUIPAMENTOS CENTRAL {i:02d}")

        st.divider()
        st.subheader("3. Ações Finais")
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
                texto_final = f"""Contato: {contato}
Sobrenome ou departamento: {departamento}
Telefone: {telefone}
Código do Cliente: {cod_cliente}
Nome do Cliente: {nome_cliente}
Relatório Fotográfico Gerado com Sucesso."""
                st.success("✅ Texto gerado com sucesso!")
                st.text_area("Texto Gerado:", value=texto_final, height=200, key=f"txt_vt_{rc}")
                botao_copiar_customizado(texto_final, "vt_txt")

    # -------------------------------------------------------------
    # SUBPAGE 2: ELABORAÇÃO DE CONTRATO
    # -------------------------------------------------------------
    elif opcao_tratativa == "📝 Elaboração de Contrato":
        cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento para elaboração de contratos e minutas.")
        
        col_opt, _ = st.columns([2, 2])
        with col_opt:
            tipo_solic = st.radio("Tipo de Solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, key=f"el_ts_{rc}")
        
        st.divider()
        st.subheader("1. Dados Principais")
        c1, c2, c3 = st.columns(3)
        with c1:
            motivo = st.text_input("Motivo da Solicitação", value="Alteração de CNPJ + Reneg de Preço", key=f"el_mot_{rc}")
            contato = st.text_input("Contato", key=f"el_cont_{rc}")
        with c2:
            telefone = st.text_input("Telefone", key=f"el_tel_{rc}")
            email = st.text_input("E-mail", key=f"el_email_{rc}")
        with c3:
            contrato_opcao = st.selectbox("Contrato / Aditamento / Distrato", ["Contrato", "Aditamento", "Distrato"], key=f"el_cop_{rc}")
            mesmo_prop = st.radio("Mesmo Proprietário?", ["Sim", "Não"], horizontal=True, key=f"el_mp_{rc}")

        st.divider()
        st.subheader("2. Dados Cadastrais & CNPJ")
        if mesmo_prop == "Sim":
            c_cnpj, c_ie = st.columns(2)
            with c_cnpj:
                cnpj_val = st.text_input("CNPJ", key=f"el_cnpj_{rc}")
            with c_ie:
                ie_val = st.text_input("I.E.", key=f"el_ie_{rc}")
        else:
            c_cnpj, c_ie = st.columns(2)
            with c_cnpj:
                cnpj_val = st.text_input("Novo CNPJ", key=f"el_ncnpj_{rc}")
            with c_ie:
                ie_val = st.text_input("Nova I.E.", key=f"el_nie_{rc}")

        st.divider()
        st.subheader("3. Comodato / Fornecimento")
        tipo_forn = st.radio("Tipo de Fornecimento:", ["Granel", "Cilindro", "Ambos"], horizontal=True, key=f"el_tf_{rc}")

        preco_g, cons_g = "", ""
        p13, p20, p45, cons_c_str = "", "", "", ""

        if tipo_forn in ["Granel", "Ambos"]:
            cg1, cg2 = st.columns(2)
            with cg1:
                preco_g = st.text_input("Preço Granel (R$/kg)", key=f"el_pg_{rc}")
            with cg2:
                cons_g = st.text_input("Consumo Previsto Granel (kg/mês)", key=f"el_cg_{rc}")

        if tipo_forn in ["Cilindro", "Ambos"]:
            st.markdown("**Preços e Quantidades por Modelo de Cilindro:**")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                p13 = st.text_input("Preço P13 (R$/und)", key=f"el_p13_{rc}")
                q13 = st.number_input("Qtd P13", min_value=0, value=0, key=f"el_q13_{rc}")
            with cc2:
                p20 = st.text_input("Preço P20 (R$/und)", key=f"el_p20_{rc}")
                q20 = st.number_input("Qtd P20", min_value=0, value=0, key=f"el_q20_{rc}")
            with cc3:
                p45 = st.text_input("Preço P45 (R$/und)", key=f"el_p45_{rc}")
                q45 = st.number_input("Qtd P45", min_value=0, value=0, key=f"el_q45_{rc}")
            
            tot_c_kg = (q13 * 13) + (q20 * 20) + (q45 * 45)
            cons_c_str = f"{tot_c_kg} kgs" if tot_c_kg > 0 else ""

        st.divider()
        if st.button("📝 Gerar Texto de Elaboração de Contrato"):
            minuta_txt = "\n** FAVOR GERAR MINUTA EM PDF PARA ENVIO AO CLIENTE **\n" if tipo_solic == "Gerar Minuta" else ""
            
            precos_c_arr = []
            if p13.strip(): precos_c_arr.append(f"[P13 = {p13} / und]")
            if p20.strip(): precos_c_arr.append(f"[P20 = {p20} / und]")
            if p45.strip(): precos_c_arr.append(f"[P45 = {p45} / und]")
            precos_c_str = " ".join(precos_c_arr)

            txt_elab = f"""Motivo da solicitação: {motivo}{minuta_txt}
Contato: {contato} Telefone: {telefone} E-mail: {email}
Contrato / Aditamento / Distrato: {contrato_opcao}
Mesmo proprietário?: {mesmo_prop}
CNPJ/Novo CNPJ: {cnpj_val} | IE/Nova IE: {ie_val}
Preço Granel: {preco_g}
Preço Cilindro: {precos_c_str}
Consumo previsto (Granel): {cons_g}
Consumo previsto (Cilindro): {cons_c_str}"""

            st.success("✅ Texto gerado com sucesso!")
            st.text_area("Texto Gerado:", value=txt_elab, height=250, key=f"txt_elab_out_{rc}")
            botao_copiar_customizado(txt_elab, "elab_txt")

    # -------------------------------------------------------------
    # SUBPAGE 3: APROVAÇÃO DE CONTRATO
    # -------------------------------------------------------------
    elif opcao_tratativa == "📋 Aprovação de Contrato":
        cabecalho_pagina("Aprovação de Contrato", "Formulário de aprovação, termos e negociações vigentes.")
        
        st.subheader("1. Identificação do Solicitante e Motivo")
        motivo_reg = st.text_input("Motivo da regularização *", key=f"ap_mot_{rc}")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            contato_ap = st.text_input("Contato", key=f"ap_c_{rc}")
        with c2:
            telefone_ap = st.text_input("Telefone", key=f"ap_t_{rc}")
        with c3:
            email_ap = st.text_input("E-mail", key=f"ap_e_{rc}")

        st.divider()
        st.subheader("2. Detalhes do Projeto Padrão")
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            projeto_num = st.text_input("Projeto (Informe o número completo do projeto) *", key=f"ap_proj_{rc}")
        with col_p2:
            st.write("")
            st.write("")
            is_cilindros = st.checkbox("Cilindros", key=f"ap_cil_{rc}")

        st.divider()
        if st.button("📝 Gerar Texto de Aprovação"):
            if not is_cilindros and not projeto_num.strip():
                st.error("⚠️ O campo 'Projeto' é obrigatório, a menos que a opção 'Cilindros' esteja marcada.")
            else:
                proj_final = "N/A" if is_cilindros else projeto_num
                txt_aprov = f"""Motivo da regularização: {motivo_reg}
Contato: {contato_ap} Telefone: {telefone_ap} E-mail: {email_ap}
Projeto Padrão: {proj_final}"""

                st.success("✅ Texto de Aprovação gerado com sucesso!")
                st.text_area("Texto Gerado:", value=txt_aprov, height=200, key=f"txt_ap_out_{rc}")
                botao_copiar_customizado(txt_aprov, "ap_txt")

    # -------------------------------------------------------------
    # SUBPAGE 4: ANIVERSÁRIO DE CONTRATO
    # -------------------------------------------------------------
    elif opcao_tratativa == "🎂 Aniversário de Contrato":
        cabecalho_pagina("Aniversário de Contrato", "Tratativa de reajuste por IPCA acumulado de 12 meses.")
        
        ipca_val, ipca_per = obter_ipca_acumulado_12m()
        st.info(f"📊 **IPCA Acumulado 12 Meses (IBGE - Ref {ipca_per}):** {ipca_val:.2f}%")
        
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            p_ant_str = st.text_input("Preço Anterior (R$)", key=f"an_pa_{rc}")
        with c_a2:
            clausula = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, key=f"an_cl_{rc}")

        p_aniv_str = "xx,xx"
        try:
            val_l = p_ant_str.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
            p_float = float(val_l)
            p_aniv_calc = p_float * (1 + (ipca_val / 100.0))
            p_aniv_str = f"{p_aniv_calc:.4f}".replace(".", ",")
        except ValueError:
            pass

        st.divider()
        if st.button("📝 Gerar Texto de Aniversário"):
            cl_txt = "\nCliente possui cláusula em contrato." if clausula == "Sim" else ""
            txt_aniv = f"""Aumento de Aniversário de contrato, IPCA - {ipca_val:.2f}%.{cl_txt}
Preço anterior: R ${p_ant_str if p_ant_str else 'xx,xx'}$
$Preço Aniversário: R$ {p_aniv_str}"""

            st.success("✅ Texto gerado com sucesso!")
            st.text_area("Texto Gerado:", value=txt_aniv, height=180, key=f"txt_aniv_out_{rc}")
            botao_copiar_customizado(txt_aniv, "aniv_txt")

        st.divider()
        st.subheader("Tratativa com C.I.")
        ci_val = st.text_input("Número da C.I.", key=f"an_ci_{rc}")
        if st.button("📝 Gerar Texto com C.I."):
            cl_txt = "\nCliente possui cláusula em contrato." if clausula == "Sim" else ""
            txt_ci = f"""Aumento de Aniversário de contrato, IPCA - {ipca_val:.2f}%.{cl_txt}
Preço anterior: R ${p_ant_str if p_ant_str else 'xx,xx'}$
$Preço Aniversário: R$ {p_aniv_str}
CI.: {ci_val if ci_val else '000.000.000'} - Preço Aniversário"""

            st.success("✅ Texto com C.I. gerado com sucesso!")
            st.text_area("Texto com C.I.:", value=txt_ci, height=200, key=f"txt_ci_out_{rc}")
            botao_copiar_customizado(txt_ci, "ci_txt")

# =====================================================================
# ABA 2: AGENDA DE OCORRÊNCIAS
# =====================================================================
elif aba_principal == "📊 Agenda de Ocorrências":
    cabecalho_pagina("Agenda de Ocorrências", "Painel interativo e acompanhamento das demandas da equipe.")
    st.info("📌 Carregue a planilha Excel oficial para visualizar indicadores, cidades e tratativas ativas.")
    
    file_excel = st.file_uploader("Upload da Planilha Excel (.xlsx)", type=["xlsx", "xls"], key=f"up_excel_{rc}")
    if file_excel:
        try:
            df = pd.read_excel(file_excel)
            st.success("Planilha carregada com sucesso!")
            st.dataframe(df.head(10), use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao ler planilha: {e}")

# =====================================================================
# ABA 3: BLOCO DE NOTAS PESSOAL
# =====================================================================
elif aba_principal == "📓 Bloco de Notas Pessoal":
    cabecalho_pagina("Bloco de Notas Pessoal", f"Anotações salvas de forma segura na nuvem para {st.session_state.usuario_logado}.")
    
    usr_key = f"notas_{st.session_state.usuario_logado}"
    notas_salvas = carregar_dados_supabase("notas")
    nota_atual = notas_salvas.get(usr_key, "")

    nova_nota = st.text_area("Suas Anotações:", value=nota_atual, height=350, key=f"area_notas_{rc}")
    if st.button("💾 Salvar Anotações na Nuvem"):
        salvar_dado_supabase("notas", usr_key, nova_nota)
        st.success("✅ Anotações salvas permanentemente no Supabase com sucesso!")
