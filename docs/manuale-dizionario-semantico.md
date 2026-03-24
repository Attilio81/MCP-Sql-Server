# Manuale: Dizionario Semantico per Server MCP

## Cos'è il dizionario semantico

Ogni database aziendale ha un vocabolario interno che non si deduce dallo schema: `anagra` non ti dice niente, ma `clienti` sì. Il dizionario semantico è un file Markdown in cui Claude accumula questa conoscenza man mano che chatta con te.

**Problema che risolve:** senza dizionario, Claude deve re-esplorare lo schema ad ogni sessione per capire che "cliente" abita nella tabella `anagra`, che "attivo" si traduce in `stato = 'A'`, e che `anagra.codice` si collega a `ordini.codcli`. Con il dizionario, Claude parte già informato.

**Come funziona:**
1. Fai una domanda: *"quante vendite ha fatto Mario Rossi?"*
2. Claude esplora lo schema, trova che `Mario Rossi` è in `anagra.cognome + nome`
3. Claude salva questa scoperta nel dizionario (in background, senza chiederti conferma)
4. Claude risponde e ti dice: *"Ho salvato nel dizionario che 'cliente per nome' corrisponde ai campi `cognome, nome` della tabella `anagra`"*
5. Sessione successiva: Claude legge il dizionario all'avvio e già conosce il mapping

---

## Configurazione

### Parametro `--dictionary-file`

Ogni server MCP può avere il proprio file dizionario. Si configura nel Manager UI oppure manualmente nel `claude_desktop_config.json`.

```json
{
  "mcpServers": {
    "db-vendite": {
      "command": "python",
      "args": [
        "-m", "mcp_sqlserver.server",
        "--connection-string", "Driver=...;Server=...;Database=Vendite;",
        "--dictionary-file", "C:\\dizionari\\vendite_dictionary.md"
      ]
    },
    "db-magazzino": {
      "command": "python",
      "args": [
        "-m", "mcp_sqlserver.server",
        "--connection-string", "Driver=...;Server=...;Database=Magazzino;",
        "--dictionary-file", "C:\\dizionari\\magazzino_dictionary.md"
      ]
    }
  }
}
```

| Parametro | Variabile d'ambiente | Default |
|-----------|---------------------|---------|
| `--dictionary-file` | `DICTIONARY_FILE` | `semantic_dictionary.md` (nella directory di lavoro del processo) |

> **Raccomandazione:** usa sempre path assoluti per i file dizionario, specialmente in setup multi-server. Il default relativo funziona solo se il processo MCP parte sempre dalla stessa directory.

### Configurazione tramite Manager UI

1. Apri il Manager (`python -m manager.server` → `http://localhost:8090`)
2. Aggiungi o modifica una connessione
3. Compila il campo **"File Dizionario"** con il path assoluto del file `.md`
4. Salva

Il campo è opzionale: se lasciato vuoto, usa il default `semantic_dictionary.md`.

---

## Formato del file dizionario

Il file è Markdown standard con tre sezioni tabellari. Claude mantiene questo formato automaticamente.

```markdown
# Dizionario Semantico
> Aggiornato automaticamente da Claude. Modificabile manualmente.

## Entità di Business
| Termine utente | Tabella | Campi chiave | Note |
|----------------|---------|--------------|------|
| cliente | anagra | codice, cognome, nome | chiave primaria: codice |
| articolo | tabArt | codart, descr | |
| agente | agenti | codage, descage | |

## Filtri e Alias
| Espressione utente | SQL equivalente | Note |
|--------------------|-----------------|------|
| "attivo" | stato = 'A' | campo in anagra |
| "anno corrente" | YEAR(data_doc) = YEAR(GETDATE()) | |
| "clienti nuovi" | data_ins >= DATEADD(year,-1,GETDATE()) | |

## Relazioni Notevoli
| Tabella da | Campo | Tabella a | Campo | Descrizione |
|------------|-------|-----------|-------|-------------|
| anagra | codice | ordini | codcli | clienti e loro ordini |
| tabArt | codart | ordini | codart | articoli negli ordini |
```

### Le tre sezioni

| Sezione | Cosa contiene | Esempio |
|---------|---------------|---------|
| **Entità di Business** | Nomi usati dall'utente → tabella e campi dove abitano | "cliente" → `anagra` |
| **Filtri e Alias** | Espressioni in linguaggio naturale → SQL equivalente | "attivo" → `stato = 'A'` |
| **Relazioni Notevoli** | Join non ovvi tra tabelle | `anagra.codice` → `ordini.codcli` |

---

## Come Claude usa il dizionario

### Lettura automatica all'avvio

Il dizionario è esposto come **MCP Resource** (`db://dictionary`). Claude lo carica automaticamente come contesto all'inizio di ogni sessione — senza che tu debba chiederlo.

### Quando Claude aggiorna il dizionario

Claude chiama il tool `update_dictionary` ogni volta che scopre:
- Quale tabella/colonne corrispondono a un'entità nominata dall'utente
- Un'espressione filtro ricorrente non ovvia dallo schema
- Un join tra tabelle non deducibile dai nomi delle colonne

Claude **non** chiede conferma prima di scrivere. Ti notifica conversazionalmente dopo:
> *"Ho salvato nel dizionario che 'cliente' corrisponde alla tabella `anagra` — lo ricorderò nelle prossime sessioni."*

Claude **non** scrive nel dizionario per:
- Informazioni già presenti
- Mappings ovvi dal nome della tabella stessa (es. una tabella già chiamata `clienti`)

### Deduplicazione automatica

Se Claude scopre una versione aggiornata di un mapping già salvato, **sostituisce la riga esistente** invece di aggiungerne una duplicata. La chiave di deduplicazione è il primo campo di ogni riga.

---

## Manager UI: editor del dizionario

### Aprire il dizionario di un server

Nel Manager, ogni card server ha un pulsante **📖**. Al click:
1. Si apre un modal con il titolo *"Dizionario Semantico — {nome-server}"*
2. Viene caricato il contenuto attuale del file `.md`
3. Puoi modificarlo liberamente nella textarea (font monospace)
4. Premi **Salva Modifiche** per scrivere le modifiche sul file

### Casi d'uso per la modifica manuale

- **Correggere un errore:** Claude ha salvato un mapping sbagliato → correggilo direttamente
- **Trasferire conoscenza:** hai già un dizionario per `db-vendite` e vuoi portare alcune sezioni in `db-magazzino` → copia-incolla dal modal di un server a quello dell'altro
- **Pre-popolare:** se conosci il dominio, puoi riempire il dizionario prima ancora di iniziare a chattare con Claude

---

## Setup multi-server

Ogni server MCP ha il **proprio** dizionario indipendente. Questo è intenzionale: `db-vendite` e `db-magazzino` hanno domini diversi e vocabolari diversi.

```
C:\dizionari\
├── vendite_dictionary.md      ← usato da db-vendite
├── magazzino_dictionary.md    ← usato da db-magazzino
└── hr_dictionary.md           ← usato da db-hr
```

Per trasferire una sezione da un dizionario a un altro:
1. Apri il Manager (`http://localhost:8090`)
2. Clicca 📖 su `db-vendite` → copia la sezione che ti interessa
3. Clicca 📖 su `db-magazzino` → incolla in fondo alla sezione corrispondente
4. Salva

---

## Riferimento tecnico

### MCP Resource: `db://dictionary`

| Proprietà | Valore |
|-----------|--------|
| URI | `db://dictionary` |
| MIME type | `text/markdown` |
| Comportamento se file mancante | Restituisce stringa vuota (nessun errore) |

### MCP Tool: `update_dictionary`

| Parametro | Tipo | Obbligatorio | Descrizione |
|-----------|------|-------------|-------------|
| `section` | `"entities" \| "filters" \| "relations"` | ✓ | Sezione target |
| `key` | `string` | ✓ | Primo campo della riga (usato per deduplicazione) |
| `row` | `string` | ✓ | Riga completa in formato Markdown table |

**Formato `row` per sezione:**
```
entities:  | termine utente | tabella | campi chiave | note |
filters:   | espressione utente | sql equivalente | note |
relations: | tabella da | campo | tabella a | campo | descrizione |
```

### API Manager

| Metodo | Path | Descrizione |
|--------|------|-------------|
| `GET` | `/api/dictionary/{server_name}` | Restituisce `{"content": "..."}`, stringa vuota se file non esiste |
| `POST` | `/api/dictionary/{server_name}` | Salva `{"content": "..."}` nel file associato al server |

Entrambi restituiscono `404` se il server non è configurato nel `claude_desktop_config.json`.

---

## Domande frequenti

**Il dizionario viene condiviso tra Claude Desktop e Claude Code?**
No. Ogni client MCP mantiene la propria sessione. Tuttavia, il file `.md` è condiviso: se Claude Desktop e Claude Code puntano allo stesso `--dictionary-file`, entrambi leggono e scrivono sullo stesso file.

**Claude sovrascrive le mie modifiche manuali?**
No. `update_dictionary` fa upsert riga per riga: sostituisce una riga esistente con la stessa chiave, o aggiunge in fondo alla sezione. Non riscrive mai l'intero file. Le tue modifiche ad altre righe rimangono intatte.

**Cosa succede se il file dizionario non esiste?**
- In lettura (`db://dictionary`): Claude riceve una stringa vuota e parte senza contesto pregresso
- In scrittura (`update_dictionary`): il file viene creato automaticamente con la struttura base

**Posso versionare il dizionario con git?**
Sì, è un file Markdown come gli altri. Se metti il file dizionario nella cartella del progetto (o in una cartella tracciata), git history ti mostrerà l'evoluzione delle scoperte semantiche nel tempo.

**Il dizionario rallenta Claude?**
No. Viene caricato come contesto all'avvio della sessione, non consultato durante ogni query. Il file è testuale e compatto — anche con centinaia di righe, il caricamento è istantaneo.
