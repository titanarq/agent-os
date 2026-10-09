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
decisions:
- dec-a-test-session-happens-inside-the-app
mechanism: |-
  Stage 1 (minimal). A "Test session" button in the app's header collapses and expands a side panel;
  the owner opens a session from the app, not for a branch. Everything lives in the panel, so the
  app's own pages are not altered, and collapsing, expanding or navigating to another page does not
  lose its state (chosen case, comment half-written, state dropdown, scroll of the list): it is kept
  in the browser and what was already sent is kept on the server. At the top of the panel, always,
  even when there is nothing to try, ONE comments box, which is a chat with the agent that interprets the feedback, with a state
  dropdown beside it: perfect, ok with improvements, needs work, or none. When a use case is chosen, the state applies to it; with none chosen the
  comment is general. Below the box, a checkbox "show only this screen's use cases", on by default,
  filters the list down to the cases of the screen the owner is on (all of them when it is off, in
  the same order); its value is kept like the rest of the panel's state. The list holds the use cases
  to try, prioritized by Agentos: first what the others depend on (signing up, logging in, creating
  a listing), then what builds on it; the owner picks one and sees its instructions in the panel. The owner can comment before acting (texts, aesthetics,
  visibility). The puntals' pending questions are answered in context.
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
comes first, filtered by default to the screen the owner is on. The owner has one comments box, always at the top of the panel, which is a chat with the agent that
interprets the feedback and asks there whatever it doubts, with a state beside it
(perfect, ok with improvements, needs work, or none) that applies to the chosen case: before acting the
owner can comment on texts, aesthetics or visibility, and after trying the owner gives the state with its text.
Even with nothing to try, the box is there for general comments. All of it is in the side panel the
header button collapses and expands, and the page of the app is left as it is. It is the only place
where the product asks the owner something in real time, and what the owner accepts there becomes
part of how consolidated parts are verified (fr-what-is-consolidated-is-correct).

What the owner writes is not a ticket. A comment that mixes several changes of different kinds is split by
Agentos and each change is launched without asking; only what would decide what the product is for
waits for the owner, who sees it, with what Agentos understood, when the next session starts.
