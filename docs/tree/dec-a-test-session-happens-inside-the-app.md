---
id: dec-a-test-session-happens-inside-the-app
type: decision
title: A test session happens inside the product's app
state: in-force
decided: '2026-10-06'
sources:
- Owner design discussion of 2026-10-06, how pass, level 3, goal C (the owner decides what; Agentos decides how)
- Owner design discussion of 2026-10-06, point 7, question 1
- 'Owner, 2026-10-09, after the first test, for every product: ''Tenemos que mejorar el cómo se hacen las sesiones de prueba y cómo doy el feedback''; the session opens from a "Test session" button in the app header, not for a branch (see uc-open-a-test-session-for-a-branch for the owner''s words on the panel, the guide, the comments box and the three states)'
- 'Owner, 2026-10-09, correcting the earlier two boxes: ''la caja de comentarios podría ser solo una no tiene sentido tener dos, una para los comentarios que se quieran hacer y un desplegable con el estado como he dicho en mis comentarios anteriores, pero unificado'' -- one comments box with a state dropdown, always at the top'
- 'Owner, 2026-10-09, second correction, which prevails: everything lives in the side panel so the interface of the app is not distorted -- the comments box next to the list of use cases and the instructions of the chosen one, collapsed and expanded from the side with the header button without losing state (''para no distorsione la interfaz la caja de comentario podría ir en el panel lateral junto a la lista de casos de uso, y las instrucciones del caso de uso y que se colapsara y desplegara desde el lateral sin perder el estado con el botón de la cabecera "sesión de pruebas"'')'
- 'Owner, 2026-10-09, third addition, which prevails: the comments box is a chat with the agent that will interpret the feedback, because if it has doubts that is the place to ask the owner (''esa caja de comentario podría ser un chat con el agente que va a interpretar eso que le digo, porque si tiene dudas, ese es el sitio para preguntarme'')'
- 'Owner, 2026-10-09, fourth addition, which prevails: on the test-session side panel, a checkbox at the top, on by default, to see only the use cases of the screen the owner is on (''si estoy en una pantalla, los casos de uso se podrían filtrar con un checkbox arriba que por defecto estuviera activado de "ver casos de uso solo de esta pantalla"'')'
- 'Owner, 2026-10-09: ''Directo, salvo decisiones'' -- a comment is split into changes launched directly, and the decisions of what are shown to the owner at the start of the next session to confirm or correct'
- 'Owner, 2026-10-09, after trying the side panel on the first host, fifth correction, which prevails where it clashes with the earlier ones: no "close the session" button and no "session is open" header with the opening time (kept internally, not drawn); a scrolling list of use cases at the top, the chat below it across the full width of the panel and over half of its height, the state dropdown and Send on one line under the chat; the chat history kept and linked only to the use case being viewed; a minimum width and a draggable edge; and what changed since the previous session, from the history of pull requests or issues, as Agentos sees best (see uc-open-a-test-session-for-a-branch for the owner''s exact words: ''sobra lo de arriba de "La sesión está abierta"'', ''que lo guardes internamente me parece bien'')'
premises:
- A puntal's questions are best answered in the context of the action that raised them
- Trying what changed is using the product, and any use is also a test
- Not everything can be tried at once, so someone other than the owner has to decide what comes first, and the first thing is what the others depend on
- A comment is useful before touching anything (texts, aesthetics, visibility), so the place to leave it exists even when there is nothing to try
- The session must not distort the app's interface, so it lives in a side panel that keeps its state when collapsed
- Feedback in free words has to be interpreted, and what the interpreter doubts is best asked in the place where the owner already is
- On a given screen the owner mostly wants the cases that live there
- A single comment mixes changes of different kinds, and only the ones that decide what the product is for need the owner again
- A comment is feedback the moment it is sent, and closing a session is bookkeeping, so the owner is not asked to close it nor shown that it is open
- The chat is where the owner spends the session, so it takes most of the panel; the panel must be wide enough to read it and resizable
- What was said about a use case belongs to the case and not to the session in which it was said, so a case keeps its conversation across sessions
- What changed since the previous session is what was merged since then, because pull requests are what really changed and issues are only the intent
rejected_alternatives:
- option: A test session as a checklist outside the app
  reason: The owner chose the session inside the app
  basis: stated
- option: A test session opened for one branch, listing the cases of what changed
  reason: 'Implied by the corrections that followed, not argued at approval: in the first test the owner opened one for a branch with no cases and no questions, closed it in 35 seconds and found nowhere to comment; the owner asked for a session opened from the app, with the comments box always present'
  basis: implied
- option: Agentos shows the owner how it splits each comment and waits for the owner's confirmation before launching any change
  reason: 'Implied by the choice made, not argued at approval: the owner chose to launch directly and to be shown only the decisions of what, at the start of the next session'
  basis: implied
- option: A button to close the session and a header showing it is open and since when
  reason: 'The owner found it unnecessary, since sending already sends the feedback (the fifth correction); the session opens by itself when the panel expands and closes by itself after a period without messages, and its times are kept in the file, not drawn'
  basis: stated
- option: One thread per session, closed with it
  reason: 'Implied by the fifth correction, not argued at approval: the owner asked for the chat history to be kept and linked only to the use case being viewed, so the thread follows the case across sessions'
  basis: implied
- option: Showing the GitHub issues as what changed since the previous session
  reason: 'Implied by the choice made, not argued at approval: the owner left it open (pull requests or issues, as Agentos sees best); pull requests are what really changed and issues are only the intent, and the merged pull requests can be read from the local git history without a network'
  basis: implied
review_triggers:
- A product cannot host a session mode in its own interface
- A change that decides what the product is for is launched from a comment without the owner having seen it
- The owner has to open the session for a branch or a feature to be able to try or comment on what the owner wants
- Feedback the owner has already sent is not read until the owner does something else, such as closing the session
- Opening a new session hides what the owner said earlier about a use case
---
The owner opens a test session from a button in the product's app header, inside the app and not for
a branch. The button collapses and expands a side panel, without losing its state, and everything
lives in it so the app's interface is not distorted. There is no button to close the session and no
header saying it is open: it opens when the panel expands, closes by itself after a period without
messages, and every message is feedback from the moment it is sent. At the top of the panel are the use
cases to try, prioritized by Agentos -- first what the others depend on, by default only those of the screen
the owner is on, until the owner unchecks the box -- in a list with its own scroll. Below it is the chat,
across the full width of the panel and over half of its height, with the state dropdown (perfect, ok with
improvements, needs work, or none) and the send button on one line under it; the state applies to the
chosen use case, whose instructions and what changed since the previous session (the pull requests merged
since then that touched it) are shown with it. The chat is with the agent that interprets the feedback: it
answers in the thread, asks there whatever it doubts and leaves its interpretation as separate changes
or decisions of what. Each use case keeps its own thread, with its history across sessions; with none
chosen the thread is the general one. The panel has a minimum width and the owner can drag its edge to
resize it. Its puntals ask their pending questions in context -- the only place where the
product asks the owner something in real time. What the owner accepts hardens the specification;
what the owner rejects returns as rework or as a question of what; the answers are written back
into the nodes.
A comment is split into separate changes that are launched directly, except the decisions of what:
those are shown to the owner when the next session starts, as what Agentos understood and where it
went, and the owner confirms or corrects them there.
