#!/usr/bin/env bash
# SessionStart-Hook: meldet, wie viele Commits der ausgecheckte Stand hinter
# origin/<default-branch> liegt. Siehe .claude/hooks/README.md fuer den Grund.
#
# Oberste Regel: Dieser Hook blockiert die Session NIEMALS. Kein Netz, kein
# Remote, detached HEAD, flatterndes DNS, fehlendes `timeout` — jeder dieser
# Faelle endet still mit Exit 0. Deshalb bewusst KEIN `set -e`: ein einzelner
# fehlschlagender Befehl darf nicht den ganzen Sessionstart abbrechen.
set -u

# Ein Hook, der bei Netzproblemen die Arbeit anhaelt, wird nach dem zweiten Mal
# abgeschaltet und schuetzt danach gar nichts. Darum: was auch immer unten
# passiert (auch ein unerwarteter Fehler), der Exit-Code ist 0.
trap 'exit 0' EXIT

FETCH_TIMEOUT="${CLAUDE_FRESHNESS_TIMEOUT:-5}"

log() { printf '%s\n' "$*"; }

main() {
  command -v git >/dev/null 2>&1 || return 0

  # `timeout` ist Pflicht — ohne harte Zeitschranke koennte das fetch den
  # Sessionstart haengen lassen. Fehlt es (z. B. macOS ohne coreutils), wird
  # still nichts geprueft, statt das Risiko einzugehen.
  local timeout_bin=""
  if command -v timeout >/dev/null 2>&1; then
    timeout_bin="timeout"
  elif command -v gtimeout >/dev/null 2>&1; then
    timeout_bin="gtimeout"
  else
    return 0
  fi

  cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || return 0
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  git remote get-url origin >/dev/null 2>&1 || return 0

  # Detached HEAD: still durchgehen (z. B. waehrend Rebase oder Bisect).
  git symbolic-ref -q HEAD >/dev/null 2>&1 || return 0

  # Default-Branch ermitteln, nicht "main" annehmen: mindestens ein Repo im
  # Portfolio nutzt "master", und genau diese Annahme hat schon einmal einen
  # Branch 15 Commits alt werden lassen. Erst der lokal gecachte
  # origin/HEAD (kostet kein Netz), dann als Fallback das Remote fragen.
  local default_branch=""
  default_branch="$(git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null)" || default_branch=""
  default_branch="${default_branch#origin/}"

  if [ -z "$default_branch" ]; then
    default_branch="$(
      "$timeout_bin" "$FETCH_TIMEOUT" git ls-remote --symref origin HEAD 2>/dev/null |
        sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p' | head -1
    )" || default_branch=""
  fi

  # Kein Default-Branch ermittelbar (kein Netz, kaputtes Remote): still raus.
  # Niemals auf "main" zurueckfallen — eine falsche Referenz meldet entweder
  # gar nichts oder Unsinn, beides schlechter als Schweigen.
  [ -n "$default_branch" ] || return 0

  "$timeout_bin" "$FETCH_TIMEOUT" git fetch --quiet origin "$default_branch" >/dev/null 2>&1 || return 0

  local behind=""
  behind="$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)" || return 0
  case "$behind" in
    ''|*[!0-9]*) return 0 ;;
    0) return 0 ;;   # Aktuell — dann schweigt der Hook.
  esac

  local commit_word="Commits"
  [ "$behind" = "1" ] && commit_word="Commit"

  log "[Klon-Aktualitaet] Der ausgecheckte Stand liegt ${behind} ${commit_word} hinter origin/${default_branch}."
  log "Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht."
  log "Vor der Arbeit angleichen, z. B.: git merge origin/${default_branch}  (oder git rebase origin/${default_branch})"
}

main
exit 0
