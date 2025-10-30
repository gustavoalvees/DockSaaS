# DockSaaS 🐳

DockSaaS é um sistema SaaS que permite criar e gerenciar containers Docker de forma automatizada via API REST, usando **FastAPI**, **SQLite**, e **Docker SDK for Python**.

##  Funcionalidades
- Criação automática de containers com limites personalizados (CPU, memória, armazenamento)
- Gerenciamento de volumes persistentes
- Registro de uso e controle de containers por usuário
- API REST fácil de integrar
- Log de ações e banco de dados SQLite para persistência

##  Tecnologias Utilizadas
- Python 3
- FastAPI
- Docker SDK for Python
- SQLite3
- Uvicorn

##  Instalação
```bash
git clone https://github.com/gustavoalvees/docksaas.git
cd docksaas
pip install -r requirements.txt
uvicorn main:app --reload
