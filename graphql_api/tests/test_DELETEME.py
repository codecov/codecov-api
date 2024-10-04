import json
import psycopg2
from ruamel.yaml import YAML
import yaml as pyyaml  # PyYAML for the non-comment-preserving part
import io


def test_commented_yaml():
    # YAML string with comments
    yaml_content = """
    # Example YAML with comments
    name: Example
    description: This is a test
    items:
      - name: item1
        value: 10
      - name: item2
        value: 20
    """

    # Step 1: Convert YAML (with preserved comments) to Python object using ruamel.yaml
    yaml = YAML()
    yaml.preserve_quotes = True
    data_obj = yaml.load(yaml_content)
    print("YAML to Python Object (ruamel.yaml):", data_obj)

    # Step 2: Convert Python object to JSON (ruamel.yaml result)
    data_dict = dict(data_obj)  # Convert to regular Python dict
    json_data = json.dumps(data_dict)
    print("Python Object (with comments) to JSON:", json_data)

    # Step 3: Insert JSON data into PostgreSQL
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="",
        host="postgres"
    )
    cur = conn.cursor()

    # Create table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS data_store (
            id SERIAL PRIMARY KEY,
            data JSONB
        )
    """)
    conn.commit()

    # Insert JSON data
    cur.execute("INSERT INTO data_store (data) VALUES (%s) RETURNING id", [json_data])
    record_id = cur.fetchone()[0]
    conn.commit()
    print(f"Inserted record with ID {record_id}")

    # Step 4: Retrieve JSON data from PostgreSQL
    cur.execute("SELECT data FROM data_store WHERE id = %s", [record_id])
    retrieved_json = cur.fetchone()[0]  # This might already be a dictionary

    # If retrieved_json is not a string, you can skip json.loads()
    if isinstance(retrieved_json, str):
        retrieved_dict = json.loads(retrieved_json)
    else:
        retrieved_dict = retrieved_json  # It's already a Python dictionary

    print("Retrieved JSON from PostgreSQL:", retrieved_dict)

    # Optional: Convert back to YAML (with comments preserved) using ruamel.yaml
    yaml_output = io.StringIO()  # Create a StringIO stream
    yaml.dump(retrieved_dict, yaml_output)  # Dump to the stream
    yaml_string = yaml_output.getvalue()  # Get the YAML content as a string
    yaml_output.close()
    print("Converted back to YAML (with comments):")
    print(yaml_string)

    # Cleanup
    cur.close()
    conn.close()
