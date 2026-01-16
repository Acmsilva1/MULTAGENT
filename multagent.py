import streamlit as st
from groq import Groq
from supabase import create_client, Client
import pandas as pd
import io
import json

# --- 1. CONEXÕES (Sem alterações aqui) ---
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação: {e}")
    st.stop()

# --- 2. PERSONALIDADE & CLASSIFICADOR ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', mentor de TI e mestre confeiteiro. 
Ajude o André em IA, Dados e LGPD com sarcasmo e precisão técnica.
Use analogias de confeitaria para explicar conceitos de TI.
"""

CLASSIFIER_PROMPT = """
Analise a entrada do usuário e extraia fatos PERMANENTES sobre ele (nome, cargo, gostos, novas ferramentas).
Responda APENAS em JSON: {"is_important": boolean, "fact_type": "formacao/interesses/lgpd", "extracted_info": "string ou null"}
"""

# --- 3. FUNÇÕES DE SUPORTE ---
def carregar_contexto():
    try:
        p = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        h = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        historico_str = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in h]) if h else ""
        perfil_str = f"André é {p['formacao']}, focado em {p['interesses']}. Estilo: {p['estilo_resposta']}."
        return perfil_str, historico_str
    except:
        return "Perfil básico ativo.", ""

# --- 4. INTERFACE E SIDEBAR (UPLOAD VOLTOU!) ---
st.set_page_config(page_title="Agente Autônomo 5.1", page_icon="🍰")
st.title("Agente Pessoal")
st.caption("Memória Seletiva + Analisador de Arquivos + Mestre Confeiteiro")

with st.sidebar:
    st.header("🗂️ Laboratório de Dados")
    arquivo = st.file_uploader("Suba arquivos (.txt, .py, .csv, .log)", type=["txt", "py", "csv", "log"])
    
    conteudo_arquivo = ""
    if arquivo:
        try:
            if arquivo.name.endswith(".csv"):
                df = pd.read_csv(arquivo)
                conteudo_arquivo = f"\n[CONTEÚDO DO CSV '{arquivo.name}']: \n{df.head(10).to_string()}"
            else:
                conteudo_arquivo = f"\n[CONTEÚDO DO ARQUIVO '{arquivo.name}']: \n{arquivo.getvalue().decode('utf-8')}"
            st.success(f"Arquivo '{arquivo.name}' carregado!")
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")

    if st.button("Limpar Chat Visual"):
        st.session_state.messages = []
        st.rerun()

# --- 5. LOGICA DO CHAT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Diga algo ou analise um arquivo..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Preparando a massa dos dados...", expanded=False) as status:
            perfil, historico = carregar_contexto()
            
            # PASSO 1: O Classificador analisa o prompt (e pode considerar o arquivo se você pedir)
            analysis = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"}
            )
            decisao = json.loads(analysis.choices[0].message.content)

            # PASSO 2: Atualização automática do Perfil
            if decisao.get("is_important"):
                coluna = "interesses" if decisao.get("fact_type") == "interesses" else "formacao"
                supabase.table("perfil_usuario").update({coluna: decisao.get("extracted_info")}).eq("usuario", "André").execute()
                status.write(f"✅ Perfil atualizado: {decisao.get('extracted_info')}")

            # PASSO 3: Resposta Principal (Inclui o conteúdo do arquivo se houver)
            prompt_completo = f"{BASE_SYSTEM_PROMPT}\n\nPERFIL: {perfil}\n\nHISTÓRICO: {historico}\n\n{conteudo_arquivo}"
            
            res_ia = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": prompt_completo}, *st.session_state.messages],
                model="llama-3.3-70b-versatile"
            )
            resposta = res_ia.choices[0].message.content
            
            # PASSO 4: Salva no histórico
            supabase.table("historico_conversas").insert({
                "pergunta": prompt, 
                "resposta": resposta, 
                "categoria": "importante" if decisao.get("is_important") else "casual"
            }).execute()
            
            status.update(label="Pronto para servir!", state="complete")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
