# Activate the Poetry venv
& ((poetry env info --path) + "\Scripts\activate.ps1")

$Env:CLCACHE_DIR = "\clcache"

python "scripts\dist-inner.py"
