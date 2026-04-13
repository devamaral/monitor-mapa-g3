"""
==============================================================
  MONITOR DE MAPA - Google My Maps
  Detecta mudança de cor nas marcações e renomeia o arquivo
  no Google Drive com Att: DD/MM/YYYY HH:MM
==============================================================

DEPENDÊNCIAS:
  pip install requests google-auth google-auth-oauthlib google-api-python-client schedule

CONFIGURAÇÃO NECESSÁRIA:
  1. Preencha as variáveis da seção CONFIGURAÇÕES abaixo
  2. Siga o passo a passo do arquivo LEIA-ME.txt para obter
     o credentials.json do Google
==============================================================
"""

import requests
import schedule
import time
import json
import re
import os
import logging
import logging.handlers
import zipfile
import io
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ===================== CONFIGURAÇÕES =====================

# URL de exportação KML do seu mapa.
# Como obter: abra o mapa no navegador, veja a URL, copie o valor do parâmetro "mid"
# Exemplo de URL do mapa: https://www.google.com/maps/d/edit?mid=1aBcDeFgHiJkLmNoPqRsTuVwXyZ
# Então a KML_URL fica:
KML_URL = "https://www.google.com/maps/d/kml?mid=1c4WTozYsi5rlGkUjJbkCOJfg9xrlndQ"

# ID do arquivo no Google Drive (mesmo "mid" do mapa)
DRIVE_FILE_ID = "1c4WTozYsi5rlGkUjJbkCOJfg9xrlndQ"

# Nome base do arquivo (sem o Att:)
# Exemplo: "Adesivos abril"
NOME_BASE_ARQUIVO = "Adesivos abril"

# Arquivo onde o snapshot anterior é salvo
SNAPSHOT_FILE = "snapshot_anterior.json"

# Arquivo de log
LOG_FILE = "monitor_mapa.log"

# Intervalo de verificação em minutos (padrão: 5 min)
INTERVALO_MINUTOS = 5

# =========================================================

# Escopos necessários para renomear arquivo no Drive
SCOPES = ["https://www.googleapis.com/auth/drive.metadata"]

# Configura o log com rotação automática (máx 500KB por arquivo, guarda 5 versões antigas)
_formato = logging.Formatter(
    fmt="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)

_handler_arquivo = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=500_000, backupCount=5, encoding="utf-8"
)
_handler_arquivo.setFormatter(_formato)

_handler_console = logging.StreamHandler()
_handler_console.setFormatter(_formato)

logging.root.setLevel(logging.INFO)
logging.root.addHandler(_handler_arquivo)
logging.root.addHandler(_handler_console)

log = logging.getLogger(__name__)

# Silencia logs internos de bibliotecas (requests, google-api, urllib3)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("google_auth_httplib2").setLevel(logging.WARNING)


def autenticar_drive():
    """Autentica na Google Drive API usando OAuth2."""
    creds = None

    # Reutiliza token salvo se existir
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # Se não tem credenciais válidas, faz login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Salva o token para próximas execuções
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def baixar_kml():
    """Baixa o KML atual do mapa (suporta KML e KMZ)."""
    try:
        # Adiciona timestamp na URL para evitar cache do servidor
        url = f"{KML_URL}&_t={int(time.time())}"
        headers = {
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        resposta = requests.get(url, timeout=30, headers=headers)
        resposta.raise_for_status()

        content_type = resposta.headers.get("Content-Type", "")
        if "kmz" in content_type:
            # KMZ é um ZIP contendo doc.kml
            with zipfile.ZipFile(io.BytesIO(resposta.content)) as kmz:
                with kmz.open("doc.kml") as kml_file:
                    return kml_file.read().decode("utf-8")
        else:
            return resposta.text
    except Exception as e:
        log.error(f"Erro ao baixar KML: {e}")
        return None


def extrair_snapshot(kml_text):
    """
    Extrai um dicionário {nome_marcacao: estilo} do KML.
    O 'estilo' representa a cor/ícone da marcação.
    """
    snapshot = {}

    # Encontra todos os blocos <Placemark>
    placemarks = re.findall(r"<Placemark>([\s\S]*?)</Placemark>", kml_text)

    for pm in placemarks:
        # Nome da marcação
        nome_match = re.search(r"<name><!\[CDATA\[(.*?)\]\]></name>", pm) or \
                     re.search(r"<name>(.*?)</name>", pm)
        nome = nome_match.group(1).strip() if nome_match else "sem_nome"

        # Estilo (representa a cor/ícone)
        style_match = re.search(r"<styleUrl>(.*?)</styleUrl>", pm)
        estilo = style_match.group(1).strip() if style_match else "sem_estilo"

        snapshot[nome] = estilo

    return snapshot


def carregar_snapshot_anterior():
    """Carrega o snapshot salvo anteriormente."""
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def salvar_snapshot(snapshot):
    """Salva o snapshot atual no disco."""
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def detectar_mudancas(anterior, atual):
    """Compara dois snapshots e retorna lista de mudanças."""
    mudancas = []

    for nome, estilo_atual in atual.items():
        if nome not in anterior:
            mudancas.append(f"NOVA marcação: '{nome}'")
        elif anterior[nome] != estilo_atual:
            mudancas.append(
                f"COR ALTERADA: '{nome}' → de [{anterior[nome]}] para [{estilo_atual}]"
            )

    for nome in anterior:
        if nome not in atual:
            mudancas.append(f"REMOVIDA marcação: '{nome}'")

    return mudancas


def obter_nome_base_drive(drive_service):
    """Lê o nome atual do arquivo no Drive e remove o sufixo '| Att:' se existir."""
    try:
        arquivo = drive_service.files().get(fileId=DRIVE_FILE_ID, fields="name").execute()
        nome_atual = arquivo.get("name", NOME_BASE_ARQUIVO)
        if " | Att: " in nome_atual:
            return nome_atual.split(" | Att: ")[0].strip()
        return nome_atual
    except Exception as e:
        log.warning(f"Não foi possível ler nome do Drive, usando padrão: {e}")
        return NOME_BASE_ARQUIVO


def obter_data_modificacao_drive(drive_service):
    """Retorna a data/hora real da última modificação do mapa no Drive (horário de Brasília)."""
    try:
        arquivo = drive_service.files().get(
            fileId=DRIVE_FILE_ID,
            fields="modifiedTime"
        ).execute()
        # O Drive retorna UTC no formato: "2026-04-13T14:51:00.000Z"
        modificado_em = arquivo.get("modifiedTime", "")
        dt_utc = datetime.strptime(modificado_em, "%Y-%m-%dT%H:%M:%S.%fZ")
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        dt_brasilia = dt_utc.astimezone(timezone(timedelta(hours=-3)))
        return dt_brasilia.strftime("%d/%m/%Y %H:%M")
    except Exception as e:
        log.warning(f"Não foi possível obter data de modificação: {e}")
        return datetime.now().strftime("%d/%m/%Y %H:%M")


def renomear_arquivo_drive(drive_service, novo_nome):
    """Renomeia o arquivo no Google Drive."""
    try:
        drive_service.files().update(
            fileId=DRIVE_FILE_ID,
            body={"name": novo_nome}
        ).execute()
        log.info(f"Arquivo renomeado para: '{novo_nome}'")
    except Exception as e:
        log.error(f"Erro ao renomear arquivo no Drive: {e}")


def verificar_mapa():
    """Função principal: verifica mudanças e atualiza o Drive se necessário."""
    log.info("Verificando mapa...")

    kml = baixar_kml()
    if not kml:
        return

    snapshot_atual = extrair_snapshot(kml)

    if not snapshot_atual:
        log.warning("Nenhuma marcação encontrada no KML. Verifique a URL.")
        return

    log.info(f"  {len(snapshot_atual)} marcação(ões) encontrada(s) no mapa.")

    snapshot_anterior = carregar_snapshot_anterior()

    if snapshot_anterior is None:
        # Primeira execução: salva estado inicial
        salvar_snapshot(snapshot_atual)
        log.info(f"Primeiro snapshot salvo com {len(snapshot_atual)} marcações. Monitoramento ativo!")
        return

    mudancas = detectar_mudancas(snapshot_anterior, snapshot_atual)

    if mudancas:
        log.info(f"⚠️  {len(mudancas)} mudança(s) detectada(s)!")
        for m in mudancas:
            log.info(f"   → {m}")

        # Renomeia o arquivo no Drive com a data/hora real da modificação
        drive_service = autenticar_drive()
        nome_base = obter_nome_base_drive(drive_service)
        agora = obter_data_modificacao_drive(drive_service)
        novo_nome = f"{nome_base} | Att: {agora}"
        renomear_arquivo_drive(drive_service, novo_nome)

        # Atualiza o snapshot
        salvar_snapshot(snapshot_atual)
    else:
        log.info("Nenhuma mudança detectada.")


def main():
    log.info("=" * 50)
    log.info("  Monitor de Mapa iniciado")
    log.info(f"  Verificação a cada {INTERVALO_MINUTOS} minuto(s)")
    log.info("=" * 50)

    # Autentica logo ao iniciar (abre o navegador só uma vez)
    log.info("Autenticando no Google Drive...")
    autenticar_drive()
    log.info("Autenticado com sucesso!")

    # Executa imediatamente na primeira vez
    verificar_mapa()

    # Agenda para rodar conforme INTERVALO_MINUTOS
    schedule.every(INTERVALO_MINUTOS).minutes.do(verificar_mapa)

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("Monitor encerrado pelo usuário.")
        print("\nMonitor encerrado. Até mais!")


if __name__ == "__main__":
    main()