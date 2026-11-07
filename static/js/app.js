// Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
// Desenvolvido por Diego Mendes Rodrigues
(function () {
  "use strict";

  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  // Na categoria compartilhada por outro usuário, vale "editar" ou "visualizar".
  const quadroDaPagina = document.getElementById("quadro");
  const permissaoDoQuadro = quadroDaPagina ? quadroDaPagina.dataset.permissao : "dono";
  const pesquisaAtiva = Boolean(quadroDaPagina && quadroDaPagina.hasAttribute("data-busca"));

  const TEMPO_DA_NOTIFICACAO = 3000;
  const notificacao = document.getElementById("notificacao");
  const textoDaNotificacao = notificacao.querySelector("[data-notificacao-texto]");
  let temporizadorDaNotificacao;

  function fecharNotificacao() {
    clearTimeout(temporizadorDaNotificacao);
    if (notificacao.open) {
      notificacao.close();
    }
  }

  function abrirNotificacao() {
    clearTimeout(temporizadorDaNotificacao);
    if (!notificacao.open) {
      notificacao.showModal();
    }
    temporizadorDaNotificacao = setTimeout(fecharNotificacao, TEMPO_DA_NOTIFICACAO);
  }

  function notificarErro(texto) {
    const mensagem = document.createElement("p");
    mensagem.textContent = texto;
    textoDaNotificacao.replaceChildren(mensagem);
    abrirNotificacao();
  }

  notificacao.querySelector("[data-notificacao-ok]").addEventListener("click", fecharNotificacao);

  // O que precisa ser preenchido nos campos ocultos antes de um formulário ser enviado: roda no
  // envio comum e também quando o formulário é gravado por fetch (prepararEnvio). Não dispare um
  // evento "submit" artificial para isso: extensões do navegador, como a do Kaspersky, reagem a ele
  // enviando o formulário de verdade, o que recarrega a página.
  const PREPARACOES_DO_ENVIO = new Map();

  function antesDeEnviar(formulario, preparar, opcoes) {
    if (!PREPARACOES_DO_ENVIO.has(formulario)) {
      PREPARACOES_DO_ENVIO.set(formulario, []);
    }
    PREPARACOES_DO_ENVIO.get(formulario).push(preparar);
    formulario.addEventListener("submit", preparar, opcoes);
  }

  function prepararEnvio(formulario) {
    (PREPARACOES_DO_ENVIO.get(formulario) || []).forEach((preparar) => preparar());
  }

  if (textoDaNotificacao.children.length) {
    abrirNotificacao();
  }

  // Sem isto, os avisos do navegador seguem o idioma do navegador, não o do sistema.
  function mensagemDeValidacao(campo) {
    if (campo.type === "radio") {
      return "Escolha uma das opções.";
    }
    if (campo.validity.valueMissing) {
      return campo.tagName === "SELECT" ? "Escolha uma opção." : "Preencha este campo.";
    }
    if (campo.validity.typeMismatch && campo.type === "email") {
      return "Informe um e-mail válido.";
    }
    if (campo.validity.badInput && campo.type === "datetime-local") {
      return "Informe a data e a hora completas.";
    }
    return "Verifique o valor informado.";
  }

  document.addEventListener(
    "invalid",
    (evento) => evento.target.setCustomValidity(mensagemDeValidacao(evento.target)),
    true
  );

  document.addEventListener("input", (evento) => {
    if (evento.target.type === "radio") {
      document.getElementsByName(evento.target.name).forEach((opcao) => {
        opcao.setCustomValidity("");
      });
    } else if (evento.target.setCustomValidity) {
      evento.target.setCustomValidity("");
    }
  });

  function fecharMenus(exceto) {
    document.querySelectorAll("[data-menu-gatilho]").forEach((gatilho) => {
      if (gatilho !== exceto) {
        gatilho.setAttribute("aria-expanded", "false");
        document.getElementById(gatilho.getAttribute("aria-controls")).hidden = true;
      }
    });
  }

  document.addEventListener("click", (evento) => {
    const gatilho = evento.target.closest("[data-menu-gatilho]");
    if (gatilho) {
      const caixa = document.getElementById(gatilho.getAttribute("aria-controls"));
      fecharMenus(gatilho);
      caixa.hidden = !caixa.hidden;
      gatilho.setAttribute("aria-expanded", String(!caixa.hidden));
    } else if (!evento.target.closest(".menu-caixa")) {
      fecharMenus();
    }
  });

  document.addEventListener("keydown", (evento) => {
    if (evento.key === "Escape") {
      const aberto = document.querySelector('[data-menu-gatilho][aria-expanded="true"]');
      fecharMenus();
      if (aberto) {
        aberto.focus();
      }
    }
  });

  function abrirDialogo(id, titulo, urlSalvar) {
    const dialogo = document.getElementById(id);
    const formulario = dialogo.querySelector("form");

    formulario.querySelectorAll("input, select, textarea").forEach((campo) => {
      campo.setCustomValidity("");
    });
    dialogo.querySelector("[data-titulo]").textContent = titulo;
    formulario.action = urlSalvar || formulario.dataset.urlNova;
    dialogo.showModal();
    return dialogo;
  }

  const TEMPO_DE_PROTECAO_DOS_CAMPOS = 500;
  const CAMPOS_PROTEGIDOS = ["tarefa-nome", "tarefa-local"];
  let temporizadorDosCampos;

  // Gerenciadores de senhas e extensões ignoram autocomplete="off" e podem preencher o campo
  // assim que o diálogo abre. Eles ficam somente leitura por um instante e, se o usuário ainda
  // não interagiu, o que tiver sido inserido nesse intervalo é descartado.
  function protegerCamposDaTarefa() {
    const dialogo = document.getElementById("dialogo-tarefa");
    const campos = CAMPOS_PROTEGIDOS.map((id) => document.getElementById(id));
    const liberar = () => {
      clearTimeout(temporizadorDosCampos);
      campos.forEach((campo) => {
        campo.readOnly = false;
      });
    };

    campos.forEach((campo) => {
      campo.readOnly = true;
    });
    dialogo.addEventListener("keydown", liberar, { capture: true, once: true });
    dialogo.addEventListener("pointerdown", liberar, { capture: true, once: true });
    temporizadorDosCampos = setTimeout(() => {
      campos.forEach((campo) => {
        campo.readOnly = false;
        campo.value = "";
      });
    }, TEMPO_DE_PROTECAO_DOS_CAMPOS);
  }

  function preencherTarefa(valores) {
    clearTimeout(temporizadorDosCampos);
    CAMPOS_PROTEGIDOS.forEach((id) => {
      document.getElementById(id).readOnly = false;
    });
    document.getElementById("tarefa-nome").value = valores.nome || "";
    document.getElementById("tarefa-prioridade").value = valores.prioridade || "baixa";
    document.getElementById("tarefa-previsao").value = valores.previsao || "";
    document.getElementById("tarefa-editor").innerHTML = valores.descricao || "";
    document.getElementById("tarefa-local").value = valores.local || "";
    document.getElementById("tarefa-projeto").value = valores.projetoId;
    preencherTipo(
      valores.tipo || "atividade",
      valores.itens ? JSON.parse(valores.itens) : [],
      valores.secoes ? JSON.parse(valores.secoes) : []
    );
    preencherVideoDoCartao(valores);
    preencherMarcacoes(
      document.querySelector("#dialogo-tarefa [data-marcacoes-campo]"),
      valores.marcacoes ? JSON.parse(valores.marcacoes) : []
    );
  }

  // Marcações: cada ENTER no campo vira uma "pílula" com o botão de remover; a lista vai em JSON
  // no campo oculto "marcacoes". O servidor (ler_marcacoes) repete a limpeza e os limites.
  const LIMITE_MARCACOES = 20;

  function chaveDaMarcacao(texto) {
    return texto.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase("pt-BR");
  }

  function desenharMarcacoes(campo) {
    const modelo = document.getElementById("modelo-marcacao");
    const lista = campo.querySelector("[data-marcacoes-lista]");

    lista.replaceChildren(
      ...campo.marcacoes.map((texto) => {
        const item = modelo.content.firstElementChild.cloneNode(true);
        const remover = item.querySelector("[data-remover-marcacao]");

        item.querySelector("[data-marcacao-texto]").textContent = texto;
        remover.setAttribute("aria-label", "Remover a marcação " + texto);
        remover.dataset.dica = "Remover a marcação";
        return item;
      })
    );
    lista.hidden = !campo.marcacoes.length;
    campo.querySelector("[data-marcacoes-valor]").value = JSON.stringify(campo.marcacoes);
  }

  function preencherMarcacoes(campo, marcacoes) {
    if (!campo) {
      return;
    }
    campo.marcacoes = marcacoes.slice();
    campo.querySelector("[data-marcacoes-entrada]").value = "";
    desenharMarcacoes(campo);
  }

  function adicionarMarcacao(campo) {
    const entrada = campo.querySelector("[data-marcacoes-entrada]");
    const texto = entrada.value.split(/\s+/).filter(Boolean).join(" ");

    if (!texto) {
      return;
    }
    const chave = chaveDaMarcacao(texto);
    if (!campo.marcacoes.some((outra) => chaveDaMarcacao(outra) === chave)) {
      if (campo.marcacoes.length >= LIMITE_MARCACOES) {
        notificarErro("Cada cartão pode ter até " + LIMITE_MARCACOES + " marcações.");
        return;
      }
      campo.marcacoes.push(texto);
      desenharMarcacoes(campo);
    }
    entrada.value = "";
  }

  document.querySelectorAll("[data-marcacoes-campo]").forEach((campo) => {
    campo.marcacoes = [];
    const entrada = campo.querySelector("[data-marcacoes-entrada]");

    entrada.addEventListener("keydown", (evento) => {
      if (evento.key !== "Enter" || evento.isComposing) {
        return;
      }
      // O ENTER cria a marcação e não envia o formulário.
      evento.preventDefault();
      adicionarMarcacao(campo);
    });
    campo.addEventListener("click", (evento) => {
      const remover = evento.target.closest("[data-remover-marcacao]");
      if (!remover) {
        return;
      }
      const item = remover.closest(".marcacao");
      const posicao = [...item.parentElement.children].indexOf(item);
      campo.marcacoes.splice(posicao, 1);
      desenharMarcacoes(campo);
      entrada.focus();
    });
    // O texto digitado e ainda sem ENTER também é gravado ao salvar.
    antesDeEnviar(campo.closest("form"), () => adicionarMarcacao(campo), { capture: true });
  });

  const TITULOS_DA_TAREFA = {
    generalista: { nova: "Novo cartão generalista", editar: "Editar cartão generalista", ver: "Cartão generalista" },
    atividade: { nova: "Nova demanda", editar: "Editar demanda", ver: "Demanda" },
    lista_de_tarefas: { nova: "Nova lista de tarefas", editar: "Editar lista de tarefas", ver: "Lista de tarefas" },
  };

  // As seções de cada tipo de cartão. No generalista, são as que o usuário acrescentou.
  const SECOES_DO_TIPO = {
    atividade: ["arquivos", "descricao"],
    lista_de_tarefas: ["arquivos", "tarefas"],
  };
  const ORDEM_DAS_SECOES = ["arquivos", "descricao", "tarefas", "video"];
  let tipoDoDialogo = "atividade";
  let secoesDoDialogo = [];
  // No generalista, as seções da coluna direita ficam em abas; esta é a que está à mostra.
  const SECOES_EM_ABAS = ["descricao", "tarefas", "video"];
  let abaDoDialogo = null;

  function linhaVaziaNasTarefas() {
    const lista = document.getElementById("tarefa-itens");
    // Uma linha vazia já pronta para digitar; tarefas sem texto não são gravadas.
    if (!lista.children.length) {
      lista.append(criarItem({}));
    }
  }

  // Mostra só as seções do cartão e, no generalista, os botões de acrescentar e de retirar.
  function atualizarSecoes() {
    const dialogo = document.getElementById("dialogo-tarefa");
    const generalista = tipoDoDialogo === "generalista";
    const somenteLeitura = dialogo.classList.contains("dialogo-somente-leitura");
    const comArquivos = document.getElementById("tarefa-anexos").children.length > 0;
    const retirarArquivos = dialogo.querySelector('[data-remover-secao="arquivos"]');

    dialogo.querySelectorAll("[data-secao]").forEach((secao) => {
      secao.hidden = !secoesDoDialogo.includes(secao.dataset.secao);
    });
    dialogo.querySelectorAll("[data-adicionar-secao]").forEach((botao) => {
      botao.hidden = secoesDoDialogo.includes(botao.dataset.adicionarSecao);
    });
    dialogo.querySelector("[data-adicionar-secoes]").hidden =
      !generalista || somenteLeitura || secoesDoDialogo.length === ORDEM_DAS_SECOES.length;
    dialogo.querySelectorAll("[data-remover-secao]").forEach((botao) => {
      botao.hidden = !generalista || somenteLeitura;
    });
    // Os arquivos já enviados são excluídos um a um: com eles, a seção fica.
    retirarArquivos.disabled = comArquivos || somenteLeitura;
    retirarArquivos.dataset.dica = comArquivos ? "Exclua os arquivos para retirá-los do cartão" : "Retirar Arquivos do cartão";
    dialogo.classList.toggle("tarefa-generalista", generalista);
    dialogo.classList.toggle(
      "tarefa-sem-coluna-direita",
      generalista && !secoesDoDialogo.some((secao) => secao !== "arquivos")
    );
    atualizarAbas(dialogo, generalista);
    document.getElementById("tarefa-secoes").value = JSON.stringify(generalista ? secoesDoDialogo : []);
  }

  function atualizarAbas(dialogo, generalista) {
    const emAbas = SECOES_EM_ABAS.filter((secao) => secoesDoDialogo.includes(secao));
    const comAbas = generalista && emAbas.length > 0;

    if (!emAbas.includes(abaDoDialogo)) {
      abaDoDialogo = emAbas[0] || null;
    }
    dialogo.classList.toggle("tarefa-com-abas", comAbas);
    dialogo.querySelector("[data-abas-da-tarefa]").hidden = !comAbas;
    dialogo.querySelectorAll("[data-aba]").forEach((aba) => {
      const selecionada = aba.dataset.aba === abaDoDialogo;
      aba.hidden = !emAbas.includes(aba.dataset.aba);
      aba.setAttribute("aria-selected", String(selecionada));
      aba.tabIndex = selecionada ? 0 : -1;
    });
    SECOES_EM_ABAS.forEach((secao) => {
      const painel = dialogo.querySelector('.tarefa-coluna-direita [data-secao="' + secao + '"]');
      if (comAbas) {
        painel.setAttribute("role", "tabpanel");
        painel.setAttribute("aria-labelledby", "aba-" + secao);
        painel.hidden = painel.hidden || secao !== abaDoDialogo;
      } else {
        painel.removeAttribute("role");
        painel.removeAttribute("aria-labelledby");
      }
    });
  }

  function escolherAba(secao) {
    const dialogo = document.getElementById("dialogo-tarefa");
    const player = document.getElementById("tarefa-video-player");

    // O vídeo não continua tocando na aba escondida: recarregar o player o interrompe.
    if (abaDoDialogo === "video" && secao !== "video" && player && player.src !== "about:blank") {
      player.src = player.src;
    }
    abaDoDialogo = secao;
    atualizarSecoes();
    dialogo.querySelector('[data-aba="' + secao + '"]').focus();
  }

  function preencherTipo(tipo, itens, secoes) {
    tipoDoDialogo = tipo;
    abaDoDialogo = null;
    secoesDoDialogo = tipo === "generalista" ? ORDEM_DAS_SECOES.filter((secao) => secoes.includes(secao)) : SECOES_DO_TIPO[tipo].slice();
    document.getElementById("tarefa-tipo").value = tipo;
    document.getElementById("tarefa-itens").replaceChildren(...itens.map(criarItem));
    if (secoesDoDialogo.includes("tarefas")) {
      linhaVaziaNasTarefas();
    }
    atualizarSecoes();
  }

  function acrescentarSecao(secao) {
    const dialogo = document.getElementById("dialogo-tarefa");

    secoesDoDialogo = ORDEM_DAS_SECOES.filter((outra) => outra === secao || secoesDoDialogo.includes(outra));
    if (SECOES_EM_ABAS.includes(secao)) {
      abaDoDialogo = secao;
    }
    if (secao === "tarefas") {
      linhaVaziaNasTarefas();
    }
    atualizarSecoes();
    const primeiro = dialogo.querySelector('[data-secao="' + secao + '"]').querySelector(
      secao === "descricao" ? "#tarefa-editor" : "input:not([type=hidden]):not([type=file]), .anexar"
    );
    if (primeiro) {
      primeiro.focus();
    }
  }

  // O conteúdo da seção retirada continua na caixa até fechá-la, mas não é gravado.
  function retirarSecao(secao) {
    secoesDoDialogo = secoesDoDialogo.filter((outra) => outra !== secao);
    if (secao === "arquivos") {
      document.getElementById("tarefa-arquivos").value = "";
      document.getElementById("tarefa-arquivos-escolhidos").textContent = "";
    } else if (secao === "video") {
      preencherVideoDoCartao({});
    }
    atualizarSecoes();
  }

  const dialogoDaTarefaComSecoes = document.getElementById("dialogo-tarefa");

  if (dialogoDaTarefaComSecoes) {
    dialogoDaTarefaComSecoes.addEventListener("click", (evento) => {
      const acrescentar = evento.target.closest("[data-adicionar-secao]");
      const retirar = evento.target.closest("[data-remover-secao]");
      const aba = evento.target.closest("[data-aba]");

      if (aba) {
        escolherAba(aba.dataset.aba);
      } else if (acrescentar) {
        acrescentarSecao(acrescentar.dataset.adicionarSecao);
      } else if (retirar && !retirar.disabled) {
        retirarSecao(retirar.dataset.removerSecao);
      }
    });
  }

  // As setas, o Home e o End passam de uma aba para outra, como nas abas do sistema.
  if (dialogoDaTarefaComSecoes) {
    dialogoDaTarefaComSecoes.querySelector("[data-abas-da-tarefa]").addEventListener("keydown", (evento) => {
      const abas = Array.from(dialogoDaTarefaComSecoes.querySelectorAll("[data-aba]:not([hidden])"));
      const atual = abas.indexOf(evento.target.closest("[data-aba]"));
      const destinos = { ArrowRight: atual + 1, ArrowLeft: atual - 1, Home: 0, End: abas.length - 1 };

      if (atual < 0 || !(evento.key in destinos)) {
        return;
      }
      evento.preventDefault();
      escolherAba(abas[(destinos[evento.key] + abas.length) % abas.length].dataset.aba);
    });
  }

  // Vídeo do cartão generalista: os dados do YouTube ou do Vimeo e o player, só para conferir antes de salvar.
  function mostrarDadosDoVideo(dados) {
    const area = document.querySelector("[data-video-dados]");
    const temVideo = Boolean(dados && dados.titulo);

    area.hidden = !temVideo;
    area.querySelectorAll("[data-video-dado]").forEach((campo) => {
      const valor = temVideo ? dados[campo.dataset.videoDado] || "" : "";
      campo.textContent = valor ? (campo.dataset.rotulo || "") + valor : "";
      campo.hidden = !valor;
    });
    document.getElementById("tarefa-video-player").src = temVideo && dados.player ? dados.player : "about:blank";
  }

  function preencherVideoDoCartao(valores) {
    if (!document.getElementById("tarefa-video-endereco")) {
      return;
    }
    document.getElementById("tarefa-video-endereco").value = valores.videoEndereco || "";
    document.getElementById("tarefa-video-atualizar").value = "";
    mostrarDadosDoVideo(
      valores.videoTitulo
        ? {
            titulo: valores.videoTitulo,
            autor: valores.videoAutor,
            publicacao: valores.videoPublicacao,
            duracao: valores.videoDuracao,
            player: valores.videoPlayer,
          }
        : null
    );
  }

  const receberVideo = document.querySelector("[data-receber-video]");

  if (receberVideo) {
    const campoDoEndereco = document.getElementById("tarefa-video-endereco");

    receberVideo.addEventListener("click", async () => {
      const endereco = campoDoEndereco.value.trim();
      let resposta;
      let dados = {};

      if (!endereco) {
        notificarErro("Informe o endereço de um vídeo do YouTube ou do Vimeo.");
        campoDoEndereco.focus();
        return;
      }
      receberVideo.disabled = true;
      receberVideo.textContent = "Recebendo...";
      try {
        resposta = await fetch(receberVideo.closest("[data-url-previa]").dataset.urlPrevia, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
          body: JSON.stringify({ endereco }),
        });
        dados = await resposta.json().catch(() => ({}));
      } catch (erro) {
        resposta = null;
      }
      receberVideo.disabled = false;
      receberVideo.textContent = "Receber Informações";

      if (!resposta) {
        notificarErro("Não foi possível conectar ao servidor. Verifique a conexão e tente novamente.");
        return;
      }
      if (!resposta.ok) {
        notificarErro(dados.erro || "Não foi possível buscar as informações do vídeo. Tente novamente.");
        return;
      }
      mostrarDadosDoVideo(dados);
      document.getElementById("tarefa-video-atualizar").value = "1";
    });

    // O ENTER no endereço busca o vídeo, em vez de salvar o cartão.
    campoDoEndereco.addEventListener("keydown", (evento) => {
      if (evento.key === "Enter" && !evento.isComposing) {
        evento.preventDefault();
        receberVideo.click();
      }
    });

    // Um endereço novo ainda não conferido: os dados antigos saem da tela.
    campoDoEndereco.addEventListener("input", () => {
      mostrarDadosDoVideo(null);
    });

    // O vídeo não continua tocando com a caixa fechada.
    campoDoEndereco.closest("dialog").addEventListener("close", () => {
      document.getElementById("tarefa-video-player").src = "about:blank";
    });
  }

  function marcarItem(marcador, concluido) {
    const texto = marcador.parentElement.querySelector(".item-texto");
    const nome = texto.value === undefined ? texto.textContent : texto.value;

    marcador.setAttribute("aria-pressed", String(concluido));
    marcador.parentElement.classList.toggle("item-concluido", concluido);
    marcador.setAttribute("aria-label", (concluido ? "Desmarcar" : "Marcar") + " a tarefa " + nome);
  }

  function criarItem(item) {
    const linha = document.getElementById("modelo-item").content.firstElementChild.cloneNode(true);

    linha.querySelector(".item-texto").value = item.texto || "";
    marcarItem(linha.querySelector(".item-marcador"), Boolean(item.concluido));
    return linha;
  }

  function adicionarItem(depoisDe) {
    const linha = criarItem({});

    if (depoisDe) {
      depoisDe.after(linha);
    } else {
      document.getElementById("tarefa-itens").append(linha);
    }
    linha.querySelector(".item-texto").focus();
  }

  const itensDaTarefa = document.getElementById("tarefa-itens");

  if (itensDaTarefa) {
    document.querySelector("[data-adicionar-item]").addEventListener("click", () => adicionarItem());

    // A nova ordem é gravada ao salvar, como a do arrasto.
    document.querySelector("[data-ordenar-itens]").addEventListener("click", () => {
      const textoDe = (linha) => linha.querySelector(".item-texto").value.trim();
      const linhas = Array.from(itensDaTarefa.children).sort((uma, outra) =>
        textoDe(uma).localeCompare(textoDe(outra), "pt-BR", { sensitivity: "base", numeric: true })
      );

      itensDaTarefa.append(...linhas);
    });

    itensDaTarefa.addEventListener("click", (evento) => {
      const marcador = evento.target.closest(".item-marcador");
      const remover = evento.target.closest("[data-remover-item]");

      if (marcador) {
        marcarItem(marcador, marcador.getAttribute("aria-pressed") !== "true");
      } else if (remover) {
        remover.closest("li").remove();
      }
    });

    // Enter cria a próxima tarefa, e Backspace em uma tarefa vazia a remove.
    itensDaTarefa.addEventListener("keydown", (evento) => {
      const campo = evento.target.closest(".item-texto");

      if (!campo) {
        return;
      }
      if (evento.key === "Enter") {
        evento.preventDefault();
        adicionarItem(campo.closest("li"));
      } else if (evento.key === "Backspace" && !campo.value) {
        const linha = campo.closest("li");
        const anterior = linha.previousElementSibling;

        evento.preventDefault();
        linha.remove();
        if (anterior) {
          anterior.querySelector(".item-texto").focus();
        }
      }
    });

    // Arrastar uma tarefa muda a ordem. Com o mouse, vale a linha inteira, inclusive o texto,
    // quando o movimento é vertical; no toque, só a alça, para a lista continuar rolando.
    const DISTANCIA_PARA_ARRASTAR = 6;
    const MARGEM_DE_ROLAGEM_DOS_ITENS = 30;
    let arrastoDoItem = null;

    itensDaTarefa.addEventListener("pointerdown", (evento) => {
      const linha = evento.target.closest(".item-da-lista");

      if (
        !linha ||
        evento.button !== 0 ||
        evento.target.closest(".item-marcador, [data-remover-item]") ||
        itensDaTarefa.closest(".dialogo-somente-leitura")
      ) {
        return;
      }
      if (evento.pointerType !== "mouse" && !evento.target.closest(".item-alca")) {
        return;
      }
      arrastoDoItem = { linha, inicioX: evento.clientX, inicioY: evento.clientY, ativo: false };
    });

    document.addEventListener("pointermove", (evento) => {
      if (!arrastoDoItem) {
        return;
      }
      const deslocamentoX = evento.clientX - arrastoDoItem.inicioX;
      const deslocamentoY = evento.clientY - arrastoDoItem.inicioY;

      if (!arrastoDoItem.ativo) {
        if (Math.hypot(deslocamentoX, deslocamentoY) < DISTANCIA_PARA_ARRASTAR) {
          return;
        }
        // No texto, um movimento horizontal continua selecionando as letras.
        if (Math.abs(deslocamentoY) < Math.abs(deslocamentoX)) {
          arrastoDoItem = null;
          return;
        }
        arrastoDoItem.ativo = true;
        arrastoDoItem.linha.classList.add("item-arrastando");
        document.body.classList.add("arrastando");
        document.activeElement.blur();
        document.getSelection().removeAllRanges();
      }

      const caixa = itensDaTarefa.getBoundingClientRect();
      if (evento.clientY < caixa.top + MARGEM_DE_ROLAGEM_DOS_ITENS) {
        itensDaTarefa.scrollTop -= 10;
      } else if (evento.clientY > caixa.bottom - MARGEM_DE_ROLAGEM_DOS_ITENS) {
        itensDaTarefa.scrollTop += 10;
      }

      const seguinte = Array.from(itensDaTarefa.children).find((outra) => {
        const posicao = outra.getBoundingClientRect();
        return outra !== arrastoDoItem.linha && evento.clientY < posicao.top + posicao.height / 2;
      });
      itensDaTarefa.insertBefore(arrastoDoItem.linha, seguinte || null);
    });

    function encerrarArrastoDoItem() {
      if (arrastoDoItem && arrastoDoItem.ativo) {
        arrastoDoItem.linha.classList.remove("item-arrastando");
        document.body.classList.remove("arrastando");
      }
      arrastoDoItem = null;
    }

    document.addEventListener("pointerup", encerrarArrastoDoItem);
    document.addEventListener("pointercancel", encerrarArrastoDoItem);

    antesDeEnviar(itensDaTarefa.closest("form"), () => {
      const itens = Array.from(itensDaTarefa.children).map((linha) => ({
        texto: linha.querySelector(".item-texto").value,
        concluido: linha.querySelector(".item-marcador").getAttribute("aria-pressed") === "true",
      }));

      document.getElementById("tarefa-itens-dados").value = JSON.stringify(itens);
    });
  }

  function preencherAnexos(cartao) {
    const entrada = document.getElementById("tarefa-arquivos");
    const modelo = document.getElementById("modelo-anexo");
    const anexos = cartao ? Array.from(cartao.querySelectorAll("[data-anexo]")) : [];

    document.getElementById("tarefa-anexos").replaceChildren(
      ...anexos.map((anexo) => {
        const linha = modelo.content.cloneNode(true);
        const link = linha.querySelector("[data-anexo-link]");
        const renomear = linha.querySelector("[data-renomear-anexo]");
        const excluir = linha.querySelector("[data-excluir]");

        link.href = anexo.dataset.urlBaixar;
        link.textContent = anexo.dataset.nome;
        linha.querySelector("[data-anexo-tamanho]").textContent = anexo.dataset.tamanho;
        renomear.dataset.url = anexo.dataset.urlRenomear;
        renomear.dataset.nome = anexo.dataset.nome;
        renomear.setAttribute("aria-label", "Alterar nome de " + anexo.dataset.nome);
        excluir.dataset.urlExcluir = anexo.dataset.urlExcluir;
        excluir.setAttribute("aria-label", "Excluir " + anexo.dataset.nome);
        // Na categoria compartilhada, só o dono exclui os arquivos.
        if (permissaoDoQuadro !== "dono") {
          excluir.remove();
        }
        return linha;
      })
    );

    entrada.value = "";
    entrada.dataset.vagas = Number(entrada.dataset.limite) - anexos.length;
    document.getElementById("tarefa-arquivos-escolhidos").textContent = "";
    document.getElementById("tarefa-anexar").hidden = Number(entrada.dataset.vagas) <= 0;
  }

  const entradaDeArquivos = document.getElementById("tarefa-arquivos");

  if (entradaDeArquivos) {
    entradaDeArquivos.addEventListener("change", () => {
      const arquivos = Array.from(entradaDeArquivos.files);
      const { limite, tamanhoMaximo, vagas, espaco, espacoUsado } = entradaDeArquivos.dataset;
      const tamanhoTotal = arquivos.reduce((soma, arquivo) => soma + arquivo.size, 0);
      const escolhidos = document.getElementById("tarefa-arquivos-escolhidos");
      let erro = "";

      if (arquivos.length > Number(vagas)) {
        erro = "Cada demanda pode ter até " + limite + " arquivos.";
      } else if (arquivos.some((arquivo) => arquivo.size > Number(tamanhoMaximo))) {
        erro = "Cada arquivo pode ter até " + Number(tamanhoMaximo) / (1024 * 1024) + " MB.";
      } else if (Number(espacoUsado) + tamanhoTotal > Number(espaco)) {
        erro = "Os anexos não cabem no seu espaço de " + Number(espaco) / (1024 * 1024) + " MB.";
      }

      if (erro) {
        entradaDeArquivos.value = "";
        escolhidos.textContent = "";
        notificarErro(erro);
      } else {
        escolhidos.textContent = arquivos.map((arquivo) => arquivo.name).join(", ");
      }
    });
  }

  function preencherCategoria(valores) {
    document.getElementById("categoria-nome").value = valores.nome || "";
    document.querySelectorAll('#dialogo-categoria input[name="icone"]').forEach((opcao) => {
      opcao.checked = opcao.value === valores.icone;
    });
    const fundo = valores.fundo || "padrao";
    document.querySelectorAll('#dialogo-categoria input[name="fundo"]').forEach((opcao) => {
      opcao.checked = opcao.value === fundo;
    });
  }

  // Quem só visualiza a categoria compartilhada vê a demanda sem poder alterá-la.
  function definirSomenteLeitura(ligado) {
    const dialogo = document.getElementById("dialogo-tarefa");

    dialogo.classList.toggle("dialogo-somente-leitura", ligado);
    dialogo.querySelectorAll("form input, form select, form textarea, form button:not([data-fechar]):not([data-abrir-historico])").forEach((campo) => {
      campo.disabled = ligado;
    });
    document.getElementById("tarefa-editor").contentEditable = String(!ligado);
    dialogo.querySelector(".dialogo-acoes [data-fechar]").textContent = ligado ? "Fechar" : "Cancelar";
  }

  const ENDERECO_NO_TEXTO = /https?:\/\/[^\s<>"]+/g;
  const PONTUACAO_NO_FIM = /[.,;:!?)\]}'"]+$/;

  // O texto entra como texto, nunca como HTML: só os endereços http e https viram links.
  function preencherComLinks(elemento, texto) {
    let inicio = 0;

    elemento.replaceChildren();
    for (const achado of texto.matchAll(ENDERECO_NO_TEXTO)) {
      const endereco = achado[0].replace(PONTUACAO_NO_FIM, "");
      const link = document.createElement("a");

      elemento.append(texto.slice(inicio, achado.index));
      link.href = endereco;
      link.textContent = endereco;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      elemento.append(link);
      inicio = achado.index + endereco.length;
    }
    elemento.append(texto.slice(inicio));
  }

  // Os dados lidos do YouTube ou do Vimeo, na caixa do vídeo: ao abrir e depois de Atualizar as informações.
  function preencherDadosDoVideo(dados) {
    document.getElementById("video-autor").value = dados.videoAutor || "";
    document.getElementById("video-titulo").value = dados.videoTitulo || "";
    preencherComLinks(document.getElementById("video-descricao"), dados.videoDescricao || "");
    document.getElementById("video-publicacao").value = dados.videoPublicacao || "";
    document.getElementById("video-duracao").value = dados.videoDuracao || "";
  }

  let videoAberto = null;
  let videoAtualizado = false;

  // O vídeo tem a própria caixa: à esquerda os dados do YouTube ou do Vimeo, à direita o player.
  function abrirVideo(cartao) {
    const dialogo = document.getElementById("dialogo-video");
    const somenteLeitura = permissaoDoQuadro === "visualizar";
    const dados = cartao.dataset;

    videoAberto = cartao;
    videoAtualizado = false;
    preencherDadosDoVideo(dados);
    document.getElementById("video-informacoes").value = dados.videoInformacoes || "";
    document.getElementById("video-informacoes").readOnly = somenteLeitura;
    preencherMarcacoes(dialogo.querySelector("[data-marcacoes-campo]"), JSON.parse(dados.marcacoes || "[]"));
    dialogo.querySelector("[data-marcacoes-entrada]").disabled = somenteLeitura;
    document.getElementById("video-player").src = dados.videoPlayer;
    dialogo.classList.toggle("dialogo-somente-leitura", somenteLeitura);
    dialogo.querySelector(".dialogo-acoes [data-fechar]").textContent = somenteLeitura ? "Fechar" : "Cancelar";
    const plataforma = dados.videoPlataforma || "YouTube";

    abrirDialogo("dialogo-video", (somenteLeitura ? "Vídeo do " : "Editar vídeo do ") + plataforma, dados.url);
  }

  const dialogoDoVideo = document.getElementById("dialogo-video");

  if (dialogoDoVideo) {
    // Fechar a caixa para o vídeo, que continuaria tocando sem aparecer.
    dialogoDoVideo.addEventListener("close", () => {
      document.getElementById("video-player").src = "about:blank";
      // O cartão mostra o título, o autor e a duração: depois de atualizados, o quadro é trocado.
      if (videoAtualizado) {
        videoAtualizado = false;
        trocarQuadro(false);
      }
    });

    // Busca de novo no YouTube ou no Vimeo; as Informações Adicionais e as marcações digitadas continuam na caixa.
    dialogoDoVideo.querySelector("[data-atualizar-video]").addEventListener("click", async (evento) => {
      const botao = evento.currentTarget;
      const cartao = videoAberto;
      let resposta;
      let dados = {};

      if (!cartao || !cartao.dataset.videoUrlAtualizar) {
        return;
      }
      botao.disabled = true;
      botao.textContent = "Atualizando...";
      try {
        resposta = await fetch(cartao.dataset.videoUrlAtualizar, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken, "X-Requested-With": "fetch" },
        });
        dados = await resposta.json().catch(() => ({}));
      } catch (erro) {
        resposta = null;
      }
      botao.disabled = false;
      botao.textContent = "Atualizar as informações";

      if (!resposta) {
        notificarErro("Não foi possível conectar ao servidor. Verifique a conexão e tente novamente.");
        return;
      }
      if (!resposta.ok) {
        notificarErro(dados.erro || "Não foi possível atualizar as informações do vídeo. Tente novamente.");
        return;
      }
      Object.assign(cartao.dataset, {
        videoAutor: dados.autor,
        videoTitulo: dados.titulo,
        videoDescricao: dados.descricao,
        videoPublicacao: dados.publicacao,
        videoDuracao: dados.duracao,
      });
      if (videoAberto === cartao) {
        preencherDadosDoVideo(cartao.dataset);
      }
      videoAtualizado = true;
    });
  }

  function abrirNovoVideo(projetoId) {
    const dialogo = document.getElementById("dialogo-video-novo");

    dialogo.querySelector("form").reset();
    document.getElementById("video-novo-projeto").value = projetoId;
    dialogo.querySelector("[data-receber-informacoes]").disabled = false;
    dialogo.showModal();
  }

  const formularioDoNovoVideo = document.querySelector("#dialogo-video-novo form");

  if (formularioDoNovoVideo) {
    formularioDoNovoVideo.addEventListener("submit", async (evento) => {
      const botao = formularioDoNovoVideo.querySelector("[data-receber-informacoes]");
      let resposta;
      let dados = {};

      evento.preventDefault();
      botao.disabled = true;
      botao.textContent = "Recebendo...";
      try {
        resposta = await fetch(formularioDoNovoVideo.dataset.url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
          body: JSON.stringify({
            projeto_id: Number(document.getElementById("video-novo-projeto").value),
            endereco: document.getElementById("video-novo-endereco").value,
          }),
        });
        dados = await resposta.json().catch(() => ({}));
      } catch (erro) {
        resposta = null;
      }
      botao.disabled = false;
      botao.textContent = "Receber Informações";

      if (!resposta) {
        notificarErro("Não foi possível conectar ao servidor. Verifique a conexão e tente novamente.");
        return;
      }
      if (!resposta.ok) {
        // A caixa continua aberta, com o endereço digitado, para o usuário corrigir.
        notificarErro(dados.erro || "Não foi possível criar o vídeo. Tente novamente.");
        return;
      }
      formularioDoNovoVideo.querySelectorAll("[data-video-campo]").forEach((campo) => {
        campo.value = dados[campo.dataset.videoCampo] || "";
      });
      // Gravado no banco: o quadro recarrega já com a tela de edição do vídeo aberta.
      const endereco = new URL(window.location.href);
      endereco.searchParams.set("tarefa", dados.id);
      window.location.assign(endereco);
    });
  }

  // Adicionar Responsável: mostra só as pessoas da categoria do cartão. As das outras categorias
  // ficam desligadas para não irem no formulário, porque todas usam o nome responsavel_id.
  function abrirResponsavel(botao) {
    const dialogo = document.getElementById("dialogo-responsavel");

    dialogo.querySelectorAll("[data-candidatos]").forEach((grupo) => {
      const daCategoria = grupo.dataset.candidatos === botao.dataset.categoria;
      grupo.hidden = !daCategoria;
      grupo.querySelectorAll("input").forEach((opcao) => {
        opcao.disabled = !daCategoria;
        opcao.checked = daCategoria && opcao.value === botao.dataset.responsavel;
      });
    });
    dialogo.querySelector("form").dataset.tarefaId = botao.closest(".tarefa").dataset.tarefaId;
    const titulo = botao.classList.contains("sem-responsavel") ? "Adicionar Responsável" : "Alterar Responsável";
    abrirDialogo("dialogo-responsavel", titulo, botao.dataset.url);
  }

  // O botão Histórico do diálogo só aparece no cartão já criado.
  function prepararHistorico(idDoDialogo, url) {
    const botao = document.querySelector("#" + idDoDialogo + " [data-abrir-historico]");
    if (botao) {
      botao.hidden = !url;
      botao.dataset.url = url || "";
    }
  }

  function editarTarefa(cartao) {
    prepararHistorico(cartao.dataset.tipo === "video" ? "dialogo-video" : "dialogo-tarefa", cartao.dataset.urlHistorico);
    if (cartao.dataset.tipo === "video") {
      abrirVideo(cartao);
      return;
    }
    const somenteLeitura = permissaoDoQuadro === "visualizar";
    const titulos = TITULOS_DA_TAREFA[cartao.dataset.tipo || "atividade"];

    preencherTarefa(cartao.dataset);
    preencherAnexos(cartao);
    definirSomenteLeitura(somenteLeitura);
    atualizarSecoes();
    document.getElementById("dialogo-tarefa").dataset.tarefaId = cartao.dataset.tarefaId;
    abrirDialogo("dialogo-tarefa", somenteLeitura ? titulos.ver : titulos.editar, cartao.dataset.url);
  }

  function preencherProjeto(valores) {
    document.getElementById("projeto-nome").value = valores.nome || "";
    const cores = Array.from(document.querySelectorAll('#dialogo-projeto input[name="cor"]'));
    (cores.find((cor) => cor.value === valores.cor) || cores[0]).checked = true;
    document.getElementById("projeto-categoria").value = valores.categoriaId || "";
    document.getElementById("projeto-concluido").checked = Boolean(valores.concluida);
  }

  let ignorarClique = false;

  document.addEventListener("click", (evento) => {
    const alvo = evento.target;
    let botao;

    if (ignorarClique) {
      return;
    }

    if ((botao = alvo.closest("[data-nova-tarefa]"))) {
      const tipo = botao.dataset.tipo || "atividade";

      fecharMenus();
      prepararHistorico("dialogo-tarefa", null);
      preencherTarefa({ projetoId: botao.dataset.projetoId, tipo });
      preencherAnexos();
      definirSomenteLeitura(false);
      atualizarSecoes();
      delete document.getElementById("dialogo-tarefa").dataset.tarefaId;
      protegerCamposDaTarefa();
      abrirDialogo("dialogo-tarefa", TITULOS_DA_TAREFA[tipo].nova);
    } else if ((botao = alvo.closest("[data-novo-video]"))) {
      fecharMenus();
      abrirNovoVideo(botao.dataset.projetoId);
    } else if ((botao = alvo.closest("[data-novo-projeto]"))) {
      preencherProjeto({ categoriaId: botao.dataset.categoriaId });
      abrirDialogo("dialogo-projeto", "Novo projeto");
    } else if ((botao = alvo.closest("[data-editar-projeto]"))) {
      preencherProjeto(botao.dataset);
      abrirDialogo("dialogo-projeto", "Editar projeto", botao.dataset.url);
    } else if ((botao = alvo.closest("[data-nova-categoria]"))) {
      preencherCategoria({});
      abrirDialogo("dialogo-categoria", "Nova categoria");
    } else if ((botao = alvo.closest("[data-editar-categoria]"))) {
      preencherCategoria(botao.dataset);
      abrirDialogo("dialogo-categoria", "Editar categoria", botao.dataset.url);
    } else if ((botao = alvo.closest("[data-renomear-anexo]"))) {
      document.getElementById("anexo-nome").value = botao.dataset.nome;
      abrirDialogo("dialogo-anexo", "Alterar nome do arquivo", botao.dataset.url);
    } else if ((botao = alvo.closest("[data-fechar]"))) {
      botao.closest("dialog").close();
    } else if ((botao = alvo.closest("[data-excluir]"))) {
      const confirmacao = document.getElementById("confirmacao");
      const formularioDaConfirmacao = confirmacao.querySelector("form");
      formularioDaConfirmacao.action = botao.dataset.urlExcluir;
      // O arquivo excluído de dentro do cartão aberto não tira o usuário do cartão.
      formularioDaConfirmacao.dataset.excluirAnexo = botao.closest("#dialogo-tarefa") ? "1" : "";
      confirmacao.showModal();
    } else if ((botao = alvo.closest("[data-escolher-responsavel]"))) {
      abrirResponsavel(botao);
    } else if (alvo.closest(".tarefa") && !alvo.closest(".tarefa-alca, .tarefa-acoes, .tarefa-anexos, .tarefa-descricao a, .tarefa-itens, .tarefa-pessoas")) {
      // O clique nas tarefas de uma lista de tarefas não abre o diálogo: nelas, só o marcador age.
      editarTarefa(alvo.closest(".tarefa"));
    }
  });

  // Os links da descrição sempre abrem em outra aba. Durante a edição, o clique só posiciona o cursor.
  document.addEventListener("click", (evento) => {
    const link = evento.target.closest(".texto-formatado a[href]");

    if (link && !link.isContentEditable) {
      evento.preventDefault();
      window.open(link.href, "_blank", "noopener");
    }
  });

  // Máscara (00) 00000-0000: só os dígitos ficam, e a pontuação é refeita a cada digitação.
  function mascararTelefone(valor) {
    const digitos = valor.replace(/\D/g, "").slice(0, 11);

    if (digitos.length <= 2) {
      return digitos.length ? "(" + digitos : "";
    }
    const ddd = "(" + digitos.slice(0, 2) + ") ";
    const resto = digitos.slice(2);
    return resto.length <= 4 ? ddd + resto : ddd + resto.slice(0, resto.length - 4) + "-" + resto.slice(-4);
  }

  document.querySelectorAll("[data-mascara-telefone]").forEach((campo) => {
    campo.value = mascararTelefone(campo.value);
    campo.addEventListener("input", () => {
      campo.value = mascararTelefone(campo.value);
    });
  });

  // Uma nova imagem troca o desafio no servidor: o código digitado da anterior deixa de valer.
  document.querySelectorAll("[data-captcha-trocar]").forEach((botao) => {
    const imagem = botao.closest(".captcha").querySelector("[data-captcha-imagem]");
    const campo = document.getElementById("captcha");

    botao.addEventListener("click", () => {
      imagem.src = imagem.src.split("?")[0] + "?t=" + Date.now();
      if (campo) {
        campo.value = "";
        campo.focus();
      }
    });
  });

  function exibirSenha(campo, botao, visivel) {
    const rotulo = visivel ? "Ocultar senha" : "Mostrar senha";

    campo.type = visivel ? "text" : "password";
    botao.setAttribute("aria-pressed", String(visivel));
    botao.setAttribute("aria-label", rotulo);
    botao.dataset.dica = rotulo;
    botao.querySelector("[data-senha-oculta]").hidden = visivel;
    botao.querySelector("[data-senha-visivel]").hidden = !visivel;
  }

  const modeloVerSenha = document.getElementById("modelo-ver-senha");

  if (modeloVerSenha) {
    document.querySelectorAll('input[type="password"]').forEach((campo) => {
      const grupo = document.createElement("span");

      grupo.className = "campo-senha";
      campo.before(grupo);
      grupo.append(campo, modeloVerSenha.content.cloneNode(true));

      const botao = grupo.querySelector("button");

      botao.addEventListener("click", () => {
        exibirSenha(campo, botao, campo.type === "password");
        campo.focus();
      });
      // Volta a ser campo de senha antes do envio, para o navegador não a guardar como texto.
      campo.form.addEventListener("submit", () => exibirSenha(campo, botao, false));
    });
  }

  const editor = document.getElementById("tarefa-editor");

  if (editor) {
    const COMANDOS_COM_ESTADO = [
      "bold",
      "italic",
      "underline",
      "insertUnorderedList",
      "insertOrderedList",
    ];
    const TAMANHO_PADRAO_DA_FONTE = 3;
    const TAMANHO_MAXIMO_DA_FONTE = 7;
    const barra = document.querySelector(".editor-barra");
    const entradaDeImagem = document.getElementById("editor-imagem");
    const entradaDeCor = document.getElementById("editor-cor");
    const dialogoDeLink = document.getElementById("dialogo-link");
    const campoDeLink = document.getElementById("link-endereco");
    const campoDaDescricao = editor.closest(".tarefa-campo-descricao");
    const dialogoDaTarefa = editor.closest("dialog");
    const botaoDeTelaInteira = barra.querySelector('[data-editor="tela-inteira"]');
    const botaoDeVisualizar = barra.querySelector('[data-editor="visualizar"]');
    let selecao = null;

    function alternarBotao(botao, ligado, rotuloLigado, rotuloDesligado) {
      const rotulo = ligado ? rotuloLigado : rotuloDesligado;

      botao.setAttribute("aria-pressed", String(ligado));
      botao.setAttribute("aria-label", rotulo);
      botao.dataset.dica = rotulo;
      botao.querySelector("[data-icone-desligado]").hidden = ligado;
      botao.querySelector("[data-icone-ligado]").hidden = !ligado;
    }

    // Só leitura: os links ficam clicáveis e os botões de formatação são desligados.
    function alternarVisualizacao(ligada) {
      campoDaDescricao.classList.toggle("editor-visualizando", ligada);
      editor.contentEditable = String(!ligada);
      barra.querySelectorAll("button, input").forEach((controle) => {
        if (controle !== botaoDeVisualizar && controle !== botaoDeTelaInteira) {
          controle.disabled = ligada;
        }
      });
      alternarBotao(botaoDeVisualizar, ligada, "Voltar à edição", "Apenas visualizar a descrição");
    }

    function alternarTelaInteira(ligada) {
      campoDaDescricao.classList.toggle("editor-tela-inteira", ligada);
      alternarBotao(botaoDeTelaInteira, ligada, "Sair da tela inteira", "Editar em tela inteira");
    }

    // Em tela inteira, o Esc só volta ao diálogo: a demanda continua aberta.
    dialogoDaTarefa.addEventListener("cancel", (evento) => {
      if (campoDaDescricao.classList.contains("editor-tela-inteira")) {
        evento.preventDefault();
        alternarTelaInteira(false);
      }
    });

    dialogoDaTarefa.addEventListener("close", () => {
      alternarTelaInteira(false);
      alternarVisualizacao(false);
    });

    function atualizarBarra() {
      COMANDOS_COM_ESTADO.forEach((comando) => {
        const ativo = document.queryCommandState(comando);
        const botao = barra.querySelector('[data-editor="' + comando + '"]');

        botao.classList.toggle("editor-ativo", ativo);
        botao.setAttribute("aria-pressed", String(ativo));
      });
    }

    // Os diálogos e o seletor de cor tiram o foco do texto: a seleção precisa voltar antes do comando.
    function restaurarSelecao() {
      editor.focus();
      if (selecao && editor.contains(selecao.commonAncestorContainer)) {
        const atual = document.getSelection();

        atual.removeAllRanges();
        atual.addRange(selecao);
      }
    }

    function executar(comando, valor) {
      restaurarSelecao();
      document.execCommand("styleWithCSS", false, false);
      document.execCommand(comando, false, valor);
      atualizarBarra();
    }

    function alterarFonte(passo) {
      restaurarSelecao();
      const atual = Number(document.queryCommandValue("fontSize")) || TAMANHO_PADRAO_DA_FONTE;
      const tamanho = Math.min(TAMANHO_MAXIMO_DA_FONTE, Math.max(1, atual + passo));

      executar("fontSize", String(tamanho));
    }

    async function inserirImagem(arquivo) {
      const tamanhoMaximo = Number(editor.dataset.tamanhoMaximo);
      const dados = new FormData();

      if (arquivo.size > tamanhoMaximo) {
        notificarErro("Cada imagem pode ter até " + tamanhoMaximo / (1024 * 1024) + " MB.");
        return;
      }

      dados.append("imagem", arquivo);
      try {
        const resposta = await fetch(editor.dataset.urlImagem, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken },
          body: dados,
        });
        const resultado = await resposta.json();

        if (resposta.ok) {
          executar("insertImage", resultado.url);
        } else {
          notificarErro(resultado.erro);
        }
      } catch (erro) {
        notificarErro("Não foi possível enviar a imagem. Tente novamente.");
      }
    }

    function inserirLink(endereco) {
      const url = /^[a-z][a-z0-9+.-]*:/i.test(endereco) ? endereco : "https://" + endereco;

      restaurarSelecao();
      if (document.getSelection().isCollapsed) {
        const link = document.createElement("a");

        link.href = url;
        link.textContent = endereco;
        executar("insertHTML", link.outerHTML);
      } else {
        executar("createLink", url);
      }
    }

    document.addEventListener("selectionchange", () => {
      const atual = document.getSelection();

      if (atual.rangeCount && editor.contains(atual.anchorNode)) {
        selecao = atual.getRangeAt(0).cloneRange();
        atualizarBarra();
      }
    });

    // Sem isto, clicar em um botão tira o foco do texto e desfaz a seleção.
    barra.addEventListener("mousedown", (evento) => {
      if (evento.target.closest("button")) {
        evento.preventDefault();
      }
    });

    barra.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-editor]");

      if (!botao) {
        return;
      }
      const comando = botao.dataset.editor;

      if (comando === "maior" || comando === "menor") {
        alterarFonte(comando === "maior" ? 1 : -1);
      } else if (comando === "imagem") {
        entradaDeImagem.click();
      } else if (comando === "link") {
        campoDeLink.value = "";
        dialogoDeLink.showModal();
      } else if (comando === "tela-inteira") {
        alternarTelaInteira(!campoDaDescricao.classList.contains("editor-tela-inteira"));
        editor.focus();
      } else if (comando === "visualizar") {
        alternarVisualizacao(!campoDaDescricao.classList.contains("editor-visualizando"));
      } else {
        executar(comando);
      }
    });

    entradaDeImagem.addEventListener("change", () => {
      const [arquivo] = entradaDeImagem.files;

      if (arquivo) {
        inserirImagem(arquivo);
      }
      entradaDeImagem.value = "";
    });

    entradaDeCor.addEventListener("change", () => {
      barra.style.setProperty("--editor-cor", entradaDeCor.value);
      executar("foreColor", entradaDeCor.value);
    });

    dialogoDeLink.querySelector("form").addEventListener("submit", (evento) => {
      evento.preventDefault();
      dialogoDeLink.close();
      inserirLink(campoDeLink.value.trim());
    });

    editor.addEventListener("paste", (evento) => {
      const imagens = Array.from(evento.clipboardData.files).filter((arquivo) =>
        arquivo.type.startsWith("image/")
      );

      if (imagens.length) {
        evento.preventDefault();
        imagens.forEach(inserirImagem);
      }
    });

    antesDeEnviar(editor.closest("form"), () => {
      document.getElementById("tarefa-descricao").value = editor.innerHTML;
    });
  }

  const tarefaAberta = document.querySelector("[data-abrir-tarefa]");

  if (tarefaAberta) {
    const endereco = new URL(window.location.href);

    // Sem o parâmetro no endereço, recarregar a página não abre a demanda de novo.
    endereco.searchParams.delete("tarefa");
    window.history.replaceState(null, "", endereco);
    editarTarefa(tarefaAberta);
  }

  const CHAVE_LATERAL = "lateral-oculta";
  const painel = document.querySelector(".painel");

  function aplicarLateral(oculta) {
    const botao = painel.querySelector("[data-alternar-lateral]");
    const rotulo = oculta ? "Exibir categorias" : "Ocultar categorias";

    painel.classList.toggle("lateral-oculta", oculta);
    botao.setAttribute("aria-expanded", String(!oculta));
    botao.setAttribute("aria-label", rotulo);
    botao.dataset.dica = rotulo;
  }

  function lerLateralOculta() {
    try {
      return window.localStorage.getItem(CHAVE_LATERAL) === "sim";
    } catch (erro) {
      return false;
    }
  }

  function salvarLateralOculta(oculta) {
    try {
      window.localStorage.setItem(CHAVE_LATERAL, oculta ? "sim" : "nao");
    } catch (erro) {
      // Sem armazenamento, a preferência vale apenas até recarregar a página.
    }
  }

  if (painel) {
    aplicarLateral(lerLateralOculta());
    painel.querySelector("[data-alternar-lateral]").addEventListener("click", () => {
      const oculta = !painel.classList.contains("lateral-oculta");
      aplicarLateral(oculta);
      salvarLateralOculta(oculta);
    });
  }

  const quadro = document.getElementById("quadro");

  // Aplicativo instalável (PWA). A barra do sistema acompanha a cor do cabeçalho do tema.
  const corDaBarra = document.querySelector('meta[name="theme-color"]');
  function atualizarCorDaBarra() {
    const cor = getComputedStyle(document.documentElement).getPropertyValue("--cabecalho").trim();
    if (corDaBarra && cor) {
      corDaBarra.content = cor;
    }
  }
  atualizarCorDaBarra();

  // O service worker só funciona em HTTPS (ou localhost). Com um certificado autoassinado o
  // navegador recusa o registro, e o sistema segue funcionando, só sem o cache.
  if ("serviceWorker" in navigator && window.isSecureContext) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  }

  // "Instalar o aplicativo" aparece no menu do usuário só quando o navegador oferece a instalação
  // (Chrome e Edge); no iPhone, a instalação é pelo Compartilhar > Adicionar à Tela de Início.
  const botaoDeInstalar = document.querySelector("[data-instalar-app]");
  let pedidoDeInstalacao = null;
  window.addEventListener("beforeinstallprompt", (evento) => {
    evento.preventDefault();
    pedidoDeInstalacao = evento;
    if (botaoDeInstalar) {
      botaoDeInstalar.hidden = false;
    }
  });
  window.addEventListener("appinstalled", () => {
    pedidoDeInstalacao = null;
    if (botaoDeInstalar) {
      botaoDeInstalar.hidden = true;
    }
  });
  if (botaoDeInstalar) {
    botaoDeInstalar.addEventListener("click", () => {
      if (!pedidoDeInstalacao) {
        return;
      }
      // Cada pedido só pode ser usado uma vez; se a pessoa recusar, o navegador pode oferecer outro.
      const pedido = pedidoDeInstalacao;
      pedidoDeInstalacao = null;
      botaoDeInstalar.hidden = true;
      pedido.prompt();
    });
  }

  // Meu Perfil: a Cor da Aplicação muda a tela na hora; o Salvar grava e o Cancelar descarta.
  document.querySelectorAll("[data-escolher-tema]").forEach((opcao) => {
    opcao.addEventListener("change", () => {
      document.documentElement.dataset.tema = opcao.value;
      atualizarCorDaBarra();
    });
  });

  // ---------- Meu Perfil: Enviar minha foto e a caixa Ajustar minha imagem do perfil.
  // As medidas ficam em pixels da área de 400 x 400 (LADO_DA_AREA); na tela, a área pode ser
  // menor (celular e o zoom da página), e as posições são aplicadas em porcentagem. O círculo
  // tem 150 px de raio no centro: o recorte de 300 x 300 começa em (50, 50).
  const dialogoDaFoto = document.getElementById("dialogo-foto");

  if (dialogoDaFoto) {
    const LADO_DA_AREA = 400;
    const RAIO_DO_CIRCULO = 150;
    const ZOOM_MINIMO = 0.5;
    const ZOOM_MAXIMO = 4;
    const PASSO_DO_TECLADO = 10;
    const entradaDaFoto = document.querySelector("[data-arquivo-da-foto]");
    const areaDaFoto = dialogoDaFoto.querySelector("[data-foto-area]");
    const imagensDaFoto = dialogoDaFoto.querySelectorAll("[data-foto-imagem]");
    const faixaDoZoom = dialogoDaFoto.querySelector("[data-foto-zoom-faixa]");
    const botaoUtilizar = dialogoDaFoto.querySelector("[data-foto-utilizar]");
    const foto = { imagem: null, base: 1, zoom: 1, x: 0, y: 0 };
    let arrasto = null;

    function larguraDaFoto() {
      return foto.imagem.naturalWidth * foto.base * foto.zoom;
    }

    function alturaDaFoto() {
      return foto.imagem.naturalHeight * foto.base * foto.zoom;
    }

    function desenharFoto() {
      const porcento = (valor) => (valor / LADO_DA_AREA) * 100 + "%";
      imagensDaFoto.forEach((imagem) => {
        imagem.style.left = porcento(foto.x);
        imagem.style.top = porcento(foto.y);
        imagem.style.width = porcento(larguraDaFoto());
        imagem.style.height = porcento(alturaDaFoto());
      });
      faixaDoZoom.value = String(foto.zoom);
    }

    // O tamanho muda em torno do centro da área, onde fica o círculo.
    function mudarZoom(novo) {
      const zoom = Math.min(ZOOM_MAXIMO, Math.max(ZOOM_MINIMO, novo));
      const centro = LADO_DA_AREA / 2;
      const proporcao = zoom / foto.zoom;
      foto.x = centro - (centro - foto.x) * proporcao;
      foto.y = centro - (centro - foto.y) * proporcao;
      foto.zoom = zoom;
      desenharFoto();
    }

    function abrirAjusteDaFoto(endereco) {
      const imagem = new Image();
      imagem.onload = () => {
        // A imagem é redimensionada para caber inteira na área, centralizada.
        foto.imagem = imagem;
        foto.base = Math.min(LADO_DA_AREA / imagem.naturalWidth, LADO_DA_AREA / imagem.naturalHeight);
        foto.zoom = 1;
        foto.x = (LADO_DA_AREA - larguraDaFoto()) / 2;
        foto.y = (LADO_DA_AREA - alturaDaFoto()) / 2;
        imagensDaFoto.forEach((elemento) => {
          elemento.src = endereco;
        });
        desenharFoto();
        botaoUtilizar.disabled = false;
        dialogoDaFoto.showModal();
        areaDaFoto.focus();
      };
      imagem.onerror = () => notificarErro("Não foi possível abrir essa imagem. Escolha uma imagem PNG, JPEG, GIF ou WebP.");
      imagem.src = endereco;
    }

    document.querySelector("[data-enviar-foto]").addEventListener("click", () => {
      entradaDaFoto.value = "";
      entradaDaFoto.click();
    });

    // A imagem é lida como data: (a política de conteúdo não aceita blob:) e não vai ao servidor:
    // só o recorte de 300 x 300 é enviado.
    entradaDaFoto.addEventListener("change", () => {
      const arquivo = entradaDaFoto.files[0];
      if (!arquivo) {
        return;
      }
      if (!arquivo.type.startsWith("image/")) {
        notificarErro("Escolha um arquivo de imagem.");
        return;
      }
      const leitor = new FileReader();
      leitor.onload = () => abrirAjusteDaFoto(leitor.result);
      leitor.onerror = () => notificarErro("Não foi possível ler essa imagem.");
      leitor.readAsDataURL(arquivo);
    });

    // Pixels da tela para pixels da área de 400 (inclui o zoom da página e a área menor do celular).
    function escalaDaArea() {
      return areaDaFoto.getBoundingClientRect().width / LADO_DA_AREA;
    }

    areaDaFoto.addEventListener("pointerdown", (evento) => {
      if (!foto.imagem || evento.button !== 0) {
        return;
      }
      evento.preventDefault();
      areaDaFoto.setPointerCapture(evento.pointerId);
      areaDaFoto.focus();
      arrasto = { id: evento.pointerId, x: evento.clientX, y: evento.clientY, inicioX: foto.x, inicioY: foto.y };
      areaDaFoto.classList.add("foto-arrastando");
    });

    areaDaFoto.addEventListener("pointermove", (evento) => {
      if (!arrasto || evento.pointerId !== arrasto.id) {
        return;
      }
      const escala = escalaDaArea();
      foto.x = arrasto.inicioX + (evento.clientX - arrasto.x) / escala;
      foto.y = arrasto.inicioY + (evento.clientY - arrasto.y) / escala;
      desenharFoto();
    });

    function terminarArrasto(evento) {
      if (arrasto && evento.pointerId === arrasto.id) {
        arrasto = null;
        areaDaFoto.classList.remove("foto-arrastando");
      }
    }

    areaDaFoto.addEventListener("pointerup", terminarArrasto);
    areaDaFoto.addEventListener("pointercancel", terminarArrasto);

    areaDaFoto.addEventListener("wheel", (evento) => {
      if (!foto.imagem) {
        return;
      }
      evento.preventDefault();
      mudarZoom(foto.zoom * (evento.deltaY < 0 ? 1.1 : 1 / 1.1));
    }, { passive: false });

    areaDaFoto.addEventListener("keydown", (evento) => {
      const movimentos = {
        ArrowLeft: [-PASSO_DO_TECLADO, 0],
        ArrowRight: [PASSO_DO_TECLADO, 0],
        ArrowUp: [0, -PASSO_DO_TECLADO],
        ArrowDown: [0, PASSO_DO_TECLADO],
      };
      if (movimentos[evento.key]) {
        foto.x += movimentos[evento.key][0];
        foto.y += movimentos[evento.key][1];
        desenharFoto();
      } else if (evento.key === "+" || evento.key === "=") {
        mudarZoom(foto.zoom * 1.1);
      } else if (evento.key === "-") {
        mudarZoom(foto.zoom / 1.1);
      } else {
        return;
      }
      evento.preventDefault();
    });

    faixaDoZoom.addEventListener("input", () => mudarZoom(parseFloat(faixaDoZoom.value)));
    dialogoDaFoto.querySelectorAll("[data-foto-zoom]").forEach((botao) => {
      botao.addEventListener("click", () => {
        mudarZoom(foto.zoom * (botao.dataset.fotoZoom === "1" ? 1.1 : 1 / 1.1));
      });
    });

    dialogoDaFoto.querySelector("[data-foto-cancelar]").addEventListener("click", () => dialogoDaFoto.close());

    dialogoDaFoto.addEventListener("close", () => {
      arrasto = null;
      foto.imagem = null;
      imagensDaFoto.forEach((elemento) => elemento.removeAttribute("src"));
    });

    // O recorte: o círculo da área vira um PNG de 300 x 300, transparente fora dele.
    function recortarFoto() {
      const lado = RAIO_DO_CIRCULO * 2;
      const margem = LADO_DA_AREA / 2 - RAIO_DO_CIRCULO;
      const tela = document.createElement("canvas");
      tela.width = lado;
      tela.height = lado;
      const contexto = tela.getContext("2d");
      contexto.imageSmoothingQuality = "high";
      contexto.beginPath();
      contexto.arc(RAIO_DO_CIRCULO, RAIO_DO_CIRCULO, RAIO_DO_CIRCULO, 0, Math.PI * 2);
      contexto.clip();
      contexto.drawImage(foto.imagem, foto.x - margem, foto.y - margem, larguraDaFoto(), alturaDaFoto());
      return new Promise((resolver) => tela.toBlob(resolver, "image/png"));
    }

    // A foto nova passa a ser o primeiro ícone da lista, escolhido, e o do cabeçalho.
    function mostrarFotoNova(endereco) {
      const opcao = document.querySelector("[data-opcao-da-foto]");
      opcao.querySelector("img").src = endereco;
      opcao.hidden = false;
      opcao.querySelector("input").checked = true;
      const botaoDoUsuario = document.querySelector(".botao-usuario");
      if (botaoDoUsuario) {
        const icone = document.createElement("img");
        icone.className = "avatar avatar-foto";
        icone.alt = "";
        icone.src = endereco;
        botaoDoUsuario.querySelector(".avatar").replaceWith(icone);
      }
    }

    botaoUtilizar.addEventListener("click", async () => {
      if (!foto.imagem) {
        return;
      }
      botaoUtilizar.disabled = true;
      try {
        const recorte = await recortarFoto();
        const dados = new FormData();
        dados.append("foto", recorte, "foto.png");
        const resposta = await fetch(dialogoDaFoto.dataset.urlFoto, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken },
          body: dados,
        });
        const corpo = await resposta.json().catch(() => ({}));
        if (!resposta.ok) {
          throw new Error(corpo.erro || "Não foi possível gravar a foto. Tente novamente.");
        }
        mostrarFotoNova(corpo.url);
        dialogoDaFoto.close();
      } catch (erro) {
        botaoUtilizar.disabled = false;
        notificarErro(erro instanceof TypeError ? "Sem conexão com o servidor. Tente novamente." : erro.message);
      }
    });
  }

  // No celular, as categorias ficam numa faixa que rola para os lados (style.css): a aberta é
  // trazida para a vista, para não ficar escondida depois da última que cabe na tela.
  const categoriaAberta = document.querySelector(".lateral .categoria-ativa");
  if (categoriaAberta && window.matchMedia("(max-width: 640px)").matches) {
    categoriaAberta.scrollIntoView({ block: "nearest", inline: "center" });
  }

  // O zoom do <html> (style.css) faz as coordenadas do ponteiro, em pixels da tela, valerem
  // mais que os pixels do CSS: as medidas aplicadas em style e em scrollLeft são divididas por ele.
  function escalaDaPagina() {
    return parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  }

  // ---------- Histórico e comentários do cartão (#dialogo-historico). O trecho vem pronto do
  // servidor (_historico.html), com os textos já escapados pelo Jinja.
  const dialogoDoHistorico = document.getElementById("dialogo-historico");

  if (dialogoDoHistorico) {
    const conteudoDoHistorico = dialogoDoHistorico.querySelector("[data-historico]");

    async function carregarHistorico(url) {
      conteudoDoHistorico.replaceChildren();
      conteudoDoHistorico.setAttribute("aria-busy", "true");
      try {
        const resposta = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
        if (!resposta.ok) {
          throw new Error(String(resposta.status));
        }
        conteudoDoHistorico.innerHTML = await resposta.text();
      } catch (erro) {
        dialogoDoHistorico.close();
        notificarErro("Não foi possível abrir o histórico. Tente novamente.");
      } finally {
        conteudoDoHistorico.removeAttribute("aria-busy");
      }
    }

    document.addEventListener("click", (evento) => {
      const botao = evento.target.closest("[data-abrir-historico]");
      if (botao && botao.dataset.url) {
        dialogoDoHistorico.showModal();
        carregarHistorico(botao.dataset.url);
      }
    });

    dialogoDoHistorico.addEventListener("submit", async (evento) => {
      const formulario = evento.target.closest("[data-comentar]");
      if (!formulario) {
        return;
      }
      evento.preventDefault();
      const campo = formulario.querySelector("textarea");
      const botao = formulario.querySelector('button[type="submit"]');
      botao.disabled = true;
      try {
        const resposta = await fetch(formulario.dataset.url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
          body: JSON.stringify({ texto: campo.value }),
        });
        if (!resposta.ok) {
          const dados = await resposta.json().catch(() => ({}));
          // Só a mensagem do servidor é mostrada; a de uma falha de conexão viria em inglês.
          throw Object.assign(new Error(), { doServidor: dados.erro });
        }
        conteudoDoHistorico.innerHTML = await resposta.text();
      } catch (erro) {
        botao.disabled = false;
        notificarErro(erro.doServidor || "Não foi possível salvar o comentário. Tente novamente.");
      }
    });
  }

  // ---------- Calendário: arrastar um cartão para outro dia muda a previsão e mantém o horário.
  // Com o mouse, o cartão inteiro arrasta; no toque, só a alça, para a página continuar rolando.
  const calendario = document.getElementById("calendario");
  if (calendario) {
    let arrastoNoCalendario = null;
    let ignorarCliqueNoCalendario = false;

    function diaSobOPonteiro(x, y) {
      const elemento = document.elementFromPoint(x, y);
      return elemento && elemento.closest(".calendario-dia");
    }

    calendario.addEventListener("pointerdown", (evento) => {
      const item = evento.target.closest(".calendario-item[data-url-previsao]");
      if (!item || evento.button !== 0 || (evento.pointerType === "touch" && !evento.target.closest(".calendario-alca"))) {
        return;
      }
      arrastoNoCalendario = { item, inicioX: evento.clientX, inicioY: evento.clientY, ativo: false, alvo: null };
    });

    document.addEventListener("pointermove", (evento) => {
      const estado = arrastoNoCalendario;
      if (!estado) {
        return;
      }
      if (!estado.ativo) {
        if (Math.hypot(evento.clientX - estado.inicioX, evento.clientY - estado.inicioY) < 6) {
          return;
        }
        const caixa = estado.item.getBoundingClientRect();
        const fantasma = estado.item.cloneNode(true);
        fantasma.classList.add("calendario-fantasma");
        fantasma.style.width = caixa.width / escalaDaPagina() + "px";
        document.body.appendChild(fantasma);
        Object.assign(estado, {
          ativo: true,
          fantasma,
          deslocamentoX: estado.inicioX - caixa.left,
          deslocamentoY: estado.inicioY - caixa.top,
        });
        estado.item.classList.add("calendario-arrastando");
        document.body.classList.add("arrastando");
      }
      evento.preventDefault();
      estado.fantasma.style.left = (evento.clientX - estado.deslocamentoX) / escalaDaPagina() + "px";
      estado.fantasma.style.top = (evento.clientY - estado.deslocamentoY) / escalaDaPagina() + "px";
      const dia = diaSobOPonteiro(evento.clientX, evento.clientY);
      if (dia !== estado.alvo) {
        if (estado.alvo) {
          estado.alvo.classList.remove("calendario-alvo");
        }
        estado.alvo = dia;
        if (dia) {
          dia.classList.add("calendario-alvo");
        }
      }
    });

    function atualizarDiasVazios() {
      calendario.querySelectorAll(".calendario-dia").forEach((dia) => {
        dia.classList.toggle("calendario-dia-vazio", !dia.querySelector(".calendario-item"));
      });
    }

    async function soltarNoDia(item, dia) {
      const origem = item.parentElement;
      const proximoNaOrigem = item.nextElementSibling;
      const hora = item.querySelector(".calendario-hora").textContent;
      const lista = dia.querySelector("[data-cartoes]");
      // Fica na ordem do horário entre os cartões do novo dia.
      const depois = Array.from(lista.children).find((outro) => outro.querySelector(".calendario-hora").textContent > hora);
      lista.insertBefore(item, depois || null);
      atualizarDiasVazios();
      try {
        const resposta = await fetch(item.dataset.urlPrevisao, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
          body: JSON.stringify({ data: dia.dataset.data }),
        });
        if (!resposta.ok) {
          throw new Error(String(resposta.status));
        }
        const dados = await resposta.json();
        item.classList.toggle("calendario-vencida", dados.vencida);
        const link = item.querySelector("a");
        link.title = dados.previsao + link.title.slice(link.title.indexOf(" ·"));
      } catch (erro) {
        origem.insertBefore(item, proximoNaOrigem);
        atualizarDiasVazios();
        notificarErro("Não foi possível mudar a data. Tente novamente.");
      }
    }

    function encerrarArrastoNoCalendario(soltar) {
      const estado = arrastoNoCalendario;
      arrastoNoCalendario = null;
      if (!estado || !estado.ativo) {
        return;
      }
      estado.fantasma.remove();
      estado.item.classList.remove("calendario-arrastando");
      document.body.classList.remove("arrastando");
      if (estado.alvo) {
        estado.alvo.classList.remove("calendario-alvo");
      }
      // O clique que encerra o arrasto não abre o cartão.
      ignorarCliqueNoCalendario = true;
      setTimeout(() => {
        ignorarCliqueNoCalendario = false;
      }, 0);
      if (soltar && estado.alvo && estado.alvo !== estado.item.closest(".calendario-dia")) {
        soltarNoDia(estado.item, estado.alvo);
      }
    }

    document.addEventListener("pointerup", () => encerrarArrastoNoCalendario(true));
    document.addEventListener("pointercancel", () => encerrarArrastoNoCalendario(false));
    calendario.addEventListener("click", (evento) => {
      if (ignorarCliqueNoCalendario) {
        evento.preventDefault();
      }
    }, true);
  }

  if (!quadro) {
    return;
  }

  const DISTANCIA_MINIMA = 6;
  const MARGEM_ROLAGEM = 60;
  let arrasto = null;

  function iniciarArrasto() {
    const { cartao } = arrasto;
    const caixa = cartao.getBoundingClientRect();
    const fantasma = cartao.cloneNode(true);

    fantasma.classList.add("tarefa-fantasma");
    fantasma.style.width = caixa.width / escalaDaPagina() + "px";
    document.body.appendChild(fantasma);

    arrasto.ativo = true;
    arrasto.fantasma = fantasma;
    arrasto.deslocamentoX = arrasto.inicioX - caixa.left;
    arrasto.deslocamentoY = arrasto.inicioY - caixa.top;
    arrasto.projetoOrigem = cartao.parentElement;
    arrasto.vizinhoOrigem = cartao.nextElementSibling;
    cartao.classList.add("tarefa-arrastando");
    document.body.classList.add("arrastando");
  }

  function posicionarCartao(x, y) {
    const elemento = document.elementFromPoint(x, y);
    const projeto = elemento && elemento.closest(".projeto");
    if (!projeto) {
      return;
    }
    const tarefas = projeto.querySelector("[data-tarefas]");
    const proximo = Array.from(tarefas.children).find((filho) => {
      if (filho === arrasto.cartao) {
        return false;
      }
      const caixa = filho.getBoundingClientRect();
      return y < caixa.top + caixa.height / 2;
    });
    tarefas.insertBefore(arrasto.cartao, proximo || null);
  }

  function rolarQuadro(x) {
    const caixa = quadro.getBoundingClientRect();
    if (x > caixa.right - MARGEM_ROLAGEM) {
      quadro.scrollLeft += 12;
    } else if (x < caixa.left + MARGEM_ROLAGEM) {
      quadro.scrollLeft -= 12;
    }
  }

  function atualizarContadores() {
    quadro.querySelectorAll(".projeto").forEach((projeto) => {
      const quantidade = projeto.querySelector("[data-tarefas]").children.length;
      const foraDaTela = Number(projeto.dataset.foraDaTela);
      const excluir = projeto.querySelector("[data-excluir-projeto]");

      projeto.querySelector("[data-contador]").textContent = quantidade;
      excluir.disabled = quantidade + foraDaTela > 0;
      if (quantidade > 0) {
        excluir.dataset.dica = excluir.dataset.dicaBloqueada;
      } else {
        excluir.dataset.dica = foraDaTela > 0 ? excluir.dataset.dicaOcultas : excluir.dataset.dicaLivre;
      }
    });
  }

  // ---------- Posição do quadro: guardada antes de cada envio e restaurada depois do redirect,
  // para a tela não voltar ao começo após salvar um diálogo ou uma ação do cartão.
  const CHAVE_DA_POSICAO = "projetos-demandas-posicao";

  function lugarDoQuadro() {
    const parametros = new URLSearchParams(location.search);
    return [parametros.get("categoria") || "", parametros.get("busca") || ""].join("|");
  }

  function guardarPosicao() {
    try {
      sessionStorage.setItem(
        CHAVE_DA_POSICAO,
        JSON.stringify({ lugar: lugarDoQuadro(), esquerda: quadro.scrollLeft, topo: window.scrollY })
      );
    } catch (erro) {
      // Sem sessionStorage (janela privada), a tela só volta ao começo.
    }
  }

  document.addEventListener("submit", (evento) => {
    if ((evento.target.method || "").toLowerCase() === "post") {
      guardarPosicao();
    }
  }, true);

  try {
    const posicao = JSON.parse(sessionStorage.getItem(CHAVE_DA_POSICAO) || "null");
    sessionStorage.removeItem(CHAVE_DA_POSICAO);
    if (posicao && posicao.lugar === lugarDoQuadro()) {
      quadro.scrollLeft = posicao.esquerda;
      window.scrollTo(0, posicao.topo);
    }
  } catch (erro) {
    // Posição inválida ou indisponível: o quadro abre no começo.
  }

  // ---------- Ações do cartão sem recarregar: Concluir, Ocultar, Simplificar e Responsável.
  // A rota continua respondendo com o redirect ao quadro; o fetch segue o redirect e o cartão
  // novo sai da página devolvida. Se ela não for o quadro (sessão expirada), o envio é o comum.
  const semAnimacao = window.matchMedia("(prefers-reduced-motion: reduce)");

  function removerComAnimacao(cartao, depois) {
    if (semAnimacao.matches) {
      cartao.remove();
      depois();
      return;
    }
    cartao.style.height = cartao.offsetHeight + "px";
    cartao.classList.add("tarefa-saindo");
    let terminou = false;
    const terminar = () => {
      if (!terminou) {
        terminou = true;
        cartao.remove();
        depois();
      }
    };
    cartao.addEventListener("animationend", terminar, { once: true });
    setTimeout(terminar, 500);
  }

  function atualizarCabecalho(pagina) {
    const alertasNovos = pagina.querySelector(".topo-acoes > .menu");
    const alertas = document.querySelector(".topo-acoes > .menu");
    if (alertasNovos && alertas) {
      alertas.replaceWith(document.importNode(alertasNovos, true));
    }
  }

  function mostrarMensagens(pagina) {
    const mensagens = pagina.querySelector("[data-notificacao-texto]");
    if (mensagens && mensagens.children.length) {
      textoDaNotificacao.replaceChildren(...Array.from(mensagens.children, (filho) => document.importNode(filho, true)));
      abrirNotificacao();
    }
  }

  document.addEventListener("submit", async (evento) => {
    const formulario = evento.target.closest("form[data-acao-cartao]");
    if (!formulario || evento.defaultPrevented) {
      return;
    }
    evento.preventDefault();
    const cartaoDoBotao = formulario.closest(".tarefa");
    const tarefaId = cartaoDoBotao ? cartaoDoBotao.dataset.tarefaId : formulario.dataset.tarefaId;
    const botao = evento.submitter || formulario.querySelector('button[type="submit"]');
    const concluindo = botao && botao.classList.contains("botao-concluir") && botao.getAttribute("aria-pressed") === "false";
    let resposta;

    if (botao) {
      botao.disabled = true;
    }
    try {
      resposta = await fetch(formulario.action, {
        method: "POST",
        body: new FormData(formulario),
        headers: { "X-CSRFToken": csrfToken },
      });
    } catch (erro) {
      notificarErro("Não foi possível salvar. Verifique a conexão e tente novamente.");
      if (botao) {
        botao.disabled = false;
      }
      return;
    }
    const pagina = new DOMParser().parseFromString(await resposta.text(), "text/html");
    if (!resposta.ok || !pagina.getElementById("quadro")) {
      HTMLFormElement.prototype.submit.call(formulario);
      return;
    }
    const dialogo = formulario.closest("dialog");
    if (dialogo) {
      dialogo.close();
    }
    const cartao = quadro.querySelector('article.tarefa[data-tarefa-id="' + tarefaId + '"]');
    const novo = pagina.querySelector('article.tarefa[data-tarefa-id="' + tarefaId + '"]');
    pagina.querySelectorAll(".projeto[data-projeto-id]").forEach((projetoNovo) => {
      const projeto = quadro.querySelector('.projeto[data-projeto-id="' + projetoNovo.dataset.projetoId + '"]');
      if (projeto) {
        projeto.dataset.foraDaTela = projetoNovo.dataset.foraDaTela;
      }
    });
    atualizarCabecalho(pagina);
    mostrarMensagens(pagina);
    quadro.dataset.versao = pagina.getElementById("quadro").dataset.versao;
    if (cartao && novo) {
      const importado = document.importNode(novo, true);
      importado.classList.add("tarefa-atualizada");
      cartao.replaceWith(importado);
      atualizarContadores();
    } else if (cartao) {
      if (concluindo) {
        cartao.classList.add("tarefa-concluindo");
      }
      removerComAnimacao(cartao, atualizarContadores);
    } else if (botao) {
      botao.disabled = false;
    }
  });

  // ---------- Excluir um arquivo do cartão aberto: o cartão é salvo, o arquivo é excluído, o cartão
  // é salvo de novo e a caixa continua aberta, com a lista de arquivos e o espaço em uso atualizados.
  const dialogoDaTarefa = document.getElementById("dialogo-tarefa");
  const formularioDaTarefa = dialogoDaTarefa ? dialogoDaTarefa.querySelector("form") : null;
  const formularioDeExclusao = document.querySelector("#confirmacao form");

  // Envia o formulário do cartão sem sair da página. prepararEnvio preenche antes os campos ocultos
  // (descrição, tarefas e marcações), como num envio comum.
  // Devolve a página do quadro, ou null se houve erro (já mostrado ao usuário).
  async function salvarCartaoAberto() {
    if (!formularioDaTarefa.reportValidity()) {
      return null;
    }
    prepararEnvio(formularioDaTarefa);
    const resposta = await fetch(formularioDaTarefa.action, {
      method: "POST",
      body: new FormData(formularioDaTarefa),
      headers: { "X-CSRFToken": csrfToken },
    });
    const pagina = new DOMParser().parseFromString(await resposta.text(), "text/html");
    const mensagens = pagina.querySelector("[data-notificacao-texto]");
    if (!resposta.ok || !pagina.getElementById("quadro")) {
      notificarErro("Não foi possível salvar o cartão. Recarregue a página e tente novamente.");
      return null;
    }
    // Salvar não gera mensagem: com uma, a gravação foi recusada (um campo ou um arquivo inválido).
    if (mensagens && mensagens.children.length) {
      mostrarMensagens(pagina);
      return null;
    }
    // Os arquivos escolhidos já foram enviados, e o vídeo do generalista já foi lido na plataforma dele.
    document.getElementById("tarefa-arquivos").value = "";
    document.getElementById("tarefa-arquivos-escolhidos").textContent = "";
    const atualizarVideo = document.getElementById("tarefa-video-atualizar");
    if (atualizarVideo) {
      atualizarVideo.value = "";
    }
    return pagina;
  }

  async function excluirArquivoDoCartaoAberto(url) {
    const tarefaId = dialogoDaTarefa.dataset.tarefaId;
    try {
      if (!(await salvarCartaoAberto())) {
        return;
      }
      const dados = new FormData();
      dados.append("csrf_token", csrfToken);
      const resposta = await fetch(url, { method: "POST", body: dados, headers: { "X-CSRFToken": csrfToken } });
      if (!resposta.ok) {
        notificarErro("Não foi possível excluir o arquivo. Tente novamente.");
        return;
      }
      const pagina = await salvarCartaoAberto();
      if (!pagina) {
        return;
      }
      // O quadro por trás da caixa recebe o cartão salvo; a caixa recebe os arquivos que ficaram.
      const novoQuadro = pagina.getElementById("quadro");
      const esquerdaAnterior = quadro.scrollLeft;
      quadro.replaceChildren(...Array.from(novoQuadro.children, (filho) => document.importNode(filho, true)));
      quadro.dataset.versao = novoQuadro.dataset.versao;
      quadro.scrollLeft = esquerdaAnterior;
      atualizarCabecalho(pagina);
      let cartao = quadro.querySelector('article.tarefa[data-tarefa-id="' + tarefaId + '"]');
      if (!cartao) {
        // Oculto ou fora da pesquisa, o cartão não está no quadro: os dados vêm do ?tarefa=.
        const endereco = new URL(enderecoDoQuadro());
        endereco.searchParams.set("tarefa", tarefaId);
        const respostaDoCartao = await fetch(endereco, { headers: { "X-Requested-With": "fetch" } });
        cartao = new DOMParser()
          .parseFromString(await respostaDoCartao.text(), "text/html")
          .querySelector("[data-abrir-tarefa]");
      }
      const entradaNova = pagina.getElementById("tarefa-arquivos");
      if (entradaNova) {
        document.getElementById("tarefa-arquivos").dataset.espacoUsado = entradaNova.dataset.espacoUsado;
        const espacoNovo = pagina.querySelector("[data-espaco-em-uso]");
        const espaco = document.querySelector("[data-espaco-em-uso]");
        if (espacoNovo && espaco) {
          espaco.textContent = espacoNovo.textContent;
        }
      }
      preencherAnexos(cartao);
      atualizarSecoes();
      notificarErro("Arquivo excluído.");
    } catch (erro) {
      notificarErro("Não foi possível salvar. Verifique a conexão e tente novamente.");
    }
  }

  if (formularioDaTarefa && formularioDeExclusao) {
    formularioDeExclusao.addEventListener("submit", (evento) => {
      if (formularioDeExclusao.dataset.excluirAnexo !== "1") {
        return;
      }
      evento.preventDefault();
      formularioDeExclusao.dataset.excluirAnexo = "";
      formularioDeExclusao.closest("dialog").close();
      excluirArquivoDoCartaoAberto(formularioDeExclusao.action);
    });
  }

  // ---------- Atualização em tempo real: no quadro com categoria compartilhada (data-url-versao),
  // a versão é consultada a cada INTERVALO_DA_VERSAO enquanto a aba está à mostra. Quando ela muda,
  // os projetos são trocados no lugar, como nas ações do cartão; com uma caixa aberta ou durante um
  // arrasto, a troca espera.
  const INTERVALO_DA_VERSAO = 20000;
  let trocandoQuadro = false;

  function ocupado() {
    return Boolean(document.querySelector("dialog[open]") || arrasto || arrastoDoProjeto || document.body.classList.contains("arrastando"));
  }

  function avisarAtualizacao() {
    let aviso = document.getElementById("aviso-atualizacao");
    if (!aviso) {
      aviso = document.createElement("p");
      aviso.id = "aviso-atualizacao";
      aviso.className = "aviso-atualizacao";
      aviso.setAttribute("role", "status");
      document.body.appendChild(aviso);
    }
    aviso.textContent = "O quadro foi atualizado com as mudanças de outras pessoas.";
    aviso.classList.add("aviso-visivel");
    clearTimeout(aviso.temporizador);
    aviso.temporizador = setTimeout(() => aviso.classList.remove("aviso-visivel"), 3500);
  }

  // A página sem ?tarefa=, para a resposta não trazer o cartão que abriu o diálogo.
  function enderecoDoQuadro() {
    const endereco = new URL(location.href);
    endereco.searchParams.delete("tarefa");
    return endereco.toString();
  }

  async function trocarQuadro(avisar) {
    if (trocandoQuadro) {
      return;
    }
    trocandoQuadro = true;
    try {
      const resposta = await fetch(enderecoDoQuadro(), { headers: { "X-Requested-With": "fetch" } });
      const pagina = new DOMParser().parseFromString(await resposta.text(), "text/html");
      const novo = pagina.getElementById("quadro");
      if (!resposta.ok || !novo || ocupado()) {
        return;
      }
      // O valor lido volta como está: não passa pelo escalaDaPagina(), que vale para o ponteiro.
      const esquerdaAnterior = quadro.scrollLeft;
      quadro.replaceChildren(...Array.from(novo.children, (filho) => document.importNode(filho, true)));
      quadro.dataset.versao = novo.dataset.versao;
      quadro.scrollLeft = esquerdaAnterior;
      atualizarCabecalho(pagina);
      if (avisar) {
        avisarAtualizacao();
      }
    } catch (erro) {
      // Sem conexão: tenta de novo na próxima consulta.
    } finally {
      trocandoQuadro = false;
    }
  }

  async function consultarVersao(avisar) {
    if (!quadro.dataset.urlVersao || document.visibilityState !== "visible" || ocupado()) {
      return;
    }
    try {
      const resposta = await fetch(quadro.dataset.urlVersao, { headers: { "X-Requested-With": "fetch" } });
      if (!resposta.ok) {
        return;
      }
      const { versao } = await resposta.json();
      if (versao !== quadro.dataset.versao) {
        await trocarQuadro(avisar);
      }
    } catch (erro) {
      // Sem conexão: tenta de novo na próxima consulta.
    }
  }

  // Depois de um arrasto próprio, a versão muda por causa dele: a troca acontece sem o aviso, e
  // traz junto o que outra pessoa tenha mudado no mesmo intervalo.
  function sincronizarSemAviso() {
    consultarVersao(false);
  }

  if (quadro.dataset.urlVersao) {
    setInterval(() => consultarVersao(true), INTERVALO_DA_VERSAO);
    document.addEventListener("visibilitychange", () => consultarVersao(true));
    // A troca adiada por uma caixa aberta acontece logo que ela fecha. O evento close não sobe
    // pela página: por isso a captura.
    document.addEventListener("close", () => setTimeout(() => consultarVersao(true), 0), true);
  }

  // ---------- Modo foco: só os projetos na tela. O Esc ou o mesmo botão saem dele.
  const botaoDoFoco = document.querySelector("[data-foco]");

  function definirModoFoco(ligado) {
    document.body.classList.toggle("modo-foco", ligado);
    if (botaoDoFoco) {
      botaoDoFoco.setAttribute("aria-pressed", String(ligado));
      botaoDoFoco.classList.toggle("botao-ativo", ligado);
      botaoDoFoco.querySelector("[data-icone-desligado]").hidden = ligado;
      botaoDoFoco.querySelector("[data-icone-ligado]").hidden = !ligado;
      botaoDoFoco.dataset.dica = ligado ? "Sair do modo foco (F)" : "Modo foco (F)";
    }
    const telaCheia = document.fullscreenElement;
    if (ligado && !telaCheia && document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else if (!ligado && telaCheia && document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    }
  }

  if (botaoDoFoco) {
    botaoDoFoco.addEventListener("click", () => definirModoFoco(!document.body.classList.contains("modo-foco")));
  }
  // O Esc da tela cheia é tratado pelo navegador: ao sair dela, o modo foco também é desligado.
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && document.body.classList.contains("modo-foco")) {
      definirModoFoco(false);
    }
  });

  // ---------- Atalhos do teclado, ignorados durante a digitação e com uma caixa aberta.
  function digitando(alvo) {
    return Boolean(alvo.closest("input, textarea, select, [contenteditable]")) || alvo.isContentEditable;
  }

  document.addEventListener("keydown", (evento) => {
    // O Esc no campo da pesquisa ainda não enviada fecha a caixa, como o ×.
    if (evento.key === "Escape" && evento.target.matches("[data-campo-pesquisa]")) {
      const cancelar = document.querySelector("[data-cancelar-pesquisa]");
      if (cancelar) {
        cancelar.click();
      }
      return;
    }
    if (evento.ctrlKey || evento.metaKey || evento.altKey || digitando(evento.target)) {
      return;
    }
    if (evento.key === "Escape") {
      if (document.body.classList.contains("modo-foco") && !document.querySelector("dialog[open]")) {
        definirModoFoco(false);
      }
      return;
    }
    if (document.querySelector("dialog[open]")) {
      return;
    }
    const tecla = evento.key.toLowerCase();
    if (tecla === "/") {
      const lupa = document.querySelector("[data-pesquisar]");
      const caixa = document.getElementById("pesquisa");
      if (lupa && caixa) {
        evento.preventDefault();
        if (caixa.hidden) {
          lupa.click();
        } else {
          caixa.querySelector("[data-campo-pesquisa]").focus();
        }
      }
    } else if (tecla === "n") {
      const criar = quadro.querySelector('[data-nova-tarefa][data-tipo="atividade"]');
      if (criar) {
        evento.preventDefault();
        criar.click();
      }
    } else if (tecla === "d" || tecla === "c") {
      const destino = document.querySelector(tecla === "d" ? "[data-meu-dia]" : "[data-calendario]");
      if (destino) {
        evento.preventDefault();
        location.href = destino.href;
      }
    } else if (tecla === "f" && botaoDoFoco) {
      evento.preventDefault();
      botaoDoFoco.click();
    } else if (evento.key === "?") {
      const atalhos = document.getElementById("dialogo-atalhos");
      if (atalhos) {
        evento.preventDefault();
        atalhos.showModal();
      }
    }
  });

  function restaurarCartao(estado) {
    estado.projetoOrigem.insertBefore(estado.cartao, estado.vizinhoOrigem);
    atualizarContadores();
  }

  function encerrarArrasto() {
    if (arrasto && arrasto.ativo) {
      arrasto.fantasma.remove();
      arrasto.cartao.classList.remove("tarefa-arrastando");
      document.body.classList.remove("arrastando");
    }
    const estado = arrasto;
    arrasto = null;
    return estado;
  }

  async function salvarPosicao(estado) {
    const { cartao } = estado;
    const projeto = cartao.closest(".projeto");
    const posicao = Array.from(cartao.parentElement.children).indexOf(cartao);

    atualizarContadores();
    try {
      const resposta = await fetch(cartao.dataset.urlMover, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ projeto_id: Number(projeto.dataset.projetoId), posicao }),
      });
      if (!resposta.ok) {
        throw new Error(resposta.status);
      }
      cartao.dataset.projetoId = projeto.dataset.projetoId;
      sincronizarSemAviso();
    } catch (erro) {
      restaurarCartao(estado);
      notificarErro("Não foi possível mover a demanda. Tente novamente.");
    }
  }

  let arrastoDoProjeto = null;

  function iniciarArrastoDaProjeto() {
    const { projeto } = arrastoDoProjeto;
    const caixa = projeto.getBoundingClientRect();
    const fantasma = projeto.cloneNode(true);

    fantasma.classList.add("projeto-fantasma");
    fantasma.style.width = caixa.width / escalaDaPagina() + "px";
    document.body.appendChild(fantasma);

    arrastoDoProjeto.ativo = true;
    arrastoDoProjeto.fantasma = fantasma;
    arrastoDoProjeto.deslocamentoX = arrastoDoProjeto.inicioX - caixa.left;
    arrastoDoProjeto.deslocamentoY = arrastoDoProjeto.inicioY - caixa.top;
    arrastoDoProjeto.vizinhaOrigem = projeto.nextElementSibling;
    projeto.classList.add("projeto-arrastando");
    document.body.classList.add("arrastando");
  }

  function posicionarProjeto(x) {
    const { projeto } = arrastoDoProjeto;
    const proxima = Array.from(quadro.children).find((outra) => {
      if (outra === projeto) {
        return false;
      }
      const caixa = outra.getBoundingClientRect();
      return x < caixa.left + caixa.width / 2;
    });
    quadro.insertBefore(projeto, proxima || null);
  }

  function encerrarArrastoDaProjeto() {
    if (arrastoDoProjeto && arrastoDoProjeto.ativo) {
      arrastoDoProjeto.fantasma.remove();
      arrastoDoProjeto.projeto.classList.remove("projeto-arrastando");
      document.body.classList.remove("arrastando");
    }
    const estado = arrastoDoProjeto;
    arrastoDoProjeto = null;
    return estado;
  }

  async function salvarOrdemDosProjetos(estado) {
    const projetos = Array.from(quadro.children).map((projeto) => Number(projeto.dataset.projetoId));

    try {
      const resposta = await fetch(quadro.dataset.urlOrdem, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ projetos }),
      });
      if (!resposta.ok) {
        throw new Error(resposta.status);
      }
      sincronizarSemAviso();
    } catch (erro) {
      quadro.insertBefore(estado.projeto, estado.vizinhaOrigem);
      notificarErro("Não foi possível mover o projeto. Tente novamente.");
    }
  }

  quadro.addEventListener("pointerdown", (evento) => {
    if (!evento.target.closest(".projeto-alca") || evento.button !== 0) {
      return;
    }
    arrastoDoProjeto = {
      projeto: evento.target.closest(".projeto"),
      inicioX: evento.clientX,
      inicioY: evento.clientY,
      ativo: false,
    };
  });

  document.addEventListener("pointermove", (evento) => {
    if (!arrastoDoProjeto) {
      return;
    }
    if (!arrastoDoProjeto.ativo) {
      const distancia = Math.hypot(
        evento.clientX - arrastoDoProjeto.inicioX,
        evento.clientY - arrastoDoProjeto.inicioY
      );
      if (distancia < DISTANCIA_MINIMA) {
        return;
      }
      iniciarArrastoDaProjeto();
    }
    arrastoDoProjeto.fantasma.style.left = (evento.clientX - arrastoDoProjeto.deslocamentoX) / escalaDaPagina() + "px";
    arrastoDoProjeto.fantasma.style.top = (evento.clientY - arrastoDoProjeto.deslocamentoY) / escalaDaPagina() + "px";
    posicionarProjeto(evento.clientX);
    rolarQuadro(evento.clientX);
  });

  document.addEventListener("pointerup", () => {
    const estado = encerrarArrastoDaProjeto();
    if (estado && estado.ativo && estado.projeto.nextElementSibling !== estado.vizinhaOrigem) {
      salvarOrdemDosProjetos(estado);
    }
  });

  document.addEventListener("pointercancel", () => {
    const estado = encerrarArrastoDaProjeto();
    if (estado && estado.ativo) {
      quadro.insertBefore(estado.projeto, estado.vizinhaOrigem);
    }
  });

  quadro.addEventListener("pointerdown", (evento) => {
    const cartao = evento.target.closest(".tarefa");
    if (
      !cartao ||
      evento.button !== 0 ||
      permissaoDoQuadro === "visualizar" ||
      pesquisaAtiva ||
      evento.target.closest(".tarefa-acoes, .tarefa-anexos, .tarefa-pessoas")
    ) {
      return;
    }
    // No toque, só a alça arrasta, para que o restante do cartão continue rolando a tela.
    if (evento.pointerType !== "mouse" && !evento.target.closest(".tarefa-alca")) {
      return;
    }
    arrasto = { cartao, inicioX: evento.clientX, inicioY: evento.clientY, ativo: false };
  });

  document.addEventListener("pointermove", (evento) => {
    if (!arrasto) {
      return;
    }
    if (!arrasto.ativo) {
      const distancia = Math.hypot(
        evento.clientX - arrasto.inicioX,
        evento.clientY - arrasto.inicioY
      );
      if (distancia < DISTANCIA_MINIMA) {
        return;
      }
      iniciarArrasto();
    }
    arrasto.fantasma.style.left = (evento.clientX - arrasto.deslocamentoX) / escalaDaPagina() + "px";
    arrasto.fantasma.style.top = (evento.clientY - arrasto.deslocamentoY) / escalaDaPagina() + "px";
    posicionarCartao(evento.clientX, evento.clientY);
    rolarQuadro(evento.clientX);
  });

  document.addEventListener("pointerup", () => {
    const estado = encerrarArrasto();
    if (!estado || !estado.ativo) {
      return;
    }
    // O clique que encerra o arrasto não deve abrir a edição da tarefa.
    ignorarClique = true;
    setTimeout(() => {
      ignorarClique = false;
    }, 0);

    const mudou =
      estado.cartao.parentElement !== estado.projetoOrigem ||
      estado.cartao.nextElementSibling !== estado.vizinhoOrigem;
    if (mudou) {
      salvarPosicao(estado);
    }
  });

  document.addEventListener("pointercancel", () => {
    const estado = encerrarArrasto();
    if (estado && estado.ativo) {
      restaurarCartao(estado);
    }
  });

  // Com o mouse, arrastar uma área livre do quadro rola os projetos para os lados.
  // No toque, a rolagem já é feita pelo navegador.
  const ALVOS_SEM_ROLAGEM = ".tarefa, .projeto-alca, a, button, input, select, textarea, label";
  let rolagem = null;

  function atualizarQuadroRolavel() {
    quadro.classList.toggle("quadro-rolavel", quadro.scrollWidth > quadro.clientWidth);
  }

  new ResizeObserver(atualizarQuadroRolavel).observe(quadro);
  atualizarQuadroRolavel();

  quadro.addEventListener("pointerdown", (evento) => {
    if (
      evento.pointerType !== "mouse" ||
      evento.button !== 0 ||
      !quadro.classList.contains("quadro-rolavel") ||
      evento.target.closest(ALVOS_SEM_ROLAGEM)
    ) {
      return;
    }
    // Sem isto, arrastar seleciona o texto dos projetos.
    evento.preventDefault();
    rolagem = { inicioX: evento.clientX, inicioScroll: quadro.scrollLeft, ativo: false };
  });

  document.addEventListener("pointermove", (evento) => {
    if (!rolagem) {
      return;
    }
    const deslocamento = evento.clientX - rolagem.inicioX;

    if (!rolagem.ativo) {
      if (Math.abs(deslocamento) < DISTANCIA_MINIMA) {
        return;
      }
      rolagem.ativo = true;
      document.body.classList.add("arrastando");
    }
    quadro.scrollLeft = rolagem.inicioScroll - deslocamento / escalaDaPagina();
  });

  function encerrarRolagem() {
    if (rolagem && rolagem.ativo) {
      document.body.classList.remove("arrastando");
      ignorarClique = true;
      setTimeout(() => {
        ignorarClique = false;
      }, 0);
    }
    rolagem = null;
  }

  document.addEventListener("pointerup", encerrarRolagem);
  document.addEventListener("pointercancel", encerrarRolagem);
  // Pesquisar: a lupa mostra a caixa à esquerda dela; o ENTER envia a busca ao quadro (GET).
  const botaoPesquisar = document.querySelector("[data-pesquisar]");
  const caixaPesquisa = document.getElementById("pesquisa");
  if (botaoPesquisar && caixaPesquisa) {
    const campoPesquisa = caixaPesquisa.querySelector("[data-campo-pesquisa]");
    botaoPesquisar.addEventListener("click", () => {
      caixaPesquisa.hidden = false;
      botaoPesquisar.setAttribute("aria-expanded", "true");
      campoPesquisa.focus();
      campoPesquisa.select();
    });
    const cancelar = caixaPesquisa.querySelector("[data-cancelar-pesquisa]");
    if (cancelar) {
      cancelar.addEventListener("click", () => {
        campoPesquisa.value = "";
        caixaPesquisa.hidden = true;
        botaoPesquisar.setAttribute("aria-expanded", "false");
        botaoPesquisar.focus();
      });
    }
  }
})();
