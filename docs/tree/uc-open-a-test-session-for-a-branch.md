---
id: uc-open-a-test-session-for-a-branch
type: use-case
title: Open a test session from the app
parent: fr-the-owner-is-asked-only-in-sessions-they-open
sources:
- 'Owner design discussion of 2026-10-06: what the owner does with Agentos (its use cases)'
- 'Owner, 2026-10-09, after the first test, for every product: the test sessions and the way feedback is given have to improve (''Tenemos que mejorar el cómo se hacen las sesiones de prueba y cómo doy el feedback''); not everything can be tried at once, so someone has to decide what comes first (signing up, logging in, creating a listing...)'
- 'Owner, 2026-10-09: the use case is picked in a hidden side panel on the left that opens from a button in the web header (first called "use cases", corrected to "test session": ''mejor llamarle "sesión de pruebas"''); the use case carries a guide of what to do and a comments box to use before any action, even before interacting (texts, aesthetics, visibility), and another box with three states -- perfect, ok with improvements, needs work (the owner''s own words: ''perfecto, ok con mejoras, mejorable o "incorrecto"'') -- with a text box for comments'
- 'Owner, 2026-10-09: as soon as the test-session panel opens, even with no use case to try, at least the comments box has to be at the top (''aunque no hubiera ningún caso de uso para probar, por lo menos la caja para comentarios arriba debería estar'')'
- 'Owner, 2026-10-09, choosing how a comment with several things becomes work: ''Directo, salvo decisiones'' -- Agentos splits it into separate changes and launches them; the decisions of what are shown to the owner when the next session starts (''lo que entendí y en qué quedó'') and the owner confirms or corrects them there'
- 'Owner, 2026-10-09, correcting the previous point, which prevails over it: there is one comments box, not two, with the state as a dropdown (''la caja de comentarios podría ser solo una no tiene sentido tener dos, una para los comentarios que se quieran hacer y un desplegable con el estado como he dicho en mis comentarios anteriores, pero unificado'')'
- 'Owner, 2026-10-09, second correction, which prevails: everything lives in the side panel so the interface of the app is not distorted -- the comments box next to the list of use cases and the instructions of the chosen one, collapsed and expanded from the side with the header button without losing state (''para no distorsione la interfaz la caja de comentario podría ir en el panel lateral junto a la lista de casos de uso, y las instrucciones del caso de uso y que se colapsara y desplegara desde el lateral sin perder el estado con el botón de la cabecera "sesión de pruebas"'')'
- 'Owner, 2026-10-09, third addition, which prevails: the comments box is a chat with the agent that will interpret the feedback, because if it has doubts that is the place to ask the owner (''esa caja de comentario podría ser un chat con el agente que va a interpretar eso que le digo, porque si tiene dudas, ese es el sitio para preguntarme'')'
- 'Owner, 2026-10-09, fourth addition, which prevails: on the test-session side panel, a checkbox at the top, on by default, to see only the use cases of the screen the owner is on (''si estoy en una pantalla, los casos de uso se podrían filtrar con un checkbox arriba que por defecto estuviera activado de "ver casos de uso solo de esta pantalla"'')'
- 'Owner, 2026-10-09, after trying the side panel on the first host, fifth correction, which prevails where it clashes with the earlier ones: small improvements -- the "close the session" button is not needed and can go, since Send already sends the feedback; the use cases go in a scrolling list at the top (with the check to see only the current screen''s) and below it the chat, with the state dropdown and the Send button on the same line under it, so the chat takes the full width of the panel and more than half of its height; the chat history is kept and linked only to the use case being viewed; the panel has a minimum width and can be made bigger or smaller by dragging its edge; and what changed since the previous session, left to Agentos (the history of GitHub pull requests or issues, ''lo que veas mejor''): ''tengo pequeñas mejoras para el panel lateral de la sesión de pruebas: 1)0 no sé para qué sirve el botón "Cerrar la sesión", pero me da la sensación de que no hace falta y se puede quitar, el botón Enviar ya va enviando el feedback que es lo que queremos. 2) pondría la parte de selección de casos de prueba en una lista (con scroll) arriba (incluído el check de ver los de esta página) y abajo en otra caja el chat y debajo el desplegable del estado y el botón Enviar en la misma línea, de forma que el chat ocupe mucho más espacio (el ancho del panel completo) y más del 50% de la altura del panel. Me gustaría que se guardara el histórico del chat y que estuviera vinculado solo al caso de uso que estamos viendo. El panel lateral debería tener un ancho mínimo de 500px y poder hacerse más grande o más chico, arrastrando el borde. Y qué ha cambiado desde la sesión anterior, el histórico de PRs o de issues de github, lo que veas mejor'''
- 'Owner, 2026-10-09, right after the fifth correction: the header of the panel saying the session is open with its opening time is not needed either, though keeping the time internally is fine: ''También sobra lo de arriba de "La sesión está abierta" y el tiempo de apertura, que lo guardes internamente me parece bien'''
decisions:
- dec-a-test-session-happens-inside-the-app
mechanism: |-
  Stage 1 (minimal). A "Test session" button in the app's header collapses and expands a side panel;
  the owner opens a session from the app, not for a branch. Everything lives in the panel, so the
  app's own pages are not altered, and collapsing, expanding or navigating to another page does not
  lose its state (chosen case, message half-written, state dropdown, scroll of the list, width of the
  panel): it is kept in the browser and what was already sent is kept on the server.
  There is no "close the session" button and no "the session is open" header with its opening time.
  Expanding the panel opens the session by itself and the session closes by itself after a period
  without messages (the first host uses 2 hours; the next opening then starts another session); its
  times are written in the session file and not drawn. A message is feedback the moment it is sent:
  Agentos reads a session that is still open, message by message and idempotently, and does not wait
  for it to close.
  The panel has two parts. At the top, the list of use cases to try, with its own scroll, headed by
  a checkbox "show only this screen's use cases", on by default, that filters the list down to the cases
  of the screen the owner is on (all of them when it is off, in the same order); its value is kept like
  the rest of the panel's state. The list is prioritized by Agentos: first what the others depend on
  (signing up, logging in, creating a listing), then what builds on it; the owner picks one and sees
  its instructions and what changed since the previous session. Below the list, the chat with the
  agent that interprets the feedback, across the full width of the panel and taking more than half of
  its height; under the chat, on a single line, the state dropdown (perfect, ok with improvements,
  needs work, or none) and the send button. The chat is there always, even when there is nothing to
  try, and the owner can comment before acting (texts, aesthetics, visibility). The puntals' pending
  questions are answered in context.
  The thread belongs to the case. Each use case has its own thread, the chat shows only the one of the
  case the owner is viewing, and its history is kept between sessions (every session that touched the
  case is read, with a date separator between them); with no case chosen the thread is the general one.
  The state applies to the chosen case. The panel has a minimum width (the first host uses 500 px) and
  the owner can make it wider or narrower by dragging its edge; the width is kept like the rest of the
  state.
  What changed since the previous session is the pull requests merged since then (number, title, link
  to the forge), filtered by the chosen case (those that changed its node under the product tree) or
  all of them with no case. They are read from the git history of the checkout that serves the app, with
  no network: pull requests are what really changed, issues are only the intent.
  What becomes of the feedback. Each message of the owner (with its case, state and page) goes to the
  interpreter, which answers in the same thread, asks there whatever it doubts -- the session is a
  place where the owner is asked (fr-the-owner-is-asked-only-in-sessions-they-open) -- and leaves
  its interpretation as separate items. A state of perfect hardens the specification; needs work
  returns as rework, ok with improvements as the changes its text names. A comment, general or per
  case, is split into separate changes and each is launched directly. The exception is a decision of
  what: it is not launched, it is shown to the owner when the next session starts, under "what I
  understood and where it went", and the owner confirms or corrects it there. The interpreter belongs to
  Agentos and serves every product; the product draws the chat and keeps the thread. Answers are
  written back into the nodes.
---
The owner opens a test session from a button in the app's header, whatever branch the product is on,
and tries one use case at a time, in the order Agentos has prioritized: what the others depend on
comes first, filtered by default to the screen the owner is on. There is nothing to open or close:
the session starts when the panel is expanded, ends by itself when the owner stops writing, and every
message counts as feedback from the moment it is sent. At the top of the panel the owner has the list
of use cases; below it, taking most of the panel, a chat with the agent that interprets the feedback and
asks there whatever it doubts, with a state beside the send button (perfect, ok with improvements, needs
work, or none) that applies to the chosen case. Each case keeps its own conversation, with its history
across sessions, and shows what has been merged since the owner's previous session. Before acting the
owner can comment on texts, aesthetics or visibility, and after trying the owner gives the state with its
text. Even with nothing to try, the chat is there for general comments. All of it is in the side panel the
header button collapses and expands, which the owner can widen or narrow, and the page of the app is left
as it is. It is the only place where the product asks the owner something in real time, and what the owner
accepts there becomes part of how consolidated parts are verified (fr-what-is-consolidated-is-correct).

What the owner writes is not a ticket. A comment that mixes several changes of different kinds is split by
Agentos and each change is launched without asking; only what would decide what the product is for
waits for the owner, who sees it, with what Agentos understood, when the next session starts.
