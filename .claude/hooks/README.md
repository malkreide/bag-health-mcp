# SessionStart-Hook: Klon-Aktualität

`check-clone-freshness.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `origin/<default-branch>` liegt. Registriert in
`.claude/settings.json` unter `hooks.SessionStart`.

## Grund

Ein veralteter Klon hat am 3.8.2026 **zweimal** eine rote CI erzeugt, deren
Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau die,
die das Gate einführten, an dem der Branch scheiterte. Man sucht den Fehler
dann in den Dateien, die man selbst geändert hat, und findet dort nichts.

Die Prüfung kostet eine Sekunde und ersetzt eine Fehlersuche in den falschen
Dateien.

## Verhalten

| Fall | Ausgabe |
| --- | --- |
| 0 Commits hinter | nichts — der Hook schweigt |
| n > 0 Commits hinter | Anzahl, Default-Branch und Angleich-Befehl |
| kein Netz, kein Remote, kein Git, DNS flattert | nichts |
| detached HEAD (Rebase, Bisect) | nichts |
| Default-Branch nicht ermittelbar | nichts |
| `timeout`/`gtimeout` nicht installiert | nichts |

## Die Regel über allen anderen: nie blockieren

Der Hook endet **immer** mit Exit 0. Umgesetzt durch drei Dinge zusammen:

- `trap 'exit 0' EXIT` fängt auch unerwartete Abbrüche ab.
- Bewusst **kein** `set -e`. Ein einzelner fehlschlagender Befehl (fetch,
  `ls-remote`, `rev-list`) darf nicht den Sessionstart abbrechen.
- Jeder Netzaufruf läuft unter `timeout` (Default 5 s, überschreibbar via
  `CLAUDE_FRESHNESS_TIMEOUT`); zusätzlich begrenzt `settings.json` den Hook
  auf 15 s. Fehlt `timeout` und `gtimeout`, wird gar nichts geprüft — lieber
  keine Prüfung als ein hängender Sessionstart.

Der Grund für diese Härte ist nicht Eleganz: Ein Hook, der bei Netzproblemen
die Arbeit anhält, wird nach dem zweiten Mal abgeschaltet und schützt danach
gar nichts.

## Default-Branch wird ermittelt, nicht angenommen

Nicht `main` annehmen. Drei Server im Portfolio (`openlex-mcp`,
`swiss-courts-mcp`, `swisstopo-mcp`) heissen ihren Standard-Branch `master`;
genau diese Annahme hat schon einmal einen Branch 15 Commits alt werden
lassen. Ermittelt wird in dieser Reihenfolge:

1. `git symbolic-ref --short refs/remotes/origin/HEAD` — lokal gecacht,
   kostet kein Netz.
2. `git ls-remote --symref origin HEAD` — nur wenn (1) leer bleibt.

Bleibt beides leer, schweigt der Hook. Ein Rückfall auf `main` findet
**nicht** statt: eine falsche Referenz meldet entweder gar nichts oder
Unsinn, beides ist schlechter als Schweigen.

## Lokal testen

```bash
./.claude/hooks/check-clone-freshness.sh; echo "exit=$?"
```

Gegenprobe — künstlich hinter den Stand zurückfallen, ohne den Branch zu
verändern:

```bash
git switch --detach HEAD~3 && ./.claude/hooks/check-clone-freshness.sh
git switch -                     # zurück
```

(Auf detached HEAD schweigt der Hook absichtlich; für eine echte Gegenprobe
einen Wegwerf-Branch drei Commits vor dem Stand anlegen.)
