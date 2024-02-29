# Activate the Poetry venv
& ((poetry env info --path) + "\Scripts\activate.ps1")

python "scripts\dist-inner.py"
