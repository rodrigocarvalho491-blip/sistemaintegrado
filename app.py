import os
import re
import uuid
import base64
import html as html_lib
import json
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
import tempfile

--- FORÇAR TEMA CLARO GLOBALMENTE NO STREAMLIT ---

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

--- CONFIGURAÇÃO GLOBAL DA PÁGINA ---

st.set_page_config(
page_title="Sistema Integrado Consigaz",
page_icon="⚙️",
layout="wide",
initial_sidebar_state="expanded"
)

--- CONEXÃO COM O SUPABASE ---

from supabase import create_client, Client

@st.cache_resource
def init_supabase() -> Client:
try:
url = st.secrets["supabase"]["URL"]
key = st.secrets["supabase"]["KEY"]
return create_client(url, key)
except Exception as e:
st.error(f"❌ Erro ao conectar ao banco de dados Supabase: {e}")
st.stop()

supabase = init_supabase()

--- CAMADA DE PERSISTÊNCIA NA NUVEM (SUPABASE) ---

def carregar_banco_usuarios():
try:
res = supabase.table("usuarios").select("*").execute()
dados = {}
for row in res.data:
dados[row["usuario"]] = {
"senha": row["senha"],
"nivel_acesso": row.get("nivel_acesso", "convencional"),
"precisa_trocar_senha": row.get("precisa_trocar_senha", False)
}

    if "admin" not in dados:
        supabase.table("usuarios").insert({
            "usuario": "admin", 
            "senha": "admin", 
            "nivel_acesso": "admin", 
            "precisa_trocar_senha": False
        }).execute()
        dados["admin"] = {"senha": "admin", "nivel_acesso": "admin", "precisa_trocar_senha": False}
    return dados
except Exception as e:
    st.error(f"Erro ao carregar usuários: {e}")
    return {"admin": {"senha": "admin", "nivel_acesso": "admin", "precisa_trocar_senha": False}}


def salvar_usuario(usuario, senha, nivel_acesso="convencional", precisa_trocar=False):
try:
payload = {
"usuario": usuario,
"senha": senha,
"nivel_acesso": nivel_acesso,
"precisa_trocar_senha": precisa_trocar
}
supabase.table("usuarios").upsert(payload).execute()
return True
except Exception as e:
st.error(f"Erro ao salvar usuário: {e}")
return False

def remover_usuario(usuario):
try:
supabase.table("usuarios").delete().eq("usuario", usuario).execute()
supabase.table("notas").delete().eq("usuario", usuario).execute()
supabase.table("acompanhamento").delete().eq("usuario", usuario).execute()
return True
except Exception as e:
st.error(f"Erro ao remover usuário: {e}")
return False

def carregar_banco_notas(usuario):
try:
res = supabase.table("notas").select("*").eq("usuario", usuario).execute()
notas = {}
for row in res.data:
notas[row["id"]] = {
"titulo": row["titulo"],
"cliente": row["cliente"],
"texto": row["texto"],
"data_modificacao": row["data_modificacao"]
}
return notas
except Exception as e:
st.error(f"Erro ao carregar notas: {e}")
return {}

def salvar_nota(nota_id, usuario, titulo, cliente, texto):
try:
data_mod = datetime.now().strftime("%d/%m/%Y %H:%M")
payload = {
"id": nota_id,
"usuario": usuario,
"titulo": titulo,
"cliente": cliente,
"texto": texto,
"data_modificacao": data_mod
}
supabase.table("notas").upsert(payload).execute()
return True
except Exception as e:
st.error(f"Erro ao salvar nota: {e}")
return False

def apagar_nota(nota_id):
try:
supabase.table("notas").delete().eq("id", nota_id).execute()
return True
except Exception as e:
st.error(f"Erro ao apagar nota: {e}")
return False

def carregar_acompanhamento(usuario, tipo):
try:
res = supabase.table("acompanhamento").select("*").eq("usuario", usuario).eq("tipo", tipo).execute()
dados = {}
for row in res.data:
dados[row["id"]] = row
return dados
except Exception:
return {}

def salvar_acompanhamento(id_reg, usuario, tipo, codigo_cliente, nome_cliente, status, ano, mes, observacoes=""):
data_mod = datetime.now().strftime("%d/%m/%Y %H:%M")
payload = {
"id": id_reg,
"usuario": usuario,
"tipo": tipo,
"codigo_cliente": codigo_cliente,
"nome_cliente": nome_cliente,
"status": status,
"ano": ano,
"mes": mes,
"observacoes": observacoes,
"data_modificacao": data_mod
}
try:
supabase.table("acompanhamento").upsert(payload).execute()
return True
except Exception as e:
err_str = str(e)
if "42501" in err_str or "row-level security" in err_str.lower():
st.error("❌ Permissão bloqueada no Supabase (RLS ativo). Execute no SQL Editor: ALTER TABLE acompanhamento DISABLE ROW LEVEL SECURITY;")
return False
try:
payload_fallback = {k: v for k, v in payload.items() if k not in ["observacoes", "nome_cliente"]}
supabase.table("acompanhamento").upsert(payload_fallback).execute()
return True
except Exception as e2:
st.error(f"Erro ao salvar acompanhamento: {e2}")
return False

def apagar_acompanhamento(id_reg):
try:
supabase.table("acompanhamento").delete().eq("id", id_reg).execute()
return True
except Exception:
return False

--- CONSULTA CNPJ & IPCA ---

@st.cache_data(ttl=3600)
def consultar_cnpj_api(cnpj):
try:
cnpj_limpo = "".join(filter(str.isdigit, str(cnpj)))
if len(cnpj_limpo) == 14:
url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
resp = requests.get(url, timeout=5)
if resp.status_code == 200:
dados = resp.json()
return {
"razao_social": dados.get("razao_social") or dados.get("nome_fantasia", ""),
"situacao_cadastral": dados.get("descricao_situacao_cadastral", "ATIVA")
}
except Exception:
pass
return None

@st.cache_data(ttl=1800, show_spinner=False)
def obter_ipca_acumulado_12m():
try:
url = "https://www.ibge.gov.br/explica/inflacao.php"
headers = {"User-Agent": "Mozilla/5.0"}
resp = requests.get(url, headers=headers, timeout=5)
if resp.status_code == 200:
match = re.search(r'IPCA\s+acumulado\s+de\s+12\s+meses.?([0-9]+,[0-9]+)%\s([A-Za-z]+/[0-9]{4})', resp.text, re.IGNORECASE | re.DOTALL)
if match:
val = float(match.group(1).replace(",", "."))
periodo = match.group(2).title()
return val, periodo
except Exception:
pass
return 4.63, "Out/2026 (Referência Oficial)"

def formatar_ci_num(ci_str):
digits = re.sub(r'\D', '', str(ci_str))
if len(digits) == 9:
return f"{digits[:3]}.{digits[3:6]}.{digits[6:]}"
elif len(digits) == 11:
return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}"
elif digits:
return ci_str.strip()
return "000.000.000"

def extrair_dois_primeiros_nomes(nome):
if not nome:
return ""
palavras = str(nome).strip().split()
validas = []
for p in palavras:
if not p.isdigit():
validas.append(p)
if len(validas) == 2:
break
if not validas and palavras:
return palavras[0]
return " ".join(validas)

--- LEITOR ROBUSTO DE ARQUIVOS (EXCEL / HTML) ---

def ler_arquivo_excel_robusto(uploaded_file):
bytes_data = uploaded_file.getvalue()
try:
return pd.read_excel(BytesIO(bytes_data))
except Exception:
pass
try:
try:
html_text = bytes_data.decode('utf-8')
except UnicodeDecodeError:
html_text = bytes_data.decode('ISO-8859-1', errors='ignore')
import re
table_match = re.search(r'<table[^>]>(.?)', html_text, re.DOTALL | re.IGNORECASE)
if not table_match:
raise ValueError("Nenhuma tabela HTML encontrada.")
table_content = table_match.group(1)
rows = []
for row_match in re.finditer(r'<tr[^>]>(.?)', table_content, re.DOTALL | re.IGNORECASE):
row_content = row_match.group(1)
cells = []
for cell_match in re.finditer(r'<t[dh][^>]>(.?)</t[dh]>', row_content, re.DOTALL | re.IGNORECASE):
cell_text = cell_match.group(1)
cell_text = re.sub(r'<[^>]+>', '', cell_text)
cell_text = cell_text.replace(' ', ' ').replace('&', '&').replace('<', '<').replace('>', '>')
cells.append(cell_text.strip())
if cells:
rows.append(cells)
if not rows:
raise ValueError("Tabela HTML extraída está vazia.")
max_cols = max(len(r) for r in rows)
header = rows[0]
if len(header) < max_cols:
header.extend([f"Col_{i}" for i in range(len(header), max_cols)])
data_rows = []
for r in rows[1:]:
if len(r) < max_cols:
r.extend([""] * (max_cols - len(r)))
elif len(r) > max_cols:
r = r[:max_cols]
data_rows.append(r)
return pd.DataFrame(data_rows, columns=header)
except Exception as e:
raise ValueError(f"Formato não suportado: {e}")

--- GERADOR DE PDF DE RELATÓRIO FOTOGRÁFICO ---

class RelatorioPDF(FPDF):
def init(self, cod_cliente="", nome_cliente="", logo_path=""):
super().init()
self.cod_cliente = cod_cliente.replace(".", "").strip().upper() if cod_cliente else ""
self.nome_cliente = nome_cliente.strip().upper() if nome_cliente else ""
self.logo_path = logo_path

def header(self):
    if self.logo_path and os.path.exists(self.logo_path):
        self.image(self.logo_path, x=10, y=8, w=45)
        
    if self.page_no() == 1:
        self.set_y(10)
        self.set_font("Arial", "B", 14)
        self.set_x(60)
        self.cell(140, 8, "RELATÓRIO FOTOGRÁFICO", align="C", ln=1)
        
        info_cabecalho = f"{self.cod_cliente} | {self.nome_cliente}".strip(" |")
        if info_cabecalho:
            self.set_font("Arial", "B", 10)
            self.set_x(60)
            self.cell(140, 6, info_cabecalho, align="C", ln=1)
        
        self.set_y(35)
    else:
        self.set_y(25)

def footer(self):
    self.set_y(-15)
    self.set_font("Arial", "I", 8)
    self.cell(0, 10, f"Página {self.page_no()}", align="C")


--- ESTILOS CSS VISUAIS & MENU SUPERIOR FIXO ---

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(file))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")

CUSTOM_CSS = """

"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def botao_copiar_customizado(texto_para_copiar, chave_unica, label_btn="📄 Copiar Texto Completo"):
texto_js = json.dumps(str(texto_para_copiar))
component_html = f"""

{label_btn}
Copiado com sucesso!


function copiarTexto_{chave_unica}() {{
const texto = {texto_js};
navigator.clipboard.writeText(texto).then(function() {{
const msg = document.getElementById("msg_{chave_unica}");
msg.style.display = "inline";
setTimeout(function() {{ msg.style.display = "none"; }}, 2500);
}}).catch(err => console.error('Erro ao copiar', err));
}}

"""
components.html(component_html, height=50)

@st.cache_data(show_spinner=False)
def _logo_base64(caminho):
try:
with open(caminho, "rb") as f:
return base64.b64encode(f.read()).decode("ascii")
except Exception:
return ""

def _logo_html(classe_img, classe_wrapper=""):
b64 = _logo_base64(LOGO_PATH)
if not b64: return ""
img_tag = f''
return f'{img_tag}' if classe_wrapper else img_tag

def cabecalho_pagina(titulo, subtitulo):
logo = _logo_html("cg-logo", "cg-logo-wrapper")
separador = '' if logo else ""
st.markdown(
f'{logo}{separador}'
f'{html_lib.escape(titulo)}'
f'{html_lib.escape(subtitulo)}'
f'',
unsafe_allow_html=True,
)

--- PAINEL KANBAN (CONTRATOS E VENDAS) ---

def renderizar_painel_acompanhamento(tipo_acompanhamento, lista_status, dict_cores):
usuario = st.session_state.usuario_atual
dados = carregar_acompanhamento(usuario, tipo_acompanhamento)
meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

if f"edit_id_{tipo_acompanhamento}" not in st.session_state:
    st.session_state[f"edit_id_{tipo_acompanhamento}"] = None

col_menu_ac, col_conteudo_ac = st.columns([1, 4])

with col_menu_ac:
    st.markdown("### 📌 Filtros")
    ano_selecionado = st.selectbox("📅 Selecione o Ano", [2024, 2025, 2026, 2027, 2028], index=2, key=f"ano_sel_{tipo_acompanhamento}")
    filtro_status = st.selectbox("🏷️ Filtrar por Status", ["Todos"] + lista_status, key=f"filtro_st_{tipo_acompanhamento}")
    
    st.divider()
    st.markdown("### 🚦 Legenda de Status")
    for st_name in lista_status:
        cor = dict_cores.get(st_name, "⚪")
        st.markdown(f"{cor} **{st_name}**")

with col_conteudo_ac:
    id_editando = st.session_state[f"edit_id_{tipo_acompanhamento}"]
    if id_editando and id_editando in dados:
        d_edit = dados[id_editando]
        st.markdown("### ✏️ Edição de Cliente")
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 3, 3])
            with c1: ed_cod = st.text_input("Código do Cliente", value=d_edit['codigo_cliente'], key=f"ed_cod_{tipo_acompanhamento}")
            with c2: ed_nome = st.text_input("Nome do Cliente", value=d_edit.get('nome_cliente', ''), key=f"ed_nom_{tipo_acompanhamento}")
            with c3: 
                idx_st = lista_status.index(d_edit['status']) if d_edit['status'] in lista_status else 0
                ed_status = st.selectbox("Status", lista_status, index=idx_st, key=f"ed_st_{tipo_acompanhamento}")
            
            c4, c5 = st.columns([2, 6])
            with c4: 
                idx_ms = d_edit['mes'] - 1 if 1 <= d_edit['mes'] <= 12 else 0
                ed_mes = st.selectbox("Mês de Alocação", meses_nomes, index=idx_ms, key=f"ed_ms_{tipo_acompanhamento}")
            with c5: ed_obs = st.text_input("Observações", value=d_edit.get('observacoes', ''), key=f"ed_obs_{tipo_acompanhamento}")
            
            b1, b2, b3, _ = st.columns([2, 2, 2, 4])
            if b1.button("💾 Salvar Alterações", type="primary", use_container_width=True, key=f"ed_salv_{tipo_acompanhamento}"):
                if salvar_acompanhamento(id_editando, usuario, tipo_acompanhamento, ed_cod.strip(), ed_nome.strip(), ed_status, d_edit['ano'], meses_nomes.index(ed_mes) + 1, ed_obs):
                    st.session_state[f"edit_id_{tipo_acompanhamento}"] = None
                    st.rerun()
            if b2.button("❌ Cancelar", use_container_width=True, key=f"ed_canc_{tipo_acompanhamento}"):
                st.session_state[f"edit_id_{tipo_acompanhamento}"] = None
                st.rerun()
            if b3.button("🗑️ Excluir Cliente", use_container_width=True, key=f"ed_del_{tipo_acompanhamento}"):
                apagar_acompanhamento(id_editando)
                st.session_state[f"edit_id_{tipo_acompanhamento}"] = None
                st.rerun()
        st.divider()

    with st.expander("➕ Adicionar Novo Cliente", expanded=False):
        c_cod, c_nom, c_st, c_mes = st.columns([2, 3, 3, 2])
        with c_cod: novo_cod = st.text_input("Código", key=f"n_cod_{tipo_acompanhamento}")
        with c_nom: novo_nome = st.text_input("Nome do Cliente", key=f"n_nom_{tipo_acompanhamento}")
        with c_st: novo_st = st.selectbox("Status Inicial", lista_status, key=f"n_st_{tipo_acompanhamento}")
        with c_mes: novo_ms = st.selectbox("Mês de Alocação", meses_nomes, key=f"n_ms_{tipo_acompanhamento}")

        c_obs, c_btn = st.columns([5, 1])
        with c_obs: novo_obs = st.text_input("Observações", placeholder="Detalhes ou anotações...", key=f"n_obs_{tipo_acompanhamento}")
        with c_btn:
            st.write(""); st.write("")
            if st.button("Adicionar", key=f"btn_add_{tipo_acompanhamento}", type="primary", use_container_width=True):
                if novo_cod.strip() and novo_nome.strip():
                    novo_id = str(uuid.uuid4())
                    if salvar_acompanhamento(novo_id, usuario, tipo_acompanhamento, novo_cod.strip(), novo_nome.strip(), novo_st, ano_selecionado, meses_nomes.index(novo_ms) + 1, novo_obs.strip()):
                        st.rerun()
                else:
                    st.warning("⚠️ Informe o código e o nome do cliente.")

    st.divider()

    cols = st.columns(12)
    for i, mes in enumerate(meses_nomes):
        with cols[i]:
            st.markdown(f"<div style='text-align:center; font-weight:bold; color:#0055A5; border-bottom:2px solid #0055A5; margin-bottom:10px; font-size:13px;'>{mes}</div>", unsafe_allow_html=True)
            for id_reg, d in dados.items():
                if not isinstance(d, dict): continue
                if d['ano'] == ano_selecionado and d['mes'] == (i + 1):
                    if filtro_status != "Todos" and d['status'] != filtro_status:
                        continue
                    
                    cor_status = dict_cores.get(d['status'], "⚪")
                    nome_cliente_raw = d.get('nome_cliente', '')
                    dois_nomes = extrair_dois_primeiros_nomes(nome_cliente_raw)

                    texto_botao = f"{cor_status} {d['codigo_cliente']}\n{dois_nomes}"
                        
                    if st.button(texto_botao, key=f"card_edit_{id_reg}", use_container_width=True, help="Clique para exibir e editar"):
                        st.session_state[f"edit_id_{tipo_acompanhamento}"] = id_reg
                        st.rerun()


--- ESTADOS DE SESSÃO ---

if "autenticado" not in st.session_state: st.session_state.autenticado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "e_admin" not in st.session_state: st.session_state.e_admin = False
if "e_supervisor" not in st.session_state: st.session_state.e_supervisor = False
if "troca_obrigatoria" not in st.session_state: st.session_state.troca_obrigatoria = False
if "filtro_dashboard_ativo" not in st.session_state: st.session_state.filtro_dashboard_ativo = "Todas"
if "ultimo_usuario_logado" not in st.session_state: st.session_state.ultimo_usuario_logado = ""
if "df_excel_agenda" not in st.session_state: st.session_state.df_excel_agenda = None

if "equipamentos" not in st.session_state: st.session_state.equipamentos = []
if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0
if "reset_counter_contrato" not in st.session_state: st.session_state.reset_counter_contrato = 0
if "reset_counter_fc" not in st.session_state: st.session_state.reset_counter_fc = 0

banco_usuarios = carregar_banco_usuarios()

if not st.session_state.autenticado:
side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
st.sidebar.markdown(
f'{side_logo_html}'
f'Sistema Integrado',
unsafe_allow_html=True,
)

st.title("🔐 Acesso ao Sistema Integrado | Consigaz")
st.markdown("Insira suas credenciais para acessar a plataforma.")

with st.form("form_login_sistema"):
    usuario_input = st.text_input("Usuário").strip().lower()
    senha_input = st.text_input("Senha", type="password", placeholder="••••••••").strip()
    btn_entrar = st.form_submit_button("Entrar no Sistema", type="primary")
    
    if btn_entrar:
        if usuario_input in banco_usuarios and banco_usuarios[usuario_input]["senha"] == senha_input:
            usr_data = banco_usuarios[usuario_input]
            st.session_state.autenticado = True
            st.session_state.usuario_atual = usuario_input
            nivel_acc = usr_data["nivel_acesso"]
            st.session_state.e_admin = (nivel_acc == "admin")
            st.session_state.e_supervisor = (nivel_acc == "supervisor")
            st.session_state.troca_obrigatoria = usr_data["precisa_trocar_senha"] or (senha_input == "123456")
            
            if st.session_state.ultimo_usuario_logado != usuario_input:
                st.session_state.df_excel_agenda = None
                st.session_state.ultimo_usuario_logado = usuario_input
            st.rerun()
        else:
            st.error("❌ Usuário ou senha incorretos!")
st.stop()


if st.session_state.troca_obrigatoria:
cabecalho_pagina("🔑 Alteração Obrigatória de Senha", "Sua conta utiliza senha temporária. Defina sua nova senha pessoal.")
with st.form("form_troca_senha_obrigat"):
nova_s1 = st.text_input("Nova Senha Pessoal *", type="password").strip()
nova_s2 = st.text_input("Confirme a Nova Senha *", type="password").strip()
btn_mudar_obrigat = st.form_submit_button("🔒 Salvar Nova Senha e Acessar", type="primary")

    if btn_mudar_obrigat:
        if not nova_s1 or not nova_s2:
            st.error("⚠️ Preencha ambos os campos de senha.")
        elif nova_s1 == "123456":
            st.error("⚠️ Escolha uma senha diferente da inicial '123456'.")
        elif nova_s1 != nova_s2:
            st.error("⚠️ As senhas digitadas não conferem.")
        else:
            curr_u = st.session_state.usuario_atual
            curr_nivel = banco_usuarios[curr_u]["nivel_acesso"]
            if salvar_usuario(curr_u, nova_s1, nivel_acesso=curr_nivel, precisa_trocar=False):
                st.session_state.troca_obrigatoria = False
                st.success("✅ Senha alterada com sucesso!")
                st.rerun()
st.stop()


--- NAVEGAÇÃO SUPERIOR ---

side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
st.sidebar.markdown(
f'{side_logo_html}'
f'Central de Atendimentos',
unsafe_allow_html=True,
)

st.sidebar.markdown(f"👤 Usuário Ativo: {st.session_state.usuario_atual}")
if st.session_state.e_admin: st.sidebar.caption("⭐ Perfil: Administrador")
elif st.session_state.e_supervisor: st.sidebar.caption("📊 Perfil: Supervisor")

if st.session_state.e_admin:
lista_abas = ["⚙️ Painel Admin"]
else:
lista_abas = [
"🛠️ Tratativa de Ocorrências",
"📊 Agenda de Ocorrências",
"📄 Status de Contratos",
"💰 Status de Vendas",
"📓 Bloco de Notas Pessoal"
]
if st.session_state.e_supervisor:
lista_abas.append("⚙️ Painel Admin")

abas_sistema = st.tabs(lista_abas)

if st.session_state.e_admin:
aba_admin = abas_sistema[0]
aba_tratativa = aba_agenda = aba_contratos = aba_vendas = aba_notas = None
else:
aba_tratativa = abas_sistema[0]
aba_agenda = abas_sistema[1]
aba_contratos = abas_sistema[2]
aba_vendas = abas_sistema[3]
aba_notas = abas_sistema[4]
aba_admin = abas_sistema[5] if st.session_state.e_supervisor else None

if "nota_selecionada_id" not in st.session_state: st.session_state.nota_selecionada_id = None

=====================================================================

ABA 1: TRATATIVA DE OCORRÊNCIAS

=====================================================================

if aba_tratativa is not None:
with aba_tratativa:
col_menu, col_conteudo = st.columns([1, 4])

    with col_menu:
        st.markdown("### 📌 Módulos de Tratativa")
        menu_tratativa = st.radio(
            "Selecione a operação:", 
            [
                "📷 Visita de Transferência",
                "📝 Elaboração de Contrato",
                "📋 Aprovação de Contrato",
                "🎂 Aniversário de Contrato",
                "🗂️ Ficha de Cliente"
            ],
            label_visibility="collapsed"
        )
            
    with col_conteudo:
        rc = st.session_state.reset_counter

        # 1. VISITA DE TRANSFERÊNCIA
        if menu_tratativa == "📷 Visita de Transferência":
            cabecalho_pagina("Visita de Transferência & Relatório Técnico", "Gerador automatizado de relatórios técnicos, formulários e inspeções fotográficas.")
            
            if st.button("🔄 Novo Cliente", key=f"btn_novo_vis_{rc}"):
                st.session_state.reset_counter += 1
                st.session_state.equipamentos = []
                st.rerun()

            st.divider()
            st.subheader("1. Identificação do Cliente")
            c1, c2, c3 = st.columns(3)
            with c1: cod_cliente = st.text_input("Código do Cliente *", key=f"vis_cod_{rc}")
            with c2: nome_cliente = st.text_input("Nome / Razão Social *", key=f"vis_nome_{rc}")
            with c3: telefone = st.text_input("Telefone *", key=f"vis_tel_{rc}")

            c4, c5, _ = st.columns(3)
            with c4: contato = st.text_input("Contato *", key=f"vis_cont_{rc}")
            with c5: departamento = st.text_input("Sobrenome ou Departamento *", key=f"vis_dep_{rc}")

            st.divider()
            st.subheader("2. Informações Contratuais & Centrais")
            qtd_centrais_visita = st.number_input("Quantidade de Centrais no Cliente *", min_value=1, max_value=10, value=1, step=1, key=f"vis_qtd_centrais_{rc}")
            
            eq_dict_visita = {}
            if qtd_centrais_visita == 1:
                c_eq1, c_eq2 = st.columns(2)
                with c_eq1: eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_cont_{rc}")
                with c_eq2:
                    desc_eq_contrato = st.text_input("Quais equipamentos contratados? *", key=f"desc_eq_{rc}")
                    eq_dict_visita[1] = desc_eq_contrato
            else:
                eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_cont_{rc}")
                st.markdown("**Equipamentos Contratados por Central:**")
                cols_cent = st.columns(min(int(qtd_centrais_visita), 3))
                for i in range(1, int(qtd_centrais_visita) + 1):
                    with cols_cent[(i - 1) % len(cols_cent)]:
                        eq_dict_visita[i] = st.text_input(f"Equipamentos Central {i:02d} *", key=f"desc_eq_cent_{i}_{rc}")

            c_f1, c_f2 = st.columns(2)
            with c_f1: tem_freq = st.radio("Possui programação cadastrada? *", ["Sim", "Não"], horizontal=True, index=None, key=f"tem_freq_{rc}")
            with c_f2:
                desc_freq = ""
                if tem_freq == "Sim": desc_freq = st.text_input("Qual a programação? *", key=f"desc_freq_{rc}")
                elif tem_freq == "Não": desc_freq = st.text_input("Nº OC de Cadastramento *", key=f"desc_freq_nao_{rc}")

            c_cp1, c_cp2 = st.columns(2)
            with c_cp1: consumo_previsto = st.text_input("Consumo Previsto (kg) *", key=f"cons_prev_{rc}")
            with c_cp2: consumo_real = st.text_input("Consumo Real/Médio (kg) *", key=f"cons_real_{rc}")
                
            c_art1, c_art2 = st.columns(2)
            with c_art1: possui_art = st.radio("Laudo ART emitido? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_art_{rc}")
            with c_art2:
                desc_art = ""
                if possui_art == "Sim": desc_art = st.text_input("Número da ART *", key=f"desc_art_sim_{rc}")
                elif possui_art == "Não": desc_art = st.text_input("Nº OC de Solicitação de Laudo *", key=f"desc_art_nao_{rc}")

            c_deb1, c_deb2 = st.columns(2)
            with c_deb1: possui_debitos = st.radio("Cliente possui débitos? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rc}")
            with c_deb2:
                desc_debitos = ""
                if possui_debitos == "Sim": desc_debitos = st.text_input("Detalhes dos Débitos", key=f"desc_deb_{rc}")

            c_nor1, c_nor2 = st.columns(2)
            with c_nor1: central_norma = st.radio("Central atende as normas? *", ["Sim", "Não"], horizontal=True, index=None, key=f"central_norma_{rc}")
            with c_nor2:
                desc_central_norma = ""
                if central_norma == "Não": desc_central_norma = st.text_input("Motivo Central fora de norma", key=f"desc_norma_{rc}")

            c_rep1, c_rep2 = st.columns(2)
            with c_rep1: rep2_correto = st.radio("Representante 2 está correto? *", ["Sim", "Não"], horizontal=True, index=None, key=f"rep2_{rc}")
            with c_rep2:
                desc_rep2 = ""
                if rep2_correto == "Não": desc_rep2 = st.text_input("Nº OC de Regularização", key=f"desc_rep2_{rc}")

            st.divider()
            st.subheader("3. Equipamentos Disponíveis no Cliente (Cálculo de Vazão)")
            opcoes_centrais_list = [f"Central {i:02d}" for i in range(1, int(qtd_centrais_visita) + 1)] if qtd_centrais_visita > 1 else ["Central"]
            
            c_cent_sel, c_qtd_eq, c_nome_eq, c_vaz_eq, c_btn_eq = st.columns([2, 1, 3, 2, 1])
            with c_cent_sel: central_dest = st.selectbox("Central", opcoes_centrais_list, key=f"sel_cent_dest_{rc}")
            with c_qtd_eq: qtd_eq_add = st.number_input("Qtd", min_value=1, value=1, step=1, key=f"qtd_eq_add_{rc}")
            with c_nome_eq: nome_eq_add = st.text_input("Equipamento", key=f"nome_eq_add_{rc}")
            with c_vaz_eq: vazao_eq_add = st.text_input("Vazão Unit. (kg/h)", key=f"vazao_eq_add_{rc}")
            with c_btn_eq:
                st.write(""); st.write("")
                if st.button("➕ Add", key=f"btn_add_eq_vis_{rc}"):
                    if nome_eq_add.strip() and vazao_eq_add.strip():
                        try:
                            v_unit = float(vazao_eq_add.replace(",", ".").lower().replace("kg/h", "").strip())
                            q_num = int(qtd_eq_add)
                            st.session_state.equipamentos.append({"central": central_dest, "qtd": q_num, "nome": nome_eq_add.strip().title(), "vazao_unit": v_unit, "vazao_total": v_unit * q_num})
                            st.rerun()
                        except ValueError:
                            st.error("Valor numérico inválido.")
                    else:
                        st.warning("Preencha nome e vazão.")

            if st.session_state.equipamentos:
                centrais_unicas = sorted(list(set([e["central"] for e in st.session_state.equipamentos])))
                vazao_geral_todas = 0.0
                for c_nome in centrais_unicas:
                    st.markdown(f"🔹 **{c_nome.upper()}**")
                    vazao_c = 0.0
                    for idx, item in enumerate(st.session_state.equipamentos):
                        if item["central"] == c_nome:
                            vazao_c += item["vazao_total"]
                            vazao_geral_todas += item["vazao_total"]
                            c_txt, c_del = st.columns([5, 1])
                            v_unit_fmt = f"{item['vazao_unit']:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                            c_txt.text(f"• {item['qtd']:02d} {item['nome']} - {v_unit_fmt} kg/h")
                            if c_del.button("❌", key=f"del_eq_{idx}_{rc}"):
                                st.session_state.equipamentos.pop(idx)
                                st.rerun()
                    st.caption(f"Vazão Subtotal {c_nome}: {vazao_c:.2f} kg/h".replace(".", ","))
                st.markdown(f"🔥 **Total - {vazao_geral_todas:.2f} kg/h**".replace(".", ","))

            st.divider()
            st.subheader("4. Novos Negócios & Satisfação")
            s3_c1, s3_c2 = st.columns(2)
            with s3_c1:
                indica_negocios = st.radio("Indicação de novos negócios? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ind_neg_{rc}")
                desc_negocios = st.text_input("Detalhes da indicação", key=f"desc_neg_{rc}") if indica_negocios == "Sim" else ""
            with s3_c2:
                cliente_satisfeito = st.radio("Cliente satisfeito com a Consigaz? *", ["Sim", "Não"], horizontal=True, index=None, key=f"cli_sat_{rc}")
                desc_satisfacao = st.text_input("Observação sobre satisfação", key=f"desc_sat_{rc}") if cliente_satisfeito else ""

            observacoes = st.text_area("Observações Gerais", key=f"obs_transf_{rc}")

            st.divider()
            st.subheader("5. Relatório Fotográfico - Upload de Imagens")
            def carregar_fotos(label, max_arquivos=None):
                fotos = st.file_uploader(label, type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_{label}_{rc}")
                if max_arquivos and fotos and len(fotos) > max_arquivos:
                    return fotos[:max_arquivos]
                return fotos

            dic_fotos_final = {}
            col_f1, col_f2 = st.columns(2)
            with col_f1: dic_fotos_final["FACHADA"] = carregar_fotos("📸 FACHADA (Até 2 fotos)", max_arquivos=2)
            with col_f2: dic_fotos_final["CILINDROS"] = carregar_fotos("📸 CILINDROS (Até 5 fotos)", max_arquivos=5)

            if qtd_centrais_visita == 1:
                c1, c2, c3 = st.columns(3)
                with c1: dic_fotos_final["ABRIGO"] = carregar_fotos("📸 ABRIGO (Até 10 fotos)", max_arquivos=10)
                with c2: dic_fotos_final["CENTRAL"] = carregar_fotos("📸 CENTRAL (Até 5 fotos)", max_arquivos=5)
                with c3: dic_fotos_final["EQUIPAMENTOS"] = carregar_fotos("📸 EQUIPAMENTOS")
            else:
                for i in range(1, int(qtd_centrais_visita) + 1):
                    st.markdown(f"**📸 FOTOS - CENTRAL {i:02d}**")
                    c1, c2, c3 = st.columns(3)
                    with c1: dic_fotos_final[f"ABRIGO CENTRAL {i:02d}"] = carregar_fotos(f"📸 ABRIGO CENTRAL {i:02d} (Até 10)", max_arquivos=10)
                    with c2: dic_fotos_final[f"CENTRAL {i:02d}"] = carregar_fotos(f"📸 CENTRAL {i:02d} (Até 5)", max_arquivos=5)
                    with c3: dic_fotos_final[f"EQUIPAMENTOS CENTRAL {i:02d}"] = carregar_fotos(f"📸 EQUIPAMENTOS CENTRAL {i:02d}")

            st.divider()
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("📝 Gerar Texto para Sistema", type="primary"):
                    linha_art = "(x) Sim ( ) Não" if possui_art == "Sim" else "( ) Sim (x) Não"
                    texto_final = f"Contato: {contato}\nSobrenome ou departamento: {departamento}\nTelefone: {telefone}\n\nEquipamentos de acordo com o contrato vigente? {eq_contrato}\nRepresentante 2 está correto? {rep2_correto}\nPossui programação cadastrada? {tem_freq}\nConsumo previsto: {consumo_previsto} kg | Consumo médio: {consumo_real} kg\nLaudo ART emitido? {linha_art}"
                    st.success("✅ Gerado com sucesso!")
                    st.text_area("Texto Gerado:", value=texto_final, height=300, key=f"txt_vis_{rc}")
                    botao_copiar_customizado(texto_final, "transf_txt")

            with col_b2:
                if st.button("📄 Gerar PDF do Relatório Fotográfico"):
                    if not cod_cliente or not nome_cliente:
                        st.error("⚠️ Preencha o Código e Nome do Cliente.")
                    else:
                        pdf = RelatorioPDF(cod_cliente=cod_cliente, nome_cliente=nome_cliente, logo_path=LOGO_PATH)
                        pdf.set_margins(10, 30, 10)
                        pdf.set_auto_page_break(auto=True, margin=20)
                        
                        is_primeira_categoria = True
                        for categoria, arquivos in dic_fotos_final.items():
                            if arquivos:
                                pdf.add_page()
                                pdf.set_font("Arial", "B", 12)
                                pdf.cell(0, 6, categoria.upper(), ln=1, align="L")
                                pdf.ln(6)
                                
                                for arq in arquivos:
                                    temp_path = None
                                    try:
                                        img = Image.open(arq)
                                        if img.mode != "RGB": img = img.convert("RGB")
                                        fd, temp_path = tempfile.mkstemp(suffix=".jpg")
                                        os.close(fd)
                                        img.save(temp_path, format="JPEG", quality=85)
                                        
                                        w_px, h_px = img.size
                                        w_alvo, h_alvo = 120, 120 * (h_px / w_px)
                                        if h_alvo > 100: h_alvo, w_alvo = 100, 100 * (w_px / h_px)
                                        pos_x = (210 - w_alvo) / 2
                                        
                                        if pdf.get_y() + h_alvo > 270: pdf.add_page()
                                        pdf.image(temp_path, x=pos_x, y=pdf.get_y(), w=w_alvo, h=h_alvo)
                                        pdf.ln(h_alvo + 6)
                                    except Exception:
                                        pass
                                    finally:
                                        if temp_path and os.path.exists(temp_path):
                                            try: os.remove(temp_path)
                                            except: pass

                        if st.session_state.equipamentos:
                            pdf.add_page()
                            pdf.set_font("Arial", "B", 12)
                            pdf.cell(0, 6, "EQUIPAMENTOS DISPONÍVEIS NO CLIENTE", ln=1, align="L")
                            pdf.ln(6)
                            for c_n in sorted(list(set([e["central"] for e in st.session_state.equipamentos]))):
                                pdf.set_font("Arial", "B", 10)
                                pdf.cell(0, 6, c_n.upper(), ln=1, align="L")
                                pdf.set_fill_color(230, 230, 230)
                                pdf.cell(20, 7, "QTD", border=1, align="C", fill=True)
                                pdf.cell(115, 7, "EQUIPAMENTO", border=1, align="L", fill=True)
                                pdf.cell(50, 7, "VAZÃO UNIT.", border=1, align="C", fill=True, ln=1)
                                pdf.set_font("Arial", "", 10)
                                v_sum = 0.0
                                for item in st.session_state.equipamentos:
                                    if item["central"] == c_n:
                                        pdf.cell(20, 6, f"{item['qtd']:02d}", border=1, align="C")
                                        pdf.cell(115, 6, f"{item['nome']}", border=1, align="L")
                                        pdf.cell(50, 6, f"{item['vazao_unit']:.2f} kg/h".replace(".", ","), border=1, align="C", ln=1)
                                        v_sum += item["vazao_total"]
                                pdf.set_font("Arial", "B", 10)
                                pdf.cell(135, 7, f"VAZÃO TOTAL {c_n.upper()}:", border=1, align="R", fill=True)
                                pdf.cell(50, 7, f"{v_sum:.2f} kg/h".replace(".", ","), border=1, align="C", fill=True, ln=1)
                                pdf.ln(4)

                        cod_limpo = re.sub(r'\D', '', str(cod_cliente))
                        data_str = datetime.now().strftime("%d-%m-%y")
                        nome_pdf = f"relatorio_{cod_limpo}_{data_str}.pdf"
                        
                        pdf_out = pdf.output(dest='S')
                        pdf_bytes = pdf_out.encode('latin-1', errors='replace') if isinstance(pdf_out, str) else bytes(pdf_out)

                        st.download_button("💾 Baixar PDF Gerado", data=pdf_bytes, file_name=nome_pdf, mime="application/pdf")

        # 2. ELABORAÇÃO DE CONTRATO
        elif menu_tratativa == "📝 Elaboração de Contrato":
            rcc = st.session_state.reset_counter_contrato
            cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento e geração do padrão de contrato.")
            
            if st.button("🔄 Novo Cliente", key=f"btn_limp_elab_{rcc}"):
                st.session_state.reset_counter_contrato += 1
                st.rerun()

            st.divider()
            st.subheader("1. Motivo")
            motivo_solicitacao = st.text_area("Descreva claramente o motivo da regularização do contrato:", key=f"motivo_{rcc}")

            st.divider()
            st.subheader("2. Dados do Cliente")
            c1, c2, c3 = st.columns(3)
            with c1: contato_contrato = st.text_input("Contato", key=f"contato_c_{rcc}")
            with c2: telefone_contrato = st.text_input("Telefone", key=f"tel_c_{rcc}")
            with c3: email_contrato = st.text_input("E-mail", key=f"email_c_{rcc}")

            st.divider()
            st.subheader("3. Solicitação")
            c_s1, c_s2 = st.columns(2)
            with c_s1: tipo_fluxo = st.radio("Selecione o objetivo da solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, index=None, key=f"fluxo_c_{rcc}")
            with c_s2: tipo_contrato = st.radio("Contrato / Aditamento / Distrato:", ["Contrato", "Aditamento", "Distrato"], horizontal=True, index=None, key=f"tp_cont_{rcc}")

            st.divider()
            st.subheader("4. Dados do Contrato")
            c_b1, c_b2 = st.columns(2)
            with c_b1: requisicao_opt = st.radio("Requisição:", ["Permanente", "Provisório"], horizontal=True, index=None, key=f"req_opt_{rcc}")
            with c_b2: mesmo_prop_opt = st.radio("Mesmo proprietário?", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_prop_{rcc}")

            cnpj_val, ie_val = "", ""
            email_novo_prop = ""
            mesmo_cnpj_opt = st.radio("Mesmo CNPJ?", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_cnpj_{rcc}")
            if mesmo_cnpj_opt == "Sim":
                cnpj_val = st.text_input("CNPJ:", key=f"cnpj_val_{rcc}")
                ie_val = st.text_input("I.E.:", key=f"ie_val_{rcc}")
            elif mesmo_cnpj_opt == "Não":
                cnpj_val = st.text_input("Novo CNPJ:", key=f"novo_cnpj_val_{rcc}")
                ie_val = st.text_input("Nova I.E.:", key=f"nova_ie_val_{rcc}")
            
            if mesmo_prop_opt == "Não":
                email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato:", key=f"email_novo_{rcc}")

            endereco_padrao = st.text_input("Endereço padrão ou entrega?:", key=f"end_padrao_{rcc}")
            qtd_entregas_c = st.number_input("Quantidade de centrais / endereços:", min_value=1, value=1, step=1, key=f"qtd_ent_c_{rcc}")
            
            eq_dict_c = {}
            if qtd_entregas_c == 1:
                eq_dict_c[1] = st.text_input("Equipamentos:", key=f"eq_ent_1_{rcc}")
            else:
                for i in range(1, int(qtd_entregas_c) + 1):
                    eq_dict_c[i] = st.text_input(f"Equipamentos Central {i:02d}:", key=f"eq_ent_{i}_{rcc}")

            st.divider()
            st.subheader("5. Comodato / Fornecimento")
            tipo_fornecimento = st.radio("Tipo de Fornecimento:", ["Granel", "Cilindro", "Ambos"], horizontal=True, index=None, key=f"tp_forn_{rcc}")
            
            preco_granel, consumo_granel = "", ""
            p13_v, p20_v, p45_v = "", "", ""
            consumo_cil = ""

            if tipo_fornecimento in ["Granel", "Ambos"]:
                c_g1, c_g2 = st.columns(2)
                with c_g1: preco_granel = st.text_input("Preço Granel (R$/kg):", key=f"preco_granel_{rcc}")
                with c_g2: consumo_granel = st.text_input("Consumo previsto (Granel) mensal:", key=f"cons_granel_{rcc}")

            if tipo_fornecimento in ["Cilindro", "Ambos"]:
                c_c1, c_c2, c_c3 = st.columns(3)
                with c_c1: p13_v = st.text_input("Preço P13 (R$):", key=f"p13_v_{rcc}")
                with c_c2: p20_v = st.text_input("Preço P20 (R$):", key=f"p20_v_{rcc}")
                with c_c3: p45_v = st.text_input("Preço P45 (R$):", key=f"p45_v_{rcc}")
                consumo_cil = st.text_input("Consumo previsto (Cilindro) mensal:", key=f"cons_cil_{rcc}")

            c_cp1, c_cp2 = st.columns(2)
            with c_cp1: cond_pagamento = st.text_input("Condição de pagamento:", key=f"cond_pag_{rcc}")
            with c_cp2: vigencia = st.text_input("Vigência:", key=f"vigencia_{rcc}")

            st.divider()
            st.subheader("6. Financeiro e Assinaturas")
            possui_debito_fin = st.radio("Possui NF's Pendentes?", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rcc}")
            resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", key=f"resp_pend_{rcc}") if possui_debito_fin == "Sim" else ""

            nome_testemunha, email_testemunha = "", ""
            responsaveis_dados = []
            if tipo_fluxo == "Enviar para Assinatura":
                c_t1, c_t2 = st.columns(2)
                with c_t1: nome_testemunha = st.text_input("Nome da Testemunha:", key=f"nome_test_{rcc}")
                with c_t2: email_testemunha = st.text_input("E-mail da Testemunha:", key=f"email_test_{rcc}")
                qtd_resp = st.selectbox("Quantidade de Responsáveis:", [1, 2, 3, 4], index=0, key=f"qtd_resp_{rcc}")
                for i in range(1, qtd_resp + 1):
                    cr1, cr2 = st.columns(2)
                    with cr1: nr = st.text_input(f"Nome Responsável {i:02d}:", key=f"n_resp_{i}_{rcc}")
                    with cr2: er = st.text_input(f"E-mail Responsável {i:02d}:", key=f"e_resp_{i}_{rcc}")
                    responsaveis_dados.append({"nome": nr, "email": er})

            st.divider()
            st.subheader("7. Condomínio CONTA SIM")
            conta_sim = st.radio("Condomínio CONTA SIM?:", ["Sim", "Não"], horizontal=True, index=None, key=f"conta_sim_{rcc}")
            num_unid, q_torres, q_blocos, p_religue, p_servico = "", "", "", "", ""
            if conta_sim == "Sim":
                cs1, cs2, cs3 = st.columns(3)
                with cs1:
                    num_unid = st.text_input("N° Unid autônomas:", key=f"num_unid_{rcc}")
                    q_torres = st.text_input("Qtd Torres:", key=f"qtd_torres_{rcc}")
                with cs2:
                    q_blocos = st.text_input("Qtd Blocos:", key=f"qtd_blocos_{rcc}")
                    p_religue = st.text_input("Valor preço de religue: R$", key=f"preco_rel_{rcc}")
                with cs3:
                    p_servico = st.text_input("Valor preço de serviço: R$", key=f"preco_serv_{rcc}")

            st.divider()
            if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
                lines = []
                if tipo_fluxo == "Gerar Minuta": lines.append("** FAVOR GERAR MINUTA EM PDF PARA ENVIO AO CLIENTE **")
                if motivo_solicitacao.strip(): lines.append(f"Descreva claramente o motivo da regularização do contrato: {motivo_solicitacao.strip()}")
                if tipo_contrato:
                    req_txt = f"Requisição ( {'X' if requisicao_opt=='Permanente' else ' '} ) Permanente ( {'X' if requisicao_opt=='Provisório' else ' '} )Provisório:" if requisicao_opt else ""
                    prop_txt = f"Mesmo proprietário?(sim/não): {mesmo_prop_opt}" if mesmo_prop_opt else ""
                    lines.append(f"Contrato / Aditamento / Distrato: {tipo_contrato} {req_txt} {prop_txt}".strip())
                
                if mesmo_cnpj_opt == "Não":
                    if cnpj_val.strip(): lines.append(f"Novo CNPJ: {cnpj_val.strip()}")
                    if ie_val.strip(): lines.append(f"Nova I.E.: {ie_val.strip()}")
                
                if endereco_padrao.strip(): lines.append(f"Endereço padrão ou entrega?: {endereco_padrao.strip()}")
                if preco_granel.strip(): lines.append(f"Preço Granel: {preco_granel.strip()}")
                
                partes_cil = []
                if p13_v.strip(): partes_cil.append(f"P13 = {p13_v.strip()}")
                if p20_v.strip(): partes_cil.append(f"P20 = {p20_v.strip()}")
                if p45_v.strip(): partes_cil.append(f"P45 = {p45_v.strip()}")
                if partes_cil: lines.append(f"Preço Cilindro: {' | '.join(partes_cil)}")
                
                if cond_pagamento.strip(): lines.append(f"Condição de pagamento: {cond_pagamento.strip()}")
                if consumo_granel.strip():
                    cg = consumo_granel.strip()
                    if not re.search(r'(?i)\bkgs?\b', cg): cg += " kgs"
                    lines.append(f"Consumo previsto (Granel) mensal: {cg}")
                if consumo_cil.strip():
                    cc = consumo_cil.strip()
                    if not re.search(r'(?i)\bkgs?\b', cc): cc += " kgs"
                    lines.append(f"Qual consumo previsto (Cilindro) mensal: {cc}")
                
                if vigencia.strip(): lines.append(f"Vigência: {vigencia.strip()}")
                
                eq_filled = [eq_dict_c[i].strip() for i in range(1, int(qtd_entregas_c) + 1) if eq_dict_c.get(i, "").strip()]
                if eq_filled: lines.append(f"Equipamentos: {' '.join(eq_filled)}")
                
                if resp_pendentes.strip(): lines.append(f"Quem será o responsável pelas NF's pendentes? {resp_pendentes.strip()}")
                if email_novo_prop.strip(): lines.append(f"E-mail do novo proprietário que receberá o novo contrato: {email_novo_prop.strip()}")
                
                if tipo_fluxo == "Enviar para Assinatura":
                    if nome_testemunha.strip(): lines.append(f"Nome da Testemunha: {nome_testemunha.strip()}")
                    if email_testemunha.strip(): lines.append(f"E-mail da Testemunha: {email_testemunha.strip()}")
                    for r in responsaveis_dados:
                        if r['nome'].strip(): lines.append(f"Nome do Responsável pela assinatura: {r['nome'].strip()}")
                        if r['email'].strip(): lines.append(f"E-mail do Responsável pela assinatura: {r['email'].strip()}")
                
                if conta_sim == "Sim":
                    lines.append(f"Condomínio CONTA SIM?: {conta_sim}")
                    if num_unid.strip(): lines.append(f"N° Unid autônomas (Aptos + áreas comuns/zeladoria): {num_unid.strip()}")
                    if q_torres.strip(): lines.append(f"Qtd Torres: {q_torres.strip()}")
                    if q_blocos.strip(): lines.append(f"Qtd Blocos: {q_blocos.strip()}")
                    if p_religue.strip(): lines.append(f"Valor preço de religue: R$ {p_religue.strip()}")
                    if p_servico.strip(): lines.append(f"Valor preço de serviço: R$ {p_servico.strip()}")

                texto_final_contrato = "\n".join([l for l in lines if l])
                st.success("✅ Gerado com sucesso!")
                st.text_area("Texto Gerado:", value=texto_final_contrato, height=400, key=f"txt_elab_{rcc}")
                botao_copiar_customizado(texto_final_contrato, "contrato_txt")

        # 3. APROVAÇÃO DE CONTRATO
        elif menu_tratativa == "📋 Aprovação de Contrato":
            rcap = st.session_state.reset_counter
            cabecalho_pagina("Aprovação de Contrato", "Formulário de solicitação de aprovação de contrato.")

            if st.button("🔄 Novo Cliente", key=f"btn_limp_aprov_{rcap}"):
                st.session_state.reset_counter += 1
                st.rerun()

            st.divider()
            st.subheader("1. Motivo")
            motivo_reg = st.text_input("Motivo da regularização *", key=f"ap_motivo_{rcap}")
            
            st.divider()
            st.subheader("2. Informações de Contato")
            c1, c2, c3 = st.columns(3)
            with c1: contato_ap = st.text_input("Contato *", key=f"ap_cont_{rcap}")
            with c2: telefone_ap = st.text_input("Telefone *", key=f"ap_tel_{rcap}")
            with c3: email_ap = st.text_input("E-mail *", key=f"ap_email_{rcap}")
            
            atualizar_email = st.radio("Atualizar E-mail? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_atu_email_{rcap}")
            novo_email_ap = st.text_input("Novo E-mail *", key=f"ap_novo_email_{rcap}") if atualizar_email == "Sim" else ""

            st.divider()
            st.subheader("3. Dados do Contrato")
            c_a1, c_a2 = st.columns(2)
            with c_a1: contrato_adit = st.radio("Contrato / Aditamento *", ["Contrato", "Aditamento"], horizontal=True, index=None, key=f"ap_tp_cont_{rcap}")
            with c_a2: vigencia_ap = st.text_input("Vigência *", key=f"ap_vig_{rcap}")

            qtd_entregas_ap = st.number_input("Quantidade de endereços/centrais", min_value=1, value=1, step=1, key=f"qtd_ent_ap_{rcap}")
            equipamentos_ap = ""
            eq_dict_ap = {}
            if qtd_entregas_ap == 1: equipamentos_ap = st.text_input("Equipamentos *", key=f"ap_eq_{rcap}")
            else:
                for i in range(1, int(qtd_entregas_ap) + 1):
                    eq_dict_ap[i] = st.text_input(f"Equipamentos - [Entrega {i}] *", key=f"ap_eq_ent_{i}_{rcap}")

            especificidade_ap = st.text_input("Existe especificidade sobre a solicitação? *", key=f"ap_esp_{rcap}")

            st.divider()
            st.subheader("4. Redimensionamento")
            redim = st.radio("Redimensionamento: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_redim_{rcap}")
            comodato_de, comodato_para, inc_tanques, env_pecas = "", "", "Não", "Não"
            if redim == "Sim":
                cp1, cp2 = st.columns(2)
                with cp1: comodato_de = st.text_input("Comodato passou de:", key=f"ap_com_de_{rcap}")
                with cp2: comodato_para = st.text_input("Para:", key=f"ap_com_para_{rcap}")
                cp3, cp4 = st.columns(2)
                with cp3: inc_tanques = st.radio("Inclusão de tanques?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_inc_tanq_{rcap}")
                with cp4: env_pecas = st.radio("Necessário lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_env_pec_{rcap}")

            st.divider()
            st.subheader("5. Condomínio Conta Sim & Portaria")
            implantacao_csim = st.radio("Implantação de conta sim: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_{rcap}")
            env_pecas_ficha, env_ficha_cliente, tp_portaria, contato_resp_port, part_local, contato_sindico = "Não", "Não", "", "", "", ""
            if implantacao_csim == "Sim":
                cs1, cs2 = st.columns(2)
                with cs1: env_pecas_ficha = st.radio("Foi enviado lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_pec_{rcap}")
                with cs2: env_ficha_cliente = st.radio("Foi enviado ficha de clientes?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_ficha_{rcap}")
                tp_portaria = st.text_input("Tipo de portaria", key=f"ap_tp_port_{rcap}")
                contato_resp_port = st.text_input("Contato do responsável:", key=f"ap_cont_resp_{rcap}")
                part_local = st.text_input("Particularidades do local", key=f"ap_part_local_{rcap}")
                contato_sindico = st.text_input("Contato atualizado do síndico", key=f"ap_cont_sind_{rcap}")

            st.divider()
            st.subheader("6. Alteração de CNPJ & Títulos em Aberto")
            alt_cnpj = st.radio("Alteração de CNPJ ou razão social? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_alt_cnpj_{rcap}")
            mesmo_prop_opt = st.radio("Se trata do mesmo proprietário: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_mesmo_prop_{rcap}")
            possui_titulos_aberto = st.radio("Possui títulos em aberto? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_tit_aberto_{rcap}")
            neg_tit_input = st.text_input("Descreva a negociação realizada:", key=f"ap_neg_tit_{rcap}") if possui_titulos_aberto == "Sim" else ""

            st.divider()
            st.subheader("7. Redução de Vigência")
            red_vig = st.radio("Redução de vigência? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_red_vig_{rcap}")
            motivo_red_vig = st.text_input("Descreva o motivo:", key=f"ap_mot_red_{rcap}") if red_vig == "Sim" else ""

            st.divider()
            st.subheader("8. Projeto Padrão")
            cp_proj1, cp_proj2 = st.columns([3, 1])
            with cp_proj1: projeto_num = st.text_input("Projeto (Número completo): *", key=f"ap_proj7_{rcap}")
            with cp_proj2:
                st.write(""); st.write("")
                is_cilindros = st.checkbox("Cilindros", key=f"ap_cil_{rcap}")

            st.divider()
            if st.button("📝 Gerar Texto de Aprovação de Contrato", type="primary"):
                faltam = []
                if not motivo_reg.strip(): faltam.append("Motivo da regularização")
                if not contato_ap.strip(): faltam.append("Contato")
                if not telefone_ap.strip(): faltam.append("Telefone")
                if not email_ap.strip(): faltam.append("E-mail")
                if not contrato_adit: faltam.append("Contrato / Aditamento")
                if not vigencia_ap.strip(): faltam.append("Vigência")
                if not redim: faltam.append("Redimensionamento")
                if not implantacao_csim: faltam.append("Implantação de conta sim")
                if not alt_cnpj: faltam.append("Alteração de CNPJ")
                if not mesmo_prop_opt: faltam.append("Mesmo proprietário")
                if not possui_titulos_aberto: faltam.append("Títulos em aberto")
                if not red_vig: faltam.append("Redução de vigência")
                if not is_cilindros and not projeto_num.strip(): faltam.append("Projeto Padrão")

                if faltam:
                    st.error("⚠️ Preencha os campos obrigatórios:\n\n- " + "\n- ".join(faltam))
                else:
                    def b_box(v): return "[ x ] sim [   ] não" if v == "Sim" else "[   ] sim [ x ] não"
                    def b_par(v): return "( X ) SIM (   ) NÃO" if v == "Sim" else "(   ) SIM ( X ) NÃO"

                    linhas = [f"Motivo da regularização: {motivo_reg.strip()}", ""]
                    linhas.append(f"Contato: {contato_ap.strip()}")
                    linhas.append(f"Telefone: {telefone_ap.strip()}")
                    linhas.append(f"E-mail: {email_ap.strip()}")
                    if atualizar_email == "Sim": linhas.append(f"Atualizar E-mail? {b_box(atualizar_email)} - Novo E-mail: {novo_email_ap.strip()}")
                    else: linhas.append(f"Atualizar E-mail? {b_box(atualizar_email)}")
                    linhas.append("")

                    linhas.append(f"Contrato / Aditamento: {contrato_adit}")
                    linhas.append(f"Vigência: {vigencia_ap.strip()}")
                    eq_txt = equipamentos_ap.strip() if qtd_entregas_ap == 1 else " ".join([f"[Entrega {i}] {eq_dict_ap[i].strip()}" for i in range(1, int(qtd_entregas_ap)+1)])
                    linhas.append(f"Equipamentos: {eq_txt}")
                    linhas.append(f"Existe especificidade sobre a solicitação: {especificidade_ap.strip()}")
                    linhas.append("")

                    linhas.append(f"Redimensionamento: {b_box(redim)}")
                    if redim == "Sim":
                        linhas.append(f"Comodato passou de: {comodato_de.strip()}")
                        linhas.append(f"Para: {comodato_para.strip()}")
                        linhas.append(f"Inclusão de tanques? {b_box(inc_tanques)}")
                        linhas.append(f"Necessário lista de peças? {b_box(env_pecas)}")
                    linhas.append("")

                    linhas.append(f"Implantação de conta sim: {b_box(implantacao_csim)}")
                    if implantacao_csim == "Sim":
                        linhas.append(f"Foi enviado lista de peças? {b_box(env_pecas_ficha)}")
                        linhas.append(f"Foi enviado ficha de clientes? {b_box(env_ficha_cliente)}")
                        linhas.append(f"Tipo de portaria: {tp_portaria.strip()}")
                        linhas.append(f"Contato do responsável: {contato_resp_port.strip()}")
                        linhas.append(f"Particularidades do local: {part_local.strip()}")
                        linhas.append(f"Contato atualizado do síndico: {contato_sindico.strip()}")
                    linhas.append("")

                    linhas.append(f"Alteração de CNPJ ou razão social? {b_box(alt_cnpj)}")
                    linhas.append(f"Se trata do mesmo proprietário: {b_par(mesmo_prop_opt)}")
                    linhas.append(f"Possui títulos em aberto {b_box(possui_titulos_aberto)}")
                    linhas.append(f"Descreva a negociação realizada: {neg_tit_input.strip() if possui_titulos_aberto=='Sim' else 'n/a'}")
                    linhas.append("")

                    linhas.append(f"Projeto (Informe o número completo do projeto): {'N/A' if is_cilindros else projeto_num.strip()}")
                    linhas.append("")

                    linhas.append(f"Redução de vigência? {b_box(red_vig)}")
                    if red_vig == "Sim": linhas.append(f"(Se sim, descreva o motivo): {motivo_red_vig.strip()}")

                    texto_aprov = "\n".join(linhas)
                    st.success("✅ Gerado com sucesso!")
                    st.text_area("Texto Gerado:", value=texto_aprov, height=450, key=f"txt_aprov_{rcap}")
                    botao_copiar_customizado(texto_aprov, "aprovacao_txt")

        # 4. ANIVERSÁRIO DE CONTRATO
        elif menu_tratativa == "🎂 Aniversário de Contrato":
            rca = st.session_state.reset_counter
            cabecalho_pagina("Aniversário de Contrato", "Calculadora de reajuste por IPCA acumulado de 12M e geração de formulário.")

            if st.button("🔄 Novo Cliente", key=f"btn_limp_aniv_{rca}"):
                st.session_state.reset_counter += 1
                st.rerun()

            st.divider()
            ipca_api, ipca_periodo = obter_ipca_acumulado_12m()
            if ipca_api is not None:
                ipca_vigente = ipca_api
                st.success(f"📊 **IPCA Acumulado de 12 meses (Referência {ipca_periodo}):** `{ipca_vigente:.2f}%`")
            else:
                ipca_vigente = st.number_input("IPCA acumulado de 12 meses (%)", min_value=0.0, value=4.63, step=0.01, format="%.2f", key=f"ipca_manual_{rca}")

            c_an1, c_an2 = st.columns(2)
            with c_an1: preco_anterior_input = st.text_input("Preço Anterior (R$)", value="7,7400", key=f"preco_ant_{rca}")
            with c_an2: clausula_contrato = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, index=None, key=f"clausula_{rca}")

            st.divider()
            p_aniv_str = "0,0000"
            try:
                val_limpo = preco_anterior_input.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
                p_ant = float(val_limpo)
                p_aniv = p_ant * (1 + (ipca_vigente / 100.0))
                p_aniv_str = f"{p_aniv:.4f}".replace(".", ",")
            except ValueError:
                pass

            if st.button("📝 Gerar Texto de Aniversário de Contrato", type="primary"):
                if clausula_contrato == "Não": st.warning("⚠️ O cliente não possui cláusula de reajuste em contrato.")
                clausula_txt = "Cliente possui cláusula em contrato.\n" if clausula_contrato == "Sim" else ""
                p_ant_fmt = preco_anterior_input.strip()
                if not p_ant_fmt.startswith("R$"): p_ant_fmt = f"R$ {p_ant_fmt}"

                texto_aniversario = f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%.\n{clausula_txt}Preço anterior: {p_ant_fmt}\nPreço Aniversário: R$ {p_aniv_str}"
                st.success("✅ Gerado com sucesso!")
                
                cv1, cv2 = st.columns([1, 2])
                with cv1: st.text_input("Preço Novo para CI:", value=f"R$ {p_aniv_str}", key=f"val_novo_{rca}")
                with cv2:
                    st.write(""); st.write("")
                    botao_copiar_customizado(f"R$ {p_aniv_str}", "copy_val_novo", label_btn="💵 Copiar Valor Novo")

                st.text_area("Texto Gerado:", value=texto_aniversario, height=180, key=f"txt_aniv_{rca}")
                botao_copiar_customizado(texto_aniversario, "aniversario_txt")

            st.divider()
            ci_input = st.text_input("Número da C.I. (9 ou 11 dígitos)", placeholder="Ex: 588358982", key=f"ci_num_{rca}")
            if st.button("📝 Gerar Texto Final com C.I.", type="primary"):
                clausula_txt = "Cliente possui cláusula em contrato.\n" if clausula_contrato == "Sim" else ""
                p_ant_fmt = preco_anterior_input.strip()
                if not p_ant_fmt.startswith("R$"): p_ant_fmt = f"R$ {p_ant_fmt}"
                ci_fmt = formatar_ci_num(ci_input)

                texto_ci = f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%.\n{clausula_txt}Preço anterior: {p_ant_fmt}\nPreço Aniversário: R$ {p_aniv_str}\n\nCI.: {ci_fmt} - Preço Aniversário"
                st.success("✅ Texto com C.I. gerado com sucesso!")
                st.text_area("Texto com C.I.:", value=texto_ci, height=220, key=f"txt_ci_{rca}")
                botao_copiar_customizado(texto_ci, "ci_txt")

        # 5. FICHA DE CLIENTE (COM CAMPOS 100% VAZIOS)
        elif menu_tratativa == "🗂️ Ficha de Cliente":
            rcf = st.session_state.reset_counter_fc
            cabecalho_pagina("Ficha de Cliente", "Preenchimento de condições contratuais e comerciais para ficha de cliente.")

            if st.button("🔄 Novo Cliente", key=f"btn_limp_fc_{rcf}"):
                st.session_state.reset_counter_fc += 1
                st.rerun()

            st.divider()
            motivo_fc = st.text_input("Motivo:", key=f"fc_motivo_{rcf}")
            
            c_fc1, c_fc2 = st.columns(2)
            with c_fc1: contrato_ant_fc = st.text_input("Contrato / Aditamento Anterior:", key=f"fc_cont_ant_{rcf}")
            with c_fc2: contrato_novo_fc = st.text_input("Contrato Novo:", key=f"fc_cont_novo_{rcf}")

            comodato_fc = st.text_input("Comodato:", key=f"fc_comodato_{rcf}")
            tipo_forn_fc = st.radio("Tipo de Fornecimento:", ["Granel", "Cilindro", "Ambos"], horizontal=True, index=None, key=f"fc_tp_forn_{rcf}")

            preco_granel_fc, p13_fc, p20_fc, p45_fc, consumo_granel_fc, consumo_cil_fc = "", "", "", "", "", ""
            if tipo_forn_fc in ["Granel", "Ambos"]:
                cfg1, cfg2 = st.columns(2)
                with cfg1: preco_granel_fc = st.text_input("Preço Granel (/kg):", key=f"fc_preco_granel_{rcf}")
                with cfg2: consumo_granel_fc = st.text_input("Consumo Mensal Previsto (Granel):", key=f"fc_cons_granel_{rcf}")

            if tipo_forn_fc in ["Cilindro", "Ambos"]:
                cp1, cp2, cp3 = st.columns(3)
                with cp1: p13_fc = st.text_input("Preço P13:", key=f"fc_p13_{rcf}")
                with cp2: p20_fc = st.text_input("Preço P20:", key=f"fc_p20_{rcf}")
                with cp3: p45_fc = st.text_input("Preço P45:", key=f"fc_p45_{rcf}")
                consumo_cil_fc = st.text_input("Consumo Mensal Previsto (Cilindro):", key=f"fc_cons_cil_{rcf}")

            cfv1, cfv2 = st.columns(2)
            with cfv1: cond_pag_fc = st.text_input("Condição de Pagamento:", key=f"fc_cond_pag_{rcf}")
            with cfv2: vigencia_fc = st.text_input("Vigência:", key=f"fc_vigencia_{rcf}")

            obs_fc = st.text_area("Obs.:", key=f"fc_obs_{rcf}")

            st.divider()
            if st.button("📝 Gerar Texto da Ficha de Cliente", type="primary", key=f"btn_gerar_fc_{rcf}"):
                linhas_fc = [f"Motivo: {motivo_fc.strip()}"]
                if contrato_ant_fc.strip(): linhas_fc.append(f"CONTRATO / ADITAMENTO ANTERIOR: {contrato_ant_fc.strip()}")
                if contrato_novo_fc.strip(): linhas_fc.append(f"CONTRATO NOVO: {contrato_novo_fc.strip()}")
                if comodato_fc.strip(): linhas_fc.append(f"COMODATO: {comodato_fc.strip()}")

                if tipo_forn_fc in ["Granel", "Ambos"] and preco_granel_fc.strip():
                    pg_c = re.sub(r'(?i)\s*/\s*kg\s*$', '', preco_granel_fc.strip())
                    linhas_fc.append(f"PREÇO GRANEL: {pg_c} /kg")

                if tipo_forn_fc in ["Cilindro", "Ambos"]:
                    partes_cil_fc = []
                    if p13_fc.strip(): partes_cil_fc.append(f"{re.sub(r'(?i)\\s*/\\s*und.*', '', p13_fc.strip())} /und P13")
                    if p20_fc.strip(): partes_cil_fc.append(f"{re.sub(r'(?i)\\s*/\\s*und.*', '', p20_fc.strip())} /und P20")
                    if p45_fc.strip(): partes_cil_fc.append(f"{re.sub(r'(?i)\\s*/\\s*und.*', '', p45_fc.strip())} /und P45")
                    if partes_cil_fc: linhas_fc.append(f"PREÇO CILINDRO: {' | '.join(partes_cil_fc)}")

                if tipo_forn_fc in ["Granel", "Ambos"] and consumo_granel_fc.strip():
                    linhas_fc.append(f"CONSUMO MENSAL PREVISTO GRANEL: {consumo_granel_fc.strip()}")
                if tipo_forn_fc in ["Cilindro", "Ambos"] and consumo_cil_fc.strip():
                    linhas_fc.append(f"CONSUMO MENSAL PREVISTO CILINDRO: {consumo_cil_fc.strip()}")

                if cond_pag_fc.strip(): linhas_fc.append(f"CONDIÇÃO DE PAGAMENTO: {cond_pag_fc.strip()}")
                if vigencia_fc.strip(): linhas_fc.append(f"VIGÊNCIA: {vigencia_fc.strip()}")
                if obs_fc.strip(): linhas_fc.append(f"Obs.: {obs_fc.strip()}")

                texto_ficha = "\n".join(linhas_fc)
                st.success("✅ Gerado com sucesso!")
                st.text_area("Texto Gerado:", value=texto_ficha, height=320, key=f"txt_fc_{rcf}")
                botao_copiar_customizado(texto_ficha, "ficha_cliente_txt")


=====================================================================

ABA 2: AGENDA DE OCORRÊNCIAS (COM ISOLAMENTO DE SESSÃO)

=====================================================================

if aba_agenda is not None:
with aba_agenda:
COL_OCORRENCIA = "Número da ocorrência"
COL_CLIENTE = "Nome do cliente"
COL_ENDERECO = "Endereço de Entrega"
COL_ABERTURA = "Data/Hora de abertura"
COL_PRAZO = "Prazo de Atendimento"
COL_FECHAMENTO = "Data/Hora de fechamento"
COL_SUB_CLASSIF = "Subclassificação Ocorrência"
COL_PROPRIETARIO = "Proprietário da ocorrência"

    def extrair_cidade(endereco):
        if pd.isna(endereco): return "-"
        s = str(endereco).strip()
        s_norm = s.replace(';', ',').replace('|', ',')
        partes = [p.strip() for p in s_norm.split(',')]
        if len(partes) >= 2:
            cidade = partes[-2].strip()
            if cidade.isdigit() and len(partes) >= 3: cidade = partes[-3].strip()
            return cidade.title()
        return s.title()

    def limpar_classificacao(texto):
        if pd.isna(texto): return "-"
        t_limpo = re.sub(r'\[.*?\]', '', str(texto)).strip()
        return t_limpo if t_limpo else str(texto)

    def classificar_status_geral(row, hoje_ref):
        prazo = row['Prazo_DT']
        if pd.isna(prazo): return "🟢 No Prazo"
        p_dia = pd.Timestamp(prazo).normalize()
        h_dia = pd.Timestamp(hoje_ref).normalize()
        
        if p_dia < h_dia: return "🔴 Vencido"
        elif p_dia == h_dia: return "🔵 Vence Hoje"
        elif p_dia == h_dia + timedelta(days=1): return "🟠 Vence Amanhã"
        else: return "🟢 No Prazo"

    col_menu_agenda, col_conteudo_agenda = st.columns([1, 4])

    with col_menu_agenda:
        st.markdown("### 📌 Filtros")
        arquivo_excel = st.file_uploader("📂 Importar Planilha Excel", type=["xlsx", "xls"], key="uploader_agenda_excel")
        
        st.divider()
        opcoes_visao = ["Todas Ocorrências", "Comodato Inativo", "Ocorrências por Cidade"]
        if st.session_state.e_supervisor:
            opcoes_visao.append("📊 Dashboard de Gestão (Gráficos)")

        tipo_visao_agenda = st.radio("Visualização:", opcoes_visao, label_visibility="collapsed")

        st.divider()
        st.markdown("### 🚦 Legenda de Status")
        st.markdown("🔴 Vencido")
        st.markdown("🔵 Vence Hoje")
        st.markdown("🟠 Vence Amanhã")
        st.markdown("🟢 No Prazo")

    with col_conteudo_agenda:
        cabecalho_pagina("Módulo de Pós-Vendas & Atendimento", "Sistema Integrado de Gestão de Ocorrências por Prazos, SLAs e Geografia")

        if arquivo_excel is not None:
            st.session_state.df_excel_agenda = arquivo_excel

        if st.session_state.df_excel_agenda is not None:
            try:
                df = ler_arquivo_excel_robusto(st.session_state.df_excel_agenda)
                df.columns = [str(c).strip() for c in df.columns]
                
                if COL_OCORRENCIA not in df.columns:
                    for idx_r, row in df.iterrows():
                        row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
                        if COL_OCORRENCIA in row_str:
                            df.columns = [str(c).strip() for c in df.iloc[idx_r].values]
                            df = df.iloc[idx_r+1:].reset_index(drop=True)
                            break

                if COL_OCORRENCIA not in df.columns:
                    st.error(f"❌ Coluna obrigatória '{COL_OCORRENCIA}' não encontrada.")
                    st.stop()

                df = df.dropna(subset=[COL_OCORRENCIA])
                df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
                df_pendentes[COL_OCORRENCIA] = pd.to_numeric(df_pendentes[COL_OCORRENCIA], errors='coerce')
                df_pendentes = df_pendentes.dropna(subset=[COL_OCORRENCIA])
                df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
                
                df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
                df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
                
                df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
                df_pendentes['Classificação Limpa'] = df_pendentes[COL_SUB_CLASSIF].apply(limpar_classificacao)
                
                if st.session_state.e_supervisor:
                    if COL_PROPRIETARIO in df_pendentes.columns: df_pendentes['Consultor'] = df_pendentes[COL_PROPRIETARIO].fillna("Geral").astype(str)
                    else: df_pendentes['Consultor'] = "Geral"
                else:
                    df_pendentes['Consultor'] = "Geral"

                hoje = datetime.now()
                dias_para_sexta = (4 - hoje.weekday()) % 7
                sexta_semana = hoje + timedelta(days=dias_para_sexta)
                sexta_semana = sexta_semana.replace(hour=23, minute=59, second=59)

                df_pendentes['Status Geral'] = df_pendentes.apply(lambda r: classificar_status_geral(r, hoje), axis=1)
                df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
                df_base_visao = df_pendentes.copy()

                if tipo_visao_agenda == "Comodato Inativo":
                    df_base_visao = df_base_visao[df_base_visao['Classificação Limpa'].str.contains("Comodato Inativo", case=False, na=False)]
                    st.subheader("⚠️ Relatório Específico: Comodato Inativo")
                elif tipo_visao_agenda == "Ocorrências por Cidade":
                    st.subheader("🏙️ Ocorrências por Cidade")
                    df_mapa_agrup = df_base_visao.groupby('Cidade').size().reset_index(name='Total Ocorrências').sort_values(by='Total Ocorrências', ascending=False)
                    
                    col_tc1, col_tc2 = st.columns(2)
                    with col_tc1: st.dataframe(df_mapa_agrup, hide_index=True, use_container_width=True)
                    with col_tc2:
                        chart_c = alt.Chart(df_mapa_agrup).mark_bar(color="#0055A5", cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                            x=alt.X('Total Ocorrências:Q', title='Qtd Ocorrências'),
                            y=alt.Y('Cidade:N', sort='-x', title='Cidade'),
                            tooltip=['Cidade', 'Total Ocorrências']
                        ).properties(height=300).interactive(bind_x=False, bind_y=False)
                        st.altair_chart(chart_c, use_container_width=True)
                    st.stop()
                elif tipo_visao_agenda == "📊 Dashboard de Gestão (Gráficos)" and st.session_state.e_supervisor:
                    st.subheader("📊 Dashboard Executivo de Gestão")
                    graficos_cfg = [
                        ("🔴 Ocorrências Vencidas", df_base_visao[df_base_visao['Status Geral'] == '🔴 Vencido'], "#D32F2F"),
                        ("🔵 Vencimento Hoje", df_base_visao[df_base_visao['Status Geral'] == '🔵 Vence Hoje'], "#1976D2"),
                    ]
                    for i in range(0, len(graficos_cfg), 2):
                        cg1, cg2 = st.columns(2)
                        with cg1:
                            t1, df1, cor1 = graficos_cfg[i]
                            st.markdown(f"#### {t1}")
                            if not df1.empty:
                                d_ag1 = df1.groupby('Consultor').size().reset_index(name='Total').sort_values(by='Total', ascending=False)
                                ch1 = alt.Chart(d_ag1).mark_bar(color=cor1).encode(x='Total:Q', y=alt.Y('Consultor:N', sort='-x')).properties(height=220)
                                st.altair_chart(ch1, use_container_width=True)
                        st.divider()
                    st.stop()
                else:
                    st.subheader("2. Agenda Geral de Visitas Pendentes")

                # BOTÕES DE FILTRO INTERATIVOS (NÚMERO EM CIMA, TEXTO EMBAIXO)
                tot_v = len(df_base_visao)
                venc_v = len(df_base_visao[df_base_visao['Status Geral'] == '🔴 Vencido'])
                hoje_v = len(df_base_visao[df_base_visao['Status Geral'] == '🔵 Vence Hoje'])
                amanha_v = len(df_base_visao[df_base_visao['Status Geral'] == '🟠 Vence Amanhã'])
                semana_v = len(df_base_visao[(df_base_visao['Status Geral'] == '🔴 Vencido') | ((df_base_visao['Prazo_DT'] >= pd.Timestamp(hoje.date())) & (df_base_visao['Prazo_DT'] <= sexta_semana))])

                fc1, fc2, fc3, fc4, fc5 = st.columns(5)
                with fc1:
                    if st.button(f"**{tot_v}**\nTotal", use_container_width=True): st.session_state.filtro_dashboard_ativo = "Todas"
                with fc2:
                    if st.button(f"**{venc_v}**\nVencidas", use_container_width=True): st.session_state.filtro_dashboard_ativo = "🔴 Vencido"
                with fc3:
                    if st.button(f"**{hoje_v}**\nVence Hoje", use_container_width=True): st.session_state.filtro_dashboard_ativo = "🔵 Vence Hoje"
                with fc4:
                    if st.button(f"**{amanha_v}**\nVence Amanhã", use_container_width=True): st.session_state.filtro_dashboard_ativo = "🟠 Vence Amanhã"
                with fc5:
                    if st.button(f"**{semana_v}**\nVencem na Semana", use_container_width=True): st.session_state.filtro_dashboard_ativo = "Semana"

                st.divider()

                c_f1, c_f2 = st.columns(2)
                with c_f1: cidade_sel = st.selectbox("Filtrar por Cidade:", ["Todas"] + sorted(list(df_base_visao['Cidade'].unique())))
                with c_f2: class_sel = st.selectbox("Filtrar por Classificação:", ["Todas"] + sorted(list(df_base_visao['Classificação Limpa'].unique())))

                df_filt = df_base_visao.copy()
                if st.session_state.filtro_dashboard_ativo != "Todas":
                    if st.session_state.filtro_dashboard_ativo == "Semana":
                        df_filt = df_filt[(df_filt['Status Geral'] == '🔴 Vencido') | ((df_filt['Prazo_DT'] >= pd.Timestamp(hoje.date())) & (df_filt['Prazo_DT'] <= sexta_semana))]
                    else:
                        df_filt = df_filt[df_filt['Status Geral'] == st.session_state.filtro_dashboard_ativo]

                if cidade_sel != "Todas": df_filt = df_filt[df_filt['Cidade'] == cidade_sel]
                if class_sel != "Todas": df_filt = df_filt[df_filt['Classificação Limpa'] == class_sel]

                df_filt['Prazo'] = df_filt['Prazo_DT'].dt.strftime('%d/%m/%Y')
                df_filt['SLA'] = (pd.to_datetime(df_filt['Prazo_DT'].dt.date) - pd.Timestamp(datetime.now().date())).dt.days
                df_filt['Status'] = df_filt['Status Geral'].apply(lambda x: x.split()[0])

                if df_filt.empty:
                    st.success("✅ Nenhuma ocorrência pendente para os filtros selecionados.")
                else:
                    df_ex = df_filt[['Status', 'SLA', COL_OCORRENCIA, COL_CLIENTE, 'Cidade', 'Classificação Limpa', 'Prazo']].copy()
                    df_ex.columns = ['Status', 'SLA', 'Nº OC', 'Cliente', 'Cidade', 'Classificação', 'Prazo']
                    df_ex['Nº OC'] = df_ex['Nº OC'].astype(str)
                    
                    st.dataframe(df_ex, hide_index=True, use_container_width=True)

            except Exception as e:
                st.error(f"⚠️ Erro ao processar o arquivo: {e}")
        else:
            st.info("👆 Por favor, faça o upload da planilha atualizada no menu lateral esquerdo.")


=====================================================================

ABA 3: STATUS DE CONTRATOS

=====================================================================

if aba_contratos is not None:
with aba_contratos:
cabecalho_pagina("Status de Contratos", "Acompanhamento de clientes em processo de contrato.")
status_c = ["Elaboração de Contrato", "Aguardando Ass do Cliente", "Aguardando Ass do Gerente", "Processo Enviado"]
cores_c = {"Elaboração de Contrato": "🔴", "Aguardando Ass do Cliente": "🟠", "Aguardando Ass do Gerente": "🟡", "Processo Enviado": "🟢"}
renderizar_painel_acompanhamento("contrato", status_c, cores_c)

=====================================================================

ABA 4: STATUS DE VENDAS

=====================================================================

if aba_vendas is not None:
with aba_vendas:
cabecalho_pagina("Status de Vendas", "Acompanhamento de clientes em negociação e venda.")
status_v = ["Negociação Criada", "Aguardando Ass Cliente", "Processo despachado", "OC Venda de peça externo aberta", "Instalação / Serviço executado"]
cores_v = {"Negociação Criada": "🔴", "Aguardando Ass Cliente": "🟠", "Processo despachado": "🟡", "OC Venda de peça externo aberta": "🔵", "Instalação / Serviço executado": "🟢"}
renderizar_painel_acompanhamento("venda", status_v, cores_v)

=====================================================================

ABA 5: BLOCO DE NOTAS PESSOAL

=====================================================================

if aba_notas is not None:
with aba_notas:
col_mn, col_cn = st.columns([1, 4])
usr = st.session_state.usuario_atual
notas_usr = carregar_banco_notas(usr)

    with col_mn:
        st.markdown("### 📓 Minhas Notas")
        if st.button("➕ Nova Nota", use_container_width=True):
            st.session_state.nota_selecionada_id = None
            st.rerun()
        st.divider()
        for n_id, n_data in notas_usr.items():
            if st.button(n_data.get("titulo", "Sem Título"), key=f"btn_n_{n_id}", use_container_width=True):
                st.session_state.nota_selecionada_id = n_id
                st.rerun()

    with col_cn:
        cabecalho_pagina("Bloco de Notas Pessoal", "Anotações vinculadas à sua conta na nuvem.")
        id_at = st.session_state.nota_selecionada_id
        t_v = notas_usr[id_at]["titulo"] if id_at in notas_usr else ""
        c_v = notas_usr[id_at]["cliente"] if id_at in notas_usr else ""
        txt_v = notas_usr[id_at]["texto"] if id_at in notas_usr else ""

        with st.form("form_nota"):
            cn1, cn2 = st.columns(2)
            with cn1: tit = st.text_input("Título", value=t_v)
            with cn2: cli = st.text_input("Cliente", value=c_v)
            txt = st.text_area("Anotação", value=txt_v, height=200)
            
            bn1, bn2, _ = st.columns([1, 1, 4])
            with bn1: btn_s = st.form_submit_button("💾 Salvar na Nuvem", type="primary")
            with bn2: btn_d = st.form_submit_button("🗑️ Apagar") if id_at else False

            if btn_s and tit:
                tid = id_at if id_at else str(uuid.uuid4())
                if salvar_nota(tid, usr, tit, cli, txt):
                    st.session_state.nota_selecionada_id = tid
                    st.success("✅ Salvo com sucesso!")
                    st.rerun()
            if btn_d and id_at:
                if apagar_nota(id_at):
                    st.session_state.nota_selecionada_id = None
                    st.rerun()


=====================================================================

PAINEL ADMIN

=====================================================================

if aba_admin is not None:
with aba_admin:
cabecalho_pagina("Painel de Administração", "Gerenciamento de usuários e senhas.")
banco_u = carregar_banco_usuarios()
ca1, ca2 = st.columns(2)

    with ca1:
        st.subheader("1. Cadastrar Novo Usuário")
        with st.form("form_novo_usuario"):
            novo_user = st.text_input("Nome do Usuário", placeholder="ex: rodrigo.carvalho").strip().lower()
            nivel_acesso = st.selectbox("Nível de Acesso", ["convencional", "supervisor", "admin"])
            if st.form_submit_button("➕ Cadastrar", type="primary"):
                if not novo_user: st.error("⚠️ Preencha o usuário.")
                elif novo_user in banco_u: st.warning("⚠️ Usuário já existe.")
                else:
                    if salvar_usuario(novo_user, "123456", nivel_acesso=nivel_acesso, precisa_trocar=True):
                        st.success(f"✅ Usuário {novo_user} criado!")
                        st.rerun()

    with ca2:
        st.subheader("2. Reset de Senha")
        l_u = [u for u in banco_u.keys() if u != "admin"]
        if l_u:
            usr_sel = st.selectbox("Usuário:", l_u)
            if st.button("🔄 Resetar para 123456", type="primary"):
                if salvar_usuario(usr_sel, "123456", nivel_acesso=banco_u[usr_sel]["nivel_acesso"], precisa_trocar=True):
                    st.success("✅ Senha resetada!")
                    st.rerun()

    st.divider()
    st.subheader("3. Usuários Cadastrados")
    d_users = [{"Usuário": k, "Nível": v["nivel_acesso"], "Status": "Troca Pendente" if v["precisa_trocar_senha"] else "Definida"} for k, v in banco_u.items()]
    st.dataframe(pd.DataFrame(d_users), hide_index=True, use_container_width=True)

    if l_u:
        cr1, cr2 = st.columns([2, 1])
        with cr1: u_rem = st.selectbox("Remover usuário:", l_u, key="sel_r")
        with cr2:
            st.write(""); st.write("")
            if st.button("🗑️ Excluir", key="btn_rem_u"):
                if remover_usuario(u_rem):
                    st.success("✅ Removido!")
                    st.rerun()


--- LOGOUT LATERAL ---

st.sidebar.divider()
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
st.session_state.autenticado = False
st.session_state.usuario_atual = ""
st.session_state.e_admin = False
st.session_state.e_supervisor = False
st.session_state.troca_obrigatoria = False
st.session_state.df_excel_agenda = None
st.rerun()
