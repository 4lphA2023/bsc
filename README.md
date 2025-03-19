# BSC Token Sniper

Un sistema modulare e sicuro per il monitoraggio e l'acquisto automatico di token sulla Binance Smart Chain (BSC), che consente l'analisi automatizzata dei token, l'acquisto e la realizzazione di profitti.

## Caratteristiche

- **Connessione Web3 Robusta**: Molteplici endpoint RPC di fallback e logica di ripetizione
- **Analisi dei Token**: Controlli di sicurezza completi tra cui:
  - Analisi del codice del contratto per individuare pattern sospetti
  - Verifica della liquidità
  - Rilevamento honeypot tramite test di acquisto/vendita
  - Analisi della cronologia delle transazioni
- **Gestione del Portafoglio**: Presa di profitto e stop-loss automatizzati
- **Sicurezza Prima di Tutto**: Estesa blacklist, verifica e monitoraggio
- **Design Modulare**: Codice ben organizzato per facile manutenzione ed estensione

## Installazione (Windows)

1. Clona il repository:
```
git clone https://github.com/4lphA2023/bsc-token-sniper.git
cd bsc-token-sniper
```

2. Esegui il file batch di installazione:
```
install.bat
```

3. Modifica il file `.env` con le tue credenziali di wallet e le impostazioni:
```
# Endpoint RPC BSC - Aggiorna con endpoint premium se disponibili
# Endpoint pubblici gratuiti (mantieni come fallback)
BSC_MAINNET_RPC_1=https://bsc-dataseed.binance.org/
BSC_MAINNET_RPC_2=https://bsc-dataseed1.defibit.io/
BSC_MAINNET_RPC_3=https://bsc-dataseed1.ninicoin.io/

# Aggiungi endpoint premium/più affidabili (se li hai)
# Esempio QuickNode (sostituisci con il tuo endpoint effettivo se ne hai uno)
BSC_MAINNET_RPC_4=https://YOUR_QUICKNODE_KEY.bsc.quiknode.pro/YOUR_TOKEN/
# Esempio Ankr
BSC_MAINNET_RPC_5=https://rpc.ankr.com/bsc/YOUR_ANKR_TOKEN

# Credenziali del wallet (CRITICHE - NON CONDIVIDERLE MAI!)
PRIVATE_KEY=la_tua_chiave_privata_qui
WALLET_ADDRESS=il_tuo_indirizzo_wallet_qui

# Chiave API BSCScan (importante per la verifica dei token)
BSCSCAN_API_KEY=la_tua_chiave_api_bscscan

# Impostazioni di investimento
MAX_INVESTMENT_PER_TOKEN=0.02  # Ridotto per iniziare con un rischio inferiore
MIN_LIQUIDITY=5                # Liquidità minima richiesta in BNB
SLIPPAGE=10                    # 10% di tolleranza slippage
GAS_MULTIPLIER=1.2             # Moltiplicatore del prezzo del gas per transazioni più veloci

# Impostazioni anti-truffa
TEST_BUY_AMOUNT=0.005          # Importo da utilizzare per i test di acquisto
MIN_SUCCESSFUL_SELLS=3         # Numero richiesto di vendite di successo nella cronologia
HONEYPOT_CHECK_ENABLED=true    # Abilita il rilevamento di honeypot
ASSEMBLY_CHECK_ENABLED=true    # Abilita il rilevamento di codice sospetto
LIQUIDITY_SAFETY_MULTIPLIER=1.5 # Fattore di sicurezza per investimento vs. liquidità

# Impostazioni di presa di profitto
TAKE_PROFIT_PERCENTAGE=20      # Vendi quando il profitto raggiunge il 20%
STOP_LOSS_PERCENTAGE=10        # Vendi quando la perdita raggiunge il 10%
MAX_HOLDING_TIME=24            # Tempo massimo di detenzione in ore
MONITORING_INTERVAL=60         # Controlla il portafoglio ogni 60 secondi

# Indirizzi dei contratti (BSC Mainnet)
WBNB_ADDRESS=0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c
BUSD_ADDRESS=0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56
```

## Servizi RPC Premium

Per un funzionamento ottimale del sistema, considera l'utilizzo di servizi RPC premium:

- **QuickNode** (https://www.quicknode.com/): Offre un piano gratuito per iniziare
- **Ankr** (https://www.ankr.com/): Ha opzioni a prezzi ragionevoli
- **GetBlock.io** (https://getblock.io/): Tier gratuito disponibile
- **NOWNodes** (https://nownodes.io/): Prova gratuita disponibile

I servizi premium offrono:
- Limiti di frequenza più elevati (meno errori "limit exceeded")
- Connessioni più affidabili
- Tempi di risposta più rapidi
- Migliore accesso ai dati storici

## Utilizzo

### Analizzare un Token

Per analizzare un token senza acquistarlo:

```
python main.py --token 0xIndirizzoTokenQui
```

### Acquistare un Token

Per analizzare e acquistare un token con un importo BNB specificato:

```
python main.py --token 0xIndirizzoTokenQui --amount 0.1
```

### Modalità di Scoperta Automatica

Per rilevare e analizzare automaticamente nuovi token appena vengono listati:

```
python main.py --auto
```

### Scansione dei Blocchi Recenti

Per scansionare i blocchi recenti alla ricerca di nuove coppie create:

```
python main.py --scan 200  # Scansiona gli ultimi 200 blocchi (ridotto per evitare limiti di frequenza)
```

### Gestione del Portafoglio

Visualizza il tuo portafoglio attuale:

```
python main.py --portfolio
```

Visualizza la cronologia delle transazioni:

```
python main.py --transactions
```

Controlla il riepilogo dei profitti:

```
python main.py --profits
```

### Esegui in Modalità Monitoraggio

Per avviare solo il monitoraggio del portafoglio (utile se hai già acquistato token):

```
python main.py
```

## Struttura del Progetto

```
bsc_token_sniper/
├── setup.py                # File di configurazione del pacchetto
├── main.py                 # Script di esecuzione principale
├── config.py               # Impostazioni di configurazione
├── utils/                  # Funzioni di utilità
│   ├── web3_singleton.py   # Singleton Web3 per gestire la connessione
├── contracts/              # ABI dei contratti e interfacce
├── database/               # Modelli e operazioni del database
├── security/               # Controlli di sicurezza
├── tokendata/              # Analisi dei token (rinominato da token)
├── trading/                # Operazioni di acquisto/vendita
├── portfolio/              # Gestione del portafoglio
└── requirements.txt        # Dipendenze del progetto
```

## Risoluzione dei Problemi di Limite di Frequenza

Se riscontri errori "limit exceeded" durante l'esecuzione, prova questi suggerimenti:

1. **Riduci l'intervallo di scansione**: Usa `--scan 200` invece di valori più grandi
2. **Utilizza endpoint RPC premium**: Aggiorna il file `.env` con endpoint premium
3. **Aumenta i tempi di attesa**: Se hai modificato il codice, aumenta i tempi di attesa tra le richieste
4. **Esegui in orari meno congestionati**: L'attività della rete è più bassa in certi orari

## Problemi con Web3.py 7.x

Se stai utilizzando una versione recente di Web3.py (7.x), potrebbero verificarsi problemi di compatibilità. Questo progetto è stato aggiornato per supportare Web3.py 7.6.1 con modifiche specifiche nel modulo di scoperta dei token.

Librerie richieste:
```
web3>=7.0.0
python-dotenv>=0.20.0
requests>=2.28.0
pandas>=1.4.2
```

## Avvertenza di Sicurezza

- **MAI** condividere la tua chiave privata
- Testa prima con piccole somme
- Il trading di criptovalute comporta rischi significativi
- Questo strumento è solo per scopi educativi

## Note Importanti per la Sicurezza

1. **Protezione della Chiave Privata**: Mai condividere o esporre la tua chiave privata
2. **Wallet Separato**: Usa un wallet separato con fondi limitati per il trading automatico
3. **Monitoraggio Regolare**: Controlla regolarmente l'attività del bot e i risultati
4. **Backup**: Mantieni backup regolari del database per evitare perdite di dati

## Licenza

Questo progetto è concesso in licenza secondo i termini della Licenza MIT - vedi il file LICENSE per i dettagli.

## Dichiarazione di non responsabilità

Questo progetto è solo per scopi educativi. Usalo a tuo rischio. Gli autori non sono responsabili per eventuali perdite finanziarie subite durante l'utilizzo di questo software.
