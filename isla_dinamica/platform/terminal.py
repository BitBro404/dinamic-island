"""Abrir una orden en una terminal, y las herramientas para resolver conflictos de merge (Claude Code, OpenCode
o VS Code). Funciones puras: `which`/`exists` se inyectan para probarlas sin depender de lo instalado."""
import os
import shlex
import shutil

# terminal → cómo se le pasa la carpeta y la orden (lista de argumentos, sin pasar por un shell)
_TERMINALS = (
    ("xfce4-terminal", lambda t, d, cmd: [t, f"--working-directory={d}", "-x", *cmd]),
    ("gnome-terminal", lambda t, d, cmd: [t, f"--working-directory={d}", "--", *cmd]),
    ("kgx", lambda t, d, cmd: [t, f"--working-directory={d}", "--", *cmd]),
    ("konsole", lambda t, d, cmd: [t, "--workdir", d, "-e", *cmd]),
    ("mate-terminal", lambda t, d, cmd: [t, f"--working-directory={d}", "-x", *cmd]),
    ("tilix", lambda t, d, cmd: [t, f"--working-directory={d}", "-e", shlex.join(cmd)]),
    ("kitty", lambda t, d, cmd: [t, "--directory", d, *cmd]),
    ("alacritty", lambda t, d, cmd: [t, "--working-directory", d, "-e", *cmd]),
    ("foot", lambda t, d, cmd: [t, f"--working-directory={d}", *cmd]),
)


def terminal_argv(folder, cmd, which=shutil.which):
    """Argv que abre una terminal en `folder` ejecutando `cmd`; None si no hay ninguna terminal conocida."""
    for name, build in _TERMINALS:
        path = which(name)
        if path:
            return build(path, folder, list(cmd))
    path = which("x-terminal-emulator")
    if path:   # solo admite una cadena con -e: todo va citado para que nada se interprete como orden aparte
        inner = f"cd {shlex.quote(folder)} && exec {shlex.join(cmd)}"
        return [path, "-e", shlex.join(["sh", "-c", inner])]
    return None


def resolvers(which=shutil.which, exists=os.path.exists):
    """Herramientas instaladas para resolver conflictos: {"claude"|"opencode"|"code": ruta}."""
    found = {}
    claude = which("claude") or next((p for p in (os.path.expanduser("~/.local/bin/claude"),
                                                   os.path.expanduser("~/.claude/local/claude")) if exists(p)), None)
    if claude:
        found["claude"] = claude
    opencode = which("opencode") or next((p for p in (os.path.expanduser("~/.opencode/bin/opencode"),)
                                          if exists(p)), None)
    if opencode:
        found["opencode"] = opencode
    code = which("code") or which("codium") or which("cursor")
    if code:
        found["code"] = code
    return found


def conflict_prompt(files, theirs, ours):
    """Instrucción para el asistente: resolver, marcar con git add y dejar el commit al usuario."""
    return (f"Hay un merge en curso: estoy fusionando la rama {theirs} en {ours} y hay conflictos en: "
            f"{', '.join(files)}. Revisa cada archivo, entiende qué cambió en cada rama y resuelve los "
            "conflictos conservando la intención de las dos. Quita todas las marcas <<<<<<< ======= >>>>>>>, "
            "comprueba que el código sigue funcionando (pruebas o build si existen) y marca cada archivo resuelto "
            "con git add. No hagas commit, ni push, ni git merge --abort: lo reviso yo y termino el merge desde la "
            "isla. Al final dime qué decidiste en cada conflicto.")


def resolver_command(tool, tools, repo, files, prompt):
    """Argv de la herramienta elegida. Claude y OpenCode van en terminal (son interactivos); VS Code no."""
    path = tools[tool]
    if tool == "claude":
        return [path, prompt]
    if tool == "opencode":
        return [path, "--prompt", prompt, repo]
    return [path, repo] + [os.path.join(repo, f) for f in files]
