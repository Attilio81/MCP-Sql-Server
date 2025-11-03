# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to the repository maintainer. You can find the contact information in the GitHub profile.

Include as much information as possible:
- Type of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

You should receive a response within 48 hours. We'll keep you updated on the progress.

## Security Best Practices

### For Users

#### 1. Credential Management

**DO:**
- Use environment variables for credentials
- Use Windows Authentication when possible
- Use Azure AD authentication for Azure SQL
- Create dedicated read-only SQL users
- Store credentials in secure vaults (Azure Key Vault, AWS Secrets Manager, etc.)

**DON'T:**
- Commit `.env` files with real credentials
- Hardcode credentials in configuration files
- Share credentials in issues or pull requests
- Use admin/sa accounts for the MCP server
- Store credentials in version control

**Example - Read-only SQL User:**
```sql
-- Create dedicated read-only user
CREATE LOGIN mcp_readonly WITH PASSWORD = 'SecurePassword123!';
USE MyDatabase;
CREATE USER mcp_readonly FOR LOGIN mcp_readonly;

-- Grant read-only permissions
ALTER ROLE db_datareader ADD MEMBER mcp_readonly;

-- Deny write permissions (defense in depth)
DENY INSERT, UPDATE, DELETE, ALTER, DROP TO mcp_readonly;
```

#### 2. Network Security

**Recommended:**
- Use SSL/TLS for SQL Server connections
- Restrict SQL Server to trusted networks
- Use firewall rules to limit access
- Enable SQL Server encryption

**Connection String with Encryption:**
```env
SQL_CONNECTION_STRING=Driver={ODBC Driver 17 for SQL Server};Server=localhost;Database=MyDB;UID=user;PWD=pass;Encrypt=yes;TrustServerCertificate=no
```

#### 3. Access Control

**Table Blacklist:**
```env
# Block sensitive tables
BLACKLIST_TABLES=passwords,api_keys,credit_cards,ssn_data

# Block patterns
BLACKLIST_TABLES=*_secret,*_private,internal_*,sys_*

# Block schemas
BLACKLIST_TABLES=security.*,admin.*
```

**Schema Whitelist:**
```env
# Only allow specific schemas
ALLOWED_SCHEMAS=public,reports,analytics

# Empty = all schemas (less secure)
ALLOWED_SCHEMAS=
```

#### 4. Query Limits

Set appropriate limits to prevent abuse:

```env
# Limit result size
MAX_ROWS=100

# Set query timeout
QUERY_TIMEOUT=30

# Connection pool
POOL_SIZE=5
POOL_TIMEOUT=30
```

#### 5. Logging and Monitoring

Enable logging to detect suspicious activity:

```env
LOG_LEVEL=INFO
```

Monitor logs for:
- Failed authentication attempts
- Blocked queries
- Timeout errors
- Access denied messages
- Unusual query patterns

**View logs:**
- Claude Desktop: Help → Show Logs
- Claude Code: Check terminal output
- Manual: Check application logs

#### 6. Regular Updates

- Keep SQL Server updated with security patches
- Update ODBC drivers regularly
- Update Python and dependencies
- Monitor for MCP SQL Server updates

### For Developers

#### 1. Code Security

**SQL Injection Prevention:**
```python
# SECURE: Use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# VULNERABLE: String concatenation
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")  # DON'T!
```

**Input Validation:**
```python
# Validate all user input
if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
    raise ValueError("Invalid table name")

# Validate query structure
if not query.upper().strip().startswith("SELECT"):
    raise ValueError("Only SELECT queries allowed")
```

**Dangerous Pattern Detection:**
```python
DANGEROUS_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "EXEC", "EXECUTE", "xp_cmdshell", "sp_executesql"
]

for keyword in DANGEROUS_KEYWORDS:
    if re.search(r'\b' + re.escape(keyword) + r'\b', query, re.IGNORECASE):
        raise ValueError(f"Keyword '{keyword}' not allowed")
```

#### 2. Error Handling

**Don't leak sensitive information:**
```python
# GOOD: Generic error message
except pyodbc.Error as e:
    logger.error(f"Database error: {e}")
    return [TextContent(type="text", text="Database error occurred")]

# BAD: Exposes connection details
except pyodbc.Error as e:
    return [TextContent(type="text", text=f"Error: {e}")]  # DON'T!
```

#### 3. Dependency Security

Check for vulnerabilities:
```bash
# Install safety
pip install safety

# Check dependencies
safety check

# Update dependencies
pip install --upgrade mcp pyodbc python-dotenv
```

#### 4. Code Review Checklist

- [ ] No hardcoded credentials
- [ ] All SQL queries use parameterized statements
- [ ] Input validation for all user inputs
- [ ] Appropriate error messages (no sensitive data leak)
- [ ] Logging doesn't include credentials
- [ ] Connection strings are sanitized in logs
- [ ] Timeout and limits are enforced
- [ ] Tests cover security scenarios

### Common Vulnerabilities and Mitigations

#### 1. SQL Injection

**Vulnerability:**
```python
# VULNERABLE CODE
query = f"SELECT * FROM {table_name} WHERE id = {user_id}"
cursor.execute(query)
```

**Mitigation:**
```python
# SECURE CODE
# Validate identifier
if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
    raise ValueError("Invalid table name")

# Use parameterized query
query = f"SELECT * FROM {table_name} WHERE id = ?"
cursor.execute(query, (user_id,))
```

#### 2. Credential Exposure

**Vulnerability:**
- Credentials in git history
- Credentials in error messages
- Credentials in logs

**Mitigation:**
```python
# Sanitize connection string in logs
def sanitize_connection_string(conn_str: str) -> str:
    """Remove password from connection string for logging."""
    return re.sub(r'PWD=([^;]+)', 'PWD=****', conn_str, flags=re.IGNORECASE)

logger.info(f"Connecting to: {sanitize_connection_string(conn_str)}")
```

#### 3. Denial of Service

**Vulnerability:**
- Unbounded query results
- Long-running queries
- Connection exhaustion

**Mitigation:**
```python
# Enforce limits
MAX_ROWS = 100
QUERY_TIMEOUT = 30

# Add TOP clause
if "TOP" not in query.upper():
    query = query.replace("SELECT", f"SELECT TOP {MAX_ROWS}", 1)

# Set timeout
cursor.execute(query, timeout=QUERY_TIMEOUT)

# Connection pooling
pool = ConnectionPool(conn_str, pool_size=5, timeout=30)
```

#### 4. Information Disclosure

**Vulnerability:**
- Exposing table names
- Exposing schema details
- Verbose error messages

**Mitigation:**
```python
# Blacklist sensitive tables
BLACKLIST_TABLES = ["passwords", "api_keys", "credit_cards"]

# Filter results
if table_name in BLACKLIST_TABLES:
    return [TextContent(type="text", text="Access denied")]

# Generic error messages
except Exception as e:
    logger.exception("Error occurred")  # Detailed log
    return [TextContent(type="text", text="An error occurred")]  # Generic message
```

### Security Testing

Test security features:

```python
def test_sql_injection_prevention():
    """Test that SQL injection attempts are blocked."""
    malicious_queries = [
        "SELECT * FROM users; DROP TABLE users;--",
        "SELECT * FROM users WHERE id = 1 OR 1=1",
        "SELECT * FROM users UNION SELECT * FROM passwords",
    ]

    for query in malicious_queries:
        is_valid, error = SecurityValidator.validate_query(query)
        assert is_valid is False

def test_dangerous_keywords_blocked():
    """Test that dangerous keywords are blocked."""
    dangerous_queries = [
        "DROP TABLE users",
        "DELETE FROM users",
        "EXEC sp_executesql @query",
        "xp_cmdshell 'dir'",
    ]

    for query in dangerous_queries:
        is_valid, error = SecurityValidator.validate_query(query)
        assert is_valid is False

def test_table_blacklist():
    """Test that blacklisted tables are blocked."""
    blacklisted_tables = ["passwords", "sys_internal", "audit_trail"]

    for table in blacklisted_tables:
        is_allowed, error = SecurityValidator.is_table_allowed(table)
        assert is_allowed is False
```

### Incident Response

If you discover a security issue in production:

1. **Isolate**: Disable the MCP server immediately
2. **Investigate**: Check logs for suspicious activity
3. **Document**: Record all findings
4. **Remediate**: Apply fixes and update configurations
5. **Monitor**: Watch for continued suspicious activity
6. **Report**: Notify maintainers if it's a code vulnerability

### Compliance Considerations

Depending on your data and regulations, you may need to:

- **GDPR**: Implement data access controls, logging, and audit trails
- **HIPAA**: Ensure PHI is encrypted and access is restricted
- **PCI DSS**: Protect cardholder data with encryption and access controls
- **SOC 2**: Implement security controls and monitoring

Consult with your compliance team before deploying in regulated environments.

### Security Resources

- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [Microsoft SQL Server Security Best Practices](https://learn.microsoft.com/en-us/sql/relational-databases/security/security-best-practices)
- [Python Security Best Practices](https://python.readthedocs.io/en/latest/library/security_warnings.html)
- [CWE Top 25 Most Dangerous Software Weaknesses](https://cwe.mitre.org/top25/)

### Contact

For security concerns, contact the maintainer privately through GitHub.

---

**Remember: Security is a shared responsibility. Always follow the principle of least privilege and defense in depth.**
