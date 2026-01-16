import streamlit as st
from groq import Groq

# --- 1. CONFIGURAÇÃO DE SEGURANÇA ---
try:
    LLAMA_KEY = st.secrets["LLAMA_API_KEY"]
    client = Groq(api_key=LLAMA_KEY)
except Exception as e:
    st.error("🚨 Erro nos Secrets! Verifique a chave LLAMA_API_KEY.")
    st.stop()

# --- 2. PERSONALIDADE (SYSTEM PROMPT) ---
SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', um mentor de TI veterano.
- Personalidade: Sarcástico, assertivo e direto. Use analogias de TI.
- Foco: IA, Dados e LGPD. 
- Governança: Se vir dados sensíveis, dê um alerta.
"""

# --- 3. INTERFACE (O TAPA NO VISUAL) ---
st.set_page_config(page_title="Agente Pessoal", page_icon="🤖")

# Título simples como solicitado
st.title("Agente Pessoal")
st.caption("Especialista em TI & Sarcasmo Técnico")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Renderização do Histórico
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 4. INPUT E PROCESSAMENTO ---
# Campo de texto customizado: "digite sua pergunta"
if prompt := st.chat_input("Digite sua pergunta"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # O "Pensando..." dinâmico
        with st.status("Pensando...", expanded=False) as status:
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *st.session_state.messages 
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                )
                resposta = chat_completion.choices[0].message.content
                status.update(label="Resposta processada!", state="complete")
            except Exception as e:
                # Fallback rápido para o modelo menor
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}, *st.session_state.messages],
                    model="llama-3.1-8b-instant",
                )
                resposta = chat_completion.choices[0].message.content
                status.update(label="Finalizado (via backup)!", state="complete")

        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})

# Sidebar para Governança
with st.sidebar:
    st.header("Controles")
    if st.button("Limpar Conversa"):
        st.session_state.messages = []
        st.rerun()
