# Guida Pubblicazione su GitHub

Questa guida ti aiuta a pubblicare il progetto MCP SQL Server su GitHub.

## Preparazione

### 1. Verifica che tutto sia pronto

```bash
cd C:\Progetti Pilota\MCPSqlServer

# Verifica che non ci siano credenziali
git status

# Controlla che .env non sia tracciato
# Se appare in git status, FERMATI e rimuovilo
```

⚠️ **IMPORTANTE**: Non committare mai il file `.env` con credenziali reali!

### 2. Rimuovi file con credenziali

```bash
# Se hai file con credenziali, rimuovili dal tracking
git rm --cached .env
git rm --cached .claude/mcp.json
git rm --cached claude_desktop_config_TRANSITO.json

# Aggiungi al .gitignore (già fatto)
```

## Pubblicazione su GitHub

### Metodo 1: Da riga di comando (Git già configurato)

```bash
# 1. Inizializza repository (se non già fatto)
git init

# 2. Aggiungi remote
git remote add origin https://github.com/Attilio81/MCP-Sql-Server.git

# 3. Aggiungi tutti i file (esclusi quelli in .gitignore)
git add .

# 4. Verifica cosa stai per committare
git status

# 5. Assicurati che NON ci siano:
#    - .env
#    - .claude/mcp.json
#    - claude_desktop_config_*.json
#    - file con password/credenziali

# 6. Crea il commit iniziale
git commit -m "Initial commit: MCP SQL Server v0.1.0

- Secure MCP server for SQL Server database inspection
- Connection pooling with configurable pool size
- Advanced security: SQL injection prevention, blacklist/whitelist
- Complete MCP tools: list_tables, describe_table, execute_query, get_table_relationships
- Comprehensive documentation and setup scripts
- Full test suite with connection validation"

# 7. Push su GitHub
git branch -M main
git push -u origin main
```

### Metodo 2: Da GitHub Desktop

1. Apri GitHub Desktop
2. File → Add Local Repository
3. Seleziona: `C:\Progetti Pilota\MCPSqlServer`
4. Clicca "Publish repository"
5. Seleziona:
   - Repository name: `MCP-Sql-Server`
   - Description: "Secure MCP server for SQL Server database inspection"
   - ☐ Keep this code private (se vuoi renderlo privato)
6. Clicca "Publish Repository"

## Dopo la Pubblicazione

### 1. Verifica su GitHub

Vai su https://github.com/Attilio81/MCP-Sql-Server e verifica:

- ✅ README.md è visualizzato correttamente
- ✅ I badge sono funzionanti
- ✅ LICENSE è presente
- ✅ SECURITY.md è presente
- ✅ CONTRIBUTING.md è presente
- ❌ Nessun file `.env` o con credenziali

### 2. Configura GitHub Repository

#### Descrizione e Topics

1. Vai su Settings
2. Aggiungi Description:
   ```
   Secure MCP server for SQL Server database inspection. Connect Claude to your SQL Server databases with advanced security features.
   ```
3. Aggiungi Topics (tags):
   ```
   mcp
   sql-server
   claude-ai
   database
   python
   mcp-server
   claude-desktop
   claude-code
   pyodbc
   database-tools
   ```

#### Branch Protection (opzionale ma raccomandato)

1. Settings → Branches
2. Add branch protection rule
3. Branch name pattern: `main`
4. Abilita:
   - ☑ Require pull request reviews before merging
   - ☑ Require status checks to pass before merging

#### Issues Templates

Crea `.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''
---

**Describe the bug**
A clear and concise description of what the bug is.

**Environment**
- Python version:
- OS:
- SQL Server version:
- ODBC Driver version:

**To Reproduce**
Steps to reproduce the behavior:
1. Configure '...'
2. Run '...'
3. See error

**Expected behavior**
What you expected to happen.

**Logs**
```
Paste relevant logs here (remove credentials!)
```

**Additional context**
Any other context about the problem.
```

### 3. Crea un Release

1. Vai su "Releases" → "Create a new release"
2. Tag version: `v0.1.0`
3. Release title: `v0.1.0 - Initial Release`
4. Description:
   ```markdown
   # MCP SQL Server v0.1.0 - Initial Release

   First stable release of MCP SQL Server, a secure MCP server for SQL Server database inspection.

   ## Features

   - 🔒 **Advanced Security**: SQL injection prevention, table blacklist/whitelist, query validation
   - 🏊 **Connection Pooling**: Efficient connection management with automatic recovery
   - 🛠️ **Complete MCP Tools**:
     - `list_tables`: List database tables with metrics
     - `describe_table`: Show complete table schema with samples
     - `execute_query`: Execute safe SELECT queries
     - `get_table_relationships`: Analyze foreign key relationships
   - 📝 **Comprehensive Documentation**: Setup guides, security best practices, troubleshooting
   - 🧪 **Test Suite**: Automated connection and functionality tests

   ## Installation

   ```bash
   git clone https://github.com/Attilio81/MCP-Sql-Server.git
   cd MCP-Sql-Server
   pip install -e .
   ```

   See [README.md](README.md) for detailed setup instructions.

   ## Compatibility

   - Python 3.10+
   - SQL Server (any version)
   - Claude Desktop
   - Claude Code

   ## What's Next

   See [Roadmap](README.md#roadmap) for planned features.
   ```

5. Clicca "Publish release"

### 4. Aggiungi README Badges (già fatto)

I badge nel README mostrano lo stato del progetto:
- ![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
- ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
- ![MCP](https://img.shields.io/badge/MCP-1.0-green.svg)

## Promuovi il Progetto

### 1. Condividi nella Community

- [MCP Servers Discussion](https://github.com/modelcontextprotocol/servers/discussions)
- Reddit: r/ClaudeAI
- Twitter/X con hashtag: #ClaudeAI #MCP #SQLServer
- LinkedIn

### 2. Aggiungi al MCP Servers List

Considera di proporre l'aggiunta alla lista ufficiale:
https://github.com/modelcontextprotocol/servers

### 3. Scrivi un Blog Post

Condividi:
- Perché hai creato questo progetto
- Come funziona
- Esempi di utilizzo
- Lessons learned

## Manutenzione

### Aggiornamenti Futuri

Quando aggiungi nuove feature:

```bash
# 1. Crea branch
git checkout -b feature/nome-feature

# 2. Fai le modifiche
# ...

# 3. Commit
git add .
git commit -m "feat: add feature description"

# 4. Push
git push origin feature/nome-feature

# 5. Crea Pull Request su GitHub
```

### Gestione Issues

Quando qualcuno apre un issue:
1. Leggi attentamente
2. Riproduci il problema
3. Rispondi entro 48 ore
4. Label appropriata (bug, enhancement, question, etc.)
5. Milestone (se parte di una release)

### Gestione Pull Requests

Quando ricevi una PR:
1. Review del codice
2. Verifica test
3. Prova localmente
4. Commenta/richiedi modifiche se necessario
5. Merge quando tutto ok

## Sicurezza

⚠️ **Revisione Periodica**

Ogni 3-6 mesi:

```bash
# Controlla history per credenziali accidentali
git log --all --full-history --source -- .env

# Se trovi credenziali:
# 1. Ruota immediatamente le credenziali compromesse
# 2. Usa git-filter-repo per rimuovere dalla history
# 3. Force push (ATTENZIONE!)
```

## Checklist Pre-Push

Prima di ogni push, verifica:

- [ ] Nessun file `.env`
- [ ] Nessuna password hardcoded
- [ ] `.gitignore` aggiornato
- [ ] Test passano: `python test_connection.py`
- [ ] Documentazione aggiornata
- [ ] Commit message chiaro
- [ ] Branch corretto

## Risorse Utili

- [GitHub Docs](https://docs.github.com/)
- [Git Best Practices](https://git-scm.com/book/en/v2)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

**Congratulazioni!** 🎉 Il tuo progetto è ora su GitHub e pronto per essere condiviso con la community!
