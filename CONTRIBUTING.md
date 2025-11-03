# Contributing to MCP SQL Server

Thank you for your interest in contributing to MCP SQL Server! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:

1. **Clear title**: Describe the issue concisely
2. **Environment details**:
   - Python version
   - OS and version
   - SQL Server version
   - ODBC driver version
3. **Steps to reproduce**: Detailed steps to recreate the issue
4. **Expected behavior**: What should happen
5. **Actual behavior**: What actually happens
6. **Logs**: Relevant error messages or logs (remove credentials!)
7. **Screenshots**: If applicable

**Example:**
```
Title: Connection pool exhaustion on high concurrent queries

Environment:
- Python 3.11.5
- Windows 11
- SQL Server 2019
- ODBC Driver 17

Steps to reproduce:
1. Set POOL_SIZE=2
2. Execute 10 concurrent queries
3. Observe timeout errors

Expected: Queries should queue and execute
Actual: TimeoutError after 5 queries

Logs:
[ERROR] Timeout acquisizione connessione dal pool
```

### Suggesting Features

For feature requests, create an issue with:

1. **Use case**: Describe the problem this feature solves
2. **Proposed solution**: How you envision the feature working
3. **Alternatives**: Other approaches you've considered
4. **Additional context**: Any relevant examples or mockups

### Pull Requests

We welcome pull requests! Here's the process:

#### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/yourusername/MCP-Sql-Server.git
cd MCP-Sql-Server
```

#### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-123
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions/fixes

#### 3. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pip install pre-commit
pre-commit install
```

#### 4. Make Your Changes

- Follow the existing code style
- Add tests for new features
- Update documentation as needed
- Keep commits focused and atomic

#### 5. Test Your Changes

```bash
# Run existing tests
pytest tests/

# Test connection
python test_connection.py

# Manual testing
python -m mcp_sqlserver.server

# Linting
ruff check src/

# Formatting
ruff format src/
```

#### 6. Commit Your Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: add PostgreSQL support

- Implement PostgreSQL connection handler
- Add PostgreSQL-specific query validation
- Update documentation with PostgreSQL examples
- Add tests for PostgreSQL functionality

Closes #123"
```

Commit message format:
```
<type>: <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Test additions/updates
- `chore`: Maintenance tasks

#### 7. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:

- **Clear title**: Summarize the changes
- **Description**: Explain what, why, and how
- **Related issues**: Reference issues with `Closes #123`
- **Screenshots**: If UI changes
- **Checklist**: Confirm all requirements met

**Pull Request Template:**
```markdown
## Description
Brief description of changes

## Related Issues
Closes #123

## Changes Made
- Added X functionality
- Fixed Y bug
- Updated Z documentation

## Testing
- [ ] All tests pass
- [ ] Added tests for new functionality
- [ ] Manual testing completed
- [ ] Documentation updated

## Screenshots (if applicable)
...

## Checklist
- [ ] Code follows project style
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Tests added/updated
```

## Development Guidelines

### Code Style

- Follow PEP 8 Python style guide
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use descriptive variable names

**Example:**
```python
# Good
def execute_query_with_timeout(query: str, timeout: int) -> list[tuple]:
    """Execute SQL query with specified timeout."""
    pass

# Avoid
def eq(q, t):
    pass
```

### Documentation

- Add docstrings to all public functions/classes
- Use Google-style docstrings
- Update README.md for user-facing changes
- Add inline comments for complex logic

**Example:**
```python
def validate_query(query: str) -> tuple[bool, str]:
    """
    Validate query is safe to execute.

    Checks for dangerous SQL keywords, injection patterns,
    and ensures query is SELECT-only.

    Args:
        query: SQL query string to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if query is safe
        - error_message: Empty string if valid, error description otherwise

    Example:
        >>> validate_query("SELECT * FROM users")
        (True, "")
        >>> validate_query("DROP TABLE users")
        (False, "Keyword 'DROP' not permitted in query")
    """
    pass
```

### Testing

- Write unit tests for new functionality
- Aim for >80% code coverage
- Use pytest fixtures for common setup
- Mock database connections in tests

**Example test:**
```python
import pytest
from mcp_sqlserver.server import SecurityValidator

def test_validate_query_allows_select():
    """Test that valid SELECT queries are allowed."""
    query = "SELECT * FROM users WHERE id = 1"
    is_valid, error = SecurityValidator.validate_query(query)
    assert is_valid is True
    assert error == ""

def test_validate_query_blocks_drop():
    """Test that DROP statements are blocked."""
    query = "DROP TABLE users"
    is_valid, error = SecurityValidator.validate_query(query)
    assert is_valid is False
    assert "DROP" in error
```

### Security

- Never commit credentials or sensitive data
- Use prepared statements for SQL queries
- Validate all user input
- Document security considerations
- Report security issues privately (see SECURITY.md)

### Performance

- Consider connection pool impact
- Avoid N+1 query patterns
- Use appropriate timeouts
- Profile performance-critical code
- Document performance characteristics

## Project Structure

Understanding the codebase:

```
mcp-sqlserver/
├── src/mcp_sqlserver/
│   ├── __init__.py           # Package initialization
│   └── server.py             # Main MCP server (480 lines)
│       ├── ConnectionPool    # Connection management
│       ├── SecurityValidator # Security validation
│       ├── list_tools()      # MCP tool definitions
│       ├── call_tool()       # MCP tool dispatcher
│       └── handle_*()        # Individual tool handlers
├── tests/                    # Unit tests (TODO: expand)
├── .env.example              # Environment template
├── pyproject.toml            # Package configuration
├── README.md                 # Main documentation
├── CLAUDE_CODE_USAGE.md      # Claude Code guide
├── SECURITY.md               # Security guidelines
├── CONTRIBUTING.md           # This file
└── test_connection.py        # Connection test script
```

## Key Components

### ConnectionPool Class
Manages database connections with thread-safe pooling:
- `__init__`: Initialize pool with connections
- `get_connection`: Context manager for acquiring connections
- `close_all`: Cleanup all connections

### SecurityValidator Class
Static methods for security validation:
- `is_table_allowed`: Check blacklist/whitelist
- `validate_query`: Validate SQL query safety

### MCP Tool Handlers
- `handle_list_tables`: List database tables
- `handle_describe_table`: Show table schema
- `handle_execute_query`: Execute SELECT queries
- `handle_table_relationships`: Show foreign keys

## Adding New Features

### Example: Adding a New Tool

1. **Define the tool in `list_tools()`:**
```python
Tool(
    name="export_data",
    description="Export query results to CSV",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "filename": {"type": "string"},
        },
        "required": ["query", "filename"],
    },
)
```

2. **Add handler in `call_tool()`:**
```python
elif name == "export_data":
    return await handle_export_data(pool, arguments)
```

3. **Implement the handler:**
```python
async def handle_export_data(pool: ConnectionPool, arguments: dict) -> list[TextContent]:
    """Handle export_data tool."""
    query = arguments["query"]
    filename = arguments["filename"]

    # Validate query
    is_valid, error = SecurityValidator.validate_query(query)
    if not is_valid:
        return [TextContent(type="text", text=f"Query invalid: {error}")]

    # Execute and export
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        # ... export logic ...

    return [TextContent(type="text", text=f"Exported to {filename}")]
```

4. **Add tests:**
```python
def test_export_data_validates_query():
    """Test export_data validates queries."""
    # ... test implementation ...
```

5. **Update documentation:**
- Add to README.md under "Available Tools"
- Add usage examples
- Update CLAUDE_CODE_USAGE.md if relevant

## Review Process

Pull requests are reviewed for:

1. **Functionality**: Does it work as intended?
2. **Code quality**: Is it readable and maintainable?
3. **Tests**: Are there adequate tests?
4. **Documentation**: Is it well-documented?
5. **Security**: Are there security concerns?
6. **Performance**: Any performance impact?
7. **Breaking changes**: Are they necessary and documented?

Reviews typically take 2-7 days. Be patient and responsive to feedback.

## Release Process

Maintainers handle releases:

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create git tag: `git tag v0.2.0`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions builds and publishes to PyPI

## Questions?

- **General questions**: Open a Discussion on GitHub
- **Bug reports**: Create an Issue
- **Security concerns**: See SECURITY.md for private reporting
- **Feature requests**: Create an Issue with the "enhancement" label

## Recognition

Contributors are recognized in:
- GitHub contributors list
- Release notes
- Annual contributor recognition

Thank you for contributing to MCP SQL Server! 🎉
