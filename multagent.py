import streamlit as st
from groq import Groq
from supabase import create_client, Client

# --- 1. CONEXÃO COM OS MOTORES ---
try:
    # Llama (Cérebro)
    client_groq = Groq(api_key=st.secrets["LLAMA_API_KEY"])
    
    # Supabase (Memória de Longo Prazo)
    supabase: Client = create_client(
        st.secrets["SUPABASE_URL"], 
        st.secrets["SUPABASE_KEY"]
    )
except Exception as e:
    st.error(f"Erro na fiação técnica: {e}")
    st.stop()

# --- 2. PERSONALIDADE (SYSTEM PROMPT) ---
SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', um mentor de TI veterano.
- Personalidade: Sarcástico, assertivo e direto. Use analogias de TI.
- Missão: Ajudar o André (Recém-formado em TI) a evoluir.
- Foco: IA, Dados e LGPD.
"""

# --- 3. INTERFACE ---
st.set_page_config(page_title="Agente Pessoal", page_icon="🤖")
st.title("Agente Pessoal")
st.caption("Memória de Longo Prazo Ativada (Supabase) | Cérebro: Llama 3.3")

# Inicializa o histórico na sessão (Memória de Curto Prazo)
if "messages" not in st.session_state:
    st.session_state.messages = []
    
    # [OPCIONAL] Aqui poderíamos fazer um supabase.table().select() 
    # para carregar mensagens antigas assim que o app abre.

# Exibe o chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 4. INPUT E PROCESSAMENTO ---
if prompt := st.chat_input("Digite sua pergunta"):
    # Salva pergunta do usuário na interface
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Pensando...", expanded=False) as status:
            try:
                # Chamada para o Llama
                chat_completion = client_groq.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *st.session_state.messages 
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                )
                resposta = chat_completion.choices[0].message.content
                
                # --- SALVANDO NO SUPABASE ---
                # Isso garante que mesmo se o Streamlit cair, o dado tá no banco
                supabase.table("memoria_agente").insert({
                    "pergunta": prompt,
                    "resposta": resposta,
                    "usuario": "André"
                }).execute()
                
                status.update(label="Resposta processada e gravada!", state="complete")
                
            except Exception as e:
                resposta = f"Deu tela azul! Erro: {str(e)}"
                status.update(label="Erro no processamento", state="error")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})

# --- 5. CONTROLES ---
with st.sidebar:
    st.header("Configurações")
    if st.button("Limpar Conversa"):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    st.info("Os dados desta conversa estão sendo protegidos e armazenados via Supabase.")
