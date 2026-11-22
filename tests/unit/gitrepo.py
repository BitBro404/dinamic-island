"""Repos git temporales para las pruebas (sin red, sin firmar commits, sin tocar la config del usuario)."""
import os
import subprocess
import tempfile

GIT = ["git", "-c", "commit.gpgsign=false", "-c", "user.name=Prueba", "-c", "user.email=prueba@example.invalid",
       "-c", "init.defaultBranch=main", "-c", "advice.detachedHead=false"]


def git(cwd, *args):
    r = subprocess.run(GIT + list(args), cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr}")
    return r.stdout


def commit(cwd, name, text="x", msg=None):
    with open(os.path.join(cwd, name), "w") as f:
        f.write(text)
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", msg or f"añade {name}")


class Repos:
    """Remoto «bare» + clon de trabajo con main subido. `self.work` es el repo que usa la isla."""
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.remote = os.path.join(self.tmp.name, "remote.git")
        self.work = os.path.join(self.tmp.name, "work")
        git(self.tmp.name, "init", "-q", "--bare", self.remote)
        git(self.tmp.name, "clone", "-q", self.remote, self.work)
        commit(self.work, "a.txt", msg="inicio")
        git(self.work, "push", "-q", "-u", "origin", "main")
        git(self.remote, "symbolic-ref", "HEAD", "refs/heads/main")
        git(self.work, "remote", "set-head", "origin", "main")

    def cleanup(self):
        self.tmp.cleanup()
