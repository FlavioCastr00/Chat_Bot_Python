// ════════════════════════════════════════════════════════════
//  ESTADO GLOBAL
// ════════════════════════════════════════════════════════════
let sessao = { logado: false, cpf: null, nome: null };
let estado = { aguardando: null, dados: {} };

// ── Utilitários ─────────────────────────────────────────────
function agora() {
    return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function fmt(v) {
    return 'R$ ' + Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(usado, total) {
    return total > 0 ? Math.round((usado / total) * 100) : 0;
}

// ── Sessão ───────────────────────────────────────────────────
function ativarSessao(cpf, nome) {
    sessao = { logado: true, cpf, nome };
    document.getElementById('sidebar-nome').textContent = nome;
    document.getElementById('sidebar-cpf').textContent = cpf;
    document.getElementById('btn-sair').style.display = 'block';
    document.querySelectorAll('.cmd-btn.locked').forEach(b => b.disabled = false);
}

function sair() {
    sessao = { logado: false, cpf: null, nome: null };
    estado = { aguardando: null, dados: {} };
    document.getElementById('sidebar-nome').textContent = 'Não identificado';
    document.getElementById('sidebar-cpf').textContent = '—';
    document.getElementById('btn-sair').style.display = 'none';
    document.querySelectorAll('.cmd-btn.locked').forEach(b => b.disabled = true);
    document.getElementById('chat-area').innerHTML = '';
    addMsg('Você saiu da conta. Para continuar, informe seu CPF.', 'bot');
    addSugestoes(['Entrar com CPF', 'Criar conta']);
}

// ── Renderização ─────────────────────────────────────────────
function addMsg(conteudo, tipo, isHTML = false) {
    const area = document.getElementById('chat-area');
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap ' + tipo;
    const msg = document.createElement('div');
    msg.className = 'msg ' + tipo;
    if (isHTML) msg.innerHTML = conteudo; else msg.textContent = conteudo;
    const time = document.createElement('div');
    time.className = 'msg-time';
    time.textContent = agora();
    wrap.appendChild(msg);
    wrap.appendChild(time);
    area.appendChild(wrap);
    area.scrollTop = area.scrollHeight;
    return msg;
}

function addLoading() {
    const area = document.getElementById('chat-area');
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap bot';
    wrap.id = 'loading-msg';
    wrap.innerHTML = '<div class="msg bot"><div class="loading-dots"><span></span><span></span><span></span></div></div>';
    area.appendChild(wrap);
    area.scrollTop = area.scrollHeight;
}

function removeLoading() {
    const el = document.getElementById('loading-msg');
    if (el) el.remove();
}

function addSugestoes(lista) {
    const area = document.getElementById('chat-area');
    const div = document.createElement('div');
    div.className = 'sugestoes';
    lista.forEach(s => {
        const t = document.createElement('span');
        t.className = 'tag';
        t.textContent = s;
        t.onclick = () => { sendCmd(s); div.remove(); };
        div.appendChild(t);
    });
    area.appendChild(div);
    area.scrollTop = area.scrollHeight;
}

// ── Templates ────────────────────────────────────────────────
function cardConta(c) {
    const usado = c.limite_total - c.limite_disponivel;
    const p = pct(usado, c.limite_total);
    const cor = p > 80 ? '#a32d2d' : '#185fa5';
    return `
      <strong style="font-size:14px">Olá, ${c.nome}! 👋</strong>
      <div class="result-card" style="margin-top:8px">
        <div class="card-row"><span class="lbl">Cartão</span><span class="val">${c.numero_cartao}</span></div>
        <div class="card-row"><span class="lbl">Venc. cartão</span><span class="val">${c.vencimento_cartao}</span></div>
        <div class="card-row"><span class="lbl">Status</span><span class="val"><span class="badge ${c.status_cartao}">${c.status_cartao}</span></span></div>
        <div class="card-row"><span class="lbl">Limite total</span><span class="val">${fmt(c.limite_total)}</span></div>
        <div class="card-row"><span class="lbl">Limite disponível</span><span class="val" style="color:#0c447c">${fmt(c.limite_disponivel)}</span></div>
        <div class="card-row"><span class="lbl">Fatura atual</span><span class="val" style="color:${c.fatura_atual > c.limite_total * 0.7 ? '#a32d2d' : '#185fa5'}">${fmt(c.fatura_atual)}</span></div>
        <div class="card-row"><span class="lbl">Venc. fatura</span><span class="val">${c.vencimento_fatura}</span></div>
        <div style="padding:8px 12px 10px">
          <div style="font-size:11px;color:#aaa;margin-bottom:4px">Uso do limite: ${p}%</div>
          <div class="prog-bar"><div class="prog-fill" style="width:${p}%;background:${cor}"></div></div>
        </div>
      </div>
    `;
}

function cardCartao(c) {
    const usado = c.limite_total - c.limite_disponivel;
    const p = pct(usado, c.limite_total);
    return `
      <strong>Informações do cartão</strong>
      <div class="result-card" style="margin-top:8px">
        <div class="card-row"><span class="lbl">Titular</span><span class="val">${c.nome}</span></div>
        <div class="card-row"><span class="lbl">Cartão</span><span class="val">${c.numero_cartao}</span></div>
        <div class="card-row"><span class="lbl">Status</span><span class="val"><span class="badge ${c.status_cartao}">${c.status_cartao}</span></span></div>
        <div class="card-row"><span class="lbl">Vencimento do cartão</span><span class="val">${c.vencimento_cartao}</span></div>
        <div class="card-row"><span class="lbl">Limite total</span><span class="val">${fmt(c.limite_total)}</span></div>
        <div class="card-row"><span class="lbl">Limite disponível</span><span class="val" style="color:#0c447c">${fmt(c.limite_disponivel)}</span></div>
        <div class="card-row"><span class="lbl">Uso do limite</span><span class="val">${p}%</span></div>
      </div>
    `;
}

function cardFatura(c) {
    const transList = (c.transacoes && c.transacoes.length > 0)
        ? c.transacoes.map(t =>
            `<div class="card-row">
            <span class="lbl">${t.descricao} <span style="color:#bbb;font-size:11px">${t.data}</span></span>
            <span class="val">${fmt(t.valor)}</span>
          </div>`
        ).join('')
        : '<div class="card-row"><span class="lbl" style="color:#bbb">Nenhuma transação registrada</span></div>';

    return `
      <strong>Sua fatura</strong>
      <div class="result-card" style="margin-top:8px">
        <div class="card-row"><span class="lbl">Valor da fatura</span><span class="val" style="color:#a32d2d">${fmt(c.fatura_atual)}</span></div>
        <div class="card-row"><span class="lbl">Vencimento</span><span class="val">${c.vencimento_fatura}</span></div>
        <div class="card-row"><span class="lbl">Limite disponível</span><span class="val" style="color:#0c447c">${fmt(c.limite_disponivel)}</span></div>
      </div>
      <div style="margin-top:10px;font-size:12px;font-weight:600;color:#888;padding-left:2px">Lançamentos</div>
      <div class="result-card">${transList}</div>
    `;
}

function ajudaHTML() {
    return `
        <strong>O que posso fazer por você</strong>
        <div class="result-card" style="margin-top:8px">
          <div class="card-row"><span class="lbl">entrar com CPF</span><span class="val" style="color:#185fa5">Identificação</span></div>
          <div class="card-row"><span class="lbl">criar conta</span><span class="val" style="color:#185fa5">Auto-cadastro</span></div>
          <div class="card-row"><span class="lbl">minha conta</span><span class="val" style="color:#185fa5">Dados e limite</span></div>
          <div class="card-row"><span class="lbl">cartão</span><span class="val" style="color:#185fa5">Status e limite</span></div>
          <div class="card-row"><span class="lbl">minha fatura</span><span class="val" style="color:#185fa5">Fatura e lançamentos</span></div>
          <div class="card-row"><span class="lbl">fazer uma compra</span><span class="val" style="color:#185fa5">Simular compra</span></div>
          <div class="card-row"><span class="lbl">bloquear cartão</span><span class="val" style="color:#a32d2d">Bloquear</span></div>
          <div class="card-row"><span class="lbl">desbloquear cartão</span><span class="val" style="color:#27500a">Desbloquear</span></div>
          <div class="card-row"><span class="lbl">atualizar meus dados</span><span class="val" style="color:#185fa5">Corrigir nome/CPF</span></div>
          <div class="card-row"><span class="lbl">encerrar minha conta</span><span class="val" style="color:#a32d2d">Excluir conta</span></div>
        </div>
      `;
}

// ── API ───────────────────────────────────────────────────────
async function api(rota, metodo = 'GET', body = null) {
    const opts = { method: metodo, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(rota, opts);
    return res.json();
}

async function classificarMensagem(msg) {
    const data = await api('/chat', 'POST', {
        message: msg,
        cpf: sessao.cpf
    });

    // Ajuda no aprendizado: abra o console do navegador para ver o ML funcionando.
    console.log('[ML] intenção:', data.intent, '| confiança:', data.confidence, '| resposta:', data.response);
    return data;
}

// ── Guard: exige login ────────────────────────────────────────
function exigeLogin() {
    if (!sessao.logado) {
        addMsg('Você precisa estar logado para isso. Informe seu CPF:', 'bot');
        estado.aguardando = 'login_cpf';
        return true;
    }
    return false;
}

// ════════════════════════════════════════════════════════════
//  EXECUÇÃO DAS INTENÇÕES PREVISTAS PELO MODELO
// ════════════════════════════════════════════════════════════
async function executarIntencao(intent, msg, mlData) {
    if (intent === 'saudacao') {
        addMsg(mlData.response || 'Olá! Como posso ajudar?', 'bot');
        addSugestoes(sessao.logado ? ['Minha fatura', 'Cartão', 'Ver minha conta'] : ['Entrar com CPF', 'Criar conta', 'Ajuda']);
        return;
    }

    if (intent === 'despedida') {
        addMsg(mlData.response || 'Até mais!', 'bot');
        return;
    }

    if (intent === 'login') {
        if (sessao.logado) {
            addMsg(`Você já está logado como ${sessao.nome}.`, 'bot');
            addSugestoes(['Ver minha conta', 'Minha fatura', 'Sair']);
            return;
        }
        addMsg('Informe seu CPF para entrar:', 'bot');
        estado.aguardando = 'login_cpf';
        return;
    }

    if (intent === 'criar_conta') {
        addMsg('Vamos criar sua conta! Qual é o seu nome completo?', 'bot');
        estado.aguardando = 'cad_nome';
        estado.dados = {};
        return;
    }

    if (intent === 'atualizar_dados') {
        if (exigeLogin()) return;
        addMsg('O que deseja atualizar? Digite "nome" ou "cpf":', 'bot');
        estado.aguardando = 'upd_campo';
        return;
    }

    if (intent === 'encerrar_conta') {
        if (exigeLogin()) return;
        addMsg('⚠️ Tem certeza que deseja encerrar sua conta? Todos os seus dados serão removidos permanentemente. Digite "sim" para confirmar ou qualquer outra coisa para cancelar.', 'bot');
        estado.aguardando = 'confirmar_encerramento';
        return;
    }

    if (intent === 'visualizar_conta') {
        if (exigeLogin()) return;
        addLoading();
        const data = await api('/minha-conta', 'POST', { cpf: sessao.cpf });
        removeLoading();
        if (data.erro) { addMsg('Erro: ' + data.erro, 'bot'); return; }
        addMsg(cardConta(data), 'bot', true);
        addSugestoes(['Minha fatura', 'Cartão', 'Fazer uma compra', 'Atualizar meus dados']);
        return;
    }

    if (intent === 'cartao') {
        if (exigeLogin()) return;
        addLoading();
        const data = await api('/meu-cartao', 'POST', { cpf: sessao.cpf });
        removeLoading();
        if (data.erro) { addMsg('Erro: ' + data.erro, 'bot'); return; }
        addMsg(cardCartao(data), 'bot', true);
        addSugestoes(data.status_cartao === 'bloqueado' ? ['Desbloquear meu cartão', 'Minha fatura'] : ['Bloquear meu cartão', 'Minha fatura', 'Fazer uma compra']);
        return;
    }

    if (intent === 'minha_fatura') {
        if (exigeLogin()) return;
        addLoading();
        const data = await api('/minha-fatura', 'POST', { cpf: sessao.cpf });
        removeLoading();
        if (data.erro) { addMsg('Erro: ' + data.erro, 'bot'); return; }
        addMsg(cardFatura(data), 'bot', true);
        addSugestoes(['Fazer uma compra', 'Cartão', 'Ver minha conta']);
        return;
    }

    if (intent === 'desbloquear_cartao') {
        if (exigeLogin()) return;
        addLoading();
        const data = await api('/desbloquear-meu-cartao', 'POST', { cpf: sessao.cpf });
        removeLoading();
        if (data.erro) { addMsg('Aviso: ' + data.erro, 'bot'); return; }
        addMsg(`🔓 ${data.mensagem}`, 'bot');
        addSugestoes(['Cartão', 'Fazer uma compra', 'Ver minha conta']);
        return;
    }

    if (intent === 'bloquear_cartao') {
        if (exigeLogin()) return;
        addLoading();
        const data = await api('/bloquear-meu-cartao', 'POST', { cpf: sessao.cpf });
        removeLoading();
        if (data.erro) { addMsg('Aviso: ' + data.erro, 'bot'); return; }
        addMsg(`🔒 ${data.mensagem}`, 'bot');
        addSugestoes(['Cartão', 'Desbloquear meu cartão', 'Ver minha conta']);
        return;
    }

    if (intent === 'fazer_compra') {
        if (exigeLogin()) return;
        addMsg('Qual é a descrição da compra? (ex: Supermercado, Netflix...)', 'bot');
        estado.aguardando = 'compra_desc';
        estado.dados = {};
        return;
    }

    if (intent === 'sair') {
        sair();
        return;
    }

    if (intent === 'ajuda') {
        addMsg(ajudaHTML(), 'bot', true);
        return;
    }

    // Fallback
    addMsg('Não entendi. Digite "ajuda" para ver o que posso fazer por você.', 'bot');
    addSugestoes(['Ajuda', sessao.logado ? 'Ver minha conta' : 'Entrar com CPF']);
}

// ════════════════════════════════════════════════════════════
//  PROCESSAMENTO PRINCIPAL
// ════════════════════════════════════════════════════════════
async function processar(msg) {
    const m = msg.trim().toLowerCase();
    const btn = document.getElementById('send-btn');
    btn.disabled = true;

    // ── Fluxos aguardando resposta ────────────────────────────
    // Estes trechos continuam manuais porque são respostas de formulário
    // como CPF, nome, dia de vencimento e valor da compra.

    // LOGIN
    if (estado.aguardando === 'login_cpf') {
        estado.aguardando = null;
        addLoading();
        const data = await api('/login', 'POST', { cpf: msg.trim() });
        removeLoading();
        if (data.erro) {
            if (data.cadastrar) {
                addMsg('CPF não encontrado. Deseja criar uma conta agora?', 'bot');
                addSugestoes(['Sim, quero me cadastrar', 'Tentar outro CPF']);
            } else {
                addMsg('Erro: ' + data.erro, 'bot');
                addSugestoes(['Tentar novamente']);
            }
            btn.disabled = false; return;
        }
        ativarSessao(data.cpf, data.nome);
        addMsg(cardConta(data), 'bot', true);
        addSugestoes(['Minha fatura', 'Cartão', 'Fazer uma compra', 'Bloquear meu cartão']);
        btn.disabled = false; return;
    }

    // CADASTRO
    if (estado.aguardando === 'cad_nome') {
        estado.dados.nome = msg.trim();
        estado.aguardando = 'cad_cpf';
        addMsg('Qual é o seu CPF? (ex: 123.456.789-00)', 'bot');
        btn.disabled = false; return;
    }

    if (estado.aguardando === 'cad_cpf') {
        estado.dados.cpf = msg.trim();
        estado.aguardando = 'cad_dia';
        addMsg('Em qual dia do mês prefere o vencimento da sua fatura? (ex: 5, 10, 15, 20)', 'bot');
        btn.disabled = false; return;
    }

    if (estado.aguardando === 'cad_dia') {
        const dia = parseInt(msg.trim());
        if (isNaN(dia) || dia < 1 || dia > 28) {
            addMsg('Dia inválido. Informe um número entre 1 e 28.', 'bot');
            btn.disabled = false; return;
        }
        addLoading();
        const data = await api('/cadastrar', 'POST', {
            cpf: estado.dados.cpf,
            nome: estado.dados.nome,
            dia_vencimento: dia
        });
        removeLoading();
        estado.aguardando = null; estado.dados = {};
        if (data.erro) { addMsg('Erro: ' + data.erro, 'bot'); btn.disabled = false; return; }
        ativarSessao(data.cpf, data.nome);
        addMsg(`
        <strong>${data.mensagem}</strong>
        <div class="result-card" style="margin-top:8px">
          <div class="card-row"><span class="lbl">Nome</span><span class="val">${data.nome}</span></div>
          <div class="card-row"><span class="lbl">CPF</span><span class="val">${data.cpf}</span></div>
          <div class="card-row"><span class="lbl">Cartão</span><span class="val">${data.numero_cartao}</span></div>
          <div class="card-row"><span class="lbl">Limite inicial</span><span class="val">${fmt(data.limite_total)}</span></div>
          <div class="card-row"><span class="lbl">Venc. fatura</span><span class="val">${data.vencimento_fatura}</span></div>
          <div class="card-row"><span class="lbl">Status</span><span class="val"><span class="badge ativo">ativo</span></span></div>
        </div>
      `, 'bot', true);
        addSugestoes(['Minha fatura', 'Cartão', 'Fazer uma compra']);
        btn.disabled = false; return;
    }

    // COMPRA
    if (estado.aguardando === 'compra_desc') {
        estado.dados.desc = msg.trim();
        estado.aguardando = 'compra_valor';
        addMsg('Qual o valor? (ex: 150.00)', 'bot');
        btn.disabled = false; return;
    }

    if (estado.aguardando === 'compra_valor') {
        const val = parseFloat(msg.replace(',', '.'));
        if (isNaN(val) || val <= 0) {
            addMsg('Valor inválido. Digite um número positivo (ex: 150.00).', 'bot');
            btn.disabled = false; return;
        }
        addLoading();
        const data = await api('/compra', 'POST', {
            cpf: sessao.cpf,
            descricao: estado.dados.desc,
            valor: val
        });
        removeLoading();
        estado.aguardando = null; estado.dados = {};
        if (data.erro) { addMsg('Recusada: ' + data.erro, 'bot'); btn.disabled = false; return; }
        addMsg(`
        <strong>Compra aprovada ✅</strong>
        <div class="result-card" style="margin-top:8px">
          <div class="card-row"><span class="lbl">Descrição</span><span class="val">${data.descricao}</span></div>
          <div class="card-row"><span class="lbl">Valor</span><span class="val" style="color:#185fa5">${fmt(data.valor)}</span></div>
          <div class="card-row"><span class="lbl">Limite restante</span><span class="val">${fmt(data.limite_disponivel)}</span></div>
          <div class="card-row"><span class="lbl">Nova fatura</span><span class="val">${fmt(data.fatura_atual)}</span></div>
        </div>
      `, 'bot', true);
        addSugestoes(['Minha fatura', 'Fazer outra compra', 'Cartão', 'Ver minha conta']);
        btn.disabled = false; return;
    }

    // ATUALIZAR DADOS
    if (estado.aguardando === 'upd_campo') {
        if (m === 'nome') {
            estado.aguardando = 'upd_nome';
            addMsg('Qual é o seu novo nome completo?', 'bot');
        } else if (m === 'cpf') {
            estado.aguardando = 'upd_cpf';
            addMsg('Qual é o novo CPF? (ex: 987.654.321-00)', 'bot');
        } else {
            addMsg('Opção inválida. Digite "nome" ou "cpf".', 'bot');
        }
        btn.disabled = false; return;
    }

    if (estado.aguardando === 'upd_nome') {
        addLoading();
        const data = await api('/atualizar-meus-dados', 'PUT', {
            busca: sessao.cpf,
            nome: msg.trim()
        });
        removeLoading();
        estado.aguardando = null;
        if (data.erro) { addMsg('Erro: ' + data.erro, 'bot'); btn.disabled = false; return; }
        sessao.nome = data.nome;
        document.getElementById('sidebar-nome').textContent = data.nome;
        addMsg(`✅ ${data.mensagem}`, 'bot');
        addSugestoes(['Ver minha conta', 'Minha fatura']);
        btn.disabled = false; return;
    }

    if (estado.aguardando === 'upd_cpf') {
        addLoading();
        const data = await api('/atualizar-meus-dados', 'PUT', {
            busca: sessao.cpf,
            cpf: msg.trim()
        });
        removeLoading();
        estado.aguardando = null;
        if (data.erro) { addMsg('Erro: ' + data.erro, 'bot'); btn.disabled = false; return; }
        sessao.cpf = data.cpf;
        document.getElementById('sidebar-cpf').textContent = data.cpf;
        addMsg(`✅ ${data.mensagem}`, 'bot');
        addSugestoes(['Ver minha conta', 'Minha fatura']);
        btn.disabled = false; return;
    }

    // ENCERRAR CONTA — confirmação
    if (estado.aguardando === 'confirmar_encerramento') {
        estado.aguardando = null;
        if (m === 'sim' || m === 'confirmar' || m === 'sim, encerrar') {
            addLoading();
            const data = await api('/encerrar-conta', 'DELETE', { cpf: sessao.cpf });
            removeLoading();
            if (data.erro) { addMsg('Erro: ' + data.erro, 'bot'); btn.disabled = false; return; }
            addMsg(`👋 ${data.mensagem}`, 'bot');
            sair();
        } else {
            addMsg('Encerramento cancelado. Sua conta continua ativa.', 'bot');
            addSugestoes(['Ver minha conta', 'Minha fatura']);
        }
        btn.disabled = false; return;
    }

    // ── Machine Learning ───────────────────────────────────────
    // A partir daqui, o chatbot não usa mais uma lista grande de if/else com includes.
    // Ele envia a frase para /chat, o Flask usa CountVectorizer + LogisticRegression,
    // e a intenção prevista decide qual funcionalidade executar.
    try {
        addLoading();
        const mlData = await classificarMensagem(msg);
        removeLoading();
        await executarIntencao(mlData.intent, msg, mlData);
    } catch (error) {
        removeLoading();
        console.error(error);
        addMsg('Erro ao consultar o modelo de Machine Learning.', 'bot');
    }

    btn.disabled = false;
}

function enviar() {
    const inp = document.getElementById('msg-input');
    const val = inp.value.trim();
    if (!val) return;
    addMsg(val, 'user');
    inp.value = '';
    setTimeout(() => processar(val), 100);
}

function sendCmd(cmd) {
    addMsg(cmd, 'user');
    setTimeout(() => processar(cmd), 100);
}

// ── Mensagem inicial ──────────────────────────────────────────
window.addEventListener('load', () => {
    setTimeout(() => {
        addMsg('Olá! 👋 Bem-vindo(a) ao Banco Digital. Agora o chatbot usa Machine Learning para entender suas mensagens. Para começar, informe seu CPF ou crie uma conta.', 'bot');
        addSugestoes(['Entrar com CPF', 'Criar conta', 'Ajuda']);
    }, 300);
});
