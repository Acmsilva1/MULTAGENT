import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Agente Pessoal", layout="wide")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na conexão: {e}")
    st.stop()

# --- 2. PERSONALIDADE E CLASSIFICADOR ---
BASE_SYSTEM_PROMPT = "Você é o 'Sênior', mentor de TI e mestre confeiteiro. Ajude o André. Use analogias inteligentes. Seja sarcástico sem ofender."
CLASSIFIER_PROMPT = 'Analise a mensagem. Responda APENAS JSON: {"is_important": boolean, "fact_type": "string", "extracted_info": "string"}'

# --- 3. FUNÇÕES DE BANCO DE DADOS ---
def carregar_dados():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        # Histórico apenas para a barra lateral
        historico_side = supabase.table("historico_conversas").select("pergunta, resposta, categoria").eq("usuario", "André").order("created_at", desc=True).limit(10).execute().data
        return perfil, historico_side
    except:
        return {}, []

perfil, hist_raw = carregar_dados()

# --- 4. SIDEBAR (HISTÓRICO MINIMALISTA) ---
with st.sidebar:
    st.header("🧠 Memória Core")
    if perfil:
        st.caption(f"🎓 {perfil.get('formacao')}")
        st.caption(f"🎨 {perfil.get('interesses')}")
    
    st.divider()
    st.subheader("📜 Conversas Recentes")
    if hist_raw:
        for item in hist_raw:
            icon = "⭐" if item['categoria'] == 'importante' else "💬"
            label = item['pergunta'][:25] + "..." if len(item['pergunta']) > 25 else item['pergunta']
            with st.expander(f"{icon} {label}"):
                st.write(item['resposta'])

    st.divider()
    if st.button("🗑️ Limpar Casuais"):
        supabase.table("historico_conversas").delete().eq("categoria", "casual").execute()
        st.rerun()

# --- 5. CHAT PRINCIPAL (SEM POLUIÇÃO) ---
st.title("Agente Sênior Ácido")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe apenas as mensagens da conversa atual
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Diga algo ao Sênior..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # Processamento em background (o st.status agora é super discreto)
        with st.empty():
            # 1. Classificação
            res_class = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile", response_format={"type": "json_object"}
            )
            decisao = json.loads(res_class.choices[0].message.content)

            # 2. Resposta da IA
            hist_context = "\n".join([f"U: {d['pergunta']} | A: {d['resposta']}" for d in hist_raw[:3]])
            res_final = client_groq.chat.completions.create(
                messages=[{"role": "system", "content": f"{BASE_SYSTEM_PROMPT}\n\nPERFIL: {perfil}\nHISTÓRICO: {hist_context}"}, *st.session_state.messages],
                model="llama-3.3-70b-versatile"
            )
            resposta = res_final.choices[0].message.content

            # 3. Salvamento Silencioso
            is_imp = decisao.get("is_important") or any(x in prompt.lower() for x in ["receita", "script", "codigo"])
            supabase.table("historico_conversas").insert({
                "usuario": "André", "pergunta": prompt, "resposta": resposta, 
                "categoria": "importante" if is_imp else "casual"
            }).execute()

        # Saída final: Apenas o texto da resposta
        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
        if is_imp: st.toast("💾 Salvo no histórico.", icon="⭐")
