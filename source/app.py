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


@app.route("/minha-conta", methods=["GET"])
def consultar_cliente(cpf):
    conn = conectar()
    c = conn.cursor()
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
    c.execute("SELECT descricao, valor, data FROM transacoes WHERE cpf_cliente = ? ORDER BY id DESC LIMIT 10", (cliente["cpf"],))
    cliente["transacoes"] = [{"descricao": t[0], "valor": t[1], "data": t[2]} for t in c.fetchall()]
    conn.close()
    return jsonify(cliente)


@app.route("/cadastrar", methods=["POST"])
def adicionar_cliente():
    data = request.get_json()
    try:
        conn = conectar()
        c = conn.cursor()
        limite = float(data.get("limite_total", 1000))
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


# ── UPDATE de cliente ───────────────────────────────────────────────────────

@app.route("/atualizar", methods=["PUT"])
def atualizar_cliente():
    """
    Atualiza dados de um cliente existente.
    Busca pelo CPF ou nome informado em 'busca'.
    Campos atualizáveis: cpf, nome, numero_cartao, limite_total,
                         vencimento_cartao, vencimento_fatura, status_cartao.
    Ao atualizar o CPF, as transações vinculadas são migradas automaticamente.
    """
    data = request.get_json()
    busca = data.get("busca", "")  # CPF ou nome para localizar o cliente

    if not busca:
        return jsonify({"erro": "Informe 'busca' com o CPF ou nome do cliente"}), 400

    conn = conectar()
    c = conn.cursor()

    busca_limpa = busca.replace('.','').replace('-','').replace(' ','')
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

    # Campos que podem ser atualizados
    novo_cpf            = data.get("cpf", cpf_atual)
    novo_nome           = data.get("nome", nome_atual)
    novo_cartao         = data.get("numero_cartao")
    novo_venc_cartao    = data.get("vencimento_cartao")
    novo_venc_fatura    = data.get("vencimento_fatura")
    novo_status         = data.get("status_cartao")

    # Recalcula limites se o limite_total for alterado
    novo_limite_total   = float(data["limite_total"]) if "limite_total" in data else limite_total_atual
    if "limite_total" in data:
        diferenca           = novo_limite_total - limite_total_atual
        novo_limite_disp    = max(0.0, limite_disp_atual + diferenca)
    else:
        novo_limite_disp    = limite_disp_atual

    try:
        # Se o CPF mudou, migra as transações antes de atualizar
        if novo_cpf != cpf_atual:
            c.execute(
                "UPDATE transacoes SET cpf_cliente = ? WHERE cpf_cliente = ?",
                (novo_cpf, cpf_atual)
            )

        # Monta UPDATE dinâmico apenas com os campos enviados
        campos_update = {
            "cpf":               novo_cpf,
            "nome":              novo_nome,
            "limite_total":      novo_limite_total,
            "limite_disponivel": novo_limite_disp,
        }
        if novo_cartao       is not None: campos_update["numero_cartao"]     = novo_cartao
        if novo_venc_cartao  is not None: campos_update["vencimento_cartao"] = novo_venc_cartao
        if novo_venc_fatura  is not None: campos_update["vencimento_fatura"] = novo_venc_fatura
        if novo_status       is not None: campos_update["status_cartao"]     = novo_status

        set_clause = ", ".join(f"{k} = ?" for k in campos_update)
        valores    = list(campos_update.values()) + [cpf_atual]

        c.execute(f"UPDATE clientes SET {set_clause} WHERE cpf = ?", valores)
        conn.commit()
        conn.close()
        return jsonify({
            "status":   "ok",
            "mensagem": f"Cliente '{novo_nome}' atualizado com sucesso!",
            "cpf_antigo": cpf_atual if novo_cpf != cpf_atual else None,
            "cpf_novo":   novo_cpf  if novo_cpf != cpf_atual else None,
        })

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"erro": "O novo CPF já pertence a outro cliente"}), 400
    except Exception as e:
        conn.close()
        return jsonify({"erro": str(e)}), 500


# ── DELETE de cliente ───────────────────────────────────────────────────────

@app.route("/deletar", methods=["DELETE"])
def deletar_cliente():
    """
    Remove um cliente e todas as suas transações.
    Aceita 'cpf' ou 'nome' no body JSON para localizar o registro.
    """
    data = request.get_json()
    busca = data.get("cpf") or data.get("nome", "")

    if not busca:
        return jsonify({"erro": "Informe 'cpf' ou 'nome' do cliente a ser deletado"}), 400

    conn = conectar()
    c = conn.cursor()

    busca_limpa = busca.replace('.','').replace('-','').replace(' ','')
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

    # Remove transações primeiro (integridade referencial)
    c.execute("DELETE FROM transacoes WHERE cpf_cliente = ?", (cpf_real,))
    c.execute("DELETE FROM clientes WHERE cpf = ?", (cpf_real,))
    conn.commit()
    conn.close()

    return jsonify({
        "status":   "ok",
        "mensagem": f"Cliente '{nome_real}' e todas as suas transações foram removidos com sucesso.",
    })


# ── Rotas existentes (sem alteração) ───────────────────────────────────────

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
