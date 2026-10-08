function iniciarMenu() {
  const botao = document.querySelector("[data-menu]");
  const painel = document.querySelector("[data-painel]");
  if (!botao || !painel) return;
  botao.addEventListener("click", () => {
    const aberto = painel.classList.toggle("hidden") === false;
    botao.setAttribute("aria-expanded", aberto ? "true" : "false");
  });
}

function iniciarCarrossel() {
  document.querySelectorAll("[data-carrossel]").forEach((raiz) => {
    const slides = [...raiz.querySelectorAll("[data-slide]")];
    if (slides.length < 2) return;
    let atual = 0;
    const pontos = [...raiz.querySelectorAll("[data-ponto]")];
    const mostrar = (indice) => {
      atual = (indice + slides.length) % slides.length;
      slides.forEach((slide, i) => slide.classList.toggle("hidden", i !== atual));
      pontos.forEach((ponto, i) => {
        ponto.classList.toggle("bg-vinho", i === atual);
        ponto.classList.toggle("bg-stone-300", i !== atual);
      });
    };
    raiz.querySelector("[data-anterior]")?.addEventListener("click", () => mostrar(atual - 1));
    raiz.querySelector("[data-proximo]")?.addEventListener("click", () => mostrar(atual + 1));
    pontos.forEach((ponto, i) => ponto.addEventListener("click", () => mostrar(i)));
    const reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduzir) return;
    let timer = setInterval(() => mostrar(atual + 1), 6500);
    raiz.addEventListener("mouseenter", () => clearInterval(timer));
    raiz.addEventListener("mouseleave", () => {
      timer = setInterval(() => mostrar(atual + 1), 6500);
    });
  });
}

function iniciarCalendario() {
  const el = document.querySelector("[data-calendario]");
  if (!el || typeof FullCalendar === "undefined") return;
  const estreito = window.matchMedia("(max-width: 768px)").matches;
  const painel = document.querySelector("[data-detalhe-evento]");
  const calendario = new FullCalendar.Calendar(el, {
    initialView: estreito ? "listMonth" : "dayGridMonth",
    locale: "pt-br",
    height: "auto",
    events: "/calendario/eventos.json",
    headerToolbar: {
      left: "prev,next today",
      center: "title",
      right: estreito ? "" : "dayGridMonth,listMonth",
    },
    buttonText: { today: "hoje", month: "mês", list: "lista" },
    eventClick(info) {
      info.jsEvent.preventDefault();
      if (!painel) return;
      const extra = info.event.extendedProps || {};
      const quando = info.event.allDay
        ? info.event.start.toLocaleDateString("pt-BR")
        : info.event.start.toLocaleString("pt-BR");
      painel.replaceChildren();
      const titulo = document.createElement("h3");
      titulo.className = "font-serif text-2xl text-tinta";
      titulo.textContent = info.event.title;
      const hora = document.createElement("p");
      hora.className = "mt-2";
      hora.textContent = quando;
      painel.append(titulo, hora);
      ["local", "subsede", "descricao"].forEach((chave) => {
        if (!extra[chave]) return;
        const linha = document.createElement("p");
        linha.className = chave === "descricao" ? "mt-2 text-stone-600" : "";
        linha.textContent = extra[chave];
        painel.append(linha);
      });
      painel.classList.remove("hidden");
    },
  });
  calendario.render();
}

document.addEventListener("DOMContentLoaded", () => {
  iniciarMenu();
  iniciarCarrossel();
  iniciarCalendario();
});
