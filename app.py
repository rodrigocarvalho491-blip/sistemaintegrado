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
        url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception:
            return None
    return None

# --- FUNÇÃO PARA OBTER O IPCA ACUMULADO DE 12 MESES ATUALIZADO DO IBGE ---
def obter_ipca_acumulado_12m():
    try:
        url = "https://servicodados.ibge.gov.br/api/v3/agregados/1737/periodos/-1/variaveis/2266?localidades=N1[1]"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            data = response.json()
            serie = data[0]["resultados"][0]["séries"][0]["série"]
            ultimo_periodo = sorted(serie.keys())[-1]
            val_str = serie[ultimo_periodo]
            if val_str:
                return float(val_str)
    except Exception:
        pass
    
    return 4.58  # Valor oficial de referência atualizado

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

# --- COMPONENTE DE BOTÃO DE CÓPIAS COM ÍCONE ESPECIAL ---
def botao_copiar_customizado(texto_para_copiar, chave_unica):
    texto_seguro = texto_para_copiar.replace('`', '\\`').replace('$', '\\$').replace('\n', '\\n')
    component_html = f"""
    <div style="margin-top: 5px; margin-bottom: 10px;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background-color: #004080;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
            setTimeout(function() {{
                msg.style.display = "none";
            }}, 2500);
        }}, function(err) {{
            alert("Erro ao copiar texto: ", err);
        }});
    }}
    </script>
    """
    components.html(component_html, height=50)

# --- MENU LATERAL DE NAVEGAÇÃO ---
st.sidebar.title("📌 Menu de Navegação")
menu = st.sidebar.radio(
    "Selecione a página:", 
    [
        "📷 Visita de Transferência",
        "📝 Elaboração de Contrato",
        "📋 Aprovação de Contrato",
        "🎂 Aniversário de Contrato"
    ]
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

    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Visita de Transferência & Relatório Técnico")
        st.markdown("Gerador automatizado de relatórios técnicos e inspeções.")

    st.divider()

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
            botao_copiar_customizado(texto_final, "transferencia_txt")


# =====================================================================
# TELA 2: ELABORAÇÃO DE CONTRATO
# =====================================================================
elif menu == "📝 Elaboração de Contrato":
    rcc = st.session_state.reset_counter_contrato

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
        horizontal=True,
        key=f"fluxo_c_{rcc}"
    )

    st.divider()

    # --- TEMA 1: MOTIVO ---
    st.subheader("1. Motivo")
    motivo_solicitacao = st.text_input("Motivo da solicitação", placeholder="Ex: Alteração de CNPJ + Reneg de Preço", key=f"motivo_{rcc}")

    st.divider()

    # --- TEMA 2: DADOS DO CLIENTE ---
    st.subheader("2. Dados do Cliente")
    col_cli1, col_cli2, col_cli3 = st.columns(3)
    with col_cli1:
        contato_contrato = st.text_input("Contato", placeholder="Ex: Sidnei", key=f"contato_c_{rcc}")
    with col_cli2:
        telefone_contrato = st.text_input("Telefone", placeholder="Ex: 11 99157-0730", key=f"tel_c_{rcc}")
    with col_cli3:
        email_contrato = st.text_input("E-mail", placeholder="Ex: adm@grscondominios.com.br", key=f"email_c_{rcc}")

    st.divider()

    # --- TEMA 3: SOLICITAÇÃO ---
    st.subheader("3. Solicitação")
    tipo_contrato = st.radio("Contrato / Aditamento / Distrato", ["Contrato", "Aditamento", "Distrato"], horizontal=True, index=None, key=f"tp_cont_{rcc}")

    st.divider()

    # --- TEMA 4: DADOS DO CONTRATO ---
    st.subheader("4. Dados do Contrato")
    col_con1, col_con2 = st.columns(2)
    
    cnpj_campo_val, ie_campo_val = "", ""
    status_cnpj_txt, razao_social_txt = "", ""
    email_novo_prop = "n/a"

    with col_con1:
        endereco_padrao = st.text_input("Endereço padrão ou entrega?", placeholder="Ex: Padrão + ENTREGA1", key=f"end_padrao_{rcc}")
        
        st.markdown("Mesmo proprietário?")
        mesmo_prop_opt = st.radio("Mesmo proprietário?", ["Sim", "Não"], horizontal=True, index=None, label_visibility="collapsed", key=f"mesmo_prop_{rcc}")
        
        if mesmo_prop_opt == "Não":
            email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato", placeholder="Ex: novo@email.com", key=f"email_novo_{rcc}")

        st.markdown("Mesmo CNPJ?")
        mesmo_cnpj_opt = st.radio("Mesmo CNPJ?", ["Sim", "Não"], horizontal=True, index=None, label_visibility="collapsed", key=f"mesmo_cnpj_{rcc}")
        
        if mesmo_cnpj_opt == "Sim":
            cnpj_campo_val = st.text_input("CNPJ", placeholder="Ex: 58.582.414/0001-56", key=f"cnpj_val_{rcc}")
            ie_campo_val = st.text_input("I.E.", placeholder="Ex: 234.208.886.111", key=f"ie_val_{rcc}")
        elif mesmo_cnpj_opt == "Não":
            cnpj_campo_val = st.text_input("Novo CNPJ", placeholder="Ex: 58.582.414/0001-56", key=f"novo_cnpj_val_{rcc}")
            ie_campo_val = st.text_input("Nova I.E.", placeholder="Ex: 234.208.886.111", key=f"nova_ie_val_{rcc}")

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
        cond_pagamento = st.text_input("Condição de pagamento", placeholder="Ex: 14 dias", key=f"cond_pag_{rcc}")
        vigencia = st.text_input("Vigência", placeholder="Ex: 60 meses", key=f"vigencia_{rcc}")
        equipamentos_contrato = st.text_input("Equipamentos", placeholder="Ex: 01 b190 + 01 CC", key=f"eq_contrato_c_{rcc}")

    st.divider()

    # --- TEMA 5: COMODATO / FORNECIMENTO ---
    st.subheader("5. Comodato / Fornecimento")
    
    st.markdown("Tipo de Fornecimento")
    tipo_fornecimento = st.radio("Tipo de Fornecimento", ["Granel", "Cilindro"], horizontal=True, index=None, label_visibility="collapsed", key=f"tp_forn_{rcc}")
    
    preco_granel = ""
    consumo_granel = ""
    
    p13_val, p20_val, p45_val = "", "", ""
    p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
    consumo_cilindro_total = 0
    
    if tipo_fornecimento == "Granel":
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            preco_granel = st.text_input("Preço Granel", placeholder="Ex: 7,50", key=f"preco_granel_{rcc}")
        with col_g2:
            consumo_granel = st.text_input("Consumo mensal previsto (kgs)", placeholder="Ex: 100 kgs", key=f"cons_granel_{rcc}")
        
    elif tipo_fornecimento == "Cilindro":
        st.markdown("**Preços por Modelo de Cilindro:**")
        col_cp1, col_cp2, col_cp3 = st.columns(3)
        with col_cp1:
            p13_val = st.text_input("Preço P13 (/und)", placeholder="xx,xx", key=f"p13_v_{rcc}")
        with col_cp2:
            p20_val = st.text_input("Preço P20 (/und)", placeholder="xx,xx", key=f"p20_v_{rcc}")
        with col_cp3:
            p45_val = st.text_input("Preço P45 (/und)", placeholder="xx,xx", key=f"p45_v_{rcc}")

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

    # --- TEMA 6: FINANCEIRO ---
    st.subheader("6. Financeiro")
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        st.markdown("Cliente possui débitos?")
        possui_debito_fin = st.radio("Cliente possui débitos?", ["Não", "Sim"], horizontal=True, index=0, label_visibility="collapsed", key=f"possui_deb_{rcc}")
        
        resp_pendentes = "n/a"
        if possui_debito_fin == "Sim":
            resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", placeholder="Ex: Cliente", key=f"resp_pend_{rcc}")

    # --- DADOS DE ASSINATURA E TESTEMUNHAS ---
    responsaveis_dados = []
    nome_testemunha, email_testemunha = "", ""

    if tipo_fluxo == "Enviar para Assinatura":
        st.markdown("---")
        st.subheader("Dados de Assinatura e Testemunhas")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            nome_testemunha = st.text_input("Nome da Testemunha", placeholder="", key=f"nome_test_{rcc}")
        with col_t2:
            email_testemunha = st.text_input("E-mail da Testemunha", placeholder="", key=f"email_test_{rcc}")

        st.markdown("---")
        qtd_responsaveis = st.selectbox("Quantidade de Responsáveis pela Assinatura", [1, 2, 3, 4], index=0, key=f"qtd_resp_{rcc}")

        for i in range(1, qtd_responsaveis + 1):
            st.markdown(f"**Responsável {i}**")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                nome_resp = st.text_input(f"Nome do Responsável {i}", placeholder="", key=f"nome_resp_{i}_{rcc}")
            with col_r2:
                email_resp = st.text_input(f"E-mail do Responsável {i}", placeholder="", key=f"email_resp_{i}_{rcc}")
            responsaveis_dados.append({"nome": nome_resp, "email": email_resp})

    st.divider()

    # --- TEMA 7: CONTA SIM ---
    st.subheader("7. Condomínio CONTA SIM")
    st.markdown("Condomínio CONTA SIM?")
    conta_sim = st.radio("Condomínio CONTA SIM?", ["Não", "Sim"], horizontal=True, index=0, label_visibility="collapsed", key=f"conta_sim_{rcc}")

    num_unidades = ""
    qtd_torres = ""
    qtd_blocos = ""
    preco_religue = ""
    preco_servico = ""

    if conta_sim == "Sim":
        col_cs1, col_cs2, col_cs3 = st.columns(3)
        with col_cs1:
            num_unidades = st.text_input("N° Unid autônomas (Aptos + áreas comuns/zeladoria)", placeholder="", key=f"num_unid_{rcc}")
            qtd_torres = st.text_input("Qtd Torres", placeholder="", key=f"qtd_torres_{rcc}")
        with col_cs2:
            qtd_blocos = st.text_input("Qtd Blocos", placeholder="", key=f"qtd_blocos_{rcc}")
            preco_religue = st.text_input("Valor preço de religue", placeholder="", key=f"preco_rel_{rcc}")
        with col_cs3:
            preco_servico = st.text_input("Valor preço de serviço", placeholder="", key=f"preco_serv_{rcc}")

    st.write("")
    observacoes_contrato = st.text_area("Obs.", placeholder="Ex: Cliente trocou de CNPJ...", key=f"obs_c_{rcc}")

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
            preco_cilindro_str = f"[P13 = {p13_val} / und] [P20 = {p20_val} / und] [P45 = {p45_val} / und]"
            texto_padrao_contrato += f"\nPreço Cilindro: {preco_cilindro_str}"
            texto_padrao_contrato += f"\nConsumo mensal previsto: {consumo_cilindro_total} KGs"

        texto_padrao_contrato += f"""
Condição de pagamento: {cond_pagamento}
Vigência: {vigencia}
Equipamentos: {equipamentos_contrato}

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
        botao_copiar_customizado(texto_padrao_contrato, "contrato_txt")


# =====================================================================
# TELA 3: APROVAÇÃO DE CONTRATO
# =====================================================================
elif menu == "📋 Aprovação de Contrato":
    rcap = st.session_state.reset_counter_aprov

    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Aprovação de Contrato")
        st.markdown("Formulário de preenchimento para solicitação de aprovação.")

    st.divider()

    # --- 1. CONTATO ---
    st.subheader("1. Informações de Contato")
    c_ap1, c_ap2, c_ap3 = st.columns(3)
    with c_ap1:
        contato_ap = st.text_input("Contato *", placeholder="Ex: Roberto", key=f"ap_cont_{rcap}")
    with c_ap2:
        telefone_ap = st.text_input("Telefone *", placeholder="Ex: 11 98888-7777", key=f"ap_tel_{rcap}")
    with c_ap3:
        email_ap = st.text_input("E-mail *", placeholder="Ex: contato@cliente.com", key=f"ap_email_{rcap}")

    st.divider()

    # --- 2. DADOS PRINCIPAIS ---
    st.subheader("2. Dados e Motivo da Solicitação")
    motivo_reg = st.text_input("Motivo da regularização *", placeholder="Ex: Adequação de infraestrutura...", key=f"ap_motivo_{rcap}")

    c_ap4, c_ap5, c_ap6 = st.columns(3)
    with c_ap4:
        atualizar_email = st.selectbox("Atualizar E-mail?", ["Não", "Sim"], index=0, key=f"ap_atu_email_{rcap}")
    with c_ap5:
        contrato_adit = st.radio("Contrato / Aditamento", ["Contrato", "Aditamento"], horizontal=True, index=None, key=f"ap_tp_cont_{rcap}")
    with c_ap6:
        vigencia_ap = st.text_input("Vigência", placeholder="Ex: 60 meses", key=f"ap_vig_{rcap}")

    c_ap7, c_ap8 = st.columns(2)
    with c_ap7:
        equipamentos_ap = st.text_input("Equipamentos", placeholder="Ex: 01 B190...", key=f"ap_eq_{rcap}")
    with c_ap8:
        especificidade_ap = st.text_input("Existe especificidade sobre a solicitação?", placeholder="Ex: Nenhuma", key=f"ap_esp_{rcap}")

    st.divider()

    # --- 3. REDIMENSIONAMENTO ---
    st.subheader("3. Redimensionamento")
    redim = st.radio("Redimensionamento:", ["não", "sim"], horizontal=True, index=0, key=f"ap_redim_{rcap}")
    
    comodato_de, comodato_para = "", ""
    inc_tanques = "não"
    env_pecas = "não"

    if redim == "sim":
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            comodato_de = st.text_input("Comodato passou de:", placeholder="Ex: 01 B190", key=f"ap_com_de_{rcap}")
        with c_p2:
            comodato_para = st.text_input("Para:", placeholder="Ex: 02 B190", key=f"ap_com_para_{rcap}")
        
        c_p3, c_p4 = st.columns(2)
        with c_p3:
            inc_tanques = st.radio("Inclusão de tanques?", ["não", "sim"], horizontal=True, index=0, key=f"ap_inc_tanq_{rcap}")
        with c_p4:
            env_pecas = st.radio("Necessário lista de peças?", ["não", "sim"], horizontal=True, index=0, key=f"ap_env_pec_{rcap}")

    st.divider()

    # --- PROJETO PADRÃO (OBRIGATÓRIO OU CILINDROS) ---
    st.subheader("Projeto Padrão")
    col_proj1, col_proj2 = st.columns([3, 1])
    with col_proj1:
        projeto_num = st.text_input("Projeto (Informe o número completo do projeto) *", placeholder="Ex: PRJ-2026/001", key=f"ap_proj_{rcap}")
    with col_proj2:
        st.write("")
        st.write("")
        is_cilindros = st.checkbox("Cilindros", key=f"ap_cil_{rcap}")

    st.divider()

    # --- 4. CONTA SIM & PORTARIA ---
    st.subheader("4. Condomínio Conta Sim & Portaria")
    implantacao_csim = st.radio("Implantação de conta sim:", ["não", "sim"], horizontal=True, index=0, key=f"ap_csim_{rcap}")
    
    env_pecas_ficha = "não"
    env_ficha_cliente = "não"
    tp_portaria = ""
    contato_resp_port = ""
    part_local = ""
    contato_sindico = ""

    if implantacao_csim == "sim":
        c_cs1, c_cs2 = st.columns(2)
        with c_cs1:
            env_pecas_ficha = st.radio("Foi enviado lista de peças?", ["não", "sim"], horizontal=True, index=0, key=f"ap_csim_pec_{rcap}")
        with c_cs2:
            env_ficha_cliente = st.radio("Foi enviado ficha de clientes?", ["não", "sim"], horizontal=True, index=0, key=f"ap_csim_ficha_{rcap}")

        tp_portaria = st.text_input("Tipo de portaria", placeholder="Ex: Remota / Presencial", key=f"ap_tp_port_{rcap}")
        contato_resp_port = st.text_input("Contato do responsável (portaria remota, nº ap ou contato)", placeholder="Ex: Apto 42 ou Tel...", key=f"ap_cont_resp_{rcap}")
        part_local = st.text_input("Particularidades do local", placeholder="Ex: Acesso pela lateral...", key=f"ap_part_local_{rcap}")
        contato_sindico = st.text_input("Contato atualizado do síndico", placeholder="Ex: 11 99999-1111 (Síndico Carlos)", key=f"ap_cont_sind_{rcap}")

    st.divider()

    # --- 5. ALTERAÇÃO DE CNPJ / RAZÃO SOCIAL ---
    st.subheader("5. Alteração de CNPJ ou Razão Social")
    alt_cnpj = st.radio("Alteração de CNPJ ou razão social?", ["não", "sim"], horizontal=True, index=0, key=f"ap_alt_cnpj_{rcap}")
    
    mesmo_prop_opt = st.radio("Se trata do mesmo proprietário:", ["NÃO", "SIM"], horizontal=True, index=0, key=f"ap_mesmo_prop_{rcap}")
    neg_tit_opt = st.radio("Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto:", ["NÃO", "SIM"], horizontal=True, index=0, key=f"ap_neg_tit_{rcap}")
    projeto_alt = st.text_input("Projeto (Informe o número completo do projeto)", placeholder="Ex: PRJ-ALT-2026", key=f"ap_proj_alt_{rcap}")

    st.divider()

    # --- 6. REDUÇÃO DE VIGÊNCIA ---
    st.subheader("6. Redução de Vigência")
    red_vig = st.radio("Redução de vigência?", ["não", "sim"], horizontal=True, index=0, key=f"ap_red_vig_{rcap}")
    
    motivo_red_vig = ""
    if red_vig == "sim":
        motivo_red_vig = st.text_input("Descreva o motivo da redução de vigência:", placeholder="Ex: Acordo comercial...", key=f"ap_mot_red_{rcap}")

    st.divider()
    if st.button("📝 Gerar Texto de Aprovação de Contrato", type="primary"):
        
        # Validação do Projeto Padrão
        if not is_cilindros and not projeto_num.strip():
            st.error("⚠️ O campo 'Projeto' é obrigatório, a menos que a opção 'Cilindros' esteja marcada.")
        else:
            proj_final = "N/A" if is_cilindros else projeto_num

            sim_nao_redim = "sim" if redim == "sim" else "não"
            sim_nao_tanq = "sim" if inc_tanques == "sim" else "não"
            sim_nao_pecas = "sim" if env_pecas == "sim" else "não"
            
            sim_nao_csim = "sim" if implantacao_csim == "sim" else "não"
            sim_nao_csim_pec = "sim" if env_pecas_ficha == "sim" else "não"
            sim_nao_csim_ficha = "sim" if env_ficha_cliente == "sim" else "não"
            
            sim_nao_alt = "sim" if alt_cnpj == "sim" else "não"
            sim_nao_red_vig = "sim" if red_vig == "sim" else "não"

            texto_aprovacao = f"""Contato: {contato_ap}
Telefone: {telefone_ap}
E-mail: {email_ap}

Motivo da regularização: {motivo_reg}

Atualizar E-mail? {atualizar_email}
Contrato / Aditamento: {contrato_adit if contrato_adit else ''}
Vigência: {vigencia_ap}
Equipamentos: {equipamentos_ap}
Existe especificidade sobre a solicitação: {especificidade_ap}

Redimensionamento: [ {'x' if sim_nao_redim == 'sim' else ' '} ] sim [ {'x' if sim_nao_redim == 'não' else ' '} ] não
Projeto (Informe o número completo do projeto): {proj_final}
Comodato passou de: {comodato_de}
Para: {comodato_para}
Inclusão de tanques? [ {'x' if sim_nao_tanq == 'sim' else ' '} ] sim [ {'x' if sim_nao_tanq == 'não' else ' '} ] não (se sim, enviar informações para a ficha)
Necessário lista de peças? [ {'x' if sim_nao_pecas == 'sim' else ' '} ] sim [ {'x' if sim_nao_pecas == 'não' else ' '} ] não (se sim, enviar lista de peças):

Implantação de conta sim: [ {'x' if sim_nao_csim == 'sim' else ' '} ] sim [ {'x' if sim_nao_csim == 'não' else ' '} ] não
Foi enviado lista de peças? [ {'x' if sim_nao_csim_pec == 'sim' else ' '} ] sim [ {'x' if sim_nao_csim_pec == 'não' else ' '} ] não
Foi enviado ficha de clientes? [ {'x' if sim_nao_csim_ficha == 'sim' else ' '} ] sim [ {'x' if sim_nao_csim_ficha == 'não' else ' '} ] não
Tipo de portaria: {tp_portaria}
Contato do responsável (em caso de portaria remota, informar o número do apartamento ou a forma de contato do responsável): {contato_resp_port}
Particularidades do local: {part_local}
Contato atualizado do síndico: {contato_sindico}

Alteração de CNPJ ou razão social? [ {'x' if sim_nao_alt == 'sim' else ' '} ] sim [ {'x' if sim_nao_alt == 'não' else ' '} ] não
Se trata do mesmo proprietário: ( {'X' if mesmo_prop_opt == 'SIM' else ' '} ) SIM ( {'X' if mesmo_prop_opt == 'NÃO' else ' '} ) NÃO
Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto: ( {'X' if neg_tit_opt == 'SIM' else ' '} ) SIM ( {'X' if neg_tit_opt == 'NÃO' else ' '} ) NÃO;

Projeto (Informe o número completo do projeto): {projeto_alt}

Redução de vigência? [ {'x' if sim_nao_red_vig == 'sim' else ' '} ] sim [ {'x' if sim_nao_red_vig == 'não' else ' '} ] não
(Se sim, descreva o motivo): {motivo_red_vig}"""

            st.success("✅ Texto de Aprovação gerado com sucesso! Copie abaixo:")
            botao_copiar_customizado(texto_aprovacao, "aprovacao_txt")


# =====================================================================
# TELA 4: ANIVERSÁRIO DE CONTRATO
# =====================================================================
elif menu == "🎂 Aniversário de Contrato":
    rca = st.session_state.reset_counter_aniv

    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=150)
    with col_titulo:
        st.title("Aniversário de Contrato")
        st.markdown("Tratativa de reajuste por IPCA acumulado de 12 meses.")

    st.divider()

    # Consulta dinâmica e atualizada do IPCA oficial do IBGE
    ipca_vigente = obter_ipca_acumulado_12m()
    st.info(f"📊 **IPCA Acumulado de 12 meses (Consultado em tempo real no IBGE):** {ipca_vigente:.2f}%")

    col_an1, col_an2 = st.columns(2)
    with col_an1:
        preco_anterior_input = st.text_input("Preço Anterior (R$)", placeholder="Ex: 6,9789", key=f"preco_ant_{rca}")
    with col_an2:
        st.write("")

    st.markdown("Cliente possui cláusula em contrato?")
    clausula_contrato = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, index=0, label_visibility="collapsed", key=f"clausula_{rca}")

    st.divider()

    # Cálculo dinâmico do preço aniversário utilizando o IPCA atual
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
        botao_copiar_customizado(texto_aniversario, "aniversario_txt")

    st.divider()

    # --- CAMPO DE C.I. E BOTÃO ADICIONAL ---
    st.subheader("Tratativa com C.I.")
    ci_input = st.text_input("Número da C.I.", placeholder="Ex: 588.386.687", key=f"ci_num_{rca}")

    if st.button("📝 Gerar Texto com C.I.", type="primary"):
        texto_ci = f"""Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%."""

        if clausula_contrato == "Sim":
            texto_ci += "\n\nCliente possui cláusula em contrato."

        texto_ci += f"""

Preço anterior: R$ {preco_anterior_input if preco_anterior_input else 'xx,xx'}
Preço Aniversário: R$ {p_aniv_str}

CI.: {ci_input if ci_input else '000.000.000'} - Preço Aniversário"""

        st.success("✅ Texto com C.I. gerado com sucesso! Copie abaixo:")
        botao_copiar_customizado(texto_ci, "ci_txt")
