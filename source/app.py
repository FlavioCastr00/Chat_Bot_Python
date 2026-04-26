from flask import Flask, request, jsonify, render_template
import sqlite3
import os

app = Flask(__name__)
DB = "clientes.db"

# ── Banco de dados ──────────────────────────────────────────────────────────

def conectar():
    return sqlite3.connect(DB)

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
    # Dados de exemplo se o banco estiver vazio
    c.execute("SELECT COUNT(*) FROM clientes")
    if c.fetchone()[0] == 0:
        exemplos = [
            ("111.222.333-44", "Ana Souza",      "4111 **** **** 1111", 5000,  3200,  1800, "03/2028", "15/05/2026", "ativo"),
            ("222.333.444-55", "Carlos Lima",    "5500 **** **** 2222", 8000,  6500,  1500, "07/2027", "20/05/2026", "ativo"),
            ("333.444.555-66", "Beatriz Oliveira","4916 **** **** 3333", 3000,  3000,  0,    "11/2026", "10/05/2026", "bloqueado"),
            ("444.555.666-77", "Diego Mendes",   "4532 **** **** 4444", 12000, 9100,  2900, "06/2029", "05/05/2026", "ativo"),
        ]
        c.executemany("""
            INSERT INTO clientes (cpf,nome,numero_cartao,limite_total,limite_disponivel,
                                  fatura_atual,vencimento_cartao,vencimento_fatura,status_cartao)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, exemplos)
        transacoes = [
            ("111.222.333-44", "Supermercado Pão de Açúcar", 320.50, "20/04/2026"),
            ("111.222.333-44", "Netflix",                    55.90,  "18/04/2026"),
            ("111.222.333-44", "Posto Shell",                180.00, "15/04/2026"),
            ("111.222.333-44", "iFood",                      89.70,  "12/04/2026"),
            ("111.222.333-44", "Amazon",                     1154.30,"10/04/2026"),
            ("222.333.444-55", "Riachuelo",                  450.00, "22/04/2026"),
            ("222.333.444-55", "Uber",                       87.30,  "19/04/2026"),
            ("222.333.444-55", "Mercado Livre",              962.70, "14/04/2026"),
            ("444.555.666-77", "Apple Store",                1299.00,"21/04/2026"),
            ("444.555.666-77", "Decathlon",                  890.50, "16/04/2026"),
            ("444.555.666-77", "Streaming Pack",             710.50, "11/04/2026"),
        ]
        c.executemany("""
            INSERT INTO transacoes (cpf_cliente, descricao, valor, data)
            VALUES (?,?,?,?)
        """, transacoes)
    conn.commit()
    conn.close()

# ── Rotas ───────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/clientes", methods=["GET"])
def listar_clientes():
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT cpf, nome, numero_cartao, limite_total, limite_disponivel, fatura_atual, vencimento_cartao, vencimento_fatura, status_cartao FROM clientes")
    rows = c.fetchall()
    conn.close()
    campos = ["cpf","nome","numero_cartao","limite_total","limite_disponivel","fatura_atual","vencimento_cartao","vencimento_fatura","status_cartao"]
    return jsonify([dict(zip(campos, r)) for r in rows])


@app.route("/cliente/<cpf>", methods=["GET"])
def consultar_cliente(cpf):
    conn = conectar()
    c = conn.cursor()
    # Busca por CPF ou por nome (parcial)
    cpf_limpo = cpf.replace('.','').replace('-','').replace(' ','')
    c.execute("""
        SELECT cpf, nome, numero_cartao, limite_total, limite_disponivel,
               fatura_atual, vencimento_cartao, vencimento_fatura, status_cartao
        FROM clientes
        WHERE REPLACE(REPLACE(cpf,'.',''),'-','') = ?
           OR LOWER(nome) LIKE LOWER(?)
    """, (cpf_limpo, f"%{cpf}%"))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"erro": "Cliente não encontrado"}), 404
    campos = ["cpf","nome","numero_cartao","limite_total","limite_disponivel","fatura_atual","vencimento_cartao","vencimento_fatura","status_cartao"]
    cliente = dict(zip(campos, row))
    # Busca transações
    c.execute("SELECT descricao, valor, data FROM transacoes WHERE cpf_cliente = ? ORDER BY id DESC LIMIT 10", (cliente["cpf"],))
    cliente["transacoes"] = [{"descricao": t[0], "valor": t[1], "data": t[2]} for t in c.fetchall()]
    conn.close()
    return jsonify(cliente)


@app.route("/add", methods=["POST"])
def adicionar_cliente():
    data = request.get_json()
    try:
        conn = conectar()
        c = conn.cursor()
        limite = float(data["limite_total"])
        c.execute("""
            INSERT INTO clientes (cpf, nome, numero_cartao, limite_total, limite_disponivel,
                                  fatura_atual, vencimento_cartao, vencimento_fatura, status_cartao)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'ativo')
        """, (
            data["cpf"], data["nome"], data.get("numero_cartao", "0000 **** **** 0000"),
            limite, limite,
            data.get("vencimento_cartao", "12/2030"),
            data.get("vencimento_fatura", "10/05/2026")
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "mensagem": f"Cliente {data['nome']} cadastrado com sucesso!"})
    except sqlite3.IntegrityError:
        return jsonify({"erro": "CPF já cadastrado"}), 400
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/bloquear", methods=["POST"])
def bloquear_cartao():
    data = request.get_json()
    busca = data.get("cpf", "")
    conn = conectar()
    c = conn.cursor()
    busca_limpa = busca.replace('.','').replace('-','').replace(' ','')
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
    return jsonify({"status": "ok", "mensagem": "Cartão bloqueado com sucesso"})


@app.route("/desbloquear", methods=["POST"])
def desbloquear_cartao():
    data = request.get_json()
    busca = data.get("cpf", "")
    conn = conectar()
    c = conn.cursor()
    busca_limpa = busca.replace('.','').replace('-','').replace(' ','')
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
    return jsonify({"status": "ok", "mensagem": "Cartão desbloqueado com sucesso"})


@app.route("/compra", methods=["POST"])
def realizar_compra():
    data = request.get_json()
    busca = data.get("cpf", "")
    descricao = data.get("descricao", "Compra")
    valor = float(data.get("valor", 0))
    from datetime import date
    hoje = date.today().strftime("%d/%m/%Y")
    conn = conectar()
    c = conn.cursor()
    busca_limpa = busca.replace('.','').replace('-','').replace(' ','')
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
    # Retorna dados atualizados
    c.execute("SELECT limite_disponivel, fatura_atual FROM clientes WHERE cpf = ?", (cpf_real,))
    lim_disp, fatura = c.fetchone()
    conn.close()
    return jsonify({
        "status": "ok",
        "mensagem": "Compra aprovada",
        "cliente": nome,
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
    inicializar_db()
    app.run(debug=True)
