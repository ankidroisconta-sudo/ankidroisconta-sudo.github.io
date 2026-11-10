#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "O Python 3 não está instalado. Abrindo a página de download…"
  echo "Instale e depois dê duplo clique neste arquivo de novo."
  open "https://www.python.org/downloads/"
  read -r -p "Pressione Enter para fechar."
  exit 1
fi
python3 coletor.py
read -r -p "Pressione Enter para fechar."
