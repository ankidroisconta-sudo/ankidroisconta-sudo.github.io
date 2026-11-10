#!/bin/bash
cd "$(dirname "$0")"
python3 coletor.py
read -r -p "Pressione Enter para fechar."
