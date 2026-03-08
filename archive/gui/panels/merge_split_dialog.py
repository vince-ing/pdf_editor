"""
MergeSplitDialog — modal Tkinter dialog for PDF merge and split operations.

Merge tab  : add / remove / reorder PDF files, then merge → single output.
Split tab  : choose split mode (page ranges, every N pages, single pages),
             configure, then split → output directory.

The dialog is self-contained: it does all file I/O itself and calls an
optional on_open_path callback so the editor can load the result.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src.gui.theme import PALETTE, FONT_UI, FONT_LABEL, FONT_MONO


# ── tiny helpers ──────────────────────────────────────────────────────────────

def _btn(parent, text, cmd, **kw):
    defaults = dict(
        bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
        activebackground=PALETTE["accent_dim"],
        activeforeground=PALETTE["accent_light"],
        font=FONT_LABEL, relief="flat", bd=0,
        padx=10, pady=5, cursor="hand2",
    )
    defaults.update(kw)
    return tk.Button(parent, text=text, command=cmd, **defaults)


def _lbl(parent, text, **kw):
    defaults = dict(bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"], font=FONT_LABEL)
    defaults.update(kw)
    return tk.Label(parent, text=text, **defaults)


def _entry(parent, var, width=38):
    return tk.Entry(
        parent, textvariable=var,
        bg="#252535", fg=PALETTE["fg_primary"],
        insertbackground=PALETTE["fg_primary"],
        relief="flat", highlightthickness=1,
        highlightbackground=PALETTE["border"],
        font=FONT_UI, width=width,
    )


# ═════════════════════════════════════════════════════════════════════════════
#  MergeSplitDialog
# ═════════════════════════════════════════════════════════════════════════════

class MergeSplitDialog:
    """
    Parameters
    ----------
    root : tk.Tk | tk.Toplevel
        Parent window.
    service : MergeSplitService
    current_doc : PDFDocument | None
        If set, split tab is pre-populated with this document.
    on_open_path : callable(str) | None
        Called with the output path after a successful merge so the editor
        can open the result automatically.
    """

    def __init__(self, root, service, current_doc=None, on_open_path=None):
        self._root         = root
        self._service      = service
        self._current_doc  = current_doc
        self._on_open_path = on_open_path

        # Merge state
        self._merge_files: list[str] = []

        # Split state
        self._split_mode_var = tk.StringVar(value="ranges")

        self._build()

    # ── dialog window ─────────────────────────────────────────────────────────

    def _build(self):
        self._win = win = tk.Toplevel(self._root)
        win.title("Merge / Split PDFs")
        win.resizable(False, False)
        win.configure(bg=PALETTE["bg_dark"])
        win.grab_set()

        # Centre on parent
        win.update_idletasks()
        pw = self._root.winfo_rootx()
        py = self._root.winfo_rooty()
        win.geometry(f"660x540+{pw + 60}+{py + 60}")

        # Header
        hdr = tk.Frame(win, bg=PALETTE["bg_mid"], height=40)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⊕ Merge & Split PDFs",
                 bg=PALETTE["bg_mid"], fg=PALETTE["accent_light"],
                 font=("Helvetica", 12, "bold"), padx=16).pack(side=tk.LEFT, fill=tk.Y)

        # Notebook
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Merge.TNotebook",        background=PALETTE["bg_dark"], borderwidth=0)
        style.configure("Merge.TNotebook.Tab",    background=PALETTE["bg_panel"],
                        foreground=PALETTE["fg_secondary"], padding=[14, 6])
        style.map("Merge.TNotebook.Tab",
                  background=[("selected", PALETTE["bg_hover"])],
                  foreground=[("selected", PALETTE["accent_light"])])

        nb = ttk.Notebook(win, style="Merge.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self._merge_tab = tk.Frame(nb, bg=PALETTE["bg_panel"])
        self._split_tab = tk.Frame(nb, bg=PALETTE["bg_panel"])
        nb.add(self._merge_tab, text=" ⊕  Merge ")
        nb.add(self._split_tab, text=" ✂  Split ")

        self._build_merge_tab(self._merge_tab)
        self._build_split_tab(self._split_tab)

        # If no document is open, default to merge tab (already default)
        # If a document is open, select split tab
        if self._current_doc:
            nb.select(1)

        # Status bar
        self._status_lbl = tk.Label(
            win, text="",
            bg=PALETTE["shadow"], fg=PALETTE["success"],
            font=FONT_MONO, anchor="w", padx=12, height=1,
        )
        self._status_lbl.pack(side=tk.BOTTOM, fill=tk.X)

    # ═════════════════════════════════════════════════════════════════════════
    #  MERGE TAB
    # ═════════════════════════════════════════════════════════════════════════

    def _build_merge_tab(self, parent):
        parent.columnconfigure(0, weight=1)

        _lbl(parent, "Add PDF files and drag to reorder. They will be merged top → bottom.",
             wraplength=580, justify="left").pack(anchor="w", padx=16, pady=(14, 6))

        # File list + scrollbar
        list_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._merge_lb = tk.Listbox(
            list_frame,
            bg="#252535", fg=PALETTE["fg_primary"],
            selectbackground=PALETTE["accent_dim"],
            selectforeground=PALETTE["accent_light"],
            activestyle="none",
            font=FONT_UI, relief="flat",
            highlightthickness=1, highlightbackground=PALETTE["border"],
            yscrollcommand=vsb.set,
            height=10,
        )
        self._merge_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self._merge_lb.yview)

        # Drag-to-reorder bindings
        self._merge_lb.bind("<ButtonPress-1>",   self._merge_drag_start)
        self._merge_lb.bind("<B1-Motion>",        self._merge_drag_motion)
        self._merge_lb.bind("<ButtonRelease-1>",  self._merge_drag_end)
        self._merge_drag_idx: int | None = None

        # List action buttons
        btn_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        btn_row.pack(fill=tk.X, padx=16, pady=(2, 8))

        _btn(btn_row, "+ Add Files", self._merge_add_files).pack(side=tk.LEFT, padx=(0, 6))
        _btn(btn_row, "↑ Move Up",   self._merge_move_up).pack(side=tk.LEFT, padx=(0, 6))
        _btn(btn_row, "↓ Move Down", self._merge_move_down).pack(side=tk.LEFT, padx=(0, 6))
        _btn(btn_row, "✕ Remove",    self._merge_remove,
             bg=PALETTE["bg_panel"], fg=PALETTE["danger"]).pack(side=tk.LEFT)

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill=tk.X, padx=16, pady=4)

        # Output path
        out_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        out_row.pack(fill=tk.X, padx=16, pady=(4, 12))
        _lbl(out_row, "Output file:").pack(side=tk.LEFT)

        self._merge_out_var = tk.StringVar()
        _entry(out_row, self._merge_out_var, width=34).pack(side=tk.LEFT, padx=(8, 6))
        _btn(out_row, "Browse…", self._merge_browse_out).pack(side=tk.LEFT)

        # Merge button
        _btn(
            parent, "⊕  Merge PDFs",
            self._do_merge,
            bg=PALETTE["accent"], fg="#FFFFFF",
            activebackground=PALETTE["accent_light"],
            font=("Helvetica", 11, "bold"), pady=8,
        ).pack(padx=16, pady=(0, 12), fill=tk.X)

    # ── merge helpers ─────────────────────────────────────────────────────────

    def _merge_add_files(self):
        paths = filedialog.askopenfilenames(
            title="Add PDF files to merge",
            filetypes=[("PDF Files", "*.pdf"), ("All", "*.*")],
            parent=self._win,
        )
        for p in paths:
            if p not in self._merge_files:
                self._merge_files.append(p)
                self._merge_lb.insert(tk.END, os.path.basename(p))

    def _merge_remove(self):
        sel = self._merge_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        self._merge_lb.delete(idx)
        self._merge_files.pop(idx)

    def _merge_move_up(self):
        sel = self._merge_lb.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        self._merge_files[idx - 1], self._merge_files[idx] = \
            self._merge_files[idx], self._merge_files[idx - 1]
        item = self._merge_lb.get(idx)
        self._merge_lb.delete(idx)
        self._merge_lb.insert(idx - 1, item)
        self._merge_lb.selection_set(idx - 1)

    def _merge_move_down(self):
        sel = self._merge_lb.curselection()
        if not sel or sel[0] >= len(self._merge_files) - 1:
            return
        idx = sel[0]
        self._merge_files[idx], self._merge_files[idx + 1] = \
            self._merge_files[idx + 1], self._merge_files[idx]
        item = self._merge_lb.get(idx)
        self._merge_lb.delete(idx)
        self._merge_lb.insert(idx + 1, item)
        self._merge_lb.selection_set(idx + 1)

    def _merge_browse_out(self):
        p = filedialog.asksaveasfilename(
            title="Save merged PDF",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile="merged.pdf",
            parent=self._win,
        )
        if p:
            self._merge_out_var.set(p)

    # ── merge drag-to-reorder ─────────────────────────────────────────────────

    def _merge_drag_start(self, event):
        self._merge_drag_idx = self._merge_lb.nearest(event.y)

    def _merge_drag_motion(self, event):
        if self._merge_drag_idx is None:
            return
        dst = self._merge_lb.nearest(event.y)
        src = self._merge_drag_idx
        if dst != src:
            # Swap
            self._merge_files[src], self._merge_files[dst] = \
                self._merge_files[dst], self._merge_files[src]
            item_src = self._merge_lb.get(src)
            item_dst = self._merge_lb.get(dst)
            self._merge_lb.delete(src)
            self._merge_lb.insert(src, item_dst)
            self._merge_lb.delete(dst)
            self._merge_lb.insert(dst, item_src)
            self._merge_drag_idx = dst
            self._merge_lb.selection_clear(0, tk.END)
            self._merge_lb.selection_set(dst)

    def _merge_drag_end(self, event):
        self._merge_drag_idx = None

    # ── do merge ──────────────────────────────────────────────────────────────

    def _do_merge(self):
        if len(self._merge_files) < 2:
            messagebox.showwarning("Merge", "Add at least 2 PDF files to merge.", parent=self._win)
            return
        out = self._merge_out_var.get().strip()
        if not out:
            messagebox.showwarning("Merge", "Choose an output file first.", parent=self._win)
            return

        self._win.config(cursor="watch")
        self._win.update()
        try:
            total_pages = self._service.merge_pdfs(self._merge_files, out)
            self._status_lbl.config(
                text=f"✓ Merged {len(self._merge_files)} files → {total_pages} pages: {os.path.basename(out)}",
                fg=PALETTE["success"],
            )
            if messagebox.askyesno(
                "Merge Complete",
                f"Merged {len(self._merge_files)} files into {total_pages} pages.\n\nOpen the merged PDF?",
                parent=self._win,
            ):
                if self._on_open_path:
                    self._on_open_path(out)
                self._win.destroy()
        except Exception as ex:
            messagebox.showerror("Merge Error", str(ex), parent=self._win)
        finally:
            self._win.config(cursor="")

    # ═════════════════════════════════════════════════════════════════════════
    #  SPLIT TAB
    # ═════════════════════════════════════════════════════════════════════════

    def _build_split_tab(self, parent):
        # Source file row
        src_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        src_row.pack(fill=tk.X, padx=16, pady=(14, 6))
        _lbl(src_row, "Source PDF:").pack(side=tk.LEFT)
        self._split_src_var = tk.StringVar()
        _entry(src_row, self._split_src_var, width=32).pack(side=tk.LEFT, padx=(8, 6))
        _btn(src_row, "Browse…", self._split_browse_src).pack(side=tk.LEFT)

        # If a document is already open, pre-fill
        if self._current_doc and self._current_doc.path:
            self._split_src_var.set(self._current_doc.path)

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill=tk.X, padx=16, pady=8)

        # Mode selector
        _lbl(parent, "Split mode:", fg=PALETTE["fg_secondary"]).pack(anchor="w", padx=16)

        modes = [
            ("ranges",  "By page ranges  (e.g. 1-3, 5, 7-9)"),
            ("every_n", "Every N pages"),
            ("single",  "One page per file"),
        ]
        mode_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        mode_frame.pack(fill=tk.X, padx=24, pady=(4, 10))
        for val, label in modes:
            tk.Radiobutton(
                mode_frame, text=label,
                variable=self._split_mode_var, value=val,
                bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                selectcolor=PALETTE["accent_dim"],
                activebackground=PALETTE["bg_hover"],
                activeforeground=PALETTE["accent_light"],
                font=FONT_UI, cursor="hand2",
                command=self._split_mode_changed,
            ).pack(anchor="w", pady=2)

        # Options card (swapped by mode)
        self._split_opts_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        self._split_opts_frame.pack(fill=tk.X, padx=24, pady=4)
        self._split_build_opts_ranges(self._split_opts_frame)

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill=tk.X, padx=16, pady=8)

        # Output directory
        out_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        out_row.pack(fill=tk.X, padx=16, pady=(0, 10))
        _lbl(out_row, "Output folder:").pack(side=tk.LEFT)
        self._split_outdir_var = tk.StringVar()
        _entry(out_row, self._split_outdir_var, width=30).pack(side=tk.LEFT, padx=(8, 6))
        _btn(out_row, "Browse…", self._split_browse_outdir).pack(side=tk.LEFT)

        # Split button
        _btn(
            parent, "✂  Split PDF",
            self._do_split,
            bg=PALETTE["accent"], fg="#FFFFFF",
            activebackground=PALETTE["accent_light"],
            font=("Helvetica", 11, "bold"), pady=8,
        ).pack(padx=16, pady=(0, 12), fill=tk.X)

    # ── split option panels ───────────────────────────────────────────────────

    def _split_mode_changed(self):
        for w in self._split_opts_frame.winfo_children():
            w.destroy()
        mode = self._split_mode_var.get()
        if mode == "ranges":
            self._split_build_opts_ranges(self._split_opts_frame)
        elif mode == "every_n":
            self._split_build_opts_every_n(self._split_opts_frame)
        # single mode has no options

    def _split_build_opts_ranges(self, parent):
        row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        row.pack(fill=tk.X, pady=4)
        _lbl(row, "Page ranges:").pack(side=tk.LEFT)
        self._ranges_var = tk.StringVar()
        _entry(row, self._ranges_var, width=28).pack(side=tk.LEFT, padx=(8, 0))
        _lbl(parent,
             'e.g.  "1-3"  →  one file (pages 1-3)\n'
             '"1-3, 4-6"  →  two files\n'
             '"1, 2, 3"  →  three single-page files',
             fg=PALETTE["fg_dim"], font=("Helvetica", 8), justify="left",
        ).pack(anchor="w", pady=(2, 0))

    def _split_build_opts_every_n(self, parent):
        row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        row.pack(fill=tk.X, pady=4)
        _lbl(row, "Pages per file:").pack(side=tk.LEFT)
        self._every_n_var = tk.IntVar(value=1)
        tk.Spinbox(
            row, from_=1, to=9999, textvariable=self._every_n_var,
            width=6,
            bg="#252535", fg=PALETTE["fg_primary"],
            buttonbackground=PALETTE["border"],
            relief="flat", highlightthickness=0,
        ).pack(side=tk.LEFT, padx=(8, 0))

    # ── split helpers ─────────────────────────────────────────────────────────

    def _split_browse_src(self):
        p = filedialog.askopenfilename(
            title="Select PDF to split",
            filetypes=[("PDF Files", "*.pdf"), ("All", "*.*")],
            parent=self._win,
        )
        if p:
            self._split_src_var.set(p)

    def _split_browse_outdir(self):
        d = filedialog.askdirectory(title="Select output folder", parent=self._win)
        if d:
            self._split_outdir_var.set(d)

    def _parse_ranges(self, raw: str, page_count: int) -> list[tuple[int, int]]:
        """Parse '1-3, 5, 7-9' into [(0,2),(4,4),(6,8)] (0-based, inclusive)."""
        ranges = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                first = int(a.strip()) - 1
                last  = int(b.strip()) - 1
            else:
                first = last = int(part) - 1
            if first < 0 or last >= page_count or first > last:
                raise ValueError(
                    f"Range '{part}' is out of bounds for a {page_count}-page document."
                )
            ranges.append((first, last))
        if not ranges:
            raise ValueError("No valid ranges found.")
        return ranges

    # ── do split ──────────────────────────────────────────────────────────────

    def _do_split(self):
        import fitz as _fitz
        src_path = self._split_src_var.get().strip()
        if not src_path or not os.path.isfile(src_path):
            messagebox.showwarning("Split", "Choose a valid source PDF first.", parent=self._win)
            return
        out_dir = self._split_outdir_var.get().strip()
        if not out_dir:
            messagebox.showwarning("Split", "Choose an output folder first.", parent=self._win)
            return

        # Use the already-open doc if paths match; otherwise open a temporary one
        if (self._current_doc and self._current_doc.path and
                os.path.abspath(src_path) == os.path.abspath(self._current_doc.path)):
            doc = self._current_doc
            own_doc = False
        else:
            from src.core.document import PDFDocument
            doc = PDFDocument(src_path)
            own_doc = True

        self._win.config(cursor="watch")
        self._win.update()
        try:
            mode     = self._split_mode_var.get()
            base     = os.path.splitext(os.path.basename(src_path))[0]

            if mode == "single":
                paths = self._service.split_pdf_single_pages(doc, out_dir, base_name=base)
                msg   = f"✓ Split into {len(paths)} single-page files → {out_dir}"

            elif mode == "every_n":
                n     = self._every_n_var.get()
                paths = self._service.split_pdf_every_n(doc, n, out_dir, base_name=base)
                msg   = f"✓ Split into {len(paths)} files (≤{n} pages each) → {out_dir}"

            else:  # ranges
                raw = self._ranges_var.get().strip()
                if not raw:
                    messagebox.showwarning("Split", "Enter page ranges first.", parent=self._win)
                    return
                try:
                    ranges = self._parse_ranges(raw, doc.page_count)
                except ValueError as ex:
                    messagebox.showerror("Range Error", str(ex), parent=self._win)
                    return
                pad = len(str(len(ranges)))
                output_paths = [
                    os.path.join(out_dir, f"{base}_part{str(i+1).zfill(pad)}.pdf")
                    for i in range(len(ranges))
                ]
                counts = self._service.split_pdf_by_range(doc, ranges, output_paths)
                msg = (
                    f"✓ Split into {len(ranges)} file(s)  "
                    f"({', '.join(str(c) for c in counts)} pages)  → {out_dir}"
                )

            self._status_lbl.config(text=msg, fg=PALETTE["success"])
            messagebox.showinfo("Split Complete", msg.lstrip("✓ "), parent=self._win)
        except Exception as ex:
            messagebox.showerror("Split Error", str(ex), parent=self._win)
        finally:
            if own_doc:
                doc.close()
            self._win.config(cursor="")