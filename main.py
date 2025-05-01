from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import io
import logging
from logging.handlers import RotatingFileHandler

# Configuração de logs
logging.basicConfig(
    handlers=[RotatingFileHandler('app.log', maxBytes=100000, backupCount=5)],
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)

app = Flask(__name__)
CORS(app)

# Configuração do diretório de downloads
DOWNLOAD_DIR = os.path.abspath("downloads")

def setup_driver():
    logging.info("Iniciando configuração do Chrome...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-software-rasterizer")
    
    # Configurar diretório de download
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    })
    
    logging.info("Instalando e configurando o ChromeDriver...")
    
    # Configuração específica para Docker
    if os.environ.get('CHROME_PATH'):
        chrome_options.binary_location = os.environ.get('CHROME_PATH')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver, DOWNLOAD_DIR
    except Exception as e:
        logging.error(f"Erro ao configurar ChromeDriver: {str(e)}")
        raise

def wait_and_click(driver, by, selector, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        element.click()
    except Exception as e:
        logging.error(f"Erro ao clicar no elemento {selector}: {str(e)}")
        raise

def wait_and_type(driver, by, selector, text, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        element.clear()
        element.send_keys(text)
    except Exception as e:
        logging.error(f"Erro ao digitar no elemento {selector}: {str(e)}")
        raise

def wait_for_download(download_dir, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        files = os.listdir(download_dir)
        audio_files = [f for f in files if f.endswith('.wav') and not f.endswith('.part')]
        if audio_files:
            return os.path.join(download_dir, audio_files[0])
        time.sleep(1)
    raise Exception("Timeout esperando pelo download do áudio")

def generate_audio(text_to_narrate, tone_configuration=None):
    driver = None
    try:
        driver, download_dir = setup_driver()
        
        logging.info("Acessando openai.fm...")
        driver.get("https://www.openai.fm")
        
        time.sleep(5)
        
        # Selecionar a voz padrão
        logging.info("Selecionando a voz...")
        voice_selector = "body > div > main > div.flex.flex-row > div > div.flex.flex-1.flex-col.pt-3.rounded-md > div > div:nth-child(2) > div"
        wait_and_click(driver, By.CSS_SELECTOR, voice_selector)
        
        # Inserir a tonalidade de voz (se fornecida)
        if tone_configuration:
            logging.info("Configurando a tonalidade de voz...")
            tone_xpath = "/html/body/div/main/div[2]/div[1]/div[2]/div/textarea"
            wait_and_type(driver, By.XPATH, tone_xpath, tone_configuration)
        else:
            # Tonalidade padrão
            default_tone = """Voice Affect: Mansa, suave como um sussurro à alma — sem ser abafada, sem soar cansada. Uma voz que acalma com leveza, como quem toca com os dedos o coração de quem ouve.

Tone: Amoroso, espiritual e acolhedor. Como quem lê a Palavra com intimidade, fé e ternura. Uma fala que não domina o espaço, mas o preenche com suavidade e calor humano.

Pacing: Calmo, porém contínuo. Sem pressa, mas com fluidez leve — como quem caminha devagar, mas constante. A voz não é arrastada, e sim presente, suave, respirada e natural.

Emotion: Fé tranquila, compaixão genuína, presença sensível. Fale como quem cuida de alguém em silêncio, com palavras que acolhem sem invadir. Emoção contida, mas real — como uma oração sincera.

Pronunciation: Clara, arredondada, sem cortes bruscos. Cada palavra deve ser dita com carinho e intenção. Dê leve ênfase emocional em palavras como "graça", "descanso", "esperança", "amor", "Senhor".

Pauses: Pausas leves e respiradas entre frases. Use o silêncio como espaço"""
            tone_xpath = "/html/body/div/main/div[2]/div[1]/div[2]/div/textarea"
            wait_and_type(driver, By.XPATH, tone_xpath, default_tone)
        
        # Inserir o texto para narração
        logging.info("Inserindo texto para narração...")
        text_xpath = "/html/body/div/main/div[2]/div[2]/div[2]/div/textarea"
        wait_and_type(driver, By.XPATH, text_xpath, text_to_narrate)
        
        # Iniciar download do áudio
        logging.info("Fazendo download do áudio...")
        download_selector = "body > div > footer > div > div > div:nth-child(1)"
        wait_and_click(driver, By.CSS_SELECTOR, download_selector)
        
        # Aguardar e obter o arquivo de áudio
        audio_file_path = wait_for_download(download_dir)
        
        # Ler o arquivo de áudio em bytes
        with open(audio_file_path, 'rb') as audio_file:
            audio_bytes = audio_file.read()
        
        # Limpar o arquivo baixado imediatamente
        try:
            os.remove(audio_file_path)
            logging.info(f"Arquivo temporário removido: {audio_file_path}")
        except Exception as e:
            logging.error(f"Erro ao remover arquivo temporário {audio_file_path}: {str(e)}")
        
        return audio_bytes
        
    except Exception as e:
        logging.error(f"Erro durante a geração do áudio: {str(e)}")
        raise
    finally:
        if driver:
            driver.quit()

@app.route('/generate-audio', methods=['POST'])
def generate_audio_endpoint():
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({
                "status": "error",
                "message": "O campo 'text' é obrigatório"
            }), 400
        
        text_to_narrate = data['text']
        tone_configuration = data.get('tone')
        
        # Gerar o áudio
        audio_bytes = generate_audio(text_to_narrate, tone_configuration)
        
        # Criar um objeto BytesIO com o conteúdo do áudio
        audio_io = io.BytesIO(audio_bytes)
        audio_io.seek(0)
        
        # Retornar o arquivo WAV binário diretamente
        response = send_file(
            audio_io,
            mimetype='audio/wav',
            as_attachment=True,
            download_name='audio.wav'
        )
        
        # Adicionar headers de cache
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logging.error(f"Erro no endpoint: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    # Garantir que o diretório de downloads existe
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    # Configurações de produção
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(host=host, port=port, debug=debug)