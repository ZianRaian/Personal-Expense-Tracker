# conftest.py — project root
# Placing this file at the project root causes pytest to add the root directory
# to sys.path automatically, so `import app` and `import database.db` resolve
# correctly from any test file inside tests/.
