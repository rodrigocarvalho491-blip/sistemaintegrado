import os
import re
import json
import uuid
import base64
import html as html_lib
import pandas as pd
import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components
import altair as alt
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from fpdf import FPDF

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
ARQUIVO_USUARIOS = os.path.join(DIRETORIO_ATUAL, "banco_usuarios.json")
ARQUIVO_NOTAS = os.path.join(DIRETORIO_ATUAL, "banco_notas.json")

# =====================================================================
# PERSISTÊNCIA LOCAL (USUÁRIOS E NOTAS)
# =====================================================================
def carregar_usuarios_local():
    if os.path.exists(ARQUIVO_USUARIOS):
        try:
            with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Usuário admin padrão
    return {
        "admin": {
            "senha": "admin",
            "nivel": "admin",
            "precisa_trocar": False
        }
    }

def salvar_usuarios_local(users):
    try:
        with open(ARQUIVO_USUARIOS, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

def carregar_notas_local():
    if os.path.exists(ARQUIVO_NOTAS):
        try:
            with open(ARQUIVO_NOTAS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def salvar_notas_local(notas):
    try:
        with open(ARQUIVO_NOTAS, "w", encoding="utf-8") as f:
            json.dump(notas, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

# --- DESIGN MODERNO & DESIGN SYSTEM CONSIGAZ (TEMA CLARO FORÇADO) ---
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

# --- CONSULTA IPCA AUTOMÁTICA (ROBUSTA IBGE/BACEN) ---
@st.cache_data(ttl=3600, show_spinner=False)
def obter_ipca_acumulado_12m():
    # 1. Tenta API SIDRA do IBGE (Tabela 1737 - IPCA variação acumulada em 12 meses)
    try:
        url = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-1/variaveis/2265?localidades=N1[1]"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            val_str = data[0]["resultados"][0]["series"][0]["serie"]
            ultimo_mes = sorted(val_str.keys())[-1]
            val = float(val_str[ultimo_mes])
            per = f"{ultimo_mes[4:6]}/{ultimo_mes[0:4]}"
            return val, per
    except Exception:
        pass

    # 2. Tenta API do Banco Central (SGS - Série 135 - IPCA acumulado em 12 meses)
    try:
        url_bacen = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.135/dados/ultimos/1?formato=json"
        resp = requests.get(url_bacen, timeout=5)
        if resp.status_code == 200:
            dados = resp.json()
            if dados:
                val = float(dados[0]["valor"])
                data_partes = dados[0]["data"].split("/")
                per = f"{data_partes[1]}/{data_partes[2]}"
                return val, per
    except Exception:
        pass

    # 3. Fallback web scraping leve da página oficial do IBGE
    try:
        url_site = "https://www.ibge.gov.br/explica/inflacao.php"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url_site, headers=headers, timeout=5)
        if resp.status_code == 200:
            match = re.search(r'([0-9]+,[0-9]+)\s*%', resp.text)
            if match:
                val = float(match.group(1).replace(",", "."))
                return val, "Atual"
    except Exception:
        pass

    # 4. Fallback padrão de segurança
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

# --- INICIALIZAÇÃO DE ESTADOS DA SESSÃO ---
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0
if "equipamentos" not in st.session_state:
    st.session_state.equipamentos = []
if "df_excel_agenda" not in st.session_state:
    st.session_state.df_excel_agenda = None

rc = st.session_state.reset_counter

def resetar_dados():
    st.session_state.reset_counter += 1
    st.session_state.equipamentos = []

# =====================================================================
# TELA DE LOGIN / AUTENTICAÇÃO
# =====================================================================
usuarios_db = carregar_usuarios_local()

if not st.session_state.usuario_logado:
    cabecalho_pagina("Acesso ao Sistema", "Insira suas credenciais para acessar o painel integrado Consigaz.")
    c_log1, c_log2 = st.columns([1, 1])
    with c_log1:
        usr_inp = st.text_input("Usuário", key="login_usr")
        pwd_inp = st.text_input("Senha", type="password", key="login_pwd")
        if st.button("🔑 Entrar no Sistema", use_container_width=True):
            u_clean = usr_inp.strip()
            if u_clean in usuarios_db:
                if usuarios_db[u_clean]["senha"] == pwd_inp:
                    st.session_state.usuario_logado = u_clean
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta.")
            else:
                st.error("❌ Usuário não encontrado.")
    st.stop()

# Verifica se o usuário precisa trocar a senha (ex: primeiro acesso 123456 ou reset)
user_info = usuarios_db.get(st.session_state.usuario_logado, {})
if user_info.get("precisa_trocar", False):
    cabecalho_pagina("Redefinição Obrigatória de Senha", "Por motivos de segurança, defina sua nova senha pessoal antes de continuar.")
    c_p1, c_p2 = st.columns([1, 1])
    with c_p1:
        nova_p1 = st.text_input("Nova Senha", type="password", key="nova_p1")
        nova_p2 = st.text_input("Confirme a Nova Senha", type="password", key="nova_p2")
        if st.button("💾 Salvar Nova Senha", use_container_width=True):
            if not nova_p1.strip() or len(nova_p1) < 4:
                st.error("A senha deve conter pelo menos 4 caracteres.")
            elif nova_p1 != nova_p2:
                st.error("As senhas não coincidem.")
            else:
                usuarios_db[st.session_state.usuario_logado]["senha"] = nova_p1
                usuarios_db[st.session_state.usuario_logado]["precisa_trocar"] = False
                salvar_usuarios_local(usuarios_db)
                st.success("Senha alterada com sucesso! Entrando no sistema...")
                st.rerun()
    st.stop()

# --- NAVEGAÇÃO LATERAL ---
with st.sidebar:
    st.markdown(f"**👤 Usuário:** {st.session_state.usuario_logado}")
    if st.button("🚪 Sair (Logout)", key="btn_logout", use_container_width=True):
        st.session_state.usuario_logado = None
        st.session_state.df_excel_agenda = None
        st.rerun()
    st.divider()
    
    lista_abas = ["🛠️ Tratativa de Ocorrências", "📊 Agenda de Ocorrências", "📓 Bloco de Notas Pessoal"]
    if user_info.get("nivel") == "admin":
        lista_abas.append("⚙️ Painel Admin")
        
    aba_principal = st.radio("Menu Principal:", lista_abas)
    st.divider()

    if aba_principal == "🛠️ Tratativa de Ocorrências":
        opcao_tratativa = st.radio(
            "Módulos de Tratativa:", 
            ["📷 Visita de Transferência", "📝 Elaboração de Contrato", "📋 Aprovação de Contrato", "🎂 Aniversário de Contrato"]
        )
        st.divider()
        st.button("🔄 Novo Cliente", on_click=resetar_dados, use_container_width=True)

    elif aba_principal == "📊 Agenda de Ocorrências":
        st.subheader("📁 Base de Dados")
        file_excel = st.file_uploader("Upload Planilha Excel (.xlsx)", type=["xlsx", "xls"], key=f"up_excel_{rc}")
        if file_excel:
            try:
                st.session_state.df_excel_agenda = pd.read_excel(file_excel)
                st.success("✅ Planilha carregada!")
            except Exception as e:
                st.error(f"Erro ao ler: {e}")

    elif aba_principal == "📓 Bloco de Notas Pessoal":
        st.subheader("📑 Suas Notas")
        notas_dict = carregar_notas_local()
        user_notas = notas_dict.get(st.session_state.usuario_logado, {})
        
        titulo_nova = st.text_input("Novo Título da Nota", key="novo_titulo_nota")
        cliente_nota = st.text_input("Cliente Vinculado (Opcional)", key="novo_cliente_nota")
        if st.button("➕ Criar Nova Nota", use_container_width=True):
            if titulo_nova.strip():
                if titulo_nova not in user_notas:
                    user_notas[titulo_nova] = {"cliente": cliente_nota, "conteudo": ""}
                    notas_dict[st.session_state.usuario_logado] = user_notas
                    salvar_notas_local(notas_dict)
                    st.success("Nota criada!")
                    st.rerun()
                else:
                    st.warning("Já existe uma nota com este título.")
            else:
                st.error("Informe um título.")
        st.divider()

# =====================================================================
# ABA 1: TRATATIVA DE OCORRÊNCIAS
# =====================================================================
if aba_principal == "🛠️ Tratativa de Ocorrências":
    
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

    elif opcao_tratativa == "📝 Elaboração de Contrato":
        cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento para elaboração de contratos e minutas.")
        
        st.subheader("Motivo")
        motivo = st.text_input("Motivo da Solicitação", key=f"el_mot_{rc}")
        
        st.subheader("Dados do Cliente")
        c1, c2, c3 = st.columns(3)
        with c1:
            contato = st.text_input("Contato", key=f"el_cont_{rc}")
        with c2:
            telefone = st.text_input("Telefone", key=f"el_tel_{rc}")
        with c3:
            email = st.text_input("E-mail", key=f"el_email_{rc}")

        st.subheader("Solicitação")
        tipo_solic = st.radio("Tipo de Solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, key=f"el_ts_{rc}")
        contrato_opcao = st.radio("Contrato / Aditamento / Distrato:", ["Contrato", "Aditamento", "Distrato"], horizontal=True, key=f"el_cop_{rc}")

        st.subheader("Dados do Contrato")
        col_end, col_mp = st.columns(2)
        with col_end:
            endereco_entrega = st.text_input("Endereço padrão ou entrega?", key=f"el_end_{rc}")
        with col_mp:
            mesmo_prop = st.radio("Mesmo proprietário?", ["Sim", "Não"], horizontal=True, key=f"el_mp_{rc}")

        col_cnpj, col_ie = st.columns(2)
        with col_cnpj:
            mesmo_cnpj = st.radio("Mesmo CNPJ?", ["Sim", "Não"], horizontal=True, key=f"el_mcnpj_{rc}")
        with col_ie:
            pass

        cnpj_label = "CNPJ" if mesmo_cnpj == "Sim" else "Novo CNPJ"
        ie_label = "I.E." if mesmo_cnpj == "Sim" else "Nova I.E."
        
        cc1, cc2 = st.columns(2)
        with cc1:
            cnpj_val = st.text_input(cnpj_label, key=f"el_cnpj_{rc}")
        with cc2:
            ie_val = st.text_input(ie_label, key=f"el_ie_{rc}")

        eq_entregas = st.number_input("Qtd de Endereços de Entrega / Centrais", min_value=1, max_value=5, value=1, key=f"el_qeq_{rc}")
        equipamentos_str = ""
        if eq_entregas == 1:
            equipamentos_str = st.text_input("Equipamentos", key=f"el_eq1_{rc}")
        else:
            arr_eq = []
            for eq_idx in range(1, eq_entregas + 1):
                val_eq = st.text_input(f"Equipamentos [Entrega {eq_idx}]", key=f"el_eq_{eq_idx}_{rc}")
                if val_eq.strip():
                    arr_eq.append(f"[Entrega {eq_idx}] {val_eq}")
            equipamentos_str = " ".join(arr_eq)

        email_novo_prop = "N/A"
        if mesmo_prop == "Não":
            email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato", key=f"el_enp_{rc}")

        c_pg, c_vig = st.columns(2)
        with c_pg:
            cond_pag = st.text_input("Condição de pagamento", key=f"el_cp_{rc}")
        with c_vig:
            vigencia = st.text_input("Vigência", key=f"el_vig_{rc}")

        st.subheader("Comodato / Fornecimento")
        tipo_forn = st.radio("Tipo de Fornecimento:", ["Granel", "Cilindro", "Ambos"], horizontal=True, key=f"el_tf_{rc}")

        preco_g, cons_g = "", ""
        p13, p20, p45, cons_c_str = "", "", "", ""
        q13, q20, q45 = 0, 0, 0

        if tipo_forn in ["Granel", "Ambos"]:
            cg1, cg2 = st.columns(2)
            with cg1:
                preco_g = st.text_input("Preço Granel (R$/kg)", key=f"el_pg_{rc}")
            with cg2:
                cons_g = st.text_input("Consumo mensal previsto (kgs)", key=f"el_cg_{rc}")

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

        st.subheader("Financeiro")
        possui_debito = st.radio("Cliente possui débitos?", ["Sim", "Não"], horizontal=True, key=f"el_deb_{rc}")
        resp_nf = "n/a"
        if possui_debito == "Sim":
            resp_nf = st.text_input("Quem será o responsável pelas NF's pendentes?", key=f"el_rnf_{rc}")

        if tipo_solic == "Enviar para Assinatura":
            st.subheader("Assinaturas e Testemunhas")
            t_col1, t_col2 = st.columns(2)
            with t_col1:
                nome_test = st.text_input("Nome da Testemunha", key=f"el_ntest_{rc}")
                email_test = st.text_input("E-mail da Testemunha", key=f"el_etest_{rc}")
            with t_col2:
                nome_resp = st.text_input("Nome do Responsável pela assinatura", key=f"el_nresp_{rc}")
                email_resp = st.text_input("E-mail do Responsável pela assinatura", key=f"el_eresp_{rc}")

        st.subheader("Condomínio CONTA SIM")
        conta_sim = st.radio("Condomínio CONTA SIM?", ["Sim", "Não"], horizontal=True, key=f"el_cs_{rc}")
        unid_aut, qtd_torres, qtd_blocos, val_relig, val_serv = "", "", "", "", ""
        if conta_sim == "Sim":
            cs1, cs2, cs3 = st.columns(3)
            with cs1:
                unid_aut = st.text_input("N° Unid autônomas (Aptos + áreas comuns/zeladoria)", key=f"el_ua_{rc}")
                qtd_torres = st.text_input("Qtd Torres", key=f"el_qt_{rc}")
            with cs2:
                qtd_blocos = st.text_input("Qtd Blocos", key=f"el_qb_{rc}")
                val_relig = st.text_input("Valor preço de religue", key=f"el_vr_{rc}")
            with cs3:
                val_serv = st.text_input("Valor preço de serviço", key=f"el_vs_{rc}")

        st.divider()
        if st.button("📝 Gerar Texto de Elaboração de Contrato"):
            minuta_aviso = "\n** FAVOR GERAR MINUTA EM PDF PARA ENVIO AO CLIENTE **\n" if tipo_solic == "Gerar Minuta" else ""
            
            precos_c_arr = []
            if p13.strip(): precos_c_arr.append(f"[P13 = {p13} / und]")
            if p20.strip(): precos_c_arr.append(f"[P20 = {p20} / und]")
            if p45.strip(): precos_c_arr.append(f"[P45 = {p45} / und]")
            precos_c_str = " ".join(precos_c_arr)

            txt_elab = f"""Motivo da solicitação: {motivo}{minuta_aviso}
Contato: {contato} Telefone: {telefone} E-mail: {email}
Contrato / Aditamento / Distrato: {contrato_opcao}
Mesmo proprietário?: {mesmo_prop}
{cnpj_label}: {cnpj_val} | {ie_label}: {ie_val}
Endereço padrão ou entrega?: {endereco_entrega}
Preço Granel: {preco_g}
Preço Cilindro: {precos_c_str}
Consumo previsto (Granel) mensal: {cons_g}
Qual consumo previsto (Cilindro) mensal: {cons_c_str}
Vigência: {vigencia}
Condição de pagamento: {cond_pag}
Equipamentos: {equipamentos_str}
Quem será o responsável pelas NF's pendentes?: {resp_nf}
E-mail do novo proprietário que receberá o novo contrato: {email_novo_prop}"""

            if tipo_solic == "Enviar para Assinatura":
                txt_elab += f"""
Nome da Testemunha: {nome_test} E-mail da Testemunha: {email_test}
Nome do Responsável pela assinatura: {nome_resp} E-mail do Responsável pela assinatura: {email_resp}"""

            txt_elab += f"\nCondomínio CONTA SIM?: {conta_sim}"
            if conta_sim == "Sim":
                txt_elab += f"""
N° Unid autônomas (Aptos + áreas comuns/zeladoria): {unid_aut}
Qtd Torres: {qtd_torres} Qtd Blocos: {qtd_blocos}
Valor preço de religue: {val_relig} Valor preço de serviço: {val_serv}"""

            st.success("✅ Texto gerado com sucesso!")
            st.text_area("Texto Gerado:", value=txt_elab, height=280, key=f"txt_elab_out_{rc}")
            botao_copiar_customizado(txt_elab, "elab_txt")

    elif opcao_tratativa == "📋 Aprovação de Contrato":
        cabecalho_pagina("Aprovação de Contrato", "Formulário de aprovação, termos e negociações vigentes.")
        
        st.subheader("1. Identificação do Solicitante e Contato")
        c1, c2, c3 = st.columns(3)
        with c1:
            contato_ap = st.text_input("Contato", key=f"ap_c_{rc}")
        with c2:
            telefone_ap = st.text_input("Telefone", key=f"ap_t_{rc}")
        with c3:
            email_ap = st.text_input("E-mail", key=f"ap_e_{rc}")

        st.subheader("2. Motivo e Dados Principais")
        motivo_reg = st.text_input("Motivo da regularização *", key=f"ap_mot_{rc}")
        atrib_email = st.radio("Atualizar E-mail?", ["Sim", "Não"], horizontal=True, key=f"ap_ae_{rc}")
        tipo_ap = st.radio("Contrato / Aditamento:", ["Contrato", "Aditamento"], horizontal=True, key=f"ap_ta_{rc}")
        vigencia_ap = st.text_input("Vigência", key=f"ap_vig_{rc}")
        
        eq_entregas_ap = st.number_input("Qtd de Endereços de Entrega / Centrais", min_value=1, max_value=5, value=1, key=f"ap_qeq_{rc}")
        equip_ap_str = ""
        if eq_entregas_ap == 1:
            equip_ap_str = st.text_input("Equipamentos", key=f"ap_eq1_{rc}")
        else:
            arr_eq_ap = []
            for eq_idx in range(1, eq_entregas_ap + 1):
                val_eq = st.text_input(f"Equipamentos [Entrega {eq_idx}]", key=f"ap_eq_{eq_idx}_{rc}")
                if val_eq.strip():
                    arr_eq_ap.append(f"[Entrega {eq_idx}] {val_eq}")
            equip_ap_str = " ".join(arr_eq_ap)

        especificidade_ap = st.text_input("Existe especificidade sobre a solicitação?", key=f"ap_esp_{rc}")

        st.subheader("3. Redimensionamento e Projetos")
        redim = st.radio("Redimensionamento:", ["Sim", "Não"], horizontal=True, key=f"ap_red_{rc}")
        c_p_ant, c_p_par = st.columns(2)
        with c_p_ant:
            com_passo = st.text_input("Comodato passou de:", key=f"ap_cp_{rc}")
        with c_p_par:
            com_para = st.text_input("Para:", key=f"ap_cpar_{rc}")
        
        inc_tanques = st.radio("Inclusão de tanques?", ["Sim", "Não"], horizontal=True, key=f"ap_it_{rc}")
        nec_pecas = st.radio("Necessário lista de peças?", ["Sim", "Não"], horizontal=True, key=f"ap_np_{rc}")

        st.subheader("4. Implantação de Conta Sim e Portaria")
        impl_cs = st.radio("Implantação de conta sim:", ["Sim", "Não"], horizontal=True, key=f"ap_ics_{rc}")
        env_pecas = st.radio("Foi enviado lista de peças?", ["Sim", "Não"], horizontal=True, key=f"ap_ep_{rc}")
        env_ficha = st.radio("Foi enviado ficha de cliente?", ["Sim", "Não"], horizontal=True, key=f"ap_ef_{rc}")
        
        tipo_portaria = st.text_input("Tipo de portaria", key=f"ap_tp_{rc}")
        contato_resp_port = st.text_input("Contato do responsável (portaria remota / apto)", key=f"ap_crp_{rc}")
        particularidades = st.text_input("Particularidades do local", key=f"ap_part_{rc}")
        contato_sindico = st.text_input("Contato atualizado do síndico", key=f"ap_csind_{rc}")

        st.subheader("5. Alteração de CNPJ ou Razão Social")
        alt_cnpj = st.radio("Alteração de CNPJ ou razão social?", ["Sim", "Não"], horizontal=True, key=f"ap_acnpj_{rc}")
        mesmo_prop_ap = st.radio("Se trata do mesmo proprietário:", ["Sim", "Não"], horizontal=True, key=f"ap_mpa_{rc}")
        
        possui_tit_aberto = st.radio("Possui títulos em aberto?", ["Sim", "Não"], horizontal=True, key=f"ap_pta_{rc}")
        neg_titulos = "n/a"
        if possui_tit_aberto == "Sim":
            neg_titulos = st.text_input("Descreva a negociação realizada com o novo proprietário:", key=f"ap_negt_{rc}")

        st.subheader("6. Redução de Vigência")
        red_vig = st.radio("Redução de vigência?", ["Sim", "Não"], horizontal=True, key=f"ap_rv_{rc}")
        motivo_red_vig = st.text_input("Motivo da redução de vigência", key=f"ap_mrv_{rc}")

        st.subheader("7. Projeto Padrão")
        col_proj, col_cil = st.columns([3, 1])
        with col_proj:
            projeto_num = st.text_input("Projeto (Informe o número completo do projeto)", key=f"ap_proj_{rc}")
        with col_cil:
            st.write("")
            st.write("")
            is_cilindros = st.checkbox("Cilindros", key=f"ap_cil_{rc}")

        st.divider()
        if st.button("📝 Gerar Texto de Aprovação"):
            proj_final = "N/A" if is_cilindros else projeto_num
            if not is_cilindros and not projeto_num.strip():
                st.error("⚠️ O campo 'Projeto' é obrigatório, a menos que a opção 'Cilindros' esteja marcada.")
            else:
                txt_aprov = f"""Motivo da regularização: {motivo_reg}
Contato: {contato_ap} Telefone: {telefone_ap} E-mail: {email_ap}
Atualizar E-mail? [{ 'x' if atrib_email=='Sim' else ' ' }] sim [{ 'x' if atrib_email=='Não' else ' ' }] não
Contrato / Aditamento: {tipo_ap}
Vigência: {vigencia_ap}
Equipamentos: {equip_ap_str}
Existe especificidade sobre a solicitação: {especificidade_ap}
Redimensionamento: [{ 'x' if redim=='Sim' else ' ' }] sim [{ 'x' if redim=='Não' else ' ' }] não
Comodato passou de: {com_passo} Para: {com_para}
Inclusão de tanques? [{ 'x' if inc_tanques=='Sim' else ' ' }] sim [{ 'x' if inc_tanques=='Não' else ' ' }] não
Necessário lista de peças? [{ 'x' if nec_pecas=='Sim' else ' ' }] sim [{ 'x' if nec_pecas=='Não' else ' ' }] não
Implantação de conta sim: [{ 'x' if impl_cs=='Sim' else ' ' }] sim [{ 'x' if impl_cs=='Não' else ' ' }] não"""

                if impl_cs == "Sim":
                    txt_aprov += f"""
Foi enviado lista de peças ? [{ 'x' if env_pecas=='Sim' else ' ' }] sim [{ 'x' if env_pecas=='Não' else ' ' }] não
Foi enviado ficha de cliente ? [{ 'x' if env_ficha=='Sim' else ' ' }] sim [{ 'x' if env_ficha=='Não' else ' ' }] não
Tipo de portaria: {tipo_portaria}
Contato do responsável: {contato_resp_port}
Particularidades do local: {particularidades}
Contato atualizado do síndico: {contato_sindico}"""

                txt_aprov += f"""
Alteração de CNPJ ou razão social? [{ 'x' if alt_cnpj=='Sim' else ' ' }] sim [{ 'x' if alt_cnpj=='Não' else ' ' }] não
Se trata do mesmo proprietário: ({ 'x' if mesmo_prop_ap=='Sim' else ' ' }) SIM ({ 'x' if mesmo_prop_ap=='Não' else ' ' }) NÃO
Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto: {neg_titulos}
Redução de vigência? [{ 'x' if red_vig=='Sim' else ' ' }] sim [{ 'x' if red_vig=='Não' else ' ' }] não"""
                if red_vig == "Sim":
                    txt_aprov += f" (Motivo: {motivo_red_vig})"

                txt_aprov += f"\nProjeto (Informe o número completo do projeto): {proj_final}"

                st.success("✅ Texto de Aprovação gerado com sucesso!")
                st.text_area("Texto Gerado:", value=txt_aprov, height=280, key=f"txt_ap_out_{rc}")
                botao_copiar_customizado(txt_aprov, "ap_txt")

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
$Preço Aniversário: R$  {p_aniv_str}"""

            st.success("✅ Texto gerado com sucesso!")
            st.text_area("Texto Gerado:", value=txt_aniv, height=180, key=f"txt_aniv_out_{rc}")
            botao_copiar_customizado(txt_aniv, "aniv_txt")

            st.markdown("### Preço Novo para Abertura da CI")
            st.warning("⚠️ Utilize este valor exato ao abrir a CI no sistema comercial.")
            st.code(f"R$ {p_aniv_str}", language="text")

        st.divider()
        st.subheader("Tratativa com C.I.")
        ci_val = st.text_input("Número da C.I. (9 dígitos sem ponto ou 11 com ponto)", key=f"an_ci_{rc}")
        
        ci_formatada = ci_val.strip()
        if ci_formatada.isdigit() and len(ci_formatada) == 9:
            ci_formatada = f"{ci_formatada[:3]}.{ci_formatada[3:6]}:{ci_formatada[6:]}".replace(":", ".")
        
        if st.button("📝 Gerar Texto com C.I."):
            cl_txt = "\nCliente possui cláusula em contrato." if clausula == "Sim" else ""
            txt_ci = f"""Aumento de Aniversário de contrato, IPCA - {ipca_val:.2f}%.{cl_txt}
Preço anterior: R ${p_ant_str if p_ant_str else 'xx,xx'}$
$Preço Aniversário: R$  {p_aniv_str}
CI.: {ci_formatada if ci_formatada else '000.358.982'} - Preço Aniversário"""

            st.success("✅ Texto com C.I. gerado com sucesso!")
            st.text_area("Texto com C.I.:", value=txt_ci, height=200, key=f"txt_ci_out_{rc}")
            botao_copiar_customizado(txt_ci, "ci_txt")

# =====================================================================
# ABA 2: AGENDA DE OCORRÊNCIAS
# =====================================================================
elif aba_principal == "📊 Agenda de Ocorrências":
    cabecalho_pagina("Agenda de Ocorrências", "Painel interativo e acompanhamento das demandas da equipe.")
    
    df_agenda = st.session_state.get("df_excel_agenda", None)
    if df_agenda is None:
        st.info("📌 Utilize o menu lateral para fazer o upload da planilha Excel de Pós-Vendas.")
    else:
        try:
            df = df_agenda.copy()
            # Localiza cabeçalho
            idx_cab = -1
            for idx, row in df.iterrows():
                row_str = " ".join([str(v) for v in row.values])
                if "Número da ocorrência" in row_str or "Prazo de Atendimento" in row_str:
                    idx_cab = idx
                    break
            if idx_cab != -1:
                df.columns = df.iloc[idx_cab]
                df = df.iloc[idx_cab + 1:].reset_index(drop=True)

            col_oc = "Número da ocorrência"
            col_cli = "Nome do cliente"
            col_end = "Endereço de Entrega"
            col_ab = "Data/Hora de abertura"
            col_pr = "Prazo de Atendimento"
            col_fech = "Data/Hora de fechamento"
            col_sub = "Subclassificação Ocorrência"

            if col_pr in df.columns:
                df["Prazo_DT"] = pd.to_datetime(df[col_pr], errors="coerce")
                df["Abertura_DT"] = pd.to_datetime(df[col_ab], errors="coerce") if col_ab in df.columns else datetime.now()
                df = df.dropna(subset=["Prazo_DT"])
                
                hoje_ts = pd.Timestamp(datetime.now().date())
                
                def calc_dias(row):
                    p = row["Prazo_DT"].normalize()
                    if p > hoje_ts:
                        return int(np.busday_count(hoje_ts.date(), p.date()))
                    elif p < hoje_ts:
                        return -int(np.busday_count(p.date(), hoje_ts.date()))
                    return 0

                df["Dias Úteis Restantes"] = df.apply(calc_dias, axis=1)

                def st_geral(row):
                    d = row["Dias Úteis Restantes"]
                    if d < 0: return "🔴 Vencido"
                    elif d == 0: return "🔵 Vence Hoje"
                    elif d == 1: return "🟠 Vence Amanhã"
                    return "🟢 No Prazo"

                df["Status Geral"] = df.apply(st_geral, axis=1)
                
                # Remove fechadas
                if col_fech in df.columns:
                    df = df[df[col_fech].isna()]

                # Menu lateral interno para Agenda
                menu_agenda = st.sidebar.radio("Filtros:", ["Todas as Ocorrências", "Comodato Inativo", "Ocorrências por Cidade"])
                
                if menu_agenda == "Todas as Ocorrências":
                    c_tot = len(df)
                    c_venc = len(df[df["Dias Úteis Restantes"] < 0])
                    c_hoje = len(df[df["Dias Úteis Restantes"] == 0])
                    c_aman = len(df[df["Dias Úteis Restantes"] == 1])
                    
                    # Sexta feira da semana atual
                    d_sem = hoje_ts + timedelta(days=(4 - hoje_ts.dayofweek) if hoje_ts.dayofweek <= 4 else 0)
                    c_sem = len(df[(df["Dias Úteis Restantes"] < 0) | ((df["Prazo_DT"].dt.normalize() >= hoje_ts) & (df["Prazo_DT"].dt.normalize() <= d_sem))])

                    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                    sel_filtro = st.session_state.get("sel_filtro_agenda", "Todas")
                    
                    with mc1:
                        if st.button(f"**{c_tot}**\nTotal", use_container_width=True):
                            st.session_state.sel_filtro_agenda = "Todas"
                            st.rerun()
                    with mc2:
                        if st.button(f"**{c_venc}**\nVencidas", use_container_width=True):
                            st.session_state.sel_filtro_agenda = "Vencidas"
                            st.rerun()
                    with mc3:
                        if st.button(f"**{c_hoje}**\nVence Hoje", use_container_width=True):
                            st.session_state.sel_filtro_agenda = "Hoje"
                            st.rerun()
                    with mc4:
                        if st.button(f"**{c_aman}**\nVence Amanhã", use_container_width=True):
                            st.session_state.sel_filtro_agenda = "Amanhã"
                            st.rerun()
                    with mc5:
                        if st.button(f"**{c_sem}**\nVencem na Semana", use_container_width=True):
                            st.session_state.sel_filtro_agenda = "Semana"
                            st.rerun()

                    filtro_ativo = st.session_state.get("sel_filtro_agenda", "Todas")
                    df_view = df.copy()
                    if filtro_ativo == "Vencidas":
                        df_view = df_view[df_view["Dias Úteis Restantes"] < 0]
                    elif filtro_ativo == "Hoje":
                        df_view = df_view[df_view["Dias Úteis Restantes"] == 0]
                    elif filtro_ativo == "Amanhã":
                        df_view = df_view[df_view["Dias Úteis Restantes"] == 1]
                    elif filtro_ativo == "Semana":
                        df_view = df_view[(df_view["Dias Úteis Restantes"] < 0) | ((df_view["Prazo_DT"].dt.normalize() >= hoje_ts) & (df_view["Prazo_DT"].dt.normalize() <= d_sem))]

                    df_view = df_view.sort_values(by="Dias Úteis Restantes", ascending=True)
                    
                    st.markdown(f"### Exibindo: {filtro_ativo}")
                    cols_show = [c for c in ["Status Geral", "Dias Úteis Restantes", col_oc, col_cli, col_end, col_pr] if c in df_view.columns]
                    st.dataframe(df_view[cols_show], use_container_width=True)

                elif menu_agenda == "Comodato Inativo":
                    st.subheader("📋 Relatório de Comodato Inativo")
                    if col_sub in df.columns:
                        df_ci = df[df[col_sub].astype(str).str.contains("Comodato Inativo", case=False, na=False)].copy()
                        if not df_ci.empty:
                            def calc_semanas(row):
                                ab = row["Abertura_DT"]
                                pr = row["Prazo_DT"]
                                dif_dias = (pr - ab).days
                                if dif_dias <= 7: return "🔴 3ª Semana"
                                elif dif_dias <= 14: return "🟡 2ª Semana"
                                return "🟢 1ª Semana"
                            df_ci["Semana Comodato"] = df_ci.apply(calc_semanas, axis=1)
                            st.dataframe(df_ci[[col_oc, col_cli, col_pr, "Semana Comodato"]], use_container_width=True)
                        else:
                            st.info("Nenhuma ocorrência de Comodato Inativo encontrada.")

                elif menu_agenda == "Ocorrências por Cidade":
                    st.subheader("🏙️ Ocorrências por Cidade")
                    def extrair_cidade(end):
                        if pd.isna(end): return "Outros"
                        partes = str(end).split(",")
                        if len(partes) >= 2: return partes[-2].strip().title()
                        return "Outros"
                    df["Cidade"] = df[col_end].apply(extrair_cidade) if col_end in df.columns else "Outros"
                    res_cid = df["Cidade"].value_counts().reset_index()
                    res_cid.columns = ["Cidade", "Quantidade"]
                    
                    c_t1, c_t2 = st.columns(2)
                    with c_t1:
                        st.dataframe(res_cid, use_container_width=True)
                    with c_t2:
                        chart = alt.Chart(res_cid).mark_bar().encode(
                            x=alt.X("Quantidade:Q"),
                            y=alt.Y("Cidade:N", sort="-x"),
                            color=alt.value("#0055A5")
                        ).properties(height=300).interactive(bind_x=False, bind_y=False)
                        st.altair_chart(chart, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao processar planilha: {e}")

# =====================================================================
# ABA 3: BLOCO DE NOTAS PESSOAL
# =====================================================================
elif aba_principal == "📓 Bloco de Notas Pessoal":
    cabecalho_pagina("Bloco de Notas Pessoal", f"Anotações salvas de forma segura na nuvem para {st.session_state.usuario_logado}.")
    
    notas_dict = carregar_notas_local()
    user_notas = notas_dict.get(st.session_state.usuario_logado, {})
    
    if not user_notas:
        st.info("Utilize o menu lateral para criar a sua primeira nota com Título e Cliente.")
    else:
        titulos = list(user_notas.keys())
        nota_escolhida = st.selectbox("Selecione a Nota:", titulos)
        if nota_escolhida:
            dados_nota = user_notas[nota_escolhida]
            st.markdown(f"**Cliente Vinculado:** {dados_nota.get('cliente', '-')}")
            
            conteudo_atual = dados_nota.get("conteudo", "")
            novo_conteudo = st.text_area("Conteúdo da Nota:", value=conteudo_atual, height=350, key=f"txt_nota_{nota_escolhida}")
            
            col_n1, col_n2 = st.columns(2)
            with col_n1:
                if st.button("💾 Salvar Nota"):
                    user_notas[nota_escolhida]["conteudo"] = novo_conteudo
                    notas_dict[st.session_state.usuario_logado] = user_notas
                    salvar_notas_local(notas_dict)
                    st.success("Nota salva com sucesso!")
            with col_n2:
                if st.button("🗑️ Excluir Nota"):
                    del user_notas[nota_escolhida]
                    notas_dict[st.session_state.usuario_logado] = user_notas
                    salvar_notas_local(notas_dict)
                    st.success("Nota excluída!")
                    st.rerun()

# =====================================================================
# ABA 4: PAINEL ADMIN (APENAS PARA O ADMIN)
# =====================================================================
elif aba_principal == "⚙️ Painel Admin" and user_info.get("nivel") == "admin":
    cabecalho_pagina("Painel do Administrador", "Gerenciamento de usuários e acessos do sistema.")
    
    st.subheader("👥 Usuários Cadastrados")
    u_list = []
    for u, v in usuarios_db.items():
        u_list.append({"Usuário": u, "Nível": v.get("nivel", "convencional"), "Troca Obrigatória": v.get("precisa_trocar", False)})
    st.dataframe(pd.DataFrame(u_list), use_container_width=True)
    
    st.divider()
    st.subheader("➕ Cadastrar Novo Usuário")
    novo_usr = st.text_input("Novo Usuário", key="admin_novo_usr")
    novo_niv = st.selectbox("Nível de Acesso", ["convencional", "admin"], key="admin_novo_niv")
    
    if st.button("Cadastrar Usuário (Senha Inicial: 123456)"):
        clean_nu = novo_usr.strip()
        if clean_nu:
            if clean_nu in usuarios_db:
                st.error("Usuário já existe.")
            else:
                usuarios_db[clean_nu] = {
                    "senha": "123456",
                    "nivel": novo_niv,
                    "precisa_trocar": True
                }
                salvar_usuarios_local(usuarios_db)
                st.success(f"Usuário {clean_nu} cadastrado com sucesso! Senha inicial: 123456 (com troca obrigatória).")
                st.rerun()
        else:
            st.error("Informe um nome de usuário válido.")

    st.divider()
    st.subheader("🔄 Resetar Senha de Usuário para Inicial (123456)")
    usr_para_reset = st.selectbox("Selecione o Usuário:", list(usuarios_db.keys()), key="select_reset_usr")
    if st.button("🔄 Resetar Senha para 123456"):
        usuarios_db[usr_para_reset]["senha"] = "123456"
        usuarios_db[usr_para_reset]["precisa_trocar"] = True
        salvar_usuarios_local(usuarios_db)
        st.success(f"Senha do usuário '{usr_para_reset}' resetada para 123456 com sucesso!")
        st.rerun()

    st.divider()
    st.subheader("🗑️ Remover Usuário")
    usr_para_remover = st.selectbox("Selecione o Usuário para Excluir:", [u for u in usuarios_db.keys() if u != "admin"], key="select_rem_usr")
    if usr_para_remover:
        if st.button("🗑️ Excluir Usuário Selecionado"):
            del usuarios_db[usr_para_remover]
            salvar_usuarios_local(usuarios_db)
            st.success(f"Usuário {usr_para_remover} removido com sucesso!")
            st.rerun()
