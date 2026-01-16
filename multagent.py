import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json

# --- 1. CONFIGURAÇÃO E CONEXÕES ---
st.set_page_config(page_title="Agente Pessoal", layout="wide")

try:
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro na fiação técnica: {e}")
    st.stop()

# --- 2. PROMPTS ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior'. Mentor de TI e Mestre Confeiteiro.
Use sarcasmo e analogias criativas. 
Responda de forma assertiva e guarde códigos e receitas no catálogo.
"""

CLASSIFIER_PROMPT = """
Analise a mensagem. Responda APENAS JSON:
{"is_important": boolean, "category": "snippet/receita/carreira/casual"}
"""

# --- 3. LÓGICA DE DADOS ---
def carregar_dados():
    try:
        perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
        catalogo = supabase.table("historico_conversas").select("*").eq("categoria", "importante").order("created_at", desc=True).execute().data
        return perfil, catalogo
    except:
        return {}, []

perfil, catalogo = carregar_dados()

# --- 4. SIDEBAR DE GOVERNANÇA ---
with st.sidebar:
    st.header("🧹 Governança")
    if st.button("🗑️ Limpar Conversas Casuais"):
        supabase.table("historico_conversas").delete().eq("categoria", "casual").execute()
        st.success("Faxina completa!")
        st.rerun()
    
    st.divider()
    st.header("🎓 Perfil do André")
    st.write(f"**Foco:** {perfil.get('formacao', 'TI')}")
    st.write(f"**Interesses:** {perfil.get('interesses', 'Dados/IA')}")
    with st.expander("🔍 Ver Perfil Completo"):
        st.json(perfil)

# --- 5. ÁREA DO CHAT (FLUXO PRINCIPAL) ---
st.title("Agente Sênior Ácido")
st.caption("Focado em TI, Dados e Confeitaria Técnica")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Container para as mensagens (para não empurrar o input)
chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Input fixo no final
if prompt := st.chat_input("Peça um script ou uma receita técnica..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with chat_container:
        with st.chat_message("user"): st.markdown(prompt)

    with chat_container:
        with st.chat_message("assistant"):
            with st.status("Processando ingredientes...", expanded=False):
                # Classificação
                res_class = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile", response_format={"type": "json_object"}
                )
                decisao = json.loads(res_class.choices[0].message.content)

                # Resposta
                res_final = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": BASE_SYSTEM_PROMPT}, *st.session_state.messages],
                    model="llama-3.3-70b-versatile"
                )
                resposta = res_final.choices[0].message.content

                # Salvamento
                is_imp = decisao.get("is_important") or any(x in prompt.lower() for x in ["receita", "script", "codigo"])
                supabase.table("historico_conversas").insert({
                    "pergunta": prompt, "resposta": resposta, 
                    "categoria": "importante" if is_imp else "casual"
                }).execute()

            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            if is_imp: st.toast("🔖 Item catalogado com sucesso!")

# --- 6. CATÁLOGOS ABAIXO DO CHAT ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.subheader("💻 Snippets de TI")
    for item in catalogo:
        if any(x in item['resposta'] for x in ["def ", "import ", "```"]):
            with st.expander(f"📌 {item['pergunta'][:40]}..."):
                st.code(item['resposta'])

with col2:
    st.subheader("📖 Livro de Receitas")
    culinaria = ["açúcar", "forno", "receita", "ingrediente", "bolo", "massa"]
    for item in catalogo:
        if any(word in item['resposta'].lower() for word in culinaria):
            with st.expander(f"🍰 {item['pergunta'][:40]}..."):
                st.markdown(item['resposta'])
