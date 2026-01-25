# Neuro-Symbolic Security Scan Report

## File: `benchmarks/vulnerable_flask_app/app.py`

### 1. rules.nsss.python.owasp.a02.hardcoded-secret 🔴
**Verdict**: True Positive
**Scope**: `app.py` (Block 1)

**Rationale**:
The API_KEY variable contains a hardcoded secret, which poses a security risk as it can be easily exposed in version control or logs.

**Vulnerable Code**:
```python
app = Flask(__name__)

# A02: Hardcoded Secret
API_KEY = "sk_live_12345_THIS_IS_A_SECRET_KEY"
```

**Remediation**:
```python
import os
API_KEY = os.getenv('API_KEY')
```

---

### 2. rules.nsss.python.owasp.a02.weak-crypto 🔴
**Verdict**: True Positive
**Scope**: `login` (Block 6)

**Rationale**:
MD5 is a weak hashing algorithm that is vulnerable to collision attacks. It should not be used for hashing passwords.

**Vulnerable Code**:
```python
    username = request.form['username']
    password = request.form['password']
    
    # A02: Weak Crypto (MD5)
    hashed_password = hashlib.md5(password.encode()).hexdigest()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # A01: SQL Injection
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{hashed_password}'"
    print(f"Executing: {query}")
    cursor.execute(query)
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
```

**Remediation**:
```python
hashed_password = hashlib.sha256(password.encode()).hexdigest()
```

---

### 3. rules.nsss.python.owasp.a01.sql-injection 🔴
**Verdict**: True Positive
**Scope**: `login` (Block 6)

**Rationale**:
The use of string interpolation in the SQL query construction makes it susceptible to SQL injection attacks. Parameterized queries should be used instead.

**Vulnerable Code**:
```python
    username = request.form['username']
    password = request.form['password']
    
    # A02: Weak Crypto (MD5)
    hashed_password = hashlib.md5(password.encode()).hexdigest()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # A01: SQL Injection
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{hashed_password}'"
    print(f"Executing: {query}")
    cursor.execute(query)
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
```

**Remediation**:
```python
cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, hashed_password))
```

---

### 4. rules.nsss.python.owasp.a01.command-injection 🔴
**Verdict**: True Positive
**Scope**: `ping` (Block 11)

**Rationale**:
The use of 'shell=True' with untrusted input (target) allows for command injection, which can lead to arbitrary command execution.

**Vulnerable Code**:
```python
    target = request.args.get('target', 'localhost')
    
    # A01: Command Injection
    # User can pass "localhost; rm -rf /"
    command = f"ping -c 1 {target}"
    output = subprocess.check_output(command, shell=True)
    
    return output
```

**Remediation**:
```python
output = subprocess.check_output(['ping', '-c', '1', target])
```

---
