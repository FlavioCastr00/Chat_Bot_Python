from flask import Flask, request, jsonify, render_template
import sqlite3
import os
from datetime import date

from ml_model import carregar_classificador

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "clientes.db")
TRAINING_FILE = os.path.join(BASE_DIR, "training_data.json")

# O classificador é treinado uma vez quando o Flask inicia.
# Ele usa CountVectorizer + LogisticRegression, definidos em ml_model.py.
classificador = carregar_classificador(TRAINING_FILE)


# ── Banco de dados ──────────────────────────────────────────────────────────

def conectar():
    return sqlite3.connect(DB)


def limpar_cpf(cpf):
    """
    Remove pontos, traços e espaços do CPF para facilitar buscas.
    """
    return (cpf or "").replace('.', '').replace('-', '').replace(' ', '')


def campos_cliente():
    return [
        "cpf", "nome", "numero_cartao", "limite_total", "limite_disponivel",
        "fatura_atual", "vencimento_cartao", "vencimento_fatura", "status_cartao"
    ]


def cliente_para_dict(row):
    if not row:
        return None
    return dict(zip(campos_cliente(), row))


def registrar_mensagem(user_message, bot_response, intent=None, confidence=None, cpf=None):
    """
    Salva o histórico de mensagens no SQLite.

    Essa tabela permite mostrar que o chatbot guarda as conversas, além dos dados
    de conta/cartão/fatura.
    """
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf_cliente TEXT,
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            intent TEXT,
            confidence REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        INSERT INTO messages (cpf_cliente, user_message, bot_response, intent, confidence)
        VALUES (?, ?, ?, ?, ?)
    """, (cpf, user_message, bot_response, intent, confidence))
    conn.commit()
    conn.close()


def buscar_cliente_por_cpf_ou_nome(busca):
    """
    Busca cliente por CPF limpo ou por trecho do nome.
    """
    conn = conectar()
    c = conn.cursor()
    busca_limpa = limpar_cpf(busca)
    c.execute("""
        SELECT cpf, nome, numero_cartao, limite_total, limite_disponivel,
               fatura_atual, vencimento_cartao, vencimento_fatura, status_cartao
        FROM clientes
        WHERE REPLACE(REPLACE(cpf,'.',''),'-','') = ?
           OR LOWER(nome) LIKE LOWER(?)
    """, (busca_limpa, f"%{busca}%"))
    row = c.fetchone()
    conn.close()
    return cliente_para_dict(row)


def gerar_numero_cartao_mascarado(cpf):
    """
    Gera um número de cartão fictício e mascarado para o projeto.
    """
    digitos = ''.join(ch for ch in cpf if ch.isdigit())
    finais = (digitos[-4:] if len(digitos) >= 4 else "0000")
    return f"4532 **** **** {finais}"


def inicializar_db():
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            numero_cartao TEXT,
            limite_total REAL DEFAULT 0,
            limite_disponivel REAL DEFAULT 0,
            fatura_atual REAL DEFAULT 0,
            vencimento_cartao TEXT,
            vencimento_fatura TEXT,
            status_cartao TEXT DEFAULT 'ativo'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf_cliente TEXT NOT NULL,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL,
            data TEXT NOT NULL,
            FOREIGN KEY (cpf_cliente) REFERENCES clientes(cpf)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf_cliente TEXT,
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            intent TEXT,
            confidence REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Dados de exemplo se o banco estiver vazio.
    c.execute("SELECT COUNT(*) FROM clientes")
    if c.fetchone()[0] == 0:
        exemplos = [
            ("111.222.333-44", "Ana Souza", "4111 **** **** 1111", 5000, 3200, 1800, "03/2028", "15/05/2026", "ativo"),
            ("222.333.444-55", "Carlos Lima", "5500 **** **** 2222", 8000, 6500, 1500, "07/2027", "20/05/2026", "ativo"),
            ("333.444.555-66", "Beatriz Oliveira", "4916 **** **** 3333", 3000, 3000, 0, "11/2026", "10/05/2026", "bloqueado"),
            ("444.555.666-77", "Diego Mendes", "4532 **** **** 4444", 12000, 9100, 2900, "06/2029", "05/05/2026", "ativo"),
        ]
        c.executemany("""
            INSERT INTO clientes (cpf,nome,numero_cartao,limite_total,limite_disponivel,
                                  fatura_atual,vencimento_cartao,vencimento_fatura,status_cartao)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, exemplos)

        transacoes = [
            ("111.222.333-44", "Supermercado Pão de Açúcar", 320.50, "20/04/2026"),
            ("111.222.333-44", "Netflix", 55.90, "18/04/2026"),
            ("111.222.333-44", "Posto Shell", 180.00, "15/04/2026"),
            ("111.222.333-44", "iFood", 89.70, "12/04/2026"),
            ("111.222.333-44", "Amazon", 1154.30, "10/04/2026"),
            ("222.333.444-55", "Riachuelo", 450.00, "22/04/2026"),
            ("222.333.444-55", "Uber", 87.30, "19/04/2026"),
            ("222.333.444-55", "Mercado Livre", 962.70, "14/04/2026"),
            ("444.555.666-77", "Apple Store", 1299.00, "21/04/2026"),
            ("444.555.666-77", "Decathlon", 890.50, "16/04/2026"),
            ("444.555.666-77", "Streaming Pack", 710.50, "11/04/2026"),
        ]
        c.executemany("""
            INSERT INTO transacoes (cpf_cliente, descricao, valor, data)
            VALUES (?,?,?,?)
        """, transacoes)

    conn.commit()
    conn.close()


# Inicializa o banco mesmo quando o Flask é iniciado pelo VSCode ou flask run.
inicializar_db()


# ── Rotas principais ────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat_ml():
    """
    Endpoint principal de Machine Learning.

    O front-end envia uma frase para cá.
    O modelo prevê a intenção usando CountVectorizer + LogisticRegression.

    Exemplo de entrada:
    {
        "message": "quero ver minha fatura",
        "cpf": "111.222.333-44"
    }

    Exemplo de saída:
    {
        "intent": "minha_fatura",
        "confidence": 0.88,
        "response": "Vou consultar sua fatura e os últimos lançamentos."
    }
    """
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    cpf = data.get("cpf")

    resultado = classificador.predict(message)

    registrar_mensagem(
        user_message=message,
        bot_response=resultado["response"],
        intent=resultado["intent"],
        confidence=resultado["confidence"],
        cpf=cpf,
    )

    return jsonify(resultado)


@app.route("/ml-info", methods=["GET"])
def ml_info():
    """
    Rota didática para conferir quais intenções o modelo conhece.
    """
    return jsonify({
        "modelo": "CountVectorizer + LogisticRegression",
        "arquivo_treino": "training_data.json",
        "intenções": [intent["tag"] for intent in classificador.intents],
        "limite_confianca": classificador.confidence_threshold,
    })


@app.route("/clientes", methods=["GET"])
def listar_clientes():
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT cpf, nome, numero_cartao, limite_total, limite_disponivel, fatura_atual, vencimento_cartao, vencimento_fatura, status_cartao FROM clientes")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(zip(campos_cliente(), r)) for r in rows])


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    cpf = data.get("cpf", "")

    conn = conectar()
    c = conn.cursor()

    cpf_limpo = limpar_cpf(cpf)

    c.execute("""
        SELECT cpf, nome, numero_cartao, limite_total,
               limite_disponivel, fatura_atual,
               vencimento_cartao, vencimento_fatura,
               status_cartao
        FROM clientes
        WHERE REPLACE(REPLACE(cpf,'.',''),'-','') = ?
    """, (cpf_limpo,))

    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"erro": "CPF não encontrado", "cadastrar": True}), 404

    return jsonify(cliente_para_dict(row))


@app.route("/minha-conta", methods=["POST"])
def consultar_cliente():
    data = request.get_json() or {}
    cpf = data.get("cpf", "")

    cliente = buscar_cliente_por_cpf_ou_nome(cpf)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado"}), 404

    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT descricao, valor, data FROM transacoes WHERE cpf_cliente = ? ORDER BY id DESC LIMIT 10", (cliente["cpf"],))
    cliente["transacoes"] = [{"descricao": t[0], "valor": t[1], "data": t[2]} for t in c.fetchall()]
    conn.close()

    return jsonify(cliente)


@app.route("/meu-cartao", methods=["POST"])
def meu_cartao():
    """
    Rota específica para dados do cartão.
    Foi adicionada para que a intenção 'cartao' não precise reaproveitar apenas /minha-conta.
    """
    data = request.get_json() or {}
    cpf = data.get("cpf", "")

    cliente = buscar_cliente_por_cpf_ou_nome(cpf)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado"}), 404

    return jsonify({
        "cpf": cliente["cpf"],
        "nome": cliente["nome"],
        "numero_cartao": cliente["numero_cartao"],
        "limite_total": cliente["limite_total"],
        "limite_disponivel": cliente["limite_disponivel"],
        "fatura_atual": cliente["fatura_atual"],
        "vencimento_cartao": cliente["vencimento_cartao"],
        "vencimento_fatura": cliente["vencimento_fatura"],
        "status_cartao": cliente["status_cartao"],
    })


@app.route("/minha-fatura", methods=["POST"])
def minha_fatura():
    data = request.get_json() or {}
    cpf = data.get("cpf", "")

    cliente = buscar_cliente_por_cpf_ou_nome(cpf)
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado"}), 404

    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT descricao, valor, data
        FROM transacoes
        WHERE cpf_cliente = ?
        ORDER BY id DESC
        LIMIT 10
    """, (cliente["cpf"],))

    cliente["transacoes"] = [
        {"descricao": t[0], "valor": t[1], "data": t[2]}
        for t in c.fetchall()
    ]

    conn.close()
    return jsonify(cliente)


# ── CADASTRAR ───────────────────────────────────────────────────────────────

@app.route("/cadastrar", methods=["POST"])
def adicionar_cliente():
    data = request.get_json() or {}
    try:
        conn = conectar()
        c = conn.cursor()

        limite = float(data.get("limite_total", 1000))
        cpf = data["cpf"]
        nome = data["nome"]
        numero_cartao = data.get("numero_cartao") or gerar_numero_cartao_mascarado(cpf)
        venc_cartao = data.get("vencimento_cartao", "12/2030")

        dia = int(data.get("dia_vencimento", 10))
        dia = min(max(dia, 1), 28)
        venc_fatura = data.get("vencimento_fatura", f"{dia:02d}/05/2026")

        c.execute("""
            INSERT INTO clientes (cpf, nome, numero_cartao, limite_total, limite_disponivel,
                                  fatura_atual, vencimento_cartao, vencimento_fatura, status_cartao)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'ativo')
        """, (cpf, nome, numero_cartao, limite, limite, venc_cartao, venc_fatura))
        conn.commit()

        c.execute("""
            SELECT cpf, nome, numero_cartao, limite_total, limite_disponivel,
                   fatura_atual, vencimento_cartao, vencimento_fatura, status_cartao
            FROM clientes
            WHERE cpf = ?
        """, (cpf,))
        row = c.fetchone()
        conn.close()

        cliente = cliente_para_dict(row)
        cliente["status"] = "ok"
        cliente["mensagem"] = f"Cliente {nome} cadastrado com sucesso!"

        registrar_mensagem("criar conta", cliente["mensagem"], "criar_conta", 1.0, cpf)
        return jsonify(cliente)

    except sqlite3.IntegrityError:
        return jsonify({"erro": "CPF já cadastrado"}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ── UPDATE de cliente ───────────────────────────────────────────────────────

@app.route("/atualizar-meus-dados", methods=["PUT"])
def atualizar_cliente():
    data = request.get_json() or {}
    busca = data.get("busca", "")

    if not busca:
        return jsonify({"erro": "Informe 'busca' com o CPF ou nome do cliente"}), 400

    conn = conectar()
    c = conn.cursor()

    busca_limpa = limpar_cpf(busca)
    c.execute("""
        SELECT cpf, nome, limite_total, limite_disponivel, fatura_atual
        FROM clientes
        WHERE REPLACE(REPLACE(cpf,'.',''),'-','') = ?
           OR LOWER(nome) LIKE LOWER(?)
    """, (busca_limpa, f"%{busca}%"))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"erro": "Cliente não encontrado"}), 404

    cpf_atual, nome_atual, limite_total_atual, limite_disp_atual, fatura_atual = row

    novo_cpf = data.get("cpf", cpf_atual)
    novo_nome = data.get("nome", nome_atual)
    novo_cartao = data.get("numero_cartao")
    novo_venc_cartao = data.get("vencimento_cartao")
    novo_venc_fatura = data.get("vencimento_fatura")
    novo_status = data.get("status_cartao")

    novo_limite_total = float(data["limite_total"]) if "limite_total" in data else limite_total_atual
    if "limite_total" in data:
        diferenca = novo_limite_total - limite_total_atual
        novo_limite_disp = max(0.0, limite_disp_atual + diferenca)
    else:
        novo_limite_disp = limite_disp_atual

    try:
        if novo_cpf != cpf_atual:
            c.execute(
                "UPDATE transacoes SET cpf_cliente = ? WHERE cpf_cliente = ?",
                (novo_cpf, cpf_atual)
            )
            c.execute(
                "UPDATE messages SET cpf_cliente = ? WHERE cpf_cliente = ?",
                (novo_cpf, cpf_atual)
            )

        campos_update = {
            "cpf": novo_cpf,
            "nome": novo_nome,
            "limite_total": novo_limite_total,
            "limite_disponivel": novo_limite_disp,
        }
        if novo_cartao is not None:
            campos_update["numero_cartao"] = novo_cartao
        if novo_venc_cartao is not None:
            campos_update["vencimento_cartao"] = novo_venc_cartao
        if novo_venc_fatura is not None:
            campos_update["vencimento_fatura"] = novo_venc_fatura
        if novo_status is not None:
            campos_update["status_cartao"] = novo_status

        set_clause = ", ".join(f"{k} = ?" for k in campos_update)
        valores = list(campos_update.values()) + [cpf_atual]

        c.execute(f"UPDATE clientes SET {set_clause} WHERE cpf = ?", valores)
        conn.commit()

        c.execute("""
            SELECT cpf, nome, numero_cartao, limite_total, limite_disponivel,
                   fatura_atual, vencimento_cartao, vencimento_fatura, status_cartao
            FROM clientes
            WHERE cpf = ?
        """, (novo_cpf,))
        cliente = cliente_para_dict(c.fetchone())
        conn.close()

        cliente["status"] = "ok"
        cliente["mensagem"] = f"Cliente '{novo_nome}' atualizado com sucesso!"
        cliente["cpf_antigo"] = cpf_atual if novo_cpf != cpf_atual else None
        cliente["cpf_novo"] = novo_cpf if novo_cpf != cpf_atual else None

        registrar_mensagem("atualizar dados", cliente["mensagem"], "atualizar_dados", 1.0, novo_cpf)
        return jsonify(cliente)

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"erro": "O novo CPF já pertence a outro cliente"}), 400
    except Exception as e:
        conn.close()
        return jsonify({"erro": str(e)}), 500


# ── DELETE de cliente ───────────────────────────────────────────────────────

@app.route("/encerrar-conta", methods=["DELETE"])
def deletar_cliente():
    data = request.get_json() or {}
    busca = data.get("cpf") or data.get("nome", "")

    if not busca:
        return jsonify({"erro": "Informe 'cpf' ou 'nome' do cliente a ser deletado"}), 400

    conn = conectar()
    c = conn.cursor()

    busca_limpa = limpar_cpf(busca)
    c.execute("""
        SELECT cpf, nome FROM clientes
        WHERE REPLACE(REPLACE(cpf,'.',''),'-','') = ?
           OR LOWER(nome) LIKE LOWER(?)
    """, (busca_limpa, f"%{busca}%"))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"erro": "Cliente não encontrado"}), 404

    cpf_real, nome_real = row

    c.execute("DELETE FROM transacoes WHERE cpf_cliente = ?", (cpf_real,))
    c.execute("DELETE FROM clientes WHERE cpf = ?", (cpf_real,))
    conn.commit()
    conn.close()

    mensagem = f"Cliente '{nome_real}' e todas as suas transações foram removidos com sucesso."
    registrar_mensagem("encerrar conta", mensagem, "encerrar_conta", 1.0, cpf_real)

    return jsonify({"status": "ok", "mensagem": mensagem})


# ── Cartão ──────────────────────────────────────────────────────────────────

@app.route("/bloquear-meu-cartao", methods=["POST"])
def bloquear_cartao():
    data = request.get_json() or {}
    busca = data.get("cpf", "")
    conn = conectar()
    c = conn.cursor()
    busca_limpa = limpar_cpf(busca)
    c.execute("""
        UPDATE clientes SET status_cartao = 'bloqueado'
        WHERE REPLACE(REPLACE(cpf,'.',''),'-','') = ?
           OR LOWER(nome) LIKE LOWER(?)
    """, (busca_limpa, f"%{busca}%"))
    if c.rowcount == 0:
        conn.close()
        return jsonify({"erro": "Cliente não encontrado"}), 404
    conn.commit()
    conn.close()

    mensagem = "Cartão bloqueado com sucesso"
    registrar_mensagem("bloquear cartão", mensagem, "bloquear_cartao", 1.0, busca)
    return jsonify({"status": "ok", "mensagem": mensagem})


@app.route("/desbloquear-meu-cartao", methods=["POST"])
def desbloquear_cartao():
    data = request.get_json() or {}
    busca = data.get("cpf", "")
    conn = conectar()
    c = conn.cursor()
    busca_limpa = limpar_cpf(busca)
    c.execute("""
        UPDATE clientes SET status_cartao = 'ativo'
        WHERE REPLACE(REPLACE(cpf,'.',''),'-','') = ?
           OR LOWER(nome) LIKE LOWER(?)
    """, (busca_limpa, f"%{busca}%"))
    if c.rowcount == 0:
        conn.close()
        return jsonify({"erro": "Cliente não encontrado"}), 404
    conn.commit()
    conn.close()

    mensagem = "Cartão desbloqueado com sucesso"
    registrar_mensagem("desbloquear cartão", mensagem, "desbloquear_cartao", 1.0, busca)
    return jsonify({"status": "ok", "mensagem": mensagem})


@app.route("/compra", methods=["POST"])
def realizar_compra():
    data = request.get_json() or {}
    busca = data.get("cpf", "")
    descricao = data.get("descricao", "Compra")
    valor = float(data.get("valor", 0))
    hoje = date.today().strftime("%d/%m/%Y")

    conn = conectar()
    c = conn.cursor()
    busca_limpa = limpar_cpf(busca)
    c.execute("""
        SELECT cpf, nome, limite_disponivel, status_cartao FROM clientes
        WHERE REPLACE(REPLACE(cpf,'.',''),'-','') = ?
           OR LOWER(nome) LIKE LOWER(?)
    """, (busca_limpa, f"%{busca}%"))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"erro": "Cliente não encontrado"}), 404

    cpf_real, nome, disponivel, status = row
    if status == "bloqueado":
        conn.close()
        return jsonify({"erro": f"Cartão de {nome} está bloqueado"}), 400

    if valor > disponivel:
        conn.close()
        return jsonify({"erro": f"Limite insuficiente. Disponível: R$ {disponivel:.2f}"}), 400

    c.execute("""
        UPDATE clientes
        SET limite_disponivel = limite_disponivel - ?,
            fatura_atual = fatura_atual + ?
        WHERE cpf = ?
    """, (valor, valor, cpf_real))
    c.execute("""
        INSERT INTO transacoes (cpf_cliente, descricao, valor, data)
        VALUES (?, ?, ?, ?)
    """, (cpf_real, descricao, valor, hoje))
    conn.commit()

    c.execute("SELECT limite_disponivel, fatura_atual FROM clientes WHERE cpf = ?", (cpf_real,))
    lim_disp, fatura = c.fetchone()
    conn.close()

    mensagem = "Compra aprovada"
    registrar_mensagem(f"compra: {descricao} - {valor}", mensagem, "fazer_compra", 1.0, cpf_real)

    return jsonify({
        "status": "ok",
        "mensagem": mensagem,
        "cliente": nome,
        "descricao": descricao,
        "valor": valor,
        "limite_disponivel": lim_disp,
        "fatura_atual": fatura
    })


@app.route("/relatorio", methods=["GET"])
def relatorio():
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM clientes")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clientes WHERE status_cartao = 'ativo'")
    ativos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM clientes WHERE status_cartao = 'bloqueado'")
    bloqueados = c.fetchone()[0]
    c.execute("SELECT SUM(fatura_atual), SUM(limite_total), SUM(limite_disponivel) FROM clientes")
    row = c.fetchone()
    total_faturas = row[0] or 0
    total_limite = row[1] or 0
    total_disponivel = row[2] or 0
    c.execute("SELECT COUNT(*) FROM transacoes")
    total_transacoes = c.fetchone()[0]
    conn.close()
    uso = round(((total_limite - total_disponivel) / total_limite * 100) if total_limite > 0 else 0, 1)
    return jsonify({
        "total_clientes": total,
        "ativos": ativos,
        "bloqueados": bloqueados,
        "total_faturas": round(total_faturas, 2),
        "total_limite": round(total_limite, 2),
        "total_disponivel": round(total_disponivel, 2),
        "uso_percentual": uso,
        "total_transacoes": total_transacoes
    })


if __name__ == "__main__":
    app.run(debug=True)
