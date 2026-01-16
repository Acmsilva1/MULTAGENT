import streamlit as st
import google.generativeai as genai
from groq import Groq

# --- CONFIGURAÇÃO ---
try:
    # Use exatamente esses nomes nos Secrets do Streamlit
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    LLAMA_KEY = st.secrets["LLAMA_API_KEY"]
    
    genai.configure(api_key=GEMINI_KEY)
    llama_client = Groq(api_key=LLAMA_KEY)
except Exception as e:
    st.error("Erro nos Secrets! Verifique as chaves GEMINI_API_KEY e LLAMA_API_KEY.")
    st.stop()

# --- AGENTES ---
SYSTEM_GEMINI = "Você é um Engenheiro de IA analítico. Forneça respostas técnicas."
SYSTEM_LLAMA = "Você é o 'Sênior Ácido'. Melhore o texto com sarcasmo e analogias."

def fluxo_multi_agente(pergunta_usuario):
    # O PULO DO GATO: Nome completo do modelo 'models/gemini-1.5-flash'
    try:
        model_gemini = genai.GenerativeModel('gemini-1.5-flash')
        res_gemini = model_gemini.generate_content(f"{SYSTEM_GEMINI}\n\nPergunta: {pergunta_usuario}")
        texto_base = res_gemini.text
    except Exception as e:
        return f"Erro no Gemini: {str(e)}. Verifique se a API Key é válida e tem acesso ao modelo."

    # Chamada do Llama (Groq)
    try:
        res_llama = llama_client.chat.completions.create(
            model="llama3-70b-8192", # Se der erro aqui, mude para "llama3-8b-8192"
            messages=[
                {"role": "system", "content": SYSTEM_LLAMA},
                {"role": "user", "content": f"Refine isso: {texto_base}"}
            ]
        )
        return res_llama.choices[0].message.content
    except Exception as e:
        return f"O Gemini funcionou, mas o Llama deu erro: {str(e)}"

# --- INTERFACE ---
st.title("🤖 Consílio de Agentes (Gemini + Llama)")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Diga lá..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Consultando as máquinas...", expanded=True):
            resposta = fluxo_multi_agente(prompt)
        
        st.markdown(resposta)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
