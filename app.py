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

# --- FUNÇÃO DE CONSULTA AUTOMÁTICA DE CNPJ E INSCRIÇÃO ESTADUAL ---
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
            st.code(texto_final, language="text")


# =====================================================================
# TELA 2: ELABORAÇÃO DE CONTRATO
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

    st.divider()

    # --- TEMA 1: MOTIVO ---
    st.subheader("1. Motivo")
    motivo_solicitacao = st.text_input("Motivo da solicitação", placeholder="Ex: Alteração de CNPJ + Reneg de Preço")

    st.divider()

    # --- TEMA 2: DADOS DO CLIENTE ---
    st.subheader("2. Dados do Cliente")
    col_cli1, col_cli2, col_cli3 = st.columns(3)
    with col_cli1:
        contato_contrato = st.text_input("Contato", placeholder="Ex: Sidnei")
    with col_cli2:
        telefone_contrato = st.text_input("Telefone", placeholder="Ex: 11 99157-0730")
    with col_cli3:
        email_contrato = st.text_input("E-mail", placeholder="Ex: adm@grscondominios.com.br")

    st.divider()

    # --- TEMA 3: SOLICITAÇÃO ---
    st.subheader("3. Solicitação")
    tipo_contrato = st.radio("Contrato / Aditamento / Distrato", ["Contrato", "Aditamento", "Distrato"], horizontal=True, index=None)

    st.divider()

    # --- TEMA 4: DADOS DO CONTRATO ---
    st.subheader("4. Dados do Contrato")
    col_con1, col_con2 = st.columns(2)
    
    # Variáveis globais de controle para preenchimento/consulta
    cnpj_campo_val, ie_campo_val = "", ""
    status_cnpj_txt, razao_social_txt, ie_consultada = "", "", ""
    uf_selecionada = ""

    estados_brasil = [
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", 
        "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", 
        "RS", "RO", "RR", "SC", "SP", "SE", "TO"
    ]

    with col_con1:
        endereco_padrao = st.text_input("Endereço padrão ou entrega?", placeholder="Ex: Padrão + ENTREGA1")
        mesmo_prop = st.radio("Mesmo proprietário?", ["Sim", "Não"], horizontal=True, index=None)
        mesmo_cnpj = st.radio("Mesmo CNPJ?", ["Sim", "Não"], horizontal=True, index=None)
        
        # Campo de seleção de Estado (UF)
        uf_selecionada = st.selectbox("Estado (UF)", estados_brasil, index=estados_brasil.index("SP") if "SP" in estados_brasil else 0)

        # Consulta automática via API do CNPJ (puxa dados da empresa e tenta capturar a Inscrição Estadual federal se disponível)
        cnpj_input_temp = st.text_input("CNPJ (Digite para consultar)", placeholder="Ex: 58.582.414/0001-56")
        
        if len("".join(filter(str.isdigit, str(cnpj_input_temp)))) == 14:
            dados_api = consultar_cnpj_api(cnpj_input_temp)
            if dados_api:
                razao_social_txt = dados_api.get("razao_social", "Não encontrada")
                situacao_cad = dados_api.get("situacao_cadastral", "")
                if situacao_cad == 2 or str(situacao_cad).upper() == "ATIVA":
                    status_cnpj_txt = "Ativo"
                else:
                    status_cnpj_txt = f"Inativa ({situacao_cad})"
                
                # Tenta extrair a Inscrição Estadual caso a API retorne nos dados estaduais do estabelecimento
                estab = dados_api.get("estabelecimento", {})
                regs_estaduais = estab.get("inscricoes_estaduais", [])
                if regs_estaduais:
                    for reg in regs_estaduais:
                        if reg.get("estado", {}).get("sigla") == uf_selecionada and reg.get("ativo"):
                            ie_consultada = reg.get("inscricao_estadual", "")
                            break

                st.markdown(f"✅ **Razão Social:** {razao_social_txt}")
                st.markdown(f"🟢 **Status CNPJ:** {status_cnpj_txt}")
                if ie_consultada:
                    st.markdown(f"🔵 **I.E. Encontrada ({uf_selecionada}):** {ie_consultada}")
            else:
                st.warning("⚠️ CNPJ não encontrado ou erro na consulta automática.")

        # Lógica dinâmica para exibição dos campos de CNPJ / IE conforme a escolha
        if mesmo_cnpj == "Sim":
            cnpj_campo_val = st.text_input("CNPJ (Confirmação)", value=cnpj_input_temp, placeholder="Ex: 58.582.414/0001-56")
            ie_campo_val = st.text_input("I.E.", value=ie_consultada, placeholder="Ex: Digite ou cole a Inscrição Estadual")
        elif mesmo_cnpj == "Não":
            cnpj_campo_val = st.text_input("Novo CNPJ", value=cnpj_input_temp, placeholder="Ex: 58.582.414/0001-56")
            ie_campo_val = st.text_input("Nova I.E.", value=ie_consultada, placeholder="Ex: Digite ou cole a Inscrição Estadual")
        else:
            cnpj_campo_val = cnpj_input_temp
            ie_campo_val = ie_consultada

    with col_con2:
        cond_pagamento = st.text_input("Condição de pagamento", placeholder="Ex: 14 dias")
        vigencia = st.text_input("Vigência", placeholder="Ex: 60 meses")
        equipamentos_contrato = st.text_input("Equipamentos", placeholder="Ex: 01 b190 + 01 CC")

    st.divider()

    # --- TEMA 5: COMODATO / FORNECIMENTO ---
    st.subheader("5. Comodato / Fornecimento")
    tipo_fornecimento = st.multiselect("Tipo de Fornecimento", ["Granel", "Cilindro"])
    
    preco_granel = ""
    consumo_granel = ""
    if "Granel" in tipo_fornecimento:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            preco_granel = st.text_input("Preço Granel", placeholder="Ex: 7,50")
        with col_g2:
            consumo_granel = st.text_input("Consumo previsto (Granel) mensal", placeholder="Ex: 100 kgs")
        
    preco_cilindro_str = ""
    consumo_cilindro_total = 0
    p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
    p13_val, p20_val, p45_val = "", "", ""
    
    if "Cilindro" in tipo_fornecimento:
        st.markdown("**Preços e Quantidades por Modelo de Cilindro:**")
        col_c_mod1, col_c_mod2 = st.columns(2)
        with col_c_mod1:
            p13_qtd = st.number_input("Qtd Cilindros P13", min_value=0, value=0, step=1)
        with col_c_mod2:
            p13_val = st.text_input("Preço P13 (/und)", placeholder="xx,xx")
            
        col_c_mod3, col_c_mod4 = st.columns(2)
        with col_c_mod3:
            p20_qtd = st.number_input("Qtd Cilindros P20", min_value=0, value=0, step=1)
        with col_c_mod4:
            p20_val = st.text_input("Preço P20 (/und)", placeholder="xx,xx")
            
        col_c_mod5, col_c_mod6 = st.columns(2)
        with col_c_mod5:
            p45_qtd = st.number_input("Qtd Cilindros P45", min_value=0, value=0, step=1)
        with col_c_mod6:
            p45_val = st.text_input("Preço P45 (/und)", placeholder="xx,xx")
        
        preco_cilindro_str = f"[P13 = {p13_val} / und] [P20 = {p20_val} / und] [P45 = {p45_val} / und]"
        consumo_cilindro_total = (p13_qtd * 13) + (p20_qtd * 20) + (p45_qtd * 45)

    st.divider()

    # --- TEMA 6: FINANCEIRO ---
    st.subheader("6. Financeiro")
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        possui_debito_fin = st.radio("Cliente possui débitos?", ["Não", "Sim"], horizontal=True, index=0)
        resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", placeholder="Ex: n/a")
    with col_fin2:
        email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato", placeholder="Ex: N/A")

    if tipo_fluxo == "Enviar para Assinatura":
        st.markdown("---")
        st.markdown("### Dados de Assinatura e Testemunhas")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            nome_testemunha = st.text_input("Nome da Testemunha", placeholder="")
            email_testemunha = st.text_input("E-mail da Testemunha", placeholder="")
        with col_a2:
            nome_responsavel = st.text_input("Nome do Responsável pela assinatura", placeholder="")
            email_responsavel = st.text_input("E-mail do Responsável pela assinatura", placeholder="")
    else:
        nome_testemunha = ""
        email_testemunha = ""
        nome_responsavel = ""
        email_responsavel = ""

    st.divider()

    # --- TEMA 7: CONTA SIM ---
    st.subheader("7. Condomínio CONTA SIM")
    conta_sim = st.radio("Condomínio CONTA SIM?", ["Não", "Sim"], horizontal=True, index=0)

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
Contrato / Aditamento / Distrato: {tipo_contrato if tipo_contrato else ''}
Mesmo proprietário?: {mesmo_prop if mesmo_prop else ''}
Mesmo CNPJ?: {mesmo_cnpj if mesmo_cnpj else ''}
Estado (UF): {uf_selecionada}"""

        if mesmo_cnpj == "Sim":
            texto_padrao_contrato += f"""
CNPJ: {cnpj_campo_val}
I.E.: {ie_campo_val}"""
        elif mesmo_cnpj == "Não":
            texto_padrao_contrato += f"""
Novo CNPJ: {cnpj_campo_val}
Nova I.E.: {ie_campo_val}"""

        if razao_social_txt:
            texto_padrao_contrato += f"\nRazão Social (Consultada): {razao_social_txt}"
        if status_cnpj_txt:
            texto_padrao_contrato += f"\nStatus CNPJ: {status_cnpj_txt}"

        texto_padrao_contrato += f"""
Endereço padrão ou entrega?: {endereco_padrao}"""

        if "Granel" in tipo_fornecimento:
            texto_padrao_contrato += f"\nPreço Granel: {preco_granel} /kg"
            
        if "Cilindro" in tipo_fornecimento:
            texto_padrao_contrato += f"\nPreço Cilindro: {preco_cilindro_str}"

        texto_padrao_contrato += f"""
Condição de pagamento: {cond_pagamento}"""

        if "Granel" in tipo_fornecimento:
            texto_padrao_contrato += f"\nConsumo previsto (Granel) mensal: {consumo_granel}"
            
        if "Cilindro" in tipo_fornecimento:
            texto_padrao_contrato += f"\nQual consumo previsto (Cilindro) mensal: {consumo_cilindro_total} kgs"

        texto_padrao_contrato += f"""
Vigência: {vigencia}
Equipamentos: {equipamentos_contrato}

Cliente possui débitos?: {possui_debito_fin}
Quem será o responsável pelas NF's pendentes? {resp_pendentes}
E-mail do novo proprietário que receberá o novo contrato: {email_novo_prop}

Nome da Testemunha: {nome_testemunha}
E-mail da Testemunha: {email_testemunha}
Nome do Responsável pela assinatura: {nome_responsavel}
E-mail do Responsável pela assinatura: {email_responsavel}

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
