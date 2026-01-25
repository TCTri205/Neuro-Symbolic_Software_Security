import sqlite3
import datetime
from typing import Optional, Dict, Any, List

class LibrarianDB:
    def __init__(self, db_path: str = "nsss_librarian.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for storing LLM decisions/insights
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                hash TEXT PRIMARY KEY,
                check_id TEXT,
                verdict TEXT,
                rationale TEXT,
                remediation TEXT,
                timestamp DATETIME,
                model TEXT,
                raw_response TEXT,
                snippet_hash TEXT  -- New: Allow lookup by code content independent of prompt
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_check_id ON decisions(check_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_snippet_hash ON decisions(snippet_hash)")

        # Table for Vulnerability Definitions (Knowledge Graph Node)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vulnerability_types (
                id TEXT PRIMARY KEY,  -- e.g., 'python.lang.security.audit.formatted-string'
                name TEXT,
                description TEXT,
                owasp_category TEXT,  -- e.g., 'A03:2021-Injection'
                cwe_id TEXT
            )
        """)

        # Table for Remediation Strategies (Knowledge Graph Node)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS remediation_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vulnerability_type_id TEXT,
                strategy_name TEXT,
                description TEXT,
                code_template TEXT,
                FOREIGN KEY(vulnerability_type_id) REFERENCES vulnerability_types(id)
            )
        """)
        
        # Table for learned patterns (placeholder for now as per requirements)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_type TEXT,
                pattern_data TEXT,
                description TEXT,
                created_at DATETIME
            )
        """)
        
        # Table for Library Profiles (Source/Sink/Sanitizer knowledge per version)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS library_profiles (
                library_name TEXT,
                version_spec TEXT,
                profile_type TEXT,  -- 'source', 'sink', 'sanitizer'
                identifier TEXT,    -- e.g., 'flask.request.args'
                metadata TEXT,      -- JSON blob for extra details
                PRIMARY KEY (library_name, version_spec, identifier)
            )
        """)
        
        conn.commit()
        conn.close()

    def get_library_profiles(self, library_name: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM library_profiles WHERE library_name = ?", 
            (library_name,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]

    def add_library_profile(self, library_name: str, version_spec: str, 
                            profile_type: str, identifier: str, metadata: str = "{}"):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO library_profiles 
            (library_name, version_spec, profile_type, identifier, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (library_name, version_spec, profile_type, identifier, metadata))
        
        conn.commit()
        conn.close()

    def add_vulnerability_type(self, id: str, name: str, description: str, owasp_category: str, cwe_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO vulnerability_types 
            (id, name, description, owasp_category, cwe_id)
            VALUES (?, ?, ?, ?, ?)
        """, (id, name, description, owasp_category, cwe_id))
        
        conn.commit()
        conn.close()

    def add_remediation_strategy(self, vulnerability_type_id: str, strategy_name: str, description: str, code_template: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO remediation_strategies 
            (vulnerability_type_id, strategy_name, description, code_template)
            VALUES (?, ?, ?, ?)
        """, (vulnerability_type_id, strategy_name, description, code_template))
        
        conn.commit()
        conn.close()

    def get_decision(self, context_hash: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM decisions WHERE hash = ?", (context_hash,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None

    def find_decision(self, check_id: str, snippet_hash: str) -> Optional[Dict[str, Any]]:
        """
        Finds a decision based on check_id and snippet hash, ignoring the full prompt context.
        This allows for fuzzy matching or re-use of insights even if prompt wording changes slightly.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Prioritize Verified True Positives? Or just any match?
        # For now, just find exact match on code+check
        cursor.execute("""
            SELECT * FROM decisions 
            WHERE check_id = ? AND snippet_hash = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (check_id, snippet_hash))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None

    def store_decision(self, context_hash: str, analysis: Dict[str, Any], raw_response: str, model: str, snippet_hash: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract fields from the first analysis item if available
        check_id = ""
        verdict = ""
        rationale = ""
        remediation = ""
        
        # Just grab the first one for metadata columns if exists
        if isinstance(analysis, list) and len(analysis) > 0:
            first = analysis[0]
            check_id = first.get("check_id", "")
            verdict = first.get("verdict", "")
            rationale = first.get("rationale", "")
            remediation = first.get("remediation", "")
            
        timestamp = datetime.datetime.now().isoformat()
        
        cursor.execute("""
            INSERT OR REPLACE INTO decisions (hash, check_id, verdict, rationale, remediation, timestamp, model, raw_response, snippet_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (context_hash, check_id, verdict, rationale, remediation, timestamp, model, raw_response, snippet_hash))
        
        conn.commit()
        conn.close()
