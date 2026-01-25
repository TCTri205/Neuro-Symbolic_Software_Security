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
                raw_response TEXT
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

    def store_decision(self, context_hash: str, analysis: Dict[str, Any], raw_response: str, model: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Extract fields from the first analysis item if available (assuming one main finding per prompt for now, 
        # or we might need to adjust if we query multiple findings at once. 
        # The prompt in orchestrator sends multiple findings. 
        # But usually we cache the whole prompt/response interaction.)
        
        # Actually, looking at the orchestrator, we send a prompt with potentially multiple findings.
        # The LLM returns an array of analysis items.
        # Ideally, we should cache the request -> response mapping. 
        # But the requirements say "Known False Positives... Verified True Positives".
        # If we cache the whole response based on the input hash, that covers it.
        # However, to be searchable by check_id, we might want to store individual items?
        # For simple caching to avoid re-asking: Hash(Prompt) -> Response is sufficient.
        # But to be a "Knowledge Base", we might want more granularity.
        
        # For this iteration, let's store the raw response mapped to the input hash,
        # AND extract the first finding's details for metadata if possible.
        
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
            INSERT OR REPLACE INTO decisions (hash, check_id, verdict, rationale, remediation, timestamp, model, raw_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (context_hash, check_id, verdict, rationale, remediation, timestamp, model, raw_response))
        
        conn.commit()
        conn.close()
