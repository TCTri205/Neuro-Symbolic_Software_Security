import yaml
import os
import sys

# Ensure we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.librarian.db import LibrarianDB

def parse_name_from_id(rule_id: str) -> str:
    # nsss.python.owasp.a01.sql-injection -> Sql Injection
    parts = rule_id.split('.')
    if len(parts) > 0:
        raw_name = parts[-1]
        return raw_name.replace('-', ' ').title()
    return rule_id

def populate_from_yaml(yaml_path: str, db_path: str = "nsss_librarian.db"):
    print(f"Loading rules from {yaml_path}...")
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: File {yaml_path} not found.")
        return

    if not data or 'rules' not in data:
        print("No rules found in YAML.")
        return

    db = LibrarianDB(db_path)
    print(f"Connected to DB at {db_path}")

    count = 0
    for rule in data['rules']:
        rule_id = rule.get('id')
        message = rule.get('message', '').strip()
        metadata = rule.get('metadata', {})
        
        owasp = metadata.get('owasp', 'Unknown')
        cwe = metadata.get('cwe', 'Unknown')
        
        name = parse_name_from_id(rule_id)
        
        print(f"Adding vulnerability type: {name} ({rule_id})")
        db.add_vulnerability_type(
            id=rule_id,
            name=name,
            description=message,
            owasp_category=owasp,
            cwe_id=cwe
        )
        
        # Add a default remediation strategy derived from the message
        # We can refine this later or parse the message more intelligently
        db.add_remediation_strategy(
            vulnerability_type_id=rule_id,
            strategy_name="Standard Mitigation",
            description=message, # Using the full message as context for now
            code_template="" # Template inference is a future task
        )
        count += 1

    print(f"Successfully populated {count} vulnerability types.")

if __name__ == "__main__":
    # Default paths
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    yaml_file = os.path.join(project_root, "rules", "nsss-python-owasp.yml")
    
    populate_from_yaml(yaml_file)
