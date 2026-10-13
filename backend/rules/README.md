# Regole estratte dalla Input Output Reference

Un file per gruppo di sezioni, scritto da un'estrazione separata, così il lavoro
e' parallelizzabile e riprendibile. `idf_rules.py` li unisce.

Ogni regola e' stata verificata contro `Energy+.idd` prima di essere scritta:
la prosa e l'IDD non sempre concordano (la documentazione scrive "GlazedDoor"
dove la chiave e' `GlassDoor`), e in caso di disaccordo vince l'IDD.
