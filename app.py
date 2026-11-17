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
    page_title="Sistema Integrado Consigaz", 
    page_icon="⚙️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONEXÃO COM O SUPABASE ---
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

# --- CAMADA DE PERSISTÊNCIA NA NUVEM (SUPABASE) ---
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

# --- FUNÇÕES DE PERSISTÊNCIA: CONTRATOS & VENDAS ---
def formatar_valor_proposta(val_raw):
    txt = " ".join(str(val_raw or "").split()).strip()
    if not txt:
        return ""
    sem_rs = re.sub(r'^r\$\s*', '', txt, flags=re.IGNORECASE).strip()
    if not any(ch.isdigit() for ch in sem_rs):
        return txt
    if re.match(r'^[\d.,]+$', sem_rs):
        try:
            if ',' in sem_rs and '.' in sem_rs:
                num = float(sem_rs.replace('.', '').replace(',', '.'))
            elif ',' in sem_rs:
                num = float(sem_rs.replace(',', '.'))
            elif '.' in sem_rs:
                partes = sem_rs.split('.')
                if len(partes[-1]) == 3 and len(partes) > 1:
                    num = float(sem_rs.replace('.', ''))
                else:
                    num = float(sem_rs)
            else:
                num = float(sem_rs)
            formatado = f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"R$ {formatado}"
        except ValueError:
            pass
    return f"R$ {sem_rs}"

def carregar_acompanhamento(usuario, tipo):
    try:
        res = supabase.table("acompanhamento").select("*").eq("usuario", usuario).eq("tipo", tipo).execute()
        dados = {}
        cache_vig = st.session_state.get("vigencia_local_cache", {})
        cache_val = st.session_state.get("valor_proposta_local_cache", {})
        cache_com = st.session_state.get("comissao_local_cache", {})
        for row in res.data:
            if row.get("vigencia") is None:
                row["vigencia"] = cache_vig.get(row["id"], "")
            if row.get("valor_proposta") is None:
                row["valor_proposta"] = cache_val.get(row["id"], "")
            if row.get("comissao") is None:
                row["comissao"] = cache_com.get(row["id"], "")
            dados[row["id"]] = row
        return dados
    except Exception:
        return {}

def salvar_acompanhamento(id_reg, usuario, tipo, codigo_cliente, nome_cliente, status, ano, mes, observacoes="", vigencia="", valor_proposta="", comissao=""):
    data_mod = datetime.now().strftime("%d/%m/%Y %H:%M")
    payload = {
        "id": id_reg,
        "usuario": usuario,
        "tipo": tipo,
        "codigo_cliente": codigo_cliente,
        "nome_cliente": nome_cliente,
        "status": status,
        "ano": int(ano),
        "mes": int(mes),
        "observacoes": observacoes,
        "vigencia": vigencia,
        "valor_proposta": valor_proposta,
        "comissao": comissao,
        "data_modificacao": data_mod
    }
    try:
        supabase.table("acompanhamento").upsert(payload).execute()
        if "vigencia_local_cache" in st.session_state:
            st.session_state["vigencia_local_cache"].pop(id_reg, None)
        if "valor_proposta_local_cache" in st.session_state:
            st.session_state["valor_proposta_local_cache"].pop(id_reg, None)
        if "comissao_local_cache" in st.session_state:
            st.session_state["comissao_local_cache"].pop(id_reg, None)
        return True
    except Exception as e:
        err_str = str(e)
        if "42501" in err_str or "row-level security" in err_str.lower():
            st.error("❌ Permissão bloqueada no Supabase (RLS ativo). Execute no SQL Editor do Supabase: `ALTER TABLE acompanhamento DISABLE ROW LEVEL SECURITY;`")
            return False
        # Tenta salvar sem 'comissao' caso a coluna ainda não exista
        try:
            payload_sem_com = {k: v for k, v in payload.items() if k != "comissao"}
            supabase.table("acompanhamento").upsert(payload_sem_com).execute()
            if "vigencia_local_cache" in st.session_state:
                st.session_state["vigencia_local_cache"].pop(id_reg, None)
            if "valor_proposta_local_cache" in st.session_state:
                st.session_state["valor_proposta_local_cache"].pop(id_reg, None)
            st.session_state.setdefault("comissao_local_cache", {})[id_reg] = comissao
            if str(comissao).strip():
                st.warning("⚠️ Cliente salvo, mas a coluna 'comissao' ainda não existe no Supabase. Execute no SQL Editor: `ALTER TABLE acompanhamento ADD COLUMN IF NOT EXISTS comissao TEXT;`")
            return True
        except Exception:
            pass
        # Tenta salvar sem 'valor_proposta' e 'comissao' caso ainda não existam
        try:
            payload_sem_val = {k: v for k, v in payload.items() if k not in ["valor_proposta", "comissao"]}
            supabase.table("acompanhamento").upsert(payload_sem_val).execute()
            if "vigencia_local_cache" in st.session_state:
                st.session_state["vigencia_local_cache"].pop(id_reg, None)
            st.session_state.setdefault("valor_proposta_local_cache", {})[id_reg] = valor_proposta
            st.session_state.setdefault("comissao_local_cache", {})[id_reg] = comissao
            colunas_faltando = []
            if str(valor_proposta).strip():
                colunas_faltando.append("ADD COLUMN IF NOT EXISTS valor_proposta TEXT")
            if str(comissao).strip():
                colunas_faltando.append("ADD COLUMN IF NOT EXISTS comissao TEXT")
            if colunas_faltando:
                st.warning(f"⚠️ Cliente salvo, mas faltam colunas no Supabase. Execute no SQL Editor: `ALTER TABLE acompanhamento {', '.join(colunas_faltando)};`")
            return True
        except Exception:
            pass
        # Tenta salvar sem 'vigencia', 'valor_proposta' e 'comissao'
        try:
            payload_sem_extras = {k: v for k, v in payload.items() if k not in ["vigencia", "valor_proposta", "comissao"]}
            supabase.table("acompanhamento").upsert(payload_sem_extras).execute()
            st.session_state.setdefault("vigencia_local_cache", {})[id_reg] = vigencia
            st.session_state.setdefault("valor_proposta_local_cache", {})[id_reg] = valor_proposta
            st.session_state.setdefault("comissao_local_cache", {})[id_reg] = comissao
            colunas_faltando = []
            if str(vigencia).strip():
                colunas_faltando.append("ADD COLUMN IF NOT EXISTS vigencia TEXT")
            if str(valor_proposta).strip():
                colunas_faltando.append("ADD COLUMN IF NOT EXISTS valor_proposta TEXT")
            if str(comissao).strip():
                colunas_faltando.append("ADD COLUMN IF NOT EXISTS comissao TEXT")
            if colunas_faltando:
                st.warning(f"⚠️ Cliente salvo, mas faltam colunas no Supabase. Execute no SQL Editor: `ALTER TABLE acompanhamento {', '.join(colunas_faltando)};`")
            return True
        except Exception:
            try:
                payload_fallback = {k: v for k, v in payload.items() if k not in ["observacoes", "nome_cliente", "vigencia", "valor_proposta", "comissao"]}
                supabase.table("acompanhamento").upsert(payload_fallback).execute()
                st.session_state.setdefault("vigencia_local_cache", {})[id_reg] = vigencia
                st.session_state.setdefault("valor_proposta_local_cache", {})[id_reg] = valor_proposta
                st.session_state.setdefault("comissao_local_cache", {})[id_reg] = comissao
                st.warning("⚠️ Cliente salvo parcialmente. Adicione as colunas 'observacoes', 'nome_cliente', 'vigencia', 'valor_proposta' e 'comissao' no Supabase executando um ALTER TABLE.")
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


# --- CONSULTA CNPJ & IPCA ---
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
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            match = re.search(r'IPCA\s+acumulado\s+de\s+12\s+meses.*?([0-9]+,[0-9]+)\s*%', resp.text, re.IGNORECASE | re.DOTALL)
            if match:
                return float(match.group(1).replace(",", ".")), "IBGE (Web)"
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


# --- LEITOR ROBUSTO DE ARQUIVOS (EXCEL / HTML) ---
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
        table_match = re.search(r'<table[^>]*>(.*?)</table>', html_text, re.DOTALL | re.IGNORECASE)
        if not table_match:
            raise ValueError("Nenhuma tabela HTML encontrada.")
        table_content = table_match.group(1)
        rows = []
        for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_content, re.DOTALL | re.IGNORECASE):
            row_content = row_match.group(1)
            cells = []
            for cell_match in re.finditer(r'<t[dh][^>]*>(.*?)</t[dh]>', row_content, re.DOTALL | re.IGNORECASE):
                cell_text = cell_match.group(1)
                cell_text = re.sub(r'<[^>]+>', '', cell_text)
                cell_text = cell_text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
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
        df = pd.DataFrame(data_rows, columns=header)
        return df
    except Exception as e:
        raise ValueError(f"Formato de arquivo não suportado ou corrompido. Erro interno: {e}")


# --- GERADOR DE PDF DE RELATÓRIO FOTOGRÁFICO ---
class RelatorioPDF(FPDF):
    def __init__(self, cod_cliente="", nome_cliente="", logo_path=""):
        super().__init__()
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
            self.set_y(30)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

# --- AUXILIARES E VISUAL ---
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(DIRETORIO_ATUAL, "logo.png")

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

div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
    position: sticky !important;
    top: 0px !important;
    z-index: 9999 !important;
    background-color: #F1F5FA !important;
    padding-top: 15px !important;
    padding-bottom: 10px !important;
    border-bottom: 1px solid #E2E8F0;
}

.block-container, [data-testid="stMainBlockContainer"] {
  max-width: 1440px !important;
  margin: 1.2rem auto 2rem auto !important;
  padding: 1.8rem 2.4rem 2.4rem 2.4rem !important;
  background: #FFFFFF !important;
  border-radius: 16px;
  box-shadow: 0 1px 2px rgba(10,37,64,.06), 0 8px 28px rgba(10,37,64,.07);
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
.cg-logo { height: 55px; width: auto; display: block; }
.cg-header-sep { width: 2px; align-self: stretch; background: #E2E8F0; }
.cg-title { font-size: 1.65rem; font-weight: 800; line-height: 1.2; color: #003366 !important; }
.cg-subtitle { font-size: 0.95rem; margin-top: 0.2rem; color: #64748B !important; font-weight: 500; }

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

div.stButton > button {
  width: 100%;
  padding: 0.6rem 0.5rem;
  border-radius: 10px !important;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  transition: all 0.2s ease;
}
div.stButton > button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,85,165,0.15);
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def botao_copiar_customizado(texto_para_copiar, chave_unica, label_btn="📄 Copiar Texto Completo"):
    texto_js = json.dumps(str(texto_para_copiar))
    component_html = f"""
    <div style="margin-top: 5px; margin-bottom: 10px;">
        <button id="btn_{chave_unica}" onclick="copiarTexto_{chave_unica}()" style="
            background-color: #0055A5; color: white; padding: 8px 16px; border: none;
            border-radius: 6px; font-weight: bold; font-size: 14px; cursor: pointer;
            display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">{label_btn}</button>
        <span id="msg_{chave_unica}" style="margin-left: 10px; color: green; font-weight: bold; font-size: 13px; display: none;">Copiado com sucesso!</span>
    </div>
    <script>
    function copiarTexto_{chave_unica}() {{
        const texto = {texto_js};
        navigator.clipboard.writeText(texto).then(function() {{
            const msg = document.getElementById("msg_{chave_unica}");
            msg.style.display = "inline";
            setTimeout(function() {{ msg.style.display = "none"; }}, 2500);
        }}).catch(err => console.error('Erro ao copiar', err));
    }}
    </script>
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
    img_tag = f'<img class="{classe_img}" src="data:image/png;base64,{b64}" alt="Consigaz">'
    return f'<div class="{classe_wrapper}">{img_tag}</div>' if classe_wrapper else img_tag

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

# --- COMPONENTE INTERATIVO DE QUADRO KANBAN COM DRAG & DROP E GRADE SEM ROLAGEM LATERAL ---
def renderizar_kanban_interativo_html(tipo_acompanhamento, cards_por_mes, meses_nomes, id_editando, pending_target_id):
    is_contrato = (tipo_acompanhamento == "contrato")
    colunas_html = ""
    for idx_m, mes_nome in enumerate(meses_nomes):
        mes_num = idx_m + 1
        itens_mes = cards_por_mes.get(mes_num, [])
        qtd_mes = len(itens_mes)
        cards_html = ""
        for item in itens_mes:
            cid = html_lib.escape(str(item["id"]))
            cor = html_lib.escape(str(item["cor"]))
            cod = html_lib.escape(str(item["codigo"]))
            nome = html_lib.escape(str(item["nome"]))
            vig = html_lib.escape(str(item.get("vigencia", "") or "").strip())
            val_prop = html_lib.escape(str(item.get("valor_proposta", "") or "").strip())
            comissao = str(item.get("comissao", "") or "").strip()
            is_selected = "selected-card" if str(item["id"]) == str(id_editando) else ""
            nome_div = f'<div class="kb-card-name">{nome}</div>' if nome else ""

            meta_div = ""
            if is_contrato and vig:
                meta_div = f'<div class="kb-card-meta kb-card-vig">📅 {vig}</div>'
            elif (not is_contrato) and val_prop:
                if comissao == "20%":
                    classe_val = "kb-card-val-verde"
                elif comissao == "10%":
                    classe_val = "kb-card-val-amarelo"
                else:
                    classe_val = "kb-card-val-neutro"
                meta_div = f'<div class="kb-card-meta {classe_val}">💰 {val_prop}</div>'

            cards_html += f"""
            <div class="kb-card {is_selected}" draggable="true" data-id="{cid}"
                 ondragstart="handleDragStart(event, '{cid}')"
                 ondragend="handleDragEnd(event)"
                 onclick="handleCardClick(event, '{cid}')">
                <div class="kb-card-top">{cor} {cod}</div>
                {nome_div}
                {meta_div}
            </div>
            """
        colunas_html += f"""
        <div class="kb-col" data-mes="{mes_num}"
             ondragenter="handleDragEnter(event)"
             ondragover="handleDragOver(event)"
             ondragleave="handleDragLeave(event)"
             ondrop="handleDrop(event, {mes_num})">
            <div class="kb-col-header">
                <span class="kb-col-title">{html_lib.escape(mes_nome)}</span>
                <span class="kb-col-count">{qtd_mes}</span>
            </div>
            <div class="kb-col-body">
                {cards_html}
            </div>
        </div>
        """

    # Calcula altura dinâmica com base nas 2 linhas de 6 meses (Jan-Jun e Jul-Dez)
    max_cards_r1 = max((len(cards_por_mes.get(m, [])) for m in range(1, 7)), default=0)
    max_cards_r2 = max((len(cards_por_mes.get(m, [])) for m in range(7, 13)), default=0)
    alt_r1 = max(205, 56 + max_cards_r1 * 78)
    alt_r2 = max(205, 56 + max_cards_r2 * 78)
    altura_iframe = alt_r1 + alt_r2 + 28

    html_board = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        * {{
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        html, body {{
            margin: 0;
            padding: 2px 0 8px 0;
            width: 100%;
            overflow-x: hidden;
            background: transparent;
        }}
        .kb-grid {{
            display: grid;
            grid-template-columns: repeat(6, minmax(0, 1fr));
            gap: 10px;
            width: 100%;
            align-items: stretch;
        }}
        @media (max-width: 1050px) {{
            .kb-grid {{
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }}
        }}
        @media (max-width: 720px) {{
            .kb-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}
        .kb-col {{
            min-width: 0;
            width: 100%;
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 8px 6px;
            min-height: 195px;
            display: flex;
            flex-direction: column;
            transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
        }}
        .kb-col.drag-over {{
            background: #EFF6FF;
            border: 2px dashed #0055A5;
            box-shadow: inset 0 0 0 2px rgba(0, 85, 165, 0.08);
        }}
        .kb-col-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-weight: 700;
            color: #0055A5;
            border-bottom: 2px solid #0055A5;
            padding: 0 3px 5px 3px;
            margin-bottom: 8px;
            font-size: 13.5px;
        }}
        .kb-col-count {{
            background: #E0ECFF;
            color: #004488;
            font-size: 11px;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 999px;
            line-height: 1.3;
        }}
        .kb-col-body {{
            display: flex;
            flex-direction: column;
            gap: 7px;
            flex: 1;
            min-height: 140px;
        }}
        .kb-card {{
            background: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 8px;
            padding: 7px 8px;
            cursor: grab;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
            transition: transform 0.14s ease, box-shadow 0.14s ease, border-color 0.14s ease;
            user-select: none;
            word-wrap: break-word;
            overflow-wrap: break-word;
            white-space: normal;
        }}
        .kb-card * {{
            pointer-events: none;
        }}
        .kb-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,85,165,0.16);
            border-color: #0055A5;
        }}
        .kb-card:active {{
            cursor: grabbing;
        }}
        .kb-card.dragging {{
            opacity: 0.45;
        }}
        .kb-card.selected-card {{
            border: 2px solid #0055A5;
            background-color: #F0F7FF;
        }}
        .kb-card-top {{
            font-weight: 700;
            font-size: 12.5px;
            color: #1B2A3A;
            line-height: 1.25;
        }}
        .kb-card-name {{
            font-weight: 500;
            font-size: 11.5px;
            color: #334155;
            margin-top: 3px;
            line-height: 1.25;
        }}
        .kb-card-meta {{
            margin-top: 5px;
            padding: 2px 5px;
            border-radius: 5px;
            font-size: 10.5px;
            font-weight: 600;
            line-height: 1.25;
            display: inline-block;
            max-width: 100%;
        }}
        .kb-card-vig {{
            background: #EFF6FF;
            color: #0055A5;
            border: 1px solid #BFDBFE;
        }}
        .kb-card-val-verde {{
            background: #DCFCE7;
            color: #15803D;
            border: 1px solid #86EFAC;
        }}
        .kb-card-val-amarelo {{
            background: #FEF9C3;
            color: #A16207;
            border: 1px solid #FDE047;
        }}
        .kb-card-val-neutro {{
            background: #F1F5F9;
            color: #334155;
            border: 1px solid #CBD5E1;
        }}
        .kb-saving-toast {{
            position: fixed;
            bottom: 10px;
            right: 12px;
            background: #0055A5;
            color: #FFFFFF;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(0,0,0,0.18);
            display: none;
            z-index: 9999;
        }}
    </style>
    </head>
    <body>
        <div class="kb-grid" id="kb-grid">
            {colunas_html}
        </div>
        <div class="kb-saving-toast" id="kb-saving-toast">💾 Salvando alteração...</div>
        <script>
            let draggedId = null;
            let isDragging = false;

            function showSavingToast() {{
                const t = document.getElementById("kb-saving-toast");
                if (t) t.style.display = "block";
            }}

            function sendToStreamlit(payload) {{
                const doc = window.parent.document;
                const inputs = doc.querySelectorAll('input[aria-label="kb_bridge_{tipo_acompanhamento}"]');
                const serialized = JSON.stringify(payload);
                inputs.forEach(function(targetInput) {{
                    try {{
                        if (targetInput._valueTracker) {{
                            targetInput._valueTracker.setValue("");
                        }}
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        nativeInputValueSetter.call(targetInput, serialized);
                        targetInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        targetInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        targetInput.dispatchEvent(new KeyboardEvent('keydown', {{
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true,
                            cancelable: true
                        }}));
                        targetInput.dispatchEvent(new KeyboardEvent('keyup', {{
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true
                        }}));
                        targetInput.dispatchEvent(new FocusEvent('blur', {{ bubbles: true }}));
                    }} catch (err) {{
                        console.error("Erro ao comunicar com Streamlit:", err);
                    }}
                }});
            }}

            function handleDragStart(e, id) {{
                isDragging = true;
                draggedId = id;
                if (e.dataTransfer) {{
                    e.dataTransfer.setData("text/plain", id);
                    e.dataTransfer.effectAllowed = "move";
                }}
                setTimeout(() => {{
                    if (e.target) e.target.classList.add("dragging");
                }}, 0);
            }}

            function handleDragEnd(e) {{
                if (e.target) e.target.classList.remove("dragging");
                document.querySelectorAll('.kb-col').forEach(c => c.classList.remove('drag-over'));
                setTimeout(() => {{ isDragging = false; }}, 80);
            }}

            function handleDragEnter(e) {{
                e.preventDefault();
                e.currentTarget.classList.add("drag-over");
            }}

            function handleDragOver(e) {{
                e.preventDefault();
                if (e.dataTransfer) {{
                    e.dataTransfer.dropEffect = "move";
                }}
                e.currentTarget.classList.add("drag-over");
            }}

            function handleDragLeave(e) {{
                if (!e.currentTarget.contains(e.relatedTarget)) {{
                    e.currentTarget.classList.remove("drag-over");
                }}
            }}

            function handleDrop(e, novoMes) {{
                e.preventDefault();
                e.stopPropagation();
                e.currentTarget.classList.remove("drag-over");
                const id = (e.dataTransfer ? e.dataTransfer.getData("text/plain") : "") || draggedId;
                draggedId = null;
                if (id) {{
                    showSavingToast();
                    sendToStreamlit({{
                        action: "move",
                        id: id,
                        mes: novoMes,
                        ts: Date.now()
                    }});
                }}
            }}

            function handleCardClick(e, id) {{
                if (isDragging) return;
                sendToStreamlit({{
                    action: "select",
                    id: id,
                    ts: Date.now()
                }});
            }}
        </script>
    </body>
    </html>
    """
    components.html(html_board, height=altura_iframe, scrolling=False)

# --- HELPERS DE CONSOLIDAÇÃO DE CONTRATOS POR VIGÊNCIA E TRIMESTRE ---
def normalizar_vigencia_label(vig_raw):
    txt = " ".join(str(vig_raw or "").split()).strip()
    if not txt:
        return "Não informada"
    m = re.match(r"^(\d+)\s*(?:m[eê]s(?:es)?)?$", txt, flags=re.IGNORECASE)
    if m:
        qtd = int(m.group(1))
        return f"{qtd} mês" if qtd == 1 else f"{qtd} meses"
    return txt

def _ordenacao_vigencia_key(vig_label):
    if vig_label == "Não informada":
        return (2, 0, "")
    m = re.match(r"^(\d+)\s*m[eê]s(?:es)?$", vig_label, flags=re.IGNORECASE)
    if m:
        return (0, int(m.group(1)), vig_label.lower())
    return (1, 0, vig_label.lower())

def renderizar_consolidado_contratos_vigencia(dados, ano_selecionado):
    trimestres_cols = [
        "1º Tri (Jan, Fev, Mar)",
        "2º Tri (Abr, Mai, Jun)",
        "3º Tri (Jul, Ago, Set)",
        "4º Tri (Out, Nov, Dez)"
    ]
    contagem_por_vigencia = {}
    totais_tri = {t: 0 for t in trimestres_cols}

    for d in dados.values():
        if not isinstance(d, dict):
            continue
        if d.get("ano") != ano_selecionado:
            continue
        if str(d.get("status", "")).strip() != "Processo Enviado":
            continue
        try:
            mes_num = int(d.get("mes", 0))
        except (TypeError, ValueError):
            continue
        if not (1 <= mes_num <= 12):
            continue

        if mes_num in (1, 2, 3):
            tri_nome = trimestres_cols[0]
        elif mes_num in (4, 5, 6):
            tri_nome = trimestres_cols[1]
        elif mes_num in (7, 8, 9):
            tri_nome = trimestres_cols[2]
        else:
            tri_nome = trimestres_cols[3]

        vig_label = normalizar_vigencia_label(d.get("vigencia", ""))
        if vig_label not in contagem_por_vigencia:
            contagem_por_vigencia[vig_label] = {t: 0 for t in trimestres_cols}

        contagem_por_vigencia[vig_label][tri_nome] += 1
        totais_tri[tri_nome] += 1

    st.divider()
    st.markdown(f"### 📊 Consolidado — Contratos \"Processo Enviado\" por Vigência ({ano_selecionado})")
    st.caption("Quantidade de contratos no status **Processo Enviado** agrupados por vigência e trimestre.")

    total_geral = sum(totais_tri.values())
    c_k1, c_k2, c_k3, c_k4, c_k5 = st.columns(5)
    c_k1.metric("1º Tri (Jan-Mar)", totais_tri[trimestres_cols[0]])
    c_k2.metric("2º Tri (Abr-Jun)", totais_tri[trimestres_cols[1]])
    c_k3.metric("3º Tri (Jul-Set)", totais_tri[trimestres_cols[2]])
    c_k4.metric("4º Tri (Out-Dez)", totais_tri[trimestres_cols[3]])
    c_k5.metric("Total Enviado", total_geral)

    if not contagem_por_vigencia:
        st.info(f"Nenhum contrato com status 'Processo Enviado' encontrado para o ano de {ano_selecionado}.")
        return

    linhas_tabela = []
    for vig_label in sorted(contagem_por_vigencia.keys(), key=_ordenacao_vigencia_key):
        valores = contagem_por_vigencia[vig_label]
        total_linha = sum(valores.values())
        linhas_tabela.append({
            "Vigência": vig_label,
            trimestres_cols[0]: valores[trimestres_cols[0]],
            trimestres_cols[1]: valores[trimestres_cols[1]],
            trimestres_cols[2]: valores[trimestres_cols[2]],
            trimestres_cols[3]: valores[trimestres_cols[3]],
            "Total": total_linha
        })

    linhas_tabela.append({
        "Vigência": "Total Geral",
        trimestres_cols[0]: totais_tri[trimestres_cols[0]],
        trimestres_cols[1]: totais_tri[trimestres_cols[1]],
        trimestres_cols[2]: totais_tri[trimestres_cols[2]],
        trimestres_cols[3]: totais_tri[trimestres_cols[3]],
        "Total": total_geral
    })

    df_consolidado = pd.DataFrame(linhas_tabela)
    st.dataframe(df_consolidado, hide_index=True, use_container_width=True)

# --- GERENCIADOR DO PAINEL KANBAN (CONTRATOS E VENDAS) COM ESTILO VISUAL ---
def renderizar_painel_acompanhamento(tipo_acompanhamento, lista_status, dict_cores):
    usuario = st.session_state.usuario_atual
    dados = carregar_acompanhamento(usuario, tipo_acompanhamento)
    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    anos_lista = [2024, 2025, 2026, 2027, 2028, 2029, 2030]
    is_contrato = (tipo_acompanhamento == "contrato")

    key_edit_id = f"edit_id_{tipo_acompanhamento}"
    key_pending_id = f"pending_select_id_{tipo_acompanhamento}"
    key_last_bridge_ts = f"last_bridge_ts_{tipo_acompanhamento}"
    key_bridge_input = f"kb_bridge_input_{tipo_acompanhamento}"

    if key_edit_id not in st.session_state:
        st.session_state[key_edit_id] = None
    if key_pending_id not in st.session_state:
        st.session_state[key_pending_id] = None
    if key_last_bridge_ts not in st.session_state:
        st.session_state[key_last_bridge_ts] = 0

    # Input oculto que recebe os eventos de clique e drag-and-drop do quadro interativo
    st.markdown(
        f"""
        <style>
        div[data-testid="stTextInput"]:has(input[aria-label="kb_bridge_{tipo_acompanhamento}"]) {{
            position: fixed;
            left: -9999px;
            top: -9999px;
            width: 1px;
            height: 1px;
            opacity: 0;
            pointer-events: none;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    bridge_raw = st.text_input(
        f"kb_bridge_{tipo_acompanhamento}",
        key=key_bridge_input,
        label_visibility="collapsed"
    )

    if bridge_raw:
        try:
            evt = json.loads(bridge_raw)
            evt_ts = evt.get("ts", 0)
            if evt_ts and evt_ts != st.session_state[key_last_bridge_ts]:
                st.session_state[key_last_bridge_ts] = evt_ts
                action = evt.get("action")
                target_id = evt.get("id")

                if action == "move" and target_id in dados:
                    novo_mes = int(evt.get("mes", dados[target_id]["mes"]))
                    reg_atual = dados[target_id]
                    if int(reg_atual["mes"]) != novo_mes:
                        ok_move = salvar_acompanhamento(
                            target_id,
                            usuario,
                            tipo_acompanhamento,
                            reg_atual["codigo_cliente"],
                            reg_atual.get("nome_cliente", ""),
                            reg_atual["status"],
                            int(reg_atual["ano"]),
                            novo_mes,
                            reg_atual.get("observacoes", ""),
                            reg_atual.get("vigencia", ""),
                            reg_atual.get("valor_proposta", ""),
                            reg_atual.get("comissao", "")
                        )
                        if ok_move:
                            if st.session_state[key_edit_id] == target_id:
                                st.session_state[f"ed_ms_{tipo_acompanhamento}_{target_id}"] = meses_nomes[novo_mes - 1]
                            st.rerun()

                elif action == "select" and target_id in dados:
                    curr_edit = st.session_state[key_edit_id]
                    if curr_edit is None or curr_edit == target_id or curr_edit not in dados:
                        st.session_state[key_edit_id] = target_id
                        st.session_state[key_pending_id] = None
                        st.rerun()
                    else:
                        # Verifica se houve alguma alteração nos campos do cliente atualmente selecionado
                        d_curr = dados[curr_edit]
                        val_cod = st.session_state.get(f"ed_cod_{tipo_acompanhamento}_{curr_edit}", d_curr["codigo_cliente"])
                        val_nom = st.session_state.get(f"ed_nom_{tipo_acompanhamento}_{curr_edit}", d_curr.get("nome_cliente", ""))
                        val_st = st.session_state.get(f"ed_st_{tipo_acompanhamento}_{curr_edit}", d_curr["status"])
                        val_ano = st.session_state.get(f"ed_ano_{tipo_acompanhamento}_{curr_edit}", int(d_curr["ano"]))
                        idx_ms_orig = int(d_curr["mes"]) - 1 if 1 <= int(d_curr["mes"]) <= 12 else 0
                        val_ms = st.session_state.get(f"ed_ms_{tipo_acompanhamento}_{curr_edit}", meses_nomes[idx_ms_orig])
                        val_obs = st.session_state.get(f"ed_obs_{tipo_acompanhamento}_{curr_edit}", d_curr.get("observacoes", ""))
                        val_vig = st.session_state.get(f"ed_vig_{tipo_acompanhamento}_{curr_edit}", d_curr.get("vigencia", "") or "")
                        val_prop = st.session_state.get(f"ed_val_prop_{tipo_acompanhamento}_{curr_edit}", d_curr.get("valor_proposta", "") or "")
                        val_com = st.session_state.get(f"ed_comissao_{tipo_acompanhamento}_{curr_edit}", d_curr.get("comissao", "") or "") or ""

                        vig_alterada = is_contrato and (str(val_vig).strip() != str(d_curr.get("vigencia", "") or "").strip())
                        prop_alterada = (not is_contrato) and (str(val_prop).strip() != str(d_curr.get("valor_proposta", "") or "").strip())
                        com_alterada = (not is_contrato) and (str(val_com).strip() != str(d_curr.get("comissao", "") or "").strip())

                        houve_alteracao = (
                            str(val_cod).strip() != str(d_curr["codigo_cliente"]).strip()
                            or str(val_nom).strip() != str(d_curr.get("nome_cliente", "")).strip()
                            or str(val_st) != str(d_curr["status"])
                            or int(val_ano) != int(d_curr["ano"])
                            or (meses_nomes.index(val_ms) + 1) != int(d_curr["mes"])
                            or str(val_obs).strip() != str(d_curr.get("observacoes", "")).strip()
                            or vig_alterada
                            or prop_alterada
                            or com_alterada
                        )

                        if houve_alteracao:
                            st.session_state[key_pending_id] = target_id
                            st.rerun()
                        else:
                            st.session_state[key_edit_id] = target_id
                            st.session_state[key_pending_id] = None
                            st.rerun()
        except Exception:
            pass

    col_menu_ac, col_conteudo_ac = st.columns([1, 4.3])
    
    with col_menu_ac:
        st.markdown("### 📌 Filtros")
        ano_selecionado = st.selectbox("📅 Selecione o Ano", anos_lista, index=2, key=f"ano_sel_{tipo_acompanhamento}")
        filtro_status = st.selectbox("🏷️ Filtrar por Status", ["Todos"] + lista_status, key=f"filtro_st_{tipo_acompanhamento}")
        
        st.divider()
        st.markdown("### 🚦 Legenda de Status")
        for st_name in lista_status:
            cor = dict_cores.get(st_name, "⚪")
            st.markdown(f"{cor} **{st_name}**")

    with col_conteudo_ac:
        id_editando = st.session_state[key_edit_id]
        pending_id = st.session_state[key_pending_id]

        if id_editando and id_editando in dados:
            d_edit = dados[id_editando]

            # Caixa de aviso quando há alterações pendentes e o usuário clicou em outro cliente
            if pending_id and pending_id in dados and pending_id != id_editando:
                d_prox = dados[pending_id]
                st.warning(
                    f"⚠️ **Alterações não salvas!** Você modificou os dados do cliente **{d_edit['codigo_cliente']} - {d_edit.get('nome_cliente', '')}**. "
                    f"Deseja salvar as alterações antes de abrir o cliente **{d_prox['codigo_cliente']} - {d_prox.get('nome_cliente', '')}**?"
                )
                col_av1, col_av2, col_av3, _ = st.columns([2.3, 2.3, 2.3, 3.1])
                if col_av1.button("💾 Salvar e Trocar", type="primary", use_container_width=True, key=f"av_salv_{tipo_acompanhamento}"):
                    ed_cod_cur = st.session_state.get(f"ed_cod_{tipo_acompanhamento}_{id_editando}", d_edit["codigo_cliente"])
                    ed_nom_cur = st.session_state.get(f"ed_nom_{tipo_acompanhamento}_{id_editando}", d_edit.get("nome_cliente", ""))
                    ed_st_cur = st.session_state.get(f"ed_st_{tipo_acompanhamento}_{id_editando}", d_edit["status"])
                    ed_ano_cur = st.session_state.get(f"ed_ano_{tipo_acompanhamento}_{id_editando}", int(d_edit["ano"]))
                    idx_ms_cur = int(d_edit["mes"]) - 1 if 1 <= int(d_edit["mes"]) <= 12 else 0
                    ed_ms_cur = st.session_state.get(f"ed_ms_{tipo_acompanhamento}_{id_editando}", meses_nomes[idx_ms_cur])
                    ed_obs_cur = st.session_state.get(f"ed_obs_{tipo_acompanhamento}_{id_editando}", d_edit.get("observacoes", ""))
                    ed_vig_cur = st.session_state.get(f"ed_vig_{tipo_acompanhamento}_{id_editando}", d_edit.get("vigencia", "") or "") if is_contrato else ""
                    ed_val_cur = formatar_valor_proposta(st.session_state.get(f"ed_val_prop_{tipo_acompanhamento}_{id_editando}", d_edit.get("valor_proposta", "") or "")) if not is_contrato else ""
                    ed_com_cur = (st.session_state.get(f"ed_comissao_{tipo_acompanhamento}_{id_editando}", d_edit.get("comissao", "") or "") or "") if not is_contrato else ""

                    if salvar_acompanhamento(
                        id_editando,
                        usuario,
                        tipo_acompanhamento,
                        str(ed_cod_cur).strip(),
                        str(ed_nom_cur).strip(),
                        ed_st_cur,
                        int(ed_ano_cur),
                        meses_nomes.index(ed_ms_cur) + 1,
                        str(ed_obs_cur),
                        str(ed_vig_cur).strip(),
                        ed_val_cur,
                        str(ed_com_cur).strip()
                    ):
                        st.session_state[key_edit_id] = pending_id
                        st.session_state[key_pending_id] = None
                        st.rerun()

                if col_av2.button("🗑️ Descartar e Trocar", use_container_width=True, key=f"av_desc_{tipo_acompanhamento}"):
                    for k_pfx in ["ed_cod", "ed_nom", "ed_st", "ed_ano", "ed_ms", "ed_vig", "ed_val_prop", "ed_comissao", "ed_obs"]:
                        st.session_state.pop(f"{k_pfx}_{tipo_acompanhamento}_{id_editando}", None)
                    st.session_state[key_edit_id] = pending_id
                    st.session_state[key_pending_id] = None
                    st.rerun()

                if col_av3.button("↩️ Continuar Editando", use_container_width=True, key=f"av_cont_{tipo_acompanhamento}"):
                    st.session_state[key_pending_id] = None
                    st.rerun()

            st.markdown("### ✏️ Edição de Cliente")
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 3, 3])
                with c1:
                    ed_cod = st.text_input("Código do Cliente", value=d_edit['codigo_cliente'], key=f"ed_cod_{tipo_acompanhamento}_{id_editando}")
                with c2:
                    ed_nome = st.text_input("Nome do Cliente", value=d_edit.get('nome_cliente', ''), key=f"ed_nom_{tipo_acompanhamento}_{id_editando}")
                with c3: 
                    idx_st = lista_status.index(d_edit['status']) if d_edit['status'] in lista_status else 0
                    ed_status = st.selectbox("Status", lista_status, index=idx_st, key=f"ed_st_{tipo_acompanhamento}_{id_editando}")
                
                anos_ed_opcoes = sorted(list(set(anos_lista + [int(d_edit['ano'])])))
                idx_ano_ed = anos_ed_opcoes.index(int(d_edit['ano']))
                idx_ms = int(d_edit['mes']) - 1 if 1 <= int(d_edit['mes']) <= 12 else 0

                if is_contrato:
                    c4, c5, c6, c7 = st.columns([1.6, 1.8, 2.2, 3.4])
                    with c4:
                        ed_ano = st.selectbox("Ano", anos_ed_opcoes, index=idx_ano_ed, key=f"ed_ano_{tipo_acompanhamento}_{id_editando}")
                    with c5:
                        ed_mes = st.selectbox("Mês de Alocação", meses_nomes, index=idx_ms, key=f"ed_ms_{tipo_acompanhamento}_{id_editando}")
                    with c6:
                        ed_vig = st.text_input("Vigência", value=d_edit.get('vigencia', '') or '', placeholder="Ex: 60 meses", key=f"ed_vig_{tipo_acompanhamento}_{id_editando}")
                    with c7:
                        ed_obs = st.text_input("Observações", value=d_edit.get('observacoes', ''), key=f"ed_obs_{tipo_acompanhamento}_{id_editando}")
                    ed_val_prop = ""
                    ed_comissao = ""
                else:
                    c4, c5, c6, c7 = st.columns([1.5, 1.8, 2.5, 2.2])
                    with c4:
                        ed_ano = st.selectbox("Ano", anos_ed_opcoes, index=idx_ano_ed, key=f"ed_ano_{tipo_acompanhamento}_{id_editando}")
                    with c5: 
                        ed_mes = st.selectbox("Mês de Alocação", meses_nomes, index=idx_ms, key=f"ed_ms_{tipo_acompanhamento}_{id_editando}")
                    with c6:
                        ed_val_prop = st.text_input("Valor da Proposta (R$)", value=d_edit.get('valor_proposta', '') or '', placeholder="Ex: R$ 15.000,00", key=f"ed_val_prop_{tipo_acompanhamento}_{id_editando}")
                    with c7:
                        com_atual = str(d_edit.get('comissao', '') or '').strip()
                        opcoes_com = ["20%", "10%"]
                        idx_com = opcoes_com.index(com_atual) if com_atual in opcoes_com else None
                        ed_comissao = st.radio("Comissão", opcoes_com, index=idx_com, horizontal=True, key=f"ed_comissao_{tipo_acompanhamento}_{id_editando}")
                    ed_obs = st.text_input("Observações", value=d_edit.get('observacoes', ''), key=f"ed_obs_{tipo_acompanhamento}_{id_editando}")
                    ed_vig = ""
                
                b1, b2, b3, _ = st.columns([2, 2, 2, 4])
                if b1.button("💾 Salvar Alterações", type="primary", use_container_width=True, key=f"ed_salv_{tipo_acompanhamento}"):
                    val_prop_salv = formatar_valor_proposta(ed_val_prop) if not is_contrato else ""
                    com_salv = (ed_comissao or "").strip() if not is_contrato else ""
                    if salvar_acompanhamento(
                        id_editando,
                        usuario,
                        tipo_acompanhamento,
                        ed_cod.strip(),
                        ed_nome.strip(),
                        ed_status,
                        int(ed_ano),
                        meses_nomes.index(ed_mes) + 1,
                        ed_obs,
                        ed_vig.strip() if is_contrato else "",
                        val_prop_salv,
                        com_salv
                    ):
                        st.session_state[key_edit_id] = None
                        st.session_state[key_pending_id] = None
                        st.rerun()
                if b2.button("❌ Cancelar", use_container_width=True, key=f"ed_canc_{tipo_acompanhamento}"):
                    for k_pfx in ["ed_cod", "ed_nom", "ed_st", "ed_ano", "ed_ms", "ed_vig", "ed_val_prop", "ed_comissao", "ed_obs"]:
                        st.session_state.pop(f"{k_pfx}_{tipo_acompanhamento}_{id_editando}", None)
                    st.session_state[key_edit_id] = None
                    st.session_state[key_pending_id] = None
                    st.rerun()
                if b3.button("🗑️ Excluir Cliente", use_container_width=True, key=f"ed_del_{tipo_acompanhamento}"):
                    apagar_acompanhamento(id_editando)
                    st.session_state[key_edit_id] = None
                    st.session_state[key_pending_id] = None
                    st.rerun()
            st.divider()

        with st.expander("➕ Adicionar Novo Cliente", expanded=False):
            c_cod, c_nom, c_st, c_mes = st.columns([2, 3, 3, 2])
            with c_cod: novo_cod = st.text_input("Código", key=f"n_cod_{tipo_acompanhamento}")
            with c_nom: novo_nome = st.text_input("Nome do Cliente", key=f"n_nom_{tipo_acompanhamento}")
            with c_st: novo_st = st.selectbox("Status Inicial", lista_status, key=f"n_st_{tipo_acompanhamento}")
            with c_mes: novo_ms = st.selectbox("Mês de Alocação", meses_nomes, key=f"n_ms_{tipo_acompanhamento}")

            if is_contrato:
                c_vig, c_obs, c_btn = st.columns([2, 4, 1.2])
                with c_vig: novo_vig = st.text_input("Vigência", placeholder="Ex: 60 meses", key=f"n_vig_{tipo_acompanhamento}")
                with c_obs: novo_obs = st.text_input("Observações", placeholder="Detalhes ou anotações...", key=f"n_obs_{tipo_acompanhamento}")
                with c_btn:
                    st.write(""); st.write("")
                    if st.button("Adicionar", key=f"btn_add_{tipo_acompanhamento}", type="primary", use_container_width=True):
                        if novo_cod.strip() and novo_nome.strip():
                            novo_id = str(uuid.uuid4())
                            if salvar_acompanhamento(novo_id, usuario, tipo_acompanhamento, novo_cod.strip(), novo_nome.strip(), novo_st, ano_selecionado, meses_nomes.index(novo_ms) + 1, novo_obs.strip(), novo_vig.strip(), "", ""):
                                st.rerun()
                        else:
                            st.warning("⚠️ Informe o código e o nome do cliente.")
            else:
                c_val, c_com, c_obs, c_btn = st.columns([2.2, 2.0, 3.3, 1.3])
                with c_val: novo_val_prop = st.text_input("Valor da Proposta (R$)", placeholder="Ex: R$ 15.000,00", key=f"n_val_prop_{tipo_acompanhamento}")
                with c_com: novo_comissao = st.radio("Comissão", ["20%", "10%"], horizontal=True, index=None, key=f"n_comissao_{tipo_acompanhamento}")
                with c_obs: novo_obs = st.text_input("Observações", placeholder="Detalhes ou anotações...", key=f"n_obs_{tipo_acompanhamento}")
                with c_btn:
                    st.write(""); st.write("")
                    if st.button("Adicionar", key=f"btn_add_{tipo_acompanhamento}", type="primary", use_container_width=True):
                        if novo_cod.strip() and novo_nome.strip():
                            novo_id = str(uuid.uuid4())
                            val_prop_fmt = formatar_valor_proposta(novo_val_prop)
                            com_fmt = (novo_comissao or "").strip()
                            if salvar_acompanhamento(novo_id, usuario, tipo_acompanhamento, novo_cod.strip(), novo_nome.strip(), novo_st, ano_selecionado, meses_nomes.index(novo_ms) + 1, novo_obs.strip(), "", val_prop_fmt, com_fmt):
                                st.rerun()
                        else:
                            st.warning("⚠️ Informe o código e o nome do cliente.")

        st.divider()
        st.caption("💡 Clique em um cartão para editar seus dados (inclusive alterar o ano) ou arraste-o para outra coluna para alterar o mês de alocação.")

        cards_por_mes = {m: [] for m in range(1, 13)}
        for id_reg, d in dados.items():
            if not isinstance(d, dict):
                continue
            if int(d.get('ano', 0)) == ano_selecionado and 1 <= int(d.get('mes', 0)) <= 12:
                if filtro_status != "Todos" and d.get('status') != filtro_status:
                    continue
                cards_por_mes[int(d['mes'])].append({
                    "id": id_reg,
                    "cor": dict_cores.get(d.get('status', ''), "⚪"),
                    "codigo": d.get('codigo_cliente', ''),
                    "nome": d.get('nome_cliente', ''),
                    "vigencia": d.get('vigencia', '') or '',
                    "valor_proposta": formatar_valor_proposta(d.get('valor_proposta', '') or ''),
                    "comissao": str(d.get('comissao', '') or '').strip()
                })

        renderizar_kanban_interativo_html(
            tipo_acompanhamento=tipo_acompanhamento,
            cards_por_mes=cards_por_mes,
            meses_nomes=meses_nomes,
            id_editando=id_editando,
            pending_target_id=pending_id
        )

        if is_contrato:
            renderizar_consolidado_contratos_vigencia(dados, ano_selecionado)

# --- GERENCIAMENTO DE ESTADO DE AUTENTICAÇÃO E SESSÃO ---
if "autenticado" not in st.session_state: st.session_state.autenticado = False
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = ""
if "e_admin" not in st.session_state: st.session_state.e_admin = False
if "e_supervisor" not in st.session_state: st.session_state.e_supervisor = False
if "troca_obrigatoria" not in st.session_state: st.session_state.troca_obrigatoria = False
if "filtro_dashboard_ativo" not in st.session_state: st.session_state.filtro_dashboard_ativo = "Todas"
if "ultimo_usuario_logado" not in st.session_state: st.session_state.ultimo_usuario_logado = ""
if "df_excel_agenda" not in st.session_state: st.session_state.df_excel_agenda = None

if "equipamentos" not in st.session_state: st.session_state.equipamentos = []
if "last_central" not in st.session_state: st.session_state.last_central = "Central"
if "reset_counter" not in st.session_state: st.session_state.reset_counter = 0
if "reset_counter_contrato" not in st.session_state: st.session_state.reset_counter_contrato = 0
if "reset_counter_fc" not in st.session_state: st.session_state.reset_counter_fc = 0


# =====================================================================
# TELA DE AUTENTICAÇÃO E TROCA OBRIGATÓRIA DE SENHA
# =====================================================================
banco_usuarios = carregar_banco_usuarios()

if not st.session_state.autenticado:
    side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
    st.sidebar.markdown(
        f'<div class="cg-side-brand">{side_logo_html}'
        f'<div class="cg-side-name">Sistema Integrado</div></div>',
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
    cabecalho_pagina("🔑 Alteração Obrigatória de Senha", "Sua conta está utilizando a senha temporária. Defina sua nova senha pessoal para prosseguir.")
    
    with st.form("form_troca_senha_obrigat"):
        nova_s1 = st.text_input("Nova Senha Pessoal *", type="password").strip()
        nova_s2 = st.text_input("Confirme a Nova Senha *", type="password").strip()
        btn_mudar_obrigat = st.form_submit_button("🔒 Salvar Nova Senha e Acessar", type="primary")
        
        if btn_mudar_obrigat:
            if not nova_s1 or not nova_s2:
                st.error("⚠️ Preencha ambos os campos de senha.")
            elif nova_s1 == "123456":
                st.error("⚠️ Escolha uma senha diferente da senha inicial '123456'.")
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

# =====================================================================
# SISTEMA AUTENTICADO & ABAS SUPERIORES
# =====================================================================
side_logo_html = _logo_html("cg-side-logo", "cg-side-logo-wrapper")
st.sidebar.markdown(
    f'<div class="cg-side-brand">{side_logo_html}'
    f'<div class="cg-side-name">Central de Atendimentos</div></div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown(f"👤 **Usuário Ativo:** `{st.session_state.usuario_atual}`")
if st.session_state.e_admin:
    st.sidebar.caption("⭐ Perfil: Administrador")
elif st.session_state.e_supervisor:
    st.sidebar.caption("📊 Perfil: Supervisor")

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
    aba_tratativa = None
    aba_agenda = None
    aba_contratos = None
    aba_vendas = None
    aba_notas = None
else:
    aba_tratativa = abas_sistema[0]
    aba_agenda = abas_sistema[1]
    aba_contratos = abas_sistema[2]
    aba_vendas = abas_sistema[3]
    aba_notas = abas_sistema[4]
    aba_admin = abas_sistema[5] if st.session_state.e_supervisor else None

if "nota_selecionada_id" not in st.session_state: st.session_state.nota_selecionada_id = None

# =====================================================================
# ABA 1: TRATATIVA DE OCORRÊNCIAS
# =====================================================================
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

            # -------------------------------------------------------------
            # 1. VISITA DE TRANSFERÊNCIA
            # -------------------------------------------------------------
            if menu_tratativa == "📷 Visita de Transferência":
                cabecalho_pagina("Visita de Transferência & Relatório Técnico", "Gerador automatizado de relatórios técnicos, formulários e inspeções fotográficas.")
                
                if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_novo_vis_{rc}"):
                    st.session_state.reset_counter += 1
                    st.session_state.equipamentos = []
                    st.rerun()

                st.divider()
                st.subheader("1. Identificação do Cliente")
                s1_l1_c1, s1_l1_c2, s1_l1_c3 = st.columns(3)
                with s1_l1_c1: cod_cliente = st.text_input("Código do Cliente *", key=f"vis_cod_{rc}")
                with s1_l1_c2: nome_cliente = st.text_input("Nome / Razão Social *", key=f"vis_nome_{rc}")
                with s1_l1_c3: telefone = st.text_input("Telefone *", key=f"vis_tel_{rc}")

                s1_l2_c1, s1_l2_c2, s1_l2_c3 = st.columns(3)
                with s1_l2_c1: contato = st.text_input("Contato *", key=f"vis_cont_{rc}")
                with s1_l2_c2: departamento = st.text_input("Sobrenome ou Departamento *", key=f"vis_dep_{rc}")
                with s1_l2_c3: st.write("")

                st.divider()
                st.subheader("2. Informações Contratuais & Centrais")
                
                qtd_centrais_visita = st.number_input("Quantidade de Centrais no Cliente *", min_value=1, max_value=10, value=1, step=1, key=f"vis_qtd_centrais_{rc}")
                st.write("")

                eq_dict_visita = {}
                if qtd_centrais_visita == 1:
                    col_eq_c1, col_eq_c2 = st.columns(2)
                    with col_eq_c1:
                        eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_cont_{rc}")
                    with col_eq_c2:
                        desc_eq_contrato = st.text_input("Quais equipamentos contratados? *", placeholder="Ex: 01 B190 + 01 CC", key=f"desc_eq_{rc}")
                        eq_dict_visita[1] = desc_eq_contrato
                else:
                    eq_contrato = st.radio("Equipamentos de acordo com contrato? *", ["Sim", "Não"], horizontal=True, index=None, key=f"eq_cont_{rc}")
                    st.markdown("**Equipamentos Contratados por Central:**")
                    cols_cent = st.columns(min(int(qtd_centrais_visita), 3))
                    for i in range(1, int(qtd_centrais_visita) + 1):
                        c_idx = (i - 1) % len(cols_cent)
                        with cols_cent[c_idx]:
                            eq_dict_visita[i] = st.text_input(f"Equipamentos Central {i:02d} *", placeholder="Ex: 01 B190 + 01 CC", key=f"desc_eq_cent_{i}_{rc}")

                st.write("")
                s2_l1_c3, s2_l1_c4 = st.columns(2)
                with s2_l1_c3:
                    tem_freq = st.radio("Possui programação cadastrada? *", ["Sim", "Não"], horizontal=True, index=None, key=f"tem_freq_{rc}")
                with s2_l1_c4:
                    desc_freq = ""
                    if tem_freq == "Sim":
                        desc_freq = st.text_input("Qual a programação? *", key=f"desc_freq_{rc}")
                    elif tem_freq == "Não":
                        desc_freq = st.text_input("Nº OC de Cadastramento *", key=f"desc_freq_nao_{rc}")

                s2_l2_c1, s2_l2_c2 = st.columns(2)
                with s2_l2_c1: consumo_previsto = st.text_input("Consumo Previsto (kg) *", key=f"cons_prev_{rc}")
                with s2_l2_c2: consumo_real = st.text_input("Consumo Real/Médio (kg) *", key=f"cons_real_{rc}")
                    
                s2_l3_c1, s2_l3_c2 = st.columns(2)
                with s2_l3_c1: possui_art = st.radio("Laudo ART emitido? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_art_{rc}")
                with s2_l3_c2:
                    desc_art = ""
                    if possui_art == "Sim":
                        desc_art = st.text_input("Número da ART *", key=f"desc_art_sim_{rc}")
                    elif possui_art == "Não":
                        desc_art = st.text_input("Nº OC de Solicitação de Laudo *", key=f"desc_art_nao_{rc}")

                s2_l4_c1, s2_l4_c2 = st.columns(2)
                with s2_l4_c1: possui_debitos = st.radio("Cliente possui débitos? *", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rc}")
                with s2_l4_c2:
                    desc_debitos = ""
                    if possui_debitos == "Sim":
                        desc_debitos = st.text_input("Detalhes dos Débitos", key=f"desc_deb_{rc}")

                s2_l5_c1, s2_l5_c2 = st.columns(2)
                with s2_l5_c1: central_norma = st.radio("Central atende as normas? *", ["Sim", "Não"], horizontal=True, index=None, key=f"central_norma_{rc}")
                with s2_l5_c2:
                    desc_central_norma = ""
                    if central_norma == "Não":
                        desc_central_norma = st.text_input("Motivo Central fora de norma", key=f"desc_norma_{rc}")

                s2_l6_c1, s2_l6_c2 = st.columns(2)
                with s2_l6_c1: rep2_correto = st.radio("Representante 2 está correto? *", ["Sim", "Não"], horizontal=True, index=None, key=f"rep2_{rc}")
                with s2_l6_c2:
                    desc_rep2 = ""
                    if rep2_correto == "Não":
                        desc_rep2 = st.text_input("Nº OC de Regularização", key=f"desc_rep2_{rc}")

                st.divider()
                st.subheader("3. Equipamentos Disponíveis no Cliente (Cálculo de Vazão)")
                
                opcoes_centrais_list = [f"Central {i:02d}" for i in range(1, int(qtd_centrais_visita) + 1)] if qtd_centrais_visita > 1 else ["Central"]
                
                c_cent_sel, c_qtd_eq, c_nome_eq, c_vaz_eq, c_btn_eq = st.columns([2, 1, 3, 2, 1])
                with c_cent_sel:
                    central_dest = st.selectbox("Central", opcoes_centrais_list, key=f"sel_cent_dest_{rc}")
                with c_qtd_eq:
                    qtd_eq_add = st.number_input("Qtd", min_value=1, value=1, step=1, key=f"qtd_eq_add_{rc}")
                with c_nome_eq:
                    nome_eq_add = st.text_input("Equipamento", placeholder="Ex: Forno Industrial", key=f"nome_eq_add_{rc}")
                with c_vaz_eq:
                    vazao_eq_add = st.text_input("Vazão Unit. (kg/h)", placeholder="Ex: 1,6 ou 0,5", key=f"vazao_eq_add_{rc}")
                with c_btn_eq:
                    st.write(""); st.write("")
                    if st.button("➕ Add", key=f"btn_add_eq_vis_{rc}"):
                        if nome_eq_add.strip() and vazao_eq_add.strip():
                            try:
                                v_unit = float(vazao_eq_add.replace(",", ".").lower().replace("kg/h", "").strip())
                                q_num = int(qtd_eq_add)
                                v_tot_item = v_unit * q_num
                                
                                st.session_state.equipamentos.append({
                                    "central": central_dest,
                                    "qtd": q_num,
                                    "nome": nome_eq_add.strip().title(),
                                    "vazao_unit": v_unit,
                                    "vazao_total": v_tot_item
                                })
                                st.success("Adicionado!")
                                st.rerun()
                            except ValueError:
                                st.error("Digite um valor numérico para a vazão.")
                        else:
                            st.warning("Preencha o nome e vazão.")

                if st.session_state.equipamentos:
                    st.write("")
                    st.markdown("**Lista de Equipamentos Cadastrados:**")
                    
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
                        
                        v_str_c = f"{vazao_c:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                        st.caption(f"Vazão Subtotal {c_nome}: {v_str_c} kg/h")
                    
                    st.write("")
                    v_str_geral = f"{vazao_geral_todas:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                    st.markdown(f"🔥 **Total - {v_str_geral} kg/h**")

                st.divider()
                st.subheader("4. Novos Negócios & Satisfação")
                s3_c1, s3_c2 = st.columns(2)
                with s3_c1:
                    indica_negocios = st.radio("Indicação de novos negócios? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ind_neg_{rc}")
                    desc_negocios = ""
                    if indica_negocios == "Sim":
                        desc_negocios = st.text_input("Detalhes da indicação", key=f"desc_neg_{rc}")
                with s3_c2:
                    cliente_satisfeito = st.radio("Cliente satisfeito com a Consigaz? *", ["Sim", "Não"], horizontal=True, index=None, key=f"cli_sat_{rc}")
                    desc_satisfacao = ""
                    if cliente_satisfeito:
                        desc_satisfacao = st.text_input("Observação sobre satisfação", key=f"desc_sat_{rc}")

                observacoes = st.text_area("Observações Gerais", key=f"obs_transf_{rc}")

                st.divider()
                st.subheader("5. Relatório Fotográfico - Upload de Imagens")
                
                def carregar_fotos(label, max_arquivos=None):
                    fotos = st.file_uploader(label, type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"up_{label}_{rc}")
                    if max_arquivos and fotos and len(fotos) > max_arquivos:
                        st.error(f"⚠️ Limite excedido para {label}. Serão considerados apenas os primeiros {max_arquivos} arquivos.")
                        return fotos[:max_arquivos]
                    return fotos

                dic_fotos_final = {}
                col_f1, col_f2 = st.columns(2)
                with col_f1: dic_fotos_final["FACHADA"] = carregar_fotos("📸 FACHADA (Até 2 fotos)", max_arquivos=2)
                with col_f2: dic_fotos_final["CILINDROS"] = carregar_fotos("📸 CILINDROS (Até 5 fotos)", max_arquivos=5)

                st.write("---")
                if qtd_centrais_visita == 1:
                    c1, c2, c3 = st.columns(3)
                    with c1: dic_fotos_final["ABRIGO"] = carregar_fotos("📸 ABRIGO (Até 10 fotos)", max_arquivos=10)
                    with c2: dic_fotos_final["CENTRAL"] = carregar_fotos("📸 CENTRAL (Até 5 fotos)", max_arquivos=5)
                    with c3: dic_fotos_final["EQUIPAMENTOS"] = carregar_fotos("📸 EQUIPAMENTOS", max_arquivos=None)
                else:
                    for i in range(1, int(qtd_centrais_visita) + 1):
                        st.markdown(f"**📸 FOTOS - CENTRAL {i:02d}**")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            nome_abrigo = f"ABRIGO CENTRAL {i:02d}"
                            dic_fotos_final[nome_abrigo] = carregar_fotos(f"📸 {nome_abrigo} (Até 10)", max_arquivos=10)
                        with c2:
                            nome_central = f"CENTRAL {i:02d}"
                            dic_fotos_final[nome_central] = carregar_fotos(f"📸 {nome_central} (Até 5)", max_arquivos=5)
                        with c3:
                            nome_equip = f"EQUIPAMENTOS CENTRAL {i:02d}"
                            dic_fotos_final[nome_equip] = carregar_fotos(f"📸 {nome_equip}", max_arquivos=None)

                st.divider()
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("📝 Gerar Texto para Sistema", type="primary"):
                        linha_art = "( ) Sim ( ) Não"
                        if possui_art == "Sim":
                            linha_art = f"(x) Sim ( ) Não {desc_art.strip()}"
                        elif possui_art == "Não":
                            linha_art = f"( ) Sim (x) Não {desc_art.strip()}"

                        if qtd_centrais_visita == 1:
                            desc_eq_val = eq_dict_visita.get(1, "").strip()
                            texto_eq_contrato = f"{eq_contrato or ''}. {desc_eq_val}".strip()
                        else:
                            linhas_eq_contr = [f"[Equipamentos Central {i:02d}: {eq_dict_visita.get(i, '').strip()}]" for i in range(1, int(qtd_centrais_visita) + 1)]
                            texto_eq_contrato = f"{eq_contrato or ''}. " + " ".join(linhas_eq_contr)

                        texto_rep2 = f"{rep2_correto or ''}" + (f" - {desc_rep2.strip()}" if rep2_correto == "Não" and desc_rep2.strip() else "")
                        texto_freq = f"{tem_freq or ''}" + (f" - {desc_freq.strip()}" if desc_freq.strip() else "")
                        texto_debitos = f"{possui_debitos or ''}" + (f" - {desc_debitos.strip()}" if possui_debitos == "Sim" and desc_debitos.strip() else "")
                        texto_central_norma = f"{central_norma or ''}" + (f" - {desc_central_norma.strip()}" if central_norma == "Não" and desc_central_norma.strip() else "")
                        texto_negocios = f"{indica_negocios or ''}" + (f" - {desc_negocios.strip()}" if indica_negocios == "Sim" and desc_negocios.strip() else "")
                        texto_satisfacao = f"{cliente_satisfeito or ''}" + (f", {desc_satisfacao.strip()}" if desc_satisfacao.strip() else "")

                        texto_disp_equip = ""
                        if st.session_state.equipamentos:
                            centrais_cad = sorted(list(set([e["central"] for e in st.session_state.equipamentos])))
                            tot_vazao_geral = 0.0
                            
                            for c_n in centrais_cad:
                                if qtd_centrais_visita > 1:
                                    texto_disp_equip += f"\n[{c_n.upper()}]\n"
                                else:
                                    texto_disp_equip += "\n[CENTRAL]\n"

                                vazao_c_sum = 0.0
                                for item in st.session_state.equipamentos:
                                    if item["central"] == c_n:
                                        v_unit_fmt = f"{item['vazao_unit']:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                        texto_disp_equip += f"{item['qtd']:02d} {item['nome']} - {v_unit_fmt} kg/h\n"
                                        vazao_c_sum += item["vazao_total"]
                                        tot_vazao_geral += item["vazao_total"]
                                
                                v_c_sum_fmt = f"{vazao_c_sum:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                if qtd_centrais_visita > 1:
                                    texto_disp_equip += f"Vazão Subtotal {c_n}: {v_c_sum_fmt} kg/h\n"
                                else:
                                    texto_disp_equip += f"Vazão Subtotal Central: {v_c_sum_fmt} kg/h\n"
                            
                            tot_g_fmt = f"{tot_vazao_geral:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                            texto_disp_equip += f"\nTotal - {tot_g_fmt} kg/h"
                        else:
                            texto_disp_equip = "\nTotal - 0 kg/h"

                        texto_final = f"""Contato: {contato}
Sobrenome ou departamento: {departamento}
Telefone: {telefone}

Equipamentos de acordo com o contrato vigente? {texto_eq_contrato}
Representante 2 está correto? {texto_rep2}
Possui programação cadastrada? {texto_freq}
Consumo de acordo com o contrato vigente? Consumo previsto: {consumo_previsto} kg | Consumo médio: {consumo_real} kg
Laudo ART emitido? {linha_art} Central atende as normas? {texto_central_norma}

Quais equipamentos disponíveis no cliente?
{texto_disp_equip}

Indicação de novos negócios do cliente: {texto_negocios}
Cliente possui débitos? {texto_debitos}
Cliente está satisfeito com o atendimento da Consigaz? {texto_satisfacao}

Obs.: {observacoes}"""

                        st.success("✅ Texto para o Sistema gerado com sucesso!")
                        st.text_area("Texto Gerado:", value=texto_final, height=350, key=f"txt_area_transf_{rc}")
                        botao_copiar_customizado(texto_final, "transf_txt")

                with col_b2:
                    if st.button("📄 Gerar PDF do Relatório Fotográfico"):
                        if not cod_cliente or not nome_cliente:
                            st.error("⚠️ Preencha o Código do Cliente e Nome/Razão Social.")
                        else:
                            pdf = RelatorioPDF(cod_cliente=cod_cliente, nome_cliente=nome_cliente, logo_path=LOGO_PATH)
                            pdf.set_margins(10, 32, 10)
                            pdf.set_auto_page_break(auto=True, margin=20)
                            
                            for categoria, arquivos in dic_fotos_final.items():
                                if arquivos:
                                    pdf.add_page()
                                    pdf.set_font("Arial", "B", 11)
                                    pdf.cell(0, 6, categoria.upper(), ln=1, align="L")
                                    pdf.ln(4)
                                    
                                    for idx, arq in enumerate(arquivos):
                                        temp_path = None
                                        try:
                                            img = Image.open(arq)
                                            if img.mode != "RGB":
                                                img = img.convert("RGB")
                                            
                                            fd, temp_path = tempfile.mkstemp(suffix=f"_{uuid.uuid4().hex}.jpg")
                                            os.close(fd)
                                            img.save(temp_path, format="JPEG")
                                            
                                            img_w_px, img_h_px = img.size
                                            proporcao = img_h_px / img_w_px
                                            w_alvo = 130
                                            h_alvo = w_alvo * proporcao
                                            
                                            if h_alvo > 110:
                                                h_alvo = 110
                                                w_alvo = h_alvo / proporcao
                                            
                                            pos_x_centro = (210 - w_alvo) / 2
                                            
                                            if pdf.get_y() + h_alvo > 270:
                                                pdf.add_page()
                                            
                                            pdf.image(temp_path, x=pos_x_centro, y=pdf.get_y(), w=w_alvo, h=h_alvo)
                                            pdf.set_y(pdf.get_y() + h_alvo + 10)
                                        except Exception:
                                            pass
                                        finally:
                                            if temp_path and os.path.exists(temp_path):
                                                try:
                                                    os.remove(temp_path)
                                                except OSError:
                                                    pass

                            if st.session_state.equipamentos:
                                pdf.add_page()
                                pdf.set_font("Arial", "B", 11)
                                pdf.cell(0, 6, "EQUIPAMENTOS DISPONÍVEIS NO CLIENTE", ln=1, align="L")
                                pdf.ln(4)
                                
                                centrais_cad = sorted(list(set([e["central"] for e in st.session_state.equipamentos])))
                                tot_pdf_geral = 0.0

                                for c_n in centrais_cad:
                                    pdf.set_font("Arial", "B", 10)
                                    pdf.cell(0, 6, c_n.upper(), ln=1, align="L")
                                    
                                    pdf.set_fill_color(230, 230, 230)
                                    pdf.cell(20, 7, "QTD", border=1, align="C", fill=True)
                                    pdf.cell(115, 7, "EQUIPAMENTO", border=1, align="L", fill=True)
                                    pdf.cell(50, 7, "VAZÃO UNIT.", border=1, align="C", fill=True, ln=1)
                                    
                                    pdf.set_font("Arial", "", 10)
                                    vazao_c_pdf = 0.0
                                    for item in st.session_state.equipamentos:
                                        if item["central"] == c_n:
                                            v_unit_fmt = f"{item['vazao_unit']:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                            pdf.cell(20, 6, f"{item['qtd']:02d}", border=1, align="C")
                                            pdf.cell(115, 6, f"{item['nome']}", border=1, align="L")
                                            pdf.cell(50, 6, f"{v_unit_fmt} kg/h", border=1, align="C", ln=1)
                                            vazao_c_pdf += item["vazao_total"]
                                            tot_pdf_geral += item["vazao_total"]

                                    v_c_pdf_fmt = f"{vazao_c_pdf:.2f}".replace(".", ",").rstrip("0").rstrip(",")
                                    pdf.set_font("Arial", "B", 10)
                                    pdf.cell(135, 7, f"VAZÃO TOTAL {c_n.upper()}:", border=1, align="R", fill=True)
                                    pdf.cell(50, 7, f"{v_c_pdf_fmt} kg/h", border=1, align="C", fill=True, ln=1)
                                    pdf.ln(4)

                            cod_limpo = re.sub(r'\D', '', str(cod_cliente))
                            data_str = datetime.now().strftime("%d-%m-%y")
                            nome_arquivo_pdf = f"relatorio_{cod_limpo}_{data_str}.pdf"
                            
                            pdf_output = pdf.output(dest='S')
                            if isinstance(pdf_output, str):
                                pdf_bytes = pdf_output.encode('latin-1', errors='replace')
                            else:
                                pdf_bytes = bytes(pdf_output)

                            st.download_button(
                                label="💾 Baixar PDF Gerado",
                                data=pdf_bytes,
                                file_name=nome_arquivo_pdf,
                                mime="application/pdf"
                            )

            # -------------------------------------------------------------
            # 2. ELABORAÇÃO DE CONTRATO
            # -------------------------------------------------------------
            elif menu_tratativa == "📝 Elaboração de Contrato":
                rcc = st.session_state.reset_counter_contrato
                cabecalho_pagina("Elaboração de Contrato", "Formulário de preenchimento e geração do padrão de solicitação de contrato.")
                
                if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_elab_{rcc}"):
                    st.session_state.reset_counter_contrato += 1
                    st.rerun()

                st.divider()

                st.subheader("1. Motivo")
                motivo_solicitacao = st.text_area("Descreva claramente o motivo da regularização do contrato:", key=f"motivo_{rcc}")

                st.divider()

                st.subheader("2. Dados do Cliente")
                col_cli1, col_cli2, col_cli3 = st.columns(3)
                with col_cli1: contato_contrato = st.text_input("Contato", key=f"contato_c_{rcc}")
                with col_cli2: telefone_contrato = st.text_input("Telefone", key=f"tel_c_{rcc}")
                with col_cli3: email_contrato = st.text_input("E-mail", key=f"email_c_{rcc}")

                st.divider()

                st.subheader("3. Solicitação")
                col_sol1, col_sol2 = st.columns(2)
                with col_sol1:
                    tipo_fluxo = st.radio("Selecione o objetivo da solicitação:", ["Gerar Minuta", "Enviar para Assinatura"], horizontal=True, index=None, key=f"fluxo_c_{rcc}")
                with col_sol2:
                    tipo_contrato = st.radio("Contrato / Aditamento / Distrato:", ["Contrato", "Aditamento", "Distrato"], horizontal=True, index=None, key=f"tp_cont_{rcc}")

                st.divider()

                st.subheader("4. Dados do Contrato")
                
                col_b2_1, col_b2_2 = st.columns(2)
                with col_b2_1:
                    requisicao_opt = st.radio("Requisição:", ["Permanente", "Provisório"], horizontal=True, index=None, key=f"req_opt_{rcc}")
                with col_b2_2:
                    mesmo_prop_opt = st.radio("Mesmo proprietário?", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_prop_{rcc}")

                cnpj_campo_val, ie_campo_val = "", ""
                email_novo_prop = "N/A"

                col_b2_3, col_b2_4 = st.columns(2)
                with col_b2_3:
                    mesmo_cnpj_opt = st.radio("Mesmo CNPJ?", ["Sim", "Não"], horizontal=True, index=None, key=f"mesmo_cnpj_{rcc}")
                    
                    if mesmo_cnpj_opt == "Sim":
                        cnpj_campo_val = st.text_input("CNPJ:", key=f"cnpj_val_{rcc}")
                        ie_campo_val = st.text_input("I.E.:", key=f"ie_val_{rcc}")
                    elif mesmo_cnpj_opt == "Não":
                        cnpj_campo_val = st.text_input("Novo CNPJ:", key=f"novo_cnpj_val_{rcc}")
                        ie_campo_val = st.text_input("Nova I.E.:", key=f"nova_ie_val_{rcc}")
                    
                    if mesmo_prop_opt == "Não":
                        email_novo_prop = st.text_input("E-mail do novo proprietário que receberá o novo contrato:", key=f"email_novo_{rcc}")

                with col_b2_4:
                    if len("".join(filter(str.isdigit, str(cnpj_campo_val)))) == 14:
                        dados_api = consultar_cnpj_api(cnpj_campo_val)
                        if dados_api:
                            st.markdown(f"✅ **Razão Social:** {dados_api.get('razao_social', 'Não encontrada')}")
                            sit = dados_api.get("situacao_cadastral", "")
                            st.markdown(f"🟢 **Status CNPJ:** {'Ativo' if sit == 2 or str(sit).upper() == 'ATIVA' else f'Inativa ({sit})'}")

                st.divider()

                st.subheader("5. Endereço / Equipamentos")
                col_b3_1, col_b3_2 = st.columns(2)
                with col_b3_1:
                    endereco_padrao = st.text_input("Endereço padrão ou entrega?:", key=f"end_padrao_{rcc}")
                with col_b3_2:
                    qtd_entregas_c = st.number_input("Quantidade de centrais / endereços:", min_value=1, value=1, step=1, key=f"qtd_ent_c_{rcc}")

                eq_dict_c = {}
                if qtd_entregas_c == 1:
                    eq_dict_c[1] = st.text_input("Equipamentos Central 01:", key=f"eq_ent_1_{rcc}")
                else:
                    st.markdown("**Equipamentos por Central / Endereço:**")
                    cols_eq_b3 = st.columns(min(int(qtd_entregas_c), 3))
                    for i in range(1, int(qtd_entregas_c) + 1):
                        c_idx = (i - 1) % len(cols_eq_b3)
                        with cols_eq_b3[c_idx]:
                            eq_dict_c[i] = st.text_input(f"Equipamentos Central {i:02d}:", key=f"eq_ent_{i}_{rcc}")

                st.divider()

                st.subheader("6. Comodato / Fornecimento")
                tipo_fornecimento = st.radio("Tipo de Fornecimento:", ["Granel", "Cilindro", "Ambos"], horizontal=True, index=None, key=f"tp_forn_{rcc}")
                
                preco_granel, consumo_granel_input = "", ""
                p13_val, p20_val, p45_val = "", "", ""
                p13_qtd, p20_qtd, p45_qtd = 0, 0, 0
                consumo_cilindro_input_kg = ""
                consumo_cilindro_total_calc = 0

                if tipo_fornecimento in ["Granel", "Ambos"]:
                    st.markdown("**Preço e Consumo Granel:**")
                    col_g1, col_g2 = st.columns(2)
                    with col_g1:
                        preco_granel = st.text_input("Preço Granel (R$/kg):", key=f"preco_granel_{rcc}")
                    with col_g2:
                        consumo_granel_input = st.text_input("Consumo previsto (Granel) mensal:", placeholder="Ex: 100 ou 100 kgs", key=f"cons_granel_{rcc}")

                if tipo_fornecimento in ["Cilindro", "Ambos"]:
                    st.markdown("**Preço Cilindro por Modelo:**")
                    col_cp1, col_cp2, col_cp3 = st.columns(3)
                    with col_cp1: p13_val = st.text_input("Preço P13 (R$):", key=f"p13_v_{rcc}")
                    with col_cp2: p20_val = st.text_input("Preço P20 (R$):", key=f"p20_v_{rcc}")
                    with col_cp3: p45_val = st.text_input("Preço P45 (R$):", key=f"p45_v_{rcc}")

                    st.markdown("**Consumo previsto (Cilindro) mensal:**")
                    tab_c1, tab_c2 = st.tabs(["Preenchimento por Quantidade de Cilindros", "Preenchimento Direto em KGs"])
                    with tab_c1:
                        col_cc1, col_cc2, col_cc3 = st.columns(3)
                        with col_cc1: p13_qtd = st.number_input("Qtd Cilindros P13", min_value=0, value=0, step=1, key=f"p13_q_{rcc}")
                        with col_cc2: p20_qtd = st.number_input("Qtd Cilindros P20", min_value=0, value=0, step=1, key=f"p20_q_{rcc}")
                        with col_cc3: p45_qtd = st.number_input("Qtd Cilindros P45", min_value=0, value=0, step=1, key=f"p45_q_{rcc}")
                        
                        consumo_cilindro_total_calc = (p13_qtd * 13) + (p20_qtd * 20) + (p45_qtd * 45)
                        if consumo_cilindro_total_calc > 0:
                            st.info(f"💡 Consumo Calculado em KGs: **{consumo_cilindro_total_calc} kgs**")

                    with tab_c2:
                        consumo_cilindro_input_kg = st.text_input("Qual consumo previsto (Cilindro) mensal em kgs:", placeholder="Ex: 130 kgs", key=f"cons_cil_kg_{rcc}")

                col_cc_out1, col_cc_out2 = st.columns(2)
                with col_cc_out1:
                    cond_pagamento = st.text_input("Condição de pagamento:", key=f"cond_pag_{rcc}")
                with col_cc_out2:
                    vigencia = st.text_input("Vigência:", key=f"vigencia_{rcc}")

                st.divider()

                st.subheader("7. Financeiro e Assinaturas")
                col_fin1, col_fin2 = st.columns(2)
                with col_fin1:
                    possui_debito_fin = st.radio("Possui NF's Pendentes?", ["Sim", "Não"], horizontal=True, index=None, key=f"possui_deb_{rcc}")
                    resp_pendentes = "N/A"
                    if possui_debito_fin == "Sim":
                        resp_pendentes = st.text_input("Quem será o responsável pelas NF's pendentes?", key=f"resp_pend_{rcc}")
                with col_fin2:
                    st.write("")

                nome_testemunha, email_testemunha = "", ""
                responsaveis_dados = []

                if tipo_fluxo == "Enviar para Assinatura":
                    st.markdown("---")
                    st.markdown("**Dados para Assinatura:**")
                    col_t1, col_t2 = st.columns(2)
                    with col_t1: nome_testemunha = st.text_input("Nome da Testemunha:", key=f"nome_test_{rcc}")
                    with col_t2: email_testemunha = st.text_input("E-mail da Testemunha:", key=f"email_test_{rcc}")

                    qtd_responsaveis = st.selectbox("Quantidade de Responsáveis pela Assinatura:", [1, 2, 3, 4], index=0, key=f"qtd_resp_{rcc}")
                    for i in range(1, qtd_responsaveis + 1):
                        col_r1, col_r2 = st.columns(2)
                        with col_r1: n_r = st.text_input(f"Nome do Responsável pela assinatura {i:02d}:", key=f"nome_resp_{i}_{rcc}")
                        with col_r2: e_r = st.text_input(f"E-mail do Responsável pela assinatura {i:02d}:", key=f"email_resp_{i}_{rcc}")
                        responsaveis_dados.append({"nome": n_r, "email": e_r})

                st.divider()

                st.subheader("8. Condomínio CONTA SIM")
                conta_sim = st.radio("Condomínio CONTA SIM?:", ["Sim", "Não"], horizontal=True, index=None, key=f"conta_sim_{rcc}")
                num_unidades, qtd_torres, qtd_blocos, preco_religue, preco_servico = "", "", "", "", ""

                if conta_sim == "Sim":
                    col_cs1, col_cs2, col_cs3 = st.columns(3)
                    with col_cs1:
                        num_unidades = st.text_input("N° Unid autônomas (Aptos + áreas comuns/zeladoria):", key=f"num_unid_{rcc}")
                        qtd_torres = st.text_input("Qtd Torres:", key=f"qtd_torres_{rcc}")
                    with col_cs2:
                        qtd_blocos = st.text_input("Qtd Blocos:", key=f"qtd_blocos_{rcc}")
                        preco_religue = st.text_input("Valor preço de religue: R$", key=f"preco_rel_{rcc}")
                    with col_cs3:
                        preco_servico = st.text_input("Valor preço de serviço: R$", key=f"preco_serv_{rcc}")

                st.divider()

                if st.button("📝 Gerar Texto Padrão do Contrato", type="primary"):
                    lines_out = []

                    if tipo_fluxo == "Gerar Minuta":
                        lines_out.append("** FAVOR GERAR MINUTA EM PDF PARA ENVIO AO CLIENTE **\n")

                    if motivo_solicitacao and motivo_solicitacao.strip():
                        lines_out.append(f"Descreva claramente o motivo da regularização do contrato: {motivo_solicitacao.strip()}")

                    req_str = ""
                    if requisicao_opt:
                        req_str = f"Requisição ( {'X' if requisicao_opt == 'Permanente' else ' '} ) Permanente ( {'X' if requisicao_opt == 'Provisório' else ' '} ) Provisório:"
                    
                    prop_str = f"Mesmo proprietário?(sim/não): {mesmo_prop_opt}" if mesmo_prop_opt else ""
                    
                    parte_tp = f"Contrato / Aditamento / Distrato: {tipo_contrato}" if tipo_contrato else ""
                    if req_str: parte_tp += f" {req_str}"
                    if prop_str: parte_tp += f" {prop_str}"
                    if parte_tp: lines_out.append(parte_tp)

                    cnpj_linha = []
                    if mesmo_cnpj_opt == "Não":
                        if cnpj_campo_val.strip(): cnpj_linha.append(f"Novo CNPJ: {cnpj_campo_val.strip()}")
                        if ie_campo_val.strip(): cnpj_linha.append(f"Nova I.E.: {ie_campo_val.strip()}")
                    if cnpj_linha:
                        lines_out.append(" ".join(cnpj_linha))

                    if endereco_padrao and endereco_padrao.strip():
                        lines_out.append(f"Endereço padrão ou entrega?: {endereco_padrao.strip()}")
                    
                    if tipo_fornecimento in ["Granel", "Ambos"] and preco_granel and preco_granel.strip():
                        lines_out.append(f"Preço Granel: {preco_granel.strip()}")

                    partes_cil = []
                    if tipo_fornecimento in ["Cilindro", "Ambos"]:
                        if p13_val.strip(): partes_cil.append(f"P13 = {p13_val.strip()}")
                        if p20_val.strip(): partes_cil.append(f"P20 = {p20_val.strip()}")
                        if p45_val.strip(): partes_cil.append(f"P45 = {p45_val.strip()}")
                    if partes_cil:
                        lines_out.append(f"Preço Cilindro: {' | '.join(partes_cil)}")
                    
                    if cond_pagamento and cond_pagamento.strip():
                        lines_out.append(f"Condição de pagamento: {cond_pagamento.strip()}")
                    
                    if tipo_fornecimento in ["Granel", "Ambos"] and consumo_granel_input and consumo_granel_input.strip():
                        val_g_fmt = consumo_granel_input.strip()
                        if not re.search(r'(?i)\bkgs?\b', val_g_fmt): val_g_fmt += " kgs"
                        lines_out.append(f"Consumo previsto (Granel) mensal: {val_g_fmt}")
                    
                    val_c_fmt = ""
                    if tipo_fornecimento in ["Cilindro", "Ambos"]:
                        if consumo_cilindro_input_kg and consumo_cilindro_input_kg.strip():
                            val_c_fmt = consumo_cilindro_input_kg.strip()
                            if not re.search(r'(?i)\bkgs?\b', val_c_fmt): val_c_fmt += " kgs"
                        elif consumo_cilindro_total_calc > 0:
                            val_c_fmt = f"{consumo_cilindro_total_calc} kgs"
                    if val_c_fmt:
                        lines_out.append(f"Qual consumo previsto (Cilindro) mensal: {val_c_fmt}")
                    
                    if vigencia and vigencia.strip():
                        lines_out.append(f"Vigência: {vigencia.strip()}")
                    
                    eq_filled = []
                    for i in range(1, int(qtd_entregas_c) + 1):
                        val_eq = eq_dict_c.get(i, "").strip()
                        if val_eq:
                            if qtd_entregas_c == 1: eq_filled.append(val_eq)
                            else: eq_filled.append(f"[Entrega {i:02d}] {val_eq}")
                    if eq_filled:
                        lines_out.append(f"Equipamentos: {' '.join(eq_filled)}")
                    
                    lines_out.append(f"Quem será o responsável pelas NF's pendentes? {resp_pendentes.strip()}")
                    lines_out.append(f"E-mail do novo proprietário que receberá o novo contrato: {email_novo_prop.strip()}")
                    
                    if tipo_fluxo == "Enviar para Assinatura":
                        if nome_testemunha and nome_testemunha.strip():
                            lines_out.append(f"Nome da Testemunha: {nome_testemunha.strip()}")
                        if email_testemunha and email_testemunha.strip():
                            lines_out.append(f"E-mail da Testemunha: {email_testemunha.strip()}")
                        
                        if responsaveis_dados:
                            for idx, resp in enumerate(responsaveis_dados, 1):
                                if resp['nome'].strip() or resp['email'].strip():
                                    sfx = f" {idx}" if len(responsaveis_dados) > 1 else ""
                                    if resp['nome'].strip():
                                        lines_out.append(f"Nome do Responsável pela assinatura{sfx}: {resp['nome'].strip()}")
                                    if resp['email'].strip():
                                        lines_out.append(f"E-mail do Responsável pela assinatura{sfx}: {resp['email'].strip()}")
                    
                    if conta_sim:
                        lines_out.append(f"Condomínio CONTA SIM?: {conta_sim}")
                        if conta_sim == "Sim":
                            if num_unidades and num_unidades.strip():
                                lines_out.append(f"N° Unid autônomas (Aptos + áreas comuns/zeladoria): {num_unidades.strip()}")
                            if qtd_torres and qtd_torres.strip():
                                lines_out.append(f"Qtd Torres: {qtd_torres.strip()}")
                            if qtd_blocos and qtd_blocos.strip():
                                lines_out.append(f"Qtd Blocos: {qtd_blocos.strip()}")
                            if preco_religue and preco_religue.strip():
                                lines_out.append(f"Valor preço de religue: R$ {preco_religue.strip()}")
                            if preco_servico and preco_servico.strip():
                                lines_out.append(f"Valor preço de serviço: R$ {preco_servico.strip()}")

                    texto_padrao_contrato = "\n".join(lines_out).strip()

                    st.success("✅ Texto padrão gerado com sucesso!")
                    st.text_area("Texto Gerado:", value=texto_padrao_contrato, height=450, key=f"txt_area_contrato_{rcc}")
                    botao_copiar_customizado(texto_padrao_contrato, "contrato_txt")

            # -------------------------------------------------------------
            # 3. APROVAÇÃO DE CONTRATO
            # -------------------------------------------------------------
            elif menu_tratativa == "📋 Aprovação de Contrato":
                rcap = st.session_state.reset_counter
                cabecalho_pagina("Aprovação de Contrato", "Formulário de solicitação de aprovação de contrato.")

                if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_aprov_{rcap}"):
                    st.session_state.reset_counter += 1
                    st.rerun()

                st.divider()

                st.subheader("1. Motivo")
                motivo_reg = st.text_input("Motivo da regularização *", key=f"ap_motivo_{rcap}")
                
                st.divider()

                st.subheader("2. Informações de Contato")
                c_ap1, c_ap2, c_ap3 = st.columns(3)
                with c_ap1: contato_ap = st.text_input("Contato *", key=f"ap_cont_{rcap}")
                with c_ap2: telefone_ap = st.text_input("Telefone *", key=f"ap_tel_{rcap}")
                with c_ap3: email_ap = st.text_input("E-mail *", key=f"ap_email_{rcap}")
                
                c_ap4, c_ap5 = st.columns(2)
                with c_ap4: 
                    atualizar_email = st.radio("Atualizar E-mail? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_atu_email_{rcap}")
                
                novo_email_ap = ""
                if atualizar_email == "Sim":
                    novo_email_ap = st.text_input("Novo E-mail *", key=f"ap_novo_email_{rcap}")

                st.divider()

                st.subheader("3. Dados do Contrato")
                c_ap6, c_ap7 = st.columns(2)
                with c_ap6: contrato_adit = st.radio("Contrato / Aditamento *", ["Contrato", "Aditamento"], horizontal=True, index=None, key=f"ap_tp_cont_{rcap}")
                with c_ap7: vigencia_ap = st.text_input("Vigência *", key=f"ap_vig_{rcap}")

                qtd_entregas_ap = st.number_input("Quantidade de endereços/centrais", min_value=1, value=1, step=1, key=f"qtd_ent_ap_{rcap}")
                equipamentos_ap = ""
                eq_dict_ap = {}
                if qtd_entregas_ap == 1:
                    equipamentos_ap = st.text_input("Equipamentos *", key=f"ap_eq_{rcap}")
                else:
                    st.markdown("**Equipamentos por Endereço de Entrega:**")
                    for i in range(1, int(qtd_entregas_ap) + 1):
                        eq_dict_ap[i] = st.text_input(f"Equipamentos - [Entrega {i}] *", key=f"ap_eq_ent_{i}_{rcap}")

                especificidade_ap = st.text_input("Existe especificidade sobre a solicitação? *", key=f"ap_esp_{rcap}")

                st.divider()

                st.subheader("4. Redimensionamento")
                redim = st.radio("Redimensionamento: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_redim_{rcap}")
                comodato_de, comodato_para, inc_tanques, env_pecas = "", "", "Não", "Não"
                
                if redim == "Sim":
                    c_p1, c_p2 = st.columns(2)
                    with c_p1: comodato_de = st.text_input("Comodato passou de:", key=f"ap_com_de_{rcap}")
                    with c_p2: comodato_para = st.text_input("Para:", key=f"ap_com_para_{rcap}")
                    
                    c_p3, c_p4 = st.columns(2)
                    with c_p3: inc_tanques = st.radio("Inclusão de tanques?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_inc_tanq_{rcap}")
                    with c_p4: env_pecas = st.radio("Necessário lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_env_pec_{rcap}")

                st.divider()

                st.subheader("5. Condomínio Conta Sim & Portaria")
                implantacao_csim = st.radio("Implantação de conta sim: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_{rcap}")
                env_pecas_ficha, env_ficha_cliente, tp_portaria, contato_resp_port, part_local, contato_sindico = "Não", "Não", "", "", "", ""
                
                if implantacao_csim == "Sim":
                    col_cs1, col_cs2 = st.columns(2)
                    with col_cs1: env_pecas_ficha = st.radio("Foi enviado lista de peças?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_pec_{rcap}")
                    with col_cs2: env_ficha_cliente = st.radio("Foi enviado ficha de clientes?", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_csim_ficha_{rcap}")
                    
                    tp_portaria = st.text_input("Tipo de portaria", key=f"ap_tp_port_{rcap}")
                    contato_resp_port = st.text_input("Contato do responsável (nº ap ou contato remota)", key=f"ap_cont_resp_{rcap}")
                    part_local = st.text_input("Particularidades do local", key=f"ap_part_local_{rcap}")
                    contato_sindico = st.text_input("Contato atualizado do síndico", key=f"ap_cont_sind_{rcap}")

                st.divider()

                st.subheader("6. Alteração de CNPJ & Títulos em Aberto")
                alt_cnpj = st.radio("Alteração de CNPJ ou razão social? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_alt_cnpj_{rcap}")
                mesmo_prop_opt = st.radio("Se trata do mesmo proprietário: *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_mesmo_prop_{rcap}")
                possui_titulos_aberto = st.radio("Possui títulos em aberto? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_tit_aberto_{rcap}")
                
                neg_tit_input = ""
                if possui_titulos_aberto == "Sim":
                    neg_tit_input = st.text_input("Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto:", key=f"ap_neg_tit_{rcap}")

                st.divider()

                st.subheader("7. Redução de Vigência")
                red_vig = st.radio("Redução de vigência? *", ["Sim", "Não"], horizontal=True, index=None, key=f"ap_red_vig_{rcap}")
                motivo_red_vig = ""
                if red_vig == "Sim":
                    motivo_red_vig = st.text_input("(Se sim, descreva o motivo):", key=f"ap_mot_red_{rcap}")

                st.divider()
                
                st.subheader("8. Projeto Padrão")
                col_proj1, col_proj2 = st.columns([3, 1])
                with col_proj1:
                    projeto_num_bloco7 = st.text_input("Projeto (Informe o número completo do projeto): *", key=f"ap_proj7_{rcap}")
                with col_proj2:
                    st.write(""); st.write("")
                    is_cilindros = st.checkbox("Cilindros", key=f"ap_cil_{rcap}")

                st.divider()

                if st.button("📝 Gerar Texto de Aprovação de Contrato", type="primary"):
                    campos_faltantes = []
                    if not motivo_reg.strip(): campos_faltantes.append("Motivo da regularização")
                    if not contato_ap.strip(): campos_faltantes.append("Contato")
                    if not telefone_ap.strip(): campos_faltantes.append("Telefone")
                    if not email_ap.strip(): campos_faltantes.append("E-mail")
                    
                    if not atualizar_email: 
                        campos_faltantes.append("Atualizar E-mail?")
                    elif atualizar_email == "Sim" and not novo_email_ap.strip(): 
                        campos_faltantes.append("Novo E-mail")
                        
                    if not contrato_adit: campos_faltantes.append("Contrato / Aditamento")
                    if not vigencia_ap.strip(): campos_faltantes.append("Vigência")
                    
                    eq_ap_texto = ""
                    if qtd_entregas_ap == 1:
                        if not equipamentos_ap.strip(): campos_faltantes.append("Equipamentos")
                        eq_ap_texto = equipamentos_ap.strip()
                    else:
                        eq_ap_linhas = []
                        for i in range(1, int(qtd_entregas_ap) + 1):
                            val_e = eq_dict_ap[i].strip()
                            if not val_e:
                                campos_faltantes.append(f"Equipamentos [Entrega {i}]")
                            else:
                                eq_ap_linhas.append(f"[Entrega {i}] {val_e}")
                        eq_ap_texto = " ".join(eq_ap_linhas)

                    if not especificidade_ap.strip(): campos_faltantes.append("Existe especificidade sobre a solicitação")
                    if not redim: campos_faltantes.append("Redimensionamento")
                    if not implantacao_csim: campos_faltantes.append("Implantação de conta sim")
                    if not alt_cnpj: campos_faltantes.append("Alteração de CNPJ ou razão social?")
                    if not mesmo_prop_opt: campos_faltantes.append("Se trata do mesmo proprietário")
                    if not possui_titulos_aberto: campos_faltantes.append("Possui títulos em aberto?")
                    if not is_cilindros and not projeto_num_bloco7.strip(): campos_faltantes.append("Projeto (Bloco 08)")
                    if not red_vig: campos_faltantes.append("Redução de vigência?")

                    if campos_faltantes:
                        st.error("⚠️ Não foi possível gerar o texto. Preencha as seguintes informações obrigatórias:\n\n- " + "\n- ".join(campos_faltantes))
                    else:
                        def sim_nao_box(val):
                            if val == "Sim": return "[ x ] sim [   ] não"
                            elif val == "Não": return "[   ] sim [ x ] não"
                            return "[   ] sim [   ] não"

                        def sim_nao_parentheses(val):
                            if val == "Sim": return "( X ) SIM (   ) NÃO"
                            elif val == "Não": return "(   ) SIM ( X ) NÃO"
                            return "(   ) SIM (   ) NÃO"

                        linhas_texto = []
                        proj_final = "N/A" if is_cilindros else projeto_num_bloco7.strip()
                        neg_final = neg_tit_input.strip() if possui_titulos_aberto == "Sim" and neg_tit_input.strip() else "n/a"

                        linhas_texto.append(f"Motivo da regularização: {motivo_reg.strip()}")
                        linhas_texto.append("")
                        
                        linhas_texto.append(f"Contato: {contato_ap.strip()}")
                        linhas_texto.append(f"Telefone: {telefone_ap.strip()}")
                        linhas_texto.append(f"E-mail: {email_ap.strip()}")
                        if atualizar_email == "Sim":
                            linhas_texto.append(f"Atualizar E-mail? {sim_nao_box(atualizar_email)} - Novo E-mail: {novo_email_ap.strip()}")
                        else:
                            linhas_texto.append(f"Atualizar E-mail? {sim_nao_box(atualizar_email)}")
                        linhas_texto.append("")
                        
                        linhas_texto.append(f"Contrato / Aditamento: {contrato_adit}")
                        linhas_texto.append(f"Vigência: {vigencia_ap.strip()}")
                        linhas_texto.append(f"Equipamentos: {eq_ap_texto}")
                        linhas_texto.append(f"Existe especificidade sobre a solicitação: {especificidade_ap.strip()}")
                        linhas_texto.append("")

                        linhas_texto.append(f"Redimensionamento: {sim_nao_box(redim)}")
                        if redim == "Sim":
                            linhas_texto.append(f"Comodato passou de: {comodato_de.strip()}")
                            linhas_texto.append(f"Para: {comodato_para.strip()}")
                            linhas_texto.append(f"Inclusão de tanques? {sim_nao_box(inc_tanques)}")
                            linhas_texto.append(f"Necessário lista de peças? {sim_nao_box(env_pecas)}")
                        linhas_texto.append("")

                        linhas_texto.append(f"Implantação de conta sim: {sim_nao_box(implantacao_csim)}")
                        if implantacao_csim == "Sim":
                            linhas_texto.append(f"Foi enviado lista de peças? {sim_nao_box(env_pecas_ficha)}")
                            linhas_texto.append(f"Foi enviado ficha de clientes? {sim_nao_box(env_ficha_cliente)}")
                            linhas_texto.append(f"Tipo de portaria: {tp_portaria.strip()}")
                            linhas_texto.append(f"Contato do responsável: {contato_resp_port.strip()}")
                            linhas_texto.append(f"Particularidades do local: {part_local.strip()}")
                            linhas_texto.append(f"Contato atualizado do síndico: {contato_sindico.strip()}")
                        linhas_texto.append("")

                        linhas_texto.append(f"Alteração de CNPJ ou razão social? {sim_nao_box(alt_cnpj)}")
                        linhas_texto.append(f"Se trata do mesmo proprietário: {sim_nao_parentheses(mesmo_prop_opt)}")
                        linhas_texto.append(f"Possui títulos em aberto {sim_nao_box(possui_titulos_aberto)}")
                        linhas_texto.append(f"Descreva a negociação realizada com o novo proprietário relacionado aos títulos em aberto: {neg_final}")
                        linhas_texto.append("")

                        linhas_texto.append(f"Projeto (Informe o número completo do projeto): {proj_final}")
                        linhas_texto.append("")

                        linhas_texto.append(f"Redução de vigência? {sim_nao_box(red_vig)}")
                        if red_vig == "Sim":
                            linhas_texto.append(f"(Se sim, descreva o motivo): {motivo_red_vig.strip()}")

                        texto_aprovacao = "\n".join(linhas_texto)

                        st.success("✅ Texto de Aprovação gerado com sucesso!")
                        st.text_area("Texto Gerado:", value=texto_aprovacao, height=500, key=f"txt_area_aprov_{rcap}")
                        botao_copiar_customizado(texto_aprovacao, "aprovacao_txt")

            # -------------------------------------------------------------
            # 4. ANIVERSÁRIO DE CONTRATO
            # -------------------------------------------------------------
            elif menu_tratativa == "🎂 Aniversário de Contrato":
                rca = st.session_state.reset_counter
                cabecalho_pagina("Aniversário de Contrato", "Calculadora de reajuste por IPCA acumulado de 12M e geração de formulário.")

                if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_aniv_{rca}"):
                    st.session_state.reset_counter += 1
                    st.rerun()

                st.divider()
                ipca_api, ipca_periodo = obter_ipca_acumulado_12m()
                if ipca_api is not None:
                    ipca_vigente = ipca_api
                    st.success(f"📊 **IPCA Acumulado de 12 meses (Fonte oficial, referência {ipca_periodo}):** `{ipca_vigente:.2f}%`")
                else:
                    ipca_vigente = st.number_input("IPCA acumulado de 12 meses (%) - informado manualmente", min_value=0.0, value=4.58, step=0.01, format="%.2f", key=f"ipca_manual_{rca}")

                col_an1, col_an2 = st.columns(2)
                with col_an1: preco_anterior_input = st.text_input("Preço Anterior (R$)", value="7,7400", key=f"preco_ant_{rca}")
                with col_an2: clausula_contrato = st.radio("Cliente possui cláusula em contrato?", ["Sim", "Não"], horizontal=True, index=None, key=f"clausula_{rca}")

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
                    if clausula_contrato == "Não":
                        st.warning("⚠️ **Atenção:** O cliente selecionado não possui cláusula de reajuste em contrato.")

                    clausula_txt = "Cliente possui cláusula em contrato.\n" if clausula_contrato == "Sim" else ""
                    
                    p_ant_fmt = preco_anterior_input.strip()
                    if not p_ant_fmt.startswith("R$"):
                        p_ant_fmt = f"R$ {p_ant_fmt}"

                    texto_aniversario = (
                        f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%.\n"
                        f"{clausula_txt}"
                        f"Preço anterior: {p_ant_fmt}\n"
                        f"Preço Aniversário: R$ {p_aniv_str}"
                    )

                    st.success("✅ Texto gerado com sucesso!")
                    
                    col_v1, col_v2 = st.columns([1, 2])
                    with col_v1:
                        st.text_input("Preço Novo para Abertura da CI:", value=f"R$ {p_aniv_str}", disabled=False, key=f"valor_novo_ci_{rca}")
                    with col_v2:
                        st.write(""); st.write("")
                        botao_copiar_customizado(f"R$ {p_aniv_str}", "btn_copy_val_novo", label_btn="💵 Copiar Valor Novo")

                    st.text_area("Texto Gerado:", value=texto_aniversario, height=180, key=f"txt_area_aniv_{rca}")
                    botao_copiar_customizado(texto_aniversario, "aniversario_txt")

                st.divider()
                st.subheader("Tratativa com C.I.")
                ci_input = st.text_input("Número da C.I. (9 ou 11 dígitos)", placeholder="Ex: 588358982 ou 588.358.982", key=f"ci_num_{rca}")

                if st.button("📝 Gerar Texto Final com C.I.", type="primary"):
                    clausula_txt = "Cliente possui cláusula em contrato.\n" if clausula_contrato == "Sim" else ""
                    
                    p_ant_fmt = preco_anterior_input.strip()
                    if not p_ant_fmt.startswith("R$"):
                        p_ant_fmt = f"R$ {p_ant_fmt}"

                    ci_fmt = formatar_ci_num(ci_input)

                    texto_ci = (
                        f"Aumento de Aniversário de contrato, IPCA - {ipca_vigente:.2f}%.\n"
                        f"{clausula_txt}"
                        f"Preço anterior: {p_ant_fmt}\n"
                        f"Preço Aniversário: R$ {p_aniv_str}\n\n"
                        f"CI.: {ci_fmt} - Preço Aniversário"
                    )

                    st.success("✅ Texto com C.I. gerado com sucesso!")
                    st.text_area("Texto com C.I.:", value=texto_ci, height=220, key=f"txt_area_ci_{rca}")
                    botao_copiar_customizado(texto_ci, "ci_txt")

            # -------------------------------------------------------------
            # 5. FICHA DE CLIENTE
            # -------------------------------------------------------------
            elif menu_tratativa == "🗂️ Ficha de Cliente":
                rcf = st.session_state.reset_counter_fc
                cabecalho_pagina("Ficha de Cliente", "Preenchimento de condições contratuais e comerciais para ficha de cliente.")

                if st.button("🔄 Novo Cliente / Limpar Tela", key=f"btn_limp_fc_{rcf}"):
                    st.session_state.reset_counter_fc += 1
                    st.rerun()

                st.divider()

                motivo_fc = st.text_input("Motivo:", key=f"fc_motivo_{rcf}")

                col_fc_c1, col_fc_c2 = st.columns(2)
                with col_fc_c1:
                    contrato_ant_fc = st.text_input("Contrato / Aditamento Anterior:", key=f"fc_cont_ant_{rcf}")
                with col_fc_c2:
                    contrato_novo_fc = st.text_input("Contrato Novo:", key=f"fc_cont_novo_{rcf}")

                comodato_fc = st.text_input("Comodato:", key=f"fc_comodato_{rcf}")

                st.divider()

                tipo_forn_fc = st.radio(
                    "Tipo de Fornecimento:",
                    ["Granel", "Cilindro", "Ambos"],
                    horizontal=True,
                    index=None,
                    key=f"fc_tp_forn_{rcf}"
                )

                preco_granel_fc = ""
                p13_fc, p20_fc, p45_fc = "", "", ""
                consumo_granel_fc = ""
                consumo_cil_fc = ""

                if tipo_forn_fc in ["Granel", "Ambos"]:
                    st.markdown("**Dados Granel:**")
                    col_fc_g1, col_fc_g2 = st.columns(2)
                    with col_fc_g1:
                        preco_granel_fc = st.text_input("Preço Granel (/kg):", key=f"fc_preco_granel_{rcf}")
                    with col_fc_g2:
                        consumo_granel_fc = st.text_input("Consumo Mensal Previsto (Granel):", key=f"fc_cons_granel_{rcf}")

                if tipo_forn_fc in ["Cilindro", "Ambos"]:
                    st.markdown("**Dados Cilindro:**")
                    col_fc_p1, col_fc_p2, col_fc_p3 = st.columns(3)
                    with col_fc_p1:
                        p13_fc = st.text_input("Preço P13 (/und P13):", key=f"fc_p13_{rcf}")
                    with col_fc_p2:
                        p20_fc = st.text_input("Preço P20 (/und P20):", key=f"fc_p20_{rcf}")
                    with col_fc_p3:
                        p45_fc = st.text_input("Preço P45 (/und P45):", key=f"fc_p45_{rcf}")
                    consumo_cil_fc = st.text_input("Consumo Mensal Previsto (Cilindro):", key=f"fc_cons_cil_{rcf}")

                st.divider()

                col_fc_v1, col_fc_v2 = st.columns(2)
                with col_fc_v1:
                    cond_pag_fc = st.text_input("Condição de Pagamento:", key=f"fc_cond_pag_{rcf}")
                with col_fc_v2:
                    vigencia_fc = st.text_input("Vigência:", key=f"fc_vigencia_{rcf}")

                obs_fc = st.text_area("Obs.:", key=f"fc_obs_{rcf}")

                st.divider()

                if st.button("📝 Gerar Texto da Ficha de Cliente", type="primary", key=f"btn_gerar_fc_{rcf}"):
                    linhas_fc = []
                    linhas_fc.append(f"CONTRATO / ADITAMENTO ANTERIOR: {contrato_ant_fc.strip()}".rstrip())
                    linhas_fc.append(f"CONTRATO NOVO: {contrato_novo_fc.strip()}".rstrip())
                    linhas_fc.append(f"COMODATO: {comodato_fc.strip()}".rstrip())

                    if tipo_forn_fc in ["Granel", "Ambos"]:
                        p_g = preco_granel_fc.strip()
                        if p_g:
                            p_g_clean = re.sub(r'(?i)\s*/\s*kg\s*$', '', p_g).strip()
                            linhas_fc.append(f"PREÇO GRANEL: {p_g_clean} /kg")
                        else:
                            linhas_fc.append("PREÇO GRANEL:")

                    if tipo_forn_fc in ["Cilindro", "Ambos"]:
                        partes_cil_fc = []
                        if p13_fc.strip():
                            p13_clean = re.sub(r'(?i)\s*/\s*und(\s*p13)?\s*$', '', p13_fc.strip()).strip()
                            partes_cil_fc.append(f"{p13_clean} /und P13")
                        if p20_fc.strip():
                            p20_clean = re.sub(r'(?i)\s*/\s*und(\s*p20)?\s*$', '', p20_fc.strip()).strip()
                            partes_cil_fc.append(f"{p20_clean} /und P20")
                        if p45_fc.strip():
                            p45_clean = re.sub(r'(?i)\s*/\s*und(\s*p45)?\s*$', '', p45_fc.strip()).strip()
                            partes_cil_fc.append(f"{p45_clean} /und P45")
                        linhas_fc.append(f"PREÇO CILINDRO: {' | '.join(partes_cil_fc)}".rstrip())

                    if tipo_forn_fc in ["Granel", "Ambos"]:
                        linhas_fc.append(f"CONSUMO MENSAL PREVISTO GRANEL: {consumo_granel_fc.strip()}".rstrip())

                    if tipo_forn_fc in ["Cilindro", "Ambos"]:
                        linhas_fc.append(f"CONSUMO MENSAL PREVISTO CILINDRO: {consumo_cil_fc.strip()}".rstrip())

                    linhas_fc.append(f"CONDIÇÃO DE PAGAMENTO: {cond_pag_fc.strip()}".rstrip())
                    linhas_fc.append(f"VIGÊNCIA: {vigencia_fc.strip()}".rstrip())
                    linhas_fc.append("")
                    linhas_fc.append(f"Motivo: {motivo_fc.strip()}".rstrip())

                    if obs_fc.strip():
                        linhas_fc.append("")
                        linhas_fc.append(f"Obs.: {obs_fc.strip()}")

                    texto_ficha_cliente = "\n".join(linhas_fc)

                    st.success("✅ Texto da Ficha de Cliente gerado com sucesso!")
                    st.text_area("Texto Gerado:", value=texto_ficha_cliente, height=320, key=f"txt_area_fc_{rcf}")
                    botao_copiar_customizado(texto_ficha_cliente, "ficha_cliente_txt")


# =====================================================================
# ABA 2: AGENDA DE OCORRÊNCIAS
# =====================================================================
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

        def limpar_classificacao(texto):
            if pd.isna(texto):
                return "-"
            texto_limpo = re.sub(r'\[.*?\]', '', str(texto)).strip()
            return texto_limpo if texto_limpo else str(texto)

        def classificar_status_abertura(row, hoje_ref):
            prazo = row['Prazo_DT']
            abertura = row['Abertura_DT']
            
            if pd.isna(prazo):
                return "Normal"
            
            prazo_dia = pd.Timestamp(prazo).normalize()
            hoje = pd.Timestamp(hoje_ref).normalize()
            
            if prazo_dia == hoje:
                return "🔵 Vence Hoje"
            elif prazo_dia < hoje:
                return "🔴 Vencido"
                
            if pd.isna(abertura):
                return "🟢 1ª Semana"
                
            abertura_dia = pd.Timestamp(abertura).normalize()
            delta_dias = (prazo_dia - abertura_dia).days
            if delta_dias <= 7:
                return "🟢 1ª Semana"
            elif delta_dias <= 14:
                return "🟡 2ª Semana"
            else:
                return "🔴 3ª Semana"

        def classificar_status_geral(row, hoje_ref):
            prazo = row['Prazo_DT']
            if pd.isna(prazo):
                return "Normal"
            
            prazo_dia = pd.Timestamp(prazo).normalize()
            hoje = pd.Timestamp(hoje_ref).normalize()
            
            amanha = hoje + timedelta(days=1)
            dias_para_sexta = (4 - hoje.weekday()) % 7
            sexta_semana = hoje + timedelta(days=dias_para_sexta)
            
            if prazo_dia < hoje:
                return "🔴 Vencido"
            elif prazo_dia == hoje:
                return "🔵 Vence Hoje"
            elif prazo_dia == amanha:
                return "🟠 Vence Amanhã"
            elif prazo_dia <= sexta_semana:
                return "🟡 Vence na Semana"
            else:
                return "🟢 No Prazo"

        col_menu_agenda, col_conteudo_agenda = st.columns([1, 4])

        with col_menu_agenda:
            st.markdown("### 📌 Filtros")
            arquivo_excel = st.file_uploader(
                "📂 Importar Planilha Excel", 
                type=["xlsx", "xls"],
                key="uploader_agenda_excel_novo"
            )
            
            st.divider()
            
            opcoes_visao = ["Todas Ocorrências", "Comodato Inativo", "Ocorrências por Cidade"]
            if st.session_state.e_supervisor:
                opcoes_visao.append("📊 Dashboard de Gestão (Gráficos)")
                opcoes_visao.append("📈 Ocorrências por Classificação")

            tipo_visao_agenda = st.radio(
                "Visualização:",
                opcoes_visao,
                label_visibility="collapsed"
            )

            st.divider()
            st.markdown("### 🏷️ Legenda de Status")
            if tipo_visao_agenda == "Comodato Inativo":
                st.markdown("🟢 **1ª Semana**")
                st.markdown("🟡 **2ª Semana**")
                st.markdown("🔴 **3ª Semana**")
            else:
                st.markdown("🔴 **Vencido**")
                st.markdown("🔵 **Vence Hoje**")
                st.markdown("🟠 **Vence Amanhã**")
                st.markdown("🟡 **Vence na Semana**")
                st.markdown("🟢 **No Prazo**")

        with col_conteudo_agenda:
            cabecalho_pagina("Módulo de Pós-Vendas & Atendimento", "Sistema Integrado de Gestão de Ocorrências por Prazos, SLAs e Geografia")

            if arquivo_excel is not None:
                try:
                    df = ler_arquivo_excel_robusto(arquivo_excel)
                    df.columns = [str(c).strip() for c in df.columns]
                    
                    if COL_OCORRENCIA not in df.columns:
                        for idx_r, row in df.iterrows():
                            row_str = " ".join([str(val) for val in row.values if pd.notna(val)])
                            if COL_OCORRENCIA in row_str:
                                df.columns = [str(c).strip() for c in df.iloc[idx_r].values]
                                df = df.iloc[idx_r+1:].reset_index(drop=True)
                                break

                    if COL_OCORRENCIA not in df.columns:
                        st.error(f"❌ A coluna obrigatória '{COL_OCORRENCIA}' não foi encontrada no arquivo. Verifique se o relatório está correto.")
                        st.stop()

                    df = df.dropna(subset=[COL_OCORRENCIA])
                    
                    if "Tratadas_Temp" not in st.session_state:
                        st.session_state.Tratadas_Temp = set()

                    df_pendentes = df[df[COL_FECHAMENTO].isna()].copy()
                    df_pendentes[COL_OCORRENCIA] = pd.to_numeric(df_pendentes[COL_OCORRENCIA], errors='coerce')
                    df_pendentes = df_pendentes.dropna(subset=[COL_OCORRENCIA])
                    df_pendentes[COL_OCORRENCIA] = df_pendentes[COL_OCORRENCIA].astype(int)
                    
                    df_pendentes = df_pendentes[~df_pendentes[COL_OCORRENCIA].isin(st.session_state.Tratadas_Temp)]
                    
                    df_pendentes['Prazo_DT'] = pd.to_datetime(df_pendentes[COL_PRAZO], format="%d/%m/%Y %H:%M", errors='coerce')
                    df_pendentes['Abertura_DT'] = pd.to_datetime(df_pendentes[COL_ABERTURA], format="%d/%m/%Y %H:%M", errors='coerce')
                    df_pendentes = df_pendentes.dropna(subset=['Prazo_DT'])
                    
                    df_pendentes['Cidade'] = df_pendentes[COL_ENDERECO].apply(extrair_cidade)
                    df_pendentes['Classificação Limpa'] = df_pendentes[COL_SUB_CLASSIF].apply(limpar_classificacao)
                    
                    if st.session_state.e_supervisor:
                        if COL_PROPRIETARIO in df_pendentes.columns:
                            df_pendentes['Consultor'] = df_pendentes[COL_PROPRIETARIO].fillna("Não Atribuído").astype(str)
                        elif 'Vendedor/Consultor' in df_pendentes.columns:
                            df_pendentes['Consultor'] = df_pendentes['Vendedor/Consultor'].fillna("Não Atribuído").astype(str)
                        else:
                            df_pendentes['Consultor'] = "Geral"
                    else:
                        df_pendentes['Consultor'] = "Geral"

                    hoje = datetime.now()
                    dias_para_sexta = (4 - hoje.weekday()) % 7
                    sexta_semana = hoje + timedelta(days=dias_para_sexta)
                    sexta_semana = sexta_semana.replace(hour=23, minute=59, second=59)

                    if tipo_visao_agenda == "Comodato Inativo":
                        df_pendentes['Status Geral'] = df_pendentes.apply(lambda r: classificar_status_abertura(r, hoje), axis=1)
                    else:
                        df_pendentes['Status Geral'] = df_pendentes.apply(lambda r: classificar_status_geral(r, hoje), axis=1)

                    df_pendentes = df_pendentes.sort_values(by='Prazo_DT', ascending=True)
                    df_base_visao = df_pendentes.copy()

                    if tipo_visao_agenda == "Comodato Inativo":
                        df_base_visao = df_base_visao[df_base_visao['Classificação Limpa'].str.contains("Comodato Inativo", case=False, na=False)]
                        st.subheader("⚠️ Relatório Específico: Comodato Inativo")
                    elif tipo_visao_agenda == "Ocorrências por Cidade":
                        st.subheader("🏙️ Ocorrências por Cidade")
                        col_tabela_cidade, col_grafico_cidade = st.columns(2)
                        with col_tabela_cidade:
                            st.markdown("**Tabela Consolidada por Cidade**")
                            df_mapa_agrup = df_base_visao.groupby('Cidade').size().reset_index(name='Total Ocorrências')
                            st.dataframe(df_mapa_agrup.sort_values(by='Total Ocorrências', ascending=False), hide_index=True, use_container_width=True)
                        with col_grafico_cidade:
                            st.markdown("**Gráfico de OCs por Cidade**")
                            chart = alt.Chart(df_mapa_agrup).mark_bar(color="#0055A5", cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
                                x=alt.X('Cidade:N', sort='-y', title='Cidade'),
                                y=alt.Y('Total Ocorrências:Q', title='Qtd Ocorrências'),
                                tooltip=['Cidade', 'Total Ocorrências']
                            ).properties(height=280)
                            st.altair_chart(chart, use_container_width=True)
                        st.stop()
                    else:
                        st.subheader("2. Agenda Geral de Visitas Pendentes")

                    st.markdown("### Filtros por Status e Prazos")
                    total_visitas = len(df_base_visao)
                    
                    if tipo_visao_agenda == "Comodato Inativo":
                        vencidas_qt = len(df_base_visao[df_base_visao['Status Geral'] == '🔴 3ª Semana'])
                        hoje_qt = len(df_base_visao[df_base_visao['Status Geral'] == '🟡 2ª Semana'])
                        amanha_qt = len(df_base_visao[df_base_visao['Status Geral'] == '🟢 1ª Semana'])
                        
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            if st.button(f"📋 **{total_visitas}**\nTotal", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "Todas"
                        with c2:
                            if st.button(f"🔴 **{vencidas_qt}**\n3ª Semana", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "🔴 3ª Semana"
                        with c3:
                            if st.button(f"🟡 **{hoje_qt}**\n2ª Semana", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "🟡 2ª Semana"
                        with c4:
                            if st.button(f"🟢 **{amanha_qt}**\n1ª Semana", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "🟢 1ª Semana"
                    else:
                        vencidas_qt = len(df_base_visao[df_base_visao['Status Geral'] == '🔴 Vencido'])
                        hoje_qt = len(df_base_visao[df_base_visao['Status Geral'] == '🔵 Vence Hoje'])
                        amanha_qt = len(df_base_visao[df_base_visao['Status Geral'] == '🟠 Vence Amanhã'])
                        semana_qt = len(df_base_visao[df_base_visao['Status Geral'] == '🟡 Vence na Semana'])
                        cinco_dias_qt = len(df_base_visao[df_base_visao['Prazo_DT'] <= sexta_semana])

                        c1, c2, c3, c4, c5 = st.columns(5)
                        with c1:
                            if st.button(f"**{total_visitas}**\nTotal", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "Todas"
                        with c2:
                            if st.button(f"**{vencidas_qt}**\nVencidas", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "🔴 Vencido"
                        with c3:
                            if st.button(f"**{hoje_qt}**\nVence Hoje", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "🔵 Vence Hoje"
                        with c4:
                            if st.button(f"**{amanha_qt}**\nVence Amanhã", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "🟠 Vence Amanhã"
                        with c5:
                            if st.button(f"**{semana_qt}**\nVence na Semana", use_container_width=True):
                                st.session_state.filtro_dashboard_ativo = "🟡 Vence na Semana"

                    st.divider()

                    if st.session_state.e_supervisor:
                        col_fc1, col_fc2, col_fc3 = st.columns(3)
                        lista_consultores = ["Todos"] + sorted(list(df_base_visao['Consultor'].unique()))
                        lista_cidades_filtro = ["Todas"] + sorted(list(df_base_visao['Cidade'].unique()))
                        lista_class_filtro = ["Todas"] + sorted(list(df_base_visao['Classificação Limpa'].unique()))

                        with col_fc1: consultor_sel = st.selectbox("Consultor:", lista_consultores)
                        with col_fc2: cidade_filtro_sel = st.selectbox("Cidade:", lista_cidades_filtro)
                        with col_fc3: class_filtro_sel = st.selectbox("Classificação:", lista_class_filtro)
                    else:
                        col_fc1, col_fc2 = st.columns(2)
                        lista_cidades_filtro = ["Todas"] + sorted(list(df_base_visao['Cidade'].unique()))
                        lista_class_filtro = ["Todas"] + sorted(list(df_base_visao['Classificação Limpa'].unique()))

                        with col_fc1: cidade_filtro_sel = st.selectbox("Filtrar por Cidade:", lista_cidades_filtro)
                        with col_fc2: class_filtro_sel = st.selectbox("Filtrar por Classificação:", lista_class_filtro)

                    df_filtrado = df_base_visao.copy()
                    
                    if st.session_state.filtro_dashboard_ativo != "Todas":
                        df_filtrado = df_filtrado[df_filtrado['Status Geral'] == st.session_state.filtro_dashboard_ativo]

                    if st.session_state.e_supervisor and consultor_sel != "Todos":
                        df_filtrado = df_filtrado[df_filtrado['Consultor'] == consultor_sel]
                    if cidade_filtro_sel != "Todas":
                        df_filtrado = df_filtrado[df_filtrado['Cidade'] == cidade_filtro_sel]
                    if class_filtro_sel != "Todas":
                        df_filtrado = df_filtrado[df_filtrado['Classificação Limpa'] == class_filtro_sel]

                    df_filtrado['Prazo'] = df_filtrado['Prazo_DT'].dt.strftime('%d/%m/%Y')

                    if df_filtrado.empty:
                        st.success("✅ Excelente! Não há nenhuma ocorrência pendente para os filtros selecionados.")
                    else:
                        if st.session_state.e_supervisor:
                            df_exibicao = df_filtrado[[
                                'Status Geral', COL_OCORRENCIA, COL_CLIENTE, 
                                'Cidade', 'Classificação Limpa', 'Prazo', 'Consultor'
                            ]].copy()
                            df_exibicao.columns = ['Status', 'Nº OC', 'Cliente', 'Cidade', 'Classificação', 'Prazo', 'Consultor']
                        else:
                            df_exibicao = df_filtrado[[
                                'Status Geral', COL_OCORRENCIA, COL_CLIENTE, 
                                'Cidade', 'Classificação Limpa', 'Prazo'
                            ]].copy()
                            df_exibicao.columns = ['Status', 'Nº OC', 'Cliente', 'Cidade', 'Classificação', 'Prazo']

                        df_exibicao['Nº OC'] = df_exibicao['Nº OC'].astype(str)
                        st.dataframe(df_exibicao, hide_index=True, use_container_width=True)

                except Exception as e:
                    st.error(f"⚠️ Ocorreu um erro ao processar o arquivo. Certifique-se de que é o relatório correto. Erro técnico: {e}")
            else:
                st.info("👆 Por favor, faça o upload da planilha atualizada de ocorrências no menu lateral esquerdo para carregar o dashboard.")


# =====================================================================
# ABA 3: STATUS DE CONTRATOS
# =====================================================================
if aba_contratos is not None:
    with aba_contratos:
        cabecalho_pagina("Status de Contratos", "Acompanhamento de clientes em processo de contrato.")
        status_contratos = ["Elaboração de Contrato", "Aguardando Ass do Cliente", "Aguardando Ass do Gerente", "Processo Enviado"]
        cores_contratos = {
            "Elaboração de Contrato": "🔴", 
            "Aguardando Ass do Cliente": "🟠", 
            "Aguardando Ass do Gerente": "🟡", 
            "Processo Enviado": "🟢"
        }
        renderizar_painel_acompanhamento("contrato", status_contratos, cores_contratos)


# =====================================================================
# ABA 4: STATUS DE VENDAS
# =====================================================================
if aba_vendas is not None:
    with aba_vendas:
        cabecalho_pagina("Status de Vendas", "Acompanhamento de clientes em negociação e venda.")
        status_vendas = ["Negociação Criada", "Aguardando Ass Cliente", "Processo despachado", "OC Venda de peça externo aberta", "Instalação / Serviço executado"]
        cores_vendas = {
            "Negociação Criada": "🔴", 
            "Aguardando Ass Cliente": "🟠", 
            "Processo despachado": "🟡", 
            "OC Venda de peça externo aberta": "🔵", 
            "Instalação / Serviço executado": "🟢"
        }
        renderizar_painel_acompanhamento("venda", status_vendas, cores_vendas)


# =====================================================================
# ABA 5: BLOCO DE NOTAS PESSOAL
# =====================================================================
if aba_notas is not None:
    with aba_notas:
        col_menu_notas, col_conteudo_notas = st.columns([1, 4])
        usuario_atual = st.session_state.usuario_atual
        notas_usuario = carregar_banco_notas(usuario_atual)

        with col_menu_notas:
            st.markdown("### 📓 Minhas Notas")
            if st.button("➕ Nova Nota", use_container_width=True):
                st.session_state.nota_selecionada_id = None
                st.rerun()
                
            st.divider()
            if not notas_usuario:
                st.caption("Nenhuma nota cadastrada.")
            else:
                for n_id, n_data in notas_usuario.items():
                    if st.button(n_data.get("titulo", "Sem Título"), key=f"btn_n_{n_id}", use_container_width=True):
                        st.session_state.nota_selecionada_id = n_id
                        st.rerun()

        with col_conteudo_notas:
            cabecalho_pagina("Bloco de Notas Pessoal", "Anotações vinculadas à sua conta e salvas na nuvem.")
            id_atual = st.session_state.nota_selecionada_id
            
            t_val = notas_usuario[id_atual]["titulo"] if id_atual in notas_usuario else ""
            c_val = notas_usuario[id_atual]["cliente"] if id_atual in notas_usuario else ""
            txt_val = notas_usuario[id_atual]["texto"] if id_atual in notas_usuario else ""

            with st.form("form_nota"):
                c1, c2 = st.columns(2)
                with c1: tit = st.text_input("Título", value=t_val)
                with c2: cli = st.text_input("Cliente", value=c_val)
                txt = st.text_area("Anotação", value=txt_val, height=200)
                
                b1, b2, _ = st.columns([1, 1, 4])
                with b1: btn_s = st.form_submit_button("💾 Salvar na Nuvem", type="primary")
                with b2: btn_d = st.form_submit_button("🗑️ Apagar") if id_atual else False

                if btn_s and tit:
                    target_id = id_atual if id_atual else str(uuid.uuid4())
                    if salvar_nota(target_id, usuario_atual, tit, cli, txt):
                        st.session_state.nota_selecionada_id = target_id
                        st.success("✅ Salvo com sucesso no banco de dados!")
                        st.rerun()
                if btn_d and id_atual:
                    if apagar_nota(id_atual):
                        st.session_state.nota_selecionada_id = None
                        st.rerun()


# =====================================================================
# PAINEL ADMIN / SUPERVISOR
# =====================================================================
if aba_admin is not None:
    with aba_admin:
        cabecalho_pagina("Painel de Administração de Usuários", "Cadastro de colaboradores, níveis de permissão e redefinição de senhas gravadas na nuvem.")
        
        banco_usuarios = carregar_banco_usuarios()
        col_adm1, col_adm2 = st.columns([1, 1])
        
        with col_adm1:
            st.subheader("1. Cadastrar Novo Usuário")
            st.caption("A senha inicial será sempre **123456** com troca obrigatória no primeiro acesso.")
            
            with st.form("form_novo_usuario"):
                novo_user = st.text_input("Nome do Usuário", placeholder="ex: rodrigo.carvalho").strip().lower()
                nivel_acesso = st.selectbox("Nível de Acesso", ["convencional", "supervisor", "admin"])
                btn_cadastrar = st.form_submit_button("➕ Cadastrar Usuário", type="primary")
                
                if btn_cadastrar:
                    if not novo_user:
                        st.error("⚠️ Preencha o nome do usuário.")
                    elif novo_user in banco_usuarios:
                        st.warning(f"⚠️ O usuário '{novo_user}' já existe.")
                    else:
                        if salvar_usuario(novo_user, "123456", nivel_acesso=nivel_acesso, precisa_trocar=True):
                            st.success(f"✅ Usuário **{novo_user}** criado com sucesso no banco de dados!")
                            st.rerun()

        with col_adm2:
            st.subheader("2. Reset de Senha de Usuário")
            lista_usuarios = [u for u in banco_usuarios.keys() if u != "admin"]
            
            if lista_usuarios:
                user_sel_senha = st.selectbox("Selecione o Usuário para Reset:", lista_usuarios)
                
                if st.button("🔄 Resetar Senha para Inicial (123456)", type="primary"):
                    curr_nivel = banco_usuarios[user_sel_senha]["nivel_acesso"]
                    if salvar_usuario(user_sel_senha, "123456", nivel_acesso=curr_nivel, precisa_trocar=True):
                        st.success(f"✅ Senha do usuário **{user_sel_senha}** resetada para **123456**!")
                        st.rerun()

        st.divider()
        st.subheader("3. Usuários Cadastrados & Remoção")
        
        data_users = []
        for k, v in banco_usuarios.items():
            nivel_txt = "Convencional"
            if v["nivel_acesso"] == "admin":
                nivel_txt = "Administrador"
            elif v["nivel_acesso"] == "supervisor":
                nivel_txt = "Supervisor"

            data_users.append({
                "Usuário": k,
                "Nível de Acesso": nivel_txt,
                "Status Senha": "⚠️ Troca Pendente" if v["precisa_trocar_senha"] else "🟢 Definida"
            })
            
        st.dataframe(pd.DataFrame(data_users), hide_index=True, use_container_width=True)

        if lista_usuarios:
            col_rem1, col_rem2 = st.columns([2, 1])
            with col_rem1:
                user_para_remover = st.selectbox("Selecione o usuário para remover:", lista_usuarios, key="sel_rem")
            with col_rem2:
                st.write(""); st.write("")
                if st.button("🗑️ Remover Usuário do Banco", key="btn_rem_u"):
                    if remover_usuario(user_para_remover):
                        st.success(f"✅ Usuário **{user_para_remover}** excluído do banco de dados!")
                        st.rerun()

# --- BARRA LATERAL LOGOUT ---
st.sidebar.divider()
if st.sidebar.button("🚪 Sair (Logout)", use_container_width=True):
    st.session_state.autenticado = False
    st.session_state.usuario_atual = ""
    st.session_state.e_admin = False
    st.session_state.e_supervisor = False
    st.session_state.troca_obrigatoria = False
    st.session_state.df_excel_agenda = None
    st.rerun()
