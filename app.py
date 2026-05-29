import os
import shutil
import errno
import datetime
import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

import yaml
from flask import (
    Flask, render_template, request, redirect, url_for, abort, Response, flash
)

app = Flask(__name__)
    
def _load_secret_key() -> str:
    try:
        with open("/app/.secret_key") as f:
            return f.read().strip()
    except Exception:
        return os.environ.get("APP_SECRET", "change-me")

app.secret_key = _load_secret_key()

DATA_ROOT = "/data"
CONFIG_PATH = "/config/config.yml"

LOG_DIR = Path("/config/logs")
LOG_PREFIX = "hardlink"
LOG_RETENTION_DAYS = 7


# -----------------------
# Config
# -----------------------
def load_config() -> dict:
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


CONFIG = load_config()
OWN_UID = int(CONFIG.get("ownership", {}).get("uid"))
OWN_GID = int(CONFIG.get("ownership", {}).get("gid"))


def mergerfs_enabled() -> bool:
    return bool(CONFIG.get("mergerfs", {}).get("enabled", True))


# -----------------------
# Auth
# -----------------------
def auth_enabled() -> bool:
    return bool(CONFIG.get("auth", {}).get("enabled"))


def check_auth(auth) -> bool:
    a = CONFIG.get("auth", {})
    return auth and auth.username == a.get("username") and auth.password == a.get("password")


@app.before_request
def require_basic_auth():
    if not auth_enabled():
        return
    auth = request.authorization
    if not check_auth(auth):
        return Response(
            "Authentication required",
            401,
            {"WWW-Authenticate": 'Basic realm="Hardlink Web"'},
        )


# -----------------------
# Logging + ownership helpers
# -----------------------
def safe_chown(path: str) -> None:
    try:
        if os.path.islink(path):
            return
        os.chown(path, OWN_UID, OWN_GID)
    except Exception:
        pass


def mkdirs_and_chown(dir_path: str) -> None:
    """
    mkdir -p and chown any directories created (best effort).
    """
    dir_path = os.path.realpath(dir_path)
    parts = dir_path.split(os.sep)

    cur = os.sep
    for part in parts[1:]:
        if not part:
            continue
        cur = os.path.join(cur, part)
        if not os.path.exists(cur):
            os.mkdir(cur)
            safe_chown(cur)


def cleanup_old_logs() -> None:
    cutoff = datetime.datetime.now() - datetime.timedelta(days=LOG_RETENTION_DAYS)
    for p in LOG_DIR.glob(f"{LOG_PREFIX}-*.log"):
        try:
            date_part = p.stem.replace(f"{LOG_PREFIX}-", "")
            d = datetime.datetime.strptime(date_part, "%Y-%m-%d")
            if d < cutoff:
                p.unlink(missing_ok=True)
        except Exception:
            pass


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe_chown(str(LOG_DIR))

    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    logfile = LOG_DIR / f"{LOG_PREFIX}-{date_str}.log"

    line = f"[{now.strftime('%H:%M:%S')}] {msg}"
    with logfile.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

    safe_chown(str(logfile))
    cleanup_old_logs()
    print(line, flush=True)


# -----------------------
# Path helpers
# -----------------------
def norm_rel(p: str) -> str:
    return (p or "").strip().replace("\\", "/").lstrip("/").strip("/")


def safe_join(root: str, rel: str) -> str:
    rel = norm_rel(rel)
    root_real = os.path.realpath(root)
    full = os.path.realpath(os.path.join(root_real, rel))
    if not (full == root_real or full.startswith(root_real + os.sep)):
        raise ValueError("Path escape blocked")
    return full


def is_under(path: str, root: str) -> bool:
    rr = os.path.realpath(root)
    rp = os.path.realpath(path)
    return rp == rr or rp.startswith(rr + os.sep)


def rel_from_root(full: str) -> str:
    root_real = os.path.realpath(DATA_ROOT)
    full_real = os.path.realpath(full)
    if full_real == root_real:
        return ""
    if not full_real.startswith(root_real + os.sep):
        raise ValueError("Not under /data")
    return full_real[len(root_real) + 1 :]


def unique_path(dest_path: str) -> str:
    if not os.path.exists(dest_path):
        return dest_path
    base, ext = os.path.splitext(dest_path)
    i = 2
    while True:
        cand = f"{base} ({i}){ext}"
        if not os.path.exists(cand):
            return cand
        i += 1


# -----------------------
# Filename helpers (rename feature)
# -----------------------
def safe_filename(name: str) -> str:
    """
    Make sure the user cannot inject paths. Only a basename is allowed.
    """
    name = (name or "").strip().replace("\\", "/")
    name = name.split("/")[-1]  # basename only
    name = name.strip()
    if not name or name in (".", ".."):
        raise ValueError("Invalid filename")
    return name


def clean_filename(name: str) -> str:
    """
    Dots/underscores -> spaces, collapse whitespace. Keeps extension.
    """
    base, ext = os.path.splitext(name)
    base = base.replace(".", " ").replace("_", " ")
    base = re.sub(r"\s+", " ", base).strip()
    return base + ext


# -----------------------
# Directory listing
# -----------------------
@dataclass
class FileEntry:
    name: str
    rel_under_dir: str
    size: int


def list_dirs(rel_dir: str) -> List[Tuple[str, str]]:
    rel_dir = norm_rel(rel_dir)
    full = safe_join(DATA_ROOT, rel_dir)
    out: List[Tuple[str, str]] = []
    try:
        for name in sorted(os.listdir(full), key=str.lower):
            p = os.path.join(full, name)
            if os.path.isdir(p):
                out.append((name, norm_rel(os.path.join(rel_dir, name))))
    except Exception:
        pass
    return out


def list_files(rel_dir: str) -> List[FileEntry]:
    rel_dir = norm_rel(rel_dir)
    full = safe_join(DATA_ROOT, rel_dir)
    out: List[FileEntry] = []
    try:
        for name in sorted(os.listdir(full), key=str.lower):
            p = os.path.join(full, name)
            if os.path.isfile(p):
                out.append(FileEntry(name=name, rel_under_dir=name, size=os.stat(p).st_size))
    except Exception:
        pass
    return out


# -----------------------
# mergerfs xattr helpers
# -----------------------
def get_xattr_str(path: str, attr: str) -> str:
    try:
        val = os.getxattr(path, attr)
        return val.decode("utf-8", errors="replace").strip("\x00")
    except OSError as e:
        raise OSError(f"Cannot read xattr '{attr}' on '{path}': {e}") from e


def mergerfs_basepath(pool_path: str) -> str:
    return get_xattr_str(pool_path, "user.mergerfs.basepath")


def mergerfs_fullpath(pool_path: str) -> str:
    return get_xattr_str(pool_path, "user.mergerfs.fullpath")


def pool_to_same_branch_dest(basepath: str, dest_pool_path: str) -> str:
    """
    Convert a destination under /data to an absolute destination on the SAME branch
    by prefixing with mergerfs basepath (host absolute path). Container must see it.
    """
    if not is_under(dest_pool_path, DATA_ROOT):
        raise ValueError("Destination not under /data")

    base = os.path.realpath(basepath)
    if not os.path.isabs(base):
        raise ValueError(f"Source basepath '{basepath}' is not absolute")

    if not os.path.isdir(base):
        raise ValueError(
            f"Source basepath '{basepath}' is not visible in container. "
            f"Mount your raw branches so '{basepath}' exists in-container."
        )

    dest_rel = rel_from_root(dest_pool_path)
    return os.path.join(base, dest_rel)


# -----------------------
# Routes
# -----------------------
@app.get("/")
def home():
    return redirect(url_for("link_page"))


@app.get("/link")
def link_page():
    src = norm_rel(request.args.get("src", ""))
    dst = norm_rel(request.args.get("dst", ""))
    mode = request.args.get("mode", "flatten")
    conflict = request.args.get("conflict", "suffix")

    files = list_files(src) if src else []

    return render_template(
        "link.html",
        title="Hardlink",
        browse_root=DATA_ROOT,
        src=src,
        dst=dst,
        mode=mode,
        conflict=conflict,
        files=files,
    )


@app.get("/browse")
def browse():
    kind = request.args.get("kind", "src")
    path = norm_rel(request.args.get("path", ""))
    back = request.args.get("back", "link")

    src = norm_rel(request.args.get("src", ""))
    dst = norm_rel(request.args.get("dst", ""))
    mode = request.args.get("mode", "flatten")
    conflict = request.args.get("conflict", "suffix")

    dirs = list_dirs(path)

    parts = [p for p in path.split("/") if p]
    crumbs = [("Root", "")]
    acc = ""
    for p in parts:
        acc = f"{acc}/{p}" if acc else p
        crumbs.append((p, acc))

    return render_template(
        "browse.html",
        title="Browse",
        browse_root=DATA_ROOT,
        kind=kind,
        path=path,
        dirs=dirs,
        crumbs=crumbs,
        back=back,
        src=src,
        dst=dst,
        mode=mode,
        conflict=conflict,
    )


@app.post("/renamefolder")
def renamefolder():
    path = norm_rel(request.form.get("path", ""))
    new_name = (request.form.get("new_name", "") or "").strip()

    if not path:
        abort(400, "Cannot rename root")
    
    if not new_name or "/" in new_name or new_name in (".", ".."):
        abort(400, "Invalid folder name")

    # Get parent directory and current folder name
    path_full = safe_join(DATA_ROOT, path)
    parent_full = os.path.dirname(path_full)
    old_name = os.path.basename(path_full)

    if not os.path.isdir(path_full):
        abort(400, "Not a directory")

    # Check that new name doesn't already exist
    new_full = os.path.join(parent_full, new_name)
    if os.path.exists(new_full):
        abort(400, "Name already exists")

    # Rename the folder
    try:
        os.rename(path_full, new_full)
        safe_chown(new_full)
        log(f"RENAME: '{path}' → '{new_name}'")
    except OSError as e:
        abort(400, f"Cannot rename: {e}")

    # Build new folder path for redirect
    new_folder_rel = rel_from_root(new_full)
    
    # Preserve browse context in redirect
    kind = request.form.get("kind", "dst")
    back = request.form.get("back", "link")
    src = request.form.get("src", "")
    dst = request.form.get("dst", "")
    base = request.form.get("base", "")
    selected = request.form.get("selected", "")
    mode = request.form.get("mode", "flatten")
    conflict = request.form.get("conflict", "suffix")
    dest = request.form.get("dest", "")
    
    return redirect(url_for("browse", kind=kind, path=new_folder_rel, back=back, src=src, dst=dst, 
                           base=base, selected=selected, mode=mode, conflict=conflict, dest=dest))


@app.post("/mkfolder")
def mkfolder():
    parent = norm_rel(request.form.get("parent", ""))
    name = (request.form.get("name", "") or "").strip()

    if not name or "/" in name or name in (".", ".."):
        abort(400, "Invalid folder name")

    parent_full = safe_join(DATA_ROOT, parent)
    new_full = os.path.join(parent_full, name)

    mkdirs_and_chown(new_full)
    log(f"MKDIR: {parent}/{name}")

    # Build the new folder path
    new_path = os.path.join(parent, name) if parent else name
    new_path = norm_rel(new_path)
    
    # Preserve browse context in redirect
    kind = request.form.get("kind", "dst")
    back = request.form.get("back", "link")
    src = request.form.get("src", "")
    dst = request.form.get("dst", "")
    base = request.form.get("base", "")
    selected = request.form.get("selected", "")
    mode = request.form.get("mode", "flatten")
    conflict = request.form.get("conflict", "suffix")
    dest = request.form.get("dest", "")
    
    return redirect(url_for("browse", kind=kind, path=new_path, back=back, src=src, dst=dst, 
                           base=base, selected=selected, mode=mode, conflict=conflict, dest=dest))


@app.post("/hardlink")
def do_hardlink():
    src = norm_rel(request.form.get("src", ""))
    dst = norm_rel(request.form.get("dst", ""))
    mode = request.form.get("mode", "flatten")
    conflict = request.form.get("conflict", "suffix")
    selected = request.form.getlist("selected")

    # UI uses name="clean" value="1"
    clean_names = (request.form.get("clean") == "1")

    # Build rename map from UI fields:
    # rename_key_<i> -> original rel path
    # rename_<i>     -> desired name (optional)
    rename_map = {}
    for k, v in request.form.items():
        if not k.startswith("rename_key_"):
            continue
        idx = k[11:]  # everything after "rename_key_" prefix
        orig = (v or "").replace("\\", "/").lstrip("/")
        new_name = (request.form.get(f"rename_{idx}", "") or "").strip()
        if orig:
            rename_map[orig] = new_name

    if not selected:
        flash("No files selected.")
        return redirect(url_for("link_page", src=src, dst=dst, mode=mode, conflict=conflict, clean=("1" if clean_names else "")))

    src_dir_pool = safe_join(DATA_ROOT, src)
    dst_dir_pool = safe_join(DATA_ROOT, dst)
    os.makedirs(dst_dir_pool, exist_ok=True)

    results, errors = [], []
    log(f"HARDLINK: src='{src}' dst='{dst}' mode='{mode}' conflict='{conflict}' clean={clean_names} count={len(selected)}")

    for rel_under in selected:
        rel_under = (rel_under or "").replace("\\", "/").lstrip("/")
        try:
            src_pool = os.path.realpath(os.path.join(src_dir_pool, rel_under))
            if not is_under(src_pool, src_dir_pool):
                raise ValueError("Selection escape blocked")
            if not os.path.isfile(src_pool):
                raise FileNotFoundError("Not a file")

            # ----- Rename logic -----
            original_base = os.path.basename(rel_under)
            original_root, original_ext = os.path.splitext(original_base)

            requested = (rename_map.get(rel_under, "") or "").strip()

            if requested:
                # Sanitize, but allow user to omit extension
                requested = safe_filename(requested)

                req_root, req_ext = os.path.splitext(requested)
                if req_ext:
                    desired = requested  # user supplied extension
                else:
                    desired = requested + original_ext  # preserve original extension
            else:
                desired = safe_filename(original_base)

            # Optional "clean filenames" pass (you said: “just that, no brackets”)
            # Apply to the stem only, then re-attach ext to avoid mangling it.
            if clean_names:
                stem, ext = os.path.splitext(desired)
                desired = safe_filename(clean_filename(stem) + ext)

            # Build pool destination path
            if mode == "preserve":
                dest_pool = os.path.join(dst_dir_pool, os.path.dirname(rel_under), desired)
            else:
                dest_pool = os.path.join(dst_dir_pool, desired)

            # Resolve real paths on same branch (mergerfs mode)
            if mergerfs_enabled():
                try:
                    basep = mergerfs_basepath(src_pool)
                    src_real = mergerfs_fullpath(src_pool)
                    dest_real = pool_to_same_branch_dest(basep, os.path.realpath(dest_pool))
                except OSError as e:
                    raise ValueError(
                        f"Mergerfs xattr error (file not on mergerfs pool?): {e}"
                    ) from e
            else:
                src_real = src_pool
                dest_real = os.path.realpath(dest_pool)

            # Conflict handling
            final_dest = dest_real
            if os.path.exists(final_dest):
                if conflict == "skip":
                    results.append((rel_under, "skipped (exists)"))
                    continue
                if conflict == "overwrite":
                    if os.path.isdir(final_dest):
                        shutil.rmtree(final_dest)
                    else:
                        os.remove(final_dest)
                else:
                    final_dest = unique_path(final_dest)

            mkdirs_and_chown(os.path.dirname(final_dest))
            os.link(src_real, final_dest)
            safe_chown(final_dest)

            results.append((rel_under, f"linked → {final_dest}"))
            log(f"OK: '{src_real}' -> '{final_dest}'")

        except OSError as e:
            if e.errno == errno.EXDEV:
                errors.append((rel_under, "EXDEV: different underlying filesystem (branch mismatch)."))
            else:
                errors.append((rel_under, f"{type(e).__name__}: {e}"))
            log(f"ERR: {rel_under}: {repr(e)}")
        except Exception as e:
            errors.append((rel_under, f"{type(e).__name__}: {e}"))
            log(f"ERR: {rel_under}: {repr(e)}")

    return render_template(
        "result.html",
        title="Results",
        back_url=url_for("link_page", src=src, dst=dst, mode=mode, conflict=conflict, clean=("1" if clean_names else "")),
        results=results,
        errors=errors,
    )


if __name__ == "__main__":
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe_chown(str(LOG_DIR))
    cleanup_old_logs()
    log("Starting hardlink-web on 0.0.0.0:8088")
    app.run(host="0.0.0.0", port=8088, debug=False)

