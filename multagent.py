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

# --- 2. PROMPTS (A MENTE DO AGENTE) ---
BASE_SYSTEM_PROMPT = """
Você é o 'Sênior'. Mentor de TI e Mestre Confeiteiro.
- Se o André pedir um código (Python, SQL, etc), ele deve ser salvo no Repositório.
- Se o André pedir uma receita de comida, ela deve ser salva no Livro de Receitas.
- Use sarcasmo, mas entregue qualidade técnica.
- Use analogias inteligentes em suas respostas.
"""

CLASSIFIER_PROMPT = """
Analise a mensagem. Responda APENAS JSON:
{"is_important": boolean, "category": "snippet/receita/carreira/casual", "title": "título curto", "content": "o conteúdo formatado"}
"""

# --- 3. FUNÇÕES DE BUSCA ---
def carregar_dados():
    perfil = supabase.table("perfil_usuario").select("*").eq("usuario", "André").single().execute().data
    # Busca tudo que foi marcado como importante para o catálogo
    catalogo = supabase.table("historico_conversas").select("*").eq("categoria", "importante").order("created_at", desc=True).execute().data
    return perfil, catalogo

# --- 4. INTERFACE ---
perfil, catalogo = carregar_dados()

# Sidebar de Governança
with st.sidebar:
    st.header("🧹 Governança")
    if st.button("Limpar Histórico Casual"):
        supabase.table("historico_conversas").delete().eq("categoria", "casual").execute()
        st.success("Faxina concluída!")
        st.rerun()
    
    st.divider()
    st.header("🎓 Perfil Ativo")
    st.info(f"**Foco:** {perfil.get('formacao')}")
    st.info(f"**Objetivo:** {perfil.get('interesses')}")

# Tabs Principais
tab_chat, tab_snippets, tab_receitas = st.tabs(["💬 Chat", "💻 Snippets de TI", "📖 Livro de Receitas"])

# --- ABA DE SNIPPETS ---
with tab_snippets:
    st.header("Repositório de Código")
    for item in catalogo:
        # Tenta identificar se o conteúdo tem cara de código
        if "def " in item['resposta'] or "import " in item['resposta'] or "```" in item['resposta']:
            with st.expander(f"📌 {item.get('pergunta')[:30]}..."):
                st.code(item['resposta'])

# --- ABA DE RECEITAS ---
with tab_receitas:
    st.header("Livro de Receitas Técnicas")
    for item in catalogo:
        # Filtra por palavras-chave de culinária se não houver categoria explícita
        culinaria = ["açúcar", "forno", "receita", "ingredientes", "bolo"]
        if any(word in item['resposta'].lower() for word in culinaria):
            with st.expander(f"🍰 {item.get('pergunta')[:30]}..."):
                st.write(item['resposta'])

# --- ABA DE CHAT ---
with tab_chat:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Peça um script ou uma receita de Red Velvet..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.status("Catalogando...", expanded=False):
                # Classificação
                res_class = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": CLASSIFIER_PROMPT}, {"role": "user", "content": prompt}],
                    model="llama-3.3-70b-versatile", response_format={"type": "json_object"}
                )
                decisao = json.loads(res_class.choices[0].message.content)

                # Geração da Resposta
                res_final = client_groq.chat.completions.create(
                    messages=[{"role": "system", "content": BASE_SYSTEM_PROMPT}, *st.session_state.messages],
                    model="llama-3.3-70b-versatile"
                )
                resposta = res_final.choices[0].message.content

                # Salvamento Inteligente
                is_imp = decisao.get("is_important") or "receita" in prompt.lower() or "codigo" in prompt.lower()
                supabase.table("historico_conversas").insert({
                    "pergunta": prompt, 
                    "resposta": resposta, 
                    "categoria": "importante" if is_imp else "casual"
                }).execute()

            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            if is_imp: st.toast("Novo item catalogado!", icon="🔖")
