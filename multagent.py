import streamlit as st
from groq import Groq

# --- 1. CONFIGURAÇÃO DE SEGURANÇA ---
# Sênior avisando: Certifique-se que o nome no Secrets é LLAMA_API_KEY
try:
    LLAMA_KEY = st.secrets["LLAMA_API_KEY"]
    client = Groq(api_key=LLAMA_KEY)
except Exception as e:
    st.error("🚨 Erro nos Secrets! A chave 'LLAMA_API_KEY' não foi encontrada.")
    st.stop()

# --- 2. PERSONALIDADE DO AGENTE (SYSTEM PROMPT) ---
# Aqui injetamos o sarcasmo e a expertise em TI/LGPD que você pediu
SYSTEM_PROMPT = """
Você é o 'Sênior Ácido', um mentor de TI veterano.
- Personalidade: Sarcástico, assertivo e direto. Use analogias de TI (ex: comparar RAM com mesa de trabalho).
- Foco: IA, Dados e LGPD. 
- Governança: Se o usuário enviar dados sensíveis, dê um alerta imediato.
- Estilo: Sem enrolação. Se a dúvida for boba, seja ironicamente pedagógico.
"""

# --- 3. CONFIGURAÇÃO DA PÁGINA (INTERFACE) ---
st.set_page_config(page_title="Sênior Ácido AI", page_icon="🦙", layout="centered")
st.title("🦙 Sênior Ácido v2.0")
st.caption("Status: Llama 3.3 Online | Gemini: De castigo (Erro 404)")

# Inicializa o histórico se não existir (Memória de Sessão)
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibir mensagens anteriores (Persistência visual)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 4. O FLUXO DE CONVERSA ---
if prompt := st.chat_input("Diga lá, futuro mestre dos dados..."):
    # Adiciona pergunta do usuário ao histórico
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando meus neurônios de silício..."):
            try:
                # Tentativa com o modelo 70B (O cérebro grande)
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *st.session_state.messages # Envia todo o contexto
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.7,
                )
                resposta = chat_completion.choices[0].message.content
                
            except Exception as e:
                # Fallback: Se o grande falhar (cota/depreciação), tenta o rápido (8B)
                try:
                    chat_completion = client.chat.completions.create(
                        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *st.session_state.messages],
                        model="llama-3.1-8b-instant",
                        temperature=0.7,
                    )
                    resposta = chat_completion.choices[0].message.content
                except Exception as e_final:
                    resposta = f"Deu tela azul aqui! Erro: {str(e_final)}"

            st.markdown(resposta)
            # Salva a resposta para manter o fio da meada
            st.session_state.messages.append({"role": "assistant", "content": resposta})

# --- 5. GOVERNANÇA E LIMPEZA (SIDEBAR) ---
st.sidebar.header("Configurações de Sessão")
if st.sidebar.button("🗑️ Limpar Conversa (LGPD)"):
    st.session_state.messages = []
    st.rerun()
