# bash completion for gutenkit
# Install:  cp completions/gutenkit.bash /etc/bash_completion.d/gutenkit
#      or:  source this file from ~/.bashrc

_gutenkit() {
    local cur cmd
    cur="${COMP_WORDS[COMP_CWORD]}"
    local cmds="search info get library list read remove sources index"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$cmds --version --help" -- "$cur") )
        return
    fi

    cmd="${COMP_WORDS[1]}"

    # complete source names after --source
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    if [ "$prev" = "--source" ]; then
        COMPREPLY=( $(compgen -W "gutenberg standardebooks perseus all" -- "$cur") )
        return
    fi

    case "$cmd" in
        search)        COMPREPLY=( $(compgen -W "--source --topic --lang --sort --page --limit --json" -- "$cur") ) ;;
        info)          COMPREPLY=( $(compgen -W "--json" -- "$cur") ) ;;
        get)           COMPREPLY=( $(compgen -W "--format --read" -- "$cur") ) ;;
        library|list)  COMPREPLY=( $(compgen -W "--json" -- "$cur") ) ;;
        remove)        COMPREPLY=( $(compgen -W "--delete-file" -- "$cur") ) ;;
        sources)       COMPREPLY=( $(compgen -W "--json" -- "$cur") ) ;;
        index)         COMPREPLY=( $(compgen -W "perseus --rebuild" -- "$cur") ) ;;
    esac
}
complete -F _gutenkit gutenkit
