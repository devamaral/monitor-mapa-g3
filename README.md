# Monitor de Mapa — Google My Maps

Monitora automaticamente um mapa do Google My Maps e, ao detectar qualquer alteração (mudança de cor, nova marcação ou remoção), renomeia o arquivo no Google Drive com a data e hora exata da modificação.

---

## O que ele faz

- A cada 2 horas baixa os dados do mapa em formato KML
- Compara com o estado salvo da última verificação
- Se algo mudou, renomeia o arquivo no Drive:
  ```
  Adesivos abril | Att: 13/04/2026 09:47
  ```
- Registra tudo em `monitor_mapa.log` para consulta posterior

---

## Pré-requisitos

- Python 3.8 ou superior
- Conta Google com acesso ao mapa e ao Google Drive
- Arquivo `credentials.json` obtido pelo Google Cloud Console

### Instalação das dependências

```bash
pip install requests google-auth google-auth-oauthlib google-api-python-client schedule
```

---

## Configuração

### 1. Obter o `credentials.json`

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto → ative a **Google Drive API**
3. Em **Credenciais** → crie uma **ID do cliente OAuth 2.0** (tipo: Aplicativo de computador)
4. Baixe o arquivo e salve como `credentials.json` na pasta do script

### 2. Preencher as configurações no código

Abra `monitor_mapa.py` e edite as três variáveis no topo:

```python
# URL do mapa: pegue o "mid" da URL do Google My Maps
# Exemplo de URL: https://www.google.com/maps/d/edit?mid=SEU_MID_AQUI
KML_URL = "https://www.google.com/maps/d/kml?mid=SEU_MID_AQUI"

# Mesmo "mid" da URL acima
DRIVE_FILE_ID = "SEU_MID_AQUI"

# Nome base do arquivo no Drive (sem o "Att:")
NOME_BASE_ARQUIVO = "Nome do seu mapa"
```

---

## Como executar

### Manualmente (com janela visível)

```bash
python monitor_mapa.py
```

### Em segundo plano (sem janela — recomendado)

```bash
pythonw monitor_mapa.py
```

### Iniciar automaticamente com o Windows

1. Crie um arquivo `iniciar_monitor.bat` com o conteúdo:
   ```bat
   @echo off
   start "" pythonw "C:\caminho\completo\monitor_mapa.py"
   ```
2. Pressione `Win + R` → digite `shell:startup` → Enter
3. Cole o atalho do `.bat` nessa pasta

Na primeira execução, o navegador abrirá para você autorizar o acesso ao Google Drive. Após isso, o token fica salvo e não será necessário repetir.

---

## Visualizando o log

Abra o arquivo `monitor_mapa.log` com qualquer editor de texto (Notepad, VS Code, etc.).

O log registra:
- Início do script
- Cada verificação realizada
- Mudanças detectadas e seus detalhes
- Erros, caso ocorram

Exemplo de log limpo (sem mudanças):
```
13/04/2026 11:00:00  [INFO    ]  ==================================================
13/04/2026 11:00:00  [INFO    ]  Monitor de Mapa iniciado
13/04/2026 11:00:00  [INFO    ]  Verificação a cada 2 horas
13/04/2026 11:00:00  [INFO    ]  ==================================================
13/04/2026 11:00:00  [INFO    ]  Autenticando no Google Drive...
13/04/2026 11:00:00  [INFO    ]  Autenticado com sucesso!
13/04/2026 11:00:00  [INFO    ]  Verificando mapa...
13/04/2026 11:00:00  [INFO    ]  Nenhuma mudança detectada.
```

Exemplo com mudança detectada:
```
13/04/2026 13:00:00  [INFO    ]  Verificando mapa...
13/04/2026 13:00:00  [INFO    ]  2 mudança(s) detectada(s)!
13/04/2026 13:00:00  [INFO    ]     → COR ALTERADA: '010040' → de [#icon-verde] para [#icon-vermelho]
13/04/2026 13:00:00  [INFO    ]     → NOVA marcação: '090099'
13/04/2026 13:00:00  [INFO    ]  Arquivo renomeado para: 'Adesivos abril | Att: 13/04/2026 12:47'
```

O arquivo de log é rotacionado automaticamente ao atingir 500 KB, mantendo até 5 versões anteriores.

---

## Arquivos do projeto

| Arquivo | Descrição |
|---|---|
| `monitor_mapa.py` | Script principal |
| `credentials.json` | Credenciais do Google (**não subir no git**) |
| `token.json` | Token de autenticação gerado automaticamente (**não subir no git**) |
| `snapshot_anterior.json` | Estado do mapa na última verificação (gerado automaticamente) |
| `monitor_mapa.log` | Registro de todas as execuções |
| `iniciar_monitor.bat` | Atalho para iniciar em segundo plano |

---