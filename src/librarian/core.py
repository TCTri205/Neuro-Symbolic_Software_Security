import hashlib
import json
from typing import Dict, Any, Optional, List
from .db import LibrarianDB
from .version import VersionMatcher

class Librarian:
    def __init__(self, db_path: str = "nsss_librarian.db"):
        self.db = LibrarianDB(db_path)

    def get_profiles(self, library_name: str, current_version: str) -> List[Dict[str, Any]]:
        """
        Retrieves profiles for a library matching the current version.
        """
        if not VersionMatcher.is_valid(current_version):
            return []

        all_profiles = self.db.get_library_profiles(library_name)
        matched = []
        
        for p in all_profiles:
            spec = p["version_spec"]
            # Treat empty spec as match all ("*")
            if not spec or spec == "*":
                matched.append(p)
                continue
            
            if VersionMatcher.match(current_version, spec):
                matched.append(p)
                
        return matched

    def add_profile(self, library_name: str, version_spec: str, 
                    profile_type: str, identifier: str, metadata: Dict[str, Any] = None):
        """
        Adds a profile entry.
        """
        meta_str = json.dumps(metadata or {})
        self.db.add_library_profile(library_name, version_spec, profile_type, identifier, meta_str)

    def compute_hash(self, prompt_messages: List[Dict[str, str]]) -> str:
        """
        Computes a stable SHA256 hash from the prompt messages.
        """
        # We only care about the content of the messages for the hash
        content_str = ""
        for msg in prompt_messages:
            content_str += f"{msg.get('role')}:{msg.get('content')}\n"
        
        return hashlib.sha256(content_str.encode("utf-8")).hexdigest()

    def query(self, prompt_messages: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """
        Checks if a decision for the given prompt already exists.
        """
        context_hash = self.compute_hash(prompt_messages)
        record = self.db.get_decision(context_hash)
        
        if record:
            # Reconstruct the insight object structure
            # We stored 'raw_response' which is the content string
            # We try to parse it again or return it as is?
            # The orchestrator expects an 'insight' dict.
            
            response_content = record["raw_response"]
            
            # We try to parse the analysis again to return a structured object
            # similar to what orchestrator does.
            analysis_data = []
            try:
                # Basic cleanup same as orchestrator (we could verify this logic is shared)
                clean_content = response_content.strip()
                if clean_content.startswith("```json"):
                    clean_content = clean_content[7:]
                elif clean_content.startswith("```"):
                    clean_content = clean_content[3:]
                if clean_content.endswith("```"):
                    clean_content = clean_content[:-3]
                clean_content = clean_content.strip()
                
                parsed = json.loads(clean_content)
                if isinstance(parsed, dict) and "analysis" in parsed:
                    analysis_data = parsed["analysis"]
            except Exception:
                pass

            return {
                "provider": "librarian",  # Indicate source is cache
                "model": record["model"],
                "response": response_content,
                "analysis": analysis_data,
                "cached": True
            }
        
        return None

    def store(self, prompt_messages: List[Dict[str, str]], 
              response_content: str, 
              analysis_data: List[Dict[str, Any]], 
              model: str):
        """
        Stores the decision in the library.
        """
        context_hash = self.compute_hash(prompt_messages)
        self.db.store_decision(context_hash, analysis_data, response_content, model)
