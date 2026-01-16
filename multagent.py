import streamlit as st
import google.generativeai as genai
from groq import Groq

# --- LIMPEZA DE CACHE (Para evitar que o erro antigo fique preso) ---
st.cache_resource.clear()

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    llama_client = Groq(api_key=st.secrets["LLAMA_API_KEY"])
except Exception as e:
    st.error("Erro nos Secrets!")
    st.stop()

def fluxo_multi_agente(pergunta_usuario):
    # TENTATIVA 1: O método mais robusto e simples
    try:
        # Usamos apenas 'gemini-1.5-flash' - o SDK cuida do resto
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(pergunta_usuario)
        texto_base = response.text
    except Exception as e:
        # TENTATIVA 2: Se o Flash falhar, vamos de Pro (o 'tanque' do Google)
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(pergunta_usuario)
            texto_base = response.text
        except Exception as e2:
            return f"O Google bloqueou as duas opções. Erro: {str(e2)}"

    # REVISÃO DO LLAMA (Isso costuma funcionar sempre)
    try:
        completion = llama_client.chat.completions.create(
            model="llama3-8b-8192", # Versão mais leve e rápida para teste
            messages=[
                {"role": "system", "content": "Você é o Sênior Ácido. Refine este texto com sarcasmo e analogias de TI."},
                {"role": "user", "content": texto_base}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e_llama:
        return f"Gemini OK, mas Llama falhou: {e_llama}"

# --- INTERFACE ---
st.title("🛡️ Agente Expert (v2.0 - Debug Mode)")

if prompt := st.chat_input("Mande sua dúvida..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Batalhando com as APIs do Google..."):
            res = fluxo_multi_agente(prompt)
            st.markdown(res)
