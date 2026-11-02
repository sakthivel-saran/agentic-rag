from pathlib import Path

# current working directory
root = Path(".")

#folders to create

folders = [
    "app/api",
    "app/core",
    "app/rag",
    "app/services",
    "data",
    "templates",
    "static",
    "uploads",
    "tests",
]

#files to create
files = [
    "app/main.py",
    "ingest_sample_kb.py",
    "run.py",
    ".env",
]

#create folders
for folder in folders:
    folder_path = root / folder
    folder_path.mkdir(parents=True, exist_ok=True)
    print(f"Created folder: {folder_path}")

#create files
for file in files:
    file_path = root / file
    file_path.touch(exist_ok=True)
    print(f"Created file: {file_path}")