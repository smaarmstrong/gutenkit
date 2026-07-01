# bash completion for gutenkit
# Install:  cp completions/gutenkit.bash /etc/bash_completion.d/gutenkit
#      or:  source this file from ~/.bashrc

_gutenkit() {
    local cur cmd
    cur="${COMP_WORDS[COMP_CWORD]}"
    local cmds="search info get library list read remove"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$cmds --version --help" -- "$cur") )
        return
    fi

    cmd="${COMP_WORDS[1]}"
    case "$cmd" in
        search)        COMPREPLY=( $(compgen -W "--topic --lang --sort --page --limit --json" -- "$cur") ) ;;
        info)          COMPREPLY=( $(compgen -W "--json" -- "$cur") ) ;;
        get)           COMPREPLY=( $(compgen -W "--format --read" -- "$cur") ) ;;
        library|list)  COMPREPLY=( $(compgen -W "--json" -- "$cur") ) ;;
        remove)        COMPREPLY=( $(compgen -W "--delete-file" -- "$cur") ) ;;
    esac
}
complete -F _gutenkit gutenkit
