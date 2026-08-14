/* Página inicial da Polloni Flow.
 *
 * A medição vem primeiro, de propósito. Ela é o que alimenta o painel de
 * relatórios, e antes ficava no fim do arquivo, depois da animação de fundo:
 * qualquer erro no canvas levava junto o registro dos cliques, e o relatório
 * mostrava zero sem que ninguém soubesse por quê.
 */

const medicao = document.body.dataset;
const temVisita = Boolean(medicao.visita);

function enviar(endereco, dados) {
    if (!endereco) return;
    // sendBeacon porque o clique no WhatsApp costuma tirar a pessoa da página
    // antes de um pedido comum terminar.
    if (navigator.sendBeacon && navigator.sendBeacon(endereco, dados)) return;
    fetch(endereco, { method: "POST", body: dados, keepalive: true }).catch(() => {});
}

/* ---------- quanto da página a pessoa viu, e por quanto tempo ---------- */

let rolagemMaxima = 0;
let segundos = 0;
let marcaDoTempo = Date.now();
let ultimoEnvio = "";

function profundidade() {
    const documento = document.documentElement;
    const total = Math.max(documento.scrollHeight, document.body.scrollHeight);
    const visivel = window.innerHeight;
    // Página que cabe inteira na tela já foi vista inteira.
    if (total <= visivel + 4) return 100;
    const rolado = (window.scrollY || documento.scrollTop || 0) + visivel;
    return Math.max(0, Math.min(100, Math.round((rolado / total) * 100)));
}

function marcarRolagem() {
    rolagemMaxima = Math.max(rolagemMaxima, profundidade());
}

// Só conta o tempo com a página à vista: aba no fundo ou celular no bolso não
// é tempo de leitura.
function acumularTempo() {
    const agora = Date.now();
    if (document.visibilityState === "visible") {
        segundos += (agora - marcaDoTempo) / 1000;
    }
    marcaDoTempo = agora;
}

function enviarMedida() {
    if (!temVisita) return;
    acumularTempo();
    marcarRolagem();

    const total = Math.round(segundos);
    const resumo = `${rolagemMaxima}:${total}`;
    // A saída pode ser avisada duas vezes (visibilitychange e pagehide) e a
    // pessoa pode voltar e sair de novo. Só vale a pena mandar o que mudou.
    if (resumo === ultimoEnvio) return;
    ultimoEnvio = resumo;

    const dados = new FormData();
    dados.append("visita", medicao.visita);
    dados.append("rolagem", String(rolagemMaxima));
    dados.append("segundos", String(total));
    enviar(medicao.medidaUrl, dados);
}

if (temVisita) {
    marcarRolagem();
    addEventListener("scroll", marcarRolagem, { passive: true });
    addEventListener("resize", marcarRolagem, { passive: true });

    document.addEventListener("visibilitychange", () => {
        acumularTempo();
        if (document.visibilityState === "hidden") enviarMedida();
    });
    // pagehide é o aviso de saída que o Safari do iPhone respeita.
    addEventListener("pagehide", enviarMedida);
}

/* ---------- cliques nos botões ---------- */

if (temVisita && medicao.eventoUrl) {
    document.querySelectorAll("[data-evento]").forEach((alvo) => {
        alvo.addEventListener("click", () => {
            const dados = new FormData();
            dados.append("evento", alvo.dataset.evento);
            dados.append("visita", medicao.visita);
            enviar(medicao.eventoUrl, dados);
            // Manda junto o quanto a pessoa tinha lido até clicar: é o que
            // mostra se o botão convence no começo ou só depois da página toda.
            enviarMedida();
        });
    });
}

/* ---------- aparições ao rolar ---------- */

const itensQueAparecem = document.querySelectorAll("[data-reveal]");

if (typeof IntersectionObserver === "function") {
    const observador = new IntersectionObserver(
        (entradas) => {
            entradas.forEach((entrada) => {
                if (entrada.isIntersecting) {
                    entrada.target.classList.add("is-visible");
                    observador.unobserve(entrada.target);
                }
            });
        },
        { threshold: 0.14 }
    );
    itensQueAparecem.forEach((item) => observador.observe(item));
} else {
    // Sem suporte, o conteúdo aparece direto — nunca escondido.
    itensQueAparecem.forEach((item) => item.classList.add("is-visible"));
}

/* ---------- animação de fundo ---------- */

const canvas = document.getElementById("networkCanvas");
const semAnimacao = matchMedia("(prefers-reduced-motion: reduce)").matches;

if (canvas && !semAnimacao) {
    const ctx = canvas.getContext("2d");
    let particulas = [];
    let quadro = null;

    // O desenho compara cada partícula com todas as outras, então o custo sobe
    // com o quadrado da quantidade. No celular vale menos partícula: a conta
    // cai para um quarto e a página deixa de esquentar o aparelho.
    function criarParticulas() {
        const area = window.innerWidth * window.innerHeight;
        const teto = window.innerWidth < 760 ? 34 : 86;
        const quantidade = Math.min(teto, Math.floor(area / 14500));
        particulas = Array.from({ length: quantidade }, () => ({
            x: Math.random() * window.innerWidth,
            y: Math.random() * window.innerHeight,
            vx: (Math.random() - 0.5) * 0.38,
            vy: (Math.random() - 0.5) * 0.38,
            size: Math.random() * 1.8 + 0.8,
        }));
    }

    function redimensionar() {
        const proporcao = window.devicePixelRatio || 1;
        canvas.width = window.innerWidth * proporcao;
        canvas.height = window.innerHeight * proporcao;
        canvas.style.width = `${window.innerWidth}px`;
        canvas.style.height = `${window.innerHeight}px`;
        ctx.setTransform(proporcao, 0, 0, proporcao, 0, 0);
        criarParticulas();
    }

    function desenhar() {
        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        particulas.forEach((particula, indice) => {
            particula.x += particula.vx;
            particula.y += particula.vy;

            if (particula.x < 0 || particula.x > window.innerWidth) particula.vx *= -1;
            if (particula.y < 0 || particula.y > window.innerHeight) particula.vy *= -1;

            ctx.beginPath();
            ctx.arc(particula.x, particula.y, particula.size, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(89, 227, 155, 0.72)";
            ctx.fill();

            for (let outro = indice + 1; outro < particulas.length; outro += 1) {
                const par = particulas[outro];
                const dx = particula.x - par.x;
                const dy = particula.y - par.y;
                const distancia = Math.sqrt(dx * dx + dy * dy);

                if (distancia < 128) {
                    ctx.beginPath();
                    ctx.moveTo(particula.x, particula.y);
                    ctx.lineTo(par.x, par.y);
                    ctx.strokeStyle = `rgba(66, 217, 255, ${0.18 * (1 - distancia / 128)})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        });

        quadro = requestAnimationFrame(desenhar);
    }

    function tocar() {
        if (quadro === null) quadro = requestAnimationFrame(desenhar);
    }

    function parar() {
        if (quadro !== null) {
            cancelAnimationFrame(quadro);
            quadro = null;
        }
    }

    addEventListener("resize", redimensionar);
    // Aba escondida não precisa de animação; parar aqui poupa bateria.
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") parar();
        else tocar();
    });

    redimensionar();
    tocar();
}
