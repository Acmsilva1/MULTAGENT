import streamlit as st
from groq import Groq
from supabase import create_client, Client
import pandas as pd
import io
import json

# --- 1. CONEXÕES ---
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação técnica: {e}")
    st.stop()

# --- 2. PERSONALIDADE (DNA DO AGENTE) ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', mentor de TI e mestre confeiteiro.
- Missão: Apoiar o André (TI, IA, Dados e LGPD) com sarcasmo e precisão.
- Especialidade: Você ama analogias de confeitaria para explicar erros de código.
- Regra: Seja assertivo. Se o André te der um dado importante, confirme que guardou.
"""

CLASSIFIER_PROMPT = """
Analise a mensagem do usuário e extraia fatos PERMANENTES (nome, cargo, gostos, novas skills).
Responda APENAS em JSON: 
{"is_important": boolean, "fact_type": "formacao/interesses/lgpd", "extracted_info": "string ou null"}
"""

# --- 3. FUNÇÕES DE INFRA E PERSISTÊNCIA ---
def carregar_contexto():
    try:
        # Busca perfil e histórico
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        historico = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        
        hist_str = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in historico]) if historico else ""
        perf_str = f"André: {perfil['formacao']}. Interesses: {perfil['interesses']}. Regras: {perfil['diretrizes_lgpd']}."
        return perf_str, hist_str, perfil
    except Exception as e:
        return "Perfil básico.", "", {}

# --- 4. INTERFACE ---
st.set_page_config(page_title="Agente Sênior Ácido", page_icon="🍰")
st.title("Agente Pessoal")
st.caption("TI + Confeitaria + Memória Auditada")

# Sidebar com Perfil e Upload
with st.sidebar:
    st.header("🗂️ Dados do André")
    
    # Visualizador de Perfil em tempo real (para você não ser enganado)
    perf_str, hist_str, perfil_raw = carregar_contexto()
    if perfil_raw:
        with st.expander("👁️ Ver Memória de Longo Prazo"):
            st.json(perfil_raw)
    
    st.divider()
    arquivo = st.file_uploader("Analisar arquivo (.txt, .py, .csv)", type=["txt", "py", "csv"])
    conteudo_arquivo = ""
    if arquivo:
        if arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
            conteudo_arquivo = f"\n[ARQUIVO CSV]:\n{df.head(10).to_string()}"
        else:
            conteudo_arquivo = f"\n[TEXTO]:\n{arquivo.getvalue().decode('utf-8')}"
        st.success("Arquivo pronto!")

    if st.button("Limpar Chat Visual"):
        st.session_state.messages = []
        st.rerun()

# Inicialização das mensagens
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 5. LÓGICA DE PROCESSAMENTO ---
if prompt := st.chat_input("Diga algo ou atualize seu perfil..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Processando dados...", expanded=False) as status:
            
            # PASSO 1: Classificação de Importância
            try:
                analysis = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile",
                    response_format={"type": "json_object"}
                )
                decisao = json.loads(analysis.choices[0].message.content)
            except:
                decisao = {"is_important": False}

            # PASSO 2: Escrita no Banco (Auditada)
            if decisao.get("is_important"):
                tipo = decisao.get("fact_type")
                info = decisao.get("extracted_info")
                coluna = "interesses" if tipo == "interesses" else "formacao"
                
                # Update real no Supabase
                supabase.table("perfil_usuario").update({coluna: info}).eq("usuario", "André").execute()
                status.write(f"💾 Banco de Dados Atualizado: {info}")

            # PASSO 3: Resposta Principal
            full_prompt = f"{BASE_SYSTEM_PROMPT}\n\nPERFIL: {perf_str}\n\nHISTÓRICO: {hist_str}\n\n{conteudo_arquivo}"
            
            completion = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": full_prompt}, *st.session_state.messages],
                model="llama-3.3-70b-versatile"
            )
            resposta = completion.choices[0].message.content
            
            # PASSO 4: Salva no Histórico
            supabase.table("historico_conversas").insert({
                "pergunta": prompt, "resposta": resposta, "categoria": "importante" if decisao.get("is_important") else "casual"
            }).execute()
            
            status.update(label="Análise concluída!", state="complete")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
