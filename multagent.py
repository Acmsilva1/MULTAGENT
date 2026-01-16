import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONEXÕES ---
try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação: {e}")
    st.stop()

# --- 2. PERSONALIDADE & LOGICA DE INTELIGÊNCIA ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', mentor de TI e mestre confeiteiro.
Seu objetivo é ajudar o André em IA, Dados e LGPD com sarcasmo e precisão técnica.
"""

# Prompt secreto para a "IA de Classificação"
CLASSIFIER_PROMPT = """
Analise a mensagem do usuário e extraia apenas fatos PERMANENTES sobre ele (nome, cargo, gostos, novas ferramentas que aprendeu).
Responda APENAS em JSON no formato:
{"is_important": boolean, "fact_type": "formacao/interesses/lgpd", "extracted_info": "string ou null"}
Se for apenas conversa fiada, is_important deve ser false.
"""

# --- 3. FUNÇÕES DE INFRAESTRUTURA ---
def carregar_contexto():
    try:
        p = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        h = supabase.table("historico_conversas").select("pergunta, resposta").eq("usuario", "André").order("created_at", desc=True).limit(3).execute().data
        historico_str = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in h]) if h else ""
        perfil_str = f"O André é {p['formacao']}, focado em {p['interesses']}. Estilo: {p['estilo_resposta']}."
        return perfil_str, historico_str
    except:
        return "Perfil não encontrado.", ""

# --- 4. INTERFACE ---
st.set_page_config(page_title="Agente Autônomo 5.0", page_icon="🧠")
st.title("Agente Pessoal")
st.caption("Cérebro com Auto-Classificação de Dados e Confeitaria Técnica")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 5. EXECUÇÃO INTELIGENTE ---
if prompt := st.chat_input("Fale comigo..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Analisando relevância dos dados...", expanded=False) as status:
            perfil, historico = carregar_contexto()
            
            # --- PASSO 1: A IA decide se a informação é importante ---
            analysis = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"}
            )
            decisao = json.loads(analysis.choices[0].message.content)

            # --- PASSO 2: Se for importante, atualiza o Perfil (Core) ---
            if decisao.get("is_important"):
                tipo = decisao.get("fact_type")
                info = decisao.get("extracted_info")
                # Update dinâmico no Supabase baseado no tipo detectado
                coluna = "interesses" if tipo == "interesses" else "formacao"
                supabase.table("perfil_usuario").update({coluna: info}).eq("usuario", "André").execute()
                status.write(f"✨ Memória Core atualizada: {info}")

            # --- PASSO 3: Gera a resposta do Sênior Ácido ---
            full_prompt = f"{BASE_SYSTEM_PROMPT}\n\nPERFIL ATUAL: {perfil}\n\nHISTÓRICO: {historico}"
            res_ia = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": full_prompt}, *st.session_state.messages],
                model="llama-3.3-70b-versatile"
            )
            resposta = res_ia.choices[0].message.content
            
            # --- PASSO 4: Salva no histórico de conversas ---
            supabase.table("historico_conversas").insert({
                "pergunta": prompt, "resposta": resposta, "categoria": "importante" if decisao.get("is_important") else "casual"
            }).execute()
            
            status.update(label="Processamento finalizado!", state="complete")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
