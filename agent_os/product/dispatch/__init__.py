"""What a compiled ticket says about itself, and the dispatch rules that read it back.

`compile` (`agent_os.product.tree.compile`) writes three marker lines at the end of every ticket --
the node it came from, the nodes it depends on, the code it touches -- and the rules in
`agent_os.product.dispatch.rules` decide, from those lines alone, whether a ticket may start in a
v2 host. Keeping both halves in one package is what keeps the writer and the reader of a marker
from drifting apart.
"""
